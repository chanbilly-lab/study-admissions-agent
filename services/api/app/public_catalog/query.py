"""Bounded opaque cursors bind filters and an immutable change-event watermark."""

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

from .schemas import PublicCatalogError, PublicOfferingQuery


@dataclass(frozen=True)
class CursorState:
    watermark: int
    release_id: UUID
    offering_id: UUID
    offering_version: int


def query_fingerprint(query: PublicOfferingQuery) -> str:
    try:
        current = PublicOfferingQuery.model_validate(query)
        raw = json.dumps(current.model_dump(mode="json", exclude={"cursor"}),
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    except Exception:
        raise PublicCatalogError(422) from None


def encode_cursor(query, watermark, release_id, offering_id, offering_version):
    if (type(watermark) is not int or not 0 <= watermark <= 9007199254740991
        or type(release_id) is not UUID or type(offering_id) is not UUID
        or type(offering_version) is not int or not 1 <= offering_version <= 2147483647):
        raise PublicCatalogError()
    body = {"v": 1, "q": query_fingerprint(query), "w": watermark,
            "r": str(release_id), "o": str(offering_id), "n": offering_version}
    encoded = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True,
        separators=(",", ":")).encode("ascii")).decode("ascii").rstrip("=")
    if len(encoded) > 512:
        raise PublicCatalogError()
    return encoded


def decode_cursor(query, cursor) -> CursorState:
    try:
        if type(cursor) is not str or not 1 <= len(cursor) <= 512 or re.fullmatch(r"[A-Za-z0-9_-]+", cursor) is None:
            raise ValueError()
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != cursor:
            raise ValueError()
        pairs = json.loads(raw.decode("ascii"), object_pairs_hook=lambda values: values)
        if (type(pairs) is not list or any(type(pair) is not tuple or len(pair) != 2 for pair in pairs)
            or len(pairs) != 6 or len({key for key, _ in pairs}) != 6):
            raise ValueError()
        body = dict(pairs)
        if (set(body) != {"v", "q", "w", "r", "o", "n"}
            or type(body["v"]) is not int or body["v"] != 1
            or body["q"] != query_fingerprint(query)
            or type(body["w"]) is not int or not 0 <= body["w"] <= 9007199254740991
            or type(body["n"]) is not int or not 1 <= body["n"] <= 2147483647
            or type(body["r"]) is not str or type(body["o"]) is not str):
            raise ValueError()
        release, offering = UUID(body["r"]), UUID(body["o"])
        if str(release) != body["r"] or str(offering) != body["o"]:
            raise ValueError()
        return CursorState(body["w"], release, offering, body["n"])
    except Exception:
        raise PublicCatalogError(422, "INVALID_CURSOR") from None
