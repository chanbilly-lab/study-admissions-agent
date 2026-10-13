"""Scheduling goldens over actual T28 results and unchanged T30 drafts."""

from datetime import timedelta
from uuid import UUID

import pytest

from services.api.app.plans.schedule_schemas import (
    ScheduleError, ScheduleInput, hours_to_microseconds, schedule_fingerprint,
)
from services.api.app.plans.scheduler import schedule_plan
from tests.unit.planning.test_t30_drafts import NOW, build, fixture_case


def request(*cases, hours="1", estimates="1", study_goals=(), slots=None, goals=()):
    initial = build(*cases, study_goals=study_goals)
    overrides = tuple({"task_key": task.task_key, "estimated_hours": estimates} for task in initial.tasks)
    draft = build(*cases, study_goals=study_goals, estimate_overrides=overrides)
    return ScheduleInput(draft=draft, assessments=tuple(case[0] for case in cases),
        generated_at=NOW, horizon_start=NOW, horizon_end=NOW + timedelta(days=2),
        display_timezone="UTC", availability_confirmed=True, rest_excluded=True,
        weekly_hours=hours, slots=slots if slots is not None else (
            {"slot_id": UUID(int=1000), "start_at": NOW, "end_at": NOW + timedelta(hours=1)},),
        internal_goals=goals)


def test_exact_fit_preserves_the_unconfirmed_original_and_accounts_for_elapsed_work():
    current = request(fixture_case("eligible"))
    original = current.draft.model_dump(mode="json")
    result = schedule_plan(current)
    assert result.status == "ready" and result.confirmed is False and result.constraints_complete is False
    assert result.draft_sha256 == current.draft.draft_sha256
    assert result.tasks[0].assigned_microseconds == 3_600_000_000
    assert result.tasks[0].remaining_microseconds == 0
    assert result.allocations[0].end_at == NOW + timedelta(hours=1)
    assert result.options == ("VERIFY_DEADLINES",)
    assert schedule_fingerprint(result.model_dump(mode="json")) == result.schedule_sha256
    assert current.draft.model_dump(mode="json") == original
    assert current.draft.confirmed is False and current.draft.scheduled is False


def test_explicit_internal_goal_prioritizes_a_ready_task_without_changing_its_source():
    cases = (fixture_case("unknown", token=1), fixture_case("eligible", token=2))
    base = request(*cases, hours="2", slots=(
        {"slot_id": UUID(int=1000), "start_at": NOW, "end_at": NOW + timedelta(hours=2)},))
    prepare = next(task for task in base.draft.tasks if task.action_code == "PREPARE_MATERIALS")
    result = schedule_plan(base.model_copy(update={"internal_goals": (
        {"task_key": prepare.task_key, "due_at": NOW + timedelta(hours=1, microseconds=1)},)}))
    assert result.status == "ready"
    assert result.allocations[0].task_key == prepare.task_key
    assert result.tasks[0].internal_goal == NOW + timedelta(hours=1, microseconds=1)
    assert result.assessment_refs == base.draft.assessment_refs


def test_verified_sources_and_slot_input_order_do_not_change_the_deterministic_proposal():
    current = request(fixture_case("eligible", token=1), fixture_case("unknown", token=2), hours="2", slots=(
        {"slot_id": UUID(int=1000), "start_at": NOW, "end_at": NOW + timedelta(minutes=30)},
        {"slot_id": UUID(int=1001), "start_at": NOW + timedelta(hours=1), "end_at": NOW + timedelta(hours=2, minutes=30)},))
    reversed_input = current.model_copy(update={"assessments": tuple(reversed(current.assessments)),
                                             "slots": tuple(reversed(current.slots))})
    assert schedule_plan(current) == schedule_plan(reversed_input)
    result = schedule_plan(current)
    assert result.tasks[0].action_code == "VERIFY_UNKNOWN"
    assert len(result.allocations) == 3 and result.tasks[0].assigned_microseconds == hours_to_microseconds("1")


@pytest.mark.parametrize("validity,action", [("needs_review", "VERIFY_HISTORY"),
    ("replaced", "VERIFY_HISTORY"), ("withdrawn", "VERIFY_HISTORY"), ("unavailable", "VERIFY_UNKNOWN")])
def test_new_verification_drafts_can_be_scheduled_but_old_actions_cannot_be_reused(validity, action):
    original = fixture_case("eligible")
    current = request(original)
    fresh = original[0].model_copy(update={"current_validity": validity})
    with pytest.raises(ScheduleError) as failure:
        schedule_plan(current.model_copy(update={"assessments": (fresh,)}))
    assert failure.value.status_code == 409
    replacement = request((fresh, original[1], original[2]))
    result = schedule_plan(replacement)
    assert result.status == "ready" and result.tasks[0].action_code == action
    assert result.assessment_refs[0].eligibility_status == "eligible"


def test_student_authored_study_remains_separate_from_unavailable_admissions_proof():
    original = fixture_case("unknown")
    fresh = original[0].model_copy(update={"current_validity": "unavailable"})
    current = request((fresh, original[1], original[2]), hours="2", study_goals=(
        {"goal_key": "DEMO_READ", "goal_text": "审阅自己选择的阅读笔记", "estimated_hours": "1"},), slots=(
        {"slot_id": UUID(int=1000), "start_at": NOW, "end_at": NOW + timedelta(hours=2)},))
    result = schedule_plan(current)
    assert result.status == "ready"
    assert [task.action_code for task in result.tasks] == ["VERIFY_UNKNOWN", "SELF_DIRECTED_STUDY"]
    autonomous = result.tasks[1]
    assert autonomous.assessment_ids == () and autonomous.deadline_keys == ()
    assert result.constraints_complete is False
