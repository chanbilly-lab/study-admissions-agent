"""Exact UTF-8 byte spans and physical lines; no PDF, OCR or fact extraction."""

from hashlib import sha256

from ..storage.schemas import StorageError
from ..storage.validation import validate_upload
from .schemas import (
    EvidenceError, EvidenceLocator, LocatedSnippet, MAX_ORIGINAL_BYTES, MAX_SNIPPET_BYTES, OriginalData,
)


def validate_original(data: bytes, *, media_type: str) -> OriginalData:
    if (type(data) is not bytes or not 0 < len(data) <= MAX_ORIGINAL_BYTES
        or type(media_type) is not str or media_type not in {"application/json", "text/csv"}):
        raise EvidenceError(422)
    filename = "DEMO_original.json" if media_type == "application/json" else "DEMO_original.csv"
    try:
        # Reuse T14's pure, bounded syntax checks. This label is never persisted
        # or used as a path. CSV is an original document, not the T15 row schema.
        checked = validate_upload(data, filename=filename, content_type=media_type)
    except StorageError:
        raise EvidenceError(422) from None
    return OriginalData(size_bytes=checked.size_bytes, sha256=checked.sha256, media_type=checked.media_type)


def _line_bounds(data: bytes, byte_start: int, byte_end: int):
    # CRLF is one boundary; lone CR and LF also end a physical line. Newline
    # bytes themselves belong to the preceding line, including both CRLF bytes.
    line_start = line_end = 1
    position = 0
    while position < byte_end:
        if data[position] == 13:
            position += 2 if position + 1 < len(data) and data[position + 1] == 10 else 1
        elif data[position] == 10:
            position += 1
        else:
            position += 1
            continue
        if position <= byte_start:
            line_start += 1
        if position < byte_end:
            line_end += 1
    return line_start, line_end


def extract_snippet(data: bytes, *, media_type: str, byte_start: int, byte_end: int) -> LocatedSnippet:
    validate_original(data, media_type=media_type)
    if (type(byte_start) is not int or type(byte_end) is not int
        or not 0 <= byte_start < byte_end <= len(data) or byte_end - byte_start > MAX_SNIPPET_BYTES):
        raise EvidenceError(422)
    try:
        # Prefix decoding proves that start is a boundary even when a suffix
        # could independently decode. The full document was validated above.
        data[:byte_start].decode("utf-8", errors="strict")
        fragment = data[byte_start:byte_end]
        text = fragment.decode("utf-8", errors="strict")
    except UnicodeError:
        raise EvidenceError(422) from None
    line_start, line_end = _line_bounds(data, byte_start, byte_end)
    locator = EvidenceLocator(byte_start=byte_start, byte_end=byte_end,
        line_start=line_start, line_end=line_end,
        page=None, section=None, location_kind="utf8_byte_lines")
    return LocatedSnippet(text=text, snippet_sha256=sha256(fragment).hexdigest(), locator=locator)
