"""Independent T32 authority and commit-boundary checks on synthetic PG data.

No task completion changes grades, school facts or an external application.
The accepted metadata grant below grants no private execution capability.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUser
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T32_PRIVATE_FAILURE_SENTINEL"


def denied(operation, *statuses):
    with pytest.raises(ValueError) as failure:
        operation()
    assert getattr(failure.value, "status_code", None) in statuses
    assert SENTINEL not in str(failure.value) + repr(failure.value)
    return failure.value


def durable(engine):
    """Compare actual persistent rows; failure diagnostics may append denied events."""
    from services.api.app.idempotency.models import IdempotencyRecord
    from services.api.app.plan_execution.models import ExecutionBase
    from services.api.app.plans.models import PlansBase

    with engine.connect() as connection:
        tables = {
            name: connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
            for base in (PlansBase, ExecutionBase) for name, table in base.metadata.tables.items()
        }
        registry = connection.execute(select(AuthOwnedResource.__table__).where(
            AuthOwnedResource.resource_type == "plan").order_by(AuthOwnedResource.id)).mappings().all()
        receipts = connection.execute(select(IdempotencyRecord.__table__)
            .order_by(IdempotencyRecord.id)).mappings().all()
        succeeded = set(connection.scalars(select(AuditEvent.id).where(AuditEvent.outcome == "succeeded")))
    return tables, registry, receipts, succeeded


def admit(case, actor):
    identity = case.service.auth_service
    privacy = case.service.plans_service.eligibility_service.profile_service.privacy_service
    principal = identity.get_principal(actor.cookie)
    before = privacy.get_admission(principal)
    age = privacy.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=before.notice_id, expected_revision=before.revision))
    privacy.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=age.notice_id, expected_revision=age.revision))
    return principal


def observed_lock(engine, worker_pid, blocker_pid, pending):
    deadline, pause = monotonic() + 40, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if pending.done():
                pending.result()
                pytest.fail("The execution worker completed before the required real SQL wait")
            connection.execute(text("SELECT pg_stat_clear_snapshot()"))
            if worker_pid and connection.scalar(text("SELECT wait_event_type='Lock' AND "
                ":blocker=ANY(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE pid=:pid"),
                {"blocker": blocker_pid, "pid": worker_pid[0]}):
                return
            pause.wait(0.01)
    pytest.fail("No actual PostgreSQL execution lock wait was observed")


def ready(case, view=None):
    from services.api.app.plan_execution.schemas import ScheduleConfiguration, WorkspaceInput
    from services.api.app.plans.schemas import EstimateOverride
    from services.api.app.plans.schedule_schemas import AvailabilitySlot

    now = case.service.auth_service._now()
    # Keep availability in the future so authority/receipt expiry checks cannot
    # accidentally pass by encountering an already-started arrangement instead.
    starts_at, ends_at = now + timedelta(minutes=5), now + timedelta(minutes=65)
    original = case.plan if view is None else view
    return case.service.update_workspace(case.principal, original.plan_id, WorkspaceInput(
        expected_version=original.state_version,
        estimate_overrides=tuple(EstimateOverride(task_key=t.task_key, estimated_hours="0.01")
            for t in original.proposal.effective_draft.tasks),
        schedule=ScheduleConfiguration(horizon_start=starts_at, horizon_end=ends_at,
            display_timezone="Asia/Hong_Kong", weekly_hours="1",
            slots=(AvailabilitySlot(slot_id=uuid4(), start_at=starts_at,
                end_at=ends_at),), internal_goals=(),
            availability_confirmed=True, rest_excluded=True)))


def confirmation(view):
    from services.api.app.plan_execution.schemas import ConfirmInput
    return ConfirmInput(expected_version=view.state_version,
        expected_draft_sha256=view.proposal.effective_draft.draft_sha256,
        expected_schedule_sha256=view.proposal.schedule.schedule_sha256,
        confirmed=True, acknowledge_unverified_deadlines=True)


def completion(view):
    from services.api.app.plan_execution.schemas import CompleteInput
    return CompleteInput(expected_version=view.state_version, confirmed=True)


def independent_task(view):
    return next(t for t in view.proposal.effective_draft.tasks if not t.dependency_keys)


def test_accepted_metadata_grant_and_admin_cannot_confirm_complete_or_read_private_execution(
        execution_case_factory, actor_factory, pg_engine, clock):
    from services.api.app.auth.grants.policy import POLICY_HASH, POLICY_VERSION
    from services.api.app.auth.grants.schemas import AcceptGrantInput, CreateGrantInput, SharingSettings
    from services.api.app.auth.grants.service import SharingService

    case = execution_case_factory()
    proposal = ready(case)
    recipient = actor_factory()
    receiver = admit(case, recipient)
    sharing = SharingService(case.service.auth_service,
        case.service.plans_service.eligibility_service.profile_service.privacy_service,
        SharingSettings(fixture_mode=True))
    state = sharing.list_grants(case.principal)
    grant = sharing.create_grant(case.principal, CreateGrantInput(resource_type="plan",
        resource_id=proposal.plan_id, expected_resource_version=1, grantee_user_id=recipient.user_id,
        fields=["status", "version"], actions=["read", "list"], expires_at=clock() + timedelta(minutes=5),
        confirmed=True, expected_revision=state.revision, owner_consent_id=state.owner_consent_id,
        sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH)).grant
    sharing.accept_grant(receiver, grant.id, AcceptGrantInput(confirmed=True,
        expected_version=grant.version, sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))
    assert sharing.require_shared(receiver, "plan", proposal.plan_id, ("status", "version")).version == 1
    before = durable(pg_engine)
    for other in (receiver, case.reviewer.principal):
        denied(lambda: case.service.get_plan(other, proposal.plan_id), 403, 404)
        denied(lambda: case.service.confirm_plan(other, proposal.plan_id, confirmation(proposal),
            SecretStr("DEMO_T32_FOREIGN")), 403, 404)
    assert durable(pg_engine) == before
    result = case.service.confirm_plan(case.principal, proposal.plan_id, confirmation(proposal),
        SecretStr("DEMO_T32_OWNER"))
    before = durable(pg_engine)
    task = independent_task(result.execution)
    for other in (receiver, case.reviewer.principal):
        denied(lambda: case.service.complete_task(other, proposal.plan_id, task.task_key,
            completion(result.execution)), 403, 404)
    assert durable(pg_engine) == before


def test_old_core_consent_cannot_be_revived_for_read_confirmation_or_completion(
        execution_case_factory, pg_engine):
    case = execution_case_factory()
    proposal = ready(case)
    result = case.service.confirm_plan(case.principal, proposal.plan_id, confirmation(proposal),
        SecretStr("DEMO_T32_CONSENT"))
    privacy = case.service.plans_service.eligibility_service.profile_service.privacy_service
    admission = privacy.get_admission(case.principal)
    privacy.withdraw_core(case.principal, admission.consent_id)
    before = durable(pg_engine)
    task = independent_task(result.execution)
    for operation in (
        lambda: case.service.get_plan(case.principal, proposal.plan_id),
        lambda: case.service.confirm_plan(case.principal, proposal.plan_id, confirmation(proposal),
            SecretStr("DEMO_T32_CONSENT")),
        lambda: case.service.complete_task(case.principal, proposal.plan_id, task.task_key,
            completion(result.execution)),
    ):
        denied(operation, 403)
    assert durable(pg_engine) == before
    admit(case, case.owner)
    before = durable(pg_engine)
    for operation in (
        lambda: case.service.get_plan(case.principal, proposal.plan_id),
        lambda: case.service.confirm_plan(case.principal, proposal.plan_id, confirmation(proposal),
            SecretStr("DEMO_T32_CONSENT")),
        lambda: case.service.complete_task(case.principal, proposal.plan_id, task.task_key,
            completion(result.execution)),
    ):
        denied(operation, 403)
    assert durable(pg_engine) == before


def test_exact_confirmation_and_completion_replays_preserve_current_progress_and_old_history(
        execution_case_factory, pg_engine):
    from services.api.app.plan_execution.models import ExecutionConfirmation, TaskCompletion

    case = execution_case_factory()
    proposal = ready(case)
    request, key = confirmation(proposal), SecretStr("DEMO_T32_REPLAY")
    accepted = case.service.confirm_plan(case.principal, proposal.plan_id, request, key)
    assert accepted.replayed is False and accepted.execution.completed_tasks == ()
    task = independent_task(accepted.execution)
    finish_request = completion(accepted.execution)
    finished = case.service.complete_task(case.principal, proposal.plan_id, task.task_key, finish_request)
    assert not finished.replayed and len(finished.execution.completed_tasks) == 1
    repeated = case.service.confirm_plan(case.principal, proposal.plan_id, request, key)
    assert repeated.replayed is True
    assert repeated.execution == finished.execution
    assert repeated.confirmed_state_version == accepted.confirmed_state_version
    repeated_finish = case.service.complete_task(case.principal, proposal.plan_id, task.task_key, finish_request)
    assert repeated_finish.replayed is True and repeated_finish.execution == finished.execution
    before = durable(pg_engine)
    denied(lambda: case.service.complete_task(case.principal, proposal.plan_id, task.task_key,
        completion(finished.execution)), 409)
    denied(lambda: case.service.confirm_plan(case.principal, proposal.plan_id,
        request.model_copy(update={"expected_draft_sha256": "f" * 64}), key), 409)
    assert durable(pg_engine) == before
    old = case.service.get_version(case.principal, proposal.plan_id, accepted.confirmed_state_version)
    assert old.completed_tasks == () and old.confirmation == accepted.execution.confirmation
    assert case.service.get_plan(case.principal, proposal.plan_id).completed_tasks == finished.execution.completed_tasks
    with Session(pg_engine) as session:
        assert len(session.scalars(select(ExecutionConfirmation).where(
            ExecutionConfirmation.plan_id == proposal.plan_id)).all()) == 1
        assert len(session.scalars(select(TaskCompletion).where(
            TaskCompletion.plan_id == proposal.plan_id)).all()) == 1
        assert session.get(AuthOwnedResource, proposal.plan_id).version == 1


@pytest.mark.parametrize("operation", ["confirm", "complete"])
def test_two_actual_sessions_return_one_event_and_exact_replay_after_real_contention(
        execution_case_factory, pg_engine, operation):
    from services.api.app.plan_execution.models import ExecutionConfirmation, TaskCompletion

    case = execution_case_factory()
    proposal = ready(case)
    request, key = confirmation(proposal), SecretStr("DEMO_T32_CONCURRENT")
    if operation == "complete":
        accepted = case.service.confirm_plan(case.principal, proposal.plan_id, request, key).execution
        task, finish_request = independent_task(accepted), completion(accepted)
        operation_call = lambda: case.service.complete_task(case.principal, proposal.plan_id,
            task.task_key, finish_request)
        target_table = TaskCompletion.__tablename__
    else:
        operation_call = lambda: case.service.confirm_plan(case.principal, proposal.plan_id, request, key)
        target_table = ExecutionConfirmation.__tablename__
    lock_id = uuid4().int % (2 ** 62)
    reached, second_started = Event(), Event()
    state = {"first": None, "second": None, "written": False, "gated": False}
    first_pid, second_pid = [], []

    def gate(connection, cursor, statement, parameters, context, executemany):
        ident, lowered = get_ident(), statement.lower().strip()
        if lowered == "select pg_backend_pid()" or lowered.startswith("select pg_advisory"):
            return
        if (ident == state["second"] and not second_pid and "from auth_users" in lowered
            and "for update" in lowered):
            second_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            second_started.set()
        if ident != state["first"]:
            return
        if lowered.startswith("insert into " + target_table):
            first_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            state["written"] = True
        if state["written"] and not state["gated"] and lowered.startswith("insert into auth_audit_events"):
            state["gated"] = True
            reached.set()
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock_id,))

    event.listen(pg_engine, "before_cursor_execute", gate)
    try:
        with pg_engine.connect() as blocker:
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
            with ThreadPoolExecutor(max_workers=2) as pool:
                def first():
                    state["first"] = get_ident()
                    return operation_call()
                def second():
                    state["second"] = get_ident()
                    return operation_call()
                pending_first = pool.submit(first)
                try:
                    assert reached.wait(40), "First write did not reach its required following audit"
                    pending_second = pool.submit(second)
                    assert second_started.wait(20)
                    observed_lock(pg_engine, second_pid, first_pid[0], pending_second)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                first_result = pending_first.result(timeout=60)
                second_result = pending_second.result(timeout=60)
    finally:
        event.remove(pg_engine, "before_cursor_execute", gate)
    assert first_result.replayed is False and second_result.replayed is True
    assert first_result.execution == second_result.execution
    model = TaskCompletion if operation == "complete" else ExecutionConfirmation
    with Session(pg_engine) as session:
        assert len(session.scalars(select(model).where(model.plan_id == proposal.plan_id)).all()) == 1


@pytest.mark.parametrize("operation", ["confirm", "complete"])
def test_real_deferred_commit_failure_rolls_back_and_the_same_request_can_retry(
        execution_case_factory, pg_engine, operation):
    from services.api.app.plan_execution.models import ExecutionConfirmation, TaskCompletion

    case = execution_case_factory()
    proposal = ready(case)
    request, key = confirmation(proposal), SecretStr("DEMO_T32_COMMIT")
    if operation == "complete":
        accepted = case.service.confirm_plan(case.principal, proposal.plan_id, request, key).execution
        task, finish_request = independent_task(accepted), completion(accepted)
        attempt = lambda: case.service.complete_task(case.principal, proposal.plan_id, task.task_key, finish_request)
        target_table = TaskCompletion.__tablename__
    else:
        attempt = lambda: case.service.confirm_plan(case.principal, proposal.plan_id, request, key)
        target_table = ExecutionConfirmation.__tablename__
    before = durable(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t32_safety_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T32_PRIVATE_FAILURE_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text(f"CREATE CONSTRAINT TRIGGER t32_safety_fail_commit AFTER INSERT ON {target_table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t32_safety_fail_commit()"))
    try:
        denied(attempt, 503)
        assert durable(pg_engine) == before
    finally:
        with pg_engine.begin() as connection:
            connection.execute(text(f"DROP TRIGGER t32_safety_fail_commit ON {target_table}"))
            connection.execute(text("DROP FUNCTION t32_safety_fail_commit()"))
    result = attempt()
    assert result.replayed is False and result.execution.state == "confirmed"
    if operation == "complete":
        assert len(result.execution.completed_tasks) == 1


def test_supplied_transaction_failure_aborts_the_callers_earlier_changes(
        execution_case_factory, pg_engine):
    case = execution_case_factory()
    proposal = ready(case)
    before = durable(pg_engine)
    with Session(pg_engine) as session:
        session.begin()
        session.execute(text("UPDATE auth_users SET status='disabled' WHERE id=:id"),
            {"id": case.owner.user_id})
        denied(lambda: case.service.confirm_plan(case.principal, proposal.plan_id, confirmation(proposal),
            SecretStr("DEMO_T32_CALLER_ABORT"), session=session), 401)
        session.commit()
    with Session(pg_engine) as session:
        assert session.get(AuthUser, case.owner.user_id).status == "active"
    assert durable(pg_engine) == before


def test_default_real_gate_and_mapper_overrides_reject_before_foreign_database_io(
        execution_case_factory, pg_engine):
    from services.api.app.idempotency.models import IdempotencyRecord
    from services.api.app.plan_execution.models import ExecutionBase
    from services.api.app.plan_execution.schemas import ExecutionPolicy
    from services.api.app.plan_execution.service import ExecutionService
    from services.api.app.profiles.models import ProfileVersion

    case = execution_case_factory()
    before = durable(pg_engine)
    closed = ExecutionService(case.service.plans_service, case.service.idempotency_service,
        case.service.store, ExecutionPolicy())
    denied(lambda: closed.create_plan(case.principal, case.request), 503)
    routed, connected = create_engine(pg_engine.url, hide_parameters=True), []
    event.listen(routed, "connect", lambda *args: connected.append(True))
    try:
        own_mappers = tuple(mapper.class_ for mapper in ExecutionBase.registry.mappers)
        for mapper in (*own_mappers, ProfileVersion, IdempotencyRecord, AuditEvent):
            with Session(pg_engine, binds={mapper: routed}) as session:
                session.begin()
                denied(lambda: case.service.get_plan(case.principal, case.plan.plan_id, session=session), 503)
                session.commit()
        assert connected == []
    finally:
        routed.dispose()
    assert durable(pg_engine) == before


def test_withdrawn_source_blocks_old_action_but_a_new_verification_only_plan_can_be_confirmed(
        execution_case_factory, pg_engine):
    from services.api.app.releases.schemas import WithdrawalRequest

    case = execution_case_factory(deferral=True, expression={"op": "gte", "field": {
        "name": "assessment", "key": "math", "basis": "achieved"}, "value": {
        "kind": "decimal", "value": "90", "unit": "points", "scale": "150"}})
    assert case.assessment.eligibility.status == "conditional"
    proposal = ready(case)
    accepted = case.service.confirm_plan(case.principal, proposal.plan_id, confirmation(proposal),
        SecretStr("DEMO_T32_WITHDRAWN"))
    case.releases.withdraw(case.reviewer.principal, WithdrawalRequest(release_id=case.release.release_id,
        expected_state_revision=case.release.state_revision, reason_code="SOURCE_UNAVAILABLE"))
    task = independent_task(accepted.execution)
    before = durable(pg_engine)
    denied(lambda: case.service.get_plan(case.principal, proposal.plan_id), 409)
    denied(lambda: case.service.confirm_plan(case.principal, proposal.plan_id, confirmation(proposal),
        SecretStr("DEMO_T32_WITHDRAWN")), 409)
    denied(lambda: case.service.complete_task(case.principal, proposal.plan_id, task.task_key,
        completion(accepted.execution)), 409)
    assert durable(pg_engine) == before
    new_plan = case.service.create_plan(case.principal, case.request)
    assert new_plan.plan_id != proposal.plan_id
    assert all(t.action_code == "VERIFY_HISTORY" for t in new_plan.proposal.effective_draft.tasks)
    assert new_plan.proposal.effective_draft.deadline_refs == ()
    prepared = ready(case, new_plan)
    fresh = case.service.confirm_plan(case.principal, new_plan.plan_id, confirmation(prepared),
        SecretStr("DEMO_T32_EXPLICIT_VERIFICATION"))
    assert fresh.execution.state == "confirmed"
    assert fresh.execution.proposal.schedule.constraints_complete is False
    assert all(t.action_code == "VERIFY_HISTORY" for t in fresh.execution.proposal.effective_draft.tasks)


@pytest.mark.parametrize("deadline,status", [("original_file", 409), ("session", 401), ("receipt", 409)])
def test_last_sql_after_idempotency_returns_cannot_extend_any_current_deadline(
        execution_case_factory, pg_engine, clock, monkeypatch, deadline, status):
    import sys

    options = {"file_lifetime_seconds": 40} if deadline == "original_file" else {}
    case = execution_case_factory(**options)
    proposal = ready(case)
    if deadline == "session":
        with Session(pg_engine) as session, session.begin():
            session.get(AuthSession, case.principal.session_id).expires_at = clock() + timedelta(seconds=40)
    elif deadline == "receipt":
        from services.api.app.idempotency.schemas import IdempotencyPolicy
        from services.api.app.idempotency.service import IdempotencyService
        from services.api.app.plan_execution.service import ExecutionService

        original = case.service
        # An explicitly configured short receipt is a test fixture. It changes
        # no frozen policy, school fact, file expiry or product retention choice.
        short = IdempotencyService(original.auth_service, original.idempotency_service.privacy_service,
            original.idempotency_service.store, IdempotencyPolicy(enabled=True, ttl_seconds=1))
        case.service = ExecutionService(original.plans_service, short, original.store, original.policy)
    before = durable(pg_engine)
    profiles = case.service.plans_service.eligibility_service.profile_service
    original_final, original_profile_final = case.service._final, profiles._final
    direct_final_code = original_final.__func__.__code__
    reached, worker_pid = Event(), []
    lock_id = uuid4().int % (2 ** 62)
    marker = "t32_safety_after_idempotency"
    role_marker = "t32_safety_last_roles"

    def outer_final(session, *args, **kwargs):
        # receipt_expiry is supplied only after the real T49 execute returned,
        # including both mandatory resource verifiers and its final authority.
        connection = session.connection()
        active = kwargs.get("receipt_expiry") is not None
        if active:
            connection.info[marker] = True
        try:
            return original_final(session, *args, **kwargs)
        finally:
            if active:
                connection.info.pop(marker, None)

    def last_profile_final(session, *args, **kwargs):
        connection = session.connection()
        # Nested source readers also use Profile._final. Observe precisely the
        # direct final authority call in Execution._final, after all proofs.
        active = connection.info.get(marker) and sys._getframe(1).f_code is direct_final_code
        if active:
            connection.info[role_marker] = 0
        try:
            return original_profile_final(session, *args, **kwargs)
        finally:
            if active:
                connection.info.pop(role_marker, None)

    def gate(connection, cursor, statement, parameters, context, executemany):
        if (role_marker in connection.info and "FROM auth_user_roles" in statement
            and "FOR UPDATE" in statement.upper()):
            connection.info[role_marker] += 1
            # Profile._final refreshes roles, then explicitly reads them last.
            if connection.info[role_marker] == 2:
                worker_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                reached.set()
                connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock_id,))

    monkeypatch.setattr(case.service, "_final", outer_final)
    monkeypatch.setattr(profiles, "_final", last_profile_final)
    event.listen(pg_engine, "after_cursor_execute", gate)
    try:
        with pg_engine.connect() as blocker:
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(case.service.confirm_plan, case.principal, proposal.plan_id,
                    confirmation(proposal), SecretStr("DEMO_T32_LAST_SQL"))
                try:
                    assert reached.wait(40), "Confirmation did not reach its actual post-T49 last role SQL"
                    observed_lock(pg_engine, worker_pid, blocker_pid, pending)
                    clock.advance(2 if deadline == "receipt" else 40)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                denied(lambda: pending.result(timeout=60), status)
    finally:
        event.remove(pg_engine, "after_cursor_execute", gate)
    assert len(worker_pid) == 1 and durable(pg_engine) == before
