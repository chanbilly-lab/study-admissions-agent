"""Strict internal inputs and unconfirmed T31 capacity proposals."""

import re
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel
from ..api.v2.idempotency_canonical import canonical_request_hash
from ..evidence.schemas import _uuid
from ..profiles.schemas import DecimalText, decimal_text
from ..rules.adapters.schemas import Hash
from ..rules.schemas import AssessmentData
from .schemas import (PlanAssessmentRef, PlanDeadlineRef, PlanDraft, TaskAction,
                      _sequence)

SCHEDULER_VERSION = "T31_v1"
MAX_SLOTS = 256
MAX_ALLOCATIONS = 4096
MAX_HORIZON_DAYS = 84
MICROSECONDS_PER_HOUR = 3_600_000_000
MAX_MICROSECONDS = 1000 * MICROSECONDS_PER_HOUR
Microseconds = Annotated[int, Field(strict=True, ge=0, le=MAX_MICROSECONDS)]
ConflictCode = Literal["CAPACITY_REQUIRED", "ESTIMATE_REQUIRED", "CAPACITY_EXCEEDED",
    "DEPENDENCY_BLOCKED", "INTERNAL_GOAL_CONFLICT", "DEADLINE_UNRESOLVED"]
ScheduleOption = Literal["REDUCE_GOALS", "EDIT_ESTIMATES", "EDIT_AVAILABILITY",
    "EDIT_HORIZON", "VERIFY_DEADLINES"]


