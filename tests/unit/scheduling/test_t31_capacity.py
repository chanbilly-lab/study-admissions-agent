"""T31 capacity goldens over real T30 synthetic drafts, without persistence."""

from datetime import timedelta
from uuid import UUID

import pytest

from services.api.app.plans.drafts import build_plan_draft
from services.api.app.plans.schemas import DraftBuildInput, PlanDraft, assessment_fingerprint, plan_draft_fingerprint
from services.api.app.plans.schedule_schemas import ScheduleInput
from services.api.app.plans.scheduler import schedule_plan
from tests.unit.planning.test_t30_drafts import NOW, fixture_case

HOUR = 3_600_000_000


def source_cases(*statuses, at=NOW, lifetime=timedelta(days=90)):
    """Reuse actual four-state fixtures with explicit test clocks and fresh hashes."""
    cases = []
    for token, status in enumerate(statuses, 1):
        assessment, rule, policy = fixture_case(status, token=token)
        values = assessment.model_dump(mode="python")
        values.update(assessment_at=at, expires_at=at + lifetime)
        initial = type(assessment).model_validate(values)
        values["result_sha256"] = assessment_fingerprint(initial.model_dump(mode="json"))
        assessment = type(assessment).model_validate(values)
        window = {"valid_from": at - timedelta(days=1), "valid_until": at + lifetime}
        rule = type(rule).model_validate(rule.model_copy(update=window))
        policy = type(policy).model_validate(policy.model_copy(update=window))
        cases.append((assessment, rule, policy))
    return tuple(cases)


def estimated_draft(cases, *, hours=None, study_goals=(), deadline_snapshots=False, at=None):
    at = at or cases[0][0].assessment_at
    options = dict(assessments=tuple(case[0] for case in cases), confirmed=True, generated_at=at,
                   study_goals=study_goals, rule_bundles=tuple(case[1] for case in cases))
    if deadline_snapshots:
        options["deadline_bundles"] = tuple(case[2] for case in cases)
    draft = build_plan_draft(DraftBuildInput(**options))
    if hours is None:
        return draft
    values = draft.model_dump(mode="python")
    tasks = []
    for task in draft.tasks:
        estimate = hours.get(task.action_code, task.estimated_hours)
        tasks.append(type(task).model_validate({**task.model_dump(mode="python"),
            "estimated_hours": estimate, "estimate_source": "user_adjusted" if estimate is not None else "unknown"}))
    values["tasks"] = tuple(tasks)
    initial = draft.model_copy(update={"tasks": tuple(tasks)})
    values["draft_sha256"] = plan_draft_fingerprint(initial.model_dump(mode="json"))
    return PlanDraft.model_validate(values)


def slot(start, end, identifier=1):
    return {"slot_id": UUID(int=identifier), "start_at": start, "end_at": end}


def schedule_input(cases, draft, *, weekly="40", slots=(), at=None, horizon_end=None,
                   zone="UTC", goals=()):
    at = at or draft.generated_at
    return ScheduleInput(draft=draft, assessments=tuple(case[0] for case in cases), generated_at=at,
        horizon_start=at, horizon_end=horizon_end or at + timedelta(days=7), display_timezone=zone,
        availability_confirmed=True, rest_excluded=True, weekly_hours=weekly,
        slots=tuple(slots), internal_goals=tuple(goals))


def scheduled_task(result, action):
    return next(task for task in result.tasks if task.action_code == action)


def codes(result):
    return {conflict.code for conflict in result.conflicts}


def test_exact_weekly_capacity_is_allocated_without_confirming_or_mutating_the_draft():
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "2"})
    before = draft.model_dump(mode="json")
    result = schedule_plan(schedule_input(cases, draft, weekly="2",
        slots=(slot(NOW, NOW + timedelta(hours=2)),)))
    assert result.status == "ready" and result.confirmed is False
    assert sum(item.duration_microseconds for item in result.allocations) == 2 * HOUR
    task = scheduled_task(result, "PREPARE_MATERIALS")
    assert task.status == "scheduled" and task.assigned_microseconds == 2 * HOUR
    assert task.remaining_microseconds == 0
    assert draft.model_dump(mode="json") == before
    assert draft.confirmed is False and draft.scheduled is False


