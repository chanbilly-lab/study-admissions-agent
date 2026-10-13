"""Bounded student declarations, without inferred eligibility or identity."""

from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator, with_config
from typing_extensions import TypedDict

from ..admissions_catalog.schemas import CatalogModel, Identifier, PositiveVersion, ScopeKey

PROFILES_HEAD = "0001_profiles_t23"
SCHEMA_VERSION = "v2.t23"
MAX_PROFILE_BYTES = 65536
DecimalText = Annotated[str, Field(strict=True, max_length=14,
    pattern=r"^(0|[1-9][0-9]{0,6})(\.[0-9]{1,6})?$")]


class ProfileError(ValueError):
    def __init__(self, status_code=503):
        codes = {422: "INVALID_PROFILE_INPUT", 404: "PROFILE_NOT_FOUND",
                 409: "PROFILE_CONFLICT", 503: "PROFILE_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes:
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__({422: "Profile input is invalid", 404: "Profile was not found",
                         409: "Profile version conflicts", 503: "Profile service is unavailable"}[status_code])


def decimal_text(value):
    if type(value) is not str or re.fullmatch(r"(0|[1-9][0-9]{0,6})(\.[0-9]{1,6})?", value) is None:
        raise ValueError("a bounded explicit decimal string is required")
    return value


def server_time(value):
    try:
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None or value.fold:
            raise ValueError()
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError("an explicit server time is required") from None


class GradeSlot(CatalogModel):
    status: Literal["provided", "missing", "pending", "not_applicable"]
    value: DecimalText | None
    scale: DecimalText | None
    unit: Literal["points", "band"] | None

    @field_validator("value", "scale")
    @classmethod
    def decimal(cls, value):
        return decimal_text(value) if value is not None else None

    @model_validator(mode="after")
    def coupled(self):
        if self.status == "provided":
            if (self.value is None or self.scale is None or self.unit is None
                or Decimal(self.scale) <= 0 or Decimal(self.value) > Decimal(self.scale)):
                raise ValueError("provided grades require a value, positive scale and matching unit")
        elif self.value is not None or self.scale is not None or self.unit is not None:
            raise ValueError("missing grades must retain null values")
        return self


class AssessmentPair(CatalogModel):
    achieved: GradeSlot
    predicted: GradeSlot


@with_config(ConfigDict(extra="forbid"))
class GradeAssessments(TypedDict, total=False):
    gaokao_total: AssessmentPair
    chinese: AssessmentPair
    math: AssessmentPair
    gaokao_english: AssessmentPair
    physics: AssessmentPair
    chemistry: AssessmentPair
    biology: AssessmentPair
    politics: AssessmentPair
    history: AssessmentPair
    geography: AssessmentPair
    ielts_overall: AssessmentPair
    ielts_listening: AssessmentPair
    ielts_reading: AssessmentPair
    ielts_writing: AssessmentPair
    ielts_speaking: AssessmentPair


ASSESSMENT_KEYS = tuple(GradeAssessments.__annotations__)


class Budget(CatalogModel):
    amount: DecimalText
    currency: Literal["CNY", "GBP"]

    @field_validator("amount")
    @classmethod
    def decimal(cls, value):
        return decimal_text(value)


class Preferences(CatalogModel):
    preferred_fields: tuple[str, ...] = Field(max_length=10)
    preferred_countries: tuple[Literal["CN", "GB"], ...] = Field(max_length=2)
    budget: Budget | None

    @field_validator("preferred_fields")
    @classmethod
    def text(cls, values):
        for value in values:
            try:
                if (type(value) is not str or not 1 <= len(value) <= 100 or not value.strip()
                    or len(value.encode("utf-8")) > 400 or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                    raise ValueError()
            except UnicodeError:
                raise ValueError("bounded preference text is required") from None
        if len(set(values)) != len(values):
            raise ValueError("preference values must be unique")
        return values

    @field_validator("preferred_countries")
    @classmethod
    def unique(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("preference values must be unique")
        return values


class ProfileSnapshot(CatalogModel):
    study_level: Literal["bachelor"]
    entry_year: int = Field(strict=True, ge=1, le=9999)
    residence_region: ScopeKey
    course_system: ScopeKey
    applicant_category: ScopeKey
    exam_province: ScopeKey
    pathway: ScopeKey
    subjects: tuple[Identifier, ...] = Field(max_length=8)
    assessments: GradeAssessments
    weekly_hours: DecimalText | None
    preferences: Preferences | None

    @field_validator("subjects")
    @classmethod
    def subjects_unique(cls, values):
        if len(set(values)) != len(values) or any(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:+-]*", v) is None for v in values):
            raise ValueError("subjects must be unique fixed identifiers")
        return values

    @field_validator("weekly_hours")
    @classmethod
    def hours(cls, value):
        if value is not None and Decimal(decimal_text(value)) > 40:
            raise ValueError("weekly hours exceed the supported capacity")
        return value

    @model_validator(mode="after")
    def units(self):
        for key, pair in self.assessments.items():
            unit = "band" if key.startswith("ielts_") else "points"
            if any(slot.status == "provided" and slot.unit != unit for slot in (pair.achieved, pair.predicted)):
                raise ValueError("assessment units must match the declared assessment")
        return self


class ConfirmedInput(CatalogModel):
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def confirmed_true(cls, value):
        if value is not True:
            raise ValueError("explicit boolean confirmation is required")
        return value


class CreateInput(ConfirmedInput):
    profile: ProfileSnapshot


class AppendInput(CreateInput):
    expected_current_version: PositiveVersion


class ProfilePolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    real_profiles_ready: bool = Field(default=False, strict=True)


class AdaptationData(CatalogModel):
    status: Literal["unknown", "unsupported"]
    reason: Literal["ADAPTER_NOT_IMPLEMENTED", "MISSING_SCOPE", "COURSE_NOT_SUPPORTED",
                    "PATHWAY_NOT_SUPPORTED", "APPLICANT_NOT_SUPPORTED"]


def adaptation(profile: ProfileSnapshot) -> AdaptationData:
    current = ProfileSnapshot.model_validate(profile)
    if current.course_system.status == "known" and current.course_system.value != "gaokao":
        return AdaptationData(status="unsupported", reason="COURSE_NOT_SUPPORTED")
    if current.pathway.status == "known" and current.pathway.value not in {"gaokao", "uk_undergraduate"}:
        return AdaptationData(status="unsupported", reason="PATHWAY_NOT_SUPPORTED")
    if current.applicant_category.status == "known" and current.applicant_category.value != "cn_mainland":
        return AdaptationData(status="unsupported", reason="APPLICANT_NOT_SUPPORTED")
    if any(key.status != "known" for key in (current.course_system, current.applicant_category,
                                            current.exam_province, current.pathway)):
        return AdaptationData(status="unknown", reason="MISSING_SCOPE")
    return AdaptationData(status="unknown", reason="ADAPTER_NOT_IMPLEMENTED")


class ProfileVersionData(CatalogModel):
    profile_id: UUID
    version_id: UUID
    version: PositiveVersion
    profile: ProfileSnapshot
    profile_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    confirmed_at: datetime = Field(strict=True)
    source: Literal["student_declared"]
    expires_at: datetime = Field(strict=True)
    is_synthetic: bool = Field(strict=True)
    adaptation: AdaptationData

    @field_validator("confirmed_at", "expires_at", mode="before")
    @classmethod
    def times(cls, value):
        return server_time(value)

    @model_validator(mode="after")
    def actual_snapshot(self):
        from ..api.v2.idempotency_canonical import canonical_request_hash
        from ..audit.retention import expires_after_months
        if (self.profile_sha256 != canonical_request_hash(self.profile.model_dump(mode="json"))
            or self.adaptation != adaptation(self.profile) or self.expires_at <= self.confirmed_at
            or self.expires_at > expires_after_months(self.confirmed_at)):
            raise ValueError("profile metadata must match its actual confirmed snapshot")
        return self


class ProfileWriteData(CatalogModel):
    version: ProfileVersionData
    replayed: bool = Field(strict=True)


class ProfileRef(CatalogModel):
    profile_id: UUID
    version_id: UUID
    version: PositiveVersion
    confirmed_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)
    is_synthetic: bool = Field(strict=True)

    @field_validator("confirmed_at", "expires_at", mode="before")
    @classmethod
    def times(cls, value):
        return server_time(value)


class ProfilePage(CatalogModel):
    items: tuple[ProfileRef, ...] = Field(max_length=20)
    next_cursor: str | None = Field(min_length=1, max_length=2048)


class ProfileContextData(CatalogModel):
    schema_version: Literal["v2.t23"]
    can_create: bool = Field(strict=True)
    can_read: bool = Field(strict=True)
    can_append: bool = Field(strict=True)
    reason: Literal["allowed", "processing_disabled"]
    is_synthetic: bool = Field(strict=True)


from ..api.v2.schemas import Meta


class ProfileMeta(Meta):
    model_config = CatalogModel.model_config
    profile_version_id: UUID | None
    profile_mode: Literal["synthetic", "real"] | None

    @model_validator(mode="after")
    def version_mode_pair(self):
        if (self.profile_version_id is None) != (self.profile_mode is None):
            raise ValueError("profile version and mode must occur together")
        return self


Item = TypeVar("Item")


class ProfileEnvelope(CatalogModel, Generic[Item]):
    data: Item
    meta: ProfileMeta

    @model_validator(mode="after")
    def actual_version(self):
        version = self.data.version if isinstance(self.data, ProfileWriteData) else self.data
        if isinstance(version, ProfileVersionData):
            if (self.meta.profile_version_id != version.version_id or self.meta.profile_mode != (
                "synthetic" if version.is_synthetic else "real")):
                raise ValueError("response metadata must reference the actual confirmed version")
        elif self.meta.profile_version_id is not None:
            raise ValueError("non-version responses cannot claim a profile version")
        return self
