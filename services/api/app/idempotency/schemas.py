"""Closed internal receipts, without request bodies, keys or cached responses."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IDEMPOTENCY_HEAD = "0001_idempotency_t49"
MAX_TTL_SECONDS = 730 * 24 * 60 * 60
MAX_VERSION = 2_147_483_647
Operation = Literal["catalog.import", "catalog.publish", "profile.create", "plan.confirm"]
ReceiptKind = Literal["import", "catalog_release", "profile", "plan"]


class IdempotencyError(ValueError):
    """Fixed safe errors, never SQL diagnostics, keys or payload contents."""

    def __init__(self, status_code=503, code=None):
        codes = {422: "INVALID_IDEMPOTENCY_INPUT", 409: "IDEMPOTENCY_CONFLICT",
                 503: "IDEMPOTENCY_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__({422: "Idempotency input is invalid", 409: "Idempotency request conflicts",
                          503: "Idempotency service is unavailable"}[status_code])


class IdempotencyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always", hide_input_in_errors=True)


class IdempotencyPolicy(IdempotencyModel):
    enabled: bool = Field(default=False, strict=True)
    real_idempotency_ready: bool = Field(default=False, strict=True)
    ttl_seconds: int | None = Field(default=None, strict=True, ge=1, le=MAX_TTL_SECONDS)

    @model_validator(mode="after")
    def explicit_ttl(self):
        if self.enabled and self.ttl_seconds is None:
            raise ValueError("an enabled receipt policy requires an explicit finite TTL")
        return self


class ResourceReceipt(IdempotencyModel):
    kind: ReceiptKind
    resource_id: UUID
    version: int = Field(strict=True, ge=1, le=MAX_VERSION)


class IdempotencyResult(IdempotencyModel):
    resource: ResourceReceipt
    replayed: bool = Field(strict=True)
    expires_at: datetime

    @field_validator("expires_at", mode="before")
    @classmethod
    def explicit_time(cls, value):
        try:
            if (type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None
                or value.fold != 0):
                raise ValueError()
            return value.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise ValueError("an aware server time is required") from None
