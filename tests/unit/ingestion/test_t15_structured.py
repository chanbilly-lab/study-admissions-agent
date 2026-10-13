"""Finite, all-or-nothing candidates preserve lexical values and safe errors."""

import csv
import io
import json
import os
import subprocess
import sys
from uuid import uuid4

from pydantic import ValidationError
import pytest

from app.ingestion.schemas import (
    CandidateInput, ImportRequest, ImportResult, ImportServiceError, ImportsPolicy,
    MAX_FIELD_BYTES, MAX_IMPORT_BYTES, MAX_IMPORT_ROWS, ParsedImport, ParsedRow,
    ROW_FIELDS, RowError,
)
from app.ingestion.structured import parse_structured_import


def row(**changes):
    return {
        "offering_id": str(uuid4()), "offering_version": 1, "entry_year": 2026,
        "source_record_reference": "DEMO_record_1", "fact_type": "score", "field_key": "minimum_score",
        "value_kind": "decimal", "value_text": "500.00", "unit": "points", "missing_reason": None,
        "footnote_state": "unknown", "footnote_text": None, "locator": None,
        **changes,
    }


def json_input(rows):
    return json.dumps(rows, ensure_ascii=False).encode("utf-8")


def csv_input(rows, header=ROW_FIELDS):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(header)
    for current in rows:
        writer.writerow("\\N" if current[field] is None else current[field] for field in header)
    return output.getvalue().encode("utf-8")


def parse(rows, *, format="json"):
    return parse_structured_import(json_input(rows) if format == "json" else csv_input(rows), format=format)


def assert_rejected(result, *, code=None, field=None, row_number=None):
    assert not result.rows and result.errors
    matching = [error for error in result.errors if (code is None or error.code == code)
                and (field is None or error.field == field)
                and (row_number is None or error.row_number == row_number)]
    assert matching
    assert all(set(error.model_dump()) == {"row_number", "field", "code"} for error in result.errors)


def test_json_preserves_lexical_decimal_footnotes_and_unresolved_locator():
    original = row(value_text="-0.00", footnote_state="present", footnote_text="  DEMO 注：另有条件\n第二行  ")
    result = parse([original])
    assert result.total_rows == 1 and not result.errors
    candidate = result.rows[0]
    assert candidate.row_number == 1
    assert candidate.value_text == "-0.00"
    assert candidate.footnote_text == original["footnote_text"]
    assert candidate.locator is None
    assert str(candidate.offering_id) == original["offering_id"]
    assert original["offering_id"] is not candidate.offering_id
    assert "reviewed" not in candidate.model_dump() and "published" not in candidate.model_dump()


def test_csv_explicit_nulls_and_logical_multiline_positions():
    first = row(fact_type="requirement", value_kind="text", value_text="DEMO 通常适用，需核验\n未形成硬规则", unit=None)
    second = row(value_text="0", footnote_state="none")
    result = parse([first, second], format="csv")
    assert not result.errors and [item.row_number for item in result.rows] == [2, 3]
    assert result.rows[0].value_text == first["value_text"]
    assert result.rows[0].unit is None and result.rows[1].value_text == "0"


@pytest.mark.parametrize("format", ["json", "csv"])
def test_one_bad_row_discards_all_good_rows_with_safe_positions(format):
    result = parse([row(), row(value_text="DEMO_bad-value-secret"), row()], format=format)
    assert_rejected(result, code="INVALID_DECIMAL", field="value_text", row_number=2 if format == "json" else 3)
    assert result.total_rows == 3 and "secret" not in result.model_dump_json()


@pytest.mark.parametrize("value", ["1e3", "NaN", "Infinity", "01", "+1", "1,000", " 10 ", "1.", "9" * 65])
def test_decimal_is_bounded_lexical_text_without_implicit_numeric_conversion(value):
    assert_rejected(parse([row(value_text=value)]), code="INVALID_DECIMAL")


