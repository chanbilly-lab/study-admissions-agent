"""Independent T30 authority and final-wait checks against the real PG chain.

These cases use synthetic profiles and actually published synthetic evidence.
They do not make a plan confirmation, grant private business access, or schedule.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, get_ident
from time import monotonic

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthOwnedResource, AuthUser
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from services.api.app.releases.schemas import WithdrawalRequest


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T30_PRIVATE_SENTINEL"


def denied(operation, *statuses):
    with pytest.raises(ValueError) as failure:
        operation()
    assert getattr(failure.value, "status_code", None) in statuses
    assert SENTINEL not in str(failure.value) + repr(failure.value)
    return failure.value


def durable(engine):
    from services.api.app.plans.models import PlansBase
    with engine.connect() as connection:
        tables = {name: connection.execute(select(table).order_by(*table.primary_key.columns))
            .mappings().all() for name, table in PlansBase.metadata.tables.items()}
        registry = connection.execute(select(AuthOwnedResource.__table__).where(
            AuthOwnedResource.resource_type == "plan").order_by(AuthOwnedResource.id)).mappings().all()
        success = set(connection.scalars(select(AuditEvent.id).where(AuditEvent.outcome == "succeeded")))
    return tables, registry, success


def admit(case, actor):
    identity = case.eligibility.auth_service
    privacy = case.eligibility.profile_service.privacy_service
    principal = identity.get_principal(actor.cookie)
    before = privacy.get_admission(principal)
    age = privacy.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=before.notice_id, expected_revision=before.revision))
    privacy.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=age.notice_id, expected_revision=age.revision))
    return principal


def test_real_metadata_grant_does_not_authorize_private_draft_or_foreign_sources(
        plan_case_factory, actor_factory, pg_engine, clock):
    from services.api.app.auth.grants.policy import POLICY_HASH, POLICY_VERSION
    from services.api.app.auth.grants.schemas import AcceptGrantInput, CreateGrantInput, SharingSettings
    from services.api.app.auth.grants.service import SharingService

    case = plan_case_factory()
    saved = case.service.create_draft(case.principal, case.request)
    recipient = actor_factory()
    recipient_principal = admit(case, recipient)
    sharing = SharingService(case.eligibility.auth_service,
        case.eligibility.profile_service.privacy_service, SharingSettings(fixture_mode=True))
    owner_state = sharing.list_grants(case.principal)
    grant = sharing.create_grant(case.principal, CreateGrantInput(resource_type="plan",
        resource_id=saved.plan_id, expected_resource_version=1, grantee_user_id=recipient.user_id,
        fields=["status", "version"], actions=["read", "list"], expires_at=clock()+timedelta(minutes=5),
        confirmed=True, expected_revision=owner_state.revision, owner_consent_id=owner_state.owner_consent_id,
        sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH)).grant
    sharing.accept_grant(recipient_principal, grant.id, AcceptGrantInput(confirmed=True,
        expected_version=grant.version, sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))
    projection = sharing.require_shared(recipient_principal, "plan", saved.plan_id, ("status", "version"))
    assert projection.version == 1 and projection.status == "active"
    before = durable(pg_engine)
    for other in (recipient_principal, case.reviewer.principal):
        denied(lambda: case.service.get_draft(other, saved.plan_id), 403, 404)
        denied(lambda: case.service.create_draft(other, case.request), 403, 404)
    assert durable(pg_engine) == before
    assert case.service.get_draft(case.principal, saved.plan_id).draft == saved.draft


def test_withdraw_and_reconfirm_cannot_revive_original_draft_source_proof(
        plan_case_factory, pg_engine):
    case = plan_case_factory()
    saved = case.service.create_draft(case.principal, case.request)
    privacy = case.eligibility.profile_service.privacy_service
    admission = privacy.get_admission(case.principal)
    privacy.withdraw_core(case.principal, admission.consent_id)
    denied(lambda: case.service.get_draft(case.principal, saved.plan_id), 403)
    denied(lambda: case.service.create_draft(case.principal, case.request), 403)
    admit(case, case.owner)
    before = durable(pg_engine)
    denied(lambda: case.service.get_draft(case.principal, saved.plan_id), 403)
    denied(lambda: case.service.create_draft(case.principal, case.request), 403)
    assert durable(pg_engine) == before


def test_withdrawn_conditional_history_produces_verification_only_without_obsolete_actions(
        plan_case_factory):
    case = plan_case_factory(deferral=True, expression={"op": "gte", "field": {
        "name": "assessment", "key": "math", "basis": "achieved"}, "value": {
        "kind": "decimal", "value": "90", "unit": "points", "scale": "150"}})
    assert case.assessment.eligibility.status == "conditional"
    case.releases.withdraw(case.reviewer.principal, WithdrawalRequest(release_id=case.release.release_id,
        expected_state_revision=case.release.state_revision, reason_code="SOURCE_UNAVAILABLE"))
    historical = case.eligibility.get_assessment(case.principal, case.assessment.assessment_id)
    assert historical.current_validity == "withdrawn" and historical.eligibility.status == "conditional"
    saved = case.service.create_draft(case.principal, case.request)
    assert all(task.kind == "verify" for task in saved.draft.tasks)
    assert not saved.draft.deadline_refs


def test_ruleset_unavailable_unknown_is_a_real_verification_draft(plan_case_factory):
    case = plan_case_factory(binding=False)
    assert case.assessment.current_validity == "unavailable"
    assert case.assessment.eligibility.status == "unknown"
    saved = case.service.create_draft(case.principal, case.request)
    assert saved.draft.tasks and all(task.kind == "verify" for task in saved.draft.tasks)
    assert saved.draft.confirmed is False and saved.draft.status == "draft"


def observed_lock(engine, worker_pid, blocker_pid, pending):
    deadline, pause = monotonic()+30, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if pending.done():
                pending.result()
                pytest.fail("The plan worker finished before the required actual SQL wait")
            if worker_pid and connection.scalar(text("SELECT wait_event_type='Lock' AND "
                    ":blocker=ANY(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE pid=:pid"),
                    {"blocker": blocker_pid, "pid": worker_pid[0]}):
                return
            pause.wait(0.01)
    pytest.fail("No actual PostgreSQL plan lock wait was observed")


@pytest.mark.parametrize("deadline", ["original_file", "application_deadline"])
def test_required_audit_wait_past_current_deadline_rolls_back_all_new_plan_rows(
        plan_case_factory, pg_engine, clock, deadline):
    from services.api.app.plans.models import PlansBase

    if deadline=="original_file":
        case = plan_case_factory(file_lifetime_seconds=40)
    else:
        case = plan_case_factory(deferral=True, expression={"op":"gte","field":{
            "name":"assessment","key":"math","basis":"achieved"},"value":{
            "kind":"decimal","value":"90","unit":"points","scale":"150"}})
        assert case.assessment.eligibility.status=="conditional"
        assert case.deferral.application_deadline.date_event.calculated_utc_instant==clock()+timedelta(seconds=40)
    before = durable(pg_engine)
    state = {"thread": None, "written": False}
    worker_pid, reached = [], Event()
    plan_tables = tuple(PlansBase.metadata.tables)
    lock_id = 30_041_927

    def gate(connection, cursor, statement, parameters, context, executemany):
        if get_ident() != state["thread"]:
            return
        if statement.lower().strip()=="select pg_backend_pid()":
            return
        if not worker_pid:
            worker_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
        lower = statement.lower()
        if lower.startswith("insert into ") and any(name in lower for name in plan_tables):
            state["written"] = True
        if state["written"] and lower.startswith("insert into auth_audit_events"):
            reached.set()
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock_id,))

    event.listen(pg_engine, "before_cursor_execute", gate)
    try:
        with pg_engine.connect() as blocker:
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
            with ThreadPoolExecutor(max_workers=1) as pool:
                def create():
                    state["thread"] = get_ident()
                    return case.service.create_draft(case.principal, case.request)
                pending = pool.submit(create)
                try:
                    assert reached.wait(30), "Required audit was not reached after actual plan INSERT"
                    observed_lock(pg_engine, worker_pid, blocker_pid, pending)
                    clock.advance(40)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                denied(lambda: pending.result(timeout=45), 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", gate)
    assert state["written"] and durable(pg_engine) == before


def test_same_transaction_failure_aborts_prior_caller_changes(plan_case_factory, pg_engine):
    case = plan_case_factory()
    before = durable(pg_engine)
    with Session(pg_engine) as session:
        session.begin()
        session.execute(text("UPDATE auth_users SET status='disabled' WHERE id=:id"), {"id": case.owner.user_id})
        denied(lambda: case.service.create_draft(case.principal, case.request, session=session), 401)
        session.commit()
    with Session(pg_engine) as session:
        assert session.get(AuthUser, case.owner.user_id).status == "active"
    assert durable(pg_engine) == before


def test_clock_rewind_after_required_audit_cannot_commit_a_future_created_draft(
        plan_case_factory, pg_engine, clock):
    from services.api.app.plans.models import PlansBase

    case=plan_case_factory()
    source_time=case.assessment.assessment_at
    clock.advance(2)
    assert clock()==source_time+timedelta(seconds=2)
    before=durable(pg_engine)
    state={"written":False,"rewound":False}
    plan_tables=tuple(PlansBase.metadata.tables)

    def rewind(connection,cursor,statement,parameters,context,executemany):
        lowered=statement.lower().strip()
        if lowered.startswith("insert into ") and any(name in lowered for name in plan_tables):
            state["written"]=True
        if state["written"] and not state["rewound"] and lowered.startswith("insert into auth_audit_events"):
            state["rewound"]=True
            clock.advance(-1)

    event.listen(pg_engine,"after_cursor_execute",rewind)
    try:
        denied(lambda: case.service.create_draft(case.principal,case.request),409)
    finally:
        event.remove(pg_engine,"after_cursor_execute",rewind)
    assert state=={"written":True,"rewound":True}
    assert clock()==source_time+timedelta(seconds=1)
    assert durable(pg_engine)==before


def test_default_real_gate_is_closed_and_foreign_mapper_never_connects(plan_case_factory, pg_engine):
    from services.api.app.assessments.models import EligibilityAssessment
    from services.api.app.plans.models import PlansBase
    from services.api.app.plans.schemas import PlanPolicy
    from services.api.app.plans.service import PlansService
    from services.api.app.profiles.models import ProfileVersion

    case = plan_case_factory()
    before = durable(pg_engine)
    closed = PlansService(case.eligibility, case.service.store, PlanPolicy())
    denied(lambda: closed.create_draft(case.principal, case.request), 503)
    routed = create_engine(pg_engine.url, hide_parameters=True)
    connected = []
    event.listen(routed, "connect", lambda *args: connected.append(True))
    try:
        own_mapper = next(iter(PlansBase.registry.mappers)).class_
        for mapper in (own_mapper, EligibilityAssessment, ProfileVersion):
            with Session(pg_engine, binds={mapper: routed}) as session:
                session.begin()
                denied(lambda: case.service.create_draft(case.principal, case.request, session=session), 503)
                session.commit()
        assert connected == []
    finally:
        routed.dispose()
    assert durable(pg_engine) == before