@pytest.mark.parametrize("slot_microseconds,expected", [(3600, "ready"), (3599, "blocked")])
def test_a_microhour_is_not_rounded_down_to_a_smaller_slot(slot_microseconds, expected):
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "0.000001"})
    result = schedule_plan(schedule_input(cases, draft, weekly="0.000001",
        slots=(slot(NOW, NOW + timedelta(microseconds=slot_microseconds)),)))
    task = scheduled_task(result, "PREPARE_MATERIALS")
    assert result.status == expected and task.estimated_microseconds == 3600
    assert task.assigned_microseconds == (3600 if expected == "ready" else 0)
    assert task.remaining_microseconds == (0 if expected == "ready" else 3600)


def test_one_microhour_over_weekly_capacity_keeps_the_entire_task_unassigned():
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "1.000001"})
    result = schedule_plan(schedule_input(cases, draft, weekly="1",
        slots=(slot(NOW, NOW + timedelta(hours=2)),)))
    task = scheduled_task(result, "PREPARE_MATERIALS")
    assert result.status == "blocked" and result.allocations == ()
    assert task.assigned_microseconds == 0 and task.remaining_microseconds == HOUR + 3600


@pytest.mark.parametrize("weekly,expected_code", [(None, "CAPACITY_REQUIRED"), ("0", None)])
def test_missing_capacity_and_explicit_zero_are_distinct(weekly, expected_code):
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "1"})
    result = schedule_plan(schedule_input(cases, draft, weekly=weekly,
        slots=(slot(NOW, NOW + timedelta(hours=1)),)))
    assert result.status == "blocked" and result.allocations == ()
    assert scheduled_task(result, "PREPARE_MATERIALS").remaining_microseconds == HOUR
    assert ("CAPACITY_REQUIRED" in codes(result)) is (expected_code is not None)


def test_zero_hour_milestone_needs_no_slot_or_weekly_capacity():
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "0"})
    result = schedule_plan(schedule_input(cases, draft, weekly="0"))
    task = scheduled_task(result, "PREPARE_MATERIALS")
    assert result.status == "ready" and result.allocations == ()
    assert task.status == "milestone" and task.start_at == task.end_at == NOW
    assert task.assigned_microseconds == task.remaining_microseconds == 0


def test_unknown_estimate_blocks_its_dependant_but_leaves_independent_work_schedulable():
    cases = source_cases("conditional")
    draft = estimated_draft(cases, hours={"OBTAIN_ACHIEVED": None, "RECHECK_CONDITIONS": "1"},
        study_goals=({"goal_key": "DEMO_READING", "goal_text": "记录本人自主阅读", "estimated_hours": "1"},))
    result = schedule_plan(schedule_input(cases, draft, weekly="1",
        slots=(slot(NOW, NOW + timedelta(hours=1)),)))
    assert result.status == "partial"
    assert scheduled_task(result, "OBTAIN_ACHIEVED").remaining_microseconds is None
    assert scheduled_task(result, "RECHECK_CONDITIONS").status == "blocked"
    assert scheduled_task(result, "SELF_DIRECTED_STUDY").assigned_microseconds == HOUR
    assert {"ESTIMATE_REQUIRED", "DEPENDENCY_BLOCKED"} <= codes(result)


