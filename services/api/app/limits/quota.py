from dataclasses import dataclass
import math
from threading import RLock
import time
from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from ..admissions_catalog.schemas import CatalogModel


class LimitError(ValueError):
    def __init__(self, code="QUOTA_UNAVAILABLE", status=503):
        self.code, self.status = code, status
        super().__init__(code)


class QuotaPolicy(CatalogModel):
    mode: Literal["disabled", "synthetic"] = "disabled"
    window_seconds: int | None = Field(default=None, strict=True, ge=1, le=86400)
    request_limit: int | None = Field(default=None, strict=True, ge=1, le=100000)
    inflight_limit: int | None = Field(default=None, strict=True, ge=1, le=1000)
    unit_limit: int | None = Field(default=None, strict=True, ge=1, le=10**9)

    @model_validator(mode="after")
    def explicit_limits(self):
        if self.mode == "synthetic" and None in (self.window_seconds, self.request_limit, self.inflight_limit, self.unit_limit):
            raise ValueError("Explicit synthetic thresholds required")
        return self


@dataclass(frozen=True)
class Reservation:
    request_id: UUID
    request_sha256: str
    units: int
    active: bool
    replayed: bool = False


class QuotaLedger:
    """Server-local total quota, not a caller role/account authorization decision."""
    def __init__(self, policy=QuotaPolicy(), *, clock=time.monotonic):
        self.policy = QuotaPolicy.model_validate(policy)
        self._initial = self.policy.model_dump()
        self.clock = clock
        self._lock = RLock()
        self._last = self._start = None
        self._requests = self._units = 0
        self._receipts = {}
        self._blocked = False

    def reserve(self, request_id: UUID, request_sha256: str, units: int) -> Reservation:
        import re
        if (type(request_id) is not UUID or type(request_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", request_sha256) is None
                or type(units) is not int or not 1 <= units <= 10**9):
            raise LimitError("INVALID_QUOTA_INPUT", 422)
        with self._lock:
            if self._blocked or self.policy.model_dump() != self._initial or self.policy.mode != "synthetic":
                raise LimitError()
            now = self.clock()
            if type(now) not in (int, float) or not math.isfinite(now) or now < 0 or self._last is not None and now < self._last:
                self._blocked = True
                raise LimitError()
            self._last = now
            if self._start is None:
                self._start = now
            old = self._receipts.get(request_id)
            if old is not None:
                if (old.request_sha256, old.units) != (request_sha256, units):
                    raise LimitError("IDEMPOTENCY_CONFLICT", 409)
                return Reservation(old.request_id, old.request_sha256, old.units, old.active, True)
            if now - self._start >= self.policy.window_seconds:
                self._start, self._requests, self._units = now, 0, 0
            active = sum(receipt.active for receipt in self._receipts.values())
            if (len(self._receipts) >= 10000 or self._requests >= self.policy.request_limit
                    or active >= self.policy.inflight_limit or self._units + units > self.policy.unit_limit):
                raise LimitError("QUOTA_EXCEEDED", 429)
            receipt = Reservation(request_id, request_sha256, units, True)
            self._receipts[request_id] = receipt
            self._requests += 1
            self._units += units
            return receipt

    def finish(self, receipt: Reservation) -> None:
        with self._lock:
            if type(receipt) is not Reservation or receipt.replayed:
                raise LimitError("INVALID_RESERVATION", 409)
            old = self._receipts.get(receipt.request_id)
            if old is not receipt:
                raise LimitError("INVALID_RESERVATION", 409)
            self._receipts[receipt.request_id] = Reservation(old.request_id, old.request_sha256, old.units, False)
            # Conservative accounting: finishing/failure never refunds reserved units.
