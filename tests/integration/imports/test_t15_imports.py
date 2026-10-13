"""Independent T15 real-PG candidate, authority and transactional acceptance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest
from alembic import command
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.admin.imports.models import ImportsBase, ImportBatch, ImportCandidateRow, ImportRowError
from services.api.app.admin.imports.store import migrate_imports, migration_config
from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion
from services.api.app.admin.sources.schemas import SourcePolicy, SourceRevisionInput
from services.api.app.admissions_catalog.models import (CatalogDataset, CatalogInstitution, CatalogProgram,
    AdmissionOffering, AdmissionOfferingVersion)
from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthSession, AuthUser, AuthUserRole
from services.api.app.idempotency.models import IdempotencyRecord
from services.api.app.ingestion.schemas import ImportsPolicy
from services.api.app.privacy.models import PrivacyAdmissionRecord
from services.api.app.storage.models import StorageObject


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T15_REJECTED_RAW_SECRET_SENTINEL"
KEY = SecretStr("DEMO_T15_IMPORT_KEY")


def denied(operation, expected):
    with pytest.raises(ValueError) as failure:
        operation()
    assert getattr(failure.value, "status_code", None) in ((expected,) if isinstance(expected, int) else expected)
    assert SENTINEL not in str(failure.value) + repr(failure.value)
    assert KEY.get_secret_value() not in str(failure.value)
    return failure.value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns)).mappings().all()


def successes(engine):
    return {row["id"] for row in rows(engine, AuditEvent) if row["outcome"] == "succeeded"}


def invoke(case, *, request=None, key=KEY):
    return case.service.import_file(case.admin.principal, request or case.request(), key)


def wait_for_block(engine, started, pid, blocker):
    assert started.wait(5)
    deadline, pause = monotonic() + 5, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE pid=:pid "
                "AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid))"),
                {"pid": pid[0], "blocker": blocker}):
                return
            pause.wait(0.01)
    pytest.fail("No actual PostgreSQL import lock contention observed")


@pytest.mark.parametrize("format", ["json", "csv"])
def test_real_typed_file_is_staged_unresolved_and_same_key_replays(format, import_case_factory,
        candidate_factory, pg_engine, io_probe):
    case = import_case_factory(format=format, rows=[candidate_factory(), candidate_factory(
        field_key="language_requirement", value_kind="text", value_text="DEMO_T15_LANGUAGE_NOTE",
        unit=None, footnote_state="unknown"), candidate_factory(
        source_record_reference="DEMO_T15_RECORD_TWO", field_key="subject_requirement",
        value_kind="text", value_text="DEMO_T15_SUBJECT_NOTE", unit=None)])
    # Governance administrators need strong identity, not a fabricated student
    # age/core-consent record. These inputs contain no real students.
    assert rows(pg_engine, PrivacyAdmissionRecord) == []
    first = invoke(case)
    second = invoke(case)
    assert first.status == "staged" and first.total_rows == first.staged_rows == 3
    assert first.error_count == 0 and not first.replayed and second.replayed
    assert first.id == second.id and len(rows(pg_engine, ImportBatch)) == 1
    assert len(rows(pg_engine, IdempotencyRecord)) == 1
    candidates = rows(pg_engine, ImportCandidateRow)
    assert len(candidates) == 3 and len({row["source_record_reference"] for row in candidates}) == 2
    assert sum(row["source_record_reference"] == "DEMO_T15_RECORD" for row in candidates) == 2
    assert {row["value_text"] for row in candidates} == {"600.00", "DEMO_T15_LANGUAGE_NOTE", "DEMO_T15_SUBJECT_NOTE"}
    assert {row["row_number"] for row in candidates} == ({1, 2, 3} if format == "json" else {2, 3, 4})
    assert all(row["review_state"] == "draft" and row["evidence_state"] == "unresolved"
        and row["locator"] is None and row["entry_year"] == 2026 and row["offering_version"] == 1
        for row in candidates)
    assert io_probe.read_count >= 2 and rows(pg_engine, PrivacyAdmissionRecord) == []


def test_natural_dedup_survives_other_keys_receipt_expiry_and_file_copy(import_case_factory,
        pg_engine, clock):
    case = import_case_factory(ttl_seconds=1)
    first = invoke(case)
    clock.advance(1)
    after_expiry = invoke(case)
    copy = case.upload()
    other = invoke(case, request=case.request(copy), key=SecretStr("DEMO_T15_DIFFERENT_KEY"))
    assert first.id == after_expiry.id == other.id
    assert len(rows(pg_engine, ImportBatch)) == len(rows(pg_engine, ImportCandidateRow)) == 1
    assert rows(pg_engine, ImportBatch)[0]["file_id"] == case.file.id
    assert copy.id != case.file.id


def test_new_copy_cannot_revive_expired_or_deleted_original_file(import_case_factory, pg_engine, clock):
    for lost in ("expired", "deleted", "deleted_batch"):
        case = import_case_factory()
        original = invoke(case)
        copy = case.upload()
        with Session(pg_engine) as session, session.begin():
            if lost == "expired":
                session.get(StorageObject, case.file.id).expires_at = clock() + timedelta(seconds=1)
            elif lost == "deleted":
                session.get(StorageObject, case.file.id).status = "deleted"
            else:
                session.get(ImportBatch, original.id).status = "deleted"
        if lost == "expired":
            clock.advance(1)
        before = rows(pg_engine, ImportBatch)
        denied(lambda: invoke(case, request=case.request(copy), key=SecretStr("DEMO_T15_COPY_NEW_KEY")), (403, 404, 409))
        denied(lambda: case.service.get_import(case.admin.principal, original.id), (403, 404, 409))
        assert rows(pg_engine, ImportBatch) == before


def test_bad_row_rejects_whole_batch_and_persists_only_closed_errors(import_case_factory,
        candidate_factory, pg_engine):
    for fault in ("bad_decimal", "footnote_missing", "injected_field"):
        good = candidate_factory(source_record_reference="DEMO_T15_GOOD")
        bad = candidate_factory(source_record_reference="DEMO_T15_BAD")
        if fault == "bad_decimal":
            bad["value_text"] = SENTINEL
        elif fault == "footnote_missing":
            del bad["footnote_state"]
        else:
            bad["reviewed"] = SENTINEL
        case = import_case_factory(rows=[good, bad])
        result = invoke(case)
        assert result.status == "rejected" and result.total_rows == 2 and result.staged_rows == 0
        assert result.errors and all(error.row_number == 2 for error in result.errors)
        assert SENTINEL not in str(result.model_dump())
        assert rows(pg_engine, ImportCandidateRow) == []
        batch = next(row for row in rows(pg_engine, ImportBatch) if row["id"] == result.id)
        assert not {"raw", "payload", "body", "error_message"} & set(batch)
        errors = [row for row in rows(pg_engine, ImportRowError) if row["import_id"] == result.id]
        assert all(set(row) == {"import_id", "row_number", "field", "code"} for row in errors)
        assert SENTINEL not in str(errors) + str(batch)
        assert invoke(case).id == result.id


def test_structural_csv_failure_keeps_unknown_total_without_raw_report(import_case_factory, pg_engine, monkeypatch):
    case = import_case_factory(format="csv", data=("wrong_header\n" + SENTINEL + "\n").encode())
    result = invoke(case)
    assert result.status == "rejected" and result.total_rows is None and result.staged_rows == 0
    assert result.errors and all(error.row_number == 0 for error in result.errors)
    assert SENTINEL not in str(result.model_dump()) + str(rows(pg_engine, ImportRowError))
    # T14 accepts a quarantined, syntactically valid JSON file larger than
    # T15's synchronous limit. T15 must reject it before any receipt/batch.
    oversized = import_case_factory(data=b'["DEMO_' + b'x' * 1048576 + b'"]')
    batches, receipts = rows(pg_engine, ImportBatch), rows(pg_engine, IdempotencyRecord)
    def unexpected_claim(*args, **kwargs):
        pytest.fail("An oversized import must not begin an idempotency operation", pytrace=False)
    monkeypatch.setattr(oversized.service.idempotency_service, "execute", unexpected_claim)
    denied(lambda: invoke(oversized), 422)
    assert rows(pg_engine, ImportBatch) == batches and rows(pg_engine, IdempotencyRecord) == receipts


def test_offering_version_year_and_dataset_never_inferred(import_case_factory, candidate_factory,
        pg_engine, catalog_tree):
    originals = {model.__tablename__: rows(pg_engine, model) for model in (
        CatalogDataset, CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion)}
    for changed in ({"entry_year": 2025}, {"offering_version": 99}, {"offering_id": str(uuid4())}):
        case = import_case_factory(rows=[candidate_factory(**changed)])
        result = invoke(case)
        assert result.status == "rejected" and result.staged_rows == 0
        assert any(error.code == "SCOPE_MISMATCH" for error in result.errors)
    assert rows(pg_engine, ImportCandidateRow) == []
    for model in (CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion):
        assert rows(pg_engine, model) == originals[model.__tablename__]
    # Source registration changes the dataset governance revision; row rejection
    # must still preserve the original offering scope/year/current pointer.
    assert rows(pg_engine, AdmissionOffering)[0]["entry_year"] == 2026


def test_request_exact_file_source_hash_format_and_dynamic_dto_are_enforced(import_case_factory,
        pg_engine, io_probe):
    case = import_case_factory()
    valid = case.request()
    for changes in ({"dataset_id": uuid4()}, {"source_id": uuid4()}, {"source_version": 2},
            {"file_sha256": "0" * 64}, {"format": "csv"}):
        denied(lambda: invoke(case, request=case.request(**changes)), (403, 404, 409, 422))
    before = io_probe.read_count
    for changes in ({"source_version": True}, {"role": "data_admin"}, {"is_synthetic": False}):
        forged = valid.model_copy(update=changes)
        denied(lambda: invoke(case, request=forged), 422)
    assert io_probe.read_count == before and rows(pg_engine, ImportBatch) == []


def test_current_role_mfa_session_manual_permission_and_latest_version(import_case_factory,
        pg_engine, clock):
    for withdrawn in ("role", "mfa", "session", "permission", "source_version"):
        case = import_case_factory()
        original = invoke(case)
        if withdrawn in {"permission", "source_version"}:
            with Session(pg_engine) as session:
                revision = session.get(CatalogDataset, case.source.dataset_id).revision
            definition = case.source_request.definition.model_copy(update={"manual_import_permission": "denied",
                "manual_import_enabled": False}) if withdrawn == "permission" else case.source_request.definition
            case.storage.source_service.revise_source(case.admin.principal,
                SourceRevisionInput(source_id=case.source.source_id, definition=definition),
                expected_dataset_revision=revision, expected_source_version=case.source.version)
        else:
            with Session(pg_engine) as session, session.begin():
                if withdrawn == "role":
                    session.get(AuthUserRole, (case.admin.actor.user_id, "data_admin")).revoked_at = clock()
                elif withdrawn == "mfa":
                    session.get(AuthSession, case.admin.actor.session_id).assurance_amr = ["pwd"]
                else:
                    session.get(AuthSession, case.admin.actor.session_id).revoked_at = clock()
        before = rows(pg_engine, ImportBatch)
        denied(lambda: invoke(case), (401, 403, 404, 409))
        denied(lambda: case.service.get_import(case.admin.principal, original.id), (401, 403, 404, 409))
        assert rows(pg_engine, ImportBatch) == before


def test_other_admin_or_forged_principal_has_no_batch_access(import_case_factory, administrator_factory,
        pg_engine):
    case = import_case_factory()
    result = invoke(case)
    stranger = administrator_factory()
    # Source-file access requires this source version's responsible actor;
    # a strong role alone does not grant access to the bound batch.
    assert stranger.actor.user_id != case.source.responsible_user_id
    denied(lambda: case.service.get_import(stranger.principal, result.id), (403, 404))
    forged = case.admin.principal.model_copy(update={"user_id": stranger.actor.user_id})
    denied(lambda: case.service.get_import(forged, result.id), 401)
    denied(lambda: case.service.get_import(case.admin.principal, uuid4()), 404)
    assert len(rows(pg_engine, ImportBatch)) == 1


def test_same_key_changed_file_conflicts_new_content_keeps_old_batch(import_case_factory,
        candidate_factory, pg_engine):
    from tests.integration.imports.conftest import serialize_rows
    case = import_case_factory()
    original = invoke(case)
    changed = case.upload(serialize_rows([candidate_factory(value_text="601.00")], "json"))
    request = case.request(changed)
    denied(lambda: invoke(case, request=request), 409)
    assert len(rows(pg_engine, ImportBatch)) == 1
    new = invoke(case, request=request, key=SecretStr("DEMO_T15_NEW_CONTENT"))
    assert new.id != original.id
    assert {row["value_text"] for row in rows(pg_engine, ImportCandidateRow)} == {"600.00", "601.00"}


def test_metadata_and_required_audit_use_same_t49_transaction(import_case_factory, monkeypatch, pg_engine):
    case = import_case_factory()
    observed, metadata, prelude = [], [], []
    idempotency = case.service.idempotency_service
    real_execute = idempotency.execute
    def tracked_execute(*args, **kwargs):
        assert prelude and all(not session.in_transaction() for session in prelude)
        for name in ("perform", "verify_resource"):
            original = kwargs[name]
            def tracked(session, *values, original=original):
                observed.append((session, session.get_transaction(), session.connection()))
                return original(session, *values)
            kwargs[name] = tracked
        return real_execute(*args, **kwargs)
    real_metadata = case.storage.get_source_file_in_transaction
    def tracked_metadata(session, *args, **kwargs):
        assert set(kwargs) >= {"expected_dataset_id", "expected_source_id", "expected_source_version"}
        if not observed:
            # Metadata/limit checks and bounded input reads finish before the
            # business transaction starts; they may commit their own audit.
            prelude.append(session)
            return real_metadata(session, *args, **kwargs)
        assert observed and session is observed[0][0]
        assert session.get_transaction() is observed[0][1]
        metadata.append(session.connection())
        return real_metadata(session, *args, **kwargs)
    monkeypatch.setattr(idempotency, "execute", tracked_execute)
    monkeypatch.setattr(case.storage, "get_source_file_in_transaction", tracked_metadata)
    result = invoke(case)
    assert result.status == "staged" and len(metadata) >= 2
    assert all(connection is observed[0][2] for _, _, connection in observed)
    assert all(connection is observed[0][2] for connection in metadata)
    assert len(rows(pg_engine, ImportBatch)) == len(rows(pg_engine, IdempotencyRecord)) == 1


def test_success_audit_failure_rolls_back_batch_candidates_receipt_but_keeps_source_blob(import_case_factory,
        pg_engine, io_probe):
    case = import_case_factory()
    before, deleted = successes(pg_engine), list(io_probe.deleted)
    def fail(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO auth_audit_events") and parameters.get("object_type") == "import":
            raise RuntimeError(SENTINEL)
    event.listen(pg_engine, "before_cursor_execute", fail)
    try:
        denied(lambda: invoke(case), 503)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail)
    assert rows(pg_engine, ImportBatch) == rows(pg_engine, ImportCandidateRow) == rows(pg_engine, IdempotencyRecord) == []
    new_successes = [row for row in rows(pg_engine, AuditEvent) if row["id"] not in before and row["outcome"] == "succeeded"]
    assert not any(row["object_type"] == "import" for row in new_successes)
    assert io_probe.deleted == deleted
    assert case.storage.read_source(case.admin.principal, case.file.id) == case.data


def test_true_commit_failure_rolls_back_import_and_is_retryable(import_case_factory, pg_engine):
    case = import_case_factory()
    before = successes(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t15_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T15_REJECTED_RAW_SECRET_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t15_commit_fault AFTER INSERT ON import_batches "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t15_fail_commit()"))
    denied(lambda: invoke(case), 503)
    assert rows(pg_engine, ImportBatch) == rows(pg_engine, ImportCandidateRow) == rows(pg_engine, IdempotencyRecord) == []
    # Storage's authorized input-read audit committed before the business TX;
    # no import success audit may survive the failed business commit.
    new_successes = [row for row in rows(pg_engine, AuditEvent) if row["id"] not in before and row["outcome"] == "succeeded"]
    assert not any(row["object_type"] == "import" for row in new_successes)
    with pg_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER t15_commit_fault ON import_batches"))
    assert invoke(case).status == "staged"


def test_final_import_audit_wait_rechecks_mfa_file_and_receipt_time(import_case_factory, pg_engine, clock):
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE TABLE demo_t15_audit_barrier (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO demo_t15_audit_barrier VALUES (1)"))
        connection.execute(text("CREATE FUNCTION t15_wait_import_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF NEW.object_type='import' AND NEW.outcome='succeeded' THEN "
            "PERFORM id FROM demo_t15_audit_barrier WHERE id=1 FOR UPDATE; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER t15_import_audit_wait BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION t15_wait_import_audit()"))
    for expires in ("mfa", "file", "receipt"):
        case = import_case_factory(ttl_seconds=1 if expires == "receipt" else 86400)
        if expires == "file":
            with Session(pg_engine) as session, session.begin():
                session.get(StorageObject, case.file.id).expires_at = clock() + timedelta(seconds=1)
        started, pid = Event(), []
        def observed(connection, cursor, statement, parameters, context, many):
            if statement.lstrip().startswith("INSERT INTO auth_audit_events") and parameters.get("object_type") == "import":
                pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
                started.set()
        event.listen(pg_engine, "before_cursor_execute", observed)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                with pg_engine.begin() as blocker:
                    blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                    blocker.execute(text("SELECT id FROM demo_t15_audit_barrier WHERE id=1 FOR UPDATE"))
                    future = pool.submit(invoke, case)
                    wait_for_block(pg_engine, started, pid, blocker_id)
                    # The inherited MFA policy permits age == max; move past
                    # the 60-second bound rather than changing its semantics.
                    clock.advance(61 if expires == "mfa" else 1)
                denied(lambda: future.result(timeout=8), (401, 403, 404, 409))
        finally:
            event.remove(pg_engine, "before_cursor_execute", observed)
        assert rows(pg_engine, ImportBatch) == rows(pg_engine, ImportCandidateRow) == rows(pg_engine, IdempotencyRecord) == []


def test_real_natural_unique_index_two_session_contention(import_case_factory, pg_engine):
    case = import_case_factory()
    result = invoke(case)
    template = dict(rows(pg_engine, ImportBatch)[0])
    with pg_engine.begin() as connection:
        connection.execute(delete(ImportCandidateRow).where(ImportCandidateRow.import_id == result.id))
        connection.execute(delete(ImportBatch).where(ImportBatch.id == result.id))
    first_values, second_values = dict(template, id=uuid4()), dict(template, id=uuid4())
    started, pid = Event(), []
    def second():
        with pg_engine.begin() as connection:
            pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            started.set()
            connection.execute(ImportBatch.__table__.insert().values(**second_values))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pg_engine.begin() as first:
            blocker = first.scalar(text("SELECT pg_backend_pid()"))
            first.execute(ImportBatch.__table__.insert().values(**first_values))
            future = pool.submit(second)
            wait_for_block(pg_engine, started, pid, blocker)
            assert not future.done()
        with pytest.raises(IntegrityError):
            future.result(timeout=8)
    assert len(rows(pg_engine, ImportBatch)) == 1


def test_store_requires_active_same_engine_for_every_new_mapper(import_case_factory, imports_store, pg_engine):
    case = import_case_factory()
    result = invoke(case)
    with Session(pg_engine) as session:
        denied(lambda: imports_store.get(session, result.id), 503)
    other = create_engine(pg_engine.url, hide_parameters=True)
    def no_connect(*args, **kwargs):
        pytest.fail("A redirected mapper must fail before opening another database connection", pytrace=False)
    event.listen(other, "do_connect", no_connect)
    try:
        for model in (None, ImportBatch, ImportCandidateRow, ImportRowError, AdmissionOffering, AdmissionOfferingVersion):
            with Session(other if model is None else pg_engine,
                    binds=None if model is None else {model: other}) as session:
                session.begin()
                denied(lambda: imports_store.get(session, result.id), 503)
                session.rollback()
    finally:
        other.dispose()
    assert len(rows(pg_engine, ImportBatch)) == 1


def test_default_import_policy_and_changed_source_policy_remain_closed(import_case_factory,
        imports_factory, pg_engine, io_probe):
    case = import_case_factory()
    closed = imports_factory(case.storage, policy=ImportsPolicy())
    denied(lambda: closed.import_file(case.admin.principal, case.request(), KEY), 503)
    copied = ImportsPolicy().model_copy(update={"enabled": 1})
    denied(lambda: imports_factory(case.storage, policy=copied), 503)
    before = io_probe.read_count
    case.storage.source_service.policy = SourcePolicy()
    denied(lambda: invoke(case), 503)
    assert io_probe.read_count == before and rows(pg_engine, ImportBatch) == []


def test_independent_imports_migration_preserves_all_existing_profiles(import_case_factory, imports_store,
        pg_engine, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.seed import seed
    case = import_case_factory()
    invoke(case)
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    def preserved():
        with pg_engine.connect() as connection:
            return {name: connection.execute(text('SELECT * FROM "' + name + '" ORDER BY 1')).all()
                for name in inspect(connection).get_table_names() if not name.startswith("import")}
    before = preserved()
    assert len(ImportsBase.metadata.tables) == 3
    migrate_imports(pg_engine)
    migrate_imports(pg_engine)
    assert preserved() == before
    with pg_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert not {"import_batches", "import_candidate_rows", "import_row_errors"} & set(inspect(pg_engine).get_table_names())
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM imports_alembic_version")) == 0
    denied(imports_store.assert_schema_ready, 503)
    assert preserved() == before
    migrate_imports(pg_engine)
    imports_store.assert_schema_ready()
    assert preserved() == before and rows(pg_engine, ImportBatch) == []
