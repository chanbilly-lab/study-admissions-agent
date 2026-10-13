"""T38 fixed DEMO content goldens: offline, with no current-authority claim.

The JSON records explicit fixed inputs and expected outcomes. Projection helpers
construct typed fixtures; their output is compared with the separately fixed atom
strings. validate_claims checks content only. No retriever, DB or model is called.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, time
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/evals/qa/t38_golden.json"
GOLDEN_SHA256 = "6222ade648d9c8f65a2a221aeaa7608af1455e1506b3071d46d84ccdf9190e92"
MAX_BYTES = 131072
FIXTURE_IDS = ("DEMO_material", "DEMO_score", "DEMO_fee", "DEMO_historical",
               "DEMO_date_only", "DEMO_date_candidate", "DEMO_injection", "DEMO_missing")
# These expected labels are fixed independently of the verifier's answers.
MANIFEST = (
    ("DEMO_01_exact_text", "exact_text", True),
    ("DEMO_02_exact_decimal", "exact_decimal", True),
    ("DEMO_03_rounded_decimal", "wrong_number", False),
    ("DEMO_04_exact_fee", "exact_unit", True),
    ("DEMO_05_wrong_unit", "wrong_unit", False),
    ("DEMO_06_historical_preserved", "historical_meaning", True),
    ("DEMO_07_historical_promoted", "wrong_meaning", False),
    ("DEMO_08_date_only", "date_only", True),
    ("DEMO_09_invented_time", "invented_time", False),
    ("DEMO_10_candidate_preserved", "candidate_utc", True),
    ("DEMO_11_candidate_promoted", "official_utc", False),
    ("DEMO_12_unknown", "unknown_no_claim", True),
    ("DEMO_13_unknown_invented", "unknown_invented", False),
    ("DEMO_14_missing_citation", "missing_citation", False),
    ("DEMO_15_duplicate_citation", "duplicate_citation", False),
    ("DEMO_16_wrong_year", "wrong_year", False),
    ("DEMO_17_wrong_project", "wrong_project", False),
    ("DEMO_18_wrong_version", "wrong_version", False),
    ("DEMO_19_wrong_province", "wrong_scope", False),
    ("DEMO_20_source_injection_data", "injection_as_data", True),
    ("DEMO_21_source_injection_obeyed", "injection_obeyed", False),
    ("DEMO_22_all_or_nothing", "all_or_nothing", False),
    ("DEMO_23_replaced_pin", "changed_release", False),
    ("DEMO_24_changed_requirements", "changed_requirements", False),
)
CHANGES = {"none", "year", "project", "version", "province", "release", "requirements"}
UNKNOWNS = {"NO_MATCHING_FACTS", "VALUE_UNAVAILABLE", "DATE_UNRESOLVED"}
ADVICE = {"REVIEW_SOURCE", "CONFIRM_WITH_INSTITUTION", "MISSING_EVIDENCE"}
SCOPE_KEYS = ("degree", "course", "campus", "teaching_language", "progression_pathway",
    "intake", "application_cycle", "channel", "course_system", "pathway", "applicant_category",
    "province", "exam_system", "subject_scope", "batch_group")
FACT_KEYS = {"fact_type", "field_key", "value_kind", "value_text", "normalized_value", "unit",
    "missing_reason", "footnote_state", "footnote_text", "claim_kind", "unit_code", "period",
    "statistics_basis", "statistic_population", "statistic_denominator", "cohort_year",
    "survey_period", "evidence_id", "date_resolution"}
DATE_KEYS = {"event_type", "original_text", "precision", "local_date", "local_time", "timezone",
    "source_alignment", "conversion_status", "calculated_utc_instant", "utc_instant", "tzdata_version"}


class GoldenError(ValueError):
    def __init__(self):
        super().__init__("INVALID_QA_GOLDEN")


def _require(condition):
    if not condition:
        raise GoldenError()


def _object(value, keys):
    _require(type(value) is dict and set(value) == set(keys))


def _walk(value, *, depth=0, budget=None):
    budget = [0] if budget is None else budget
    budget[0] += 1
    _require(depth <= 20 and budget[0] <= 10000)
    kind = type(value)
    if kind is str:
        _require(len(value.encode("utf-8")) <= 4096)
    elif kind is int:
        _require(abs(value) <= 9007199254740991)
    elif kind not in {bool, type(None)}:
        _require(kind in {dict, list} and len(value) <= 100)
        if kind is dict:
            _require(all(type(key) is str for key in value))
            for key, item in value.items():
                _walk(key, depth=depth + 1, budget=budget)
                _walk(item, depth=depth + 1, budget=budget)
        else:
            for item in value:
                _walk(item, depth=depth + 1, budget=budget)


def _uuid(value):
    _require(type(value) is str)
    try:
        parsed = UUID(value)
        _require(str(parsed) == value and parsed.version == 4)
    except (ValueError, AttributeError):
        raise GoldenError() from None


def _hash(value):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)


def validate_golden(document):
    """Reject changed safety markers, expected labels, extra keys and budgets."""
    try:
        _walk(document)
        _object(document, {"schema_version", "task_id", "is_synthetic", "fixture_only",
            "current_authority_established", "manual_domain_review_completed", "target",
            "scope", "release", "retrieved_at", "fixtures", "cases"})
        _require(document["schema_version"] == "T38_GOLDEN_V1" and document["task_id"] == "T38")
        for field in ("is_synthetic", "fixture_only"):
            _require(document[field] is True)
        for field in ("current_authority_established", "manual_domain_review_completed"):
            _require(document[field] is False)
        _object(document["target"], {"offering_id", "offering_version", "entry_year"})
        _uuid(document["target"]["offering_id"])
        _require(type(document["target"]["offering_version"]) is int and document["target"]["offering_version"] == 1)
        _require(type(document["target"]["entry_year"]) is int and document["target"]["entry_year"] == 2027)
        scope = document["scope"]
        _object(scope, {"dataset_id", "institution_id", "program_id", "country", "study_level", "entry_year", *SCOPE_KEYS})
        for field in ("dataset_id", "institution_id", "program_id"):
            _uuid(scope[field])
        _require(scope["country"] == "CN" and scope["study_level"] == "undergraduate")
        _require(type(scope["entry_year"]) is int and scope["entry_year"] == document["target"]["entry_year"])
        for field in SCOPE_KEYS:
            _object(scope[field], {"status", "value"})
            _require(scope[field]["status"] == "known" and type(scope[field]["value"]) is str)
            _require(re.fullmatch(r"DEMO_[A-Za-z0-9_.:+-]{1,95}", scope[field]["value"]) is not None)
        _object(document["release"], {"id", "requirements_version", "content_sha256"})
        _uuid(document["release"]["id"])
        _hash(document["release"]["requirements_version"])
        _hash(document["release"]["content_sha256"])
        _require(document["retrieved_at"] == "2026-10-04T00:00:00Z")
        _require(type(document["fixtures"]) is list and len(document["fixtures"]) == len(FIXTURE_IDS))
        for fixture, fixture_id in zip(document["fixtures"], FIXTURE_IDS, strict=True):
            _object(fixture, {"id", "evidence_id", "fact", "quote", "expected_atom"})
            _require(fixture["id"] == fixture_id and type(fixture["quote"]) is str and fixture["quote"].startswith("DEMO_"))
            _uuid(fixture["evidence_id"])
            _object(fixture["fact"], FACT_KEYS)
            _require(fixture["fact"]["evidence_id"] == fixture["evidence_id"])
            _require(type(fixture["fact"].get("field_key")) is str and fixture["fact"]["field_key"].startswith("DEMO_"))
            if fixture["fact"]["date_resolution"] is not None:
                _object(fixture["fact"]["date_resolution"], DATE_KEYS)
                _require(fixture["fact"]["date_resolution"]["utc_instant"] is None)
            atom = fixture["expected_atom"]
            if atom is not None:
                _object(atom, {"kind", "value"})
                _require(type(atom["kind"]) is str and atom["kind"] in {"text", "number", "date"})
                _require(type(atom["value"]) is str and 0 < len(atom["value"]) <= 2000)
        _require(len({item["evidence_id"] for item in document["fixtures"]}) == len(FIXTURE_IDS))
        _require(type(document["cases"]) is list and len(document["cases"]) == len(MANIFEST))
        for case, (case_id, scenario, accepted) in zip(document["cases"], MANIFEST, strict=True):
            _object(case, {"id", "scenario", "fixture_ids", "current_fixture_ids", "current_change",
                "unknown_reasons", "answer", "expected"})
            _require(case["id"] == case_id and case["scenario"] == scenario)
            _require(type(case["current_change"]) is str and case["current_change"] in CHANGES)
            for field, allowed, maximum in (("fixture_ids", set(FIXTURE_IDS), 3),
                ("current_fixture_ids", set(FIXTURE_IDS), 3), ("unknown_reasons", UNKNOWNS, 3)):
                items = case[field]
                _require(type(items) is list and len(items) <= maximum and all(type(item) is str and item in allowed for item in items))
                _require(len(set(items)) == len(items))
            _object(case["answer"], {"status", "claims", "advice_codes"})
            _require(type(case["answer"]["status"]) is str and case["answer"]["status"] in {"answered", "unknown"})
            _require(type(case["answer"]["claims"]) is list and len(case["answer"]["claims"]) <= 3)
            for claim in case["answer"]["claims"]:
                _object(claim, {"citation", "value"})
                _require(type(claim["citation"]) is str)
                if claim["citation"] not in FIXTURE_IDS:
                    _uuid(claim["citation"])
                _require(type(claim["value"]) is str and 0 < len(claim["value"]) <= 2000)
            advice = case["answer"]["advice_codes"]
            _require(type(advice) is list and len(advice) <= 3 and all(type(item) is str and item in ADVICE for item in advice))
            _require(len(set(advice)) == len(advice))
            _object(case["expected"], {"accepted", "error_code", "answer_status"})
            _require(case["expected"]["accepted"] is accepted)
            _require(case["expected"]["error_code"] == (None if accepted else "CITATION_CONFLICT"))
            _require(case["expected"]["answer_status"] == (case["answer"]["status"] if accepted else None))
        return document
    except GoldenError:
        raise
    except Exception:
        raise GoldenError() from None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _nonfinite(_value):
    raise GoldenError()


def load_golden(path=DEFAULT_PATH, *, verify_digest=True):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        _require(len(raw) <= MAX_BYTES)
        if verify_digest:
            _require(sha256(raw).hexdigest() == GOLDEN_SHA256)
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite)
        return validate_golden(document)
    except GoldenError:
        raise
    except Exception:
        raise GoldenError() from None


def _native_fact(fact):
    value = deepcopy(fact)
    temporal = value["date_resolution"]
    if temporal is not None:
        for field, decoder in (("local_date", date.fromisoformat), ("local_time", time.fromisoformat)):
            if temporal[field] is not None:
                temporal[field] = decoder(temporal[field])
        for field in ("calculated_utc_instant", "utc_instant"):
            if temporal[field] is not None:
                temporal[field] = datetime.fromisoformat(temporal[field].replace("Z", "+00:00"))
    return value


def _bundle(document, case, *, current=False):
    from app.model_gateway.schemas import ModelScope
    from app.public_catalog.schemas import PublicEvidenceData, PublicFactData
    from app.qa.schemas import RetrievalRequest, bundle_from_public, citation_from_public

    scope, target, release = deepcopy(document["scope"]), deepcopy(document["target"]), deepcopy(document["release"])
    change = case["current_change"] if current else "none"
    if change == "year":
        scope["entry_year"] = target["entry_year"] = 2028
    elif change == "project":
        scope["program_id"] = "00000000-0000-4000-8000-000000000020"
        target["offering_id"] = "00000000-0000-4000-8000-000000000021"
    elif change == "version":
        target["offering_version"] = 2
    elif change == "province":
        scope["province"] = {"status": "known", "value": "DEMO_other_province"}
    elif change == "release":
        release["id"] = "00000000-0000-4000-8000-000000000022"
    elif change == "requirements":
        release["requirements_version"] = "3" * 64
    request = RetrievalRequest(release_id=release["id"], **target,
        scope={key: value for key, value in scope.items() if key != "dataset_id"}, intent="background", keywords=())
    model_scope = ModelScope(dataset_id=scope["dataset_id"], **target)
    citations = []
    aliases = {}
    included = case["current_fixture_ids"] if current else case["fixture_ids"]
    for fixture in document["fixtures"]:
        if fixture["id"] not in included:
            continue
        fact = PublicFactData.model_validate(_native_fact(fixture["fact"]))
        raw = fixture["quote"].encode("utf-8")
        evidence = PublicEvidenceData(evidence_id=fixture["evidence_id"], release_id=release["id"],
            release_version=1, requirements_version=release["requirements_version"], is_synthetic=True,
            **target, language="zh-Hans", quote=fixture["quote"], document_sha256=sha256(raw).hexdigest(),
            snippet_sha256=sha256(raw).hexdigest(), locator={"byte_start": 0, "byte_end": len(raw),
                "line_start": 1, "line_end": fixture["quote"].count("\n") + 1, "page": None,
                "section": None, "location_kind": "utf8_byte_lines"}, scope=scope,
            publisher="DEMO_GOLDEN_SOURCE", authority_claim="not_official")
        citation = citation_from_public(fact, evidence)
        citations.append(citation)
        aliases[fixture["id"]] = citation.id
    bundle = bundle_from_public(request, model_scope=model_scope, release_version=1,
        requirements_version=release["requirements_version"], content_sha256=release["content_sha256"],
        citations=tuple(citations), unknown_reasons=case["unknown_reasons"],
        retrieved_at=datetime.fromisoformat(document["retrieved_at"].replace("Z", "+00:00")), is_synthetic=True)
    fixed_atoms = {fixture["id"]: fixture["expected_atom"] for fixture in document["fixtures"]}
    for alias, citation_id in aliases.items():
        expected = fixed_atoms[alias]
        actual = next((atom for atom in bundle.atoms if atom.citation_id == citation_id), None)
        _require((actual is None) == (expected is None))
        if actual is not None:
            _require(actual.kind == expected["kind"] and actual.value == expected["value"])
    return bundle, aliases


def verify_golden(document):
    """Return the actual sample denominator and mismatches, without raw inputs."""
    validate_golden(document)
    sys.path.insert(0, str(ROOT / "services/api")) if str(ROOT / "services/api") not in sys.path else None
    from app.qa.schemas import QAError
    from app.qa.validation import validate_claims

    failures = []
    accepted_count = rejected_count = unknown_count = 0
    for case in document["cases"]:
        original, aliases = _bundle(document, case)
        current, _ = _bundle(document, case, current=True)
        answer = {"status": case["answer"]["status"], "claims": [
            {"citation_id": aliases.get(claim["citation"], claim["citation"]), "value": claim["value"]}
            for claim in case["answer"]["claims"]], "advice_codes": case["answer"]["advice_codes"]}
        try:
            result = validate_claims(original, answer, current_bundle=current)
            actual = {"accepted": True, "error_code": None, "answer_status": result.status}
            accepted_count += 1
            unknown_count += result.status == "unknown"
        except QAError as error:
            actual = {"accepted": False, "error_code": error.code, "answer_status": None}
            rejected_count += 1
        if actual != case["expected"]:
            failures.append(case["id"])
    return {"schema_version": "T38_EVAL_REPORT_V1", "fixture_only": True,
        "current_authority_established": False, "manual_domain_review_completed": False,
        "sample_count": len(document["cases"]), "matched_count": len(document["cases"]) - len(failures),
        "accepted_count": accepted_count, "rejected_count": rejected_count,
        "unknown_accepted_count": unknown_count, "failed_case_ids": failures}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)
    try:
        report = verify_golden(load_golden(args.file))
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return int(bool(report["failed_case_ids"]))
    except GoldenError:
        print(json.dumps({"error_code": "INVALID_QA_GOLDEN", "fixture_only": True}))
        return 1
    except Exception:
        print(json.dumps({"error_code": "QA_GOLDEN_UNAVAILABLE", "fixture_only": True}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
