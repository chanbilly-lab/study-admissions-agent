"""Independent T35 intrinsic data checks; synthetic snapshots are no authority."""

from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from services.api.app.plan_revisions.schemas import (
    CompletionReference, DeadlineReference, DecisionInput, PlanPin, ProposeInput,
    HistoricalSchedule, ReplacementData, RevisionData, RevisionDecisionData, RevisionDiff, RevisionError,
    RevisionHistoryData, RevisionPolicy, RevisionSourceRef, proposal_fingerprint,
)
from services.api.app.api.v2.idempotency_canonical import canonical_request_hash
from services.api.app.plan_revisions.diff import compare_plans
from services.api.app.plans.schedule_schemas import ScheduleDraft, schedule_fingerprint
from services.api.app.plans.scheduler import schedule_plan
from tests.unit.scheduling.test_t31_capacity import estimated_draft, source_cases, schedule_input, slot


NOW = datetime(2026, 10, 4, 9, tzinfo=timezone.utc)


def history(*, confirmed=True, hours="1", cases=None):
    cases = cases or source_cases("unknown")
    draft = estimated_draft(cases, hours={"VERIFY_UNKNOWN": hours, "PREPARE_MATERIALS": hours})
    pin = PlanPin(plan_id=uuid4(), source_plan_version_id=uuid4(), state_version=4 if confirmed else 2,
        state="confirmed" if confirmed else "draft", proposal_id=uuid4(), proposal_state_version=2,
        source_draft_sha256=draft.draft_sha256, draft_sha256=draft.draft_sha256, schedule_sha256=None,
        profile_id=draft.profile_id, profile_version_id=draft.profile_version_id, profile_version=1,
        profile_sha256=draft.profile_sha256, confirmation_id=uuid4() if confirmed else None, is_synthetic=True)
    sources = tuple(RevisionSourceRef(assessment_id=assessment.assessment_id, result_sha256=assessment.result_sha256,
        target=assessment.target, entry_year=2027, release_id=assessment.release_id,
        requirements_version=assessment.requirements_version, ruleset_version=assessment.ruleset_version,
        stage=assessment.stage, original_eligibility_status=assessment.eligibility.status,
        original_validity=assessment.current_validity, current_validity="needs_review") for assessment, _, _ in cases)
    completed = (CompletionReference(completion_id=uuid4(), confirmation_id=pin.confirmation_id,
        task_key=draft.tasks[0].task_key, completed_state_version=4, completed_at=NOW,
        source="student_declared"),) if confirmed else ()
    return RevisionHistoryData(schema_version="v2.t35", pin=pin, tasks=draft.tasks, sources=sources,
        deadlines=(), schedule=None, completion_refs=completed, created_at=NOW,
        expires_at=NOW+timedelta(days=1), current_actions=False)


def proposal():
    old, new = history(), history(confirmed=False, hours="2")
    fields = ("estimates",)
    diff = RevisionDiff(changed_fields=fields, business_changed=True,
        diff_sha256=canonical_request_hash({"changed_fields": list(fields), "business_changed": True}))
    raw = dict(schema_version="v2.t35", revision_id=uuid4(), revision_version=1, status="proposed",
        old=old, new=new, diff=diff, decision=None, replacement=None,
        created_at=NOW, expires_at=NOW+timedelta(hours=1), is_synthetic=True)
    native = RevisionData.model_construct(**raw, proposal_sha256="0"*64)
    raw["proposal_sha256"] = proposal_fingerprint(native)
    return RevisionData(**raw)


@pytest.mark.parametrize("value", [False, 0, 1, "true", None])
def test_each_student_action_requires_exact_true(value):
    with pytest.raises(ValueError):
        ProposeInput(old_plan_id=uuid4(), new_plan_id=uuid4(), expected_old_state_version=4,
            expected_new_state_version=2, student_confirmed=value)
    with pytest.raises(ValueError):
        DecisionInput(expected_revision_version=1, action="accept", student_confirmed=value)


@pytest.mark.parametrize("value", [True, False, 0, -1, 2147483648, "2", 2.0])
def test_plan_cas_is_bounded_strict_integer(value):
    with pytest.raises(ValueError):
        ProposeInput(old_plan_id=uuid4(), new_plan_id=uuid4(), expected_old_state_version=value,
            expected_new_state_version=2, student_confirmed=True)


