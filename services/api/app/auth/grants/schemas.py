"""Frozen metadata-only sharing wire; no identity proof crosses subjects."""

from datetime import datetime, timezone
import re
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from ..schemas import AuthModel
from ...api.v2.schemas import PageInfo

Kind = Literal["profile", "plan", "attachment", "export", "job"]
SharedField = Literal["status", "version"]
SharedAction = Literal["read", "list"]


class SharingSettings(AuthModel):
    fixture_mode: bool = Field(default=False, strict=True)


class SharingScopeData(AuthModel):
    resource_type: Kind
    fields: list[SharedField]
    actions: list[SharedAction]


class SharingPolicyData(AuthModel):
    policy_version: str
    text: str
    text_sha256: str
    is_synthetic: bool = Field(strict=True)
    sharing_available: bool = Field(strict=True)
    readiness_reason: Literal["disabled", "synthetic_test_ready"]
    max_duration_seconds: Literal[2592000]
    scope_matrix: list[SharingScopeData]
    guardian_verification_available: Literal[False]
    private_business_available: Literal[False]


class CreateGrantInput(AuthModel):
    resource_type: Kind
    resource_id: UUID
    expected_resource_version: int = Field(strict=True, ge=1)
    grantee_user_id: UUID
    fields: list[SharedField] = Field(min_length=1, max_length=2)
    actions: list[SharedAction] = Field(min_length=1, max_length=2)
    expires_at: datetime
    confirmed: Literal[True]
    expected_revision: int = Field(strict=True, ge=0)
    owner_consent_id: UUID
    sharing_policy_version: str = Field(strict=True, min_length=1, max_length=100)
    sharing_policy_hash: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")

    @field_validator("confirmed", mode="before")
    @classmethod
    def confirm_bool(cls, value):
        if value is not True:
            raise ValueError("explicit boolean confirmation is required")
        return value

    @field_validator("fields", "actions")
    @classmethod
    def unique_scope(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("scope values must be unique")
        return sorted(value)

    @field_validator("expires_at", mode="before")
    @classmethod
    def explicit_datetime(cls, value):
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
            raise ValueError("an explicit time offset is required")
        return value

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("an explicit time offset is required")
        return value.astimezone(timezone.utc)


class AcceptGrantInput(AuthModel):
    confirmed: Literal[True]
    expected_version: int = Field(strict=True, ge=1)
    sharing_policy_version: str = Field(strict=True, min_length=1, max_length=100)
    sharing_policy_hash: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")

    @field_validator("confirmed", mode="before")
    @classmethod
    def confirm_bool(cls, value):
        if value is not True:
            raise ValueError("explicit boolean confirmation is required")
        return value


class GrantData(AuthModel):
    id: UUID
    resource_id: UUID
    resource_type: Kind
    resource_version: int = Field(strict=True, ge=1)
    owner_user_id: UUID
    grantee_user_id: UUID
    fields: list[SharedField]
    actions: list[SharedAction]
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    state: Literal["pending", "accepted", "revoked"]
    version: int = Field(strict=True, ge=1)
    sharing_policy_version: str
    is_synthetic: bool = Field(strict=True)
    access_active: bool = Field(strict=True)


class GrantMutationData(AuthModel):
    user_id: UUID
    revision: int = Field(strict=True, ge=0)
    grant: GrantData


class GrantListData(AuthModel):
    user_id: UUID
    revision: int = Field(strict=True, ge=0)
    actor_declaration_id: UUID | None
    owner_consent_id: UUID | None
    sharing_available: bool = Field(strict=True)
    total: int = Field(strict=True, ge=0)
    items: list[GrantData]
    page: PageInfo


class SharedProjection(AuthModel):
    resource_id: UUID
    resource_type: Kind
    is_synthetic: bool = Field(strict=True)
    requested_fields: tuple[SharedField, ...]
    status: Literal["active", "deleted"] | None
    version: int | None = Field(strict=True, ge=1)


class SharedPage(AuthModel):
    items: tuple[SharedProjection, ...]
    total: int = Field(strict=True, ge=0)
    next_cursor: UUID | None
