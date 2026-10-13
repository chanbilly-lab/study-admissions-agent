"""Syntax and resource checks preserve bytes without asserting malware safety."""

import csv
from hashlib import sha256
import json

import pytest

from app.storage.schemas import MAX_FILE_BYTES, StorageError
from app.storage.validation import validate_upload


def upload(data, filename="DEMO_input.json", content_type="application/json"):
    return validate_upload(data, filename=filename, content_type=content_type)


@pytest.mark.parametrize("data,name,mime", [
    (b'%PDF-1.7\nDEMO shallow quarantine fixture\n%%EOF\n', "DEMO_document.pdf", "application/pdf"),
    ('name,value\r\nDEMO_学生,2\r\n'.encode(), "DEMO_成绩.csv", "text/csv"),
    (b'{"DEMO_name":"[brackets are text]","value":2}', "DEMO_input.json", "application/json"),
    (b'[]', "DEMO_empty_array.json", "application/json"),
])
def test_valid_formats_preserve_exact_hash(data, name, mime):
    result = upload(data, name, mime)
    assert result.media_type == mime
    assert result.size_bytes == len(data)
    assert result.sha256 == sha256(data).hexdigest()
    assert not any("path" in key for key in result.model_dump())


@pytest.mark.parametrize("filename", [
    "../DEMO_file.json", "DEMO\\file.json", "DEMO_file.json:payload", "NUL.json",
    "COM¹.json", "DEMO_file.json.", "DEMO_file.json ", "DEMO_file.json.exe",
    "DEMO_file\x00.json", "DEMO_file\n.json", "DEMO?.json", ".json",
])
def test_filename_injection_rejected(filename):
    with pytest.raises(StorageError) as caught:
        upload(b'{}', filename)
    assert caught.value.status_code == 422
    assert filename not in str(caught.value)


def test_mime_and_extension_cannot_override_actual_format():
    for data, filename, mime in [
        (b'{}', "DEMO_x.json", "application/pdf"),
        (b'{}', "DEMO_x.json", "application/json; charset=utf-8"),
        (b'not json', "DEMO_x.json", "application/json"),
        (b'%PDF-1.7\n%%EOF', "DEMO_x.csv", "text/csv"),
        (b'<!DOCTYPE html><html></html>', "DEMO_x.csv", "text/csv"),
        (b'PK\x03\x04archive', "DEMO_x.csv", "text/csv"),
        (b'MZbinary', "DEMO_x.csv", "text/csv"),
    ]:
        with pytest.raises(StorageError):
            upload(data, filename, mime)


def test_exact_ten_mib_and_one_byte_over():
    data = b'["' + b'x' * (MAX_FILE_BYTES - 4) + b'"]'
    assert len(data) == MAX_FILE_BYTES
    assert upload(data).size_bytes == MAX_FILE_BYTES
    with pytest.raises(StorageError) as caught:
        upload(data + b' ')
    assert caught.value.status_code == 413


def test_bytes_are_nonempty_exact_bytes():
    for value in (b'', bytearray(b'{}'), memoryview(b'{}'), '{}', None):
        with pytest.raises(StorageError):
            upload(value)


def test_text_is_strict_utf8_with_no_nul_or_binary_controls():
    for data in (b'{"x":"\xff"}', b'\xff,x\n', b'x,\x00\n', b'x,\x01\n'):
        with pytest.raises(StorageError):
            upload(data, "DEMO_x.csv" if data[:1] != b'{' else "DEMO_x.json",
                   "text/csv" if data[:1] != b'{' else "application/json")


def test_pdf_is_only_a_bounded_header_and_tail_check():
    for data in (b'%PDF-1.9\n%%EOF', b'%PDF-1.7\nno EOF', b'MZ%PDF-1.7\n%%EOF',
                 b'%PDF-1.7\n%%EOF\nappended content'):
        with pytest.raises(StorageError):
            upload(data, "DEMO_x.pdf", "application/pdf")
    # No parser, decompressor or scanner is invoked, even for an action-like body.
    assert upload(b'%PDF-2.0\n/JavaScript (quarantined text)\n%%EOF',
                  "DEMO_x.pdf", "application/pdf").media_type == "application/pdf"


def test_csv_bounds_and_no_global_field_limit_mutation():
    before = csv.field_size_limit()
    assert upload(b'x\n' + b'a' * 65_536 + b'\n', "DEMO_x.csv", "text/csv")
    for data in (b'x\n' + b'a' * 65_537 + b'\n', b','.join([b'x'] * 201) + b'\n',
                 b'x,y\n' * 50_001, b'x\n' * 100_001, b'a,"unterminated'):
        with pytest.raises(StorageError):
            upload(data, "DEMO_x.csv", "text/csv")
    assert csv.field_size_limit() == before


def test_json_duplicate_nonfinite_root_and_lone_surrogate_rejected():
    for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}',
                 b'1', b'"text"', b'null', b'{"x":"\\ud800"}'):
        with pytest.raises(StorageError):
            upload(data)


def test_json_depth_nodes_are_bounded_before_parser(monkeypatch):
    assert upload(b'[' * 32 + b'0' + b']' * 32)
    original = json.loads
    calls = []
    def counting(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(json, "loads", counting)
    for data in (b'[' * 33 + b'0' + b']' * 33, b'[' + b'0,' * 100_000 + b'0]'):
        with pytest.raises(StorageError):
            upload(data)
    assert calls == []


def test_csv_utf8_field_byte_bound_not_only_character_count():
    data = 'header\n'.encode() + ('学' * 21_846).encode() + b'\n'
    with pytest.raises(StorageError):
        upload(data, "DEMO_x.csv", "text/csv")
