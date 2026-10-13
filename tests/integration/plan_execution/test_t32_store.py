"""T32 storage projections over the actual published synthetic pipeline."""

from datetime import timedelta
import json
from uuid import uuid4

from pydantic import SecretStr
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from services.api.app.audit.service import AuditError

from services.api.app.plan_execution.schemas import (
    CompleteInput, ConfirmInput, ExecutionError, ScheduleConfiguration, WorkspaceInput,
)
from services.api.app.plans.schemas import EstimateOverride
from services.api.app.plans.schedule_schemas import AvailabilitySlot

pytestmark = pytest.mark.postgres


def workspace_input(case, current, *, hours="0.01", capacity="1", clear=False, start_offset=timedelta()):
    now = case.service.auth_service._now()+start_offset
    configuration = None if clear else ScheduleConfiguration(
        horizon_start=now, horizon_end=now + timedelta(hours=1), display_timezone="UTC",
        weekly_hours=capacity, availability_confirmed=True, rest_excluded=True,
        slots=(AvailabilitySlot(slot_id=uuid4(), start_at=now, end_at=now + timedelta(hours=1)),),
        internal_goals=(),
    )
    return WorkspaceInput(expected_version=current.state_version,
        estimate_overrides=tuple(EstimateOverride(task_key=t.task_key, estimated_hours=hours)
            for t in current.proposal.effective_draft.tasks), schedule=configuration)


def workspace(case, **options):
    current = case.service.get_plan(case.principal, case.plan.plan_id)
    return case.service.update_workspace(case.principal,current.plan_id,workspace_input(case,current,**options))


def confirm(case, value, *, key="DEMO_T32_STORE"):
    request = ConfirmInput(expected_version=value.state_version,
        expected_draft_sha256=value.proposal.effective_draft.draft_sha256,
        expected_schedule_sha256=value.proposal.schedule.schedule_sha256,
        confirmed=True, acknowledge_unverified_deadlines=True)
    result = case.service.confirm_plan(case.principal, value.plan_id, request, SecretStr(key))
    return result, request


def old_rows(engine, plan_id):
    with engine.connect() as connection:
        return tuple(connection.execute(text(statement), {"id": plan_id}).all() for statement in (
            "SELECT current_version_id FROM plan_draft_roots WHERE id=:id",
            "SELECT id,payload,audit_event_id FROM plan_draft_versions WHERE plan_id=:id ORDER BY id",
            "SELECT task_key,payload FROM plan_draft_tasks WHERE plan_id=:id ORDER BY task_key",
            "SELECT version FROM auth_owned_resources WHERE id=:id",
        ))


def count(engine, table):
    with engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM " + table)).scalar_one()


def test_full_lifecycle_keeps_t30_and_registry_immutable_and_returns_as_of_history(execution_case_factory, pg_engine):
    case = execution_case_factory()
    initial = case.plan
    frozen = old_rows(pg_engine, initial.plan_id)
    ready = workspace(case)
    assert ready.state_version == 2 and ready.proposal.schedule.status == "ready"
    assert ready.proposal.effective_draft.confirmed is False
    assert ready.proposal.schedule.constraints_complete is False
    confirmed, request = confirm(case, ready)
    assert confirmed.confirmed_state_version == 3
    latest = confirmed.execution
    for task in ready.proposal.schedule.tasks:
        latest = case.service.complete_task(case.principal, latest.plan_id, task.task_key,
            CompleteInput(expected_version=latest.state_version, confirmed=True)).execution
    replay = case.service.confirm_plan(case.principal, ready.plan_id, request, SecretStr("DEMO_T32_STORE"))
    assert replay.replayed is True and replay.execution == latest
    assert replay.confirmed_state_version == 3
    assert old_rows(pg_engine, initial.plan_id) == frozen
    assert case.service.get_version(case.principal, initial.plan_id, 1) == initial
    assert case.service.get_version(case.principal, initial.plan_id, 2) == ready
    old_confirm = case.service.get_version(case.principal, initial.plan_id, 3)
    assert old_confirm.confirmation.id == confirmed.execution.confirmation.id and old_confirm.completed_tasks == ()
    assert count(pg_engine, "plan_execution_confirmations") == 1
    assert count(pg_engine, "plan_task_completions") == len(ready.proposal.schedule.tasks)


