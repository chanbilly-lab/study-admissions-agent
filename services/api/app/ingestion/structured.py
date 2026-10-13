"""Finite JSON/CSV parsing into unapproved, all-or-nothing candidate rows."""

import csv
import io
import json
import re

from pydantic import ValidationError

from .schemas import (
    CandidateInput, ImportFormat, MAX_DECIMAL_LENGTH, MAX_FIELD_BYTES, MAX_IMPORT_BYTES,
    MAX_IMPORT_ROWS, NULLABLE_FIELDS, ParsedImport, ParsedRow, ROW_FIELDS, RowError,
)


MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 10_000
_FIELDS = frozenset(ROW_FIELDS)
_INTEGER_FIELDS = frozenset(("offering_version", "entry_year"))


class _DuplicateKey(ValueError):
    pass


def _failure(code, *, total_rows=None):
    return ParsedImport(rows=(), errors=(RowError(row_number=0, field="document", code=code),),
                        total_rows=total_rows)


def _lexical_bounds(text):
    """Bound recursion and allocations before invoking the stdlib JSON decoder."""
    depth = nodes = 0
    in_string = escaped = in_atom = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
            in_atom = False
            nodes += 1
        elif character in "[{":
            depth += 1
            nodes += 1
            in_atom = False
            if depth > MAX_JSON_DEPTH:
                raise ValueError()
        elif character in "]}":
            depth -= 1
            in_atom = False
        elif character.isspace() or character in ",:":
            in_atom = False
        elif not in_atom:
            nodes += 1
            in_atom = True
        if nodes > MAX_JSON_NODES:
            raise ValueError()


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKey()
        value[key] = item
    return value


def _bounded_integer(value):
    # Numeric JSON tokens are only valid for the two bounded integer metadata
    # fields. Semantic decimal values must arrive as original string literals.
    if len(value.lstrip("-")) > 10:
        raise ValueError()
    return int(value)


def _reject_number(_):
    raise ValueError()


def _json_rows(text):
    _lexical_bounds(text)
    rows = json.loads(text, object_pairs_hook=_unique_pairs, parse_int=_bounded_integer,
                      parse_float=_reject_number, parse_constant=_reject_number)
    if type(rows) is not list:
        raise ValueError()
    return rows


def _coupled_error(raw, number):
    if (raw.get("value_text") is None) != (raw.get("missing_reason") is not None):
        return RowError(row_number=number, field="value_text", code="MISSING_VALUE_REASON")
    value = raw.get("value_text")
    if (raw.get("value_kind") == "decimal" and type(value) is str
        and (len(value) > MAX_DECIMAL_LENGTH or re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None)):
        return RowError(row_number=number, field="value_text", code="INVALID_DECIMAL")
    if (raw.get("footnote_state") == "present") != (raw.get("footnote_text") is not None):
        return RowError(row_number=number, field="footnote_text", code="INVALID_FOOTNOTE")
    return RowError(row_number=number, field="document", code="INVALID_FIELD")


def _candidate(raw, number):
    if type(raw) is not dict:
        return None, [RowError(row_number=number, field="document", code="INVALID_STRUCTURE")]
    errors = []
    if set(raw) - _FIELDS:
        errors.append(RowError(row_number=number, field="document", code="UNEXPECTED_FIELD"))
    for field in ROW_FIELDS:
        if field not in raw:
            errors.append(RowError(row_number=number, field=field, code="MISSING_FIELD"))
        elif type(raw[field]) is str:
            try:
                oversized = len(raw[field].encode("utf-8")) > MAX_FIELD_BYTES
            except UnicodeError:
                errors.append(RowError(row_number=number, field=field, code="INVALID_FIELD"))
            else:
                if oversized:
                    errors.append(RowError(row_number=number, field=field, code="FIELD_TOO_LARGE"))
    if errors:
        return None, errors
    try:
        candidate = CandidateInput.model_validate(raw)
        return ParsedRow(**candidate.model_dump(), row_number=number), []
    except ValidationError as invalid:
        for item in invalid.errors(include_input=False, include_context=False, include_url=False):
            field = item["loc"][0] if item["loc"] else None
            if field not in _FIELDS:
                error = _coupled_error(raw, number)
            else:
                code = ("INVALID_INTEGER" if field in _INTEGER_FIELDS else
                        "INVALID_UUID" if field == "offering_id" else
                        "INVALID_FOOTNOTE" if field in {"footnote_state", "footnote_text"} else
                        "INVALID_DECIMAL" if field == "value_text" and raw["value_kind"] == "decimal" else
                        "INVALID_FIELD")
                error = RowError(row_number=number, field=field, code=code)
            if error not in errors:
                errors.append(error)
        return None, errors


def _csv_rows(text):
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=",", strict=True)
    header = next(reader, None)
    if header != list(ROW_FIELDS):
        return None, "INVALID_HEADER"
    rows = []
    for cells in reader:
        if len(rows) == MAX_IMPORT_ROWS:
            return None, "TOO_MANY_ROWS"
        if len(cells) != len(ROW_FIELDS):
            rows.append(None)
            continue
        row = dict(zip(ROW_FIELDS, cells))
        for field in NULLABLE_FIELDS:
            if row[field] == "\\N":
                row[field] = None
        for field in _INTEGER_FIELDS:
            value = row[field]
            if re.fullmatch(r"[1-9][0-9]{0,9}", value) is not None:
                row[field] = int(value)
            # Otherwise leave the original lexical string to be rejected by
            # strict metadata validation. Empty/space/NaN is never inferred null.
        rows.append(row)
    return rows, None


def parse_structured_import(data: bytes, *, format: ImportFormat) -> ParsedImport:
    """Return safe positions/codes; any error discards every candidate row.

    JSON positions count array records from one. CSV positions count logical
    records including the header, so quoted multiline values do not change them.
    This parser performs no source approval, fact interpretation, IO or execution.
    """
    if type(data) is not bytes or not data or type(format) is not str or format not in {"json", "csv"}:
        return _failure("INVALID_STRUCTURE")
    if len(data) > MAX_IMPORT_BYTES:
        return _failure("INPUT_TOO_LARGE")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeError:
        return _failure("INVALID_ENCODING")
    try:
        if format == "json":
            raw_rows = _json_rows(text)
            if len(raw_rows) > MAX_IMPORT_ROWS:
                return _failure("TOO_MANY_ROWS")
        else:
            raw_rows, error = _csv_rows(text)
            if error is not None:
                return _failure(error)
    except _DuplicateKey:
        return _failure("DUPLICATE_KEY")
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError, csv.Error):
        return _failure("INVALID_STRUCTURE")
    if not raw_rows:
        return _failure("EMPTY_IMPORT", total_rows=0)
    rows, errors = [], []
    offset = 1 if format == "json" else 2
    for index, raw in enumerate(raw_rows, start=offset):
        candidate, row_errors = _candidate(raw, index)
        if candidate is not None:
            rows.append(candidate)
        errors.extend(row_errors)
    return ParsedImport(rows=() if errors else tuple(rows), errors=tuple(errors), total_rows=len(raw_rows))
