"""Independent T34 sidecar, authority and actual PostgreSQL boundary checks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4
import re

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUser
from services.api.app.privacy.models import PrivacyAdmissionRecord
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T34_PRIVATE_FAILURE_SENTINEL"
SIDECAR_TABLES = ("change_event_receipts", "assessment_change_impacts", "plan_change_impacts")


def denied(operation, *statuses):
    with pytest.raises(ValueError) as failure:
        operation()
    assert getattr(failure.value, "status_code", None) in statuses
    assert SENTINEL not in str(failure.value) + repr(failure.value)
    return failure.value


def original_rows(engine):
    from services.api.app.assessments.models import AssessmentsBase
    from services.api.app.plans.models import PlansBase
    from services.api.app.plan_execution.models import ExecutionBase

    with engine.connect() as connection:
        rows = {name: connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
            for base in (AssessmentsBase, PlansBase, ExecutionBase)
            for name, table in base.metadata.tables.items()}
        rows["plan_registry"] = connection.execute(select(AuthOwnedResource.__table__).where(
            AuthOwnedResource.resource_type == "plan").order_by(AuthOwnedResource.id)).mappings().all()
    return rows


def sidecar_rows(engine):
    from services.api.app.changes.models import ChangesBase

    with engine.connect() as connection:
        return {name: connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
            for name, table in ChangesBase.metadata.tables.items()}


def succeeded(engine):
    with engine.connect() as connection:
        return set(connection.scalars(select(AuditEvent.id).where(AuditEvent.outcome == "succeeded")))


def withdraw(case):
    from services.api.app.releases.models import ChangeEvent
    from services.api.app.releases.schemas import WithdrawalRequest

    case.releases.withdraw(case.reviewer.principal, WithdrawalRequest(release_id=case.release.release_id,
        expected_state_revision=case.release.state_revision, reason_code="SOURCE_UNAVAILABLE"))
    with Session(case.service.store.engine) as session:
        return session.scalar(select(ChangeEvent.id).where(ChangeEvent.release_id == case.release.release_id,
            ChangeEvent.event_type == "withdrawn"))


def prepared(case, view=None):
    from services.api.app.plan_execution.schemas import ScheduleConfiguration, WorkspaceInput
    from services.api.app.plans.schemas import EstimateOverride
    from services.api.app.plans.schedule_schemas import AvailabilitySlot

    view = case.plan if view is None else view
    now = case.execution.auth_service._now()
    start, end = now + timedelta(minutes=5), now + timedelta(minutes=65)
    return case.execution.update_workspace(case.principal, view.plan_id, WorkspaceInput(
        expected_version=view.state_version,
        estimate_overrides=tuple(EstimateOverride(task_key=t.task_key, estimated_hours="0.01")
            for t in view.proposal.effective_draft.tasks),
        schedule=ScheduleConfiguration(horizon_start=start, horizon_end=end,
            display_timezone="Asia/Hong_Kong", weekly_hours="1",
            slots=(AvailabilitySlot(slot_id=uuid4(), start_at=start, end_at=end),),
            internal_goals=(), availability_confirmed=True, rest_excluded=True)))


def confirm_and_complete(case):
    from services.api.app.plan_execution.schemas import ConfirmInput, CompleteInput

    view = prepared(case)
    accepted = case.execution.confirm_plan(case.principal, view.plan_id, ConfirmInput(
        expected_version=view.state_version, expected_draft_sha256=view.proposal.effective_draft.draft_sha256,
        expected_schedule_sha256=view.proposal.schedule.schedule_sha256, confirmed=True,
        acknowledge_unverified_deadlines=True), SecretStr("DEMO_T34_EXPLICIT_CONFIRM")).execution
    task = next(t for t in accepted.proposal.effective_draft.tasks if not t.dependency_keys)
    return case.execution.complete_task(case.principal, accepted.plan_id, task.task_key,
        CompleteInput(expected_version=accepted.state_version, confirmed=True)).execution


def admit(case, actor):
    privacy = case.service.eligibility_service.profile_service.privacy_service
    principal = case.service.auth_service.get_principal(actor.cookie)
    before = privacy.get_admission(principal)
    age = privacy.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=before.notice_id, expected_revision=before.revision))
    privacy.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=age.notice_id, expected_revision=age.revision))
    return principal


def observe_lock(engine, worker_pid, blocker_pid, pending):
    deadline, pause = monotonic() + 40, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if pending.done():
                pending.result()
                pytest.fail("The changes worker completed before the required real PostgreSQL wait")
            connection.execute(text("SELECT pg_stat_clear_snapshot()"))
            if worker_pid and connection.scalar(text("SELECT wait_event_type='Lock' AND "
                ":blocker=ANY(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE pid=:pid"),
                {"blocker": blocker_pid, "pid": worker_pid[0]}):
                return
            pause.wait(0.01)
    pytest.fail("No actual PostgreSQL changes lock wait was observed")


def test_two_sessions_deduplicate_one_event_without_rewriting_confirmed_history(change_case_factory, pg_engine):
    case = change_case_factory()
    completed = confirm_and_complete(case)
    assert completed.completed_tasks
    event_id = withdraw(case)
    before = original_rows(pg_engine)
    lock_id = uuid4().int % (2**62)
    reached, second_started = Event(), Event()
    first_pid, second_pid = [], []
    selected_columns = []
    state = {"first": None, "second": None, "gated": False}

    def identify(connection, cursor, statement, parameters, context, executemany):
        if get_ident() in (state["first"], state["second"]):
            sql = " ".join(statement.lower().replace('"', '').split())
            if sql.startswith("select "):
                selected_columns.append(sql.split(" from ", 1)[0])
        if get_ident() == state["second"] and not second_pid:
            # Set a placeholder before nested SQL to prevent listener recursion.
            second_pid.append(0)
            second_pid[0] = connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
            second_started.set()

    def hold_written(connection, cursor, statement, parameters, context, executemany):
        if (get_ident() == state["first"] and not state["gated"]
            and statement.lower().startswith("insert into assessment_change_impacts")):
            state["gated"] = True
            first_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            reached.set()
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock_id,))

    event.listen(pg_engine, "before_cursor_execute", identify)
    event.listen(pg_engine, "after_cursor_execute", hold_written)
    try:
        with pg_engine.connect() as blocker:
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
            with ThreadPoolExecutor(max_workers=2) as pool:
                def first():
                    state["first"] = get_ident()
                    return case.service.process_event(event_id)
                def second():
                    state["second"] = get_ident()
                    return case.service.process_event(event_id)
                pending_first = pool.submit(first)
                try:
                    assert reached.wait(40), "The first real impact INSERT was not reached"
                    pending_second = pool.submit(second)
                    assert second_started.wait(20)
                    observe_lock(pg_engine, second_pid, first_pid[0], pending_second)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                first_result = pending_first.result(timeout=60)
                second_result = pending_second.result(timeout=60)
    finally:
        event.remove(pg_engine, "before_cursor_execute", identify)
        event.remove(pg_engine, "after_cursor_execute", hold_written)
    assert first_result.replayed is False and second_result.replayed is True
    assert any("eligibility_assessments" in projection for projection in selected_columns)
    # A JSONB target extraction is permitted; a whole private payload is not.
    # These are actual worker SELECT lists, excluding our own full-row snapshots.
    forbidden = re.compile(r"\b(?:eligibility_assessments|student_profile_versions)\."
        r"(?:payload|replay_snapshot|evaluation)\s*(?=,|$|as\b)")
    assert not any(forbidden.search(projection) for projection in selected_columns)
    assert not any(re.search(r"\b(?:replay_snapshot|evaluation)\s*(?=,|$|as\b)", projection)
        for projection in selected_columns)
    assert original_rows(pg_engine) == before
    rows = sidecar_rows(pg_engine)
    assert len(rows["change_event_receipts"]) == 1
    assert len(rows["assessment_change_impacts"]) == 1
    assert len(rows["plan_change_impacts"]) == 1
    assert len(case.service.get_plan_impacts(case.principal, completed.plan_id).items) == 1


def test_processed_impact_is_inherited_by_a_later_explicit_history_verification_plan(change_case_factory, pg_engine):
    case = change_case_factory()
    event_id = withdraw(case)
    case.service.process_event(event_id)
    sidecars = sidecar_rows(pg_engine)
    new_plan = case.execution.create_plan(case.principal, case.request)
    assert new_plan.plan_id != case.plan.plan_id
    assert all(t.action_code == "VERIFY_HISTORY" for t in new_plan.proposal.effective_draft.tasks)
    original = original_rows(pg_engine)
    page = case.service.get_plan_impacts(case.principal, new_plan.plan_id)
    assert len(page.items) == 1
    assert original_rows(pg_engine) == original
    assert sidecar_rows(pg_engine) == sidecars
    # Existing execution still refuses its old current-source action.
    denied(lambda: case.execution.get_plan(case.principal, case.plan.plan_id), 409)


def test_owner_only_change_trace_is_not_a_metadata_grant_or_admin_private_port(
        change_case_factory, actor_factory, pg_engine):
    from services.api.app.auth.grants.policy import POLICY_HASH, POLICY_VERSION
    from services.api.app.auth.grants.schemas import AcceptGrantInput, CreateGrantInput, SharingSettings
    from services.api.app.auth.grants.service import SharingService

    case = change_case_factory()
    recipient = actor_factory(role="student")
    receiver = admit(case, recipient)
    sharing = SharingService(case.service.auth_service,
        case.service.eligibility_service.profile_service.privacy_service, SharingSettings(fixture_mode=True))
    state = sharing.list_grants(case.principal)
    grant = sharing.create_grant(case.principal, CreateGrantInput(resource_type="plan", resource_id=case.plan.plan_id,
        expected_resource_version=1, grantee_user_id=recipient.user_id, fields=["status", "version"],
        actions=["read", "list"], expires_at=case.service.auth_service._now()+timedelta(minutes=5),
        confirmed=True, expected_revision=state.revision, owner_consent_id=state.owner_consent_id,
        sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH)).grant
    sharing.accept_grant(receiver, grant.id, AcceptGrantInput(confirmed=True, expected_version=grant.version,
        sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))
    assert sharing.require_shared(receiver, "plan", case.plan.plan_id, ("status", "version")).version == 1
    case.service.process_event(withdraw(case))
    before = sidecar_rows(pg_engine)
    for foreign in (receiver, case.reviewer.principal):
        denied(lambda: case.service.get_plan_impacts(foreign, case.plan.plan_id), 403, 404)
        denied(lambda: case.service.get_assessment_impacts(foreign, case.assessment.assessment_id), 403, 404)
    page = case.service.get_plan_impacts(case.principal, case.plan.plan_id)
    assert len(page.items) == 1
    encoded = page.model_dump_json()
    for forbidden in ("profile_sha256", "value_text", "quote", "file_id", "replay_snapshot", "owner_user_id"):
        assert forbidden not in encoded
    assert sidecar_rows(pg_engine) == before


def test_withdrawn_original_core_never_revives_trace_after_new_consent(change_case_factory, pg_engine):
    case = change_case_factory()
    case.service.process_event(withdraw(case))
    privacy = case.service.eligibility_service.profile_service.privacy_service
    admission = privacy.get_admission(case.principal)
    privacy.withdraw_core(case.principal, admission.consent_id)
    original, impacts = original_rows(pg_engine), sidecar_rows(pg_engine)
    denied(lambda: case.service.get_plan_impacts(case.principal, case.plan.plan_id), 403)
    new_principal = admit(case, case.owner)
    assert privacy.get_admission(new_principal).consent_id != admission.consent_id
    denied(lambda: case.service.get_plan_impacts(new_principal, case.plan.plan_id), 403, 409)
    denied(lambda: case.service.get_assessment_impacts(new_principal, case.assessment.assessment_id), 403, 409)
    assert original_rows(pg_engine) == original and sidecar_rows(pg_engine) == impacts


@pytest.mark.parametrize("boundary", ["session", "declaration"])
def test_real_required_audit_wait_cannot_return_a_trace_after_authority_expiry(
        change_case_factory, pg_engine, clock, boundary):
    case = change_case_factory()
    case.service.process_event(withdraw(case))
    deadline = clock() + timedelta(seconds=40)
    with Session(pg_engine) as same, same.begin():
        if boundary == "session":
            same.get(AuthSession, case.principal.session_id).expires_at = deadline
        else:
            for row in same.scalars(select(PrivacyAdmissionRecord).where(
                PrivacyAdmissionRecord.user_id == case.owner.user_id)):
                if row.declaration_expires_at is not None:
                    row.declaration_expires_at = deadline
    before, successful = sidecar_rows(pg_engine), succeeded(pg_engine)
    lock_id, reached, pid = uuid4().int % (2**62), Event(), []
    state = {"worker": None, "held": False}

    def gate(connection, cursor, statement, parameters, context, executemany):
        if (get_ident() == state["worker"] and not state["held"]
            and statement.lower().startswith("insert into auth_audit_events")):
            state["held"] = True
            pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            reached.set()
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock_id,))

    event.listen(pg_engine, "before_cursor_execute", gate)
    try:
        with pg_engine.connect() as blocker:
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            with ThreadPoolExecutor(max_workers=1) as pool:
                def attempt():
                    state["worker"] = get_ident()
                    return case.service.get_plan_impacts(case.principal, case.plan.plan_id)
                pending = pool.submit(attempt)
                try:
                    assert reached.wait(40), "The required private audit INSERT was not reached"
                    observe_lock(pg_engine, pid, blocker_pid, pending)
                    clock.advance(40)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                denied(lambda: pending.result(timeout=60), 401 if boundary == "session" else 403)
    finally:
        event.remove(pg_engine, "before_cursor_execute", gate)
    assert sidecar_rows(pg_engine) == before and succeeded(pg_engine) == successful


def test_real_deferred_commit_failure_rolls_back_all_sidecars_and_retries_exact_event(change_case_factory, pg_engine):
    case = change_case_factory()
    event_id = withdraw(case)
    before, original, successful = sidecar_rows(pg_engine), original_rows(pg_engine), succeeded(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t34_safety_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T34_PRIVATE_FAILURE_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t34_safety_fail_commit AFTER INSERT ON change_event_receipts "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t34_safety_fail_commit()"))
    try:
        denied(lambda: case.service.process_event(event_id), 503)
        assert sidecar_rows(pg_engine) == before and original_rows(pg_engine) == original
        assert succeeded(pg_engine) == successful
    finally:
        with pg_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER t34_safety_fail_commit ON change_event_receipts"))
            connection.execute(text("DROP FUNCTION t34_safety_fail_commit()"))
    result = case.service.process_event(event_id)
    assert result.replayed is False
    assert len(sidecar_rows(pg_engine)["change_event_receipts"]) == 1
    # Separately fail the required owner audit after real trace rows were read.
    # Processing reuses T19's existing audit reference, and creates no fake actor.
    before, original, successful = sidecar_rows(pg_engine), original_rows(pg_engine), succeeded(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t34_safety_fail_trace_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF NEW.outcome='succeeded' AND current_setting('t34.trace_read',true)='1' THEN "
            "RAISE EXCEPTION 'DEMO_T34_PRIVATE_FAILURE_SENTINEL' USING ERRCODE='23514'; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER t34_safety_fail_trace_audit BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION t34_safety_fail_trace_audit()"))
    trace_read = []
    def mark_trace(connection, cursor, statement, parameters, context, executemany):
        sql = " ".join(statement.lower().split())
        if sql.startswith("select ") and " from plan_change_impacts" in sql:
            trace_read.append(True)
            connection.exec_driver_sql("SELECT set_config('t34.trace_read','1',true)")
    event.listen(pg_engine, "after_cursor_execute", mark_trace)
    try:
        denied(lambda: case.service.get_plan_impacts(case.principal, case.plan.plan_id), 503)
        assert trace_read
    finally:
        event.remove(pg_engine, "after_cursor_execute", mark_trace)
        with pg_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER t34_safety_fail_trace_audit ON auth_audit_events"))
            connection.execute(text("DROP FUNCTION t34_safety_fail_trace_audit()"))
    assert sidecar_rows(pg_engine) == before and original_rows(pg_engine) == original
    assert succeeded(pg_engine) == successful


def test_caller_failure_aborts_prior_writes_even_when_caught_before_commit(change_case_factory, pg_engine):
    case = change_case_factory()
    case.service.process_event(withdraw(case))
    before = sidecar_rows(pg_engine)
    with Session(pg_engine) as same:
        same.begin()
        same.execute(text("UPDATE auth_users SET status='disabled' WHERE id=:id"), {"id":case.owner.user_id})
        denied(lambda: case.service.get_plan_impacts(case.principal, case.plan.plan_id, session=same), 401)
        same.commit()
    with Session(pg_engine) as same:
        assert same.get(AuthUser, case.owner.user_id).status == "active"
    assert sidecar_rows(pg_engine) == before


def test_default_gate_and_mixed_mapper_bindings_refuse_before_any_foreign_io(change_case_factory, pg_engine):
    from services.api.app.assessments.models import EligibilityAssessment
    from services.api.app.changes.models import ChangesBase
    from services.api.app.changes.schemas import ChangesPolicy
    from services.api.app.changes.service import ChangesService
    from services.api.app.profiles.models import ProfileVersion
    from services.api.app.releases.models import ChangeEvent

    case = change_case_factory()
    event_id = withdraw(case)
    closed = ChangesService(case.service.eligibility_service, case.execution, case.service.store, ChangesPolicy())
    observed = []
    def any_sql(*args):
        observed.append(True)
    event.listen(pg_engine, "before_cursor_execute", any_sql)
    try:
        denied(lambda: closed.process_event(event_id), 503)
        denied(lambda: closed.get_plan_impacts(case.principal, case.plan.plan_id), 503)
        assert observed == []
    finally:
        event.remove(pg_engine, "before_cursor_execute", any_sql)
    before = sidecar_rows(pg_engine)
    routed, connected = create_engine(pg_engine.url, hide_parameters=True), []
    event.listen(routed, "connect", lambda *args: connected.append(True))
    try:
        own = tuple(mapper.class_ for mapper in ChangesBase.registry.mappers)
        for mapper in (*own, EligibilityAssessment, ProfileVersion, ChangeEvent, AuditEvent):
            with Session(pg_engine, binds={mapper:routed}) as same:
                same.begin()
                denied(lambda: case.service.get_plan_impacts(case.principal, case.plan.plan_id, session=same), 503)
                same.commit()
        assert connected == []
    finally:
        routed.dispose()
    assert sidecar_rows(pg_engine) == before
