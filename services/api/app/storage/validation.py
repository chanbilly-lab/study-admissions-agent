"""Bounded syntax checks; neither malware scanning nor admissions fact review."""

import csv
from hashlib import sha256
import io
import json
import math
import re

from .schemas import MAX_FILE_BYTES, StorageError, ValidatedUpload


_TYPES = {".pdf": "application/pdf", ".csv": "text/csv", ".json": "application/json"}
_DEVICES = {"CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$",
            *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)),
            "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³"}


def validate_filename(filename: str, content_type: str) -> str:
    if (type(filename) is not str or not 1 <= len(filename) <= 255
        or filename != filename.strip() or filename.endswith((".", " "))
        or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in filename)
        or any(c in filename for c in '/\\:<>"|?*') or filename in {".", ".."}):
        raise StorageError(422, "INVALID_FILE")
    try:
        filename.encode("utf-8")
    except UnicodeError:
        raise StorageError(422, "INVALID_FILE") from None
    stem, separator, extension = filename.rpartition(".")
    suffix = "." + extension
    if (not separator or not stem or stem.endswith((".", " "))
        or stem.split(".", 1)[0].upper() in _DEVICES
        or suffix not in _TYPES or type(content_type) is not str or content_type != _TYPES[suffix]):
        raise StorageError(422, "INVALID_FILE")
    # Extensions are labels, not a mechanism for executing or interpreting files.
    return content_type


def _text(data: bytes) -> str:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeError:
        raise StorageError(422, "INVALID_FILE") from None
    if "\x00" in text or any(ord(c) < 32 and c not in "\t\r\n" for c in text):
        raise StorageError(422, "INVALID_FILE")
    return text


def _csv(text: str) -> None:
    beginning = text.lstrip().lower()
    if (not beginning or beginning.startswith(("%pdf", "pk\x03\x04", "mz", "<!doctype", "<html", "<svg"))):
        raise StorageError(422, "INVALID_FILE")
    rows = cells = 0
    try:
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=",", strict=True):
            rows += 1
            cells += len(row)
            if (rows > 100_000 or not row or len(row) > 200 or cells > 100_000
                or any(len(field.encode("utf-8")) > 65_536 for field in row)):
                raise StorageError(422, "INVALID_FILE")
    except (csv.Error, UnicodeError):
        raise StorageError(422, "INVALID_FILE") from None
    if rows == 0:
        raise StorageError(422, "INVALID_FILE")


def _json(text: str) -> None:
    # Bound nesting before the standard parser allocates recursive containers.
    depth = lexical_nodes = 0
    in_atom = False
    in_string = escaped = False
    for c in text:
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
        elif c == '"':
            lexical_nodes += 1
            in_string = True
            in_atom = False
        elif c in "[{":
            lexical_nodes += 1
            in_atom = False
            depth += 1
            if depth > 32:
                raise StorageError(422, "INVALID_FILE")
        elif c in "]}":
            depth -= 1
            in_atom = False
        elif c.isspace() or c in ",:":
            in_atom = False
        elif not in_atom:
            lexical_nodes += 1
            in_atom = True
        if lexical_nodes > 100_000:
            raise StorageError(422, "INVALID_FILE")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError
        return result

    def reject_constant(_):
        raise ValueError

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_float=finite_float,
                           parse_constant=reject_constant)
        if not isinstance(value, (dict, list)):
            raise ValueError
        pending = [value]
        nodes = 0
        while pending:
            node = pending.pop()
            nodes += 1
            if nodes > 100_000:
                raise ValueError
            if isinstance(node, dict):
                # Keys are input nodes too; validate escaped lone surrogates.
                for key, child in node.items():
                    key.encode("utf-8")
                    nodes += 1
                    pending.append(child)
                if nodes > 100_000:
                    raise ValueError
            elif isinstance(node, list):
                pending.extend(node)
            elif isinstance(node, str):
                node.encode("utf-8")
    except (ValueError, TypeError, RecursionError, UnicodeError, OverflowError):
        raise StorageError(422, "INVALID_FILE") from None


def validate_upload(data: bytes, *, filename: str, content_type: str) -> ValidatedUpload:
    if type(data) is not bytes or not data:
        raise StorageError(422, "INVALID_FILE")
    if len(data) > MAX_FILE_BYTES:
        raise StorageError(413, "FILE_TOO_LARGE")
    media_type = validate_filename(filename, content_type)
    if media_type == "application/pdf":
        if (re.match(rb"%PDF-(?:1\.[0-7]|2\.0)(?:\r\n|\r|\n)", data) is None
            or not data.rstrip(b" \t\r\n").endswith(b"%%EOF")):
            raise StorageError(422, "INVALID_FILE")
    elif media_type == "text/csv":
        _csv(_text(data))
    else:
        _json(_text(data))
    return ValidatedUpload(media_type=media_type, size_bytes=len(data), sha256=sha256(data).hexdigest())


__all__ = ["MAX_FILE_BYTES", "validate_upload", "validate_filename"]
