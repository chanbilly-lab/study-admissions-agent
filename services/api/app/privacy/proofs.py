"""Trusted internal references; these are not sharing HTTP response fields."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from ..auth.schemas import AuthModel


class DeclaredAdultProof(AuthModel):
    user_id: UUID
    declaration_id: UUID
    notice_id: UUID
    policy_version: str
    expires_at: datetime
    is_synthetic: bool = Field(strict=True)


class PurposeProof(DeclaredAdultProof):
    consent_id: UUID
