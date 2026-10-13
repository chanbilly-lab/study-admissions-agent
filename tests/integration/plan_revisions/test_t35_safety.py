"""T35 independent synthetic authority, contention and real commit boundaries."""

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
from services.api.app.plan_revisions.schemas import DecisionInput, ProposeInput


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T35_PRIVATE_FAULT_SENTINEL"


def denied(operation, *statuses):
    with pytest.raises(Exception) as caught:
        operation()
    assert getattr(caught.value, "status_code", None) in statuses
    assert SENTINEL not in str(caught.value) + repr(caught.value)
    return caught.value


def decision(action="accept"):
    return DecisionInput(expected_revision_version=1, action=action, student_confirmed=True)


def original_rows(engine):
    from services.api.app.plans.models import PlansBase
    from services.api.app.plan_execution.models import ExecutionBase
    with engine.connect() as connection:
        result = {name: connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
            for base in (PlansBase, ExecutionBase) for name, table in base.metadata.tables.items()}
        result["registry"] = connection.execute(select(AuthOwnedResource.__table__).where(
            AuthOwnedResource.resource_type == "plan").order_by(AuthOwnedResource.id)).mappings().all()
    return result


def revision_rows(engine):
    from services.api.app.plan_revisions.models import RevisionsBase
    with engine.connect() as connection:
        return {name: connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
            for name, table in RevisionsBase.metadata.tables.items()}


def succeeded(engine):
    with engine.connect() as connection:
        return set(connection.scalars(select(AuditEvent.id).where(AuditEvent.outcome == "succeeded")))


def observe_lock(engine, pids, blocker, pending):
    deadline, pause = monotonic()+40, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if pending.done():
                pending.result()
                pytest.fail("Revision worker completed before the required PostgreSQL lock wait")
            connection.execute(text("SELECT pg_stat_clear_snapshot()"))
            if pids and connection.scalar(text("SELECT wait_event_type='Lock' AND "
                ":blocker=ANY(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE pid=:pid"),
                {"blocker": blocker, "pid": pids[0]}):
                return
            pause.wait(0.01)
    pytest.fail("No actual revision PostgreSQL lock wait was observed")


