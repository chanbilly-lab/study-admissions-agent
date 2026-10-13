"""Read-only, offline validation of T50A source candidates, never source contents.

URL checks are syntactic and reject local addresses; they neither resolve DNS
nor establish official ownership, access, licensing, or factual applicability.
Those claims still need human review before any production import or release.
"""
from __future__ import annotations

import argparse
from datetime import date
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlsplit


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data/research/source_registry_2026.json"
DATASET_TYPES = (
    "institution_directory", "province_cutoff", "score_distribution",
    "admission_statistics", "admission_policy", "curriculum", "outcomes",
)
EXAM_TYPES = {"province_cutoff", "score_distribution", "admission_statistics", "admission_policy"}
SOURCE_ROLES = {
    "navigation": set(DATASET_TYPES),
    "authority_entry": EXAM_TYPES,
    "institution_directory": {"institution_directory"},
    "admissions_entry": EXAM_TYPES,
    "curriculum_entry": {"curriculum"},
    "outcomes_entry": {"outcomes"},
}
TIME_BASES = {
    "unknown", "publication_year", "exam_year", "entry_cohort", "graduation_cohort",
    "academic_year", "institution_directory", "admissions_year",
}
ACCESS_STATUSES = {"page_read", "partial_page", "linked_not_opened", "search_result_only", "source_unavailable"}
MAINLAND_NAMES = (
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
)
REGION_NAMES = {f"cn_region_{number:02d}": name for number, name in enumerate(MAINLAND_NAMES, 1)}
REGION_NAMES.update({"hk": "香港", "mo": "澳门", "tw": "台湾"})
LOCAL_PATHWAYS = {"hk": "hk_local_admissions", "mo": "mo_local_admissions", "tw": "tw_local_admissions"}
ROOT_LITERALS = {
    "schema": "study.research.source-registry.v1", "task_id": "T50A",
    "target_reference_year": 2026, "registered_as_of": "2026-10-01", "timezone": "Asia/Hong_Kong",
    "candidate_only": True, "is_synthetic": False, "nationwide_collection_complete": False,
    "reviewed_fact_count": 0, "published_fact_count": 0, "imported_institution_count": 0,
    "expected_total": None, "coverage_ratio": None,
    "personalized_scope": "one_configured_province_ordinary_gaokao_plus_uk_undergraduate",
}
SOURCE_LITERALS = {
    "review_status": "review_required", "publication_status": "not_released", "rights_status": "not_reviewed",
    "review_owner": None, "automated_fetch_enabled": False, "affects_eligibility": False,
    "snapshot_status": "not_captured", "snapshot_sha256": None, "is_synthetic": False,
}
SOURCE_KEYS = set(SOURCE_LITERALS) | {
    "id", "publisher", "title", "url", "hostname", "source_role", "region_keys", "dataset_types", "pathways",
    "identity_basis_url", "identity_basis_locator", "observed_period_label", "time_basis", "source_year",
    "year_mapping_status", "year_basis_url", "access_status", "checked_on", "failure_reason", "notes",
}
REGION_KEYS = {
    "region_key", "region_name", "region_kind", "ordinary_gaokao_applicability", "pathways",
    "authority_source_ids", "institution_directory_source_ids",
}
UNIT_KEYS = {
    "region_key", "dataset_type", "pathway", "candidate_source_ids", "missing_reason", "expected_total", "coverage_ratio",
}


class RegistryError(ValueError):
    """An exact contract or cross-record invariant was violated."""


def require(condition, path, message):
    if not condition:
        raise RegistryError(f"{path}: {message}")


def exact_object(value, keys, path):
    require(type(value) is dict, path, "must be an object")
    missing, extra = keys - value.keys(), value.keys() - keys
    require(not missing and not extra, path, f"missing keys {sorted(missing)}; forbidden extra keys {sorted(extra)}")


def literal(value, expected, path):
    require(type(value) is type(expected) and value == expected, path, f"must be exactly {expected!r}")


