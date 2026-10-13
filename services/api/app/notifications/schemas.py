"""Bounded T36 wire contracts; no client supplied authority or content."""

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel
from ..changes.schemas import ImpactReason
from ..evidence.schemas import _uuid
from ..profiles.schemas import ProfileMeta
from ..rules.expression import explicit_instant

MAX_BODY_BYTES = 65536
JOBS_HEAD = "0001_jobs_t36"


class NotificationError(Exception):
    def __init__(self, status_code=503):
        self.status_code = status_code
        self.code = {422:"INVALID_NOTIFICATION_INPUT",404:"NOTIFICATION_NOT_FOUND",409:"NOTIFICATION_CONFLICT"}.get(status_code,"NOTIFICATION_UNAVAILABLE")
        super().__init__(self.code)


class NotificationPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_notifications: bool = Field(default=False, strict=True)
    real_notifications_ready: Literal[False] = False

    @field_validator("real_notifications_ready", mode="before")
    @classmethod
    def closed(cls, value):
        if value is not False:
            raise ValueError("real notifications are unavailable")
        return value


class PreferenceInput(CatalogModel):
    expected_version: int = Field(strict=True, ge=0, le=2147483647)
    enabled: bool = Field(strict=True)
    profile_id: UUID | None
    student_confirmed: Literal[True]

    _id = field_validator("profile_id", mode="before")(lambda value: None if value is None else _uuid(value))

    @field_validator("student_confirmed", mode="before")
    @classmethod
    def explicit(cls, value):
        if value is not True:
            raise ValueError("explicit student confirmation is required")
        return value

    @model_validator(mode="after")
    def choice(self):
        if self.enabled != (self.profile_id is not None):
            raise ValueError("only enablement binds an explicitly selected profile")
        return self


class MarkReadInput(CatalogModel):
    expected_version: int = Field(strict=True, ge=1, le=2147483647)
    student_confirmed: Literal[True]
    _explicit = field_validator("student_confirmed", mode="before")(PreferenceInput.explicit.__func__)


class NotificationContextData(CatalogModel):
    schema_version: Literal["v2.t36"]
    can_read: bool = Field(strict=True)
    can_manage_preferences: bool = Field(strict=True)
    can_mark_read: bool = Field(strict=True)
    is_synthetic: bool = Field(strict=True)
    delivery_channel: Literal["in_app"]
    external_delivery_enabled: Literal[False]
    _closed = field_validator("external_delivery_enabled", mode="before")(NotificationPolicy.closed.__func__)


class NotificationPreferenceData(CatalogModel):
    version: int = Field(strict=True, ge=0, le=2147483647)
    enabled: bool = Field(strict=True)
    profile_id: UUID | None
    profile_version_id: UUID | None
    profile_sha256: str | None = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    is_synthetic: bool = Field(strict=True)
    updated_at: datetime | None
    _ids = field_validator("profile_id","profile_version_id", mode="before")(lambda value: None if value is None else _uuid(value))
    _time = field_validator("updated_at", mode="before")(lambda value: None if value is None else explicit_instant(value))

    @model_validator(mode="after")
    def binding(self):
        bound = (self.profile_id, self.profile_version_id, self.profile_sha256)
        if (self.enabled and any(value is None for value in bound)) or (not self.enabled and any(value is not None for value in bound)):
            raise ValueError("enablement and profile proof must agree")
        if (self.version == 0) != (self.updated_at is None) or self.version == 0 and self.enabled:
            raise ValueError("an absent preference is disabled and unversioned")
        return self


class NotificationData(CatalogModel):
    id: UUID
    version: int = Field(strict=True, ge=1, le=2)
    event_id: UUID
    assessment_id: UUID
    profile_id: UUID
    profile_version_id: UUID
    profile_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    is_synthetic: bool = Field(strict=True)
    reason: ImpactReason
    needs_review: bool = Field(strict=True)
    dataset_id: UUID
    entry_year: int = Field(strict=True, ge=1, le=9999)
    offering_id: UUID
    offering_version: int = Field(strict=True, ge=1, le=2147483647)
    before_release_id: UUID | None
    after_release_id: UUID | None
    created_at: datetime
    expires_at: datetime
    read_at: datetime | None
    _ids = field_validator("id","event_id","assessment_id","profile_id","profile_version_id","dataset_id","offering_id", mode="before")(_uuid)
    _optional_ids = field_validator("before_release_id","after_release_id", mode="before")(lambda value: None if value is None else _uuid(value))
    _times = field_validator("created_at","expires_at", mode="before")(explicit_instant)
    _read = field_validator("read_at", mode="before")(lambda value: None if value is None else explicit_instant(value))

    @model_validator(mode="after")
    def content(self):
        if (self.before_release_id is None and self.after_release_id is None or self.expires_at <= self.created_at
            or (self.version == 2) != (self.read_at is not None)
            or self.read_at is not None and not self.created_at <= self.read_at < self.expires_at
            or self.needs_review != (self.reason != "REFERENCE_REPLACED")):
            raise ValueError("notification references, review marker and finite times must agree")
        return self


class NotificationPage(CatalogModel):
    items: tuple[NotificationData, ...] = Field(max_length=20)
    next_cursor: str | None = Field(strict=True, min_length=1, max_length=1024)

    @field_validator("items", mode="before")
    @classmethod
    def bounded(cls, value):
        if type(value) not in {tuple,list} or len(value)>20:
            raise ValueError("a bounded native collection is required")
        return value

    @model_validator(mode="after")
    def distinct(self):
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("notification IDs must be unique")
        return self


Item = TypeVar("Item")


class NotificationEnvelope(CatalogModel, Generic[Item]):
    data: Item
    meta: ProfileMeta

    @model_validator(mode="after")
    def metadata(self):
        version = self.data.profile_version_id if isinstance(self.data,(NotificationPreferenceData,NotificationData)) else None
        if version is None:
            if self.meta.profile_version_id is not None or self.meta.profile_mode is not None:
                raise ValueError("this response has no single profile version")
        elif (self.meta.profile_version_id != version or self.meta.profile_mode != ("synthetic" if self.data.is_synthetic else "real")):
            raise ValueError("metadata must bind the server profile version")
        return self