@pytest.mark.parametrize("second_action", ["accept", "reject"])
def test_two_sessions_decide_once_or_replay_without_rewriting_old_execution(
        revision_case_factory, pg_engine, second_action):
    case = revision_case_factory()
    proposal = case.service.propose(case.principal, case.request).revision
    original = original_rows(pg_engine)
    lock = uuid4().int % (2**62)
    reached, second_started = Event(), Event()
    first_pid, second_pid = [], []
    state = {"first": None, "second": None, "blocked": False}

    def identify(connection, cursor, sql, parameters, context, executemany):
        if get_ident() == state["second"] and not second_pid:
            second_pid.append(0)
            second_pid[0] = connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
            second_started.set()

    def gate(connection, cursor, sql, parameters, context, executemany):
        if (get_ident() == state["first"] and not state["blocked"]
            and sql.lower().startswith("insert into revision_decisions")):
            state["blocked"] = True
            first_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            reached.set()
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock,))

    event.listen(pg_engine, "before_cursor_execute", identify)
    event.listen(pg_engine, "after_cursor_execute", gate)
    try:
        with pg_engine.connect() as blocker:
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock})
            with ThreadPoolExecutor(max_workers=2) as pool:
                def first():
                    state["first"] = get_ident()
                    return case.service.decide(case.principal, proposal.revision_id, decision())
                def second():
                    state["second"] = get_ident()
                    return case.service.decide(case.principal, proposal.revision_id, decision(second_action))
                a = pool.submit(first)
                try:
                    assert reached.wait(40), "First actual decision INSERT was not reached"
                    b = pool.submit(second)
                    assert second_started.wait(20)
                    observe_lock(pg_engine, second_pid, first_pid[0], b)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock})
                accepted = a.result(timeout=60)
                if second_action == "accept":
                    repeated = b.result(timeout=60)
                    assert repeated.replayed is True
                    assert repeated.revision.decision.decision_id == accepted.revision.decision.decision_id
                else:
                    denied(lambda: b.result(timeout=60), 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", identify)
        event.remove(pg_engine, "after_cursor_execute", gate)
    assert accepted.replayed is False and accepted.revision.status == "accepted"
    assert original_rows(pg_engine) == original
    rows = revision_rows(pg_engine)
    assert len(rows["revision_decisions"]) == len(rows["plan_replacement_links"]) == 1
    assert accepted.revision.old.completion_refs
    assert accepted.revision.new.completion_refs == ()
    assert accepted.revision.replacement.new_plan_confirmed is False
    assert accepted.revision.replacement.completion_credit_transferred is False


def test_unique_old_successor_applies_across_distinct_revision_proposals(revision_case_factory, pg_engine):
    from services.api.app.plans.schemas import PlanCreateInput
    case = revision_case_factory()
    first = case.service.propose(case.principal, case.request).revision
    extra = case.execution.create_plan(case.principal, PlanCreateInput(
        assessment_ids=tuple(ref.assessment_id for ref in case.new_plan.proposal.effective_draft.assessment_refs), confirmed=True))
    request = ProposeInput(old_plan_id=case.old_plan.plan_id, new_plan_id=extra.plan_id,
        expected_old_state_version=case.old_plan.state_version, expected_new_state_version=extra.state_version,
        student_confirmed=True)
    second = case.service.propose(case.principal, request).revision
    original = original_rows(pg_engine)
    case.service.decide(case.principal, first.revision_id, decision())
    denied(lambda: case.service.decide(case.principal, second.revision_id, decision()), 409)
    assert original_rows(pg_engine) == original
    rows = revision_rows(pg_engine)
    assert len(rows["revision_proposals"]) == 2
    assert len(rows["plan_replacement_links"]) == len(rows["revision_decisions"]) == 1
    rejected = case.service.decide(case.principal, second.revision_id, decision("reject"))
    assert rejected.revision.status == "rejected"


@pytest.mark.parametrize("changed", ["old_completion", "new_workspace"])
def test_acceptance_does_not_silently_absorb_changed_plan_cas(revision_case_factory, pg_engine, changed):
    from services.api.app.plan_execution.schemas import CompleteInput, WorkspaceInput
    from services.api.app.plans.schemas import EstimateOverride
    # The old execution may append completion only while its original profile
    # remains current; the separate history case tests a new profile version.
    case = revision_case_factory(complete_old=False, profile_change=changed != "old_completion")
    proposal = case.service.propose(case.principal, case.request).revision
    if changed == "old_completion":
        task = next(t for t in case.old_plan.proposal.effective_draft.tasks if not t.dependency_keys)
        current = case.execution.complete_task(case.principal, case.old_plan.plan_id, task.task_key,
            CompleteInput(expected_version=case.old_plan.state_version, confirmed=True)).execution
        assert current.completed_tasks
    else:
        current = case.execution.update_workspace(case.principal, case.new_plan.plan_id,
            WorkspaceInput(expected_version=case.new_plan.state_version, estimate_overrides=(
                EstimateOverride(task_key=case.new_plan.proposal.effective_draft.tasks[0].task_key,
                    estimated_hours="0.02"),), schedule=None))
        assert current.state_version > case.new_plan.state_version
    original = original_rows(pg_engine)
    denied(lambda: case.service.decide(case.principal, proposal.revision_id, decision()), 409)
    assert not revision_rows(pg_engine)["plan_replacement_links"]
    rejected = case.service.decide(case.principal, proposal.revision_id, decision("reject"))
    assert rejected.revision.status == "rejected"
    assert original_rows(pg_engine) == original
    history = case.service.get_history(case.principal, case.old_plan.plan_id)
    if changed == "old_completion":
        assert history.completion_refs
    assert history.current_actions is False


def test_new_profile_and_withdrawn_source_preserve_finite_history_and_allow_explicit_rejection(
        revision_case_factory, pg_engine):
    from services.api.app.changes.models import AssessmentChangeImpact
    from services.api.app.releases.models import ChangeEvent
    from services.api.app.releases.schemas import WithdrawalRequest
    case = revision_case_factory(profile_change=True)
    denied(lambda: case.execution.get_plan(case.principal, case.old_plan.plan_id), 409)
    history = case.service.get_history(case.principal, case.old_plan.plan_id)
    assert history.completion_refs and history.current_actions is False
    proposal = case.service.propose(case.principal, case.request).revision
    assert proposal.old.pin.profile_version_id != proposal.new.pin.profile_version_id
    case.clock.advance(1)
    case.releases.withdraw(case.reviewer.principal, WithdrawalRequest(release_id=case.release.release_id,
        expected_state_revision=case.release.state_revision, reason_code="SOURCE_UNAVAILABLE"))
    with Session(pg_engine) as session:
        event_id = session.scalar(select(ChangeEvent.id).where(ChangeEvent.release_id == case.release.release_id,
            ChangeEvent.event_type == "withdrawn"))
    assert event_id is not None
    processed = case.changes.process_event(event_id)
    assert processed.assessment_count > 0 and processed.plan_count > 0
    with Session(pg_engine) as session:
        impact = session.scalar(select(AssessmentChangeImpact).where(AssessmentChangeImpact.event_id == event_id,
            AssessmentChangeImpact.assessment_id == case.assessment.assessment_id))
        assert impact is not None and impact.needs_review is True
        assert impact.created_at > proposal.created_at
    original = original_rows(pg_engine)
    denied(lambda: case.service.decide(case.principal, proposal.revision_id, decision()), 409)
    result = case.service.decide(case.principal, proposal.revision_id, decision("reject"))
    retained = case.service.get_history(case.principal, case.old_plan.plan_id)
    assert result.revision.status == "rejected"
    assert result.revision.diff == proposal.diff and result.revision.proposal_sha256 == proposal.proposal_sha256
    assert retained.completion_refs == history.completion_refs
    assert retained.pin == history.pin
    assert retained.sources[0].current_validity == "withdrawn"
    assert original_rows(pg_engine) == original
    assert not revision_rows(pg_engine)["plan_replacement_links"]
    # These are finite historical source references, not grades or old evidence.
    assert not {"replay_snapshot", "profile_snapshot", "quote", "value_text", "owner_user_id"} & retained.model_dump().keys()


def admit(case, actor):
    from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
    privacy = case.service.profile_service.privacy_service
    principal = case.service.auth_service.get_principal(actor.cookie)
    before = privacy.get_admission(principal)
    adult = privacy.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=before.notice_id, expected_revision=before.revision))
    privacy.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=adult.notice_id, expected_revision=adult.revision))
    return principal


