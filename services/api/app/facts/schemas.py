"""Closed T17 draft fact contracts; classification is never publication."""

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.date_schemas import (
    ConversionStatus, DateEventData, EventType, Precision,
)
from ..admissions_catalog.schemas import CatalogModel, Identifier, PositiveVersion, _identifier
from ..evidence.schemas import _utc
from ..ingestion.schemas import ParsedRow, _uuid


FACTS_HEAD = "0001_facts_t17"
MAX_CONFLICTS = 200
ClaimKind = Literal["unknown", "minimum_requirement", "typical_offer", "historical_statistic", "information"]
UnitCode = Literal["unknown", "points", "percent", "fraction", "CNY", "GBP", "item", "people", "text", "ISO_DATE"]
Period = Literal["unknown", "not_applicable", "academic_year", "program", "one_time", "survey_period"]
StatisticsBasis = Literal["unknown", "not_applicable", "admission", "employment", "other"]


class FactsError(ValueError):
    """Fixed errors without original values, paths, parser or SQL details."""

    def __init__(self, status_code=503, code=None):
        codes = {422: "INVALID_FACT_INPUT", 404: "FACT_NOT_FOUND",
                 409: "FACT_CONFLICT", 503: "FACT_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


def _bounded_context(value: str, maximum: int) -> str:
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise ValueError("bounded valid context text is required") from None
    if (not value.strip() or len(encoded) > maximum
            or any(ord(c) < 32 and c not in "\t\r\n" or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError("bounded nonblank context text is required")
    return value


class Classification(CatalogModel):
    claim_kind: ClaimKind
    unit_code: UnitCode
    period: Period
    statistics_basis: StatisticsBasis
    statistic_population: str | None = Field(strict=True, min_length=1, max_length=512)
    statistic_denominator: str | None = Field(strict=True, min_length=1, max_length=512)
    cohort_year: int | None = Field(strict=True, ge=1, le=9999)
    survey_period: str | None = Field(strict=True, min_length=1, max_length=100)
    date_event_id: UUID | None

    @field_validator("statistic_population", "statistic_denominator")
    @classmethod
    def bounded_statistics_context(cls, value):
        return _bounded_context(value, 512) if value is not None else None

    @field_validator("survey_period")
    @classmethod
    def bounded_survey_period(cls, value):
        return _bounded_context(value, 100) if value is not None else None

    @field_validator("date_event_id", mode="before")
    @classmethod
    def canonical_date_reference(cls, value):
        return _uuid(value) if value is not None else None


class FactCreate(CatalogModel):
    import_id: UUID
    import_row_id: UUID
    classification: Classification
    evidence_id: UUID | None

    @field_validator("import_id", "import_row_id", "evidence_id", mode="before")
    @classmethod
    def canonical_reference(cls, value):
        return _uuid(value) if value is not None else None


class FactPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    real_facts_ready: bool = Field(default=False, strict=True)


class DateResolutionSnapshot(CatalogModel):
    date_event_id: UUID
    dataset_id: UUID
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    reference_key: Identifier
    is_synthetic: bool = Field(strict=True)
    evidence_reference: Identifier | None
    event_type: EventType
    original_text: str = Field(strict=True, min_length=1, max_length=4000)
    precision: Precision
    local_date: date | None = Field(strict=True)
    local_time: time | None = Field(strict=True)
    timezone: str | None = Field(strict=True, min_length=1, max_length=100)
    source_alignment: Literal["pending", "conflict"]
    conversion_status: ConversionStatus
    calculated_utc_instant: datetime | None = Field(strict=True)
    utc_instant: None
    tzdata_version: Literal["2026.4"]

    @field_validator("date_event_id", "dataset_id", "offering_id", mode="before")
    @classmethod
    def canonical_reference(cls, value):
        return _uuid(value)

    @field_validator("reference_key", "evidence_reference")
    @classmethod
    def exact_namespace_reference(cls, value):
        return _identifier(value) if value is not None else None

    @model_validator(mode="after")
    def revalidate_pinned_original_date(self):
        source = self.model_dump()
        source["id"] = source.pop("date_event_id")
        # Fixed T12 markers cannot be promoted by a snapshot or a model copy.
        source.update(review_state="draft", evidence_state="unresolved")
        DateEventData.model_validate(source)
        return self

    @classmethod
    def from_date_event(cls, value: DateEventData):
        current = DateEventData.model_validate(value)
        data = current.model_dump(exclude={"review_state", "evidence_state"})
        data["date_event_id"] = data.pop("id")
        return cls.model_validate(data)


class TypedPayload(ParsedRow):
    classification: Classification
    evidence_id: UUID | None
    normalized_value: str | None = Field(strict=True, min_length=1, max_length=4096)
    date_resolution: DateResolutionSnapshot | None
    state: Literal["draft", "review_required"]
    hard_rule: Literal[False]
    publication_eligible: Literal[False]

    @field_validator("evidence_id", mode="before")
    @classmethod
    def canonical_evidence_reference(cls, value):
        return _uuid(value) if value is not None else None

    @field_validator("hard_rule", "publication_eligible", mode="before")
    @classmethod
    def strict_unapproved_marker(cls, value):
        if value is not False:
            raise ValueError("a strict false unapproved marker is required")
        return value

    @model_validator(mode="after")
    def revalidate_derived_payload(self):
        from .typing import _typed_values
        row = ParsedRow.model_validate({name: getattr(self, name) for name in ParsedRow.model_fields})
        normalized, expected = _typed_values(row, self.classification,
            evidence_id=self.evidence_id, date_resolution=self.date_resolution)
        has_conflicts = bool(getattr(self, "conflicting_ids", ()))
        if self.normalized_value != normalized or self.state != ("conflicted" if has_conflicts else expected):
            raise ValueError("typed payload must match its original row and explicit classification")
        return self


class TypedCandidate(TypedPayload):
    id: UUID
    version: Literal[1]
    import_id: UUID
    import_row_id: UUID
    dataset_id: UUID
    is_synthetic: bool = Field(strict=True)
    created_at: datetime = Field(strict=True)
    conflicting_ids: tuple[UUID, ...] = Field(max_length=MAX_CONFLICTS)
    state: Literal["draft", "review_required", "conflicted"]

    @field_validator("id", "import_id", "import_row_id", "dataset_id", mode="before")
    @classmethod
    def canonical_server_reference(cls, value):
        return _uuid(value)

    @field_validator("version", mode="before")
    @classmethod
    def exact_candidate_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("a strict initial candidate version is required")
        return value

    @field_validator("created_at", mode="before")
    @classmethod
    def native_server_timestamp(cls, value):
        return _utc(value)

    @field_validator("conflicting_ids", mode="before")
    @classmethod
    def canonical_conflict_references(cls, value):
        if type(value) not in (tuple, list):
            raise ValueError("a bounded sequence of conflict references is required")
        return tuple(_uuid(item) for item in value)

    @model_validator(mode="after")
    def coherent_server_scope_and_conflicts(self):
        ParsedRow.model_validate({name: getattr(self, name) for name in ParsedRow.model_fields}).validate_namespace(self.is_synthetic)
        if (len(set(self.conflicting_ids)) != len(self.conflicting_ids) or self.id in self.conflicting_ids
                or (self.state == "conflicted") != bool(self.conflicting_ids)):
            raise ValueError("conflict references must be distinct other candidates")
        if self.date_resolution is not None and (
            self.date_resolution.dataset_id != self.dataset_id
            or self.date_resolution.is_synthetic != self.is_synthetic
        ):
            raise ValueError("date scope and synthetic marker must match the candidate")
        return self
