"""Closed manual-import contracts, without approval or executable fact semantics."""

import re
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import (
    CatalogModel, Identifier, PositiveVersion, _identifier, _namespace,
)


PARSER_SCHEMA_VERSION = "T15_v1"
MAX_IMPORT_BYTES = 1_048_576
MAX_IMPORT_ROWS = 200
MAX_FIELD_BYTES = 4_096
MAX_DECIMAL_LENGTH = 64
ROW_FIELDS = (
    "offering_id", "offering_version", "entry_year", "source_record_reference",
    "fact_type", "field_key", "value_kind", "value_text", "unit", "missing_reason",
    "footnote_state", "footnote_text", "locator",
)
NULLABLE_FIELDS = frozenset(("value_text", "unit", "missing_reason", "footnote_text", "locator"))
MAX_ROW_ERRORS = MAX_IMPORT_ROWS * (len(ROW_FIELDS) + 1)

ImportFormat = Literal["json", "csv"]
RowField = Literal[
    "document", "offering_id", "offering_version", "entry_year", "source_record_reference",
    "fact_type", "field_key", "value_kind", "value_text", "unit", "missing_reason",
    "footnote_state", "footnote_text", "locator",
]
RowCode = Literal[
    "INVALID_ENCODING", "INPUT_TOO_LARGE", "INVALID_STRUCTURE", "EMPTY_IMPORT",
    "TOO_MANY_ROWS", "INVALID_HEADER", "DUPLICATE_KEY", "MISSING_FIELD",
    "UNEXPECTED_FIELD", "INVALID_FIELD", "FIELD_TOO_LARGE", "INVALID_INTEGER",
    "INVALID_UUID", "INVALID_DECIMAL", "MISSING_VALUE_REASON", "INVALID_FOOTNOTE",
    "SCOPE_MISMATCH", "NAMESPACE_MISMATCH",
]
MissingReason = Literal["not_provided", "not_applicable", "not_published", "unavailable", "ambiguous"]