def test_metadata_grant_admin_and_foreign_student_have_no_private_revision_port(
        revision_case_factory, actor_factory, pg_engine, clock):
    from services.api.app.auth.grants.policy import POLICY_HASH, POLICY_VERSION
    from services.api.app.auth.grants.schemas import AcceptGrantInput, CreateGrantInput, SharingSettings
    from services.api.app.auth.grants.service import SharingService
    case = revision_case_factory()
    proposal = case.service.propose(case.principal, case.request).revision
    receiver_actor = actor_factory()
    receiver = admit(case, receiver_actor)
    sharing = SharingService(case.service.auth_service, case.service.profile_service.privacy_service,
        SharingSettings(fixture_mode=True))
    state = sharing.list_grants(case.principal)
    grant = sharing.create_grant(case.principal, CreateGrantInput(resource_type="plan",
        resource_id=case.old_plan.plan_id, expected_resource_version=1, grantee_user_id=receiver.user_id,
        fields=["status", "version"], actions=["read", "list"], expires_at=clock()+timedelta(minutes=5),
        confirmed=True, expected_revision=state.revision, owner_consent_id=state.owner_consent_id,
        sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH)).grant
    sharing.accept_grant(receiver, grant.id, AcceptGrantInput(confirmed=True, expected_version=grant.version,
        sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))
    assert sharing.require_shared(receiver, "plan", case.old_plan.plan_id, ("status", "version")).version == 1
    original, revisions = original_rows(pg_engine), revision_rows(pg_engine)
    for foreign in (receiver, case.reviewer.principal):
        denied(lambda: case.service.get_history(foreign, case.old_plan.plan_id), 403, 404)
        denied(lambda: case.service.get_revision(foreign, proposal.revision_id), 403, 404)
        denied(lambda: case.service.propose(foreign, case.request), 403, 404)
        denied(lambda: case.service.decide(foreign, proposal.revision_id, decision()), 403, 404)
    assert original_rows(pg_engine) == original and revision_rows(pg_engine) == revisions
    # A provided transaction cannot commit an earlier account change after denial.
    with Session(pg_engine) as supplied:
        supplied.begin()
        supplied.get(AuthUser, case.owner.user_id).status = "disabled"
        supplied.flush()
        denied(lambda: case.service.get_history(case.principal, case.old_plan.plan_id, session=supplied), 401)
        supplied.commit()
    with Session(pg_engine) as session:
        assert session.get(AuthUser, case.owner.user_id).status == "active"