class ScheduleError(ValueError):
    def __init__(self, status_code=422):
        codes = {422: "INVALID_SCHEDULE_INPUT", 409: "SCHEDULE_SOURCE_CONFLICT",
                 503: "SCHEDULE_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes:
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


def _utc(value):
    # Check tzinfo identity before invoking any user-supplied offset callback.
    if (type(value) is not datetime or type(value.tzinfo) is not timezone
        or value.fold or value.utcoffset() != timedelta(0)):
        raise ValueError("an explicit native UTC instant is required")
    return value.astimezone(timezone.utc)


def hours_to_microseconds(value):
    """Convert six-decimal hours exactly, without floating point or rounding."""
    current = decimal_text(value)
    whole, _, fraction = current.partition(".")
    return int(whole) * MICROSECONDS_PER_HOUR + int(fraction.ljust(6, "0")) * 3600


def schedule_fingerprint(payload):
    return canonical_request_hash({key: value for key, value in payload.items()
                                   if key != "schedule_sha256"})


def _timezone_key(value):
    if type(value) is not str or not 1 <= len(value) <= 100:
        raise ValueError("an explicit supported IANA key is required")
    parts = value.split("/")
    regions = {"Africa", "America", "Antarctica", "Arctic", "Asia", "Atlantic",
               "Australia", "Europe", "Indian", "Pacific"}
    if value != "UTC" and (len(parts) < 2 or parts[0] not in regions
        or any(re.fullmatch(r"[A-Za-z0-9_+-]+", item) is None for item in parts)):
        raise ValueError("an explicit supported IANA key is required")
    return value


class AvailabilitySlot(CatalogModel):
    slot_id: UUID
    start_at: datetime = Field(strict=True)
    end_at: datetime = Field(strict=True)

    _id = field_validator("slot_id", mode="before")(_uuid)
    _times = field_validator("start_at", "end_at", mode="before")(_utc)

    @model_validator(mode="after")
    def bounded_duration(self):
        if not self.start_at < self.end_at <= self.start_at + timedelta(hours=8):
            raise ValueError("availability must be positive and at most eight elapsed hours")
        return self


class InternalGoal(CatalogModel):
    task_key: Hash
    due_at: datetime = Field(strict=True)

    _time = field_validator("due_at", mode="before")(_utc)


class ScheduleInput(CatalogModel):
    draft: PlanDraft
    assessments: tuple[AssessmentData, ...] = Field(min_length=1, max_length=4)
    generated_at: datetime = Field(strict=True)
    horizon_start: datetime = Field(strict=True)
    horizon_end: datetime = Field(strict=True)
    display_timezone: str = Field(strict=True, min_length=1, max_length=100)
    availability_confirmed: Literal[True]
    rest_excluded: Literal[True]
    weekly_hours: DecimalText | None
    slots: tuple[AvailabilitySlot, ...] = Field(max_length=MAX_SLOTS)
    internal_goals: tuple[InternalGoal, ...] = Field(default=(), max_length=100)

    _times = field_validator("generated_at", "horizon_start", "horizon_end", mode="before")(_utc)
    _zone = field_validator("display_timezone", mode="before")(_timezone_key)

    @field_validator("availability_confirmed", "rest_excluded", mode="before")
    @classmethod
    def explicit_true(cls, value):
        if value is not True:
            raise ValueError("availability and excluded rest require explicit confirmation")
        return value

    @field_validator("weekly_hours", mode="before")
    @classmethod
    def capacity(cls, value):
        if value is not None and hours_to_microseconds(value) > 40 * MICROSECONDS_PER_HOUR:
            raise ValueError("weekly capacity exceeds the supported bound")
        return value

    @field_validator("draft", mode="before")
    @classmethod
    def native_draft(cls, value):
        if type(value) not in (dict, PlanDraft):
            raise ValueError("an exact server draft is required")
        raw = value if type(value) is dict else value.__dict__
        for name in ("generated_at", "expires_at"):
            _utc(raw.get(name))
        for name, maximum in (("tasks", 100), ("assessment_refs", 4), ("deadline_refs", 120), ("warnings", 7)):
            _sequence(raw.get(name), maximum, minimum=1 if name in {"tasks", "assessment_refs"} else 0)
        return value

    @field_validator("assessments", "slots", "internal_goals", mode="before")
    @classmethod
    def bounded_native(cls, value, info):
        maximum = {"assessments": 4, "slots": MAX_SLOTS, "internal_goals": 100}[info.field_name]
        _sequence(value, maximum, minimum=1 if info.field_name == "assessments" else 0)
        if info.field_name == "assessments":
            for item in value:
                if type(item) not in (dict, AssessmentData):
                    raise ValueError("exact server assessments are required")
                raw = item if type(item) is dict else item.__dict__
                for name in ("assessment_at", "expires_at"):
                    _utc(raw.get(name))
        return value

    @model_validator(mode="after")
    def bounded_horizon(self):
        if not (self.draft.generated_at <= self.generated_at <= self.horizon_start < self.horizon_end
                <= self.draft.expires_at):
            raise ValueError("the horizon must remain inside the draft's retained lifetime")
        if self.horizon_end - self.horizon_start > timedelta(days=MAX_HORIZON_DAYS):
            raise ValueError("the horizon exceeds the supported bound")
        ordered = sorted(self.slots, key=lambda item: item.start_at)
        if len({item.slot_id for item in ordered}) != len(ordered):
            raise ValueError("availability IDs must be unique")
        for index, item in enumerate(ordered):
            if not self.horizon_start <= item.start_at < item.end_at <= self.horizon_end:
                raise ValueError("availability must stay within the horizon")
            if index and ordered[index - 1].end_at > item.start_at:
                raise ValueError("availability cannot overlap")
        if sum((item.end_at - item.start_at for item in ordered), timedelta()) > timedelta(hours=520):
            raise ValueError("total availability exceeds the supported bound")
        keys = {item.task_key for item in self.draft.tasks}
        if len({item.task_key for item in self.internal_goals}) != len(self.internal_goals):
            raise ValueError("internal goals must be unique")
        for goal in self.internal_goals:
            if goal.task_key not in keys or not self.horizon_start <= goal.due_at <= self.horizon_end:
                raise ValueError("internal goals must belong to the bounded draft horizon")
        return self


class ScheduleAllocation(CatalogModel):
    task_key: Hash
    slot_id: UUID
    start_at: datetime = Field(strict=True)
    end_at: datetime = Field(strict=True)
    duration_microseconds: Microseconds
    week_start: date = Field(strict=True)

    _times = field_validator("start_at", "end_at", mode="before")(_utc)

    @model_validator(mode="after")
    def exact_duration(self):
        delta = self.end_at - self.start_at
        actual = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
        if actual <= 0 or actual != self.duration_microseconds:
            raise ValueError("allocations must retain exact positive elapsed duration")
        return self


class TaskSchedule(CatalogModel):
    task_key: Hash
    action_code: TaskAction
    assessment_ids: tuple[UUID, ...] = Field(max_length=4)
    dependency_keys: tuple[Hash, ...] = Field(max_length=60)
    deadline_keys: tuple[Hash, ...] = Field(max_length=120)
    internal_goal: datetime | None = Field(strict=True)
    estimated_hours: DecimalText | None
    estimated_microseconds: Microseconds | None
    assigned_microseconds: Microseconds
    remaining_microseconds: Microseconds | None
    status: Literal["scheduled", "milestone", "blocked"]
    start_at: datetime | None = Field(strict=True)
    end_at: datetime | None = Field(strict=True)

    @field_validator("internal_goal", "start_at", "end_at", mode="before")
    @classmethod
    def optional_utc(cls, value):
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def whole_task(self):
        estimated = None if self.estimated_hours is None else hours_to_microseconds(self.estimated_hours)
        if self.estimated_microseconds != estimated:
            raise ValueError("estimated duration must match the exact hours")
        if self.status == "blocked":
            if (self.assigned_microseconds != 0 or self.remaining_microseconds != estimated
                or self.start_at is not None or self.end_at is not None):
                raise ValueError("failed trial allocations cannot consume capacity")
        else:
            if (estimated is None or self.assigned_microseconds != estimated or self.remaining_microseconds != 0
                or self.start_at is None or self.end_at is None or self.end_at < self.start_at
                or (self.status == "milestone") != (estimated == 0)):
                raise ValueError("completed capacity proposals must account for the entire task")
            if self.internal_goal is not None and self.end_at >= self.internal_goal:
                raise ValueError("internal goals are strict completion bounds")
        return self


class ScheduleConflict(CatalogModel):
    code: ConflictCode
    task_key: Hash | None
    deadline_key: Hash | None


class ScheduleWeek(CatalogModel):
    week_start: date = Field(strict=True)
    capacity_microseconds: Microseconds | None
    assigned_microseconds: Microseconds

    @model_validator(mode="after")
    def capacity(self):
        if self.week_start.weekday() != 0 or (self.capacity_microseconds is not None
            and self.assigned_microseconds > self.capacity_microseconds):
            raise ValueError("week proposals cannot exceed confirmed capacity")
        if self.capacity_microseconds is None and self.assigned_microseconds:
            raise ValueError("unknown capacity cannot be allocated")
        return self


class ScheduleDraft(CatalogModel):
    schema_version: Literal["T31_v1"]
    scheduler_version: Literal["T31_v1"]
    status: Literal["ready", "partial", "blocked"]
    confirmed: Literal[False]
    constraints_complete: Literal[False]
    draft_sha256: Hash
    profile_id: UUID
    profile_version_id: UUID
    profile_sha256: Hash
    is_synthetic: bool = Field(strict=True)
    generated_at: datetime = Field(strict=True)
    horizon_start: datetime = Field(strict=True)
    horizon_end: datetime = Field(strict=True)
    display_timezone: str = Field(strict=True)
    weekly_hours: DecimalText | None
    assessment_refs: tuple[PlanAssessmentRef, ...] = Field(min_length=1, max_length=4)
    deadline_refs: tuple[PlanDeadlineRef, ...] = Field(max_length=120)
    tasks: tuple[TaskSchedule, ...] = Field(min_length=1, max_length=100)
    allocations: tuple[ScheduleAllocation, ...] = Field(max_length=MAX_ALLOCATIONS)
    weeks: tuple[ScheduleWeek, ...] = Field(max_length=14)
    conflicts: tuple[ScheduleConflict, ...] = Field(max_length=222)
    options: tuple[ScheduleOption, ...] = Field(max_length=5)
    schedule_sha256: Hash

    _times = field_validator("generated_at", "horizon_start", "horizon_end", mode="before")(_utc)
    _zone = field_validator("display_timezone", mode="before")(_timezone_key)
    _capacity = field_validator("weekly_hours", mode="before")(ScheduleInput.capacity.__func__)

    @field_validator("assessment_refs", "deadline_refs", "tasks", "allocations", "weeks", "conflicts", "options", mode="before")
    @classmethod
    def bounded_output(cls, value, info):
        return _sequence(value, {"assessment_refs": 4, "deadline_refs": 120, "tasks": 100,
            "allocations": MAX_ALLOCATIONS, "weeks": 14, "conflicts": 222, "options": 5}[info.field_name],
            minimum=1 if info.field_name in {"assessment_refs", "tasks"} else 0)

    @field_validator("confirmed", "constraints_complete", mode="before")
    @classmethod
    def exact_false(cls, value):
        if value is not False:
            raise ValueError("a capacity proposal cannot confirm a plan or official constraints")
        return value

    @model_validator(mode="after")
    def exact_result(self):
        from ..admissions_catalog.dates import _load_timezone
        zone = _load_timezone(self.display_timezone)
        if not self.generated_at <= self.horizon_start < self.horizon_end or (
            self.horizon_end - self.horizon_start > timedelta(days=MAX_HORIZON_DAYS)):
            raise ValueError("proposal times must retain the bounded horizon")
        tasks = {item.task_key: item for item in self.tasks}
        weeks = {item.week_start: item for item in self.weeks}
        if len(tasks) != len(self.tasks) or len(weeks) != len(self.weeks):
            raise ValueError("schedule references must be unique")
        totals = {key: 0 for key in tasks}
        weekly = {key: 0 for key in weeks}
        pieces = {key: [] for key in tasks}
        ordered = sorted(self.allocations, key=lambda item: item.start_at)
        for index, item in enumerate(ordered):
            if item.task_key not in tasks or item.week_start not in weeks:
                raise ValueError("allocations must belong to the proposal")
            if not self.horizon_start <= item.start_at < item.end_at <= self.horizon_end:
                raise ValueError("allocation times must stay inside the horizon")
            if index and ordered[index - 1].end_at > item.start_at:
                raise ValueError("allocated time cannot overlap across tasks")
            for instant in (item.start_at, item.end_at - timedelta(microseconds=1)):
                local = instant.astimezone(zone).date()
                if local - timedelta(days=local.weekday()) != item.week_start:
                    raise ValueError("an allocation must stay in its actual local ISO week")
            totals[item.task_key] += item.duration_microseconds
            weekly[item.week_start] += item.duration_microseconds
            pieces[item.task_key].append(item)
        if any(totals[key] != task.assigned_microseconds for key, task in tasks.items()) or any(
            weekly[key] != week.assigned_microseconds for key, week in weeks.items()):
            raise ValueError("all task and week totals must account for actual allocations")
        capacity = None if self.weekly_hours is None else hours_to_microseconds(self.weekly_hours)
        if any(week.capacity_microseconds != capacity for week in self.weeks):
            raise ValueError("each week must use the same explicitly confirmed capacity")
        visiting, visited = set(), set()
        def visit(key):
            if key in visiting:
                raise ValueError("proposal dependencies cannot contain a cycle")
            if key in visited:
                return
            visiting.add(key)
            task = tasks[key]
            if len(set(task.dependency_keys)) != len(task.dependency_keys):
                raise ValueError("dependency references must be unique")
            for parent in task.dependency_keys:
                if parent not in tasks:
                    raise ValueError("each dependency must belong to the proposal")
                visit(parent)
                if task.status != "blocked" and (tasks[parent].end_at is None
                    or tasks[parent].end_at > task.start_at):
                    raise ValueError("all dependencies must finish before a task starts")
            if task.status != "blocked":
                if not self.horizon_start <= task.start_at <= task.end_at <= self.horizon_end:
                    raise ValueError("task bounds must stay inside the horizon")
                if task.status == "milestone":
                    if task.start_at != task.end_at or task.end_at >= self.horizon_end:
                        raise ValueError("a milestone needs one instant inside the horizon")
                elif not pieces[key] or (task.start_at, task.end_at) != (
                    pieces[key][0].start_at, pieces[key][-1].end_at):
                    raise ValueError("task bounds must equal its actual first and last allocation")
            if task.internal_goal is not None and not self.horizon_start <= task.internal_goal <= self.horizon_end:
                raise ValueError("internal goals must retain their bounded input scope")
            visiting.remove(key)
            visited.add(key)
        for key in tasks:
            visit(key)
        completed = sum(item.status != "blocked" for item in self.tasks)
        expected = "ready" if completed == len(self.tasks) else "partial" if completed else "blocked"
        if self.status != expected or schedule_fingerprint(self.model_dump(mode="json")) != self.schedule_sha256:
            raise ValueError("the proposal state and hash must match its content")
        return self