class ImportServiceError(ValueError):
    """Fixed safe errors; never raw rows, filenames, SQL or parser exceptions."""

    def __init__(self, status_code=503, code=None):
        codes = {422: "INVALID_IMPORT_INPUT", 409: "IMPORT_CONFLICT",
                 404: "IMPORT_NOT_FOUND", 503: "IMPORT_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


def _uuid(value):
    if type(value) is UUID:
        return value
    if type(value) is not str:
        raise ValueError("a canonical UUID reference is required")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise ValueError("a canonical UUID reference is required") from None
    if str(parsed) != value:
        raise ValueError("a canonical UUID reference is required")
    return parsed


def _text(value: str) -> str:
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise ValueError("bounded valid text is required") from None
    if (len(encoded) > MAX_FIELD_BYTES or not value.strip()
        or any(ord(c) < 32 and c not in "\t\r\n" or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError("bounded nonblank text is required")
    return value


class CandidateInput(CatalogModel):
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    source_record_reference: Identifier
    fact_type: Literal["requirement", "score", "fee", "material", "date", "statistic"]
    field_key: Identifier
    value_kind: Literal["text", "decimal"]
    value_text: str | None = Field(strict=True, min_length=1, max_length=MAX_FIELD_BYTES)
    unit: str | None = Field(strict=True, min_length=1, max_length=MAX_FIELD_BYTES)
    missing_reason: MissingReason | None
    footnote_state: Literal["present", "none", "unknown"]
    footnote_text: str | None = Field(strict=True, min_length=1, max_length=MAX_FIELD_BYTES)
    locator: str | None = Field(strict=True, min_length=1, max_length=MAX_FIELD_BYTES)

    @field_validator("offering_id", mode="before")
    @classmethod
    def canonical_offering_id(cls, value):
        return _uuid(value)

    @field_validator("source_record_reference", "field_key")
    @classmethod
    def exact_reference(cls, value):
        return _identifier(value)

    @field_validator("value_text", "unit", "footnote_text", "locator")
    @classmethod
    def original_text(cls, value):
        return _text(value) if value is not None else None

    @model_validator(mode="after")
    def explicit_missing_and_footnotes(self):
        if (self.value_text is None) != (self.missing_reason is not None):
            raise ValueError("missing values require an explicit reason and present values no missing reason")
        if self.value_text is not None and self.value_kind == "decimal":
            if (len(self.value_text) > MAX_DECIMAL_LENGTH
                or re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", self.value_text) is None):
                raise ValueError("a bounded decimal lexical string is required")
        if (self.footnote_state == "present") != (self.footnote_text is not None):
            raise ValueError("a present footnote requires text and other states require null")
        return self

    def validate_namespace(self, is_synthetic: bool) -> None:
        current = type(self).model_validate(self)
        if type(is_synthetic) is not bool:
            raise ValueError("a strict synthetic marker is required")
        _namespace(current.source_record_reference, is_synthetic)


class ParsedRow(CandidateInput):
    row_number: int = Field(strict=True, ge=1, le=MAX_IMPORT_ROWS + 1)


class RowError(CatalogModel):
    row_number: int = Field(strict=True, ge=0, le=MAX_IMPORT_ROWS + 1)
    field: RowField
    code: RowCode


class ParsedImport(CatalogModel):
    rows: tuple[ParsedRow, ...] = Field(max_length=MAX_IMPORT_ROWS)
    errors: tuple[RowError, ...] = Field(max_length=MAX_ROW_ERRORS)
    total_rows: int | None = Field(strict=True, ge=0, le=MAX_IMPORT_ROWS)

    @model_validator(mode="after")
    def atomic_rows(self):
        if self.errors:
            if self.rows:
                raise ValueError("a rejected import contains no candidate rows")
        elif self.total_rows is None or self.total_rows == 0 or len(self.rows) != self.total_rows:
            raise ValueError("a successful parse contains every candidate row")
        if self.total_rows is None and any(error.row_number != 0 for error in self.errors):
            raise ValueError("unknown structures use only a document-level position")
        if self.total_rows is not None and any(error.row_number > self.total_rows + 1 for error in self.errors):
            raise ValueError("error positions must belong to the counted logical records")
        if self.rows:
            positions = tuple(row.row_number for row in self.rows)
            if positions not in (tuple(range(1, len(self.rows) + 1)), tuple(range(2, len(self.rows) + 2))):
                raise ValueError("candidate positions must follow the original logical record order")
        return self


class ImportRequest(CatalogModel):
    dataset_id: UUID
    source_id: UUID
    source_version: PositiveVersion
    file_id: UUID
    file_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    format: ImportFormat

    @field_validator("dataset_id", "source_id", "file_id", mode="before")
    @classmethod
    def canonical_scope_id(cls, value):
        return _uuid(value)


class ImportsPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    real_imports_ready: bool = Field(default=False, strict=True)


class ImportResult(CatalogModel):
    id: UUID
    status: Literal["staged", "rejected"]
    total_rows: int | None = Field(strict=True, ge=0, le=MAX_IMPORT_ROWS)
    staged_rows: int = Field(strict=True, ge=0, le=MAX_IMPORT_ROWS)
    error_count: int = Field(strict=True, ge=0, le=MAX_ROW_ERRORS)
    errors: tuple[RowError, ...] = Field(max_length=MAX_ROW_ERRORS)
    replayed: bool = Field(strict=True)

    @field_validator("id", mode="before")
    @classmethod
    def canonical_batch_id(cls, value):
        return _uuid(value)

    @model_validator(mode="after")
    def closed_counts(self):
        if self.error_count != len(self.errors):
            raise ValueError("error count must match the safe error list")
        if self.status == "staged":
            if self.errors or self.total_rows is None or self.total_rows == 0 or self.staged_rows != self.total_rows:
                raise ValueError("staged imports contain every row and no errors")
        elif self.staged_rows != 0 or not self.errors:
            raise ValueError("rejected imports contain errors and no candidate rows")
        if self.total_rows is None:
            if any(error.row_number != 0 for error in self.errors):
                raise ValueError("unknown structures use only a document-level position")
        elif any(error.row_number > self.total_rows + 1 for error in self.errors):
            raise ValueError("error positions must belong to the counted logical records")
        return self
