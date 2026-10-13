"""Independent PostgreSQL proof, history and last-wait assessment boundaries.

All positive rules are explicit synthetic bindings to the actual published chain.
These checks never certify a real admissions rule or substitute a fake Principal.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

from alembic import command
from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine, delete, event, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.assessments.models import AssessmentsBase, EligibilityAssessment
from services.api.app.assessments.store import AssessmentsStore, migrate_assessments, migration_config
from services.api.app.admissions_catalog.models import CatalogDataset
from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthOwnedResource
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from services.api.app.rules.expression import parse_expression
from services.api.app.rules.schemas import ReplayRequest
from services.api.app.rules.service import EligibilityService
from services.api.app.releases.schemas import PublishMember, PublishRequest, WithdrawalRequest


pytestmark = pytest.mark.postgres


def denied(operation, *statuses):
    with pytest.raises(ValueError) as caught:
        operation()
    assert getattr(caught.value, "status_code", None) in statuses
    assert "DEMO_T28_PRIVATE_SENTINEL" not in str(caught.value) + repr(caught.value)
    return caught.value


def rows(engine, table):
    table = getattr(table, "__table__", table)
    with engine.connect() as connection:
        return connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()


def succeeded(engine):
    return {row["id"] for row in rows(engine, AuditEvent) if row["outcome"] == "succeeded"}


def test_assessment_migration_missing_prerequisites_creates_nothing(pg_engine):
    assert inspect(pg_engine).get_table_names() == []
    denied(lambda: migrate_assessments(pg_engine), 503)
    assert inspect(pg_engine).get_table_names() == []


def test_assessment_readiness_rejects_incompatible_parent_head(assessments_store, pg_engine):
    before = rows(pg_engine, EligibilityAssessment)
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE releases_alembic_version SET version_num='DEMO_wrong_head'"))
    denied(assessments_store.assert_schema_ready, 503)
    denied(lambda: migrate_assessments(pg_engine), 503)
    assert rows(pg_engine, EligibilityAssessment) == before


def test_repeated_upgrade_and_isolated_downgrade_preserve_populated_parent_domains(
        assessments_store, catalog_tree, pg_engine):
    table_names = set(inspect(pg_engine).get_table_names())
    own_tables = {"eligibility_assessments", "assessments_alembic_version"}
    parent_names = sorted(table_names - own_tables)

    def snapshot():
        with pg_engine.connect() as connection:
            return {name: connection.execute(text('SELECT row_to_json(t)::text FROM "' + name
                + '" AS t ORDER BY row_to_json(t)::text')).scalars().all() for name in parent_names}

    before = snapshot()
    assert before["catalog_offerings"] and before["catalog_datasets"]
    assert len(AssessmentsBase.metadata.tables) == 1
    migrate_assessments(pg_engine)
    migrate_assessments(pg_engine)
    assessments_store.assert_schema_ready()
    assert snapshot() == before
    with pg_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert set(inspect(pg_engine).get_table_names()) == table_names - {"eligibility_assessments"}
    assert snapshot() == before
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM pg_proc WHERE proname='assessments_reject_update' "
            "AND pronamespace=current_schema()::regnamespace")) == 0
    migrate_assessments(pg_engine)
    assessments_store.assert_schema_ready()
    assert snapshot() == before
    assert rows(pg_engine, EligibilityAssessment) == []


def observed_lock(engine, worker_pid, blocker_pid, future):
    deadline, pause = monotonic() + 25, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if future.done():
                future.result()
                pytest.fail("The worker finished without reaching the required PostgreSQL lock")
            if worker_pid and connection.scalar(text("SELECT wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)) "
                    "FROM pg_stat_activity WHERE pid=:pid"), {"blocker": blocker_pid, "pid": worker_pid[0]}):
                return
            pause.wait(0.01)
    pytest.fail("The required actual PostgreSQL lock wait was not observed")


def score(key="gaokao_total", minimum="600", scale="750"):
    return {"op": "gte", "field": {"name": "assessment", "key": key, "basis": "achieved"},
        "value": {"kind": "decimal", "value": minimum, "unit": "points", "scale": scale}}


def test_nested_ast_survives_commit_and_replay_keeps_original_microsecond_time_and_minimal_context(
        assessment_case_factory, clock, pg_engine):
    expression = {"op": "all", "children": [score(), {"op": "any", "children": [
        {"op": "eq", "field": {"name": "entry_year"}, "value": {"kind": "integer", "value": 2026}},
        {"op": "not", "child": {"op": "exists", "field": {"name": "subjects"}}}]}]}
    case = assessment_case_factory(expression=expression)
    clock.advance(0.123456)
    at = clock()
    result = case.service.evaluate(case.principal, case.request)
    assert result.eligibility.status == "eligible" and result.assessment_at == at
    assert result.assessment_at.microsecond == 123456
    saved = rows(pg_engine, EligibilityAssessment)[0]
    assert parse_expression(saved["replay_snapshot"]["expression"]) == parse_expression(expression)
    assert set(saved["replay_snapshot"]["expression"]) == {"op", "children"}
    projected = saved["replay_snapshot"]["context"]["fields"]
    assert {item["field"]["name"] for item in projected} == {"entry_year", "subjects", "assessment"}
    assert all(item["field"].get("basis") != "predicted" for item in projected)
    assert "weekly_hours" not in str(saved["replay_snapshot"]["context"])
    clock.advance(2)
    history = case.service.get_assessment(case.principal, result.assessment_id)
    replay = case.service.replay(case.principal, result.assessment_id, ReplayRequest(confirmed=True))
    assert history.current_validity == replay.current_validity == "current"
    assert history.eligibility == replay.eligibility == result.eligibility
    assert replay.assessment_at == at and replay.result_sha256 == result.result_sha256 and replay.replayed
    assert rows(pg_engine, EligibilityAssessment) == [saved]

    # Real replacement/withdrawal changes current validity, not the historical
    # AST, profile values, assessment instant or immutable result fingerprint.
    with Session(pg_engine) as session:
        revision = session.get(CatalogDataset, case.release.dataset_id).revision
    replacement = case.releases.publish(case.reviewer.principal, PublishRequest(
        dataset_id=case.release.dataset_id, expected_dataset_revision=revision, entry_year=2026,
        kind="test_fixture", valid_from=clock(), valid_until=clock() + timedelta(hours=1),
        members=tuple(PublishMember(fact_id=member.fact_id, expected_case_revision=member.case_revision,
            expected_decision_id=member.decision_id, public_evidence=False) for member in case.release.members),
        replaces_release_id=case.release.release_id, expected_replaced_state_revision=case.release.state_revision),
        SecretStr("DEMO_T28_REPLACEMENT"))
    old = case.service.replay(case.principal, result.assessment_id, ReplayRequest(confirmed=True))
    assert old.current_validity == "replaced" and old.eligibility == result.eligibility
    assert old.assessment_at == at and old.result_sha256 == result.result_sha256
    denied(lambda: case.service.evaluate(case.principal, case.request), 409)
    new_bundle = case.bundle.model_copy(update={"release_id": replacement.release_id,
        "requirements_version": replacement.requirements_version})
    successor = EligibilityService(case.profiles, case.releases, case.service.store, case.service.policy,
        rule_binding_reader=lambda session, query: (new_bundle,))
    new_request = case.request.model_copy(update={"release_id": replacement.release_id})
    fresh = successor.evaluate(case.principal, new_request)
    assert fresh.eligibility.status == "eligible"
    case.releases.withdraw(case.reviewer.principal, WithdrawalRequest(release_id=replacement.release_id,
        expected_state_revision=replacement.state_revision, reason_code="ADMIN_REQUEST"))
    withdrawn = successor.replay(case.principal, fresh.assessment_id, ReplayRequest(confirmed=True))
    assert withdrawn.current_validity == "withdrawn" and withdrawn.eligibility == fresh.eligibility
    assert withdrawn.assessment_at == fresh.assessment_at and withdrawn.result_sha256 == fresh.result_sha256
    denied(lambda: successor.evaluate(case.principal, new_request), 409)
    assert saved in rows(pg_engine, EligibilityAssessment)


def test_database_rejects_update_but_audit_retention_and_trusted_result_delete_are_possible(
        assessment_case_factory, pg_engine):
    case = assessment_case_factory()
    result = case.service.evaluate(case.principal, case.request)
    original = rows(pg_engine, EligibilityAssessment)
    with pytest.raises(IntegrityError) as failed:
        with pg_engine.begin() as connection:
            connection.execute(update(EligibilityAssessment).where(EligibilityAssessment.id == result.assessment_id)
                .values(result_sha256="0" * 64))
    assert failed.value.orig.sqlstate == "23514"
    assert rows(pg_engine, EligibilityAssessment) == original
    with pg_engine.begin() as connection:
        trigger = connection.scalar(text("SELECT tgtype FROM pg_trigger WHERE tgrelid='eligibility_assessments'::regclass "
            "AND tgname='eligibility_assessments_no_update' AND NOT tgisinternal"))
        assert trigger & 16 and not trigger & 8
        connection.execute(delete(AuditEvent).where(AuditEvent.id == original[0]["audit_event_id"]))
    assert case.service.get_assessment(case.principal, result.assessment_id).eligibility == result.eligibility
    with pg_engine.begin() as connection:
        connection.execute(delete(EligibilityAssessment).where(EligibilityAssessment.id == result.assessment_id))
    denied(lambda: case.service.get_assessment(case.principal, result.assessment_id), 404)


@pytest.mark.parametrize("failure_stage", ["audit", "commit"])
def test_actual_required_audit_or_deferred_commit_failure_leaves_no_assessment_or_success_audit(
        assessment_case_factory, pg_engine, failure_stage):
    case = assessment_case_factory()
    before = succeeded(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION demo_t28_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'Synthetic T28 transaction rejection' USING ERRCODE='23514'; END $$"))
        if failure_stage == "commit":
            connection.execute(text("CREATE CONSTRAINT TRIGGER demo_t28_failure AFTER INSERT ON eligibility_assessments "
                "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION demo_t28_failure()"))
        else:
            connection.execute(text("CREATE TRIGGER demo_t28_failure BEFORE INSERT ON auth_audit_events "
                "FOR EACH ROW EXECUTE FUNCTION demo_t28_failure()"))
    try:
        denied(lambda: case.service.evaluate(case.principal, case.request), 503)
        assert rows(pg_engine, EligibilityAssessment) == []
        assert succeeded(pg_engine) == before
    finally:
        with pg_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER demo_t28_failure ON "
                + ("eligibility_assessments" if failure_stage == "commit" else "auth_audit_events")))
            connection.execute(text("DROP FUNCTION demo_t28_failure()"))
    assert case.service.evaluate(case.principal, case.request).eligibility.status == "eligible"


def test_caught_caller_transaction_failure_aborts_preceding_writes_and_caller_success_can_rollback(
        assessment_case_factory, pg_engine):
    case = assessment_case_factory()
    before, audits = rows(pg_engine, AuthOwnedResource), succeeded(pg_engine)
    with Session(pg_engine) as session:
        session.begin()
        session.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == case.profile.profile_id).values(status="deleted"))
        denied(lambda: case.service.evaluate(case.principal, case.request, session=session), 404)
        session.commit()
    assert rows(pg_engine, AuthOwnedResource) == before and rows(pg_engine, EligibilityAssessment) == []
    assert succeeded(pg_engine) == audits
    with Session(pg_engine) as session, session.begin():
        result = case.service.evaluate(case.principal, case.request, session=session)
        assert result.eligibility.status == "eligible" and session.in_transaction()
        session.rollback()
    assert rows(pg_engine, EligibilityAssessment) == [] and succeeded(pg_engine) == audits


def test_original_conditional_replays_but_expired_completion_deadline_loses_current_validity(
        assessment_case_factory, pg_engine, clock):
    case = assessment_case_factory(expression=score("math", "100", "150"), deferral=True)
    result = case.service.evaluate(case.principal, case.request)
    assert result.eligibility.status == "conditional" and result.current_validity == "current"
    assert len(result.eligibility.obligations) == 1
    original = rows(pg_engine, EligibilityAssessment)
    clock.advance(40)  # Exact application deadline is no longer BEFORE.
    history = case.service.get_assessment(case.principal, result.assessment_id)
    replay = case.service.replay(case.principal, result.assessment_id, ReplayRequest(confirmed=True))
    assert history.eligibility == replay.eligibility == result.eligibility
    assert history.current_validity == replay.current_validity == "needs_review"
    assert replay.assessment_at == result.assessment_at and replay.result_sha256 == result.result_sha256
    assert rows(pg_engine, EligibilityAssessment) == original


def test_withdraw_and_new_core_confirmation_do_not_revive_an_old_assessment(
        assessment_case_factory, pg_engine):
    case = assessment_case_factory()
    result = case.service.evaluate(case.principal, case.request)
    privacy = case.profiles.privacy_service
    active = privacy.get_admission(case.principal)
    privacy.withdraw_core(case.principal, active.consent_id)
    denied(lambda: case.service.replay(case.principal, result.assessment_id, ReplayRequest(confirmed=True)), 403)
    current = privacy.get_admission(case.principal)
    age = privacy.declare_age(case.principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=current.notice_id, expected_revision=current.revision))
    privacy.confirm_core(case.principal, CoreConsentInput(confirmed=True, purpose="core_consultation",
        notice_id=age.notice_id, expected_revision=age.revision))
    denied(lambda: case.service.get_assessment(case.principal, result.assessment_id), 403)
    assert len(rows(pg_engine, EligibilityAssessment)) == 1


def run_after_last_role_sql_wait(case, engine, clock, monkeypatch, *, seconds):
    """Block the second role SELECT in Profile._final, its actual last SQL."""
    armed, entered, worker_pid = [], Event(), []
    original = case.profiles._final
    main_thread, key = get_ident(), int(uuid4().hex[:12], 16)
    def final(*args, **kwargs):
        armed.append(0)
        return original(*args, **kwargs)
    def wait(connection, cursor, statement, parameters, context, many):
        if (get_ident() != main_thread and armed and "FROM auth_user_roles" in statement
                and "FOR UPDATE" in statement):
            armed[-1] += 1
            if armed[-1] == 2 and not entered.is_set():
                worker_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                entered.set()
                connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    monkeypatch.setattr(case.profiles, "_final", final)
    event.listen(engine, "before_cursor_execute", wait)
    try:
        with engine.begin() as blocker:
            blocker.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(case.service.evaluate, case.principal, case.request)
                try:
                    deadline = monotonic() + 25
                    while not entered.wait(0.02):
                        if pending.done():
                            pending.result()
                            pytest.fail("The evaluation returned before its final authorization SQL")
                        assert monotonic() < deadline, "The evaluation never reached its final authorization SQL"
                    observed_lock(engine, worker_pid, blocker_pid, pending)
                    clock.advance(seconds)
                    blocker.commit()
                    return pending
                finally:
                    blocker.rollback()
    finally:
        event.remove(engine, "before_cursor_execute", wait)


@pytest.mark.parametrize("unused_any", [False, True])
def test_only_necessary_completion_deadlines_control_final_wait_commit(
        assessment_case_factory, pg_engine, clock, monkeypatch, unused_any):
    required = score("math", "100", "150")
    expression = {"op": "any", "children": [score(), required]} if unused_any else required
    case = assessment_case_factory(expression=expression, deferral=True)
    before = succeeded(pg_engine)
    pending = run_after_last_role_sql_wait(case, pg_engine, clock, monkeypatch, seconds=40)
    if unused_any:
        actual = pending.result(timeout=30)
        assert actual.eligibility.status == "eligible" and actual.eligibility.obligations == ()
        assert len(rows(pg_engine, EligibilityAssessment)) == 1
    else:
        denied(lambda: pending.result(timeout=30), 409)
        assert rows(pg_engine, EligibilityAssessment) == [] and succeeded(pg_engine) == before


def test_last_authorization_sql_wait_cannot_commit_after_original_file_expiry(
        assessment_case_factory, pg_engine, clock, monkeypatch):
    case = assessment_case_factory(file_lifetime_seconds=1)
    before = succeeded(pg_engine)
    pending = run_after_last_role_sql_wait(case, pg_engine, clock, monkeypatch, seconds=1)
    denied(lambda: pending.result(timeout=30), 409)
    assert rows(pg_engine, EligibilityAssessment) == [] and succeeded(pg_engine) == before


def test_assessment_mapper_routing_cannot_escape_the_current_transaction_engine(
        assessment_case_factory, pg_engine):
    case = assessment_case_factory()
    other, attempts = create_engine(pg_engine.url, hide_parameters=True), []
    def unexpected_connect(*args):
        attempts.append(True)
        raise AssertionError("A foreign assessment mapper must be rejected before connecting")
    event.listen(other, "do_connect", unexpected_connect)
    try:
        with Session(pg_engine, binds={EligibilityAssessment: other}) as session, session.begin():
            denied(lambda: case.service.evaluate(case.principal, case.request, session=session), 503)
    finally:
        other.dispose()
    assert attempts == [] and rows(pg_engine, EligibilityAssessment) == []


def test_server_bundle_stage_or_window_change_cannot_reuse_a_different_approved_literal(
        assessment_case_factory, clock):
    case = assessment_case_factory()
    assert case.service.evaluate(case.principal, case.request).eligibility.status == "eligible"
    original_stage, original_until = case.bundle.stage, case.bundle.valid_until
    try:
        # A valid DTO remains insufficient: only the already-published exact
        # descriptor proves the intended stage and window for this test rule.
        object.__setattr__(case.bundle, "stage", "enrollment")
        stage = case.service.evaluate(case.principal, case.request.model_copy(update={"stage": "enrollment"}))
        assert stage.eligibility.status == "unknown" and stage.eligibility.reason == "BINDING_UNAVAILABLE"
        assert stage.rule_refs == () and stage.ruleset_version is None
        object.__setattr__(case.bundle, "stage", original_stage)
        object.__setattr__(case.bundle, "valid_until", original_until + timedelta(hours=1))
        window = case.service.evaluate(case.principal, case.request)
        assert window.eligibility.status == "unknown" and window.eligibility.reason == "BINDING_UNAVAILABLE"
        assert window.rule_refs == () and window.ruleset_version is None
    finally:
        object.__setattr__(case.bundle, "stage", original_stage)
        object.__setattr__(case.bundle, "valid_until", original_until)