@pytest.mark.parametrize("name", ["owner_user_id", "diff", "completed_tasks", "accepted_at", "grades"])
def test_clients_cannot_supply_ownership_differences_or_completion_conclusions(name):
    raw = dict(old_plan_id=uuid4(), new_plan_id=uuid4(), expected_old_state_version=4,
        expected_new_state_version=2, student_confirmed=True)
    assert ProposeInput(**raw).student_confirmed is True
    with pytest.raises(ValueError):
        ProposeInput(**raw, **{name: "DEMO_PRIVATE_SENTINEL"})


def test_copy_and_construct_cannot_bypass_distinct_ids_or_decision_cas():
    raw = dict(old_plan_id=uuid4(), new_plan_id=uuid4(), expected_old_state_version=4,
        expected_new_state_version=2, student_confirmed=True)
    good = ProposeInput(**raw)
    for forged in (good.model_copy(update={"new_plan_id": good.old_plan_id}),
                   ProposeInput.model_construct(**{**raw, "student_confirmed": 1})):
        with pytest.raises(ValueError):
            ProposeInput.model_validate(forged)
    with pytest.raises(ValueError):
        DecisionInput.model_validate(DecisionInput.model_construct(expected_revision_version=True,
            action="accept", student_confirmed=True))


@pytest.mark.parametrize("value", [True, 0, 1, "false", None])
def test_real_processing_gate_cannot_be_claimed(value):
    with pytest.raises(ValueError):
        RevisionPolicy(enabled=True, allow_test_revisions=True, real_revisions_ready=value)


@pytest.mark.parametrize("mutation", ["confirmation", "task", "duplicate", "expired", "version"])
def test_history_cannot_claim_foreign_or_out_of_lifetime_original_completion(mutation):
    good = history()
    raw = good.model_dump(mode="python")
    item = good.completion_refs[0]
    if mutation == "confirmation":
        item = item.model_copy(update={"confirmation_id": uuid4()})
    elif mutation == "task":
        item = item.model_copy(update={"task_key": "f"*64})
    elif mutation == "expired":
        item = item.model_copy(update={"completed_at": good.expires_at})
    elif mutation == "version":
        item = item.model_copy(update={"completed_state_version": good.pin.state_version+1})
    raw["completion_refs"] = (item, item) if mutation == "duplicate" else (item,)
    with pytest.raises(ValueError):
        RevisionHistoryData.model_validate(raw)


@pytest.mark.parametrize("value", [True, 0, 1])
def test_history_never_claims_current_actions_even_through_model_copy(value):
    good = history()
    with pytest.raises(ValueError):
        RevisionHistoryData.model_validate(good.model_copy(update={"current_actions": value}))


def test_history_has_no_grade_quote_or_replay_payload_extension():
    good = history()
    for name in ("profile_snapshot", "replay_snapshot", "quote", "value_text", "owner_user_id"):
        with pytest.raises(ValueError):
            RevisionHistoryData.model_validate({**good.model_dump(mode="python"), name: "DEMO_PRIVATE"})
    assert good.current_actions is False
    assert good.sources[0].current_validity != "current"


@pytest.mark.parametrize("field", ["new_plan_confirmed", "completion_credit_transferred"])
@pytest.mark.parametrize("value", [True, 0, 1])
def test_accepted_relationship_has_no_new_confirmation_or_completion_credit(field, value):
    raw = dict(relationship_id=uuid4(), old_plan_id=uuid4(), new_plan_id=uuid4(),
        accepted_at=NOW, new_plan_confirmed=False, completion_credit_transferred=False)
    assert ReplacementData(**raw).completion_credit_transferred is False
    with pytest.raises(ValueError):
        ReplacementData(**{**raw, field: value})


