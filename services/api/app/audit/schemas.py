"""Closed internal events: no request actors, payloads or exception messages."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..auth.schemas import AuthModel

POLICY_VERSION = "T10_audit_v1"
Action = Literal[
    "auth.login.start", "auth.login.consume", "auth.login.complete", "auth.login.cancel", "auth.logout",
    "auth.role.assign", "auth.role.revoke", "authorization.owned.check", "authorization.owned.list",
    "authorization.owned.register", "authorization.owned.execute", "authorization.capability.check",
    "privacy.adult.declare", "privacy.admission.invalidate", "privacy.core.confirm", "privacy.core.withdraw",
    "sharing.grant.create", "sharing.grant.accept", "sharing.grant.revoke", "sharing.read", "sharing.list",
    "sharing.execute_read", "audit.read", "audit.purge", "catalog.import", "catalog.review", "catalog.publish",
    "catalog.withdraw", "export.create", "deletion.accept", "administrator.action"]
ObjectType = Literal["login_transaction", "session", "user", "profile", "plan", "attachment", "export", "job",
                     "admission", "consent", "access_grant", "catalog_release", "import", "deletion_job", "audit_event"]
Reason = Literal["OK", "UNAUTHORIZED", "FORBIDDEN", "NOT_FOUND", "CONFLICT", "VALIDATION_ERROR",
                 "SERVICE_UNAVAILABLE", "INTERNAL_ERROR"]


class AuditActor(AuthModel):
    """Server-internal reference, never an identity credential."""
    user_id: UUID
    session_id: UUID | None
    is_synthetic: bool = Field(strict=True)


class AuditEventInput(AuthModel):
    action: Action
    outcome: Literal["succeeded", "denied", "failed"]
    reason_code: Reason
    object_type: ObjectType | None = None
    object_id: UUID | None = None
    object_version: int | None = Field(default=None, strict=True, ge=1)

    @model_validator(mode="after")
    def fixed_reference(self):
        if self.object_id is not None and self.object_type is None:
            raise ValueError("a fixed object type is required")
        if self.object_version is not None and self.object_id is None:
            raise ValueError("version requires an object reference")
        if self.outcome != "succeeded" and (self.object_id is not None or self.object_version is not None):
            raise ValueError("failed attempts do not retain requested object identifiers")
        if (self.outcome == "succeeded") != (self.reason_code == "OK"):
            raise ValueError("fixed outcome and reason must agree")
        return self


class AuditEventData(AuditEventInput):
    id: UUID
    occurred_at: datetime
    actor_kind: Literal["anonymous", "user", "system"]
    actor_user_id: UUID | None
    actor_session_id: UUID | None
    request_id: str = Field(strict=True, pattern=r"^[0-9a-f]{32}$")
    is_synthetic: bool = Field(strict=True)
    policy_version: Literal["T10_audit_v1"]
    expires_at: datetime

    @field_validator("occurred_at", "expires_at")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("an explicit time offset is required")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def coupled_actor(self):
        if (self.actor_kind == "user") != (self.actor_user_id is not None):
            raise ValueError("actor references must agree")
        if self.actor_kind != "user" and self.actor_session_id is not None:
            raise ValueError("non-user events cannot contain a session")
        if self.expires_at <= self.occurred_at:
            raise ValueError("retention must be finite")
        from .retention import expires_after_months
        if self.expires_at > expires_after_months(self.occurred_at):
            raise ValueError("audit retention exceeds the product maximum")
        return self


class AuditPage(AuthModel):
    items: tuple[AuditEventData, ...]
    next_cursor: UUID | None
