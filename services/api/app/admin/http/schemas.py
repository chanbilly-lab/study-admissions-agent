"""Closed source/import workspace inputs and minimal administration output."""

from calendar import monthrange
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ...admissions_catalog.schemas import CatalogModel, PositiveVersion
from ...ingestion.schemas import ImportRequest, MAX_IMPORT_BYTES
from ...storage.validation import validate_filename
from ..sources.schemas import SourceCreateInput, SourceDefinition, _utc_time


class AdminContextData(CatalogModel):
    schema_version: Literal["v2.t21"]
    can_manage_sources: bool = Field(strict=True)
    can_import: bool = Field(strict=True)
    is_synthetic: bool = Field(strict=True)


class ConfirmedInput(CatalogModel):
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit confirmation is required")
        return value


class AdminSourceRegisterInput(ConfirmedInput):
    source: SourceCreateInput
    expected_dataset_revision: PositiveVersion


class AdminSourceRevisionInput(ConfirmedInput):
    definition: SourceDefinition
    expected_dataset_revision: PositiveVersion
    expected_source_version: PositiveVersion


class AdminSourceFileInput(ConfirmedInput):
    source_id: UUID
    source_version: PositiveVersion
    filename: str = Field(strict=True, min_length=1, max_length=255)
    content_type: Literal["application/json", "text/csv"]
    content_utf8: str = Field(strict=True, min_length=1, max_length=MAX_IMPORT_BYTES, repr=False)

    @model_validator(mode="after")
    def bounded_original(self):
        try:
            content = self.content_utf8.encode("utf-8")
            validate_filename(self.filename, self.content_type)
        except (UnicodeError, ValueError, TypeError):
            raise ValueError("a valid UTF-8 JSON or CSV upload is required") from None
        if len(content) > MAX_IMPORT_BYTES:
            raise ValueError("the upload exceeds the synchronous byte limit")
        return self


class AdminImportInput(ImportRequest, ConfirmedInput):
    pass


class AdminSourceData(SourceDefinition):
    id: UUID
    dataset_id: UUID
    source_id: UUID
    version: PositiveVersion
    is_synthetic: bool = Field(strict=True)
    created_at: datetime = Field(strict=True)
    permission_reviewed_at: datetime | None = Field(strict=True)
    recheck_due_at: datetime = Field(strict=True)
    auto_fetch_enabled: Literal[False]
    dataset_revision: PositiveVersion

    @field_validator("created_at", "permission_reviewed_at", "recheck_due_at", mode="before")
    @classmethod
    def server_timestamp(cls, value):
        return _utc_time(value) if value is not None else None

    @field_validator("auto_fetch_enabled", mode="before")
    @classmethod
    def fetching_disabled(cls, value):
        if value is not False:
            raise ValueError("automatic fetching is disabled")
        return value

    @model_validator(mode="after")
    def server_metadata(self):
        SourceDefinition.model_validate({name: getattr(self, name)
            for name in SourceDefinition.model_fields}).validate_namespace(self.is_synthetic)
        recorded = any(value != "pending" for value in (
            self.manual_import_permission, self.publication_permission, self.automated_fetch_permission))
        if recorded != (self.permission_reviewed_at is not None):
            raise ValueError("permission metadata does not match the recorded declaration")
        if self.permission_reviewed_at is not None and self.permission_reviewed_at != self.created_at:
            raise ValueError("permission metadata must use the version creation timestamp")
        try:
            year = self.created_at.year + 2
            cap = self.created_at.replace(year=year, day=min(self.created_at.day, monthrange(year, self.created_at.month)[1]))
            expected = min(self.created_at + timedelta(days=self.recheck_days), cap)
        except (ValueError, OverflowError):
            raise ValueError("the recheck date is outside the supported calendar") from None
        if self.recheck_due_at != expected:
            raise ValueError("the recheck date must match the declared interval")
        return self