def nonempty_text(value, path):
    require(type(value) is str and bool(value.strip()), path, "must be a nonempty string")
    return value


def enum(value, allowed, path):
    require(type(value) is str and value in allowed, path, f"must be one of {sorted(allowed)}")


def string_list(value, path, *, nonempty=False):
    require(type(value) is list, path, "must be an array")
    if nonempty:
        require(bool(value), path, "must not be empty")
    for index, item in enumerate(value):
        nonempty_text(item, f"{path}[{index}]")
    require(len(set(value)) == len(value), path, "duplicate values are forbidden")
    return value


def calendar_date(value, path):
    nonempty_text(value, path)
    require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)), path, "must be an ISO calendar date")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise RegistryError(f"{path}: invalid calendar date") from error


def safe_url(value, path):
    nonempty_text(value, path)
    require(not any(ord(character) <= 32 or ord(character) == 127 for character in value)
            and "\\" not in value, path, "URL whitespace, controls, or backslashes are forbidden")
    try:
        parsed = urlsplit(value)
        hostname, port = parsed.hostname, parsed.port
    except ValueError as error:
        raise RegistryError(f"{path}: malformed URL") from error
    require(parsed.scheme in {"http", "https"} and bool(hostname), path, "must be an absolute HTTP(S) URL")
    require(parsed.username is None and parsed.password is None, path, "URL credentials are forbidden")
    require(port is None or 0 < port < 65536, path, "invalid port")
    require(not hostname.endswith(".") and hostname != "localhost"
            and not hostname.endswith((".localhost", ".local", ".internal", ".lan", ".home")),
            path, "local/internal hostnames are forbidden")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise RegistryError(f"{path}: invalid hostname") from error
        labels = ascii_hostname.split(".")
        require(len(labels) >= 2 and all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                                       for label in labels)
                and bool(re.search(r"[a-zA-Z]", labels[-1])), path, "must use a valid public hostname")
    else:
        require(address.is_global, path, "non-public IP addresses are forbidden")
    sensitive_keys = {"password", "passwd", "secret", "token", "access_token", "api_key", "apikey", "authorization", "sessionid"}
    require(not any(key.lower() in sensitive_keys for key, _ in parse_qsl(parsed.query)),
            path, "credential query parameters are forbidden")
    return hostname


def unit_pathway(region_key, dataset_type):
    if dataset_type in {"institution_directory", "curriculum", "outcomes"}:
        return "institution_reference"
    if region_key not in LOCAL_PATHWAYS or dataset_type in {"province_cutoff", "score_distribution"}:
        return "ordinary_gaokao"
    return LOCAL_PATHWAYS[region_key]


def source_reference(identifier, sources, path, *, region_key, dataset_type=None, pathway=None):
    require(identifier in sources, path, "dangling source reference")
    source = sources[identifier]
    require(region_key in source["region_keys"], path, "source does not cover this region")
    if dataset_type is not None:
        require(dataset_type in source["dataset_types"], path, "source does not cover this dataset type")
    if pathway is not None:
        require(pathway in source["pathways"], path, "source does not cover this pathway")
    return source


