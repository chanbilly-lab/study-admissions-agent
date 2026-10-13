"""Frozen BATCH-ZJ-2026-CUTOFF-01 imports and local-only read protocol."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ...admissions_catalog.schemas import CatalogModel, Identifier
from ...api.reference_contract import StatisticalQuery
from ...api.v2.schemas import PageInfo
from ..candidates import Text

SOURCE_URL = "https://www.zjzs.net/art/2026/6/25/art_155_12467.html"
SOURCE_TITLE = "2026年浙江省普通高校招生各类别分数线"
REVIEW_REF = "USER_ZJ2026_ORDINARY_3"
Hash = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
LineKind = Literal["segment_first", "segment_second", "special_category"]
KNOWN_VALUES = {"segment_first": 494, "segment_second": 266, "special_category": 594}


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware UTC timestamp is required")
    return value.astimezone(timezone.utc)


class SourceInput(CatalogModel):
    publisher: Literal["浙江省教育考试院"]
    url: Literal["https://www.zjzs.net/art/2026/6/25/art_155_12467.html"]
    title: Literal["2026年浙江省普通高校招生各类别分数线"]
    published_label: Literal["2026-06-25 13:22"]
    published_timezone: None = None
    retrieved_at: datetime
    original_sha256: Hash
    body_bytes: int = Field(strict=True, ge=1, le=2 * 1024 * 1024)
    authority_status: Literal["official_site_checked"] = "official_site_checked"
    public_reuse_permission: Literal["unknown"] = "unknown"

    @field_validator("retrieved_at")
    @classmethod
    def capture_utc(cls, value):
        return utc(value)


class CutoffItem(CatalogModel):
    record_key: Identifier
    exam_year: Literal[2026] = 2026
    region_key: Literal["cn_region_11"] = "cn_region_11"
    subject_category: Literal["普通类"] = "普通类"
    line_kind: LineKind
    original_label: Text
    value: int = Field(strict=True, ge=0, le=10000)
    unit: Literal["points"] = "points"
    is_synthetic: Literal[False] = False
    max_score: None = None
    bonus_definition: None = None
    max_score_missing_reason: Literal["not_stated_in_source"] = "not_stated_in_source"
    bonus_missing_reason: Literal["not_stated_in_source"] = "not_stated_in_source"
    excerpt: str = Field(strict=True, min_length=1, max_length=800)
    locator: str = Field(strict=True, min_length=1, max_length=500)

    @field_validator("exam_year", mode="before")
    @classmethod
    def exact_year(cls, value):
        if type(value) is not int or value != 2026:
            raise ValueError("The batch only contains the explicit 2026 examination year")
        return value

    @field_validator("is_synthetic", mode="before")
    @classmethod
    def real_marker(cls, value):
        if value is not False:
            raise ValueError("Only real reference facts are allowed")
        return value

    @field_validator("excerpt", "locator")
    @classmethod
    def bounded_plain_text(cls, value):
        if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("A bounded single-line evidence description is required")
        return value

    @model_validator(mode="after")
    def exact_reviewed_values(self):
        if self.record_key.upper().startswith("DEMO_") or self.value != KNOWN_VALUES[self.line_kind]:
            raise ValueError("Only the three explicitly reviewed real facts belong to this batch")
        label = {"segment_first": "第一段", "segment_second": "第二段",
                 "special_category": "特殊类型招生控制线"}[self.line_kind]
        if self.original_label != label:
            raise ValueError("The original line name cannot be reclassified")
        return self


class ImportManifest(CatalogModel):
    schema_version: Literal["reference.cutoffs.import.1"]
    batch_key: Literal["ZJ2026_ORDINARY_CUTOFF_3"]
    source: SourceInput
    records: tuple[CutoffItem, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def exact_batch(self):
        if {row.line_kind for row in self.records} != set(KNOWN_VALUES):
            raise ValueError("All three distinct reviewed line kinds are required")
        if len({row.record_key for row in self.records}) != 3:
            raise ValueError("Distinct real record keys are required")
        return self


class ReviewProof(CatalogModel):
    schema_version: Literal["reference.cutoffs.review.1"]
    batch_id: UUID
    manifest_sha256: Hash
    original_sha256: Hash
    review_ref: Literal["USER_ZJ2026_ORDINARY_3"]
    decision: Literal["approve_local"]
    confirmed_at: datetime

    @field_validator("confirmed_at")
    @classmethod
    def confirmation_utc(cls, value):
        return utc(value)


class LocalStatisticalQuery(StatisticalQuery):
    limit: int = Field(default=20, ge=3, le=100)


class LocalBatch(CatalogModel):
    batch_id: UUID
    manifest_sha256: Hash
    state: Literal["approved_local"] = "approved_local"
    review_ref: Literal["USER_ZJ2026_ORDINARY_3"]
    approved_at: datetime

    @field_validator("approved_at")
    @classmethod
    def approved_utc(cls, value):
        return utc(value)


class LocalCutoffData(CatalogModel):
    schema_version: Literal["reference.cutoffs.local.1"] = "reference.cutoffs.local.1"
    resource: Literal["province_cutoffs"] = "province_cutoffs"
    filters: dict[str, str | int | None]
    items: tuple[CutoffItem, ...] = Field(default=(), max_length=3)
    page: PageInfo
    release_id: None = None
    expected_total: None = None
    coverage_ratio: None = None
    business_available: Literal[False] = False
    local_reference_only: Literal[True] = True
    reference_available: bool = Field(strict=True)
    missing_reason: Literal["not_collected", "not_applicable", "scope_not_supported", "withdrawn", "review_pending"] | None
    source: SourceInput | None = None
    batch: LocalBatch | None = None

    @model_validator(mode="after")
    def availability(self):
        if self.reference_available:
            if (self.missing_reason is not None or self.source is None or self.batch is None
                    or len(self.items) != 3 or {row.line_kind for row in self.items} != set(KNOWN_VALUES)
                    or len({row.record_key for row in self.items}) != 3):
                raise ValueError("Only a reviewed batch can carry real reference items")
        elif self.missing_reason is None or self.items or self.source is not None or self.batch is not None:
            raise ValueError("Unavailable reference data cannot reveal records or evidence")
        if self.page.has_more or self.page.next_cursor is not None:
            raise ValueError("This finite batch never issues cursors")
        if len(self.items) > self.page.limit:
            raise ValueError("Reference items cannot exceed the requested limit")
        return self
