"""Bounded deterministic capacity proposals, without persistence or confirmation."""

from datetime import datetime, time, timedelta, timezone

from pydantic import TypeAdapter

from ..admissions_catalog.dates import _load_timezone
from .schemas import PlanAssessmentRef, assessment_fingerprint
from .schedule_schemas import (MAX_ALLOCATIONS, SCHEDULER_VERSION, ScheduleDraft,
    ScheduleError, ScheduleInput, hours_to_microseconds, schedule_fingerprint)

_PRIORITY = {"VERIFY_UNKNOWN": 0, "VERIFY_HISTORY": 0, "REVIEW_INELIGIBLE": 1,
    "OBTAIN_ACHIEVED": 2, "RECHECK_CONDITIONS": 3, "PREPARE_MATERIALS": 4,
    "SELF_DIRECTED_STUDY": 5}


def _duration(delta):
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _source_ref(item):
    return PlanAssessmentRef(assessment_id=item.assessment_id, result_sha256=item.result_sha256,
        target=item.target, release_id=item.release_id, requirements_version=item.requirements_version,
        ruleset_version=item.ruleset_version, stage=item.stage, eligibility_status=item.eligibility.status,
        current_validity=item.current_validity, rule_refs=item.rule_refs)


def _validate_sources(current):
    draft = current.draft
    fresh = {item.assessment_id: item for item in current.assessments}
    if len(fresh) != len(current.assessments) or set(fresh) != {item.assessment_id for item in draft.assessment_refs}:
        raise ScheduleError(409)
    for reference in draft.assessment_refs:
        item = fresh[reference.assessment_id]
        if (assessment_fingerprint(item.model_dump(mode="json")) != item.result_sha256
            or _source_ref(item) != reference
            or (item.profile_id, item.profile_version_id, item.profile_sha256, item.profile_is_synthetic)
                != (draft.profile_id, draft.profile_version_id, draft.profile_sha256, draft.is_synthetic)
            or item.profile_is_synthetic != item.catalogue_is_synthetic
            or not item.assessment_at <= current.generated_at < item.expires_at
            or current.horizon_end > item.expires_at):
            raise ScheduleError(409)
        if item.current_validity != "current":
            allowed = "VERIFY_UNKNOWN" if item.current_validity == "unavailable" else "VERIFY_HISTORY"
            if any(task.action_code != allowed for task in draft.tasks if item.assessment_id in task.assessment_ids):
                raise ScheduleError(409)
    # Student-authored study has no assessment claim. Other tasks need an exact source.
    if any(not task.assessment_ids and task.action_code != "SELF_DIRECTED_STUDY" for task in draft.tasks):
        raise ScheduleError(409)


def _monday(instant, zone):
    local = instant.astimezone(zone).date()
    return local - timedelta(days=local.weekday())


def _week_boundary(day, zone):
    """Never choose an ambiguous/nonexistent local Monday midnight."""
    local = datetime.combine(day, time())
    candidates = set()
    for fold in (0, 1):
        instant = local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if instant.astimezone(zone).replace(tzinfo=None, fold=0) == local:
            candidates.add(instant)
    if len(candidates) != 1:
        raise ScheduleError(422)
    return candidates.pop()


def _segments(current, zone):
    free, weeks = [], set()
    for slot in sorted(current.slots, key=lambda item: (item.start_at, str(item.slot_id))):
        cursor = slot.start_at
        while cursor < slot.end_at:
            week = _monday(cursor, zone)
            _week_boundary(week, zone)
            boundary = _week_boundary(week + timedelta(days=7), zone)
            end = min(slot.end_at, boundary)
            if end <= cursor:
                raise ScheduleError(422)
            free.append((cursor, end, slot.slot_id, week))
            weeks.add(week)
            cursor = end
    return free, weeks


def _trial(free, used, work, ready_at, goal, capacity, task_key):
    """A failed trial returns no changes to the shared free time or week totals."""
    remaining, allocations, updated = work, [], []
    trial_used = dict(used)
    for start, end, slot_id, week in free:
        if remaining == 0:
            updated.append((start, end, slot_id, week))
            continue
        first = max(start, ready_at)
        last = min(end, goal - timedelta(microseconds=1)) if goal is not None else end
        available = max(0, _duration(last - first))
        amount = min(remaining, available, max(0, capacity - trial_used.get(week, 0)))
        if amount == 0:
            updated.append((start, end, slot_id, week))
            continue
        finish = first + timedelta(microseconds=amount)
        if start < first:
            updated.append((start, first, slot_id, week))
        if finish < end:
            updated.append((finish, end, slot_id, week))
        allocations.append(dict(task_key=task_key, slot_id=slot_id, start_at=first, end_at=finish,
            duration_microseconds=amount, week_start=week))
        trial_used[week] = trial_used.get(week, 0) + amount
        remaining -= amount
    if remaining:
        return None
    return sorted(updated, key=lambda item: (item[0], str(item[2]))), trial_used, allocations


