"""Trusted storage boundary: opaque server UUIDs, never browser paths."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from .schemas import StorageError, StorageNamespace, StoredBlob, ValidatedUpload


@runtime_checkable
class StorageBackend(Protocol):
    def verify_ready(self) -> None: ...

    def write(self, namespace: StorageNamespace, object_id: UUID, data: bytes) -> StoredBlob: ...

    def read(self, namespace: StorageNamespace, object_id: UUID,
             expected_size: int, expected_sha256: str) -> bytes: ...

    def delete(self, namespace: StorageNamespace, object_id: UUID) -> bool: ...


__all__ = ["StorageBackend", "StorageNamespace", "StoredBlob", "ValidatedUpload", "StorageError"]
