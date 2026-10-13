"""Calendar and deadline goldens: UTC capacity is separate from official facts."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from services.api.app.admissions_catalog.date_schemas import DateEventData, DateEventInput
from services.api.app.admissions_catalog.dates import _load_timezone, normalize_date_event
from services.api.app.plans.scheduler import schedule_plan
from tests.unit.scheduling.test_t31_capacity import (
    HOUR, NOW, codes, estimated_draft, schedule_input, scheduled_task, slot, source_cases,
)


def test_local_monday_splits_a_single_utc_slot_into_two_independent_week_capacities():
    start = datetime(2026, 10, 4, 15, 30, tzinfo=timezone.utc)
    cases = source_cases("eligible", at=start)
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "1"})
    result = schedule_plan(schedule_input(cases, draft, weekly="0.5", zone="Asia/Shanghai",
        slots=(slot(start, start + timedelta(hours=1)),)))
    assert result.status == "ready"
    assert [(item.week_start, item.duration_microseconds) for item in result.allocations] == [
        (date(2026, 9, 28), HOUR // 2), (date(2026, 10, 5), HOUR // 2)]
    assert all(week.assigned_microseconds <= week.capacity_microseconds for week in result.weeks)
    assert [(week.week_start, week.assigned_microseconds) for week in result.weeks if week.assigned_microseconds] == [
        (date(2026, 9, 28), HOUR // 2), (date(2026, 10, 5), HOUR // 2)]


def test_local_week_capacity_cannot_be_borrowed_from_the_next_week():
    start = datetime(2026, 10, 4, 15, 30, tzinfo=timezone.utc)
    cases = source_cases("eligible", at=start)
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "1"})
    result = schedule_plan(schedule_input(cases, draft, weekly="0.499999", zone="Asia/Shanghai",
        slots=(slot(start, start + timedelta(hours=1)),)))
    assert result.status == "blocked" and result.allocations == ()
    assert scheduled_task(result, "PREPARE_MATERIALS").remaining_microseconds == HOUR
    assert all(week.assigned_microseconds == 0 for week in result.weeks)


@pytest.mark.parametrize("start,local_start,local_end", [
    (datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc), (0, 30), (3, 30)),
    (datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc), (1, 30), (2, 30)),
])
def test_dst_explicit_utc_slots_count_two_elapsed_hours_without_wall_clock_guessing(start, local_start, local_end):
    zone = _load_timezone("Europe/London")
    end = start + timedelta(hours=2)
    assert (start.astimezone(zone).hour, start.astimezone(zone).minute) == local_start
    assert (end.astimezone(zone).hour, end.astimezone(zone).minute) == local_end
    cases = source_cases("eligible", at=start)
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "2"})
    result = schedule_plan(schedule_input(cases, draft, weekly="2", zone="Europe/London",
        slots=(slot(start, end),)))
    task = scheduled_task(result, "PREPARE_MATERIALS")
    assert result.status == "ready" and task.start_at == start and task.end_at == end
    assert task.assigned_microseconds == 2 * HOUR
    assert sum(item.duration_microseconds for item in result.allocations) == 2 * HOUR
    assert all(item.start_at.tzinfo == item.end_at.tzinfo == timezone.utc for item in result.allocations)


@pytest.mark.parametrize("extra_microseconds,status", [(0, "blocked"), (1, "ready")])
def test_internal_target_requires_completion_strictly_before_it(extra_microseconds, status):
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "1"})
    due = NOW + timedelta(hours=1, microseconds=extra_microseconds)
    result = schedule_plan(schedule_input(cases, draft, weekly="1",
        slots=(slot(NOW, NOW + timedelta(hours=1)),),
        goals=({"task_key": draft.tasks[0].task_key, "due_at": due},)))
    task = scheduled_task(result, "PREPARE_MATERIALS")
    assert result.status == status and task.internal_goal == due
    if status == "blocked":
        assert "INTERNAL_GOAL_CONFLICT" in codes(result)
        assert result.allocations == () and task.remaining_microseconds == HOUR
    else:
        assert task.end_at < due and task.remaining_microseconds == 0


def test_zero_work_milestone_at_the_internal_goal_is_also_a_conflict():
    cases = source_cases("eligible")
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "0"})
    result = schedule_plan(schedule_input(cases, draft, weekly="0",
        goals=({"task_key": draft.tasks[0].task_key, "due_at": NOW},)))
    assert result.status == "blocked" and result.allocations == ()
    assert "INTERNAL_GOAL_CONFLICT" in codes(result)


def with_deadline_precision(case, precision):
    assessment, rule, policy = case
    values = policy.model_dump(mode="python")
    for purpose in ("application", "supplement"):
        binding = values[purpose + "_deadline"]
        original = binding["date_event"]
        event_values = original.copy()
        event_values.update(original_text="DEMO_原始学校期限，尚未核定官方时刻", precision=precision,
            local_date=NOW.date() + timedelta(days=1) if precision == "date" else NOW.date(),
            local_time=None if precision == "date" else time(19, 0, 30 if precision == "second" else 0))
        for name in ("conversion_status", "calculated_utc_instant", "utc_instant", "review_state", "evidence_state", "tzdata_version"):
            event_values.pop(name, None)
        event_input = DateEventInput.model_validate(event_values)
        event = DateEventData(**event_input.model_dump(mode="python"),
            **normalize_date_event(event_input).model_dump(mode="python"), utc_instant=None,
            review_state="draft", evidence_state="unresolved")
        binding["date_event"] = event
    return assessment, rule, type(policy).model_validate(values)


@pytest.mark.parametrize("precision", ["date", "minute", "second"])
def test_school_precision_and_candidate_utc_are_preserved_without_enforcing_a_fake_deadline(precision):
    cases = (with_deadline_precision(source_cases("conditional")[0], precision),)
    draft = estimated_draft(cases, hours={"OBTAIN_ACHIEVED": "1", "RECHECK_CONDITIONS": "0"},
        deadline_snapshots=True)
    later = NOW + timedelta(days=2)
    result = schedule_plan(schedule_input(cases, draft, weekly="1",
        slots=(slot(later, later + timedelta(hours=1)),)))
    assert result.status == "ready" and result.constraints_complete is False
    assert result.deadline_refs == draft.deadline_refs
    assert "DEADLINE_UNRESOLVED" in codes(result) and "VERIFY_DEADLINES" in result.options
    for reference in result.deadline_refs:
        event = reference.date_event
        assert event.precision == precision and event.utc_instant is None
        assert event.timezone == "Asia/Shanghai" and event.source_alignment == "pending"
        if precision == "date":
            assert event.local_time is None and event.calculated_utc_instant is None
        else:
            assert event.conversion_status == "unique" and event.calculated_utc_instant is not None
            assert scheduled_task(result, "OBTAIN_ACHIEVED").end_at > event.calculated_utc_instant
    work = scheduled_task(result, "OBTAIN_ACHIEVED")
    followup = scheduled_task(result, "RECHECK_CONDITIONS")
    references = {reference.deadline_key: reference for reference in result.deadline_refs}
    assert {references[key].purpose for key in work.deadline_keys} == {"supplement"}
    assert {references[key].purpose for key in followup.deadline_keys} == {"application", "supplement"}


def test_missing_school_snapshot_stays_unresolved_and_keeps_the_two_exact_event_references():
    cases = source_cases("conditional")
    draft = estimated_draft(cases, hours={"OBTAIN_ACHIEVED": "1", "RECHECK_CONDITIONS": "0"})
    result = schedule_plan(schedule_input(cases, draft, slots=(slot(NOW, NOW + timedelta(hours=1)),)))
    assert result.status == "ready" and result.deadline_refs == draft.deadline_refs
    assert all(reference.date_event is None and reference.reference_calendar is None for reference in result.deadline_refs)
    assert {reference.event_id for reference in result.deadline_refs} == {
        cases[0][2].application_deadline.date_event.id, cases[0][2].supplement_deadline.date_event.id}
    assert result.constraints_complete is False and "DEADLINE_UNRESOLVED" in codes(result)


def test_enrollment_application_not_applicable_is_not_substituted_for_supplement():
    from tests.unit.planning.test_t30_drafts import fixture_case
    cases = (fixture_case(stage="enrollment"),)
    draft = estimated_draft(cases, hours={"OBTAIN_ACHIEVED": "1", "RECHECK_CONDITIONS": "0"},
        deadline_snapshots=True)
    result = schedule_plan(schedule_input(cases, draft, slots=(slot(NOW, NOW + timedelta(hours=1)),)))
    application = next(reference for reference in result.deadline_refs if reference.purpose == "application")
    supplement = next(reference for reference in result.deadline_refs if reference.purpose == "supplement")
    assert application.status == "not_applicable" and application.event_id is None
    assert supplement.status == "before" and supplement.event_id is not None
    work = scheduled_task(result, "OBTAIN_ACHIEVED")
    assert work.deadline_keys == (supplement.deadline_key,)
    assert "DEADLINE_UNRESOLVED" in codes(result) and result.constraints_complete is False


def test_horizon_can_end_at_the_original_source_ttl_without_extending_retention():
    lifetime = timedelta(hours=2)
    cases = source_cases("eligible", lifetime=lifetime)
    draft = estimated_draft(cases, hours={"PREPARE_MATERIALS": "2"})
    result = schedule_plan(schedule_input(cases, draft, weekly="2", horizon_end=NOW + lifetime,
        slots=(slot(NOW, NOW + lifetime),)))
    assert result.status == "ready" and result.horizon_end == draft.expires_at
    assert scheduled_task(result, "PREPARE_MATERIALS").end_at == cases[0][0].expires_at
    with pytest.raises(ValueError):
        schedule_input(cases, draft, horizon_end=NOW + lifetime + timedelta(microseconds=1))
