"""Closed public projections; no private provenance identifiers or storage URLs."""

import re
from datetime import date, datetime, time
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.date_schemas import ConversionStatus, EventType, Precision, _utc_candidate
from ..admissions_catalog.schemas import CatalogModel, Identifier, PositiveVersion, ScopeKey, _identifier, _namespace
from ..api.v2.schemas import PageInfo
from ..evidence.schemas import EvidenceLocator, EvidenceScope, Language, _uuid
from ..facts.schemas import ClaimKind, Period, StatisticsBasis, UnitCode, _bounded_context
from ..ingestion.schemas import MissingReason


DEMO_BANNER = "DEMO：合成测试资料，不是真实招生依据"


class PublicCatalogError(ValueError):
    """Fixed public errors never include input, SQL, source URLs or paths."""

    def __init__(self, status_code=503, code=None):
        codes = {422: "VALIDATION_ERROR", 404: "NOT_FOUND", 409: "CONFLICT", 503: "SERVICE_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes:
            status_code, code = 503, None
        if code is not None and code != codes[status_code] and not (status_code == 422 and code == "INVALID_CURSOR"):
            status_code, code = 503, None
        self.status_code = status_code
        self.code = code or codes[status_code]
        super().__init__(self.code)


class PublicCatalogPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    real_catalog_ready: bool = Field(default=False, strict=True)
    allow_test_fixture_read: bool = Field(default=False, strict=True)


class PublicOfferingQuery(CatalogModel):
    entry_year: int = Field(strict=True, ge=1, le=9999)
    country: str | None = Field(default=None, strict=True, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    study_level: Literal["undergraduate"] | None = None
    province: str | None = Field(default=None, strict=True, min_length=1, max_length=106)
    pathway: str | None = Field(default=None, strict=True, min_length=1, max_length=106)
    course_system: str | None = Field(default=None, strict=True, min_length=1, max_length=106)
    applicant_category: str | None = Field(default=None, strict=True, min_length=1, max_length=106)
    release_id: UUID | None = None
    limit: int = Field(default=20, strict=True, ge=1, le=100)
    cursor: str | None = Field(default=None, strict=True, min_length=1, max_length=512)

    @field_validator("country")
    @classmethod
    def exact_country(cls, value):
        if value is not None and re.fullmatch(r"[A-Z]{2}", value) is None:
            raise ValueError("an exact uppercase country code is required")
        return value

    @field_validator("province", "pathway", "course_system", "applicant_category")
    @classmethod
    def explicit_scope_key(cls, value):
        if value is not None:
            scope = ScopeKey.from_canonical_key(value)
            if scope.status == "unknown":
                raise ValueError("unknown scope is not a public query filter")
        return value

    @field_validator("release_id", mode="before")
    @classmethod
    def canonical_release_id(cls, value):
        return _uuid(value) if value is not None else None

    @field_validator("cursor")
    @classmethod
    def nonblank_cursor(cls, value):
        if value is not None and (not value.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in value)):
            raise ValueError("a bounded opaque ASCII cursor is required")
        return value


class PublicConfigData(CatalogModel):
    api_version: Literal["v2"]
    schema_version: Literal["v2.t20"]
    contract_stage: Literal["public_catalog"]
    app_environment: Literal["development", "test", "production"]
    query_role: Literal["demo_only", "published_readonly"]
    data_mode: Literal["demo", "verified"]
    model_mode: Literal["disabled", "mock"]
    live_available: Literal[False]
    business_available: bool = Field(strict=True)
    allow_test_fixture_read: bool = Field(strict=True)
    demo_banner: Literal["DEMO：合成测试资料，不是真实招生依据"] | None
    supported_scope: list[str] = Field(max_length=0)
    supported_province: None
    entry_year: None

    @model_validator(mode="after")
    def explicit_demo_boundary(self):
        if self.allow_test_fixture_read:
            if self.app_environment != "test" or self.data_mode != "demo" or self.demo_banner != DEMO_BANNER:
                raise ValueError("synthetic public reads require the explicit test/demo boundary")
        elif self.demo_banner is not None:
            raise ValueError("a DEMO banner requires the explicit synthetic reader")
        return self


class PublicDateData(CatalogModel):
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

    @field_validator("local_date", mode="before")
    @classmethod
    def native_date(cls, value):
        if value is not None and type(value) is not date:
            raise ValueError("a native calendar date is required")
        return value

    @field_validator("local_time", mode="before")
    @classmethod
    def native_time(cls, value):
        if value is not None and (type(value) is not time or value.tzinfo is not None or value.fold or value.microsecond):
            raise ValueError("a native whole-second local time is required")
        return value

    @field_validator("calculated_utc_instant", mode="before")
    @classmethod
    def candidate_utc(cls, value):
        return _utc_candidate(value)

    @model_validator(mode="after")
    def finite_date_projection(self):
        if (self.conversion_status == "unique") != (self.calculated_utc_instant is not None):
            raise ValueError("only a unique conversion has a UTC candidate")
        if self.precision == "unknown" and any(v is not None for v in (self.local_date, self.local_time, self.timezone)):
            raise ValueError("unknown precision has no inferred local components")
        if self.precision == "date" and (self.local_date is None or self.local_time is not None):
            raise ValueError("date precision has no inferred local time")
        if self.precision in {"minute", "second"} and (self.local_date is None or self.local_time is None):
            raise ValueError("time precision requires explicit local components")
        if self.precision == "minute" and self.local_time is not None and self.local_time.second:
            raise ValueError("minute precision cannot contain seconds")
        return self


class PublicFactData(CatalogModel):
    fact_type: Literal["requirement", "score", "fee", "material", "date", "statistic"]
    field_key: Identifier
    value_kind: Literal["text", "decimal"]
    value_text: str | None = Field(strict=True, min_length=1, max_length=4096)
    normalized_value: str | None = Field(strict=True, min_length=1, max_length=4096)
    unit: str | None = Field(strict=True, min_length=1, max_length=4096)
    missing_reason: MissingReason | None
    footnote_state: Literal["present", "none", "unknown"]
    footnote_text: str | None = Field(strict=True, min_length=1, max_length=4096)
    claim_kind: ClaimKind
    unit_code: UnitCode
    period: Period
    statistics_basis: StatisticsBasis
    statistic_population: str | None = Field(strict=True, min_length=1, max_length=512)
    statistic_denominator: str | None = Field(strict=True, min_length=1, max_length=512)
    cohort_year: int | None = Field(strict=True, ge=1, le=9999)
    survey_period: str | None = Field(strict=True, min_length=1, max_length=100)
    evidence_id: UUID | None
    date_resolution: PublicDateData | None

    @field_validator("field_key")
    @classmethod
    def explicit_field_key(cls, value):
        return _identifier(value)

    @field_validator("evidence_id", mode="before")
    @classmethod
    def canonical_evidence_id(cls, value):
        return _uuid(value) if value is not None else None

    @field_validator("value_text", "normalized_value", "unit", "footnote_text", "statistic_population", "statistic_denominator", "survey_period")
    @classmethod
    def bounded_text(cls, value, info):
        if value is None:
            return None
        maximum = 512 if info.field_name in {"statistic_population", "statistic_denominator"} else 100 if info.field_name == "survey_period" else 4096
        return _bounded_context(value, maximum)

    @model_validator(mode="after")
    def missing_and_footnote_projection(self):
        if (self.value_text is None) != (self.missing_reason is not None):
            raise ValueError("missing values require an explicit missing reason")
        if self.value_text is None and self.normalized_value is not None:
            raise ValueError("missing values cannot acquire a normalized value")
        if (self.footnote_state == "present") != (self.footnote_text is not None):
            raise ValueError("present footnotes require their original text")
        return self


class PublicOfferingData(CatalogModel):
    release_id: UUID
    release_version: Literal[1]
    requirements_version: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    content_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ruleset_version: None
    id: UUID
    version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    is_synthetic: bool = Field(strict=True)
    institution_id: UUID
    institution_name: str = Field(strict=True, min_length=1, max_length=200)
    program_id: UUID
    program_name: str = Field(strict=True, min_length=1, max_length=200)
    scope: EvidenceScope
    facts: tuple[PublicFactData, ...] = Field(min_length=1, max_length=50)

    @field_validator("release_id", "id", "institution_id", "program_id", mode="before")
    @classmethod
    def canonical_ids(cls, value):
        return _uuid(value)

    @field_validator("release_version", mode="before")
    @classmethod
    def initial_release_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("the fixed release version is required")
        return value

    @model_validator(mode="after")
    def explicit_scope_and_names(self):
        _namespace(self.institution_name, self.is_synthetic)
        _namespace(self.program_name, self.is_synthetic)
        if (self.scope.entry_year != self.entry_year or self.scope.institution_id != self.institution_id
                or self.scope.program_id != self.program_id):
            raise ValueError("public labels and scope must describe the same offering")
        return self


class CoverageData(CatalogModel):
    status: Literal["no_published_records", "partial"]
    returned_count: int = Field(strict=True, ge=0, le=100)
    expected_total: None
    coverage_ratio: None

    @model_validator(mode="after")
    def no_completeness_inference(self):
        if self.status == "no_published_records" and self.returned_count != 0:
            raise ValueError("coverage describes only the returned published records")
        return self


class PublicOfferingsData(CatalogModel):
    items: tuple[PublicOfferingData, ...] = Field(max_length=100)
    page: PageInfo
    coverage: CoverageData

    @model_validator(mode="after")
    def bounded_page_projection(self):
        if len(self.items) > self.page.limit or self.coverage.returned_count != len(self.items):
            raise ValueError("coverage and page bounds must match the returned items")
        identities = [(item.release_id, item.id, item.version) for item in self.items]
        if len(set(identities)) != len(identities):
            raise ValueError("public offering pages must be distinct")
        return self


class PublicEvidenceData(CatalogModel):
    evidence_id: UUID
    release_id: UUID
    release_version: Literal[1]
    requirements_version: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    is_synthetic: bool = Field(strict=True)
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    language: Language
    quote: str = Field(strict=True, min_length=1, max_length=4096)
    document_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    snippet_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    locator: EvidenceLocator
    scope: EvidenceScope
    publisher: str = Field(strict=True, min_length=1, max_length=200)
    authority_claim: Literal["unclassified", "claimed_official", "not_official"]

    @field_validator("evidence_id", "release_id", "offering_id", mode="before")
    @classmethod
    def canonical_ids(cls, value):
        return _uuid(value)

    @field_validator("release_version", mode="before")
    @classmethod
    def initial_release_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("the fixed release version is required")
        return value

    @model_validator(mode="after")
    def exact_public_quote(self):
        try:
            raw = self.quote.encode("utf-8")
        except UnicodeError:
            raise ValueError("a bounded UTF-8 quote is required") from None
        if (len(raw) > 4096 or len(raw) != self.locator.byte_end - self.locator.byte_start
                or sha256(raw).hexdigest() != self.snippet_sha256 or self.entry_year != self.scope.entry_year):
            raise ValueError("public quote, locator, hash and offering year must agree")
        _namespace(self.publisher, self.is_synthetic)
        return self