def test_withdraw_and_new_consent_cannot_revive_old_private_revision_history(revision_case_factory, pg_engine):
    from services.api.app.privacy.schemas import CoreConsentInput
    case = revision_case_factory()
    proposal = case.service.propose(case.principal, case.request).revision
    privacy = case.service.profile_service.privacy_service
    before = privacy.get_admission(case.principal)
    privacy.withdraw_core(case.principal, before.consent_id)
    original, revisions = original_rows(pg_engine), revision_rows(pg_engine)
    for run in (lambda: case.service.get_history(case.principal, case.old_plan.plan_id),
                lambda: case.service.get_revision(case.principal, proposal.revision_id),
                lambda: case.service.decide(case.principal, proposal.revision_id, decision("reject"))):
        denied(run, 403)
    current = privacy.get_admission(case.principal)
    privacy.confirm_core(case.principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=current.notice_id, expected_revision=current.revision))
    assert privacy.get_admission(case.principal).revision > before.revision
    denied(lambda: case.service.get_history(case.principal, case.old_plan.plan_id), 403)
    denied(lambda: case.service.decide(case.principal, proposal.revision_id, decision("reject")), 403)
    assert original_rows(pg_engine) == original and revision_rows(pg_engine) == revisions


def test_disabled_and_mapper_routed_sessions_fail_before_database_or_failure_audit(
        revision_case_factory, pg_engine):
    from services.api.app.plan_revisions.models import RevisionProposal, RevisionDecision, PlanReplacement
    from services.api.app.plan_revisions.schemas import RevisionPolicy
    from services.api.app.plan_revisions.service import RevisionService
    from services.api.app.assessments.models import EligibilityAssessment
    from services.api.app.profiles.models import ProfileVersion
    case = revision_case_factory()
    closed = RevisionService(case.execution, case.service.changes_service, case.service.store, RevisionPolicy())
    statements = []
    def record(*arguments):
        statements.append(arguments[2])
    event.listen(pg_engine, "before_cursor_execute", record)
    try:
        assert closed.context(case.principal).can_propose is False
        denied(lambda: closed.get_history(case.principal, case.old_plan.plan_id), 503)
        denied(lambda: closed.propose(case.principal, case.request), 503)
    finally:
        event.remove(pg_engine, "before_cursor_execute", record)
    assert statements == []
    routed = create_engine(pg_engine.url, hide_parameters=True)
    connected = []
    event.listen(routed, "do_connect", lambda *arguments: connected.append(True))
    try:
        original = revision_rows(pg_engine)
        for mapper in (RevisionProposal, RevisionDecision, PlanReplacement, EligibilityAssessment, ProfileVersion, AuditEvent):
            with Session(bind=pg_engine, binds={mapper: routed}) as supplied:
                supplied.begin()
                denied(lambda: case.service.get_history(case.principal, case.old_plan.plan_id, session=supplied), 503)
                supplied.commit()
        assert connected == []
        assert revision_rows(pg_engine) == original
    finally:
        routed.dispose()


