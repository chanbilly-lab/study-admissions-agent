"""Closed administration DTOs; no implicit review or publication permission."""

import re
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from ...admissions_catalog.schemas import CatalogModel, PositiveVersion
from ...evidence.schemas import (DocumentCreate, EvidenceScope, SnippetCreate, SnippetData,
                                VersionCreate)
from ...facts.schemas import Classification, FactCreate, TypedCandidate
from ...ingestion.schemas import ParsedRow
from ...releases.schemas import PublishRequest, ReleaseKind, ReleaseState, WithdrawalReason
from ...reviews.schemas import ReviewCaseData, ReviewRequest
from ..http.schemas import ConfirmedInput


class AdminDocumentInput(DocumentCreate, ConfirmedInput):
    pass


class AdminVersionInput(VersionCreate, ConfirmedInput):
    pass


class AdminSnippetInput(SnippetCreate, ConfirmedInput):
    pass


class AdminFactInput(FactCreate, ConfirmedInput):
    pass


class AdminReviewInput(ReviewRequest, ConfirmedInput):
    pass


class AdminPublishInput(PublishRequest, ConfirmedInput):
    @field_validator("valid_from", "valid_until", mode="before")
    @classmethod
    def explicit_http_instant(cls, value):
        if type(value) is datetime:
            return value
        if type(value) is not str or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})", value
        ) is None:
            raise ValueError("an explicit RFC3339 offset instant is required")
        try:
            if value.endswith("-00:00"):
                raise ValueError
            if not value.endswith("Z") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
                raise ValueError
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError
            return parsed.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise ValueError("an explicit RFC3339 offset instant is required") from None


class AdminWithdrawalInput(ConfirmedInput):
    expected_state_revision: PositiveVersion
    reason_code: WithdrawalReason


class ReviewContextData(CatalogModel):
    schema_version: Literal["v2.t22"]
    can_prepare: bool = Field(strict=True)
    can_review: bool = Field(strict=True)
    can_publish: bool = Field(strict=True)
    can_withdraw: bool = Field(strict=True)
    is_synthetic: bool = Field(strict=True)


class ImportRowData(CatalogModel):
    row_id: UUID
    row: ParsedRow


class ImportRowsData(CatalogModel):
    import_id: UUID
    dataset_id: UUID
    source_id: UUID
    source_version: PositiveVersion
    file_id: UUID
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    format: Literal["json", "csv"]
    is_synthetic: bool = Field(strict=True)
    total_rows: int = Field(strict=True, ge=1, le=200)
    rows: tuple[ImportRowData, ...] = Field(max_length=20)
    next_cursor: str | None


class ReviewCandidateRef(CatalogModel):
    fact_id: UUID
    version: Literal[1]
    dataset_id: UUID
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    state: Literal["draft", "review_required", "conflicted"]
    is_synthetic: bool = Field(strict=True)
    created_at: datetime


class ReviewCandidatesData(CatalogModel):
    dataset_id: UUID
    entry_year: int = Field(strict=True, ge=1, le=9999)
    dataset_revision: PositiveVersion
    items: tuple[ReviewCandidateRef, ...] = Field(max_length=100)
    next_cursor: str | None


ReviewGap = Literal["MISSING_EVIDENCE", "INCOMPLETE_SCOPE", "UNKNOWN_FOOTNOTE", "MISSING_VALUE",
                    "INCOMPLETE_STATISTICS", "UNRESOLVED_DATE", "UNRESOLVED_LOCATOR", "BASE_DRAFT",
                    "CURRENT_CONFLICTS", "SELF_REVIEW_FORBIDDEN"]


class ReviewConflictData(CatalogModel):
    fact_id: UUID
    version: Literal[1]
    value_kind: Literal["text", "decimal"]
    value_text: str | None
    normalized_value: str | None
    unit_text: str | None
    footnote_state: Literal["present", "none", "unknown"]
    footnote_text: str | None
    classification: Classification
    evidence_id: UUID | None
    state: Literal["draft", "review_required", "conflicted"]


class ReviewDetailData(CatalogModel):
    fact: TypedCandidate
    case: ReviewCaseData
    evidence: SnippetData | None
    scope: EvidenceScope
    gaps: tuple[ReviewGap, ...] = Field(max_length=10)
    conflicts: tuple[ReviewConflictData, ...] = Field(max_length=200)


class ReleaseHeadData(CatalogModel):
    release_id: UUID
    version: Literal[1]
    state: ReleaseState
    state_revision: PositiveVersion
    kind: ReleaseKind
    is_synthetic: bool = Field(strict=True)
    valid_from: datetime
    valid_until: datetime
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requirements_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    member_count: int = Field(strict=True, ge=1, le=50)
    replaces_release_id: UUID | None
    replaced_by_release_id: UUID | None


class CurrentReleaseData(CatalogModel):
    dataset_id: UUID
    entry_year: int = Field(strict=True, ge=1, le=9999)
    dataset_revision: PositiveVersion
    release: ReleaseHeadData | None


class PublishPrecheckData(CatalogModel):
    status: Literal["precheck_passed"]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_revision: PositiveVersion
    member_count: int = Field(strict=True, ge=1, le=50)
    checked_at: datetime
    is_synthetic: bool = Field(strict=True)
