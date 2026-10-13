"""Independent T17 current-authority, provenance and PostgreSQL transaction tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from hashlib import sha256
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from services.api.app.admin.imports.models import ImportBatch, ImportCandidateRow
from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion
from services.api.app.admin.sources.schemas import SourcePolicy, SourceRevisionInput
from services.api.app.admissions_catalog.date_models import CatalogDateEvent
from services.api.app.admissions_catalog.date_schemas import DateEventInput
from services.api.app.admissions_catalog.date_store import DateEventStore
from services.api.app.admissions_catalog.models import AdmissionOffering, CatalogDataset
from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthSession, AuthUser, AuthUserRole
from services.api.app.evidence.models import Document, DocumentVersion, EvidenceSnippet
from services.api.app.evidence.schemas import DocumentCreate, VersionCreate, SnippetCreate
from services.api.app.facts.models import FactsBase, FactCandidate, FactConflict
from services.api.app.facts.schemas import FactPolicy
from services.api.app.facts.store import migrate_facts, migration_config
from services.api.app.storage.models import StorageObject


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T17_PRIVATE_FAILURE_SENTINEL"


def denied(call, *codes):
    with pytest.raises(ValueError) as caught:
        call()
    assert caught.value.status_code in codes
    assert SENTINEL not in str(caught.value) + repr(caught.value)
    return caught.value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(model.__table__.select().order_by(*model.__table__.primary_key.columns)).mappings().all()


def create(case, classification, **changes):
    return case.facts.create_fact(case.admin.principal, case.fact_request(classification, **changes))


def verify(case, session, candidate, **changes):
    fields = dict(expected_offering_id=candidate.offering_id, expected_offering_version=candidate.offering_version,
        expected_entry_year=candidate.entry_year)
    fields.update(changes)
    return case.facts.verify_in_transaction(session, case.admin.principal, candidate.id, **fields)


def wait_for_block(engine, started, pids, blocker):
    assert started.wait(timeout=5), "The contender did not reach its SQL boundary"
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with engine.connect() as connection:
            locked = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                "WHERE pid=:pid AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)))"),
                {"pid": pids[0], "blocker": blocker})
        if locked:
            return
    pytest.fail("The actual PostgreSQL lock wait was not observed")


def install_audit_barrier(engine):
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE demo_t17_audit_barrier(id integer PRIMARY KEY)"))
        connection.execute(text("INSERT INTO demo_t17_audit_barrier VALUES(1)"))
        connection.execute(text("CREATE FUNCTION demo_t17_wait_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF current_setting('t17.probe',true)='1' THEN "
            "PERFORM id FROM demo_t17_audit_barrier WHERE id=1 FOR UPDATE; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER demo_t17_audit_wait BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION demo_t17_wait_audit()"))


def make_date(case, engine):
    raw = case.raw_rows[0]
    event_id = uuid4()
    request = DateEventInput(id=event_id, dataset_id=case.source.dataset_id, offering_id=raw["offering_id"],
        offering_version=raw["offering_version"], entry_year=raw["entry_year"],
        reference_key="DEMO_T17_DATE_" + uuid4().hex, is_synthetic=True,
        event_type="application_deadline", original_text=raw["value_text"], precision="date",
        local_date=date(2026, 10, 1), local_time=None, timezone=None, source_alignment="pending", evidence_reference=None)
    with Session(engine) as session, session.begin():
        revision = session.get(CatalogDataset, case.source.dataset_id).revision
        DateEventStore(engine).create_date_event(session, request, expected_dataset_revision=revision)
    return event_id


@pytest.mark.parametrize("format", ["json", "csv"])
def test_exact_import_fields_units_evidence_and_unpublished_state(fact_case_factory, classification_factory,
        candidate_factory, pg_engine, format):
    raw = candidate_factory(unit="DEMO_raw_points", footnote_state="present",
        footnote_text="DEMO_Manual footnote; no automatic policy")
    case = fact_case_factory(format=format, rows=[raw])
    candidate = create(case, classification_factory())
    assert candidate.import_id == case.imported.id and candidate.import_row_id == case.row_ids[0]
    assert candidate.value_text == "600.00" and candidate.unit == raw["unit"] and candidate.normalized_value == "600"
    assert candidate.classification.unit_code == "points"
    assert candidate.classification.claim_kind == "minimum_requirement" and candidate.state == "review_required"
    assert candidate.evidence_id == case.snippets[0].id and candidate.version == 1
    assert candidate.hard_rule is False and candidate.publication_eligible is False and candidate.is_synthetic is True
    assert candidate.row_number == (1 if format == "json" else 2)
    assert candidate.missing_reason is None and candidate.footnote_state == "present" and candidate.date_resolution is None
    assert candidate.footnote_text == raw["footnote_text"]
    serialized = candidate.model_dump()
    assert not {"owner", "role", "path", "file_id", "published", "approved"} & set(serialized)
    assert case.facts.get_fact(case.admin.principal, candidate.id) == candidate
    with Session(pg_engine) as session, session.begin():
        assert verify(case, session, candidate) == candidate


def test_minimum_typical_historical_are_distinct_semantics(fact_case_factory, classification_factory, pg_engine):
    case = fact_case_factory()
    minimum = create(case, classification_factory())
    typical = create(case, classification_factory(claim_kind="typical_offer"))
    historical = create(case, classification_factory(claim_kind="historical_statistic", period="survey_period",
        statistics_basis="admission", statistic_population="DEMO_2025 entrants", statistic_denominator="DEMO_10 entrants",
        cohort_year=2025, survey_period="DEMO_2025 survey"))
    assert len({minimum.id, typical.id, historical.id}) == 3
    assert historical.classification.cohort_year == 2025 and historical.entry_year == 2026
    assert all(candidate.hard_rule is False and candidate.publication_eligible is False for candidate in
        (minimum, typical, historical))
    assert rows(pg_engine, FactConflict) == []


def test_equivalent_numbers_not_conflicts_different_values_preserve_every_candidate(fact_case_factory,
        candidate_factory, classification_factory, pg_engine):
    exact = "1." + "0" * 60 + "1"
    adjacent = "1." + "0" * 60 + "2"
    case = fact_case_factory(rows=[candidate_factory(value_text=value) for value in (exact + "0", exact, adjacent)])
    first = create(case, classification_factory(), index=0)
    equivalent = create(case, classification_factory(), index=1)
    assert first.normalized_value == equivalent.normalized_value == exact and rows(pg_engine, FactConflict) == []
    assert first.value_text == exact + "0" and len(first.value_text) == 64
    different = create(case, classification_factory(), index=2)
    assert different.normalized_value == adjacent and different.state == "conflicted"
    assert set(different.conflicting_ids) == {first.id, equivalent.id}
    for prior in (first, equivalent):
        fresh = case.facts.get_fact(case.admin.principal, prior.id)
        assert fresh.state == "conflicted" and different.id in fresh.conflicting_ids
    assert len(rows(pg_engine, FactCandidate)) == 3 and len(rows(pg_engine, FactConflict)) == 2
    from fastapi.testclient import TestClient
    from services.api.app.api.public import create_public_app
    from services.api.app.settings import V2RuntimeSettings
    settings = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    with TestClient(create_public_app(settings)) as client:
        response = client.get("/v2/offerings")
        assert response.status_code == 200 and response.json()["data"]["items"] == []
        assert "DEMO_T15_RECORD" not in response.text and exact not in response.text
        assert client.get("/v2/facts/" + str(first.id)).status_code == 404
    assert "conflicted" not in response.text and "review_required" not in response.text


def test_unknown_missing_and_footnotes_stay_draft_without_guessed_values(fact_case_factory, candidate_factory,
        classification_factory, pg_engine):
    raw = candidate_factory(value_text=None, unit=None, missing_reason="not_published", footnote_state="unknown")
    case = fact_case_factory(rows=[raw], with_evidence=False)
    candidate = create(case, classification_factory(claim_kind="unknown", unit_code="unknown", period="unknown",
        statistics_basis="unknown"))
    assert candidate.state == "draft" and candidate.normalized_value is None and candidate.evidence_id is None
    assert candidate.value_text is None and candidate.unit is None and candidate.missing_reason == "not_published"
    assert candidate.footnote_state == "unknown" and candidate.footnote_text is None
    assert candidate.classification.cohort_year is None and candidate.classification.statistic_denominator is None
    assert candidate.hard_rule is False and candidate.publication_eligible is False
    bounded_text = "DEMO_" + "\n" * 4091
    large = fact_case_factory(rows=[candidate_factory(fact_type="requirement", value_kind="text", value_text=bounded_text,
        unit=bounded_text, footnote_state="present", footnote_text=bounded_text, locator=bounded_text)], with_evidence=False)
    value = create(large, classification_factory(unit_code="text"))
    assert value.normalized_value == value.value_text == value.unit == value.footnote_text == value.locator == bounded_text
    with pg_engine.connect() as connection:
        payload_bytes = connection.scalar(text("SELECT octet_length(payload::text) FROM fact_candidates WHERE id=:id"),
            {"id": value.id})
    assert 32768 < payload_bytes <= 262144
    assert large.facts.get_fact(large.admin.principal, value.id) == value
    uncertain = fact_case_factory(rows=[candidate_factory(fact_type="requirement", value_kind=kind,
        field_key="uncertain_value_kind", value_text="100", unit=None) for kind in ("text", "decimal")], with_evidence=False)
    classification = classification_factory(claim_kind="unknown", unit_code="unknown")
    text_value = create(uncertain, classification, index=0)
    numeric_value = create(uncertain, classification, index=1)
    assert text_value.normalized_value == numeric_value.normalized_value == "100"
    assert text_value.value_kind == "text" and numeric_value.value_kind == "decimal"
    assert numeric_value.state == "conflicted" and numeric_value.conflicting_ids == (text_value.id,)
    assert uncertain.facts.get_fact(uncertain.admin.principal, text_value.id).conflicting_ids == (numeric_value.id,)


def test_exact_natural_key_replays_same_candidate_and_classification_change_appends(fact_case_factory,
        classification_factory, pg_engine):
    case = fact_case_factory()
    request = case.fact_request(classification_factory())
    first = case.facts.create_fact(case.admin.principal, request)
    second = case.facts.create_fact(case.admin.principal, request)
    assert first.id == second.id and len(rows(pg_engine, FactCandidate)) == 1
    without_evidence = create(case, classification_factory(), evidence_id=None)
    assert without_evidence.id != first.id and without_evidence.state == "draft"
    assert rows(pg_engine, FactConflict) == []


def test_same_hash_copy_evidence_cannot_replace_original_file_binding(fact_case_factory, classification_factory,
        evidence_factory, pg_engine):
    case = fact_case_factory()
    copied = case.upload()
    evidence = evidence_factory(case.storage)
    document = evidence.create_document(case.admin.principal, DocumentCreate(dataset_id=case.source.dataset_id,
        source_id=case.source.source_id, source_version=case.source.version,
        document_reference="DEMO_T17_COPY_" + uuid4().hex, language="und"))
    version = evidence.create_version(case.admin.principal, VersionCreate(document_id=document.id,
        expected_current_version=0, file_id=copied.id, file_sha256=copied.sha256))
    original = case.snippets[0]
    span = evidence.create_snippet(case.admin.principal, SnippetCreate(document_id=document.id,
        document_version=version.version, offering_id=original.offering_id, offering_version=original.offering_version,
        entry_year=original.entry_year, byte_start=original.locator.byte_start, byte_end=original.locator.byte_end))
    assert copied.sha256 == case.file.sha256 and copied.id != case.file.id
    denied(lambda: create(case, classification_factory(), evidence_id=span.id), 409)
    assert rows(pg_engine, FactCandidate) == []


def test_wrong_row_batch_offering_year_and_scope_are_rejected(fact_case_factory, candidate_factory,
        classification_factory, pg_engine):
    case = fact_case_factory()
    other = fact_case_factory(rows=[candidate_factory(field_key="other_total")])
    denied(lambda: create(case, classification_factory(), import_row_id=other.row_ids[0]), 404, 409)
    value = create(case, classification_factory())
    for fields in ({"expected_offering_id": uuid4()}, {"expected_offering_version": 2}, {"expected_entry_year": 2025}):
        with Session(pg_engine) as session, session.begin():
            denied(lambda: verify(case, session, value, **fields), 409)
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE catalog_offerings SET applicant_category_key='known:DEMO_CHANGED_CATEGORY' WHERE id=:id"),
            {"id": value.offering_id})
    denied(lambda: case.facts.get_fact(case.admin.principal, value.id), 409)


def test_candidate_and_conflict_update_delete_are_database_immutable(fact_case_factory, candidate_factory,
        classification_factory, pg_engine):
    case = fact_case_factory(rows=[candidate_factory(value_text=value) for value in ("600", "601")])
    create(case, classification_factory(), index=0)
    create(case, classification_factory(), index=1)
    before = {model: rows(pg_engine, model) for model in (FactCandidate, FactConflict)}
    for model in (FactCandidate, FactConflict):
        for command_text in (f"UPDATE {model.__tablename__} SET id=id", f"DELETE FROM {model.__tablename__}"):
            with pytest.raises(DBAPIError):
                with pg_engine.begin() as connection:
                    connection.execute(text(command_text))
    assert all(rows(pg_engine, model) == values for model, values in before.items())


def test_current_role_session_and_mfa_are_required_on_replay(fact_case_factory, classification_factory, pg_engine, clock):
    for boundary in ("role", "session", "mfa"):
        case = fact_case_factory()
        candidate = create(case, classification_factory())
        with Session(pg_engine) as session, session.begin():
            if boundary == "role":
                session.get(AuthUserRole, (case.admin.actor.user_id, "data_admin")).revoked_at = clock()
            elif boundary == "session":
                session.get(AuthSession, case.admin.actor.session_id).revoked_at = clock()
            else:
                session.get(AuthSession, case.admin.actor.session_id).assurance_auth_time = clock() - timedelta(seconds=61)
        denied(lambda: case.facts.get_fact(case.admin.principal, candidate.id), 401, 403)
        denied(lambda: create(case, classification_factory()), 401, 403)


def test_latest_source_permission_and_original_file_availability_are_current(fact_case_factory,
        classification_factory, pg_engine, clock):
    for boundary in ("permission", "expired", "deleted", "hash"):
        case = fact_case_factory()
        candidate = create(case, classification_factory())
        if boundary == "expired":
            clock.advance(1)
        with Session(pg_engine) as session, session.begin():
            if boundary == "permission":
                session.get(CatalogSourceVersion, case.source.id).manual_import_enabled = False
            else:
                row = session.get(StorageObject, case.file.id)
                if boundary == "expired":
                    row.expires_at = clock()
                elif boundary == "deleted":
                    row.status = "deleted"
                else:
                    row.sha256 = "0" * 64
        denied(lambda: case.facts.get_fact(case.admin.principal, candidate.id), 403, 404, 409)


def test_reviewer_receives_only_bounded_candidate_without_raw_io_or_owner_impersonation(fact_case_factory,
        classification_factory, administrator_factory, facts_factory, storage_factory, io_probe, monkeypatch):
    case = fact_case_factory()
    candidate = create(case, classification_factory())
    reviewer = administrator_factory()
    storage = storage_factory(identity=reviewer.service)
    reviewer_facts = facts_factory(storage)
    denied(lambda: storage.read_source(reviewer.principal, case.file.id), 403)
    before = io_probe.read_count
    monkeypatch.setattr(storage, "read_source", lambda *_: pytest.fail("Derived fact getter must not read original bytes"))
    visible = reviewer_facts.get_fact(reviewer.principal, candidate.id)
    assert visible.id == candidate.id and visible.value_text == "600.00" and io_probe.read_count == before
    denied(lambda: reviewer_facts.create_fact(reviewer.principal, case.fact_request(classification_factory())), 403)


def test_original_row_and_raw_unit_changes_invalidate_the_fingerprint(fact_case_factory, classification_factory, pg_engine):
    for field, changed in (("value_text", "602.00"), ("unit", "DEMO_RAW_DIFFERENT_UNIT"), ("footnote_state", "unknown")):
        case = fact_case_factory()
        candidate = create(case, classification_factory())
        with pg_engine.begin() as connection:
            connection.execute(text(f"UPDATE import_candidate_rows SET {field}=:changed WHERE id=:id"),
                {"id": case.row_ids[0], "changed": changed})
        denied(lambda: case.facts.get_fact(case.admin.principal, candidate.id), 409)


def test_date_resolution_exact_original_scope_and_current_fingerprint(fact_case_factory, candidate_factory,
        classification_factory, catalog_tree, pg_engine):
    raw = candidate_factory(fact_type="date", field_key="application_deadline", value_kind="text",
        value_text="2026-10-01", unit="ISO_DATE")
    case = fact_case_factory(rows=[raw])
    date_id = make_date(case, pg_engine)
    candidate = create(case, classification_factory(unit_code="ISO_DATE", date_event_id=date_id))
    assert candidate.value_text == "2026-10-01" and candidate.date_resolution.date_event_id == date_id
    assert candidate.date_resolution.conversion_status == "date_only" and candidate.date_resolution.utc_instant is None
    assert candidate.date_resolution.local_time is None and candidate.date_resolution.timezone is None
    reread = case.facts.get_fact(case.admin.principal, candidate.id)
    assert reread.date_resolution == candidate.date_resolution
    assert type(reread.date_resolution.local_date) is date
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE catalog_date_events SET original_text='DEMO_ALTERED_ORIGINAL' WHERE id=:id"), {"id": date_id})
    denied(lambda: case.facts.get_fact(case.admin.principal, candidate.id), 409)
    denied(lambda: create(case, classification_factory(unit_code="ISO_DATE", date_event_id=date_id)), 409, 422)


def test_date_lock_wait_without_evidence_and_caller_failure_cannot_commit_partial_work(fact_case_factory,
        candidate_factory, classification_factory, pg_engine, clock, monkeypatch):
    raw = candidate_factory(fact_type="date", field_key="application_deadline", value_kind="text",
        value_text="2026-10-01", unit="ISO_DATE")
    case = fact_case_factory(rows=[raw], with_evidence=False)
    date_id = make_date(case, pg_engine)
    classification = classification_factory(unit_code="ISO_DATE", date_event_id=date_id)
    with Session(pg_engine) as session, session.begin():
        session.get(StorageObject, case.file.id).expires_at = clock() + timedelta(seconds=1)
    started, pids, worker_thread = Event(), [], []
    def observe(connection, cursor, statement, parameters, context, many):
        if (worker_thread and get_ident() == worker_thread[0]
            and statement.lstrip().startswith("SELECT") and "catalog_date_events" in statement
            and "FOR UPDATE" in statement.upper() and not started.is_set()):
            pids.append(connection.scalar(text("SELECT pg_backend_pid()")))
            started.set()
    def work():
        worker_thread.append(get_ident())
        return create(case, classification)
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM catalog_date_events WHERE id=:id FOR UPDATE"), {"id": date_id})
                pending = pool.submit(work)
                wait_for_block(pg_engine, started, pids, blocker_id)
                clock.advance(1)
            denied(lambda: pending.result(timeout=8), 404, 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
    assert rows(pg_engine, FactCandidate) == []
    with Session(pg_engine) as session, session.begin():
        session.get(StorageObject, case.file.id).expires_at = clock() + timedelta(days=1)
    candidate = create(case, classification)
    original_audit = case.facts._audit
    def late_audit(session, current):
        original_audit(session, current)
        clock.advance(1)
    monkeypatch.setattr(case.facts, "_audit", late_audit)
    before_audit_ids = {row["id"] for row in rows(pg_engine, AuditEvent)}
    with Session(pg_engine) as session:
        session.begin()
        row = session.get(StorageObject, case.file.id)
        row.expires_at = clock() + timedelta(seconds=1)
        session.flush()
        denied(lambda: verify(case, session, candidate), 404, 409)
        assert not session.in_transaction()
        session.commit()
        session.rollback()
    new_audit = [row for row in rows(pg_engine, AuditEvent) if row["id"] not in before_audit_ids]
    assert all(row["outcome"] in {"denied", "failed"} for row in new_audit)
    with Session(pg_engine) as session:
        assert session.get(StorageObject, case.file.id).expires_at > clock() + timedelta(hours=1)


def test_default_policy_forged_inputs_and_non_test_demo_cannot_write(fact_case_factory, classification_factory,
        facts_factory, pg_engine):
    case = fact_case_factory()
    closed = facts_factory(case.storage, policy=FactPolicy())
    denied(lambda: closed.create_fact(case.admin.principal, case.fact_request(classification_factory())), 503)
    denied(lambda: facts_factory(case.storage, policy=FactPolicy().model_copy(update={"enabled": 1})), 503)
    request = case.fact_request(classification_factory()).model_copy(update={"value_text": "999"})
    denied(lambda: case.facts.create_fact(case.admin.principal, request), 422)
    case.admin.service.runtime_settings = case.admin.service.runtime_settings.model_copy(update={"app_environment": "development"})
    denied(lambda: create(case, classification_factory()), 503)
    assert rows(pg_engine, FactCandidate) == []


def test_caller_transaction_same_engine_mapper_and_actor_binding(fact_case_factory, classification_factory,
        facts_factory, storage_factory, administrator_factory, pg_engine):
    case = fact_case_factory()
    candidate = create(case, classification_factory())
    with Session(pg_engine) as session:
        denied(lambda: verify(case, session, candidate), 503)
    engine_other = create_engine(pg_engine.url, hide_parameters=True)
    def no_foreign_connection(*_):
        pytest.fail("Wrong mapper engine must be rejected before connecting")
    event.listen(engine_other, "connect", no_foreign_connection)
    try:
        for mapper in (FactCandidate, FactConflict, ImportCandidateRow, DocumentVersion, StorageObject,
                       CatalogSourceVersion, CatalogDateEvent, AuthUser, AuditEvent):
            with Session(pg_engine, binds={mapper: engine_other}) as session, session.begin():
                denied(lambda: verify(case, session, candidate), 503)
        with Session(engine_other) as session, session.begin():
            denied(lambda: verify(case, session, candidate), 503)
    finally:
        engine_other.dispose()
    other = administrator_factory()
    other_facts = facts_factory(storage_factory(identity=other.service))
    connections = []
    def observe(connection, *_):
        connections.append(id(connection))
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with Session(pg_engine) as session, session.begin():
            assert verify(case, session, candidate).id == candidate.id
            assert len(set(connections)) == 1
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
    with Session(pg_engine) as session, session.begin():
        verify(case, session, candidate)
        denied(lambda: other_facts.verify_in_transaction(session, other.principal, candidate.id,
            expected_offering_id=candidate.offering_id, expected_offering_version=1, expected_entry_year=2026), 403)


def test_required_audit_failure_rolls_back_new_candidate_and_conflict(fact_case_factory, candidate_factory,
        classification_factory, pg_engine):
    case = fact_case_factory(rows=[candidate_factory(value_text=value) for value in ("600", "601")])
    first = create(case, classification_factory(), index=0)
    inserted = False
    def fail(connection, cursor, statement, parameters, context, many):
        nonlocal inserted
        if statement.lstrip().startswith("INSERT INTO fact_candidates"):
            inserted = True
        elif inserted and statement.lstrip().startswith("INSERT INTO auth_audit_events"):
            raise RuntimeError(SENTINEL)
    event.listen(pg_engine, "before_cursor_execute", fail)
    try:
        denied(lambda: create(case, classification_factory(), index=1), 503)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail)
    assert inserted and len(rows(pg_engine, FactCandidate)) == 1 and rows(pg_engine, FactConflict) == []
    assert case.facts.get_fact(case.admin.principal, first.id).state == "review_required"


def test_true_deferred_commit_failure_rolls_back_then_retry_succeeds(fact_case_factory, classification_factory, pg_engine):
    case = fact_case_factory()
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION demo_t17_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T17_PRIVATE_FAILURE_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER demo_t17_commit_failure AFTER INSERT ON fact_candidates "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION demo_t17_commit_failure()"))
    denied(lambda: create(case, classification_factory()), 503)
    assert rows(pg_engine, FactCandidate) == [] and rows(pg_engine, FactConflict) == []
    with pg_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER demo_t17_commit_failure ON fact_candidates"))
    assert create(case, classification_factory()).state == "review_required"


@pytest.mark.parametrize("expiry", ["file", "mfa"])
def test_audit_lock_wait_expiry_refuses_candidate_and_rolls_back(fact_case_factory, classification_factory,
        pg_engine, clock, expiry):
    case = fact_case_factory()
    if expiry == "file":
        with Session(pg_engine) as session, session.begin():
            session.get(StorageObject, case.file.id).expires_at = clock() + timedelta(seconds=1)
    install_audit_barrier(pg_engine)
    started, pids = Event(), []
    def mark(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO fact_candidates"):
            connection.execute(text("SET LOCAL t17.probe='1'"))
        elif statement.lstrip().startswith("INSERT INTO auth_audit_events") and not started.is_set():
            if connection.scalar(text("SELECT current_setting('t17.probe',true)")) == "1":
                pids.append(connection.scalar(text("SELECT pg_backend_pid()")))
                started.set()
    event.listen(pg_engine, "before_cursor_execute", mark)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t17_audit_barrier WHERE id=1 FOR UPDATE"))
                pending = pool.submit(create, case, classification_factory())
                wait_for_block(pg_engine, started, pids, blocker_id)
                clock.advance(1 if expiry == "file" else 61)
            denied(lambda: pending.result(timeout=8), 401, 403, 404, 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", mark)
    assert rows(pg_engine, FactCandidate) == [] and rows(pg_engine, FactConflict) == []


@pytest.mark.parametrize("different", [False, True])
def test_two_real_sessions_serialize_dedup_and_conflict_discovery(fact_case_factory, candidate_factory,
        classification_factory, pg_engine, different):
    case = fact_case_factory(rows=[candidate_factory(value_text=value) for value in ("600", "601")])
    classification = classification_factory()
    first_request = case.fact_request(classification, index=0)
    second_request = case.fact_request(classification, index=1 if different else 0)
    install_audit_barrier(pg_engine)
    first_started, second_started = Event(), Event()
    first_pid, second_pid, second_thread = [], [], []
    def mark(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO fact_candidates") and not first_started.is_set():
            connection.execute(text("SET LOCAL t17.probe='1'"))
        elif statement.lstrip().startswith("INSERT INTO auth_audit_events") and not first_started.is_set():
            if connection.scalar(text("SELECT current_setting('t17.probe',true)")) == "1":
                first_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
                first_started.set()
        if second_thread and get_ident() == second_thread[0] and statement.lstrip().startswith("SELECT") and "auth_users" in statement and not second_started.is_set():
            second_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            second_started.set()
    def second():
        second_thread.append(get_ident())
        return case.facts.create_fact(case.admin.principal, second_request)
    event.listen(pg_engine, "before_cursor_execute", mark)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t17_audit_barrier WHERE id=1 FOR UPDATE"))
                pending = pool.submit(case.facts.create_fact, case.admin.principal, first_request)
                wait_for_block(pg_engine, first_started, first_pid, blocker_id)
                contender = pool.submit(second)
                wait_for_block(pg_engine, second_started, second_pid, first_pid[0])
            first, second_value = pending.result(timeout=8), contender.result(timeout=8)
    finally:
        event.remove(pg_engine, "before_cursor_execute", mark)
    assert len(rows(pg_engine, FactCandidate)) == (2 if different else 1)
    assert len(rows(pg_engine, FactConflict)) == (1 if different else 0)
    if different:
        assert first.id != second_value.id
        assert case.facts.get_fact(case.admin.principal, first.id).state == "conflicted"
        assert case.facts.get_fact(case.admin.principal, second_value.id).state == "conflicted"
    else:
        assert first.id == second_value.id


def test_different_responsible_users_and_sources_share_a_real_scope_lock(fact_case_factory,
        candidate_factory, classification_factory, pg_engine):
    first_case = fact_case_factory(rows=[candidate_factory(value_text="600")])
    second_case = fact_case_factory(rows=[candidate_factory(value_text="601")])
    assert first_case.admin.actor.user_id != second_case.admin.actor.user_id
    assert first_case.source.source_id != second_case.source.source_id
    assert first_case.imported.id != second_case.imported.id
    assert first_case.raw_rows[0]["offering_id"] == second_case.raw_rows[0]["offering_id"]
    classification = classification_factory()
    install_audit_barrier(pg_engine)
    first_started, second_started = Event(), Event()
    first_pid, second_pid, second_thread = [], [], []
    def mark(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO fact_candidates") and not first_started.is_set():
            connection.execute(text("SET LOCAL t17.probe='1'"))
        elif statement.lstrip().startswith("INSERT INTO auth_audit_events") and not first_started.is_set():
            if connection.scalar(text("SELECT current_setting('t17.probe',true)")) == "1":
                first_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
                first_started.set()
        if (second_thread and get_ident() == second_thread[0] and statement.lstrip().startswith("SELECT")
            and "FOR UPDATE" in statement.upper() and any(name in statement for name in
                ("catalog_datasets", "catalog_offerings")) and not second_started.is_set()):
            second_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            second_started.set()
    def second():
        second_thread.append(get_ident())
        return create(second_case, classification)
    event.listen(pg_engine, "before_cursor_execute", mark)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t17_audit_barrier WHERE id=1 FOR UPDATE"))
                pending = pool.submit(create, first_case, classification)
                wait_for_block(pg_engine, first_started, first_pid, blocker_id)
                contender = pool.submit(second)
                wait_for_block(pg_engine, second_started, second_pid, first_pid[0])
            first, second_value = pending.result(timeout=8), contender.result(timeout=8)
    finally:
        event.remove(pg_engine, "before_cursor_execute", mark)
    assert first.id != second_value.id and len(rows(pg_engine, FactCandidate)) == 2
    assert len(rows(pg_engine, FactConflict)) == 1
    assert first_case.facts.get_fact(first_case.admin.principal, first.id).conflicting_ids == (second_value.id,)
    assert second_case.facts.get_fact(second_case.admin.principal, second_value.id).conflicting_ids == (first.id,)


def test_independent_migration_repeat_downgrade_preserves_all_prior_domains(fact_case_factory,
        classification_factory, facts_store, pg_engine, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.seed import seed
    case = fact_case_factory()
    create(case, classification_factory())
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    def preserved():
        with pg_engine.connect() as connection:
            return {name: connection.execute(text('SELECT * FROM "' + name + '" ORDER BY 1')).all()
                for name in inspect(connection).get_table_names() if name not in
                    {"fact_candidates", "fact_conflicts", "facts_alembic_version"}}
    before = preserved()
    assert len(FactsBase.metadata.tables) == 2
    assert {item["name"] for item in inspect(pg_engine).get_indexes("fact_candidates")} >= {"ix_fact_logical_key"}
    assert {item["name"] for item in inspect(pg_engine).get_indexes("fact_conflicts")} >= {"ix_fact_conflict_right"}
    migrate_facts(pg_engine)
    migrate_facts(pg_engine)
    assert preserved() == before
    with pg_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert not {"fact_candidates", "fact_conflicts"} & set(inspect(pg_engine).get_table_names())
    denied(facts_store.assert_schema_ready, 503)
    assert preserved() == before
    migrate_facts(pg_engine)
    facts_store.assert_schema_ready()
    assert preserved() == before and rows(pg_engine, FactCandidate) == []