@pytest.mark.parametrize("deadline", ["session", "file"])
def test_required_final_sql_wait_rechecks_session_or_current_source_file_and_rolls_back_decision(
        revision_case_factory, pg_engine, clock, monkeypatch, deadline):
    case = revision_case_factory(file_lifetime_seconds=40 if deadline == "file" else None)
    proposal = case.service.propose(case.principal, case.request).revision
    if deadline == "session":
        with Session(pg_engine) as session, session.begin():
            session.get(AuthSession, case.owner.session_id).expires_at = clock()+timedelta(seconds=40)
    original, revisions, successes = original_rows(pg_engine), revision_rows(pg_engine), succeeded(pg_engine)
    state = {"written": False, "worker": None, "final": False, "profile_final": False, "blocked": False}
    reached, pids = Event(), []
    lock = uuid4().int % (2**62)
    original_final = case.service._final
    def final(*args, **kwargs):
        state["final"] = state["written"]
        try:
            return original_final(*args, **kwargs)
        finally:
            state["final"] = False
    monkeypatch.setattr(case.service, "_final", final)
    original_profile_final = case.service.profile_service._final
    def profile_final(*args, **kwargs):
        state["profile_final"] = state["final"]
        try:
            return original_profile_final(*args, **kwargs)
        finally:
            state["profile_final"] = False
    monkeypatch.setattr(case.service.profile_service, "_final", profile_final)

    def gate(connection, cursor, sql, parameters, context, executemany):
        if get_ident() != state["worker"]:
            return
        normalized = " ".join(sql.lower().split())
        if normalized.startswith("insert into revision_decisions"):
            state["written"] = True
        if (state["profile_final"] and not state["blocked"] and normalized.startswith("select ")
            and "from auth_user_roles" in normalized):
            state["blocked"] = True
            pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            reached.set()
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock,))
    event.listen(pg_engine, "after_cursor_execute", gate)
    try:
        with pg_engine.connect() as blocker:
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock})
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            with ThreadPoolExecutor(max_workers=1) as pool:
                def execute():
                    state["worker"] = get_ident()
                    return case.service.decide(case.principal, proposal.revision_id, decision())
                pending = pool.submit(execute)
                try:
                    assert reached.wait(40), "No mandatory post-decision authority SQL was reached"
                    observe_lock(pg_engine, pids, blocker_pid, pending)
                    clock.advance(40)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock})
                denied(lambda: pending.result(timeout=60), 401 if deadline == "session" else 409)
    finally:
        event.remove(pg_engine, "after_cursor_execute", gate)
    assert state["written"] and state["blocked"]
    assert original_rows(pg_engine) == original
    assert revision_rows(pg_engine) == revisions
    assert succeeded(pg_engine) == successes


def test_actual_required_audit_and_deferred_commit_failures_leave_no_decision_or_relationship(
        revision_case_factory, pg_engine):
    case = revision_case_factory()
    proposal = case.service.propose(case.principal, case.request).revision
    original, revisions, successes = original_rows(pg_engine), revision_rows(pg_engine), succeeded(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t35_independent_fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF current_setting('t35.fail_audit',true)='1' AND NEW.outcome='succeeded' THEN "
            "RAISE EXCEPTION 'DEMO_T35_PRIVATE_FAULT_SENTINEL' USING ERRCODE='23514'; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER t35_independent_audit BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION t35_independent_fail_audit()"))
    marked = []
    def fail_after_actual_write(connection, cursor, sql, parameters, context, executemany):
        if sql.lower().startswith("insert into revision_decisions"):
            marked.append(True)
            connection.exec_driver_sql("SET LOCAL t35.fail_audit='1'")
    event.listen(pg_engine, "after_cursor_execute", fail_after_actual_write)
    try:
        denied(lambda: case.service.decide(case.principal, proposal.revision_id, decision()), 503)
    finally:
        event.remove(pg_engine, "after_cursor_execute", fail_after_actual_write)
        with pg_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER t35_independent_audit ON auth_audit_events"))
            connection.execute(text("DROP FUNCTION t35_independent_fail_audit()"))
    assert marked
    assert original_rows(pg_engine) == original and revision_rows(pg_engine) == revisions
    assert succeeded(pg_engine) == successes
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t35_independent_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T35_PRIVATE_FAULT_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t35_independent_commit AFTER INSERT ON revision_decisions "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t35_independent_fail_commit()"))
    try:
        denied(lambda: case.service.decide(case.principal, proposal.revision_id, decision()), 503)
    finally:
        with pg_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER t35_independent_commit ON revision_decisions"))
            connection.execute(text("DROP FUNCTION t35_independent_fail_commit()"))
    assert original_rows(pg_engine) == original and revision_rows(pg_engine) == revisions
    assert succeeded(pg_engine) == successes
    result = case.service.decide(case.principal, proposal.revision_id, decision())
    assert result.revision.status == "accepted" and not result.replayed
    assert original_rows(pg_engine) == original


