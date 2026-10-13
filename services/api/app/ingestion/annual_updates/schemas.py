"""Closed contracts for an internal review date, never an admissions deadline."""

from datetime import datetime, timezone
import hashlib
import json
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from ...admissions_catalog.schemas import CatalogModel, Identifier, _identifier


def canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def config_digest(config: "ScheduleConfig") -> str:
    current = ScheduleConfig.model_validate(config.model_dump())
    return hashlib.sha256(canonical(current.model_dump(mode="json"))).hexdigest()


def cycle_identity(schedule_id: str, year: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"study:annual-source:{schedule_id}:{year}")


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware clock is required")
    return value.astimezone(timezone.utc)


class UpdateTarget(CatalogModel):
    reference_key: Identifier
    dataset_type: Literal["province_cutoffs", "admission_observations", "entry_requirements"]
    country: Literal["CN", "GB"]
    pathway: Literal["ordinary_gaokao", "uk_undergraduate"]
    region_key: str | None = Field(default=None, strict=True, pattern=r"^cn_region_[0-9]{2}$")
    institution_ref: Identifier | None = None
    program_ref: Identifier | None = None
    college_ref: Identifier | None = None
    subject_category: str | None = Field(default=None, strict=True, min_length=1, max_length=128)
    batch: str | None = Field(default=None, strict=True, min_length=1, max_length=128)
    round: str | None = Field(default=None, strict=True, min_length=1, max_length=128)
    intake: str | None = Field(default=None, strict=True, min_length=1, max_length=40)
    target_year_offset: int = Field(strict=True, ge=-1, le=1)
    source_hints: tuple[Identifier, ...] = Field(default=(), max_length=10)
    scope_status: Literal["requires_source_and_scope_review"] = "requires_source_and_scope_review"

    @field_validator("reference_key", "institution_ref", "program_ref", "college_ref")
    @classmethod
    def identifiers(cls, value):
        return _identifier(value) if value is not None else None

    @field_validator("subject_category", "batch", "round", "intake")
    @classmethod
    def plain_scope(cls, value):
        if value is not None and (not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ValueError("A plain scope label is required")
        return value

    @model_validator(mode="after")
    def separate_paths(self):
        for hint in self.source_hints:
            _identifier(hint)
        if len(self.source_hints) != len(set(self.source_hints)):
            raise ValueError("Source hints must be unique")
        if self.dataset_type == "entry_requirements":
            if (self.country != "GB" or self.pathway != "uk_undergraduate" or not self.institution_ref
                    or any(value is not None for value in (self.region_key, self.subject_category, self.batch, self.round))):
                raise ValueError("A separate UK institution scope is required")
        else:
            if (self.country != "CN" or self.pathway != "ordinary_gaokao" or self.region_key is None
                    or self.region_key not in {f"cn_region_{number:02d}" for number in range(1, 32)}
                    or self.college_ref is not None or self.intake is not None):
                raise ValueError("A separate mainland examination scope is required")
            if self.dataset_type == "province_cutoffs" and (self.institution_ref is not None or self.program_ref is not None):
                raise ValueError("Province cutoffs cannot be institution admission scores")
        if self.program_ref is not None and self.institution_ref is None:
            raise ValueError("A programme reference requires its institution")
        return self


class ScheduleConfig(CatalogModel):
    schema_version: Literal["annual.source.schedule.1"]
    schedule_id: Identifier
    revision: int = Field(strict=True, ge=1, le=2_147_483_647)
    enabled: bool = Field(default=False, strict=True)
    start_cycle_year: int = Field(default=2026, strict=True, ge=2000, le=9998)
    timezone: str = Field(default="Asia/Shanghai", strict=True, min_length=1, max_length=100)
    month: int = Field(default=11, strict=True, ge=1, le=12)
    day: int = Field(default=1, strict=True, ge=1, le=28)
    hour: int = Field(default=9, strict=True, ge=0, le=23)
    minute: int = Field(default=0, strict=True, ge=0, le=59)
    poll_interval_seconds: int = Field(default=3600, strict=True, ge=60, le=3600)
    max_consecutive_failures: int = Field(default=5, strict=True, ge=1, le=10)
    targets: tuple[UpdateTarget, ...] = Field(min_length=1, max_length=10)

    @field_validator("schedule_id")
    @classmethod
    def exact_identifier(cls, value):
        return _identifier(value)

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value):
        ZoneInfo(value)
        return value

    @model_validator(mode="after")
    def unique_targets(self):
        if len({target.reference_key for target in self.targets}) != len(self.targets):
            raise ValueError("Each annual target must have a unique reference")
        return self


class RequestPlan(CatalogModel):
    id: UUID
    target_ref: Identifier
    dataset_type: Literal["province_cutoffs", "admission_observations", "entry_requirements"]
    exam_year: int | None = Field(default=None, strict=True, ge=1, le=9999)
    entry_year: int | None = Field(default=None, strict=True, ge=1, le=9999)
    scope: UpdateTarget
    source_evidence_year: None = None
    status: Literal["awaiting_collection"] = "awaiting_collection"
    network_requested: Literal[False] = False
    facts_updated: Literal[False] = False
    published: Literal[False] = False

    @field_validator("network_requested", "facts_updated", "published", mode="before")
    @classmethod
    def exact_false(cls, value):
        if value is not False:
            raise ValueError("Only a collection request is supported")
        return value

    @model_validator(mode="after")
    def year_axis(self):
        if self.target_ref != self.scope.reference_key or self.dataset_type != self.scope.dataset_type:
            raise ValueError("The request scope must match its target")
        if self.dataset_type == "entry_requirements":
            valid = self.entry_year is not None and self.exam_year is None
        else:
            valid = self.exam_year is not None and self.entry_year is None
        if not valid:
            raise ValueError("Examination and entry years cannot be mixed")
        return self


class AnnualPlan(CatalogModel):
    schema_version: Literal["annual.source.plan.1"] = "annual.source.plan.1"
    cycle_id: UUID
    schedule_id: Identifier
    config_revision: int = Field(strict=True, ge=1, le=2_147_483_647)
    config_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    cycle_year: int = Field(strict=True, ge=2000, le=9998)
    scheduled_at: datetime
    planned_at: datetime
    requests: tuple[RequestPlan, ...] = Field(min_length=1, max_length=10)

    @field_validator("scheduled_at", "planned_at")
    @classmethod
    def utc_instant(cls, value):
        return utc(value)

    @model_validator(mode="after")
    def bound_identity_and_years(self):
        _identifier(self.schedule_id)
        if self.cycle_id != cycle_identity(self.schedule_id, self.cycle_year) or self.planned_at < self.scheduled_at:
            raise ValueError("A due annual identity is required")
        if len({request.target_ref for request in self.requests}) != len(self.requests):
            raise ValueError("Annual request targets must be unique")
        for request in self.requests:
            actual = request.entry_year if request.dataset_type == "entry_requirements" else request.exam_year
            if (request.id != uuid5(self.cycle_id, request.target_ref)
                    or actual != self.cycle_year + request.scope.target_year_offset):
                raise ValueError("Request identity and requested year must be pinned to the cycle")
        return self
