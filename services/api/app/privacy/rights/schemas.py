"""Closed rights contracts. A queued deletion is never a completed erasure."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

MAX_EXPORT_BYTES = 10 * 1024 * 1024
MAX_SCOPE_BYTES = 262144
ZERO_HASH = "0" * 64
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Kind = Literal["export", "deletion"]
Status = Literal["queued", "running", "completed", "failed", "cancelled"]
Reason = Literal["OK", "RIGHTS_DISABLED", "AUTHORITY_REVOKED", "OWNER_DELETED", "EXPIRED",
    "EXPORT_LIMIT", "RETRYABLE_FAILURE", "ATTEMPTS_EXHAUSTED", "LEASE_LOST", "LEDGER_UNAVAILABLE"]
EventKind = Literal["owner_deleted", "session_revoked", "role_revoked", "core_withdrawn", "grant_revoked", "file_deleted"]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("UTC instant required")
    return value.astimezone(timezone.utc)


class RightsPolicy(Closed):
    enabled: StrictBool = False
    allow_test_rights: StrictBool = False
    real_rights_ready: Literal[False] = False
    lease_seconds: Annotated[StrictInt, Field(ge=1, le=300)] = 30
    max_attempts: Annotated[StrictInt, Field(ge=1, le=5)] = 3
    retry_seconds: Annotated[StrictInt, Field(ge=1, le=300)] = 1
    export_ttl_seconds: Annotated[StrictInt, Field(ge=1, le=86400)] = 3600
    max_export_bytes: Annotated[StrictInt, Field(ge=1, le=MAX_EXPORT_BYTES)] = MAX_EXPORT_BYTES
    max_rows: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000


class OwnerConfirmation(Closed):
    owner_confirmed: Literal[True]

    @field_validator("owner_confirmed", mode="before")
    @classmethod
    def explicit(cls, value):
        if value is not True:
            raise ValueError("Explicit confirmation required")
        return value


class RightsContext(Closed):
    enabled: StrictBool
    real_rights_ready: Literal[False] = False
    reason: Reason
    deletion_accepted: StrictBool = False
    online_cleanup_days: Literal[30] = 30
    responsibility_retention_months: Literal[24] = 24
    backup_retention_days: Literal[35] = 35
    max_export_bytes: Annotated[StrictInt, Field(ge=1, le=MAX_EXPORT_BYTES)] = MAX_EXPORT_BYTES


class RightsRequestData(Closed):
    request_id: UUID
    kind: Kind
    status: Status
    reason: Reason
    attempts: Annotated[StrictInt, Field(ge=0, le=5)]
    accepted_at: datetime
    online_cleanup_due_at: datetime | None
    completed_at: datetime | None
    artifact_expires_at: datetime | None
    online_cleanup_complete: StrictBool
    retained_responsibility_until: datetime
    backup_retention_days: Literal[35] = 35
    is_synthetic: Literal[True] = True

    @field_validator("accepted_at", "online_cleanup_due_at", "completed_at", "artifact_expires_at", "retained_responsibility_until")
    @classmethod
    def dates(cls, value):
        return utc(value) if value is not None else value

    @model_validator(mode="after")
    def meaning(self):
        if self.online_cleanup_complete != (self.kind == "deletion" and self.status == "completed"):
            raise ValueError("Cleanup status conflict")
        if (self.status == "completed") != (self.completed_at is not None):
            raise ValueError("Completion receipt required")
        if (self.kind == "deletion") != (self.online_cleanup_due_at is not None):
            raise ValueError("Deletion deadline required")
        return self


class ExportContent(Closed):
    request_id: UUID
    content_type: Literal["application/json"] = "application/json"
    content_json: Annotated[str, Field(min_length=1, max_length=MAX_EXPORT_BYTES)]
    size_bytes: Annotated[StrictInt, Field(ge=1, le=MAX_EXPORT_BYTES)]
    sha256: Hash
    expires_at: datetime
    is_synthetic: Literal[True] = True

    @model_validator(mode="after")
    def content(self):
        import hashlib, json
        data = self.content_json.encode("utf-8")
        if len(data) != self.size_bytes or hashlib.sha256(data).hexdigest() != self.sha256:
            raise ValueError("Artifact bytes conflict")
        if not isinstance(json.loads(self.content_json), dict):
            raise ValueError("Export object required")
        utc(self.expires_at)
        return self


class LedgerEventData(Closed):
    event_id: UUID
    kind: EventKind
    owner_user_id: UUID
    resource_id: UUID | None = None
    role: Literal["student", "data_admin", "operations"] | None = None
    role_granted_at: datetime | None = None
    recorded_at: datetime
    expires_at: datetime

    @field_validator("recorded_at", "expires_at", "role_granted_at")
    @classmethod
    def dates(cls, value):
        return utc(value) if value is not None else value

    @model_validator(mode="after")
    def shape(self):
        from ...audit.retention import expires_after_months
        if not self.recorded_at < self.expires_at <= expires_after_months(self.recorded_at):
            raise ValueError("Ledger retention required")
        if self.kind == "role_revoked":
            if self.resource_id is not None or self.role is None or self.role_granted_at is None:
                raise ValueError("Exact role epoch required")
        elif self.role is not None or self.role_granted_at is not None:
            raise ValueError("Unexpected role epoch")
        if self.kind in {"owner_deleted", "session_revoked", "core_withdrawn", "grant_revoked", "file_deleted"} and self.resource_id is None:
            raise ValueError("Exact reference required")
        return self


class LedgerProof(Closed):
    ledger_id: UUID
    sequence: Annotated[StrictInt, Field(ge=0, le=10000)]
    chain_sha256: Hash


class Lease(Closed):
    request_id: UUID
    kind: Kind
    generation: Annotated[StrictInt, Field(ge=1, le=2147483647)]
    worker_id: UUID
    token: UUID
    until: datetime

    @field_validator("until")
    @classmethod
    def date(cls, value):
        return utc(value)


class RightsError(Exception):
    def __init__(self, status_code=503, code="SERVICE_UNAVAILABLE"):
        self.status_code, self.code = status_code, code
        super().__init__(code)