def test_text_kind_is_uninterpreted_candidate_and_not_a_numeric_qualification():
    candidate = parse([row(value_kind="text", value_text="  通常或视情况；NaN  ")]).rows[0]
    assert candidate.value_text == "  通常或视情况；NaN  "
    assert candidate.value_kind == "text"


def test_missing_value_and_unknown_footnote_are_explicit_independent_states():
    result = parse([row(value_text=None, missing_reason="not_published", footnote_state="unknown")])
    assert not result.errors and result.rows[0].value_text is None
    for changes in ({"value_text": None}, {"missing_reason": "ambiguous"},
                    {"value_text": None, "missing_reason": "anything"}):
        assert_rejected(parse([row(**changes)]))
    assert parse([row(footnote_state="none")]).rows[0].footnote_state == "none"
    assert parse([row(footnote_state="unknown")]).rows[0].footnote_state == "unknown"


def test_missing_footnote_key_and_contradictory_footnotes_cannot_be_silently_completed():
    missing = row()
    del missing["footnote_state"]
    assert_rejected(parse([missing]), code="MISSING_FIELD", field="footnote_state")
    for changes in ({"footnote_state": "present"}, {"footnote_text": "DEMO note"},
                    {"footnote_state": "present", "footnote_text": ""}):
        assert_rejected(parse([row(**changes)]), code="INVALID_FOOTNOTE")


def test_csv_blank_na_and_null_token_do_not_coerce_values_or_nullable_text():
    assert_rejected(parse([row(unit="")], format="csv"), field="unit")
    assert parse([row(unit="NA", value_text="0")], format="csv").rows[0].unit == "NA"
    missing = parse([row(value_text=None, missing_reason="unavailable")], format="csv")
    assert missing.rows[0].value_text is None
    assert_rejected(parse([row(source_record_reference="\\N")], format="csv"))


@pytest.mark.parametrize("changes", [
    {"entry_year": True}, {"entry_year": 0}, {"entry_year": 10000},
    {"offering_version": "1"}, {"offering_version": 2147483648},
])
def test_json_metadata_is_strict_bounded_integer(changes):
    assert_rejected(parse([row(**changes)]), code="INVALID_INTEGER")


def test_csv_metadata_uses_exact_positive_integer_lexemes():
    for invalid in ("01", "+1", " 1", "1.0", "1e0", "0", "-1"):
        assert_rejected(parse([row(offering_version=invalid)], format="csv"), code="INVALID_INTEGER")
    assert parse([row(offering_version=2147483647)], format="csv").rows[0].offering_version == 2147483647


def test_uuid_references_are_explicit_canonical_and_not_guessed():
    identifier = str(uuid4())
    for invalid in (identifier.upper(), "{" + identifier + "}", "urn:uuid:" + identifier, True,
                    "DEMO_school_name", identifier.replace("-", "")):
        assert_rejected(parse([row(offering_id=invalid)]), code="INVALID_UUID")


def test_json_extra_fields_and_nested_injection_never_enter_candidate_or_error_details():
    injected = row(owner_user_id="DEMO_private-secret", reviewed=True, rule={"exec": "DEMO_private-secret"})
    assert_rejected(parse([injected]), code="UNEXPECTED_FIELD", field="document")
    assert "secret" not in parse([injected]).model_dump_json()
    assert_rejected(parse([row(value_text={"instruction": "DEMO_private-secret"})]), field="value_text")
    assert_rejected(parse(["DEMO_private-secret"]), code="INVALID_STRUCTURE", row_number=1)


def test_duplicate_json_keys_are_document_errors_without_retaining_keys_or_values():
    value = b'[{"DEMO_private-secret":1,"DEMO_private-secret":2}]'
    result = parse_structured_import(value, format="json")
    assert_rejected(result, code="DUPLICATE_KEY", row_number=0)
    assert result.total_rows is None and "secret" not in result.model_dump_json()


@pytest.mark.parametrize("payload", [b'{}', b'[NaN]', b'[Infinity]', b'[1.0]', b'[' + b'9' * 10000 + b']', b'[{'])
def test_json_invalid_structure_nonfinite_or_unbounded_numeric_tokens_fail_closed(payload):
    result = parse_structured_import(payload, format="json")
    assert_rejected(result, code="INVALID_STRUCTURE", row_number=0)
    assert result.total_rows is None


