"""Independent route/scope examples using explicitly synthetic rule bundles."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import socket
from uuid import UUID

from pydantic import ValidationError
import pytest

from app.evidence.schemas import EvidenceScope
from app.rules.adapters import canonical_province, scope_request_from_profile, select_rules
from app.rules.adapters.schemas import AdapterPolicy, RuleBundle, ScopeRequest, TargetReference
from app.rules.expression import parse_expression


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
DATASET, INSTITUTION, PROGRAM, OFFERING, RELEASE, BUNDLE, FACT, EVIDENCE = (
    UUID(f"00000000-0000-4000-8000-{n:012d}") for n in range(1, 9))
PROVINCES = (
    "Beijing", "Tianjin", "Hebei", "Shanxi", "InnerMongolia", "Liaoning", "Jilin", "Heilongjiang",
    "Shanghai", "Jiangsu", "Zhejiang", "Anhui", "Fujian", "Jiangxi", "Shandong", "Henan", "Hubei",
    "Hunan", "Guangdong", "Guangxi", "Hainan", "Chongqing", "Sichuan", "Guizhou", "Yunnan",
    "Tibet", "Shaanxi", "Gansu", "Qinghai", "Ningxia", "Xinjiang")
EXTRA_SCOPES = ("intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")
PROGRAM_SCOPES = ("degree", "course", "campus", "teaching_language", "progression_pathway")


@pytest.fixture(autouse=True)
def offline_no_socket(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("T26 scope examples must not connect or resolve a host")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def known(value):
    return {"status": "known", "value": value}


def unknown():
    return {"status": "unknown", "value": None}


def na():
    return {"status": "not_applicable", "value": None}


def request(country="CN", **updates):
    target = {"dataset_id": DATASET, "institution_id": INSTITUTION, "program_id": PROGRAM,
        "offering_id": OFFERING, "offering_version": 1, "country": country}
    data = {"entry_year": 2027, "study_level": "bachelor", "residence_region": known("HK"),
        "course_system": known("gaokao"), "applicant_category": known("cn_mainland"),
        "exam_province": known("Zhejiang"), "pathway": known("gaokao" if country == "CN" else "uk_undergraduate"),
        "target": target, "stage": "application", "assessment_at": NOW,
        "intake": known("DEMO_autumn"), "application_cycle": known("DEMO_2027_cycle"),
        "channel": known("DEMO_regular"), "exam_system": known("DEMO_ordinary_gaokao"),
        "subject_scope": known("DEMO_physics_group"), "batch_group": known("DEMO_general")}
    data.update(updates)
    data["target"] = (data["target"].model_dump() if isinstance(data["target"], TargetReference)
        else deepcopy(data["target"]))
    scope_data = {"dataset_id": data["target"]["dataset_id"],
        "institution_id": data["target"]["institution_id"], "program_id": data["target"]["program_id"],
        "country": data["target"]["country"], "study_level": "undergraduate", "entry_year": data["entry_year"],
        **{name: known("DEMO_" + name) for name in PROGRAM_SCOPES},
        **{name: data[name] if data[name] is not None else known("DEMO_missing_target_" + name) for name in EXTRA_SCOPES},
        "course_system": data["course_system"], "pathway": data["pathway"],
        "applicant_category": data["applicant_category"], "province": na()}
    if data["target"]["country"] == "CN":
        province = data["exam_province"]
        if hasattr(province, "model_dump"):
            province = province.model_dump()
        expected = canonical_province(province["value"]) if province["status"] == "known" else None
        scope_data["province"] = known(expected or "Zhejiang")
    # Test-only target carries the independently explicit complete project scope.
    # It is a fingerprint of that scope, not a claim of student/human authority.
    data["target"].setdefault("scope_sha256", fingerprint(EvidenceScope.model_validate(scope_data)))
    return ScopeRequest.model_validate(data)


def fingerprint(model):
    raw = json.dumps(model.model_dump(mode="json"), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return sha256(raw).hexdigest()


def bundle(supplied=None, *, scope_updates=None, **updates):
    current = request() if supplied is None else supplied
    scope_data = {"dataset_id": current.target.dataset_id, "institution_id": current.target.institution_id,
        "program_id": current.target.program_id, "country": current.target.country,
        "study_level": "undergraduate", "entry_year": current.entry_year,
        **{name: known("DEMO_" + name) for name in PROGRAM_SCOPES},
        **{name: getattr(current, name) for name in EXTRA_SCOPES},
        "course_system": current.course_system, "pathway": current.pathway,
        "applicant_category": current.applicant_category,
        "province": current.exam_province if current.target.country == "CN" else na()}
    if current.target.country == "CN" and current.exam_province.status == "known":
        scope_data["province"] = known(canonical_province(current.exam_province.value) or current.exam_province.value)
    scope_data.update(scope_updates or {})
    scope = EvidenceScope.model_validate(scope_data)
    expression = parse_expression({"op": "exists", "field": {"name": "entry_year"}})
    data = {"bundle_id": BUNDLE, "reference_key": "DEMO_T26_RANGE_FIXTURE", "release_id": RELEASE,
        "release_version": 1, "requirements_version": "a" * 64, "ruleset_version": "b" * 64,
        "is_synthetic": True, "scope": scope, "scope_sha256": fingerprint(scope),
        "offering_id": current.target.offering_id, "offering_version": current.target.offering_version,
        "stage": current.stage, "valid_from": NOW - timedelta(days=1),
        "valid_until": NOW + timedelta(days=1), "expression": expression,
        "expression_sha256": fingerprint(expression), "fact_ids": (FACT,), "evidence_ids": (EVIDENCE,)}
    data.update(updates)
    if "scope" in updates and "scope_sha256" not in updates:
        data["scope_sha256"] = fingerprint(data["scope"])
    if "expression" in updates and "expression_sha256" not in updates:
        data["expression_sha256"] = fingerprint(parse_expression(data["expression"]))
    return RuleBundle.model_validate(data)


def policy(**updates):
    return AdapterPolicy.model_validate({"enabled": True, "allow_test_bundles": True,
        "real_adapters_ready": False, "app_environment": "test", "data_mode": "demo", **updates})


def select(supplied, *bundles, **kwargs):
    return select_rules(supplied, policy=kwargs.pop("policy", policy()),
        provider=kwargs.pop("provider", lambda query: tuple(bundles)),
        verifier=kwargs.pop("verifier", lambda query, candidate: True), **kwargs)


def assert_unavailable(result, status="unknown"):
    assert result.selection_status == status
    assert result.reason != "MATCHED"
    assert all(getattr(result, name) is None for name in
        ("bundle_id", "release_id", "requirements_version", "ruleset_version"))


def bind_target(current, candidate):
    payload = current.model_dump()
    payload["target"]["scope_sha256"] = candidate.scope_sha256
    return ScopeRequest.model_validate(payload)


def profile(**updates):
    current = request()
    data = {"study_level": "bachelor", "entry_year": 2027,
        **{name: getattr(current, name).model_dump() for name in
            ("residence_region", "course_system", "applicant_category", "exam_province", "pathway")},
        "subjects": [], "assessments": {"math": {
            "achieved": {"status": "missing", "value": None, "unit": None, "scale": None},
            "predicted": {"status": "provided", "value": "140", "unit": "points", "scale": "150"}}},
        "weekly_hours": "0", "preferences": {"preferred_fields": ["DEMO_PRIVATE_PREFERENCE"],
            "preferred_countries": ["CN"], "budget": {"amount": "0", "currency": "CNY"}}}
    data.update(updates)
    return data


def test_all_31_registered_provinces_are_input_keys_not_a_claim_of_real_coverage():
    assert len(PROVINCES) == len(set(PROVINCES)) == 31
    for province in PROVINCES:
        assert canonical_province(province) == province
        assert canonical_province(province.lower()) == province
        current = request(exam_province=known(province))
        assert_unavailable(select(current))
        matched = select(current, bundle(current))
        assert matched.selection_status == "matched" and matched.adapter == "CN_GAOKAO"
    assert canonical_province("inner_mongolia") == "InnerMongolia"
    assert canonical_province("shanxi") != canonical_province("shaanxi")


@pytest.mark.parametrize("name", ["ZHEJIANG", "zHeJiAnG", " Zhejiang", "Zhejiang ", "ZJ", "Xizang",
    "HongKong", "Macau", "Taiwan", "XPCC", "XinjiangProductionCorps", "DEMO_PROVINCE", ""])
def test_nonregistered_spelling_does_not_guess_a_province(name):
    assert canonical_province(name) is None
    if name and name.strip() == name:
        assert_unavailable(select(request(exam_province=known(name)), bundle()))


def test_alias_comparison_does_not_rewrite_the_original_student_or_evidence():
    current = request(exam_province=known("zhejiang"))
    original = current.model_dump(mode="json")
    candidate = bundle(request())
    old_scope_hash = candidate.scope_sha256
    assert select(current, candidate).selection_status == "matched"
    assert current.model_dump(mode="json") == original
    assert candidate.scope_sha256 == old_scope_hash
    assert candidate.scope.province.value == "Zhejiang"


@pytest.mark.parametrize("province", ["Hebei", "Shanxi", "Shaanxi", "Xinjiang"])
def test_other_province_rules_are_not_fallback_coverage(province):
    assert_unavailable(select(request(exam_province=known(province)), bundle()))


@pytest.mark.parametrize("year", [2026, 2028])
def test_reference_or_other_admission_year_is_not_2027_qualification(year):
    assert_unavailable(select(request(entry_year=year), bundle()))


@pytest.mark.parametrize("region", [known("CN"), known("HK"), known("MO"), known("TW"), unknown(), na()])
def test_residence_does_not_determine_an_explicit_mainland_gaokao_identity(region):
    current = request(residence_region=region)
    assert select(current, bundle()).selection_status == "matched"


@pytest.mark.parametrize("field,value", [
    ("course_system", "HKDSE"), ("course_system", "hmt_joint"), ("course_system", "taiwan_gsat"),
    ("applicant_category", "hmt_joint"), ("applicant_category", "hk_local"),
    ("pathway", "hkdse"), ("pathway", "taiwan_undergraduate")])
def test_known_unsupported_identity_course_and_path_are_explicit(field, value):
    assert_unavailable(select(request(**{field: known(value)}), bundle()), "unsupported")


@pytest.mark.parametrize("field", ["course_system", "applicant_category", "pathway", "exam_province"])
@pytest.mark.parametrize("state", [unknown(), na()])
def test_domestic_missing_scope_is_not_completed_from_residence(field, state):
    assert_unavailable(select(request(**{field: state}), bundle()))


@pytest.mark.parametrize("field", EXTRA_SCOPES)
@pytest.mark.parametrize("state", [None, unknown()])
def test_explicit_extra_scope_is_not_inferred_from_gaokao_province_or_year(field, state):
    assert_unavailable(select(request(**{field: state}), bundle()))


@pytest.mark.parametrize("field", EXTRA_SCOPES)
def test_channels_cycles_subjects_and_batches_require_exact_declarations(field):
    assert_unavailable(select(request(**{field: known("DEMO_other")}), bundle()))
    assert_unavailable(select(request(**{field: na()}), bundle()))
    current = request(**{field: na()})
    assert select(current, bundle(scope_updates={field: na()})).selection_status == "matched"


def test_subject_list_does_not_implicitly_become_a_subject_scope():
    raw = profile(subjects=["physics", "math"])
    old = deepcopy(raw)
    current = request()
    projected = scope_request_from_profile(raw, target=current.target, stage=current.stage,
        assessment_at=NOW, **{name: (None if name == "subject_scope" else getattr(current, name)) for name in EXTRA_SCOPES})
    assert projected.subject_scope is None
    assert_unavailable(select(projected, bundle()))
    assert raw == old


@pytest.mark.parametrize("country,pathway", [("CN", "uk_undergraduate"), ("GB", "gaokao")])
def test_domestic_and_uk_paths_do_not_cross_country(country, pathway):
    current = request(country=country, pathway=known(pathway))
    assert_unavailable(select(current, bundle(current)), "unsupported")


@pytest.mark.parametrize("country", ["HK", "MO", "TW", "US"])
def test_other_institution_regions_are_outside_the_closed_target_contract(country):
    with pytest.raises(ValidationError):
        request(country=country)


@pytest.mark.parametrize("student_province", [known("Zhejiang"), unknown(), na()])
def test_uk_rule_explicitly_not_province_limited_does_not_need_student_province(student_province):
    current = request(country="GB", exam_province=student_province)
    selected = select(current, bundle(current))
    assert selected.selection_status == "matched" and selected.adapter == "UK_UNDERGRADUATE"


def test_uk_known_province_limit_and_unknown_rule_scope_are_distinct():
    current = request(country="GB")
    limited = bundle(current, scope_updates={"province": known("zhejiang")})
    assert select(bind_target(current, limited), limited).selection_status == "matched"
    for student_province in (known("Shaanxi"), unknown(), na()):
        limited = bundle(current, scope_updates={"province": known("Zhejiang")})
        other = request(country="GB", exam_province=student_province)
        assert_unavailable(select(bind_target(other, limited), limited))
    assert_unavailable(select(current, bundle(current, scope_updates={"province": unknown()})))


@pytest.mark.parametrize("year", [2026, 2028])
def test_uk_provisional_2027_is_not_a_generic_year_rule(year):
    current = request(country="GB", entry_year=year)
    assert_unavailable(select(current, bundle(current)))


@pytest.mark.parametrize("stage", ["application", "enrollment"])
def test_application_and_enrollment_are_independent_stages(stage):
    current = request(stage=stage)
    assert select(current, bundle(current)).selection_status == "matched"
    other = "enrollment" if stage == "application" else "application"
    assert_unavailable(select(current, bundle(stage=other)))


@pytest.mark.parametrize("dimension", ["dataset_id", "institution_id", "program_id", "offering_id", "offering_version"])
def test_exact_target_identity_and_pinned_version_cannot_be_replaced_by_names(dimension):
    current = request()
    target = current.target.model_dump()
    target[dimension] = 2 if dimension == "offering_version" else UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
    assert_unavailable(select(request(target=target), bundle()))


@pytest.mark.parametrize("dimension", PROGRAM_SCOPES)
def test_program_course_and_progression_are_not_student_course_or_route_fields(dimension):
    # The full target scope pin and independent binding verification are both
    # needed; neither project IDs nor a scope DTO alone supply authority.
    current = request()
    candidate = bundle(scope_updates={dimension: known("DEMO_different_" + dimension)})
    assert_unavailable(select(current, candidate))
    explicit = bind_target(current, candidate)
    assert select(explicit, candidate).selection_status == "matched"
    assert_unavailable(select(explicit, candidate, verifier=lambda query, bound: False))
    incomplete = bundle(scope_updates={dimension: unknown()})
    assert_unavailable(select(bind_target(current, incomplete), incomplete))


@pytest.mark.parametrize("assessment", [NOW - timedelta(days=1), NOW + timedelta(days=1), NOW + timedelta(days=2)])
def test_bundle_window_is_explicit_half_open(assessment):
    current = request(assessment_at=assessment)
    selected = select(current, bundle())
    if assessment == NOW - timedelta(days=1):
        assert selected.selection_status == "matched"
    else:
        assert_unavailable(selected)


def test_two_applicable_rule_bindings_are_ambiguous_in_both_orders():
    current = request()
    first = bundle()
    second = bundle(bundle_id=UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"), ruleset_version="c" * 64)
    for ordered in ((first, second), (second, first)):
        result = select(current, *ordered)
        assert_unavailable(result)
        assert result.reason == "AMBIGUOUS_RULESETS"


@pytest.mark.parametrize("invalidity", ["missing_ruleset", "expired", "withdrawn"])
def test_one_invalid_same_binding_cannot_be_hidden_by_one_valid_bundle(invalidity):
    good = bundle()
    other_id = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
    updates = {"bundle_id": other_id}
    if invalidity == "missing_ruleset":
        updates["ruleset_version"] = None
    elif invalidity == "expired":
        updates["valid_until"] = NOW
    bad = bundle(**updates)
    for ordered in ((good, bad), (bad, good)):
        result = select(request(), *ordered,
            verifier=lambda query, candidate: not (invalidity == "withdrawn" and candidate.bundle_id == other_id))
        assert_unavailable(result)


def test_different_target_year_or_stage_can_be_filtered_without_invalidating_a_current_rule():
    current = request()
    different_target = bundle(offering_id=UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"), ruleset_version=None)
    different_year = bundle(scope_updates={"entry_year": 2026}, ruleset_version=None)
    different_stage = bundle(stage="enrollment", ruleset_version=None)
    for candidate in (different_target, different_year, different_stage):
        for ordered in ((candidate, bundle()), (bundle(), candidate)):
            assert select(current, *ordered).selection_status == "matched"


def test_scope_match_is_not_eligibility_and_provider_receives_only_a_minimum_query():
    seen = []
    def provider(query):
        seen.append(query.model_dump(mode="json"))
        return (bundle(),)
    current = request()
    selected = select(current, provider=provider)
    assert selected.selection_status == "matched"
    assert selected.model_dump().keys() == {"selection_status", "reason", "adapter", "bundle_id",
        "release_id", "requirements_version", "ruleset_version"}
    assert len(seen) == 1 and set(seen[0]) == {"target", "entry_year", "stage"}
    assert seen[0]["target"] == current.target.model_dump(mode="json")
    assert selected.bundle_id == BUNDLE and selected.release_id == RELEASE
    assert selected.requirements_version == "a" * 64 and selected.ruleset_version == "b" * 64


def test_profile_projection_preserves_unknowns_without_sending_achieved_predicted_or_preferences():
    raw = profile(exam_province=unknown(), pathway=known("uk_undergraduate"))
    before = deepcopy(raw)
    target = request(country="GB").target
    current = scope_request_from_profile(raw, target=target, stage="application", assessment_at=NOW,
        **{name: getattr(request(country="GB"), name) for name in EXTRA_SCOPES})
    assert current.exam_province.status == "unknown"
    assert current.study_level == "bachelor"
    selected = select(current, bundle(current))
    assert selected.selection_status == "matched"
    assert raw == before
    wire = json.dumps(current.model_dump(mode="json"))
    assert "DEMO_PRIVATE_PREFERENCE" not in wire and "assessments" not in wire and "subjects" not in wire
