"""Hostile inputs and untrusted bindings against the T26 pure boundary."""

from copy import deepcopy
from datetime import datetime, timedelta, tzinfo
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import UUID

from pydantic import ValidationError
import pytest

from app.rules.adapters import select_rules
from app.rules.adapters.schemas import AdapterInputError, AdapterPolicy, RuleBundle, ScopeRequest, TargetReference

from test_t26_matrix import (
    BUNDLE, EXTRA_SCOPES, NOW, assert_unavailable, bind_target, bundle, fingerprint, known, policy, request, select,
)


SENTINEL = "DEMO_PRIVATE_ADAPTER_ATTACK_SENTINEL"
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def offline_no_socket(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("T26 adversarial tests must not connect or resolve a host")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def rejected(raw, *, supplied_policy=None):
    with pytest.raises(AdapterInputError) as caught:
        select_rules(raw, policy=policy() if supplied_policy is None else supplied_policy,
            provider=lambda query: (bundle(),), verifier=lambda query, bound: True)
    assert caught.value.status_code == 422 and caught.value.code == "INVALID_ADAPTER_INPUT"
    assert SENTINEL not in str(caught.value) and SENTINEL not in repr(caught.value)


def test_default_closed_selector_never_calls_an_injected_provider():
    def unexpected(*args):
        raise AssertionError("disabled selection must not call any provider or verifier")
    result = select_rules(request(), policy=AdapterPolicy(), provider=unexpected, verifier=unexpected)
    assert_unavailable(result)
    assert result.reason == "POLICY_DISABLED"


@pytest.mark.parametrize("field,value", [("entry_year", True), ("entry_year", 2027.0), ("entry_year", "2027"),
    ("entry_year", 0), ("entry_year", 10000), ("study_level", "undergraduate"), ("stage", "offer"),
    ("stage", ["application"]), ("assessment_at", 1791028800), ("assessment_at", True),
    ("assessment_at", "2026-10-03"), ("assessment_at", datetime(2026, 10, 3)),
    ("residence_region", {"status": "known", "value": ["CN"]}),
    ("exam_province", {"status": "unknown", "value": "Zhejiang"}),
    ("course_system", {"status": ["known"], "value": "gaokao"})])
def test_untrusted_request_shapes_do_not_coerce_types_or_missing_scope(field, value):
    raw = request().model_dump()
    raw[field] = value
    rejected(raw)


@pytest.mark.parametrize("field", ["owner_user_id", "role", "is_synthetic", "reviewed", "confirmed",
    "grades", "preferences", "server_now", "student_region"])
def test_client_values_cannot_expand_the_pure_scope_input(field):
    raw = request().model_dump()
    raw[field] = SENTINEL
    rejected(raw)


@pytest.mark.parametrize("field", EXTRA_SCOPES)
def test_missing_extra_scope_key_is_not_equivalent_to_explicit_null(field):
    raw = request().model_dump()
    del raw[field]
    rejected(raw)


@pytest.mark.parametrize("field,value", [("offering_version", True), ("offering_version", "1"),
    ("offering_version", 0), ("offering_version", 2147483648),
    ("dataset_id", "00000000000040008000000000000001"), ("offering_id", SENTINEL),
    ("country", "cn"), ("country", ["CN"]), ("scope_sha256", "A" * 64)])
def test_target_references_are_exact_not_names_or_loose_uuid_forms(field, value):
    raw = request().model_dump()
    raw["target"][field] = value
    rejected(raw)


@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_outer_and_nested_model_construction_is_revalidated(mode):
    current = request()
    if mode == "copy":
        forged = current.model_copy(update={"entry_year": True})
        nested = current.target.model_copy(update={"offering_version": "1"})
    else:
        forged = ScopeRequest.model_construct(**{**current.model_dump(), "entry_year": True})
        nested = TargetReference.model_construct(**{**current.target.model_dump(), "offering_version": "1"})
    rejected(forged)
    rejected(current.model_copy(update={"target": nested}))


@pytest.mark.parametrize("updates", [{"enabled": 1}, {"allow_test_bundles": "true"},
    {"real_adapters_ready": True}, {"real_adapters_ready": 0},
    {"allow_test_bundles": True, "app_environment": "production"},
    {"allow_test_bundles": True, "data_mode": "verified"}, {"model_mode": "mock"}])
def test_policy_cannot_promote_test_bundles_or_fake_formal_readiness(updates):
    forged = policy().model_copy(update=updates)
    rejected(request(), supplied_policy=forged)


def test_facts_only_null_ruleset_never_compiles_a_numeric_or_typical_offer_rule():
    current = request()
    candidate = bundle(ruleset_version=None)
    result = select(current, candidate)
    assert_unavailable(result)
    assert result.reason == "RULESET_UNAVAILABLE"


@pytest.mark.parametrize("settings", [AdapterPolicy(enabled=True),
    AdapterPolicy(enabled=True, app_environment="test", data_mode="verified")])
def test_no_formal_provider_exists_even_when_external_verifier_claims_true(settings):
    synthetic = bundle()
    assert_unavailable(select(request(), synthetic, policy=settings))
    formal = bundle(is_synthetic=False, reference_key="BOUNDARY_ONLY_UNREVIEWED_METADATA")
    result = select(request(), formal, policy=settings)
    assert_unavailable(result)
    assert result.reason == "REAL_RULES_UNAVAILABLE"


def test_formal_metadata_cannot_be_accepted_in_a_test_demo_fixture_path():
    formal = bundle(is_synthetic=False, reference_key="BOUNDARY_ONLY_UNREVIEWED_METADATA")
    assert_unavailable(select(request(), formal))


def test_missing_provider_and_missing_binding_verifier_are_independent_unknowns():
    current = request()
    assert_unavailable(select_rules(current, policy=policy(), provider=None, verifier=lambda query, bound: True))
    assert_unavailable(select_rules(current, policy=policy(), provider=lambda query: (bundle(),), verifier=None))


@pytest.mark.parametrize("answer", [False, None, 0, 1, "true", [True], {"reviewed": True}])
def test_binding_requires_exact_true_not_python_truthiness(answer):
    assert_unavailable(select(request(), bundle(), verifier=lambda query, bound: answer))


@pytest.mark.parametrize("state", ["unreviewed", "withdrawn", "replaced", "conflicted"])
def test_current_binding_port_rejects_review_or_publication_invalidations(state):
    calls = []
    def verifier(query, candidate):
        calls.append((query.target.offering_id, candidate.bundle_id, state))
        return False
    result = select(request(), bundle(), verifier=verifier)
    assert_unavailable(result)
    assert result.reason == "BINDING_UNVERIFIED"
    assert calls == [(request().target.offering_id, BUNDLE, state)]


@pytest.mark.parametrize("port", ["provider", "verifier"])
def test_provider_or_verifier_exceptions_are_safe_unknown_without_secret_values(port):
    def explode(*args):
        raise RuntimeError(SENTINEL)
    result = select(request(), bundle(), **{port: explode})
    assert_unavailable(result)
    assert SENTINEL not in str(result) and SENTINEL not in repr(result)
    assert SENTINEL not in json.dumps(result.model_dump(mode="json"))


@pytest.mark.parametrize("poison", [None, True, "DEMO_bundle", {"reviewed": True},
    lambda: None])
def test_invalid_provider_container_is_not_an_authority_proof(poison):
    assert_unavailable(select(request(), provider=lambda query: poison))


def test_unbounded_generators_are_rejected_without_iteration():
    touched = []
    def streamed():
        touched.append(True)
        yield bundle()
    assert_unavailable(select(request(), provider=lambda query: streamed()))
    assert touched == []
    assert_unavailable(select(request(), provider=lambda query: (bundle(),) * 33))


@pytest.mark.parametrize("tamper", ["scope_hash", "expression_hash", "extra", "bad_ast", "refs", "marker"])
def test_a_bad_second_bundle_cannot_hide_behind_a_matching_first_bundle(tamper):
    good = bundle()
    raw = good.model_dump()
    raw["expression"] = good.expression
    assert select(request(), provider=lambda query: (raw,)).selection_status == "matched"
    raw["bundle_id"] = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
    if tamper == "scope_hash":
        raw["scope"]["campus"] = known("DEMO_changed_campus")
    elif tamper == "expression_hash":
        raw["expression"] = {"op": "exists", "field": {"name": "subjects"}}
    elif tamper == "extra":
        raw["approved"] = SENTINEL
    elif tamper == "bad_ast":
        raw["expression"] = {"op": "any", "children": [{"op": "exists", "field": {"name": "entry_year"}},
            {"op": "exec", "code": SENTINEL}]}
    elif tamper == "refs":
        raw["fact_ids"] = (raw["fact_ids"][0],) * 2
    else:
        raw["is_synthetic"] = 1
    for ordered in ((good, raw), (raw, good)):
        result = select(request(), provider=lambda query, ordered=ordered: ordered)
        assert_unavailable(result)
        assert SENTINEL not in str(result) and SENTINEL not in repr(result)


@pytest.mark.parametrize("mode", ["copy", "construct"])
def test_forged_bundle_instances_cannot_bypass_exact_hash_and_marker_checks(mode):
    good = bundle()
    changed_scope = good.scope.model_copy(update={"campus": known("DEMO_forged_campus")})
    if mode == "copy":
        forged = good.model_copy(update={"scope": changed_scope})
    else:
        forged = RuleBundle.model_construct(**{**good.model_dump(), "scope": changed_scope, "expression": good.expression})
    assert_unavailable(select(request(), forged))


def test_scope_fingerprint_mismatch_is_denied_before_any_binding_verifier():
    current = request()
    candidate = bundle(scope_updates={"campus": known("DEMO_other_campus")})
    visited = []
    def verifier(query, value):
        visited.append(True)
        return True
    assert_unavailable(select(current, candidate, verifier=verifier))
    assert visited == []
    assert select(bind_target(current, candidate), candidate, verifier=verifier).selection_status == "matched"
    assert visited == [True]


@pytest.mark.parametrize("boundary", ["depth", "nodes", "bytes", "reference_count"])
def test_one_oversized_bundle_is_rejected_even_when_another_is_applicable(boundary):
    good = bundle()
    raw = good.model_dump()
    raw["expression"] = good.expression
    assert select(request(), provider=lambda query: (raw,)).selection_status == "matched"
    if boundary == "depth":
        expression = {"op": "exists", "field": {"name": "subjects"}}
        for _ in range(17):
            expression = {"op": "not", "child": expression}
        raw["expression"] = expression
    elif boundary == "nodes":
        leaf = {"op": "exists", "field": {"name": "subjects"}}
        raw["expression"] = {"op": "all", "children": [
            {"op": "all", "children": [deepcopy(leaf) for _ in range(32)]} for _ in range(8)]}
    elif boundary == "bytes":
        raw["expression"] = " " * 65537
    else:
        raw["evidence_ids"] = tuple(UUID(int=n) for n in range(1, 34))
    for ordered in ((raw, good), (good, raw)):
        assert_unavailable(select(request(), provider=lambda query, ordered=ordered: ordered))


def test_provider_cannot_mutate_the_minimal_query_into_a_different_target():
    def provider(query):
        object.__setattr__(query, "entry_year", 2028)
        return (bundle(),)
    assert_unavailable(select(request(), provider=provider))


def test_verifier_cannot_change_the_expression_or_validity_after_preselection():
    candidate = bundle()
    def verifier(query, bound):
        object.__setattr__(bound, "valid_until", NOW)
        return True
    assert_unavailable(select(request(), candidate, verifier=verifier))


def test_custom_timezone_code_is_not_executed_during_native_timestamp_validation():
    touched = []
    class HostileTimezone(tzinfo):
        def utcoffset(self, value):
            touched.append("utcoffset")
            return timedelta(0)
        def dst(self, value):
            touched.append("dst")
            return timedelta(0)
        def tzname(self, value):
            touched.append("tzname")
            return SENTINEL
    raw = request().model_dump()
    raw["assessment_at"] = datetime(2026, 10, 3, tzinfo=HostileTimezone())
    rejected(raw)
    assert touched == []


def test_pure_import_and_explicit_time_ignore_environment_and_do_not_load_db_or_models():
    code = r'''
import builtins, json, socket, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "services/api"))
original_import = builtins.__import__
def isolated_import(name, *args, **kwargs):
    blocked = ("sqlalchemy", "psycopg", "alembic", "httpx", "requests", "openai",
        "app.main", "app.database", "app.models", "app.profiles", "app.providers", "app.seed", "app.settings")
    if any(name == part or name.startswith(part + ".") for part in blocked):
        raise AssertionError("unexpected impure import: " + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = isolated_import
def deny(*args, **kwargs):
    raise AssertionError("scope selection attempted network or DNS")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = deny
from app.rules.adapters import canonical_province, select_rules
from app.rules.adapters.schemas import AdapterPolicy, ScopeRequest
known = lambda value: {"status": "known", "value": value}
scopes = {"residence_region": known("TW"), "course_system": known("gaokao"),
    "applicant_category": known("cn_mainland"), "exam_province": known("Zhejiang"), "pathway": known("gaokao")}
uid = "00000000-0000-4000-8000-000000000001"
request = ScopeRequest(entry_year=2027,study_level="bachelor",**scopes,
    target={"dataset_id":uid,"institution_id":uid,"program_id":uid,"offering_id":uid,
        "offering_version":1,"country":"CN","scope_sha256":"a"*64},
    stage="application",assessment_at=datetime(2026,10,3,tzinfo=timezone.utc),
    **{name:None for name in ("intake","application_cycle","channel","exam_system","subject_scope","batch_group")})
assert canonical_province("zhejiang") == "Zhejiang"
result = select_rules(request,policy=AdapterPolicy())
assert result.selection_status == "unknown" and result.reason == "POLICY_DISABLED"
assert all(not any(name == p or name.startswith(p+".") for p in ("sqlalchemy","psycopg","app.main","app.models","app.profiles","app.providers","app.settings")) for name in sys.modules)
print("T26 pure import and closed default: passed")
'''
    environment = dict(os.environ)
    environment.update({"V2_APP_ENVIRONMENT": "production", "V2_DATA_MODE": "verified", "V2_MODEL_MODE": "live",
        "SUPPORTED_PROVINCE": "Taiwan", "ENTRY_YEAR": "9999", "MODEL_MODE": "live", "DEMO_MODE": "false"})
    completed = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert "T26 pure import and closed default: passed" in completed.stdout