def test_json_lexical_bounds_handle_escaped_braces_and_reject_deep_or_many_nodes():
    assert parse([row(value_kind="text", value_text='[{"escaped": "\\\\\"}]')]).rows
    for payload in (b'[' * 33 + b'0' + b']' * 33, b'[' + b','.join([b'0'] * 10001) + b']'):
        assert_rejected(parse_structured_import(payload, format="json"), row_number=0)


@pytest.mark.parametrize("header", [ROW_FIELDS[::-1], ROW_FIELDS[:-1], (*ROW_FIELDS[:-1], "owner_user_id"), (*ROW_FIELDS[:-1], ROW_FIELDS[0])])
def test_csv_requires_exact_complete_unique_header(header):
    output = io.StringIO(newline="")
    csv.writer(output).writerow(header)
    assert_rejected(parse_structured_import(output.getvalue().encode(), format="csv"), code="INVALID_HEADER", row_number=0)


def test_csv_wrong_column_counts_and_unclosed_quotes_do_not_pad_or_keep_good_rows():
    payload = csv_input([row()]) + b'only,three,columns\r\n'
    result = parse_structured_import(payload, format="csv")
    assert_rejected(result, row_number=3)
    assert result.total_rows == 2
    assert_rejected(parse_structured_import(csv_input([]) + b'"unterminated', format="csv"), row_number=0)


def test_empty_and_encoding_failures_have_honest_known_or_unknown_counts():
    for format, payload in (("json", b'[]'), ("csv", csv_input([]))):
        result = parse_structured_import(payload, format=format)
        assert_rejected(result, code="EMPTY_IMPORT", row_number=0)
        assert result.total_rows == 0
    assert_rejected(parse_structured_import(b'\xff', format="json"), code="INVALID_ENCODING")
    for invalid in (bytearray(b'[]'), "[]", b''):
        assert_rejected(parse_structured_import(invalid, format="json"), code="INVALID_STRUCTURE")
    assert_rejected(parse_structured_import(b'[]', format="pdf"), code="INVALID_STRUCTURE")


