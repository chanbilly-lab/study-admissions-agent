"""T32 wire-only UTC parsing and response bindings; no domain IO."""

import re
from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel
from ..plans.schedule_schemas import AvailabilitySlot, InternalGoal
from ..profiles.schemas import ProfileMeta
from .schemas import (CompleteResult, ConfirmResult, ExecutionData,
                      ScheduleConfiguration, WorkspaceInput)

UTC_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)"


def wire_utc(value):
    """Parse only explicit UTC RFC3339 wire fields, retaining microseconds."""
    if type(value) is not str or re.fullmatch(UTC_PATTERN, value) is None:
        raise ValueError("an explicit UTC wire instant is required")
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("an explicit UTC wire instant is required") from None
    return result.astimezone(timezone.utc)


class HttpAvailabilitySlot(AvailabilitySlot):
    start_at: datetime = Field(strict=True, json_schema_extra={"pattern": "^" + UTC_PATTERN + "$"})
    end_at: datetime = Field(strict=True, json_schema_extra={"pattern": "^" + UTC_PATTERN + "$"})
    _wire_time = field_validator("start_at", "end_at", mode="before")(wire_utc)


class HttpInternalGoal(InternalGoal):
    due_at: datetime = Field(strict=True, json_schema_extra={"pattern": "^" + UTC_PATTERN + "$"})
    _wire_time = field_validator("due_at", mode="before")(wire_utc)


class HttpScheduleConfiguration(ScheduleConfiguration):
    horizon_start: datetime = Field(strict=True, json_schema_extra={"pattern": "^" + UTC_PATTERN + "$"})
    horizon_end: datetime = Field(strict=True, json_schema_extra={"pattern": "^" + UTC_PATTERN + "$"})
    slots: tuple[HttpAvailabilitySlot, ...] = Field(max_length=256)
    internal_goals: tuple[HttpInternalGoal, ...] = Field(max_length=100)
    _wire_time = field_validator("horizon_start", "horizon_end", mode="before")(wire_utc)


class HttpWorkspaceInput(WorkspaceInput):
    schedule: HttpScheduleConfiguration | None

    def to_domain(self) -> WorkspaceInput:
        # All times were parsed at these finite HTTP fields; the pure domain
        # still receives its original exact native UTC values.
        # Never serialize malformed constructed input into a warning containing
        # private values; the domain validation below still rejects bad fields.
        return WorkspaceInput.model_validate(self.model_dump(warnings=False))


class PlanMeta(ProfileMeta):
    """Actual profile binding for a bounded plan, without a single release claim."""


Item = TypeVar("Item")


class PlanEnvelope(CatalogModel, Generic[Item]):
    data: Item
    meta: PlanMeta

    @model_validator(mode="after")
    def actual_profile(self):
        value = self.data.execution if isinstance(self.data, (ConfirmResult, CompleteResult)) else self.data
        if isinstance(value, ExecutionData):
            draft = value.proposal.effective_draft
            if (self.meta.profile_version_id != draft.profile_version_id
                or self.meta.profile_mode != ("synthetic" if value.is_synthetic else "real")):
                raise ValueError("metadata must bind the actual confirmed profile")
        elif self.meta.profile_version_id is not None:
            raise ValueError("non-plan responses cannot claim a profile version")
        return self
