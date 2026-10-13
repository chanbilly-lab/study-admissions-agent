"""Closed internal storage contracts; metadata is never an access credential."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_FILE_BYTES = 10485760
STORAGE_HEAD = "0001_storage_t14"


class StorageError(ValueError):
    def __init__(self, status_code=503, code=None):
        codes = {422: "INVALID_FILE", 413: "FILE_TOO_LARGE", 404: "FILE_NOT_FOUND",
                 409: "STORAGE_CONFLICT", 503: "STORAGE_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


class StorageNamespace(StrEnum):
    student_private = "student_private"
    source_quarantine = "source_quarantine"


class StorageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always", hide_input_in_errors=True)


class StoredBlob(StorageModel):
    namespace: StorageNamespace
    object_id: UUID
    size_bytes: int = Field(strict=True, ge=1, le=MAX_FILE_BYTES)
    sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")

    @field_validator("object_id")
    @classmethod
    def random_identifier(cls, value):
        if value.version != 4:
            raise ValueError("a server UUIDv4 is required")
        return value


class ValidatedUpload(StorageModel):
    media_type: Literal["application/pdf", "text/csv", "application/json"]
    size_bytes: int = Field(strict=True, ge=1, le=MAX_FILE_BYTES)
    sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")


class FileData(StorageModel):
    id: UUID
    namespace: StorageNamespace
    is_synthetic: bool = Field(strict=True)
    status: Literal["quarantined", "delete_pending", "deleted"]
    media_type: Literal["application/pdf", "text/csv", "application/json"]
    size_bytes: int = Field(strict=True, ge=1, le=MAX_FILE_BYTES)
    sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)

    @field_validator("id")
    @classmethod
    def random_identifier(cls, value):
        if value.version != 4:
            raise ValueError("a server UUIDv4 is required")
        return value

    @field_validator("created_at", "expires_at", mode="before")
    @classmethod
    def native_timestamp(cls, value):
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None or value.fold != 0:
            raise ValueError("a native aware timestamp is required")
        try:
            return value.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise ValueError("timestamp is outside the supported calendar") from None

    @field_validator("expires_at")
    @classmethod
    def bounded_expiry(cls, value, info):
        from calendar import monthrange
        created = info.data.get("created_at")
        if created is not None:
            try:
                end = created.replace(year=created.year + 2,
                    day=min(created.day, monthrange(created.year + 2, created.month)[1]))
            except (ValueError, OverflowError):
                raise ValueError("timestamp is outside the supported calendar") from None
            if not created < value <= end:
                raise ValueError("finite expiry within the product upper bound is required")
        return value


class StoragePolicy(StorageModel):
    enabled: bool = Field(default=False, strict=True)
    real_storage_ready: bool = Field(default=False, strict=True)
    source_retention_days: int | None = Field(default=None, strict=True, ge=1, le=730)