def test_byte_field_and_row_limits_use_utf8_and_never_silently_truncate():
    assert parse([row(value_kind="text", value_text="😀" * (MAX_FIELD_BYTES // 4))]).rows
    assert_rejected(parse([row(value_kind="text", value_text="😀" * (MAX_FIELD_BYTES // 4 + 1))]), code="FIELD_TOO_LARGE")
    valid = json_input([row()])
    assert parse_structured_import(valid + b' ' * (MAX_IMPORT_BYTES - len(valid)), format="json").rows
    assert_rejected(parse_structured_import(valid + b' ' * (MAX_IMPORT_BYTES - len(valid) + 1), format="json"), code="INPUT_TOO_LARGE")
    for format in ("json", "csv"):
        assert len(parse([row() for _ in range(MAX_IMPORT_ROWS)], format=format).rows) == MAX_IMPORT_ROWS
        result = parse([row() for _ in range(MAX_IMPORT_ROWS + 1)], format=format)
        assert_rejected(result, code="TOO_MANY_ROWS", row_number=0)
        assert result.total_rows is None


def test_surrogates_controls_and_unicode_identifier_codes_are_not_accepted():
    for changes in ({"value_kind": "text", "value_text": "\ud800"},
                    {"unit": "DEMO\x00secret"}, {"source_record_reference": "DEMO_学校"},
                    {"field_key": "minimum\n"}):
        payload = json.dumps([row(**changes)], ensure_ascii=True).encode()
        result = parse_structured_import(payload, format="json")
        assert_rejected(result)
        assert "secret" not in result.model_dump_json()


def test_namespace_requires_server_context_and_rejects_forged_models():
    candidate = CandidateInput(**row())
    candidate.validate_namespace(True)
    with pytest.raises(ValueError):
        candidate.validate_namespace(False)
    for value in ("demo_record", "DeMo_record"):
        with pytest.raises(ValueError):
            CandidateInput(**row(source_record_reference=value)).validate_namespace(False)
    for forged in (candidate.model_copy(update={"offering_version": True}),
                   CandidateInput.model_construct(**{**candidate.model_dump(), "footnote_state": "present"})):
        with pytest.raises(ValidationError):
            CandidateInput.model_validate(forged)
    with pytest.raises(ValidationError):
        candidate.value_text = "1"


def test_closed_policy_request_and_result_revalidate_unsafe_copies_and_counts():
    assert ImportsPolicy().model_dump() == {"enabled": False, "real_imports_ready": False}
    request = ImportRequest(dataset_id=uuid4(), source_id=uuid4(), source_version=1, file_id=uuid4(), file_sha256="a" * 64, format="json")
    with pytest.raises(ValidationError):
        ImportRequest.model_validate(request.model_copy(update={"source_version": True}))
    with pytest.raises(ValidationError):
        ImportRequest(**{**request.model_dump(), "owner_user_id": uuid4()})
    error = RowError(row_number=1, field="offering_id", code="SCOPE_MISMATCH")
    result = ImportResult(id=uuid4(), status="rejected", total_rows=1, staged_rows=0, error_count=1, errors=(error,), replayed=False)
    for changes in ({"staged_rows": 1}, {"error_count": 0}, {"status": "staged"}, {"replayed": 1}):
        with pytest.raises(ValidationError):
            ImportResult.model_validate(result.model_copy(update=changes))
    with pytest.raises(ValidationError):
        RowError(row_number=1, field="DEMO_secret", code="arbitrary")
    with pytest.raises(ValidationError):
        ParsedImport(rows=(ParsedRow(**row(), row_number=1),), errors=(error,), total_rows=1)
    assert str(ImportServiceError(500, "DEMO_secret")) == "IMPORT_UNAVAILABLE"


def test_parse_result_copies_cannot_forge_logical_positions_or_structure_counts():
    parsed = parse([row(), row()])
    for rows in ((parsed.rows[1], parsed.rows[0]),
                 (parsed.rows[0].model_copy(update={"row_number": 99}), parsed.rows[1])):
        with pytest.raises(ValidationError):
            ParsedImport.model_validate(parsed.model_copy(update={"rows": rows}))
    error = RowError(row_number=99, field="offering_id", code="SCOPE_MISMATCH")
    with pytest.raises(ValidationError):
        ImportResult(id=uuid4(), status="rejected", total_rows=1, staged_rows=0,
                     error_count=1, errors=(error,), replayed=False)
    with pytest.raises(ValidationError):
        ParsedImport(rows=(), errors=(RowError(row_number=1, field="document", code="INVALID_STRUCTURE"),), total_rows=None)


def test_generated_error_models_and_policy_revalidate_constructed_instances():
    for forged in (RowError.model_construct(row_number=0, field="owner_user_id", code="INVALID_FIELD"),
                   RowError.model_construct(row_number=True, field="document", code="INVALID_STRUCTURE")):
        with pytest.raises(ValidationError):
            ParsedImport(rows=(), errors=(forged,), total_rows=None)
    with pytest.raises(ValidationError):
        ImportsPolicy.model_validate(ImportsPolicy.model_construct(enabled="true", real_imports_ready=False))


def test_fresh_import_and_parsing_do_not_initialize_database_network_or_global_csv_options():
    program = '''
import csv, sys
initial = csv.field_size_limit()
from app.ingestion.schemas import ImportsPolicy
from app.ingestion.structured import parse_structured_import
assert not ImportsPolicy().enabled
assert parse_structured_import(b'[]', format='json').errors
assert csv.field_size_limit() == initial
assert not any(name.startswith(('sqlalchemy', 'httpx', 'app.auth', 'app.storage',
                               'app.main', 'app.admin', 'app.providers', 'app.idempotency'))
               for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-B", "-c", program], capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": "services/api", "IMPORTS_ENABLED": "true"})
    assert result.returncode == 0, result.stderr
