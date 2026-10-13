"""Bounded internal JSON hashing, without coercion or a persisted request body.

This is the project's explicit encoding, not RFC 8785 JSON Canonicalization.
Typed callers serialize UUIDs, dates and decimal values deliberately before use.
"""

from hashlib import sha256
import json


MAX_CANONICAL_BYTES = 1_048_576
MAX_CANONICAL_DEPTH = 32
MAX_CANONICAL_NODES = 100_000
MAX_SAFE_INTEGER = 2**53 - 1


class CanonicalRequestError(ValueError):
    def __init__(self):
        super().__init__("Request cannot be canonically hashed")


def canonical_request_hash(value: object) -> str:
    """Hash exact JSON primitives; object order is ignored, array order is not.

    Depth counts object/array containers, including the root. Nodes count each
    container, value and object key. Shared acyclic objects are traversed anew;
    cycles are rejected. No Unicode normalization or whitespace trimming occurs.
    """
    if type(value) not in (dict, list):
        raise CanonicalRequestError()
    digest = sha256()
    encoded_bytes = nodes = 0
    ancestors = set()

    def emit(chunk: bytes):
        nonlocal encoded_bytes
        encoded_bytes += len(chunk)
        if encoded_bytes > MAX_CANONICAL_BYTES:
            raise CanonicalRequestError()
        digest.update(chunk)

    def count():
        nonlocal nodes
        nodes += 1
        if nodes > MAX_CANONICAL_NODES:
            raise CanonicalRequestError()

    def string(text):
        # A cheap character bound precedes any UTF-8 or escaped-string allocation.
        # One bounded string can expand to at most six JSON bytes per character.
        if len(text) > MAX_CANONICAL_BYTES:
            raise CanonicalRequestError()
        text.encode("utf-8", errors="strict")
        emit(json.dumps(text, ensure_ascii=False).encode("utf-8", errors="strict"))

    def visit(current, depth):
        count()
        kind = type(current)
        if current is None:
            emit(b"null")
        elif kind is bool:
            emit(b"true" if current else b"false")
        elif kind is int:
            if not -MAX_SAFE_INTEGER <= current <= MAX_SAFE_INTEGER:
                raise CanonicalRequestError()
            emit(str(current).encode("ascii"))
        elif kind is str:
            string(current)
        elif kind in (dict, list):
            if depth >= MAX_CANONICAL_DEPTH or id(current) in ancestors:
                raise CanonicalRequestError()
            minimum_children = len(current) * (2 if kind is dict else 1)
            if minimum_children > MAX_CANONICAL_NODES - nodes:
                raise CanonicalRequestError()
            ancestors.add(id(current))
            try:
                if kind is dict:
                    if any(type(key) is not str for key in current):
                        raise CanonicalRequestError()
                    emit(b"{")
                    for index, key in enumerate(sorted(current)):
                        if index:
                            emit(b",")
                        count()
                        string(key)
                        emit(b":")
                        visit(current[key], depth + 1)
                    emit(b"}")
                else:
                    emit(b"[")
                    for index, child in enumerate(current):
                        if index:
                            emit(b",")
                        visit(child, depth + 1)
                    emit(b"]")
            finally:
                ancestors.remove(id(current))
        else:
            raise CanonicalRequestError()

    try:
        visit(value, 0)
    except CanonicalRequestError:
        raise
    except (UnicodeError, ValueError, TypeError, KeyError, RuntimeError, RecursionError):
        raise CanonicalRequestError() from None
    return digest.hexdigest()


__all__ = ["canonical_request_hash", "CanonicalRequestError"]