def test_workspace_clear_is_a_new_proposal_and_stale_cas_preserves_all_rows(execution_case_factory, pg_engine):
    case = execution_case_factory()
    frozen = old_rows(pg_engine, case.plan.plan_id)
    ready = workspace(case)
    cleared = workspace(case, hours=None, clear=True)
    assert cleared.state_version == 3 and cleared.proposal.schedule is None
    assert all(t.estimated_hours is None for t in cleared.proposal.effective_draft.tasks)
    assert old_rows(pg_engine, case.plan.plan_id) == frozen
    before = count(pg_engine, "plan_execution_proposals")
    with pytest.raises(ExecutionError) as error:
        case.service.update_workspace(case.principal, case.plan.plan_id,
            WorkspaceInput(expected_version=ready.state_version, estimate_overrides=(), schedule=None))
    assert error.value.status_code == 409
    assert case.service.get_plan(case.principal, case.plan.plan_id) == cleared
    assert count(pg_engine, "plan_execution_proposals") == before


def test_zero_hours_still_require_manual_completion_and_dependency_order(execution_case_factory, pg_engine):
    case = execution_case_factory(deferral=True,expression={"op":"gte",
        "field":{"name":"assessment","key":"math","basis":"achieved"},
        "value":{"kind":"decimal","value":"100","unit":"points","scale":"150"}})
    ready = workspace(case, hours="0", capacity="0")
    assert ready.proposal.schedule.status == "ready" and ready.proposal.schedule.allocations == ()
    confirmed, _ = confirm(case, ready)
    latest = confirmed.execution
    assert latest.completed_tasks == ()
    child = next(t for t in ready.proposal.effective_draft.tasks if t.dependency_keys)
    with pytest.raises(ExecutionError) as error:
        case.service.complete_task(case.principal, ready.plan_id, child.task_key,
            CompleteInput(expected_version=latest.state_version, confirmed=True))
    assert error.value.status_code == 409 and count(pg_engine, "plan_task_completions") == 0
    for task in ready.proposal.schedule.tasks:
        latest = case.service.complete_task(case.principal, latest.plan_id, task.task_key,
            CompleteInput(expected_version=latest.state_version, confirmed=True)).execution
    assert len(latest.completed_tasks) == len(ready.proposal.effective_draft.tasks)
    assert all(c.source == "student_declared" for c in latest.completed_tasks)


def test_confirm_rejects_unknown_capacity_without_claim_or_confirmation(execution_case_factory, pg_engine):
    case = execution_case_factory()
    blocked = workspace(case, capacity=None)
    assert blocked.proposal.schedule.status == "blocked"
    claims = count(pg_engine, "idempotency_records")
    with pytest.raises(ExecutionError) as error:
        confirm(case, blocked)
    assert error.value.status_code == 409
    assert count(pg_engine, "idempotency_records") == claims
    assert count(pg_engine, "plan_execution_confirmations") == 0
    assert case.service.get_plan(case.principal, blocked.plan_id).state == "draft"


def test_confirmed_schedule_is_recomputed_from_stored_availability_before_progress(execution_case_factory, pg_engine):
    case = execution_case_factory()
    ready = workspace(case)
    confirmed, _ = confirm(case, ready)
    # The existing schedule remains self-consistent, but its slot no longer exists.
    shifted = ready.proposal.schedule_configuration.slots[0]
    new_slot=AvailabilitySlot(slot_id=shifted.slot_id,start_at=shifted.start_at+timedelta(minutes=30),end_at=shifted.end_at)
    changed=ScheduleConfiguration.model_validate(ready.proposal.schedule_configuration.model_copy(update={"slots":(new_slot,)})).model_dump(mode="json")
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE plan_execution_proposals DISABLE TRIGGER plan_execution_proposals_no_update"))
        connection.execute(text("UPDATE plan_execution_proposals SET payload=jsonb_set(payload,'{schedule_configuration}',CAST(:payload AS jsonb)) WHERE id=:id"),
            {"payload":json.dumps(changed), "id":ready.proposal.id})
        connection.execute(text("ALTER TABLE plan_execution_proposals ENABLE TRIGGER plan_execution_proposals_no_update"))
    first = ready.proposal.schedule.tasks[0]
    with pytest.raises(ExecutionError) as error:
        case.service.complete_task(case.principal, ready.plan_id, first.task_key,
            CompleteInput(expected_version=confirmed.execution.state_version, confirmed=True))
    assert error.value.status_code == 409
    assert count(pg_engine, "plan_task_completions") == 0
    with pytest.raises(ExecutionError) as read_error:
        case.service.get_plan(case.principal, ready.plan_id)
    assert read_error.value.status_code == 409


