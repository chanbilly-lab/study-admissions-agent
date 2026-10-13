"""Immutable derived evidence contracts; provenance does not imply approval."""

from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import (
    CatalogModel, Identifier, MAX_VERSION, PositiveVersion, ScopeKey, _identifier, _namespace,
)


MAX_ORIGINAL_BYTES = 1_048_576
MAX_SNIPPET_BYTES = 4_096
EVIDENCE_HEAD = "0001_evidence_t16"
Language = Literal["zh-Hans", "zh-Hant", "en", "und"]
OriginalMediaType = Literal["application/json", "text/csv"]


class EvidenceError(ValueError):
    def __init__(self, status_code=503, code=None):
        codes = {422: "INVALID_EVIDENCE_INPUT", 404: "EVIDENCE_NOT_FOUND",
                 409: "EVIDENCE_CONFLICT", 503: "EVIDENCE_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


def _uuid(value):
    if type(value) is UUID:
        return value
    if type(value) is not str:
        raise ValueError("a canonical UUID is required")
    try:
        result = UUID(value)
    except ValueError:
        raise ValueError("a canonical UUID is required") from None
    if str(result) != value:
        raise ValueError("a canonical UUID is required")
    return result


def _utc(value):
    try:
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None or value.fold:
            raise ValueError()
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError("a native, unambiguous aware server timestamp is required") from None


class EvidencePolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    real_evidence_ready: bool = Field(default=False, strict=True)


class DocumentCreate(CatalogModel):
    dataset_id: UUID
    source_id: UUID
    source_version: PositiveVersion
    document_reference: Identifier
    language: Language

    @field_validator("dataset_id", "source_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value)

    @field_validator("document_reference")
    @classmethod
    def exact_reference(cls, value):
        return _identifier(value)

    def validate_namespace(self, is_synthetic: bool) -> None:
        current = type(self).model_validate(self)
        if type(is_synthetic) is not bool:
            raise ValueError("a strict synthetic marker is required")
        _namespace(current.document_reference, is_synthetic)


class DocumentData(DocumentCreate):
    id: UUID
    is_synthetic: bool = Field(strict=True)
    current_version: int = Field(strict=True, ge=0, le=MAX_VERSION)
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def canonical_document_id(cls, value):
        return _uuid(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def server_time(cls, value):
        return _utc(value)

    @model_validator(mode="after")
    def output_namespace(self):
        _namespace(self.document_reference, self.is_synthetic)
        return self


class VersionCreate(CatalogModel):
    document_id: UUID
    expected_current_version: int = Field(strict=True, ge=0, le=MAX_VERSION)
    file_id: UUID
    file_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

    @field_validator("document_id", "file_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value)


class VersionData(CatalogModel):
    id: UUID
    document_id: UUID
    version: PositiveVersion
    document_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(strict=True, ge=1, le=MAX_ORIGINAL_BYTES)
    media_type: OriginalMediaType
    is_synthetic: bool = Field(strict=True)
    created_at: datetime

    @field_validator("id", "document_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def server_time(cls, value):
        return _utc(value)


class SnippetCreate(CatalogModel):
    document_id: UUID
    document_version: PositiveVersion
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    byte_start: int = Field(strict=True, ge=0, lt=MAX_ORIGINAL_BYTES)
    byte_end: int = Field(strict=True, ge=1, le=MAX_ORIGINAL_BYTES)

    @field_validator("document_id", "offering_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value)

    @model_validator(mode="after")
    def bounded_span(self):
        if not 0 < self.byte_end - self.byte_start <= MAX_SNIPPET_BYTES:
            raise ValueError("a nonempty bounded half-open byte span is required")
        return self


class EvidenceLocator(CatalogModel):
    byte_start: int = Field(strict=True, ge=0, lt=MAX_ORIGINAL_BYTES)
    byte_end: int = Field(strict=True, ge=1, le=MAX_ORIGINAL_BYTES)
    line_start: int = Field(strict=True, ge=1, le=MAX_ORIGINAL_BYTES + 1)
    line_end: int = Field(strict=True, ge=1, le=MAX_ORIGINAL_BYTES + 1)
    page: None
    section: None
    location_kind: Literal["utf8_byte_lines"]

    @model_validator(mode="after")
    def nonempty_span_and_lines(self):
        span_bytes = self.byte_end - self.byte_start
        if not 0 < span_bytes <= MAX_SNIPPET_BYTES or self.line_start > self.line_end:
            raise ValueError("a nonempty bounded byte span and ordered physical lines are required")
        if (self.line_start > self.byte_start + 1 or self.line_end > self.byte_end
                or self.line_end - self.line_start > span_bytes - 1):
            raise ValueError("physical lines must be reachable within the byte span")
        return self


class EvidenceScope(CatalogModel):
    dataset_id: UUID
    program_id: UUID
    institution_id: UUID
    country: str = Field(strict=True, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    study_level: Literal["undergraduate"]
    entry_year: int = Field(strict=True, ge=1, le=9999)
    degree: ScopeKey
    course: ScopeKey
    campus: ScopeKey
    teaching_language: ScopeKey
    progression_pathway: ScopeKey
    intake: ScopeKey
    application_cycle: ScopeKey
    channel: ScopeKey
    course_system: ScopeKey
    pathway: ScopeKey
    applicant_category: ScopeKey
    province: ScopeKey
    exam_system: ScopeKey
    subject_scope: ScopeKey
    batch_group: ScopeKey

    @field_validator("dataset_id", "program_id", "institution_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value)


class OriginalData(CatalogModel):
    size_bytes: int = Field(strict=True, ge=1, le=MAX_ORIGINAL_BYTES)
    sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    media_type: OriginalMediaType


class LocatedSnippet(CatalogModel):
    text: str = Field(strict=True, min_length=1, max_length=MAX_SNIPPET_BYTES)
    snippet_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    locator: EvidenceLocator

    @model_validator(mode="after")
    def exact_text_hash_and_span(self):
        try:
            encoded = self.text.encode("utf-8")
        except UnicodeError:
            raise ValueError("valid UTF-8 text is required") from None
        if (len(encoded) > MAX_SNIPPET_BYTES or len(encoded) != self.locator.byte_end - self.locator.byte_start
            or sha256(encoded).hexdigest() != self.snippet_sha256):
            raise ValueError("text, hash and exact byte span must agree")
        return self


class SnippetData(LocatedSnippet):
    id: UUID
    document_id: UUID
    document_version: PositiveVersion
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    language: Language
    document_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    is_synthetic: bool = Field(strict=True)
    created_at: datetime
    scope: EvidenceScope

    @field_validator("id", "document_id", "offering_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def server_time(cls, value):
        return _utc(value)

    @model_validator(mode="after")
    def exact_scope_year(self):
        if self.entry_year != self.scope.entry_year:
            raise ValueError("snippet and server-derived offering scope years must agree")
        return self