@pytest.mark.parametrize("mutation", ["same_plan", "other_profile", "new_completed", "expired", "wrong_mode", "false_hash"])
def test_complete_proposal_binding_survives_only_an_exact_valid_snapshot(mutation):
    good = proposal()
    raw = good.model_dump(mode="python")
    raw.update(old=good.old, new=good.new, diff=good.diff)
    if mutation == "same_plan":
        raw["new"] = good.new.model_copy(update={"pin": good.new.pin.model_copy(update={"plan_id": good.old.pin.plan_id})})
    elif mutation == "other_profile":
        raw["new"] = good.new.model_copy(update={"pin": good.new.pin.model_copy(update={"profile_id": uuid4()})})
    elif mutation == "new_completed":
        raw["new"] = good.new.model_copy(update={"completion_refs": good.old.completion_refs})
    elif mutation == "expired":
        raw["expires_at"] = good.old.expires_at + timedelta(seconds=1)
    elif mutation == "wrong_mode":
        raw["is_synthetic"] = False
    else:
        raw["proposal_sha256"] = "f"*64
    if mutation != "false_hash":
        raw["proposal_sha256"] = proposal_fingerprint(RevisionData.model_construct(**raw))
    with pytest.raises(ValueError):
        RevisionData.model_validate(raw)


def test_acceptance_preserves_original_completion_ids_without_new_credit():
    good = proposal()
    when = NOW+timedelta(seconds=1)
    decision = RevisionDecisionData(decision_id=uuid4(), action="accept", revision_version=2, decided_at=when)
    relationship = ReplacementData(relationship_id=uuid4(), old_plan_id=good.old.pin.plan_id,
        new_plan_id=good.new.pin.plan_id, accepted_at=when, new_plan_confirmed=False,
        completion_credit_transferred=False)
    accepted = RevisionData.model_validate(good.model_copy(update={"status": "accepted", "revision_version": 2,
        "decision": decision, "replacement": relationship}))
    assert accepted.proposal_sha256 == good.proposal_sha256
    assert accepted.old.completion_refs == good.old.completion_refs
    assert accepted.new.completion_refs == ()


def test_custom_timezone_is_rejected_before_native_datetime_callbacks():
    class UnsafeTimezone(tzinfo):
        calls = 0
        def utcoffset(self, value):
            self.calls += 1
            raise AssertionError("DEMO_PRIVATE_CALLBACK")
    zone = UnsafeTimezone()
    good = history()
    with pytest.raises(ValueError):
        RevisionHistoryData.model_validate(good.model_copy(update={"expires_at": NOW.replace(tzinfo=zone)}))
    assert zone.calls == 0


def test_deadline_reference_cannot_promote_a_calculated_or_guessed_official_instant():
    raw = dict(deadline_key="a"*64, assessment_id=uuid4(), assessment_key="math", purpose="supplement",
        status="unknown", event_id=uuid4(), precision="date", local_date=NOW.date(), local_time=None,
        timezone="Asia/Shanghai", reference_calendar="Asia/Shanghai", official_utc_instant=None)
    assert DeadlineReference(**raw).local_time is None
    unresolved = DeadlineReference(**(raw | {"precision": "unknown", "local_date": None,
        "local_time": None, "timezone": None, "reference_calendar": None, "status": "unknown"}))
    assert unresolved.precision == "unknown" and unresolved.official_utc_instant is None
    with pytest.raises(ValueError):
        DeadlineReference(**{**raw, "official_utc_instant": NOW})