def validate_registry(data):
    """Validate without mutating input; return candidate counts, never coverage claims."""
    exact_object(data, set(ROOT_LITERALS) | {"sources", "regions", "coverage_units"}, "$" )
    for key, expected in ROOT_LITERALS.items():
        literal(data[key], expected, f"$.{key}")
    registered_date = calendar_date(data["registered_as_of"], "$.registered_as_of")
    for key in ("sources", "regions", "coverage_units"):
        require(type(data[key]) is list, f"$.{key}", "must be an array")

    sources = {}
    for index, source in enumerate(data["sources"]):
        path = f"$.sources[{index}]"
        exact_object(source, SOURCE_KEYS, path)
        for key, expected in SOURCE_LITERALS.items():
            literal(source[key], expected, f"{path}.{key}")
        for key in ("id", "publisher", "title", "identity_basis_locator", "notes"):
            nonempty_text(source[key], f"{path}.{key}")
        require(source["id"] not in sources, f"{path}.id", "duplicate source ID")
        hostname = safe_url(source["url"], f"{path}.url")
        literal(source["hostname"], hostname, f"{path}.hostname")
        safe_url(source["identity_basis_url"], f"{path}.identity_basis_url")
        enum(source["source_role"], SOURCE_ROLES, f"{path}.source_role")
        for key in ("region_keys", "dataset_types", "pathways"):
            string_list(source[key], f"{path}.{key}", nonempty=True)
        require(set(source["region_keys"]) <= REGION_NAMES.keys(), f"{path}.region_keys", "unknown region key")
        require(set(source["dataset_types"]) <= SOURCE_ROLES[source["source_role"]],
                f"{path}.dataset_types", "dataset type is incompatible with source role")
        enum(source["time_basis"], TIME_BASES, f"{path}.time_basis")
        enum(source["access_status"], ACCESS_STATUSES, f"{path}.access_status")
        checked_date = calendar_date(source["checked_on"], f"{path}.checked_on")
        require(checked_date <= registered_date, f"{path}.checked_on", "cannot claim a future check")
        if source["observed_period_label"] is not None:
            nonempty_text(source["observed_period_label"], f"{path}.observed_period_label")
        if source["failure_reason"] is not None:
            nonempty_text(source["failure_reason"], f"{path}.failure_reason")
        if source["access_status"] in {"partial_page", "search_result_only", "source_unavailable"}:
            nonempty_text(source["failure_reason"], f"{path}.failure_reason")
        if source["access_status"] == "page_read":
            literal(source["failure_reason"], None, f"{path}.failure_reason")
        enum(source["year_mapping_status"], {"unverified", "explicit_gregorian"}, f"{path}.year_mapping_status")
        if source["year_mapping_status"] == "unverified":
            literal(source["source_year"], None, f"{path}.source_year")
            literal(source["year_basis_url"], None, f"{path}.year_basis_url")
        else:
            require(type(source["source_year"]) is int and 1 <= source["source_year"] <= 9999,
                    f"{path}.source_year", "must be a Gregorian integer year, not boolean")
            nonempty_text(source["observed_period_label"], f"{path}.observed_period_label")
            require(bool(re.search(rf"(?<!\d){source['source_year']}(?!\d)", source["observed_period_label"])),
                    f"{path}.source_year", "mapped year must match an explicit year token in the original period label")
            safe_url(source["year_basis_url"], f"{path}.year_basis_url")
            literal(source["access_status"], "page_read", f"{path}.access_status")
            require(source["time_basis"] != "unknown", f"{path}.time_basis", "mapped year requires a known time basis")
        sources[source["id"]] = source

    regions = {}
    for index, region in enumerate(data["regions"]):
        path = f"$.regions[{index}]"
        exact_object(region, REGION_KEYS, path)
        nonempty_text(region["region_key"], f"{path}.region_key")
        key = region["region_key"]
        require(key in REGION_NAMES, f"{path}.region_key", "unknown stable region key")
        require(key not in regions, f"{path}.region_key", "duplicate region key")
        literal(region["region_name"], REGION_NAMES[key], f"{path}.region_name")
        kind = {"hk": "hong_kong", "mo": "macau", "tw": "taiwan"}.get(key, "mainland_province")
        literal(region["region_kind"], kind, f"{path}.region_kind")
        literal(region["ordinary_gaokao_applicability"], "not_applicable" if key in LOCAL_PATHWAYS else "applicable",
                f"{path}.ordinary_gaokao_applicability")
        string_list(region["pathways"], f"{path}.pathways", nonempty=True)
        required_pathways = {"institution_reference", LOCAL_PATHWAYS.get(key, "ordinary_gaokao")}
        require(required_pathways <= set(region["pathways"]), f"{path}.pathways", "missing applicable reference/admissions pathway")
        for field, role in (("authority_source_ids", "authority_entry"),
                            ("institution_directory_source_ids", "institution_directory")):
            string_list(region[field], f"{path}.{field}")
            for identifier in region[field]:
                source = source_reference(identifier, sources, f"{path}.{field}", region_key=key)
                if role == "institution_directory":
                    literal(source["source_role"], role, f"{path}.{field}")
                    require("institution_directory" in source["dataset_types"], f"{path}.{field}", "not an institution directory")
                    require("institution_reference" in source["pathways"], f"{path}.{field}", "not an institution reference pathway")
                else:
                    enum(source["source_role"], {"authority_entry", "admissions_entry"}, f"{path}.{field}")
                    relevant_types = {"admission_statistics", "admission_policy"} if key in LOCAL_PATHWAYS else EXAM_TYPES
                    require(bool(relevant_types & set(source["dataset_types"])), f"{path}.{field}", "not a relevant admissions authority candidate")
                    require(LOCAL_PATHWAYS.get(key, "ordinary_gaokao") in source["pathways"],
                            f"{path}.{field}", "not the region's admissions pathway")
        regions[key] = region
    require(set(regions) == set(REGION_NAMES), "$.regions", "must contain exactly the 34 stable regions")

    units = set()
    for index, unit in enumerate(data["coverage_units"]):
        path = f"$.coverage_units[{index}]"
        exact_object(unit, UNIT_KEYS, path)
        nonempty_text(unit["region_key"], f"{path}.region_key")
        require(unit["region_key"] in regions, f"{path}.region_key", "unknown region reference")
        enum(unit["dataset_type"], DATASET_TYPES, f"{path}.dataset_type")
        key, dataset_type = unit["region_key"], unit["dataset_type"]
        pair = (key, dataset_type)
        require(pair not in units, path, "duplicate region/type coverage unit")
        units.add(pair)
        literal(unit["pathway"], unit_pathway(key, dataset_type), f"{path}.pathway")
        literal(unit["expected_total"], None, f"{path}.expected_total")
        literal(unit["coverage_ratio"], None, f"{path}.coverage_ratio")
        string_list(unit["candidate_source_ids"], f"{path}.candidate_source_ids")
        inapplicable = key in LOCAL_PATHWAYS and dataset_type in {"province_cutoff", "score_distribution"}
        if inapplicable:
            literal(unit["candidate_source_ids"], [], f"{path}.candidate_source_ids")
            literal(unit["missing_reason"], "not_applicable", f"{path}.missing_reason")
        else:
            literal(unit["missing_reason"], "source_candidate_only" if unit["candidate_source_ids"] else "not_collected",
                    f"{path}.missing_reason")
            for identifier in unit["candidate_source_ids"]:
                source = source_reference(identifier, sources, f"{path}.candidate_source_ids",
                                          region_key=key, dataset_type=dataset_type, pathway=unit["pathway"])
                if dataset_type in {"curriculum", "outcomes"}:
                    literal(source["source_role"], f"{dataset_type}_entry", f"{path}.candidate_source_ids")
    require(units == {(key, kind) for key in REGION_NAMES for kind in DATASET_TYPES},
            "$.coverage_units", "must contain exactly 34 × 7 unique region/type units")
    return {
        "task_id": "T50A", "source_candidates": len(sources), "regions": len(regions), "coverage_units": len(units),
        "units_with_candidates": sum(bool(unit["candidate_source_ids"]) for unit in data["coverage_units"]),
        "reviewed_fact_count": 0, "published_fact_count": 0, "imported_institution_count": 0,
        "expected_total": None, "coverage_ratio": None, "candidate_only": True,
    }


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "$", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def reject_nonfinite(value):
    raise RegistryError("$: non-finite JSON numbers are forbidden")


def load_registry(path):
    content = Path(path).read_text(encoding="utf-8")
    return json.loads(content, object_pairs_hook=unique_json_object, parse_constant=reject_nonfinite)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline, read-only T50A source candidate contract validation")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)
    try:
        summary = validate_registry(load_registry(args.path))
    except (RegistryError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print("VALID: " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
