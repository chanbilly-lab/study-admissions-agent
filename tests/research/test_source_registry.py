"""Offline contract boundaries using small invented candidates, not real facts."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from scripts.verify_source_registry import RegistryError, load_registry, main, validate_registry


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify_source_registry.py"
MAINLAND_NAMES = (
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
)
TYPES = ("institution_directory", "province_cutoff", "score_distribution", "admission_statistics", "admission_policy", "curriculum", "outcomes")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Source registry tests must never access the network")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.fixture
def registry():
    source = {
        "id": "test_authority", "publisher": "离线测试发布者", "title": "测试候选入口",
        "url": "http://exam.example.edu/admissions", "hostname": "exam.example.edu",
        "source_role": "authority_entry", "region_keys": ["cn_region_01"],
        "dataset_types": ["province_cutoff"], "pathways": ["ordinary_gaokao"],
        "identity_basis_url": "https://directory.example.edu/links", "identity_basis_locator": "测试链接表第一行",
        "observed_period_label": None, "time_basis": "unknown", "source_year": None,
        "year_mapping_status": "unverified", "year_basis_url": None,
        "access_status": "linked_not_opened", "checked_on": "2026-10-01", "failure_reason": None,
        "review_status": "review_required", "publication_status": "not_released", "rights_status": "not_reviewed",
        "review_owner": None, "automated_fetch_enabled": False, "affects_eligibility": False,
        "snapshot_status": "not_captured", "snapshot_sha256": None, "is_synthetic": False,
        "notes": "仅离线边界夹具；未访问URL，不表示真实机构或官方事实。",
    }
    regions = [
        {"region_key": f"cn_region_{number:02d}", "region_name": name, "region_kind": "mainland_province",
         "ordinary_gaokao_applicability": "applicable", "pathways": ["ordinary_gaokao", "institution_reference"],
         "authority_source_ids": [source["id"]] if number == 1 else [], "institution_directory_source_ids": []}
        for number, name in enumerate(MAINLAND_NAMES, 1)
    ]
    for key, name, kind in (("hk", "香港", "hong_kong"), ("mo", "澳门", "macau"), ("tw", "台湾", "taiwan")):
        regions.append({"region_key": key, "region_name": name, "region_kind": kind,
                        "ordinary_gaokao_applicability": "not_applicable", "pathways": [f"{key}_local_admissions", "institution_reference"],
                        "authority_source_ids": [], "institution_directory_source_ids": []})
    units = []
    for region in regions:
        key = region["region_key"]
        for kind in TYPES:
            inapplicable = key in {"hk", "mo", "tw"} and kind in {"province_cutoff", "score_distribution"}
            if kind in {"institution_directory", "curriculum", "outcomes"}:
                pathway = "institution_reference"
            elif key.startswith("cn_region_") or inapplicable:
                pathway = "ordinary_gaokao"
            else:
                pathway = f"{key}_local_admissions"
            refs = [source["id"]] if key == "cn_region_01" and kind == "province_cutoff" else []
            units.append({"region_key": key, "dataset_type": kind, "pathway": pathway, "candidate_source_ids": refs,
                          "missing_reason": "not_applicable" if inapplicable else "source_candidate_only" if refs else "not_collected",
                          "expected_total": None, "coverage_ratio": None})
    return {
        "schema": "study.research.source-registry.v1", "task_id": "T50A", "target_reference_year": 2026,
        "registered_as_of": "2026-10-01", "timezone": "Asia/Hong_Kong", "candidate_only": True,
        "is_synthetic": False, "nationwide_collection_complete": False, "reviewed_fact_count": 0,
        "published_fact_count": 0, "imported_institution_count": 0, "expected_total": None, "coverage_ratio": None,
        "personalized_scope": "one_configured_province_ordinary_gaokao_plus_uk_undergraduate",
        "sources": [source], "regions": regions, "coverage_units": units,
    }


def unit(data, region_key, dataset_type):
    return next(item for item in data["coverage_units"] if item["region_key"] == region_key and item["dataset_type"] == dataset_type)


def test_valid_registry_preserves_input_and_never_claims_fact_coverage(registry):
    before = deepcopy(registry)
    summary = validate_registry(registry)
    assert registry == before
    assert summary == {"task_id": "T50A", "source_candidates": 1, "regions": 34, "coverage_units": 238,
                       "units_with_candidates": 1, "reviewed_fact_count": 0, "published_fact_count": 0,
                       "imported_institution_count": 0, "expected_total": None, "coverage_ratio": None, "candidate_only": True}


@pytest.mark.parametrize("field,value", [
    ("target_reference_year", True), ("target_reference_year", "2026"),
    ("reviewed_fact_count", False), ("published_fact_count", 1), ("imported_institution_count", 1),
    ("candidate_only", 1), ("is_synthetic", True), ("nationwide_collection_complete", True),
    ("expected_total", 100), ("coverage_ratio", 0), ("registered_as_of", "2027-01-01"),
    ("personalized_scope", "nationwide_gaokao"),
])
def test_rejects_false_root_claims_and_boolean_numbers(registry, field, value):
    registry[field] = value
    with pytest.raises(RegistryError, match=field):
        validate_registry(registry)


@pytest.mark.parametrize("container,extra", [("root", "student_profile"), ("source", "cutoff_score"),
                                            ("source", "target_reference_year"), ("region", "published_count"), ("unit", "employment_rate")])
def test_rejects_extra_fact_private_and_uncontracted_fields(registry, container, extra):
    item = {"root": registry, "source": registry["sources"][0], "region": registry["regions"][0], "unit": registry["coverage_units"][0]}[container]
    item[extra] = 1
    with pytest.raises(RegistryError, match="forbidden extra"):
        validate_registry(registry)


@pytest.mark.parametrize("container,field", [("root", "expected_total"), ("source", "review_owner"),
                                            ("region", "authority_source_ids"), ("unit", "coverage_ratio")])
def test_required_nullable_and_empty_fields_cannot_be_omitted(registry, container, field):
    item = {"root": registry, "source": registry["sources"][0], "region": registry["regions"][0], "unit": registry["coverage_units"][0]}[container]
    del item[field]
    with pytest.raises(RegistryError, match="missing keys"):
        validate_registry(registry)


@pytest.mark.parametrize("field,value", [
    ("publication_status", "published"), ("review_status", "reviewed"), ("review_owner", "admin"),
    ("rights_status", "licensed"), ("automated_fetch_enabled", True), ("affects_eligibility", True),
    ("snapshot_status", "captured"), ("snapshot_sha256", "a" * 64), ("is_synthetic", True),
    ("notes", []), ("hostname", "different.example.edu"), ("checked_on", "2026-10-02"),
])
def test_rejects_false_source_state_and_wrong_types(registry, field, value):
    registry["sources"][0][field] = value
    with pytest.raises(RegistryError, match=field):
        validate_registry(registry)


@pytest.mark.parametrize("url", [
    "file:///tmp/facts.json", "https://user:password@example.edu/", "http://localhost/",
    "http://127.0.0.1/", "http://10.1.2.3/", "http://169.254.169.254/",
    "http://[::1]/", "http://127.1/", "http://2130706433/", "http://example.local/",
    "https://example.edu:bad/", "https://example.edu:0/", "https://example.edu/\nsecret",
    "https://example.edu\\@127.0.0.1/", "https://example.edu/?access_token=credential",
])
def test_rejects_unsafe_urls_without_resolving_or_fetching(registry, url):
    registry["sources"][0]["url"] = url
    with pytest.raises(RegistryError, match="url"):
        validate_registry(registry)


@pytest.mark.parametrize("field", ["identity_basis_url", "year_basis_url"])
def test_checks_basis_urls_too(registry, field):
    source = registry["sources"][0]
    if field == "year_basis_url":
        source.update(year_mapping_status="explicit_gregorian", source_year=2025, observed_period_label="2025年", time_basis="exam_year", access_status="page_read")
    source[field] = "http://127.0.0.1/evidence"
    with pytest.raises(RegistryError, match=field):
        validate_registry(registry)


def test_historical_year_with_explicit_basis_is_not_relabelled_as_target_year(registry):
    source = registry["sources"][0]
    source.update(year_mapping_status="explicit_gregorian", source_year=2021, observed_period_label="2021年",
                  time_basis="publication_year", access_status="page_read", year_basis_url="https://exam.example.edu/2021")
    assert validate_registry(registry)["source_candidates"] == 1
    assert source["source_year"] == 2021 and registry["target_reference_year"] == 2026


@pytest.mark.parametrize("label", ["2023届", "114學年度", "115學年度", "2025/26学年"])
def test_original_cohort_or_academic_label_cannot_be_relabelled_as_target_year(registry, label):
    source = registry["sources"][0]
    source.update(year_mapping_status="explicit_gregorian", source_year=2026, observed_period_label=label,
                  time_basis="graduation_cohort", access_status="page_read", year_basis_url="https://exam.example.edu/report")
    with pytest.raises(RegistryError, match="source_year"):
        validate_registry(registry)


@pytest.mark.parametrize("changes", [
    {"source_year": 2026}, {"year_basis_url": "https://exam.example.edu/2026"},
    {"year_mapping_status": "explicit_gregorian", "source_year": True},
    {"year_mapping_status": "explicit_gregorian", "source_year": 2026, "observed_period_label": "2026年", "year_basis_url": "https://exam.example.edu/2026"},
    {"year_mapping_status": "explicit_gregorian", "source_year": 2026, "observed_period_label": "2026年", "year_basis_url": "https://exam.example.edu/2026", "access_status": "page_read"},
])
def test_rejects_unverified_or_unread_year_mapping(registry, changes):
    registry["sources"][0].update(changes)
    with pytest.raises(RegistryError):
        validate_registry(registry)


@pytest.mark.parametrize("status", ["partial_page", "search_result_only", "source_unavailable"])
def test_failed_or_incomplete_access_requires_reason(registry, status):
    source = registry["sources"][0]
    source["access_status"] = status
    with pytest.raises(RegistryError, match="failure_reason"):
        validate_registry(registry)
    source["failure_reason"] = "本次读取未取得完整页面；不能声称尚未公布。"
    assert validate_registry(registry)["source_candidates"] == 1


@pytest.mark.parametrize("case", ["source_id", "region", "unit", "missing_region", "missing_unit"])
def test_requires_unique_complete_regions_and_units(registry, case):
    if case == "source_id":
        registry["sources"].append(deepcopy(registry["sources"][0]))
    elif case == "region":
        registry["regions"].append(deepcopy(registry["regions"][0]))
    elif case == "unit":
        registry["coverage_units"].append(deepcopy(registry["coverage_units"][0]))
    elif case == "missing_region":
        registry["regions"].pop()
    else:
        registry["coverage_units"].pop()
    with pytest.raises(RegistryError):
        validate_registry(registry)


@pytest.mark.parametrize("case", ["dangling", "wrong_region", "wrong_type", "wrong_pathway", "authority_as_curriculum",
                                  "false_missing_reason", "false_coverage", "hmt_gaokao", "wrong_region_name", "directory_as_hmt"])
def test_cross_record_scope_and_missing_states_are_consistent(registry, case):
    source = registry["sources"][0]
    cutoff = unit(registry, "cn_region_01", "province_cutoff")
    if case == "dangling":
        cutoff["candidate_source_ids"] = ["absent"]
    elif case == "wrong_region":
        source["region_keys"] = ["cn_region_02"]
    elif case == "wrong_type":
        source["dataset_types"] = ["score_distribution"]
    elif case == "wrong_pathway":
        source["pathways"] = ["hk_local_admissions"]
    elif case == "authority_as_curriculum":
        source["dataset_types"].append("curriculum")
    elif case == "false_missing_reason":
        cutoff["missing_reason"] = "not_collected"
    elif case == "false_coverage":
        cutoff["coverage_ratio"] = 1
    elif case == "hmt_gaokao":
        registry["regions"][-3]["ordinary_gaokao_applicability"] = "applicable"
    elif case == "wrong_region_name":
        registry["regions"][0]["region_name"] = "天津"
    else:
        directory = deepcopy(source)
        directory.update(id="test_directory", source_role="institution_directory", dataset_types=["institution_directory"], pathways=["institution_reference"])
        registry["sources"].append(directory)
        registry["regions"][-3]["institution_directory_source_ids"] = [directory["id"]]
    with pytest.raises(RegistryError):
        validate_registry(registry)


def test_navigation_curriculum_hint_does_not_fill_school_curriculum_unit(registry):
    navigation = deepcopy(registry["sources"][0])
    navigation.update(id="test_major_navigation", source_role="navigation", dataset_types=["curriculum"], pathways=["institution_reference"])
    registry["sources"].append(navigation)
    assert validate_registry(registry)["source_candidates"] == 2
    curriculum = unit(registry, "cn_region_01", "curriculum")
    curriculum.update(candidate_source_ids=[navigation["id"]], missing_reason="source_candidate_only")
    with pytest.raises(RegistryError, match="candidate_source_ids"):
        validate_registry(registry)


def test_admissions_publication_may_be_a_province_cutoff_candidate(registry):
    source = registry["sources"][0]
    source["source_role"] = "admissions_entry"
    registry["regions"][0]["authority_source_ids"] = []
    assert validate_registry(registry)["units_with_candidates"] == 1


@pytest.mark.parametrize("region_key", ["hk", "mo", "tw"])
def test_local_admissions_entry_can_be_a_regional_authority_candidate(registry, region_key):
    source = deepcopy(registry["sources"][0])
    source.update(id="test_local_authority", source_role="admissions_entry", region_keys=[region_key],
                  dataset_types=["admission_policy"], pathways=[f"{region_key}_local_admissions"])
    registry["sources"].append(source)
    region = next(item for item in registry["regions"] if item["region_key"] == region_key)
    region["authority_source_ids"] = [source["id"]]
    unit(registry, region_key, "admission_policy").update(candidate_source_ids=[source["id"]], missing_reason="source_candidate_only")
    assert validate_registry(registry)["units_with_candidates"] == 2
    source["pathways"] = ["ordinary_gaokao"]
    with pytest.raises(RegistryError, match="authority_source_ids"):
        validate_registry(registry)


@pytest.mark.parametrize("region_key,dataset_type", [(key, kind) for key in ("hk", "mo", "tw")
                                                   for kind in ("province_cutoff", "score_distribution")])
def test_hmt_inapplicable_units_cannot_have_candidates(registry, region_key, dataset_type):
    source = deepcopy(registry["sources"][0])
    source.update(id="test_hmt", region_keys=[region_key], dataset_types=[dataset_type])
    registry["sources"].append(source)
    unit(registry, region_key, dataset_type)["candidate_source_ids"] = [source["id"]]
    with pytest.raises(RegistryError, match="candidate_source_ids"):
        validate_registry(registry)


@pytest.mark.parametrize("changes", [{"pathway": "ordinary_gaokao"}, {"missing_reason": "not_applicable"},
                                     {"expected_total": False}, {"coverage_ratio": False}])
def test_local_admission_units_keep_local_pathway_and_unknown_coverage(registry, changes):
    unit(registry, "hk", "admission_policy").update(changes)
    with pytest.raises(RegistryError):
        validate_registry(registry)


def test_cli_is_read_only_and_returns_nonzero_for_invalid_input(registry, tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    result = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), str(path)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0 and result.stdout.startswith("VALID: ") and not result.stderr
    assert path.read_bytes() == before
    registry["sources"][0]["automated_fetch_enabled"] = True
    path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    result = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), str(path)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 1 and "automated_fetch_enabled" in result.stderr and not result.stdout
    assert path.read_bytes() == before


@pytest.mark.parametrize("content", ['{"task_id":"T50A","task_id":"other"}', '{"expected_total":NaN}', '[', '\ufeff{}'])
def test_invalid_json_and_duplicate_keys_fail_without_writes(content, tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    before = path.read_bytes()
    assert main([str(path)]) == 1
    assert "INVALID:" in capsys.readouterr().err
    assert path.read_bytes() == before


def test_cli_missing_file_is_reported(capsys, tmp_path):
    assert main([str(tmp_path / "absent.json")]) == 1
    assert "INVALID:" in capsys.readouterr().err


def test_utf8_load_then_validate_does_not_change_file(registry, tmp_path):
    path = tmp_path / "登记.json"
    path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    assert validate_registry(load_registry(path))["regions"] == 34
    assert path.read_bytes() == before
