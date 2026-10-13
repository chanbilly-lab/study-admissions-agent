"""Strict internal date candidates; no approved deadline or evidence claim."""

from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .schemas import CatalogModel, Identifier, PositiveVersion, _IdentityInput, _identifier, _namespace


EventType = Literal[
    "application_open", "application_deadline", "equal_consideration",
    "materials_deadline", "language_supplement", "score_supplement",
    "offer_acceptance", "scholarship_deadline", "enrollment",
]
Precision = Literal["date", "minute", "second", "unknown"]
ConversionStatus = Literal[
    "unique", "date_only", "unknown", "missing_timezone", "ambiguous",
    "nonexistent", "source_conflict", "out_of_range",
]


class DateEventInput(_IdentityInput):
    id: UUID
    dataset_id: UUID
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    event_type: EventType
    original_text: str = Field(strict=True, min_length=1, max_length=4000)
    local_date: date | None = Field(strict=True)
    local_time: time | None = Field(strict=True)
    timezone: str | None = Field(strict=True, min_length=1, max_length=100)
    precision: Precision
    source_alignment: Literal["pending", "conflict"]
    evidence_reference: Identifier | None

    @field_validator("original_text")
    @classmethod
    def valid_original_text(cls, value):
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ValueError("original text must be valid text") from None
        if not value.strip() or "\x00" in value:
            raise ValueError("original text must be nonblank text without null bytes")
        return value

    @field_validator("local_date", mode="before")
    @classmethod
    def native_date(cls, value):
        if value is not None and type(value) is not date:
            raise ValueError("a native calendar date is required")
        return value

    @field_validator("local_time", mode="before")
    @classmethod
    def native_time(cls, value):
        if value is not None and (
            type(value) is not time or value.tzinfo is not None or value.fold != 0
            or value.microsecond != 0
        ):
            raise ValueError("a native local time without timezone, fold or fraction is required")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        if value is not None:
            # The loader uses only the pinned package, never host TZPATH or cache.
            from .dates import _load_timezone
            _load_timezone(value)
        return value

    @field_validator("evidence_reference")
    @classmethod
    def exact_evidence_reference(cls, value):
        return _identifier(value) if value is not None else None

    @model_validator(mode="after")
    def precision_fields(self):
        if self.evidence_reference is not None:
            _namespace(self.evidence_reference, self.is_synthetic)
        if self.precision == "unknown":
            if any(value is not None for value in (self.local_date, self.local_time, self.timezone)):
                raise ValueError("unknown precision requires null date, time and timezone")
        elif self.precision == "date":
            if self.local_date is None or self.local_time is not None:
                raise ValueError("date precision needs a date and no time")
        elif self.local_date is None or self.local_time is None:
            raise ValueError("time precision needs a date and local time")
        elif self.precision == "minute" and self.local_time.second != 0:
            raise ValueError("minute precision cannot contain seconds")
        return self


def _utc_candidate(value):
    if value is not None and (
        type(value) is not datetime or value.tzinfo is None
        or value.utcoffset() != timedelta(0) or value.microsecond != 0 or value.fold != 0
    ):
        raise ValueError("a whole-second aware UTC candidate is required")
    return value


class DateResolution(CatalogModel):
    conversion_status: ConversionStatus
    calculated_utc_instant: datetime | None = Field(strict=True)
    tzdata_version: Literal["2026.4"]

    @field_validator("calculated_utc_instant", mode="before")
    @classmethod
    def aware_utc_candidate(cls, value):
        return _utc_candidate(value)

    @model_validator(mode="after")
    def conversion_fields(self):
        if (self.conversion_status == "unique") != (self.calculated_utc_instant is not None):
            raise ValueError("only unique conversion can contain a calculated UTC candidate")
        return self


class DateEventData(DateEventInput):
    conversion_status: ConversionStatus
    calculated_utc_instant: datetime | None = Field(strict=True)
    utc_instant: None
    review_state: Literal["draft"]
    evidence_state: Literal["unresolved"]
    tzdata_version: Literal["2026.4"]

    @field_validator("calculated_utc_instant", mode="before")
    @classmethod
    def aware_utc_candidate(cls, value):
        return _utc_candidate(value)

    @model_validator(mode="after")
    def recompute_candidate(self):
        from .dates import normalize_date_event
        source = DateEventInput.model_validate({
            field: getattr(self, field) for field in DateEventInput.model_fields
        })
        current = normalize_date_event(source)
        if (self.conversion_status != current.conversion_status
            or self.calculated_utc_instant != current.calculated_utc_instant
            or self.tzdata_version != current.tzdata_version):
            raise ValueError("stored date conversion must match the current pinned calculation")
        return self
