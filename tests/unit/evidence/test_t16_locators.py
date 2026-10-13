"""Actual byte provenance, bounded locators and unapproved evidence DTOs."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from pydantic import ValidationError
import pytest

from app.admissions_catalog.schemas import ScopeKey
from app.evidence.locators import extract_snippet, validate_original
from app.evidence.schemas import (
    DocumentCreate, DocumentData, EvidenceError, EvidenceLocator, EvidencePolicy, EvidenceScope,
    LocatedSnippet, MAX_ORIGINAL_BYTES, MAX_SNIPPET_BYTES, OriginalData, SnippetCreate, SnippetData,
    VersionCreate, VersionData,
)


FIXTURE = Path(__file__).resolve().parents[3] / "data/fixtures/evidence/DEMO_T16_original.json"
MANUAL_REPORT = Path(__file__).resolve().parents[3] / "docs/acceptance/T16_manual_review.md"
NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
PROGRAM_FIELDS = ("degree", "course", "campus", "teaching_language", "progression_pathway")
OFFERING_FIELDS = ("intake", "application_cycle", "channel", "course_system", "pathway",
                   "applicant_category", "province", "exam_system", "subject_scope", "batch_group")


def scope(**changes):
    return EvidenceScope(dataset_id=uuid4(), program_id=uuid4(), institution_id=uuid4(), country="GB",
        study_level="undergraduate", entry_year=2026,
        **{name: ScopeKey(status="unknown", value=None) for name in (*PROGRAM_FIELDS, *OFFERING_FIELDS)},
        **changes)


def excerpt(data, text, *, media_type="application/json"):
    encoded = text.encode("utf-8")
    start = data.index(encoded)
    return extract_snippet(data, media_type=media_type, byte_start=start, byte_end=start + len(encoded))


def snippet_data():
    original = FIXTURE.read_bytes()
    located = excerpt(original, "DEMO_合成证据：仅测试定位，不是真实招生要求。")
    return SnippetData(**located.model_dump(), id=uuid4(), document_id=uuid4(), document_version=1,
        offering_id=uuid4(), offering_version=1, entry_year=2026, language="zh-Hans",
        document_sha256=sha256(original).hexdigest(), is_synthetic=True, created_at=NOW, scope=scope())


def test_actual_manual_fixture_hash_bytes_lines_and_report_match():
    data = FIXTURE.read_bytes()
    checked = validate_original(data, media_type="application/json")
    assert checked.size_bytes == 365
    assert checked.sha256 == "5edf7f71fc75d7ded528d25811520c8ef378b3f0bbead3aaf0f33f01408f298c"
    assert b"\r" not in data and data.endswith(b"\n")
    report = MANUAL_REPORT.read_text(encoding="utf-8")
    assert checked.sha256 in report
    for text, start, end, line, expected_hash in (
        ("DEMO_合成证据：仅测试定位，不是真实招生要求。", 81, 146, 4,
         "f2b076ddea78e9c1cca22ffd8db0adf0b2453fcf498734a8ea1cc156b08dd271"),
        ("DEMO_缺少成绩且没有已审核后补政策时，结果保持 unknown。", 165, 241, 5,
         "9a7dc68ecf2bdd30f8638d39cf29e495710bc075b9e475f860cdab52b79745b2"),
        ("DEMO_<script>do_not_execute()</script>", 323, 361, 7,
         "7d0522c0152475ced9cb9f1df5cb708a2a2fc657397ec4abc92d35f4c31c384c"),
    ):
        found = extract_snippet(data, media_type="application/json", byte_start=start, byte_end=end)
        assert found.text == text and found.snippet_sha256 == expected_hash
        assert found.locator.line_start == found.locator.line_end == line
        assert found.locator.page is None and found.locator.section is None
        assert expected_hash in report and text in report


def test_changed_original_creates_a_different_actual_hash_without_overwriting_bytes():
    original = FIXTURE.read_bytes()
    changed = original.replace(b"DEMO_T16_INSTITUTION", b"DEMO_T16_OTHER")
    assert validate_original(changed, media_type="application/json").sha256 != sha256(original).hexdigest()
    assert FIXTURE.read_bytes() == original


def test_original_json_and_csv_are_documents_not_t15_candidate_headers():
    for data, media in ((b'{"DEMO_message":"unapproved text"}', "application/json"),
                        (b'column_a,column_b\nDEMO_entry,unknown\n', "text/csv")):
        result = validate_original(data, media_type=media)
        assert result.sha256 == sha256(data).hexdigest() and result.size_bytes == len(data)


@pytest.mark.parametrize("media,data", [
    ("application/pdf", b'%PDF-1.7\nDEMO\n%%EOF'), ("text/html", b'<h1>DEMO</h1>'),
    ("application/json", b'%PDF-1.7\n%%EOF'), ("text/csv", b'<!doctype html><script>DEMO</script>'),
    ("application/json", b'{"x":1,"x":2}'), ("application/json", b'[NaN]'),
    ("application/json", b'{"x":"\xff"}'), ("text/csv", b'col\n"unterminated'),
])
def test_unsupported_or_invalid_original_never_receives_a_document_hash(media, data):
    with pytest.raises(EvidenceError) as error:
        validate_original(data, media_type=media)
    assert error.value.status_code == 422 and str(error.value) == "INVALID_EVIDENCE_INPUT"


def test_original_size_bounds_and_exact_native_bytes():
    minimum = b'{}'
    maximum = minimum + b' ' * (MAX_ORIGINAL_BYTES - len(minimum))
    assert validate_original(maximum, media_type="application/json").size_bytes == MAX_ORIGINAL_BYTES
    many_lines = minimum + b'\n' * (MAX_ORIGINAL_BYTES - len(minimum))
    last = extract_snippet(many_lines, media_type="application/json",
        byte_start=MAX_ORIGINAL_BYTES - 1, byte_end=MAX_ORIGINAL_BYTES)
    assert last.locator.line_start == last.locator.line_end == MAX_ORIGINAL_BYTES - 2
    for invalid in (maximum + b' ', b'', bytearray(minimum), "{}"):
        with pytest.raises(EvidenceError):
            validate_original(invalid, media_type="application/json")


def test_half_open_utf8_ranges_preserve_multibyte_text_whitespace_and_end_boundary():
    text = "  DEMO_汉字😀\t  "
    data = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    found = excerpt(data, "  DEMO_汉字😀")
    assert found.text == "  DEMO_汉字😀"
    assert found.snippet_sha256 == sha256(found.text.encode()).hexdigest()
    last = extract_snippet(data, media_type="application/json", byte_start=len(data) - 1, byte_end=len(data))
    assert last.text == "}" and last.locator.line_end == 1


def test_start_or_end_inside_a_utf8_codepoint_is_rejected():
    data = json.dumps({"text": "DEMO_😀"}, ensure_ascii=False).encode()
    start = data.index("😀".encode())
    for lo, hi in ((start + 1, start + 4), (start, start + 3), (start + 1, start + 3)):
        with pytest.raises(EvidenceError):
            extract_snippet(data, media_type="application/json", byte_start=lo, byte_end=hi)


@pytest.mark.parametrize("start,end", [(True, 2), (0, True), (0.0, 2), (0, "2"), (-1, 1), (1, 1), (1, 0), (0, 100)])
def test_offsets_are_exact_integers_and_a_nonempty_existing_span(start, end):
    with pytest.raises(EvidenceError):
        extract_snippet(b'{}', media_type="application/json", byte_start=start, byte_end=end)


def test_snippet_cap_is_utf8_bytes_and_not_character_count():
    for text in ("A" * MAX_SNIPPET_BYTES, "😀" * (MAX_SNIPPET_BYTES // 4)):
        data = json.dumps({"text": text}, ensure_ascii=False).encode()
        assert len(excerpt(data, text).text.encode()) == MAX_SNIPPET_BYTES
    text = "😀" * (MAX_SNIPPET_BYTES // 4 + 1)
    with pytest.raises(EvidenceError):
        excerpt(json.dumps({"text": text}, ensure_ascii=False).encode(), text)


def test_physical_lines_keep_crlf_single_and_lone_cr_boundaries_not_csv_records():
    data = b'heading,value\r\n"DEMO_first\r\nDEMO_second",x\rend,z\n'
    found = excerpt(data, "DEMO_first\r\nDEMO_second", media_type="text/csv")
    assert (found.locator.line_start, found.locator.line_end) == (2, 3)
    assert excerpt(data, "end", media_type="text/csv").locator.line_start == 4
    newline = data.index(b'\r\n')
    for lo, hi in ((newline, newline + 2), (newline + 1, newline + 2)):
        fragment = extract_snippet(data, media_type="text/csv", byte_start=lo, byte_end=hi)
        assert (fragment.locator.line_start, fragment.locator.line_end) == (1, 1)


def test_trailing_newline_belongs_to_its_original_line_and_unicode_is_not_a_byte_newline():
    data = b'col\nDEMO_value\n'
    found = extract_snippet(data, media_type="text/csv", byte_start=len(data) - 1, byte_end=len(data))
    assert found.text == "\n" and found.locator.line_start == found.locator.line_end == 2
    text = "DEMO_a\u2028b"
    assert excerpt(json.dumps({"x": text}, ensure_ascii=False).encode(), text).locator.line_end == 1


def test_locator_dto_rejects_pages_sections_and_contradictory_spans():
    located = excerpt(FIXTURE.read_bytes(), "DEMO_T16_INSTITUTION")
    for changes in ({"page": 1}, {"section": "DEMO_heading"}, {"location_kind": "pdf_page"},
                    {"byte_start": True}, {"line_start": 99}, {"byte_end": located.locator.byte_start}):
        with pytest.raises(ValidationError):
            EvidenceLocator.model_validate(located.locator.model_copy(update=changes))


def test_locator_rejects_unreachable_physical_lines_in_copies_and_constructs():
    locator = EvidenceLocator(byte_start=10, byte_end=13, line_start=1, line_end=1,
        page=None, section=None, location_kind="utf8_byte_lines")
    for changes in ({"line_start": 12, "line_end": 12}, {"line_end": 14}, {"line_end": 4}):
        for forged in (locator.model_copy(update=changes),
                       EvidenceLocator.model_construct(**{**locator.model_dump(), **changes})):
            with pytest.raises(ValidationError):
                EvidenceLocator.model_validate(forged)


def test_located_text_hash_span_and_nested_constructs_are_revalidated():
    found = excerpt(FIXTURE.read_bytes(), "DEMO_T16_INSTITUTION")
    for changes in ({"text": "DEMO_other"}, {"snippet_sha256": "a" * 64},
                    {"locator": found.locator.model_copy(update={"byte_end": found.locator.byte_end + 1})},
                    {"text": "\ud800"}):
        with pytest.raises(ValidationError):
            LocatedSnippet.model_validate(found.model_copy(update=changes))
    with pytest.raises(ValidationError):
        LocatedSnippet.model_validate(LocatedSnippet.model_construct(**{**found.model_dump(), "snippet_sha256": "bad"}))


def test_document_namespace_language_explicit_identity_and_optimistic_version_contracts():
    create = DocumentCreate(dataset_id=uuid4(), source_id=uuid4(), source_version=1,
        document_reference="DEMO_document", language="und")
    create.validate_namespace(True)
    with pytest.raises(ValueError):
        create.validate_namespace(False)
    for reference in ("demo_document", "DeMo_document"):
        with pytest.raises(ValueError):
            DocumentCreate(**{**create.model_dump(), "document_reference": reference}).validate_namespace(False)
    with pytest.raises(ValidationError):
        DocumentCreate(**{**create.model_dump(), "language": "auto"})
    document = DocumentData(**create.model_dump(), id=uuid4(), is_synthetic=True, current_version=0, created_at=NOW)
    assert document.current_version == 0
    version = VersionCreate(document_id=document.id, expected_current_version=0, file_id=uuid4(), file_sha256="a" * 64)
    for forged in (version.model_copy(update={"expected_current_version": True}),
                   VersionCreate.model_construct(**{**version.model_dump(), "file_id": "DEMO_guess"})):
        with pytest.raises(ValidationError):
            VersionCreate.model_validate(forged)


def test_snippet_output_keeps_every_unknown_scope_and_does_not_expose_storage_identity():
    value = snippet_data()
    assert all(getattr(value.scope, field).status == "unknown" for field in (*PROGRAM_FIELDS, *OFFERING_FIELDS))
    for extra in ({"file_id": uuid4()}, {"path": "DEMO_private"}, {"owner_user_id": uuid4()}, {"reviewed": True}):
        with pytest.raises(ValidationError):
            SnippetData(**{**value.model_dump(), **extra})
    for forged in (value.model_copy(update={"entry_year": 2027}),
                   value.model_copy(update={"scope": value.scope.model_copy(update={"province": ScopeKey.model_construct(status="unknown", value="DEMO_guess")})})):
        with pytest.raises(ValidationError):
            SnippetData.model_validate(forged)


def test_server_timestamps_are_native_aware_and_safe_on_calendar_overflow():
    value = snippet_data()
    local = NOW.astimezone(timezone(timedelta(hours=8)))
    assert SnippetData(**{**value.model_dump(), "created_at": local}).created_at == NOW
    for invalid in (NOW.replace(tzinfo=None), NOW.replace(fold=1), "2026-10-03T00:00:00Z",
                    datetime.max.replace(tzinfo=timezone(timedelta(hours=-1)))):
        with pytest.raises(ValidationError):
            SnippetData(**{**value.model_dump(), "created_at": invalid})


def test_version_and_span_dtos_are_bounded_frozen_and_have_no_fake_approval():
    version = VersionData(id=uuid4(), document_id=uuid4(), version=1, document_sha256="a" * 64,
        size_bytes=2, media_type="application/json", is_synthetic=True, created_at=NOW)
    for changes in ({"version": 0}, {"version": True}, {"media_type": "application/pdf"}, {"is_synthetic": 1}):
        with pytest.raises(ValidationError):
            VersionData.model_validate(version.model_copy(update=changes))
    with pytest.raises(ValidationError):
        version.document_sha256 = "b" * 64
    for changes in ({"byte_start": True}, {"byte_end": MAX_SNIPPET_BYTES + 1}, {"document_version": 0}):
        with pytest.raises(ValidationError):
            SnippetCreate(**{**dict(document_id=uuid4(), document_version=1, offering_id=uuid4(),
                offering_version=1, entry_year=2026, byte_start=0, byte_end=1), **changes})
    assert set(OriginalData(size_bytes=2, sha256="a" * 64, media_type="application/json").model_dump()) == {"size_bytes", "sha256", "media_type"}
    assert "reviewed" not in version.model_dump()


def test_fresh_module_import_and_closed_policy_do_not_initialize_runtime_or_mutate_csv_globals():
    program = '''
import csv, sys
initial = csv.field_size_limit()
from app.evidence.schemas import EvidencePolicy
from app.evidence.locators import validate_original
assert EvidencePolicy().model_dump() == {'enabled':False,'real_evidence_ready':False}
assert validate_original(b'{}', media_type='application/json').size_bytes == 2
assert csv.field_size_limit() == initial
assert not any(name.startswith(('sqlalchemy','httpx','app.auth','app.audit','app.main','app.providers')) for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-B", "-c", program], capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": "services/api", "EVIDENCE_ENABLED": "true"})
    assert result.returncode == 0, result.stderr
    assert str(EvidenceError(500, "DEMO_secret")) == "EVIDENCE_UNAVAILABLE"