def schedule_plan(value: ScheduleInput | dict) -> ScheduleDraft:
    """Revalidate a server-bound draft; return a capacity proposal, never confirmation."""
    try:
        if type(value) not in (dict, ScheduleInput):
            raise ScheduleError(422)
        current = ScheduleInput.model_validate(value)
        _validate_sources(current)
        zone = _load_timezone(current.display_timezone)
        free, weeks = _segments(current, zone)
        capacity = None if current.weekly_hours is None else hours_to_microseconds(current.weekly_hours)
        tasks = {item.task_key: item for item in current.draft.tasks}
        goals = {item.task_key: item.due_at for item in current.internal_goals}
        done, summaries, allocations, conflicts, used = {}, [], [], [], {}
        pending = set(tasks)
        # The current date chain cannot authorize any official school hard deadline.
        conflicts.append(dict(code="DEADLINE_UNRESOLVED", task_key=None, deadline_key=None))
        if capacity is None:
            conflicts.append(dict(code="CAPACITY_REQUIRED", task_key=None, deadline_key=None))
        while pending:
            ready = [tasks[key] for key in pending if all(parent in done for parent in tasks[key].dependency_keys)]
            if not ready:
                raise ScheduleError(422)
            task = min(ready, key=lambda item: (goals.get(item.task_key, current.horizon_end),
                       _PRIORITY[item.action_code], item.task_key))
            key, goal = task.task_key, goals.get(task.task_key)
            estimate = None if task.estimated_hours is None else hours_to_microseconds(task.estimated_hours)
            parents = [done[parent] for parent in task.dependency_keys]
            start = end = None
            code = None
            pieces = []
            if any(parent is None for parent in parents):
                code = "DEPENDENCY_BLOCKED"
            elif estimate is None:
                code = "ESTIMATE_REQUIRED"
            else:
                earliest = max((current.horizon_start, *parents))
                if estimate == 0:
                    if earliest >= current.horizon_end or goal is not None and earliest >= goal:
                        code = "INTERNAL_GOAL_CONFLICT" if goal is not None else "CAPACITY_EXCEEDED"
                    else:
                        start = end = earliest
                elif capacity is None:
                    code = "CAPACITY_REQUIRED"
                else:
                    trial = _trial(free, used, estimate, earliest, goal, capacity, key)
                    if trial is None:
                        code = "INTERNAL_GOAL_CONFLICT" if goal is not None else "CAPACITY_EXCEEDED"
                    else:
                        next_free, next_used, pieces = trial
                        if len(allocations) + len(pieces) > MAX_ALLOCATIONS:
                            raise ScheduleError(422)
                        free, used = next_free, next_used
                        start, end = pieces[0]["start_at"], pieces[-1]["end_at"]
            if code is not None:
                conflicts.append(dict(code=code, task_key=key, deadline_key=None))
            done[key] = end
            deadline_keys = tuple(ref for ref in task.deadline_keys if task.action_code != "OBTAIN_ACHIEVED"
                or next(item for item in current.draft.deadline_refs if item.deadline_key == ref).purpose == "supplement")
            summaries.append(dict(task_key=key, action_code=task.action_code, assessment_ids=task.assessment_ids,
                dependency_keys=task.dependency_keys, deadline_keys=deadline_keys, internal_goal=goal,
                estimated_hours=task.estimated_hours, estimated_microseconds=estimate,
                assigned_microseconds=0 if code is not None else estimate,
                remaining_microseconds=estimate if code is not None else 0,
                status="blocked" if code is not None else "milestone" if estimate == 0 else "scheduled",
                start_at=start, end_at=end))
            allocations.extend(pieces)
            pending.remove(key)
        for ref in current.draft.deadline_refs:
            if ref.status != "not_applicable":
                conflicts.append(dict(code="DEADLINE_UNRESOLVED", task_key=None, deadline_key=ref.deadline_key))
        completed = sum(item["status"] != "blocked" for item in summaries)
        options = {"VERIFY_DEADLINES"}
        if any(item["status"] == "blocked" for item in summaries):
            options.update(("REDUCE_GOALS", "EDIT_ESTIMATES", "EDIT_AVAILABILITY", "EDIT_HORIZON"))
        draft = current.draft
        values = dict(schema_version=SCHEDULER_VERSION, scheduler_version=SCHEDULER_VERSION,
            status="ready" if completed == len(summaries) else "partial" if completed else "blocked",
            confirmed=False, constraints_complete=False, draft_sha256=draft.draft_sha256,
            profile_id=draft.profile_id, profile_version_id=draft.profile_version_id,
            profile_sha256=draft.profile_sha256, is_synthetic=draft.is_synthetic,
            generated_at=current.generated_at, horizon_start=current.horizon_start, horizon_end=current.horizon_end,
            display_timezone=current.display_timezone, weekly_hours=current.weekly_hours,
            assessment_refs=draft.assessment_refs, deadline_refs=draft.deadline_refs,
            tasks=tuple(summaries), allocations=tuple(sorted(allocations, key=lambda item: (item["start_at"], item["task_key"]))),
            weeks=tuple(dict(week_start=week, capacity_microseconds=capacity, assigned_microseconds=used.get(week, 0))
                        for week in sorted(weeks)), conflicts=tuple(conflicts), options=tuple(sorted(options)))
        values["schedule_sha256"] = schedule_fingerprint(TypeAdapter(dict).dump_python(values, mode="json"))
        return ScheduleDraft.model_validate(values)
    except ScheduleError:
        raise
    except (ValueError, TypeError, OverflowError, RecursionError, KeyError, AttributeError):
        raise ScheduleError(422) from None
