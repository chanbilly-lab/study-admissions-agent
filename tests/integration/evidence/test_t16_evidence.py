"""Independent real-PG T16 trust, replay, immutability and transaction checks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from services.api.app.admissions_catalog.models import (CatalogDataset, AdmissionOffering, AdmissionOfferingVersion)
from services.api.app.admissions_catalog.schemas import ScopeKey
from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion
from services.api.app.admin.sources.schemas import SourcePolicy, SourceRevisionInput
from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthSession, AuthUser, AuthUserRole
from services.api.app.evidence.models import EvidenceBase, Document, DocumentVersion, EvidenceSnippet
from services.api.app.evidence.schemas import EvidencePolicy
from services.api.app.evidence.store import migrate_evidence, migration_config
from services.api.app.storage.models import StorageObject
from tests.integration.evidence.conftest import TARGET


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T16_FIXED_ERROR_SENTINEL"


def denied(operation, expected):
    with pytest.raises(ValueError) as failure:
        operation()
    assert getattr(failure.value, "status_code", None) in ((expected,) if isinstance(expected, int) else expected)
    assert SENTINEL not in str(failure.value) + repr(failure.value)
    return failure.value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns)).mappings().all()


def snippet(case, *, request=None, principal=None):
    return case.service.create_snippet(principal or case.admin.principal, request or case.snippet_request())


def verify(case, session, value, *, principal=None, **changes):
    expected = dict(expected_offering_id=value.offering_id, expected_offering_version=value.offering_version,
                    expected_entry_year=value.entry_year)
    expected.update(changes)
    return case.service.verify_in_transaction(session, principal or case.admin.principal, value.id, **expected)


def wait_for_block(engine, started, pids, blocker):
    assert started.wait(5)
    deadline, pause = monotonic() + 5, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE pid=:pid "
                "AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid))"),
                {"pid": pids[0], "blocker": blocker}):
                return
            pause.wait(0.01)
    pytest.fail("No actual PostgreSQL evidence lock contention observed")


@pytest.mark.parametrize("format", ["json", "csv"])
def test_exact_original_bytes_locators_and_server_scope_survive_replay(format, evidence_case_factory,
        pg_engine, catalog_tree):
    case = evidence_case_factory(format=format)
    first, repeated = snippet(case), snippet(case)
    assert first == repeated and first.text == TARGET
    assert first.document_sha256 == sha256(case.content).hexdigest()
    assert first.snippet_sha256 == sha256(TARGET.encode("utf-8")).hexdigest()
    assert first.locator.byte_start == case.content.index(TARGET.encode("utf-8"))
    assert first.locator.byte_end - first.locator.byte_start == len(TARGET.encode("utf-8"))
    assert first.locator.line_start == first.locator.line_end == (3 if format == "json" else 2)
    assert first.locator.page is None and first.locator.section is None
    assert first.locator.location_kind == "utf8_byte_lines"
    assert first.language == "zh-Hans" and first.is_synthetic is True
    assert first.scope.dataset_id == catalog_tree.dataset.id
    assert first.scope.program_id == catalog_tree.program.id
    assert first.scope.applicant_category == catalog_tree.offering.applicant_category
    assert first.scope.province == catalog_tree.offering.province
    assert not {"file_id", "path", "owner_user_id", "backend_key"} & set(first.model_dump())
    assert len(rows(pg_engine, EvidenceSnippet)) == len(rows(pg_engine, DocumentVersion)) == 1
    assert case.service.get_snippet(case.admin.principal, first.id) == first


def test_hash_copy_keeps_version_new_hash_appends_and_old_trace_is_preserved(evidence_case_factory, pg_engine):
    case = evidence_case_factory()
    old = snippet(case)
    copy = case.upload()
    assert copy.id != case.file.id
    copied = case.service.create_version(case.admin.principal, case.version_request(copy))
    assert copied.id == case.version.id and copied.version == 1
    changed_content = case.content.replace(b"DEMO_ALPHA", b"DEMO_CHANGED")
    changed = case.upload(changed_content)
    new = case.service.create_version(case.admin.principal, case.version_request(changed))
    assert new.version == 2 and new.document_sha256 != old.document_sha256
    denied(lambda: case.service.create_version(case.admin.principal, case.version_request(changed, expected=1)), 409)
    assert case.service.get_snippet(case.admin.principal, old.id) == old
    start = changed_content.index(TARGET.encode("utf-8"))
    new_snippet = snippet(case, request=case.snippet_request(version_number=2,
        span=(start, start + len(TARGET.encode("utf-8")))))
    assert new_snippet.id != old.id and new_snippet.document_sha256 == new.document_sha256
    assert len(rows(pg_engine, DocumentVersion)) == len(rows(pg_engine, EvidenceSnippet)) == 2
    assert rows(pg_engine, Document)[0]["current_version"] == 2


def test_database_rejects_version_and_snippet_update_delete(evidence_case_factory, pg_engine):
    case = evidence_case_factory()
    value = snippet(case)
    before = {model: rows(pg_engine, model) for model in (DocumentVersion, EvidenceSnippet)}
    for model, key in ((DocumentVersion, case.version.id), (EvidenceSnippet, value.id)):
        for action in ("UPDATE", "DELETE"):
            statement = (f'UPDATE "{model.__tablename__}" SET id=id WHERE id=:id' if action == "UPDATE"
                         else f'DELETE FROM "{model.__tablename__}" WHERE id=:id')
            with pytest.raises(DBAPIError):
                with pg_engine.begin() as connection:
                    connection.execute(text(statement), {"id": key})
        assert rows(pg_engine, model) == before[model]


def test_exact_offering_version_year_and_identity_are_not_interchangeable(evidence_case_factory,
        catalog_store, catalog_tree, pg_engine):
    case = evidence_case_factory()
    value = snippet(case)
    alternate = catalog_tree.offering.model_copy(update={"id": uuid4(), "reference_key": "DEMO_OTHER_IDENTITY",
        "applicant_category": ScopeKey(status="known", value="DEMO_OTHER_CATEGORY")})
    with Session(pg_engine) as session, session.begin():
        catalog_store.create_offering(session, alternate,
            expected_dataset_revision=catalog_store.get_dataset(session, alternate.dataset_id).revision, version_id=uuid4())
    for changes in ({"expected_offering_id": alternate.id}, {"expected_offering_version": 2},
                    {"expected_entry_year": 2025}):
        with Session(pg_engine) as session, session.begin():
            denied(lambda: verify(case, session, value, **changes), 409)
    for changes in ({"entry_year": 2025}, {"offering_version": 99}, {"offering_id": uuid4()}):
        denied(lambda: snippet(case, request=case.snippet_request(**changes)), (404, 409))
    assert len(rows(pg_engine, EvidenceSnippet)) == 1


def test_current_catalog_scope_change_invalidates_stored_fingerprint(evidence_case_factory, pg_engine):
    case = evidence_case_factory()
    value = snippet(case)
    # UPDATE/DELETE immutability does not prove an initial privileged INSERT
    # used real byte positions. All local CHECK/FKs accept this self-consistent
    # text/hash/span, but the position is beyond the exact original version.
    corrupt = dict(rows(pg_engine, EvidenceSnippet)[0], id=uuid4(),
        byte_start=case.version.size_bytes + 1,
        byte_end=case.version.size_bytes + 1 + len(TARGET.encode("utf-8")))
    with pg_engine.begin() as connection:
        connection.execute(EvidenceSnippet.__table__.insert().values(**corrupt))
    denied(lambda: case.service.get_snippet(case.admin.principal, corrupt["id"]), (409, 503))
    with Session(pg_engine) as session, session.begin():
        session.get(AdmissionOffering, value.offering_id).applicant_category_key = "known:DEMO_CHANGED_IDENTITY"
    denied(lambda: case.service.get_snippet(case.admin.principal, value.id), 409)
    with Session(pg_engine) as session, session.begin():
        denied(lambda: verify(case, session, value), 409)
    assert {row["id"] for row in rows(pg_engine, EvidenceSnippet)} == {value.id, corrupt["id"]}


def test_file_source_refs_hash_and_dynamic_inputs_are_revalidated(evidence_case_factory, pg_engine, io_probe):
    case = evidence_case_factory(create_version=False)
    request = case.version_request()
    denied(lambda: case.service.create_version(case.admin.principal,
        request.model_copy(update={"file_sha256": "0" * 64})), (409, 422))
    before = io_probe.read_count
    for changes in ({"expected_current_version": True}, {"owner": uuid4()}, {"is_synthetic": False}):
        denied(lambda: case.service.create_version(case.admin.principal, request.model_copy(update=changes)), 422)
    assert io_probe.read_count == before and rows(pg_engine, DocumentVersion) == []
    other = evidence_case_factory()
    denied(lambda: case.service.create_version(case.admin.principal, case.version_request(other.file)), (403, 409))
    assert len(rows(pg_engine, DocumentVersion)) == 1


def test_invalid_utf8_span_pdf_and_empty_or_oversized_ranges_do_not_create_evidence(evidence_case_factory,
        pg_engine, io_probe):
    case = evidence_case_factory()
    start = case.content.index("升".encode("utf-8"))
    valid = case.snippet_request()
    for span in ((start + 1, start + 3), (start, start), (0, len(case.content) + 1)):
        denied(lambda: snippet(case, request=valid.model_copy(update={"byte_start": span[0], "byte_end": span[1]})), 422)
    pdf = case.upload(b"%PDF-1.7\nDEMO_T16\n%%EOF", "pdf")
    denied(lambda: case.service.create_version(case.admin.principal, case.version_request(pdf)), 422)
    assert rows(pg_engine, EvidenceSnippet) == [] and len(rows(pg_engine, DocumentVersion)) == 1


def test_reviewer_reads_only_bounded_derived_snippet_not_full_source_or_creation(evidence_case_factory,
        administrator_factory, evidence_factory, storage_factory, pg_engine, monkeypatch, io_probe):
    case = evidence_case_factory()
    value = snippet(case)
    reviewer = administrator_factory()
    review_storage = storage_factory(identity=reviewer.service)
    review_service = evidence_factory(review_storage)
    assert reviewer.actor.user_id != case.source.responsible_user_id
    before = io_probe.read_count
    denied(lambda: review_storage.read_source(reviewer.principal, case.file.id), 403)
    assert io_probe.read_count == before
    def forbidden_bytes(*args, **kwargs):
        pytest.fail("Derived review must not call Storage.read_source", pytrace=False)
    monkeypatch.setattr(review_storage, "read_source", forbidden_bytes)
    assert review_service.get_snippet(reviewer.principal, value.id) == value
    with Session(pg_engine) as session, session.begin():
        assert review_service.verify_in_transaction(session, reviewer.principal, value.id,
            expected_offering_id=value.offering_id, expected_offering_version=1, expected_entry_year=2026) == value
    denied(lambda: case.service.create_snippet(reviewer.principal, case.snippet_request()), 403)
    assert len(rows(pg_engine, EvidenceSnippet)) == 1


def test_role_mfa_session_and_forged_principal_never_authorize_existing_snippet(evidence_case_factory,
        pg_engine, clock, administrator_factory):
    for lost in ("role", "mfa", "session"):
        case = evidence_case_factory()
        value = snippet(case)
        with Session(pg_engine) as session, session.begin():
            if lost == "role":
                session.get(AuthUserRole, (case.admin.actor.user_id, "data_admin")).revoked_at = clock()
            elif lost == "mfa":
                session.get(AuthSession, case.admin.actor.session_id).assurance_amr = ["pwd"]
            else:
                session.get(AuthSession, case.admin.actor.session_id).revoked_at = clock()
        denied(lambda: case.service.get_snippet(case.admin.principal, value.id), (401, 403))
        denied(lambda: snippet(case), (401, 403))
    stranger = administrator_factory()
    forged = case.admin.principal.model_copy(update={"user_id": stranger.actor.user_id})
    denied(lambda: case.service.get_snippet(forged, value.id), 401)


def test_source_revised_permission_and_deleted_or_expired_file_block_old_trace(evidence_case_factory,
        pg_engine, clock):
    for lost in ("source_version", "permission", "deleted", "expired", "hash",
                 "future_document", "future_version", "future_snippet", "clock_rollback"):
        case = evidence_case_factory()
        value = snippet(case)
        if lost in {"source_version", "permission"}:
            with Session(pg_engine) as session:
                revision = session.get(CatalogDataset, case.source.dataset_id).revision
            definition = case.source_request.definition
            if lost == "permission":
                definition = definition.model_copy(update={"manual_import_permission": "denied", "manual_import_enabled": False})
            case.storage.source_service.revise_source(case.admin.principal,
                SourceRevisionInput(source_id=case.source.source_id, definition=definition),
                expected_dataset_revision=revision, expected_source_version=1)
        elif lost == "future_document":
            with Session(pg_engine) as session, session.begin():
                session.get(Document, case.document.id).created_at = clock() + timedelta(seconds=1)
        elif lost == "future_version":
            changed_content = case.content.replace(b"DEMO_ALPHA", b"DEMO_FUTURE_ALPHA")
            file = case.upload(changed_content)
            version = dict(next(row for row in rows(pg_engine, DocumentVersion) if row["id"] == case.version.id),
                id=uuid4(), version=2, file_id=file.id, document_sha256=file.sha256,
                size_bytes=file.size_bytes, media_type=file.media_type, created_at=clock() + timedelta(seconds=1))
            derived = dict(next(row for row in rows(pg_engine, EvidenceSnippet) if row["id"] == value.id),
                id=uuid4(), document_version=2)
            derived["byte_start"] = changed_content.index(TARGET.encode("utf-8"))
            derived["byte_end"] = derived["byte_start"] + len(TARGET.encode("utf-8"))
            with pg_engine.begin() as connection:
                connection.execute(text("UPDATE evidence_documents SET current_version=2 WHERE id=:id"), {"id": case.document.id})
                connection.execute(DocumentVersion.__table__.insert().values(**version))
                connection.execute(EvidenceSnippet.__table__.insert().values(**derived))
            # An invalid future version does not silently rewrite old trace.
            assert case.service.get_snippet(case.admin.principal, value.id) == value
            value = value.model_copy(update={"id": derived["id"], "document_version": 2})
        elif lost == "future_snippet":
            derived = dict(next(row for row in rows(pg_engine, EvidenceSnippet) if row["id"] == value.id),
                id=uuid4(), text="DEMO_ALPHA", snippet_sha256=sha256(b"DEMO_ALPHA").hexdigest(),
                byte_start=case.content.index(b"DEMO_ALPHA"), line_start=2, line_end=2,
                created_at=clock() + timedelta(seconds=1))
            derived["byte_end"] = derived["byte_start"] + len(b"DEMO_ALPHA")
            with pg_engine.begin() as connection:
                connection.execute(EvidenceSnippet.__table__.insert().values(**derived))
            value = value.model_copy(update={"id": derived["id"]})
        elif lost == "clock_rollback":
            clock.advance(-1)
        else:
            with Session(pg_engine) as session, session.begin():
                file = session.get(StorageObject, case.file.id)
                if lost == "deleted":
                    file.status = "deleted"
                elif lost == "expired":
                    file.expires_at = clock() + timedelta(seconds=1)
                else:
                    file.sha256 = "0" * 64
            if lost == "expired":
                clock.advance(1)
        denied(lambda: case.service.get_snippet(case.admin.principal, value.id), (401, 403, 404, 409))
        with Session(pg_engine) as session, session.begin():
            denied(lambda: verify(case, session, value), (401, 403, 404, 409))


def test_caller_session_and_each_mapper_must_use_same_engine(evidence_case_factory, pg_engine):
    case = evidence_case_factory()
    value = snippet(case)
    with Session(pg_engine) as session:
        denied(lambda: verify(case, session, value), 503)
    other = create_engine(pg_engine.url, hide_parameters=True)
    def no_connection(*args, **kwargs):
        pytest.fail("Foreign mapper rejected after opening a connection", pytrace=False)
    event.listen(other, "do_connect", no_connection)
    try:
        for model in (None, Document, DocumentVersion, EvidenceSnippet, AuthUser, CatalogSource,
                      CatalogSourceVersion, StorageObject, AdmissionOffering, AdmissionOfferingVersion, AuditEvent):
            with Session(other if model is None else pg_engine,
                    binds=None if model is None else {model: other}) as session:
                session.begin()
                denied(lambda: verify(case, session, value), 503)
                session.rollback()
    finally:
        other.dispose()


def test_verify_same_transaction_and_actor_binding_does_not_fake_source_owner(evidence_case_factory,
        administrator_factory, pg_engine, monkeypatch):
    case = evidence_case_factory()
    value = snippet(case)
    reviewer = administrator_factory()
    seen = []
    real_success = case.admin.service.store.audit.success
    def audited(session, *args, **kwargs):
        seen.append((session, session.get_transaction(), session.connection()))
        return real_success(session, *args, **kwargs)
    monkeypatch.setattr(case.admin.service.store.audit, "success", audited)
    with Session(pg_engine) as session, session.begin():
        tx, connection = session.get_transaction(), session.connection()
        assert verify(case, session, value) == value
        assert seen and all(current is session and current_tx is tx and current_connection is connection
            for current, current_tx, current_connection in seen)
        denied(lambda: verify(case, session, value, principal=reviewer.principal), 403)


def test_required_audit_failure_rolls_back_new_snippet_without_destroying_original(evidence_case_factory,
        pg_engine, io_probe):
    case = evidence_case_factory()
    inserted = set()
    def fail_after_candidate(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO evidence_snippets"):
            inserted.add(connection)
        if connection in inserted and statement.lstrip().startswith("INSERT INTO auth_audit_events"):
            raise RuntimeError(SENTINEL)
    deleted = list(io_probe.deleted)
    event.listen(pg_engine, "before_cursor_execute", fail_after_candidate)
    try:
        denied(lambda: snippet(case), 503)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail_after_candidate)
    assert rows(pg_engine, EvidenceSnippet) == [] and len(rows(pg_engine, DocumentVersion)) == 1
    assert io_probe.deleted == deleted
    assert case.storage.read_source(case.admin.principal, case.file.id) == case.content


def test_real_deferred_commit_failure_rolls_back_version_pointer_then_retry(evidence_case_factory, pg_engine):
    case = evidence_case_factory(create_version=False)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t16_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T16_FIXED_ERROR_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t16_commit_fault AFTER INSERT ON evidence_document_versions "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t16_fail_commit()"))
    denied(lambda: case.service.create_version(case.admin.principal, case.version_request()), 503)
    assert rows(pg_engine, DocumentVersion) == [] and rows(pg_engine, Document)[0]["current_version"] == 0
    with pg_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER t16_commit_fault ON evidence_document_versions"))
    assert case.service.create_version(case.admin.principal, case.version_request()).version == 1


def install_audit_barrier(engine):
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE demo_t16_audit_barrier (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO demo_t16_audit_barrier VALUES (1)"))
        connection.execute(text("CREATE FUNCTION t16_wait_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "IF NEW.outcome='succeeded' AND current_setting('t16.probe',true)='1' THEN "
            "PERFORM id FROM demo_t16_audit_barrier WHERE id=1 FOR UPDATE; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER t16_audit_wait BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION t16_wait_audit()"))


def test_actual_audit_wait_rechecks_file_expiry_and_mfa_before_return(evidence_case_factory, pg_engine, clock):
    install_audit_barrier(pg_engine)
    for lost in ("file", "mfa"):
        case = evidence_case_factory()
        value = snippet(case)
        if lost == "file":
            with Session(pg_engine) as session, session.begin():
                session.get(StorageObject, case.file.id).expires_at = clock() + timedelta(seconds=1)
        started, pids = Event(), []
        def mark(connection, cursor, statement, parameters, context, many):
            if statement.lstrip().startswith("SELECT") and "FROM evidence_snippets" in statement:
                connection.exec_driver_sql("SET LOCAL t16.probe='1'")
            if statement.lstrip().startswith("INSERT INTO auth_audit_events"):
                if connection.scalar(text("SELECT current_setting('t16.probe',true)")) == "1":
                    pids.append(connection.scalar(text("SELECT pg_backend_pid()")))
                    started.set()
        event.listen(pg_engine, "before_cursor_execute", mark)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                with pg_engine.begin() as blocker:
                    blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                    blocker.execute(text("SELECT id FROM demo_t16_audit_barrier WHERE id=1 FOR UPDATE"))
                    future = pool.submit(case.service.get_snippet, case.admin.principal, value.id)
                    wait_for_block(pg_engine, started, pids, blocker_id)
                    clock.advance(1 if lost == "file" else 61)
                denied(lambda: future.result(timeout=8), (401, 403, 404, 409))
        finally:
            event.remove(pg_engine, "before_cursor_execute", mark)


def test_actual_concurrent_expected_version_allows_only_one_append(evidence_case_factory, pg_engine):
    case = evidence_case_factory()
    first_file = case.upload(case.content.replace(b"DEMO_ALPHA", b"DEMO_FIRST"))
    second_file = case.upload(case.content.replace(b"DEMO_ALPHA", b"DEMO_SECOND"))
    first_request, second_request = case.version_request(first_file, expected=1), case.version_request(second_file, expected=1)
    install_audit_barrier(pg_engine)
    first_started, second_started, first_pid, second_pid, second_thread = Event(), Event(), [], [], []
    def mark(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO evidence_document_versions"):
            connection.exec_driver_sql("SET LOCAL t16.probe='1'")
        if statement.lstrip().startswith("INSERT INTO auth_audit_events") and connection.scalar(
                text("SELECT current_setting('t16.probe',true)")) == "1":
            first_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            first_started.set()
        if second_thread and get_ident() == second_thread[0] and statement.lstrip().startswith("SELECT") and "auth_users" in statement:
            second_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            second_started.set()
    def second():
        second_thread.append(get_ident())
        return case.service.create_version(case.admin.principal, second_request)
    event.listen(pg_engine, "before_cursor_execute", mark)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t16_audit_barrier WHERE id=1 FOR UPDATE"))
                first = pool.submit(case.service.create_version, case.admin.principal, first_request)
                wait_for_block(pg_engine, first_started, first_pid, blocker_id)
                competing = pool.submit(second)
                wait_for_block(pg_engine, second_started, second_pid, first_pid[0])
            assert first.result(timeout=8).version == 2
            denied(lambda: competing.result(timeout=8), 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", mark)
    assert len(rows(pg_engine, DocumentVersion)) == rows(pg_engine, Document)[0]["current_version"] == 2


def test_default_and_forged_policy_close_operations_before_bytes(evidence_case_factory, evidence_factory,
        pg_engine, io_probe):
    case = evidence_case_factory()
    closed = evidence_factory(case.storage, policy=EvidencePolicy())
    before = io_probe.read_count
    denied(lambda: closed.create_version(case.admin.principal, case.version_request()), 503)
    denied(lambda: evidence_factory(case.storage, policy=EvidencePolicy().model_copy(update={"enabled": 1})), 503)
    case.storage.source_service.policy = SourcePolicy()
    denied(lambda: snippet(case), 503)
    assert io_probe.read_count == before and rows(pg_engine, EvidenceSnippet) == []


def test_independent_migration_repeat_downgrade_preserves_prior_heads_and_data(evidence_case_factory,
        evidence_store, pg_engine, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.seed import seed
    case = evidence_case_factory()
    snippet(case)
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    def preserved():
        with pg_engine.connect() as connection:
            return {name: connection.execute(text('SELECT * FROM "' + name + '" ORDER BY 1')).all()
                for name in inspect(connection).get_table_names() if not name.startswith("evidence_")}
    before = preserved()
    assert len(EvidenceBase.metadata.tables) == 3
    migrate_evidence(pg_engine)
    migrate_evidence(pg_engine)
    assert preserved() == before
    with pg_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert not {"evidence_documents", "evidence_document_versions", "evidence_snippets"} & set(inspect(pg_engine).get_table_names())
    denied(evidence_store.assert_schema_ready, 503)
    assert preserved() == before
    migrate_evidence(pg_engine)
    evidence_store.assert_schema_ready()
    assert preserved() == before and rows(pg_engine, Document) == []
