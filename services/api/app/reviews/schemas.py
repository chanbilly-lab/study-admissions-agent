"""Explicit human checks and bounded historical decisions, without release."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel, MAX_VERSION, PositiveVersion
from ..evidence.schemas import _utc
from ..ingestion.schemas import _uuid


REVIEWS_HEAD = "0001_reviews_t18"
CHECK_FIELDS = (
    "original_value", "claim_kind", "unit", "period", "scope", "evidence_location",
    "missingness", "footnote", "statistics_context", "date_context",
)
CheckField = Literal["original_value", "claim_kind", "unit", "period", "scope", "evidence_location",
    "missingness", "footnote", "statistics_context", "date_context"]
CheckStatus = Literal["accepted", "rejected", "not_applicable"]
ReturnReason = Literal["INVALID_VALUE", "MISSING_EVIDENCE", "SCOPE_MISMATCH", "UNIT_MISMATCH",
    "PERIOD_UNCLEAR", "MISSING_CONTEXT", "FOOTNOTE_UNRESOLVED", "SOURCE_UNAVAILABLE",
    "CONFLICT_UNRESOLVED", "UNSUPPORTED_LITERAL"]
ConflictReason = Literal["SELECTED_SUPPORTED", "INCORRECT_VALUE", "WRONG_CONTEXT", "DUPLICATE_OR_EQUIVALENT"]


class ReviewsError(ValueError):
    """Safe fixed errors; no original snippets, credentials or SQL details."""

    def __init__(self, status_code=503, code=None):
        codes = {422: "INVALID_REVIEW_INPUT", 404: "REVIEW_NOT_FOUND",
                 409: "REVIEW_CONFLICT", 503: "REVIEW_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


class ReviewCheck(CatalogModel):
    field: CheckField
    status: CheckStatus


class ConflictResolution(CatalogModel):
    fact_id: UUID
    reason_code: ConflictReason

    @field_validator("fact_id", mode="before")
    @classmethod
    def canonical_fact_reference(cls, value):
        return _uuid(value)


class _ReviewAction(CatalogModel):
    fact_id: UUID
    action: Literal["approve", "return"]
    checks: tuple[ReviewCheck, ...] = Field(min_length=10, max_length=10)
    conflict_resolutions: tuple[ConflictResolution, ...] = Field(max_length=200)
    return_reason: ReturnReason | None

    @field_validator("fact_id", mode="before")
    @classmethod
    def canonical_fact_reference(cls, value):
        return _uuid(value)

    @model_validator(mode="after")
    def explicit_checks_and_reasons(self):
        if set(check.field for check in self.checks) != set(CHECK_FIELDS):
            raise ValueError("every fixed review check must occur exactly once")
        if (self.action == "return") != (self.return_reason is not None):
            raise ValueError("only a returned decision contains an explicit finite reason")
        resolutions = tuple(item.fact_id for item in self.conflict_resolutions)
        if len(set(resolutions)) != len(resolutions) or self.fact_id in resolutions:
            raise ValueError("conflict resolutions require distinct other candidates")
        if self.action == "return" and resolutions:
            raise ValueError("returning a candidate does not resolve or select conflicting candidates")
        if self.action == "approve":
            values = {check.field: check.status for check in self.checks}
            if any(values[field] != "accepted" for field in CHECK_FIELDS[:8]) or "rejected" in values.values():
                raise ValueError("approval requires explicit accepted critical checks")
        return self


class ReviewRequest(_ReviewAction):
    expected_fact_version: Literal[1]
    expected_case_revision: int = Field(strict=True, ge=0, le=MAX_VERSION)

    @field_validator("expected_fact_version", mode="before")
    @classmethod
    def strict_fact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("a strict initial candidate version is required")
        return value


class ReviewPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    real_reviews_ready: bool = Field(default=False, strict=True)


class ReviewDecisionData(_ReviewAction):
    decision_id: UUID
    case_id: UUID
    case_revision: PositiveVersion
    reviewer_user_id: UUID
    created_at: datetime = Field(strict=True)
    is_synthetic: bool = Field(strict=True)
    current_approved: bool = Field(strict=True)

    @field_validator("decision_id", "case_id", "reviewer_user_id", mode="before")
    @classmethod
    def canonical_server_reference(cls, value):
        return _uuid(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def native_server_timestamp(cls, value):
        return _utc(value)

    @model_validator(mode="after")
    def no_returned_approval(self):
        if self.current_approved and self.action != "approve":
            raise ValueError("a returned decision cannot be a current approval")
        return self


class ReviewCaseData(CatalogModel):
    case_id: UUID | None
    logical_key_hash: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    case_revision: int = Field(strict=True, ge=0, le=MAX_VERSION)
    chosen_fact_id: UUID | None
    current_decision_id: UUID | None
    current_approved: bool = Field(strict=True)
    is_synthetic: bool = Field(strict=True)

    @field_validator("case_id", "chosen_fact_id", "current_decision_id", mode="before")
    @classmethod
    def canonical_nullable_reference(cls, value):
        return _uuid(value) if value is not None else None

    @model_validator(mode="after")
    def coherent_case_projection(self):
        if self.case_id is None:
            if self.case_revision != 0 or self.chosen_fact_id is not None or self.current_decision_id is not None or self.current_approved:
                raise ValueError("a missing case contains no decision or selection")
        elif self.case_revision == 0 or self.current_decision_id is None:
            raise ValueError("a recorded case contains a positive decision revision")
        if self.current_approved and (self.chosen_fact_id is None or self.current_decision_id is None):
            raise ValueError("a current approval requires an explicit selected candidate and decision")
        return self
