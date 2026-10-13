"""Bounded authenticated synthetic packages; no filesystem or database access."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import os
from typing import Annotated, Literal
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

MAX_PAYLOAD_BYTES = 10 * 1024 * 1024
MAX_METADATA_BYTES = 4096
MAGIC = b"STUDY-T44\x00\x01"
NONCE_BYTES = 12
MAX_PACKAGE_BYTES = len(MAGIC) + 4 + MAX_METADATA_BYTES + NONCE_BYTES + MAX_PAYLOAD_BYTES + 16


class BackupError(ValueError):
    """Fixed non-sensitive reason, never dump bytes or encryption keys."""


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always", allow_inf_nan=False)


class BackupPolicy(Closed):
    mode: Literal["disabled", "synthetic"] = "disabled"
    max_payload_bytes: Annotated[StrictInt, Field(ge=1, le=MAX_PAYLOAD_BYTES)] = MAX_PAYLOAD_BYTES


def _utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise BackupError("BACKUP_INVALID")
    return value.astimezone(timezone.utc)


class BackupMetadata(Closed):
    schema_version: Literal["t44.synthetic.1"] = "t44.synthetic.1"
    backup_id: UUID
    captured_at: datetime
    expires_at: datetime
    payload_size: Annotated[StrictInt, Field(ge=1, le=MAX_PAYLOAD_BYTES)]
    payload_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    is_synthetic: Literal[True] = True
    runtime_verified: Literal[False] = False
    traffic_ready: Literal[False] = False

    @field_validator("captured_at", "expires_at")
    @classmethod
    def dates(cls, value):
        return _utc(value)

    @field_validator("is_synthetic", "runtime_verified", "traffic_ready", mode="before")
    @classmethod
    def booleans(cls, value):
        if type(value) is not bool:
            raise ValueError("Explicit boolean required")
        return value

    @model_validator(mode="after")
    def duration(self):
        if not timedelta(0) < self.expires_at - self.captured_at <= timedelta(days=35):
            raise ValueError("Invalid retention interval")
        return self


def _policy(value: BackupPolicy) -> BackupPolicy:
    if type(value) is not BackupPolicy:
        raise BackupError("BACKUP_INVALID")
    try:
        current = BackupPolicy.model_validate(value.model_dump())
    except ValueError:
        raise BackupError("BACKUP_INVALID") from None
    if current.mode != "synthetic":
        raise BackupError("BACKUP_DISABLED")
    return current


def _key(value: bytes) -> bytes:
    if type(value) is not bytes or len(value) != 32:
        raise BackupError("BACKUP_INVALID")
    return value


def _canonical(metadata: BackupMetadata) -> bytes:
    return json.dumps(metadata.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def seal_synthetic(payload: bytes, key: bytes, *, now: datetime, expires_at: datetime,
                   policy: BackupPolicy = BackupPolicy()) -> bytes:
    """Encrypt caller-supplied synthetic bytes in memory; disabled by default."""
    current = _policy(policy)
    secret = _key(key)
    if type(payload) is not bytes or not 1 <= len(payload) <= current.max_payload_bytes:
        raise BackupError("BACKUP_INVALID")
    try:
        metadata = BackupMetadata(backup_id=uuid4(), captured_at=_utc(now), expires_at=_utc(expires_at),
                                  payload_size=len(payload), payload_sha256=sha256(payload).hexdigest())
        header = _canonical(metadata)
    except ValueError:
        raise BackupError("BACKUP_INVALID") from None
    if len(header) > MAX_METADATA_BYTES:
        raise BackupError("BACKUP_INVALID")
    nonce = os.urandom(NONCE_BYTES)
    prefix = MAGIC + len(header).to_bytes(4, "big") + header
    return prefix + nonce + AESGCM(secret).encrypt(nonce, payload, prefix)


def _unique_pairs(pairs):
    document = {}
    for name, value in pairs:
        if name in document:
            raise BackupError("BACKUP_INVALID")
        document[name] = value
    return document


def unseal_synthetic(package: bytes, key: bytes, *, now: datetime,
                     policy: BackupPolicy = BackupPolicy()) -> tuple[BackupMetadata, bytes]:
    """Authenticate and decrypt an unexpired package; this never restores a service."""
    current = _policy(policy)
    secret = _key(key)
    at = _utc(now)
    if type(package) is not bytes or not len(MAGIC) + 4 + NONCE_BYTES + 17 <= len(package) <= MAX_PACKAGE_BYTES:
        raise BackupError("BACKUP_INVALID")
    if not package.startswith(MAGIC):
        raise BackupError("BACKUP_INVALID")
    header_size = int.from_bytes(package[len(MAGIC):len(MAGIC) + 4], "big")
    if not 1 <= header_size <= MAX_METADATA_BYTES:
        raise BackupError("BACKUP_INVALID")
    end = len(MAGIC) + 4 + header_size
    if len(package) < end + NONCE_BYTES + 17:
        raise BackupError("BACKUP_INVALID")
    header = package[len(MAGIC) + 4:end]
    try:
        # Reject duplicate keys first; JSON-mode validation preserves strict UUID/UTC dates.
        document = json.loads(header.decode("ascii"), object_pairs_hook=_unique_pairs)
        metadata = BackupMetadata.model_validate_json(json.dumps(document, allow_nan=False))
        if _canonical(metadata) != header or metadata.payload_size > current.max_payload_bytes:
            raise BackupError("BACKUP_INVALID")
        if metadata.captured_at > at or metadata.expires_at <= at:
            raise BackupError("BACKUP_EXPIRED")
        if len(package) != end + NONCE_BYTES + metadata.payload_size + 16:
            raise BackupError("BACKUP_INVALID")
        nonce = package[end:end + NONCE_BYTES]
        payload = AESGCM(secret).decrypt(nonce, package[end + NONCE_BYTES:], package[:end])
        if len(payload) != metadata.payload_size or not hmac.compare_digest(sha256(payload).hexdigest(), metadata.payload_sha256):
            raise BackupError("BACKUP_INVALID")
        return metadata, payload
    except BackupError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError, InvalidTag):
        raise BackupError("BACKUP_INVALID") from None