def test_failed_task_trial_reserves_no_capacity_for_itself_or_its_child():
    cases = source_cases("conditional")
    draft = estimated_draft(cases, hours={"OBTAIN_ACHIEVED": "4", "RECHECK_CONDITIONS": "1"},
        study_goals=({"goal_key": "DEMO_INDEPENDENT", "goal_text": "记录独立练习", "estimated_hours": "2"},))
    result = schedule_plan(schedule_input(cases, draft, weekly="2",
        slots=(slot(NOW, NOW + timedelta(hours=2)),)))
    work = scheduled_task(result, "OBTAIN_ACHIEVED")
    study = scheduled_task(result, "SELF_DIRECTED_STUDY")
    assert result.status == "partial" and work.assigned_microseconds == 0
    assert work.remaining_microseconds == 4 * HOUR
    assert scheduled_task(result, "RECHECK_CONDITIONS").status == "blocked"
    assert study.start_at == NOW and study.end_at == NOW + timedelta(hours=2)
    assert all(item.task_key == study.task_key for item in result.allocations)


def test_positive_work_splits_across_slots_and_child_waits_for_its_last_fragment():
    cases = source_cases("conditional")
    draft = estimated_draft(cases, hours={"OBTAIN_ACHIEVED": "2", "RECHECK_CONDITIONS": "1"})
    slots = (slot(NOW, NOW + timedelta(hours=1), 1),
             slot(NOW + timedelta(hours=3), NOW + timedelta(hours=5), 2))
    result = schedule_plan(schedule_input(cases, draft, weekly="3", slots=slots))
    work, child = scheduled_task(result, "OBTAIN_ACHIEVED"), scheduled_task(result, "RECHECK_CONDITIONS")
    assert result.status == "ready"
    assert [item.duration_microseconds for item in result.allocations if item.task_key == work.task_key] == [HOUR, HOUR]
    assert work.end_at == NOW + timedelta(hours=4)
    assert child.start_at == work.end_at and child.end_at == NOW + timedelta(hours=5)


def test_compatible_shared_work_is_counted_once_with_both_targets_and_separate_followups():
    cases = source_cases("conditional", "conditional")
    draft = estimated_draft(cases, hours={"OBTAIN_ACHIEVED": "2", "RECHECK_CONDITIONS": "1"})
    result = schedule_plan(schedule_input(cases, draft, weekly="4",
        slots=(slot(NOW, NOW + timedelta(hours=4)),)))
    work = scheduled_task(result, "OBTAIN_ACHIEVED")
    checks = [item for item in result.tasks if item.action_code == "RECHECK_CONDITIONS"]
    assert result.status == "ready" and len(checks) == 2
    assert len([item for item in result.tasks if item.action_code == "OBTAIN_ACHIEVED"]) == 1
    assert set(work.assessment_ids) == {case[0].assessment_id for case in cases}
    assert sum(item.duration_microseconds for item in result.allocations) == 4 * HOUR
    assert all(item.start_at >= work.end_at for item in checks)


def test_explicit_slot_input_order_does_not_change_the_capacity_proposal():
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "2"})
    slots = (slot(NOW, NOW + timedelta(hours=1), 10),
             slot(NOW + timedelta(hours=2), NOW + timedelta(hours=3), 20))
    first = schedule_plan(schedule_input(cases, draft, slots=slots))
    second = schedule_plan(schedule_input(cases, draft, slots=tuple(reversed(slots))))
    assert first == second and first.status == "ready"


@pytest.mark.parametrize("boundary", ["eight_hour_slot", "256_slots", "520_hours", "84_days"])
def test_explicit_computation_limits_accept_the_exact_boundary(boundary):
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "0"})
    horizon_end = NOW + timedelta(days=84)
    if boundary == "eight_hour_slot":
        slots = (slot(NOW, NOW + timedelta(hours=8)),)
    elif boundary == "256_slots":
        slots = tuple(slot(NOW + timedelta(minutes=2 * index),
                           NOW + timedelta(minutes=2 * index + 1), index + 1) for index in range(256))
    elif boundary == "520_hours":
        slots = tuple(slot(NOW + timedelta(days=index), NOW + timedelta(days=index, hours=8), index + 1)
                      for index in range(65))
    else:
        slots = ()
    result = schedule_plan(schedule_input(cases, draft, slots=slots, horizon_end=horizon_end))
    assert result.status == "ready" and result.allocations == ()
