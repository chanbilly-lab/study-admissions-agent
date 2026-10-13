"""T28 private HTTP contracts; rule sources remain server-only ports."""

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel, ScopeKey, PositiveVersion
from ..profiles.schemas import ProfileMeta
from .adapters.schemas import Hash, Stage, TargetReference
from .assessment_engine import EligibilityEngineResult
from .expression import explicit_instant
from ..evidence.schemas import _uuid

ASSESSMENTS_HEAD = "0001_assessments_t28"
ENGINE_VERSION = "T28_v1"
MAX_ASSESSMENT_REQUEST_BYTES = 16384
CurrentValidity = Literal["current", "withdrawn", "replaced", "needs_review", "unavailable"]


class AssessmentError(ValueError):
    def __init__(self, status_code=503):
        codes = {422: "INVALID_ASSESSMENT_INPUT", 404: "ASSESSMENT_NOT_FOUND",
                 409: "ASSESSMENT_CONFLICT", 503: "ASSESSMENT_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes:
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


class AssessmentPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_bindings: bool = Field(default=False, strict=True)
    real_assessments_ready: Literal[False] = False

    @field_validator("real_assessments_ready", mode="before")
    @classmethod
    def formal_closed(cls, value):
        if value is not False:
            raise ValueError("formal rules are unavailable")
        return value


class ReplayRequest(CatalogModel):
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit confirmation is required")
        return value


class AssessmentRequest(ReplayRequest):
    profile_id: UUID
    profile_version_id: UUID
    target: TargetReference
    release_id: UUID
    stage: Stage
    intake: ScopeKey | None
    application_cycle: ScopeKey | None
    channel: ScopeKey | None
    exam_system: ScopeKey | None
    subject_scope: ScopeKey | None
    batch_group: ScopeKey | None

    _ids = field_validator("profile_id", "profile_version_id", "release_id", mode="before")(_uuid)


class UnknownDimension(CatalogModel):
    status: Literal["unknown"]
    reason: Literal["DATA_UNAVAILABLE"]


class RuleReference(CatalogModel):
    bundle_id: UUID
    expression_sha256: Hash
    fact_ids: tuple[UUID, ...] = Field(min_length=1, max_length=32)
    evidence_ids: tuple[UUID, ...] = Field(min_length=1, max_length=32)


class AssessmentContextData(CatalogModel):
    schema_version: Literal["v2.t28"]
    can_evaluate: bool = Field(strict=True)
    can_read: bool = Field(strict=True)
    can_replay: bool = Field(strict=True)
    reason: Literal["ready", "processing_disabled", "ruleset_unavailable"]
    is_synthetic: bool = Field(strict=True)


class AssessmentData(CatalogModel):
    assessment_id: UUID
    version: Literal[1]
    profile_id: UUID
    profile_version_id: UUID
    profile_version: PositiveVersion
    profile_sha256: Hash
    target: TargetReference
    release_id: UUID
    requirements_version: Hash
    ruleset_version: Hash | None
    stage: Stage
    assessment_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)
    engine_version: Literal["T28_v1"]
    binding_mode: Literal["unavailable", "test_fixture"]
    profile_is_synthetic: bool = Field(strict=True)
    catalogue_is_synthetic: bool = Field(strict=True)
    eligibility: EligibilityEngineResult
    competition_context: UnknownDimension
    preference_fit: UnknownDimension
    data_quality: UnknownDimension
    rule_refs: tuple[RuleReference, ...] = Field(max_length=1)
    result_sha256: Hash
    current_validity: CurrentValidity
    replayed: bool = Field(strict=True)

    _time = field_validator("assessment_at", "expires_at", mode="before")(explicit_instant)

    @field_validator("version", mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("an exact initial result is required")
        return value

    @model_validator(mode="after")
    def exact_binding(self):
        if self.expires_at <= self.assessment_at:
            raise ValueError("result retention must be bounded")
        if self.binding_mode == "test_fixture":
            if not self.profile_is_synthetic or not self.catalogue_is_synthetic or self.ruleset_version is None or len(self.rule_refs) != 1:
                raise ValueError("test rules require explicit synthetic binding")
        elif (self.ruleset_version is not None or self.rule_refs or self.eligibility.status != "unknown"
              or self.eligibility.evaluation is not None
              or self.eligibility.reason not in {"RULESET_UNAVAILABLE", "BINDING_UNAVAILABLE", "SCOPE_UNAVAILABLE"}):
            raise ValueError("unavailable rules cannot yield eligibility")
        return self


# This local metadata preserves the original foundation contract. Assessment
# envelopes have their own correspondence guard instead of a profile DTO guard.
AssessmentMeta = ProfileMeta
Item = TypeVar("Item")


class AssessmentEnvelope(CatalogModel, Generic[Item]):
    data: Item
    meta: AssessmentMeta

    @model_validator(mode="after")
    def actual_assessment(self):
        if isinstance(self.data, AssessmentData):
            expected_mode = "synthetic" if self.data.profile_is_synthetic else "real"
            if (self.meta.profile_version_id != self.data.profile_version_id
                or self.meta.profile_mode != expected_mode):
                raise ValueError("assessment metadata must match its actual profile snapshot")
        elif self.meta.profile_version_id is not None or self.meta.profile_mode is not None:
            raise ValueError("context cannot claim a private profile snapshot")
        return self