def test_returned_history_creation_time_is_checked_even_when_latest_is_current(execution_case_factory, pg_engine):
    case = execution_case_factory()
    ready = workspace(case)
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE plan_execution_proposals DISABLE TRIGGER plan_execution_proposals_no_update"))
        connection.execute(text("UPDATE plan_execution_proposals SET created_at=:future WHERE id=:id"),
            {"future":case.service.auth_service._now()+timedelta(seconds=5), "id":case.plan.proposal.id})
        connection.execute(text("ALTER TABLE plan_execution_proposals ENABLE TRIGGER plan_execution_proposals_no_update"))
    assert case.service.get_plan(case.principal, ready.plan_id) == ready
    with pytest.raises(ExecutionError) as error:
        case.service.get_version(case.principal, ready.plan_id, 1)
    assert error.value.status_code == 409


def test_required_new_proposal_failure_rolls_back_head_and_success_audits(execution_case_factory, pg_engine):
    case = execution_case_factory()
    current = case.service.get_plan(case.principal,case.plan.plan_id)
    request = workspace_input(case,current)
    before = count(pg_engine,"plan_execution_proposals")
    with pg_engine.connect() as connection:
        succeeded_before = connection.execute(text("SELECT count(*) FROM auth_audit_events WHERE outcome='succeeded'")).scalar_one()
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION demo_t32_fail_proposal() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'DEMO failure' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE TRIGGER demo_t32_failure BEFORE INSERT ON plan_execution_proposals FOR EACH ROW EXECUTE FUNCTION demo_t32_fail_proposal()"))
    with pytest.raises(ExecutionError) as error:
        case.service.update_workspace(case.principal,current.plan_id,request)
    assert error.value.status_code == 503
    # Failure audit may be emitted separately; durable success events must not survive.
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT state_version,current_proposal_id FROM plan_execution_heads WHERE plan_id=:id"),
            {"id":case.plan.plan_id}).one() == (1,case.plan.proposal.id)
        successes=connection.execute(text("SELECT count(*) FROM auth_audit_events WHERE outcome='succeeded'")).scalar_one()
    assert count(pg_engine,"plan_execution_proposals") == before
    assert successes == succeeded_before


def test_first_confirmation_rejects_elapsed_proposal_but_confirmed_past_work_remains_completable(execution_case_factory, pg_engine):
    case = execution_case_factory()
    elapsed = workspace(case)
    case.service.auth_service.clock.advance(1)
    claims = count(pg_engine,"idempotency_records")
    with pytest.raises(ExecutionError) as error:
        confirm(case,elapsed,key="DEMO_T32_ELAPSED")
    assert error.value.status_code == 409
    assert count(pg_engine,"idempotency_records") == claims
    assert count(pg_engine,"plan_execution_confirmations") == 0
    future = workspace(case,start_offset=timedelta(minutes=2))
    confirmed,request = confirm(case,future,key="DEMO_T32_FUTURE")
    # Allocations have passed, while the original session/release/receipt remain current.
    case.service.auth_service.clock.advance(600)
    assert case.service.get_plan(case.principal,future.plan_id) == confirmed.execution
    replay = case.service.confirm_plan(case.principal,future.plan_id,request,SecretStr("DEMO_T32_FUTURE"))
    assert replay.replayed is True
    current = replay.execution
    for task in future.proposal.schedule.tasks:
        current = case.service.complete_task(case.principal,current.plan_id,task.task_key,
            CompleteInput(expected_version=current.state_version,confirmed=True)).execution
    assert len(current.completed_tasks) == len(future.proposal.schedule.tasks)