def test_intrinsic_contract_import_does_not_connect_or_import_persistence_in_fresh_process(tmp_path):
    root = Path(__file__).resolve().parents[3]
    source = "import sys,socket\nsys.path.insert(0,"+repr(str(root))+")\n"+"""
def deny(*args,**kwargs): raise AssertionError('unexpected network access')
socket.create_connection=deny
from services.api.app.plan_revisions.schemas import ProposeInput,RevisionPolicy
assert RevisionPolicy().real_revisions_ready is False
for prefix in ('sqlalchemy','psycopg','alembic','services.api.app.auth.service','services.api.app.main'):
 assert not any(n==prefix or n.startswith(prefix+'.') for n in sys.modules),prefix
print('T35 intrinsic import without persistence')
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", source], cwd=tmp_path,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_an_estimate_only_change_is_reviewable_without_claiming_a_new_school_fact():
    old, new = history(hours="1"), history(confirmed=False, hours="2")
    diff = compare_plans(old, new)
    assert diff.changed_fields == ("estimates",)
    assert diff.business_changed
    assert old.completion_refs and not new.completion_refs


def test_explicit_dependency_change_is_not_hidden_by_identical_task_titles():
    cases = source_cases("unknown", "eligible")
    old, new = history(cases=cases), history(confirmed=False, cases=cases)
    assert len(new.tasks) == 2 and all(not task.dependency_keys for task in new.tasks)
    changed = new.tasks[1].model_copy(update={"dependency_keys": (new.tasks[0].task_key,)})
    new = RevisionHistoryData.model_validate(new.model_copy(update={"tasks": (new.tasks[0], changed)}))
    diff = compare_plans(old, new)
    assert diff.changed_fields == ("dependencies",)
    assert diff.business_changed


def with_schedule(value, scheduled):
    wrapper = HistoricalSchedule(**{key: getattr(scheduled, key) for key in HistoricalSchedule.model_fields})
    return RevisionHistoryData.model_validate(value.model_copy(update={"schedule": wrapper,
        "pin": value.pin.model_copy(update={"schedule_sha256": scheduled.schedule_sha256})}))


def test_explicit_capacity_change_is_reviewable_without_promoting_official_constraints():
    cases = source_cases("unknown")
    draft = estimated_draft(cases, hours={"VERIFY_UNKNOWN": "1"})
    availability = (slot(NOW+timedelta(minutes=5), NOW+timedelta(hours=2)),)
    first = schedule_plan(schedule_input(cases, draft, weekly="2", slots=availability))
    second = schedule_plan(schedule_input(cases, draft, weekly="3", slots=availability))
    old = with_schedule(history(), first)
    new = with_schedule(history(confirmed=False), second)
    diff = compare_plans(old, new)
    assert diff.changed_fields == ("schedule",)
    assert old.schedule.constraints_complete is new.schedule.constraints_complete is False


def test_schedule_keeps_task_to_time_relationship_when_identical_duration_slots_are_swapped():
    cases = source_cases("unknown", "eligible")
    draft = estimated_draft(cases, hours={"VERIFY_UNKNOWN": "0.01", "PREPARE_MATERIALS": "0.01"})
    scheduled = schedule_plan(schedule_input(cases, draft, weekly="1",
        slots=(slot(NOW+timedelta(minutes=5), NOW+timedelta(hours=1)),)))
    assert len(scheduled.tasks) == len(scheduled.allocations) == 2
    assert all(not task.dependency_keys for task in scheduled.tasks)
    first, second = scheduled.tasks
    exchange = {first.task_key: second.task_key, second.task_key: first.task_key}
    times = {first.task_key: (second.start_at, second.end_at), second.task_key: (first.start_at, first.end_at)}
    changed = scheduled.model_copy(update={
        "tasks": tuple(task.model_copy(update={"start_at": times[task.task_key][0],
            "end_at": times[task.task_key][1]}) for task in scheduled.tasks),
        "allocations": tuple(piece.model_copy(update={"task_key": exchange[piece.task_key]}) for piece in scheduled.allocations)})
    changed = ScheduleDraft.model_validate(changed.model_copy(update={
        "schedule_sha256": schedule_fingerprint(changed.model_dump(mode="json"))}))
    # Prove a legal entire schedule before checking the intrinsic history diff.
    assert changed.status == scheduled.status == "ready"
    old = with_schedule(history(cases=cases, hours="0.01"), scheduled)
    new = with_schedule(history(confirmed=False, cases=cases, hours="0.01"), changed)
    diff = compare_plans(old, new)
    assert diff.changed_fields == ("schedule",)


@pytest.mark.parametrize("noise", ["none", "references", "generated_at"])
def test_reference_or_time_noise_alone_cannot_fabricate_a_reviewable_revision(noise):
    old, new = history(), history(confirmed=False)
    if noise == "references":
        new = RevisionHistoryData.model_validate(new.model_copy(update={"sources": (
            new.sources[0].model_copy(update={"release_id": uuid4(), "result_sha256": "e"*64}),)}))
    elif noise == "generated_at":
        new = RevisionHistoryData.model_validate(new.model_copy(update={"created_at": NOW+timedelta(seconds=1)}))
    with pytest.raises(RevisionError) as error:
        compare_plans(old, new)
    assert error.value.status_code == 409
