"""Server-only durable lease and cleanup permission contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from ..admissions_catalog.schemas import CatalogModel
from ..api.v2.idempotency_canonical import canonical_request_hash
from ..evidence.schemas import _uuid
from ..notifications.schemas import NotificationError, NotificationPolicy
from ..rules.expression import explicit_instant

JobError = NotificationError
JobKind = Literal["release_impact","notification","export","model","cleanup_probe"]
JobReason = Literal["OK","AUTHORITY_REVOKED","PREFERENCE_CHANGED","PROFILE_CHANGED","EXPIRED","LEASE_LOST","RETRYABLE_FAILURE","HANDLER_UNAVAILABLE","PERMIT_INVALID","ATTEMPTS_EXHAUSTED"]


class JobsPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_jobs: bool = Field(default=False, strict=True)
    real_jobs_ready: Literal[False] = False
    lease_seconds: int = Field(default=30, strict=True, ge=1, le=300)
    max_attempts: int = Field(default=3, strict=True, ge=1, le=5)
    retry_seconds: int = Field(default=1, strict=True, ge=1, le=60)
    job_ttl_seconds: int = Field(default=86400, strict=True, ge=1, le=86400)
    allow_cleanup_probe: bool = Field(default=False, strict=True)
    _closed = field_validator("real_jobs_ready", mode="before")(NotificationPolicy.closed.__func__)


class JobClaim(CatalogModel):
    job_id: UUID
    worker_id: UUID
    generation: int = Field(strict=True, ge=1, le=2147483647)
    lease_token: UUID
    lease_until: datetime
    _ids = field_validator("job_id","worker_id","lease_token", mode="before")(_uuid)
    _time = field_validator("lease_until", mode="before")(explicit_instant)


class JobResult(CatalogModel):
    job_id: UUID
    kind: JobKind
    status: Literal["queued","running","completed","cancelled","failed"]
    reason: JobReason
    attempts: int = Field(strict=True, ge=0, le=5)
    generation: int = Field(strict=True, ge=0, le=2147483647)
    _id = field_validator("job_id", mode="before")(_uuid)


class CleanupResource(CatalogModel):
    resource_id: UUID
    resource_type: Literal["profile","plan","attachment","export","job"]
    version: int = Field(strict=True, ge=1, le=2147483647)
    status: Literal["active","deleted"]
    is_synthetic: bool = Field(strict=True)
    _id = field_validator("resource_id", mode="before")(_uuid)


class CleanupScope(CatalogModel):
    owner_user_id: UUID
    is_synthetic: bool = Field(strict=True)
    resources: tuple[CleanupResource, ...] = Field(min_length=1, max_length=100)
    watermark: int = Field(strict=True, ge=1, le=2147483647)
    purpose: Literal["deletion_cleanup","retention_cleanup"]
    _id = field_validator("owner_user_id", mode="before")(_uuid)

    @field_validator("resources", mode="before")
    @classmethod
    def bounded(cls, value):
        if type(value) not in {tuple,list} or not 1<=len(value)<=100:
            raise ValueError("a bounded exact resource collection is required")
        return value

    @model_validator(mode="after")
    def exact(self):
        ids = [str(item.resource_id) for item in self.resources]
        if ids != sorted(set(ids)) or any(item.is_synthetic != self.is_synthetic for item in self.resources):
            raise ValueError("cleanup resources are sorted unique and mode-bound")
        return self


def scope_hash(scope):
    return canonical_request_hash(CleanupScope.model_validate(scope).model_dump(mode="json"))