def test_own_migration_roundtrip_preserves_parent_heads_and_enforces_history_fk_and_budget(execution_store,execution_case_factory,pg_engine):
    from alembic import command
    from services.api.app.plan_execution.models import ExecutionBase
    from services.api.app.plan_execution.store import HEADS,migrate_execution,migration_config
    def parent_heads():
        with pg_engine.connect() as connection:
            return {name:connection.execute(text("SELECT version_num FROM "+name)).scalars().all() for name in HEADS}
    frozen = parent_heads()
    with pg_engine.begin() as connection:
        config=migration_config()
        config.attributes["connection"]=connection
        command.downgrade(config,"base")
        assert all(connection.scalar(text("SELECT to_regclass(:name)"),{"name":name}) is None
            for name in ExecutionBase.metadata.tables)
    assert parent_heads() == frozen
    migrate_execution(pg_engine)
    execution_store.assert_schema_ready()
    assert parent_heads() == frozen
    case=execution_case_factory()
    ready=workspace(case)
    confirmed,_=confirm(case,ready)
    first=ready.proposal.schedule.tasks[0]
    case.service.complete_task(case.principal,ready.plan_id,first.task_key,
        CompleteInput(expected_version=confirmed.execution.state_version,confirmed=True))
    for table in ("plan_execution_proposals","plan_execution_confirmations","plan_task_completions"):
        with pytest.raises(IntegrityError) as error:
            with pg_engine.begin() as connection:
                connection.execute(text("UPDATE "+table+" SET audit_event_id=audit_event_id"))
        assert error.value.orig.sqlstate == "23514"
    proposal_columns="id,plan_id,source_version_id,owner_user_id,is_synthetic,state_version,payload,draft_sha256,schedule_sha256,created_at,expires_at,audit_event_id"
    for field in ("owner_user_id","source_version_id"):
        selected={name:name for name in proposal_columns.split(",")}
        selected.update(id=":new_id",state_version="99")
        selected[field]=":foreign_id"
        with pytest.raises(IntegrityError) as error:
            with pg_engine.begin() as connection:
                connection.execute(text("INSERT INTO plan_execution_proposals ("+proposal_columns+") SELECT "+
                    ",".join(selected.values())+" FROM plan_execution_proposals WHERE id=:original"),
                    {"new_id":uuid4(),"foreign_id":uuid4(),"original":ready.proposal.id})
        assert error.value.orig.sqlstate == "23503"
    with pytest.raises(IntegrityError) as error:
        with pg_engine.begin() as connection:
            connection.execute(text("INSERT INTO plan_task_completions (id,plan_id,source_version_id,owner_user_id,is_synthetic,confirmation_id,task_key,state_version,request_sha256,source,completed_at,expires_at,audit_event_id) SELECT :new_id,plan_id,source_version_id,owner_user_id,is_synthetic,confirmation_id,:unknown_key,99,request_sha256,source,completed_at,expires_at,audit_event_id FROM plan_task_completions LIMIT 1"),
                {"new_id":uuid4(),"unknown_key":"f"*64})
    assert error.value.orig.sqlstate == "23503"
    with pytest.raises(IntegrityError) as error:
        with pg_engine.begin() as connection:
            connection.execute(text("INSERT INTO plan_execution_proposals ("+proposal_columns+") SELECT :new_id,plan_id,source_version_id,owner_user_id,is_synthetic,99,jsonb_build_object('text',repeat('x',1048576)),draft_sha256,schedule_sha256,created_at,expires_at,audit_event_id FROM plan_execution_proposals WHERE id=:original"),
                {"new_id":uuid4(),"original":ready.proposal.id})
    assert error.value.orig.sqlstate == "23514"


def test_required_success_audit_insert_failure_leaves_no_new_proposal_or_head_change(execution_case_factory,pg_engine):
    case=execution_case_factory()
    current=case.service.get_plan(case.principal,case.plan.plan_id)
    request=workspace_input(case,current)
    proposals=count(pg_engine,"plan_execution_proposals")
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION demo_t32_fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.outcome='succeeded' AND NEW.action='authorization.owned.execute' AND NEW.object_type='plan' AND NEW.object_version=2 THEN RAISE EXCEPTION 'DEMO audit failure' USING ERRCODE='23514'; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER demo_t32_required_audit BEFORE INSERT ON auth_audit_events FOR EACH ROW EXECUTE FUNCTION demo_t32_fail_audit()"))
    with pytest.raises(AuditError) as error:
        case.service.update_workspace(case.principal,current.plan_id,request)
    assert error.value.status_code == 503
    assert count(pg_engine,"plan_execution_proposals") == proposals
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT state_version,current_proposal_id FROM plan_execution_heads WHERE plan_id=:id"),
            {"id":current.plan_id}).one() == (current.state_version,current.proposal.id)