def test_initial_rehashed_revision_snapshots_cannot_fabricate_original_persisted_history(
        revision_case_factory, pg_engine):
    from services.api.app.api.v2.idempotency_canonical import canonical_request_hash
    from services.api.app.plan_revisions.models import RevisionProposal
    from services.api.app.plan_revisions.schemas import RevisionData, RevisionDiff, RevisionHistoryData, proposal_fingerprint

    case = revision_case_factory()
    good = case.service.propose(case.principal, case.request).revision
    original = original_rows(pg_engine)
    with Session(pg_engine) as session:
        baseline = dict(session.execute(select(RevisionProposal.__table__).where(
            RevisionProposal.id == good.revision_id)).mappings().one())
    for variant in ("task_estimate", "source_reference", "difference"):
        old, diff = good.old, good.diff
        if variant == "task_estimate":
            tasks = list(old.tasks)
            tasks[0] = tasks[0].model_copy(update={"estimated_hours": "0.03"})
            old = RevisionHistoryData.model_validate(old.model_copy(update={"tasks": tuple(tasks)}))
        elif variant == "source_reference":
            sources = list(old.sources)
            sources[0] = sources[0].model_copy(update={"ruleset_version": "f"*64})
            old = RevisionHistoryData.model_validate(old.model_copy(update={"sources": tuple(sources)}))
        else:
            raw_diff = {"changed_fields": ["task_business"], "business_changed": True}
            assert tuple(raw_diff["changed_fields"]) != good.diff.changed_fields
            diff = RevisionDiff(**raw_diff, diff_sha256=canonical_request_hash(raw_diff))
        fake = good.model_copy(update={"revision_id": uuid4(), "old": old, "diff": diff})
        fake = RevisionData.model_validate(fake.model_copy(update={"proposal_sha256": proposal_fingerprint(fake)}))
        # All FK/pin and intrinsic DTO checks remain valid; no immutable UPDATE
        # trigger is disabled. This is a malicious initial, fully rehashed INSERT.
        values = baseline | {"id": fake.revision_id, "payload": fake.model_dump(mode="json"),
            "payload_sha256": fake.proposal_sha256,
            "request_sha256": canonical_request_hash({"DEMO_variant": variant, "id": str(fake.revision_id)})}
        with pg_engine.begin() as connection:
            connection.execute(RevisionProposal.__table__.insert().values(**values))
        stored, successes = revision_rows(pg_engine), succeeded(pg_engine)
        denied(lambda: case.service.get_revision(case.principal, fake.revision_id), 409)
        denied(lambda: case.service.decide(case.principal, fake.revision_id, decision()), 409)
        assert revision_rows(pg_engine) == stored and succeeded(pg_engine) == successes
        assert original_rows(pg_engine) == original
    assert case.service.get_revision(case.principal, good.revision_id).proposal_sha256 == good.proposal_sha256
    assert not revision_rows(pg_engine)["plan_replacement_links"]
