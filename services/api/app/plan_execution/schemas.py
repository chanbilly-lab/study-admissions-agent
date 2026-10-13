"""Bounded T32 state, separate from immutable T30 draft identities."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel, PositiveVersion
from ..evidence.schemas import _uuid
from ..plans.schemas import EstimateOverride, PlanDraft, _sequence
from ..plans.schedule_schemas import (AvailabilitySlot, InternalGoal, ScheduleDraft,
    _utc, _timezone_key, hours_to_microseconds)
from ..profiles.schemas import DecimalText
from ..rules.adapters.schemas import Hash

EXECUTION_HEAD = "0001_execution_t32"
SCHEMA_VERSION = "v2.t32"
MAX_SOURCE_BYTES = 384 * 1024
MAX_PROPOSAL_BYTES = 1024 * 1024
MAX_BODY_BYTES = 64 * 1024


class ExecutionError(ValueError):
    def __init__(self, status_code=503):
        codes = {422: "INVALID_EXECUTION_INPUT", 404: "EXECUTION_NOT_FOUND",
                 409: "EXECUTION_CONFLICT", 503: "EXECUTION_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes:
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


class ExecutionPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_execution: bool = Field(default=False, strict=True)
    real_execution_ready: Literal[False] = False

    @field_validator("real_execution_ready", mode="before")
    @classmethod
    def closed(cls, value):
        if value is not False:
            raise ValueError("real execution is unavailable")
        return value


class ScheduleConfiguration(CatalogModel):
    horizon_start: datetime = Field(strict=True)
    horizon_end: datetime = Field(strict=True)
    display_timezone: str = Field(strict=True, min_length=1, max_length=100)
    weekly_hours: DecimalText | None
    slots: tuple[AvailabilitySlot, ...] = Field(max_length=256)
    internal_goals: tuple[InternalGoal, ...] = Field(max_length=100)
    availability_confirmed: Literal[True]
    rest_excluded: Literal[True]

    _time = field_validator("horizon_start", "horizon_end", mode="before")(_utc)
    _zone = field_validator("display_timezone", mode="before")(_timezone_key)

    @field_validator("weekly_hours", mode="before")
    @classmethod
    def capacity(cls, value):
        if value is not None and hours_to_microseconds(value) > 40 * 3_600_000_000:
            raise ValueError("weekly work exceeds the supported bound")
        return value

    @field_validator("slots", "internal_goals", mode="before")
    @classmethod
    def bounded(cls, value, info):
        return _sequence(value, 256 if info.field_name == "slots" else 100)

    @field_validator("availability_confirmed", "rest_excluded", mode="before")
    @classmethod
    def true(cls, value):
        if value is not True:
            raise ValueError("explicit availability confirmation is required")
        return value


class WorkspaceInput(CatalogModel):
    expected_version: PositiveVersion
    estimate_overrides: tuple[EstimateOverride, ...] = Field(max_length=100)
    schedule: ScheduleConfiguration | None

    @field_validator("estimate_overrides", mode="before")
    @classmethod
    def overrides(cls, value):
        values = _sequence(value, 100)
        rows = tuple(EstimateOverride.model_validate(v) for v in values)
        if len({v.task_key for v in rows}) != len(rows):
            raise ValueError("estimate keys must be unique")
        return rows


class ConfirmInput(CatalogModel):
    expected_version: PositiveVersion
    expected_draft_sha256: Hash
    expected_schedule_sha256: Hash
    confirmed: Literal[True]
    acknowledge_unverified_deadlines: Literal[True]

    @field_validator("confirmed", "acknowledge_unverified_deadlines", mode="before")
    @classmethod
    def true(cls, value):
        if value is not True:
            raise ValueError("explicit plan confirmation is required")
        return value


class CompleteInput(CatalogModel):
    expected_version: PositiveVersion
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def true(cls, value):
        if value is not True:
            raise ValueError("explicit completion confirmation is required")
        return value


class ProposalData(CatalogModel):
    id: UUID
    state_version: PositiveVersion
    estimate_overrides: tuple[EstimateOverride, ...] = Field(max_length=100)
    effective_draft: PlanDraft
    schedule_configuration: ScheduleConfiguration | None
    schedule: ScheduleDraft | None
    created_at: datetime = Field(strict=True)

    _id = field_validator("id", mode="before")(_uuid)
    _time = field_validator("created_at", mode="before")(_utc)
    _estimates = field_validator("estimate_overrides", mode="before")(WorkspaceInput.overrides.__func__)

    @model_validator(mode="after")
    def matching(self):
        if (self.schedule is None) != (self.schedule_configuration is None):
            raise ValueError("schedule and its input must be present together")
        tasks = {t.task_key: t for t in self.effective_draft.tasks}
        if any(v.task_key not in tasks or tasks[v.task_key].estimated_hours != v.estimated_hours for v in self.estimate_overrides):
            raise ValueError("estimates must match the exact effective draft")
        if self.schedule is not None:
            config, schedule = self.schedule_configuration, self.schedule
            if (schedule.draft_sha256 != self.effective_draft.draft_sha256 or schedule.generated_at != self.created_at
                or {t.task_key for t in schedule.tasks} != set(tasks)
                or any(getattr(config,k) != getattr(schedule,k) for k in
                       ("horizon_start","horizon_end","display_timezone","weekly_hours"))):
                raise ValueError("schedule must bind its exact draft and configuration")
        return self


class ConfirmationData(CatalogModel):
    id: UUID
    proposal_id: UUID
    confirmed_state_version: PositiveVersion
    confirmed_at: datetime = Field(strict=True)
    acknowledge_unverified_deadlines: Literal[True]

    _ids = field_validator("id", "proposal_id", mode="before")(_uuid)
    _time = field_validator("confirmed_at", mode="before")(_utc)
    _true = field_validator("acknowledge_unverified_deadlines", mode="before")(ConfirmInput.true.__func__)


class CompletionData(CatalogModel):
    task_key: Hash
    completed_state_version: PositiveVersion
    completed_at: datetime = Field(strict=True)
    source: Literal["student_declared"]

    _time = field_validator("completed_at", mode="before")(_utc)


class ExecutionData(CatalogModel):
    schema_version: Literal["v2.t32"]
    plan_id: UUID
    source_plan_version_id: UUID
    source_draft_sha256: Hash
    state_version: PositiveVersion
    state: Literal["draft", "confirmed"]
    proposal: ProposalData
    confirmation: ConfirmationData | None
    completed_tasks: tuple[CompletionData, ...] = Field(max_length=100)
    created_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)
    is_synthetic: bool = Field(strict=True)

    _ids = field_validator("plan_id", "source_plan_version_id", mode="before")(_uuid)
    _time = field_validator("created_at", "expires_at", mode="before")(_utc)
    _rows = field_validator("completed_tasks", mode="before")(lambda value: _sequence(value, 100))

    @model_validator(mode="after")
    def current_projection(self):
        draft = self.proposal.effective_draft
        if (self.created_at > self.proposal.created_at or self.expires_at != draft.expires_at
            or self.created_at != draft.generated_at or self.is_synthetic != draft.is_synthetic
            or self.proposal.state_version > self.state_version or self.expires_at <= self.proposal.created_at
            or (self.state == "confirmed") != (self.confirmation is not None)):
            raise ValueError("execution must bind its exact proposal and lifetime")
        if self.confirmation is None:
            if self.completed_tasks:
                raise ValueError("unconfirmed plans cannot have completions")
        else:
            c = self.confirmation
            if (c.proposal_id != self.proposal.id or not self.proposal.state_version < c.confirmed_state_version <= self.state_version
                or not self.proposal.created_at <= c.confirmed_at < self.expires_at
                or self.proposal.schedule is None or self.proposal.schedule.status != "ready"
                or self.proposal.schedule.weekly_hours is None):
                raise ValueError("confirmation must bind a ready proposal")
            schedule = self.proposal.schedule
            if (c.confirmed_at >= schedule.horizon_end
                or any(a.start_at < c.confirmed_at for a in schedule.allocations)
                or any(t.start_at < c.confirmed_at for t in schedule.tasks if t.status == "milestone")):
                raise ValueError("confirmed arrangements must start at or after their original confirmation")
        keys = {t.task_key: t for t in draft.tasks}
        completed = {c.task_key: c for c in self.completed_tasks}
        if len(completed) != len(self.completed_tasks):
            raise ValueError("completions must be unique")
        for c in self.completed_tasks:
            if (c.task_key not in keys or self.confirmation is None
                or not self.confirmation.confirmed_state_version < c.completed_state_version <= self.state_version
                or not self.confirmation.confirmed_at <= c.completed_at < self.expires_at
                or any(k not in completed or completed[k].completed_state_version >= c.completed_state_version
                       for k in keys[c.task_key].dependency_keys)):
                raise ValueError("completion must follow its confirmed dependencies")
        if len({c.completed_state_version for c in self.completed_tasks}) != len(self.completed_tasks):
            raise ValueError("completion versions must be unique")
        return self


class ExecutionSummary(CatalogModel):
    plan_id: UUID
    state_version: PositiveVersion
    state: Literal["draft", "confirmed"]
    proposal_id: UUID
    draft_sha256: Hash
    schedule_sha256: Hash | None
    confirmation_id: UUID | None
    completed_count: int = Field(strict=True, ge=0, le=100)
    created_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)
    is_synthetic: bool = Field(strict=True)

    _ids = field_validator("plan_id", "proposal_id", mode="before")(_uuid)
    _optional = field_validator("confirmation_id", mode="before")(lambda value: _uuid(value) if value is not None else None)
    _time = field_validator("created_at", "expires_at", mode="before")(_utc)


class ExecutionPage(CatalogModel):
    items: tuple[ExecutionSummary, ...] = Field(max_length=20)
    next_cursor: str | None = Field(strict=True, max_length=1024)


class ExecutionContextData(CatalogModel):
    schema_version: Literal["v2.t32"]
    can_create: bool = Field(strict=True)
    can_read: bool = Field(strict=True)
    can_edit: bool = Field(strict=True)
    can_confirm: bool = Field(strict=True)
    can_complete: bool = Field(strict=True)
    reason: Literal["ready", "processing_disabled"]
    is_synthetic: bool = Field(strict=True)


class ConfirmResult(CatalogModel):
    execution: ExecutionData
    replayed: bool = Field(strict=True)
    confirmed_state_version: PositiveVersion

    @model_validator(mode="after")
    def exact_confirmation(self):
        if self.execution.confirmation is None or self.confirmed_state_version != self.execution.confirmation.confirmed_state_version:
            raise ValueError("receipt must name the immutable confirmation")
        return self


class CompleteResult(CatalogModel):
    execution: ExecutionData
    replayed: bool = Field(strict=True)
