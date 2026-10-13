"""Fixed DEMO content goldens and integrity failures, never publication proof."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.verify_qa_golden import (
    DEFAULT_PATH, GOLDEN_SHA256, MANIFEST, MAX_BYTES, ROOT, GoldenError,
    load_golden, main, validate_golden, verify_golden,
)


@pytest.fixture
def golden():
    return load_golden()


def test_fixed_inputs_and_independent_outcomes_match_all_24(golden):
    original = deepcopy(golden)
    report = verify_golden(golden)
    assert report == {
        "schema_version": "T38_EVAL_REPORT_V1", "fixture_only": True,
        "current_authority_established": False, "manual_domain_review_completed": False,
        "sample_count": 24, "matched_count": 24, "accepted_count": 8,
        "rejected_count": 16, "unknown_accepted_count": 1, "failed_case_ids": [],
    }
    assert golden == original
    assert len(MANIFEST) == 24


def test_fixed_atom_includes_precision_units_footnotes_and_statistical_meaning(golden):
    atoms = {item["id"]: json.loads(item["expected_atom"]["value"])
        for item in golden["fixtures"] if item["expected_atom"] is not None}
    assert atoms["DEMO_score"]["value_text"] == "600.1234567890123456789012345678901234567890123456789012345678901234"
    assert atoms["DEMO_fee"]["unit"] == "元"
    assert atoms["DEMO_fee"]["unit_code"] == "CNY"
    assert atoms["DEMO_historical"]["claim_kind"] == "historical_statistic"
    assert atoms["DEMO_historical"]["cohort_year"] == 2026
    assert atoms["DEMO_historical"]["statistic_denominator"] == "DEMO_该项目录取学生人数"
    assert atoms["DEMO_historical"]["footnote_text"] == "DEMO_历史统计不是当前最低要求。"
    assert atoms["DEMO_date_only"]["date_resolution"]["local_time"] is None
    candidate = atoms["DEMO_date_candidate"]["date_resolution"]
    assert candidate["precision"] == "minute"
    assert candidate["calculated_utc_instant"] == "2027-01-15T16:30:00Z"
    assert candidate["utc_instant"] is None
    assert all("evidence_id" not in atom for atom in atoms.values())


@pytest.mark.parametrize("field,value", [
    ("is_synthetic", False), ("fixture_only", 1),
    ("current_authority_established", True), ("manual_domain_review_completed", True),
])
def test_fixture_markers_cannot_claim_real_authority_or_review(golden, field, value):
    golden[field] = value
    with pytest.raises(GoldenError, match="^INVALID_QA_GOLDEN$"):
        validate_golden(golden)


@pytest.mark.parametrize("mutation", ["flip", "unknown_label", "unknown_error", "remove_case", "duplicate_case"])
def test_expected_labels_and_sample_denominator_cannot_be_rewritten(golden, mutation):
    if mutation == "flip":
        golden["cases"][2]["expected"] = {"accepted": True, "error_code": None, "answer_status": "answered"}
    elif mutation == "unknown_label":
        golden["cases"][0]["scenario"] = "probably_eligible"
    elif mutation == "unknown_error":
        golden["cases"][2]["expected"]["error_code"] = "MODEL_APPROVED"
    elif mutation == "remove_case":
        golden["cases"].pop()
    else:
        golden["cases"][1] = deepcopy(golden["cases"][0])
    with pytest.raises(GoldenError):
        validate_golden(golden)


@pytest.mark.parametrize("mutation", ["private_key", "unknown_reason", "tool_advice", "extra_scope", "fake_official_utc"])
def test_closed_fixture_surface_rejects_tool_private_and_inferred_data(golden, mutation):
    if mutation == "private_key":
        golden["fixtures"][0]["fact"]["student_id"] = "SENTINEL_PRIVATE"
    elif mutation == "unknown_reason":
        golden["cases"][11]["unknown_reasons"] = ["MODEL_CONFIDENCE"]
    elif mutation == "tool_advice":
        golden["cases"][0]["answer"]["advice_codes"] = ["EXECUTE_SQL"]
    elif mutation == "extra_scope":
        golden["scope"]["owner_id"] = "SENTINEL_OWNER"
    else:
        golden["fixtures"][4]["fact"]["date_resolution"]["utc_instant"] = "2027-01-15T23:59:00Z"
    with pytest.raises(GoldenError):
        validate_golden(golden)


def test_changed_fixed_atom_cannot_validate_itself_using_projection_helper(golden):
    # The expected atom is independent of atom_value: a shape-valid fixed string
    # changed on its own is caught before outcome totals can falsely pass.
    golden["fixtures"][2]["expected_atom"]["value"] = golden["fixtures"][2]["expected_atom"]["value"].replace('"元"', '"万元"')
    with pytest.raises(GoldenError):
        verify_golden(golden)


def test_whole_answer_and_unknown_are_explicit_fixed_goldens(golden):
    cases = {case["id"]: case for case in golden["cases"]}
    mixed = cases["DEMO_22_all_or_nothing"]
    assert len(mixed["answer"]["claims"]) == 2
    assert mixed["expected"] == {"accepted": False, "error_code": "CITATION_CONFLICT", "answer_status": None}
    unknown = cases["DEMO_12_unknown"]
    assert unknown["answer"] == {"status": "unknown", "claims": [], "advice_codes": ["MISSING_EVIDENCE"]}
    assert unknown["expected"]["accepted"] is True


def test_fixture_bytes_are_pinned_and_changed_quote_rejected(tmp_path, golden):
    assert sha256(DEFAULT_PATH.read_bytes()).hexdigest() == GOLDEN_SHA256
    golden["fixtures"][0]["quote"] += "SENTINEL_CHANGED"
    target = tmp_path / "changed.json"
    target.write_text(json.dumps(golden, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(GoldenError):
        load_golden(target)


@pytest.mark.parametrize("raw", [b'{"task_id":"T38","task_id":"T38"}', b'{"n":NaN}', b'{"n":Infinity}', b'\xff'])
def test_json_duplicate_nonfinite_and_invalid_utf8_rejected_before_inputs(raw, tmp_path):
    target = tmp_path / "invalid.json"
    target.write_bytes(raw)
    with pytest.raises(GoldenError):
        load_golden(target, verify_digest=False)


@pytest.mark.parametrize("mutation", ["bytes", "depth", "oversized_text", "float", "lone_surrogate"])
def test_loader_and_native_fixture_budgets_are_bounded(golden, tmp_path, mutation):
    if mutation == "bytes":
        target = tmp_path / "large.json"
        target.write_bytes(b" " * (MAX_BYTES + 1))
        with pytest.raises(GoldenError):
            load_golden(target, verify_digest=False)
        return
    if mutation == "depth":
        nested = None
        for _ in range(22):
            nested = [nested]
        golden["extra"] = nested
    elif mutation == "oversized_text":
        golden["fixtures"][0]["quote"] = "DEMO_" + "x" * 4096
    elif mutation == "float":
        golden["target"]["entry_year"] = 2027.0
    else:
        golden["fixtures"][0]["quote"] = "DEMO_\ud800"
    with pytest.raises(GoldenError):
        validate_golden(golden)


def test_cli_bad_fixture_output_never_echoes_raw_input_or_path(tmp_path, capsys):
    target = tmp_path / "SENTINEL_PATH.json"
    target.write_text('{"SENTINEL_RAW":"private"}', encoding="utf-8")
    assert main(["--file", str(target)]) == 1
    output = capsys.readouterr().out
    assert json.loads(output) == {"error_code": "INVALID_QA_GOLDEN", "fixture_only": True}
    assert "SENTINEL" not in output


def test_fresh_process_cli_is_offline_without_retriever_model_or_sql():
    code = """
import runpy, socket, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'services/api'))
def forbidden(*args, **kwargs):
    raise AssertionError('external authority was invoked')
socket.create_connection = forbidden
socket.socket.connect = forbidden
import sqlalchemy
sqlalchemy.create_engine = forbidden
from app.qa import retrieval
retrieval.ScopedRetriever.retrieve = forbidden
from app.model_gateway import gateway
gateway.ModelGateway.complete = forbidden
sys.argv = ['scripts/verify_qa_golden.py']
runpy.run_path('scripts/verify_qa_golden.py', run_name='__main__')
"""
    process = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False)
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["sample_count"] == report["matched_count"] == 24
    assert report["current_authority_established"] is False
