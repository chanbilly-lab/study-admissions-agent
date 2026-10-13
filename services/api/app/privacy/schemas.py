"""Explicit T08 wire contract; age declarations are never verified identities."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from ..auth.schemas import AuthModel


AgeBand = Literal["unknown", "under_14", "14_17", "18_plus"]
AdmissionReason = Literal["allowed", "processing_disabled", "age_missing", "age_expired",
    "notice_changed", "policy_changed", "consent_missing", "consent_withdrawn", "consent_invalidated",
    "role_missing"]


class PrivacyAgePolicy(AuthModel):
    under_14: Literal["public_only"]
    age_14_17: Literal["private_disabled"]
    age_18_plus: Literal["self_declaration_and_confirmation"]
    unknown: Literal["public_only"]
    guardian_verification_available: Literal[False]
    declaration_is_verification: Literal[False]


class PrivacyRetentionPolicy(AuthModel):
    file_types: list[Literal["pdf", "utf8_csv", "json"]]
    max_file_bytes: Literal[10485760]
    private_data_max_months: Literal[24]
    online_deletion_max_days: Literal[30]
    sanitized_logs_max_days: Literal[30]
    audit_authorization_max_months: Literal[24]
    backup_max_days: Literal[35]
    cleanup_implemented: Literal[False]


class PrivacyNoticeData(AuthModel):
    policy_version: str
    notice_id: UUID | None
    notice_version: str | None
    notice_hash: str
    text: str
    is_synthetic: bool = Field(strict=True)
    readiness: bool = Field(strict=True)
    readiness_reason: Literal["processing_disabled", "test_fixture_ready"]
    purposes: list[Literal["core_consultation"]]
    age_policy: PrivacyAgePolicy
    retention_policy: PrivacyRetentionPolicy


class AdmissionData(AuthModel):
    user_id: UUID
    revision: int = Field(ge=0, strict=True)
    age_band: Literal["18_plus"] | None
    age_assurance: Literal["unknown", "declared"]
    declared_at: datetime | None
    declaration_expires_at: datetime | None
    policy_version: str
    notice_id: UUID | None
    notice_version: str | None
    consent_id: UUID | None
    consent_status: Literal["not_confirmed", "active", "withdrawn", "invalidated"]
    core_consultation_allowed: bool = Field(strict=True)
    reason: AdmissionReason
    readiness: bool = Field(strict=True)
    is_synthetic: bool = Field(strict=True)
    private_business_available: Literal[False]


class AgeDeclarationInput(AuthModel):
    age_band: AgeBand
    confirmed: Literal[True]
    notice_id: UUID
    expected_revision: int = Field(ge=0, strict=True)

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit boolean confirmation is required")
        return value


class CoreConsentInput(AuthModel):
    purpose: Literal["core_consultation"]
    notice_id: UUID
    confirmed: Literal[True]
    expected_revision: int = Field(ge=0, strict=True)

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit boolean confirmation is required")
        return value


__all__ = ["PrivacyAgePolicy", "PrivacyRetentionPolicy", "PrivacyNoticeData", "AdmissionData",
           "AgeDeclarationInput", "CoreConsentInput", "AgeBand", "AdmissionReason"]
