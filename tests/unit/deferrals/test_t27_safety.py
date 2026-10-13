"""Independent trust-boundary attacks against the pure T27 permission port."""

from datetime import date, datetime, time, timedelta, timezone, tzinfo
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import UUID

import pytest

from app.rules.deferral import (
    DeadlineBinding, DeferralBundle, DeferralInputError, DeferralPolicy,
    DeferralRequest, DeferralResult, evaluate_deferral,
)
from test_t27_matrix import (
    NOW, POLICY_EVIDENCE, APP_EVIDENCE, SUP_EVIDENCE, bundle, deadline,
    evaluate, event, policy, request, unavailable,
)


SENTINEL = "DEMO_PRIVATE_VALUE_MUST_NOT_LEAK"


@pytest.fixture(autouse=True)
def offline_no_socket(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("T27 safety cases must not connect or resolve a host")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def raw_request():
    current = request()
    assert evaluate(current, bundle(current)).deferral_status == "allowed"
    return current.model_dump()


def raw_bundle():
    candidate = bundle()
    assert evaluate(request(), candidate).deferral_status == "allowed"
    return candidate.model_dump()


def input_error(raw, *, configured=None):
    with pytest.raises(DeferralInputError) as caught:
        evaluate_deferral(raw, bundles=(bundle(),), policy=policy() if configured is None else configured,
            verifier=lambda query, candidate: True)
    assert caught.value.status_code == 422 and caught.value.code == "INVALID_DEFERRAL_INPUT"
    assert str(caught.value) == "Deferral input is invalid"
    assert SENTINEL not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize("field,value", [
    ("entry_year", True), ("entry_year", "2027"), ("entry_year", 2027.0),
    ("entry_year", 0), ("entry_year", 10000), ("release_version", False),
    ("release_version", "1"), ("release_version", 0), ("release_version", 2147483648),
    ("requirements_version", "a" * 63), ("requirements_version", "g" * 64),
    ("ruleset_version", "b" * 65), ("release_id", "NOT_A_UUID_" + SENTINEL),
    ("release_id", "00000000000040008000000000000005"),
    ("stage", "offer_acceptance"), ("stage", ["application"]),
    ("assessment_key", "__dict__"), ("assessment_key", ["ielts_overall"]),
    ("basis", "forecast"), ("missing_state", "failed"),
    ("assessment_at", 1791028800), ("assessment_at", True),
    ("assessment_at", "2026-10-03"), ("assessment_at", datetime(2026, 10, 3, 12)),
    ("assessment_at", date(2026, 10, 3)),
])
def test_request_rejects_coercion_paths_and_free_form_untrusted_items(field, value):
    raw = raw_request()
    raw[field] = value
    input_error(raw)


@pytest.mark.parametrize("field", ["owner_user_id", "roles", "grades", "preferences", "reviewed", "conditional"])
def test_private_values_or_self_asserted_authority_are_not_request_fields(field):
    raw = raw_request()
    raw[field] = SENTINEL
    input_error(raw)


@pytest.mark.parametrize("field", ["ruleset_version", "requirements_version", "assessment_at", "target"])
def test_required_request_fields_are_not_defaulted_even_when_nullable(field):
    raw = raw_request()
    del raw[field]
    input_error(raw)


def test_absent_ruleset_is_unknown_instead_of_synthetic_policy_fallback():
    current = request(ruleset_version=None)
    result = evaluate(current, bundle(current, ruleset_version=None))
    unavailable(result)
    assert result.reason == "RULESET_UNAVAILABLE"


@pytest.mark.parametrize("forgery", ["copy", "construct", "nested_target"])
def test_forged_request_models_are_revalidated_at_public_function(forgery):
    current = request()
    if forgery == "copy":
        forged = current.model_copy(update={"entry_year": True})
    elif forgery == "construct":
        forged = DeferralRequest.model_construct(**{**current.model_dump(), "release_version": False})
    else:
        forged_target = current.target.model_copy(update={"scope_sha256": "f" * 63})
        forged = current.model_copy(update={"target": forged_target})
    input_error(forged)


@pytest.mark.parametrize("updates", [
    {"real_deferrals_ready": True}, {"real_deferrals_ready": 0},
    {"enabled": 1}, {"enabled": "true"}, {"allow_test_bundles": 1},
    {"app_environment": "production"}, {"data_mode": "verified"},
    {"reviewed": True},
])
def test_policy_cannot_be_enabled_by_truthiness_or_forged_formal_readiness(updates):
    configured = {**policy().model_dump(), **updates}
    input_error(request(), configured=configured)


@pytest.mark.parametrize("forgery", ["copy", "construct"])
def test_frozen_policy_is_not_a_bypass_to_production_or_real_enable(forgery):
    configured = (policy().model_copy(update={"app_environment": "production"}) if forgery == "copy"
        else DeferralPolicy.model_construct(**{**policy().model_dump(), "real_deferrals_ready": True}))
    input_error(request(), configured=configured)


def test_default_and_formal_boundaries_remain_closed_even_with_true_verifier():
    candidate = bundle()
    default = evaluate_deferral(request(), bundles=(candidate,), verifier=lambda query, value: True)
    unavailable(default)
    assert default.reason == "POLICY_DISABLED"
    for environment in ("development", "test", "production"):
        configured = DeferralPolicy(enabled=True, app_environment=environment, data_mode="verified")
        result = evaluate(request(), candidate, policy=configured)
        unavailable(result)
        assert result.reason == "REAL_POLICIES_UNAVAILABLE"
    formal = bundle(reference_key="REAL_CANDIDATE_NOT_REVIEWED", is_synthetic=False)
    unavailable(evaluate(request(), formal))


@pytest.mark.parametrize("source", [None, (), []])
def test_no_policy_collection_is_not_an_implicit_can_submit_later(source):
    unavailable(evaluate(request(), bundles=source))


def test_generator_and_non_native_container_are_rejected_without_iteration():
    calls = []
    def generating():
        calls.append("iterated")
        yield bundle()
    class DangerousList(list):
        def __iter__(self):
            calls.append("iterated subclass")
            raise RuntimeError(SENTINEL)
        def __len__(self):
            calls.append("length subclass")
            raise RuntimeError(SENTINEL)
    for source in (generating(), DangerousList([bundle()]), {"bundle": bundle()}):
        result = evaluate(request(), bundles=source)
        unavailable(result)
        assert result.reason == "INVALID_BUNDLE"
    assert calls == []


def test_collection_budget_accepts_32_identical_bindings_and_rejects_33_before_verifier():
    current, candidate, calls = request(), bundle(), []
    assert evaluate(current, bundles=[candidate] * 32).deferral_status == "allowed"
    result = evaluate(current, bundles=[candidate] * 33,
        verifier=lambda query, value: calls.append(value.bundle_id) or True)
    unavailable(result)
    assert result.reason == "INVALID_BUNDLE" and calls == []


@pytest.mark.parametrize("field,value", [
    ("policy_version", "f" * 63), ("scope_sha256", "0" * 64),
    ("release_version", True), ("offering_version", False), ("is_synthetic", 1),
    ("reference_key", "REAL_LABELED_SYNTHETIC"), ("application_deadline_required", 1),
    ("assessment_keys", ()), ("assessment_keys", ("ielts_overall",) * 2),
    ("assessment_keys", ("unknown_grade",)), ("assessment_keys", ("ielts_overall",) * 16),
    ("allowed_missing_states", ()), ("allowed_missing_states", ("not_applicable",)),
    ("allowed_missing_states", ("missing", "missing")),
    ("allowed_missing_states", ("missing", "pending", "known")),
    ("policy_evidence_ids", ()), ("policy_evidence_ids", (POLICY_EVIDENCE,) * 2),
    ("policy_evidence_ids", tuple(UUID(int=n) for n in range(33))),
    ("valid_until", NOW - timedelta(days=2)), ("reviewed", True),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_bad_member_cannot_be_hidden_after_a_good_binding_or_filtered_as_another_scope(field, value, reverse):
    bad = raw_bundle()
    bad[field] = value
    # Complete collection validation must precede any first-match selection.
    candidates = (bad, bundle()) if reverse else (bundle(), bad)
    calls = []
    result = evaluate(request(), bundles=candidates, verifier=lambda query, item: calls.append(item) or True)
    unavailable(result)
    assert result.reason == "INVALID_BUNDLE" and calls == []


@pytest.mark.parametrize("path,value", [
    ("reference_calendar", ""), ("reference_calendar", "Europe/London\n"),
    ("evidence_ids", ()), ("evidence_ids", (SUP_EVIDENCE, SUP_EVIDENCE)),
    ("evidence_ids", tuple(UUID(int=n) for n in range(33))),
])
def test_deadline_nullable_fields_and_evidence_bounds_are_not_self_asserted_proof(path, value):
    bad = raw_bundle()
    bad["supplement_deadline"][path] = value
    result = evaluate(request(), bundles=(bad,))
    unavailable(result)
    assert result.reason == "INVALID_BUNDLE"


@pytest.mark.parametrize("field", ["reference_calendar", "evidence_ids"])
def test_required_deadline_nullable_fields_do_not_get_fabricated_defaults(field):
    bad = raw_bundle()
    del bad["supplement_deadline"][field]
    unavailable(evaluate(request(), bundles=(bad,)))


@pytest.mark.parametrize("field,value", [
    ("review_state", "reviewed"), ("evidence_state", "verified"),
    ("utc_instant", datetime(2026, 10, 8, 9, tzinfo=timezone.utc)),
    ("calculated_utc_instant", datetime(2026, 10, 8, 8, tzinfo=timezone.utc)),
    ("conversion_status", "date_only"), ("confirmed", True),
])
def test_candidate_date_cannot_be_upgraded_or_its_mechanical_utc_changed_in_the_policy(field, value):
    good = bundle(supplement_deadline=deadline(precision="minute", local_time=time(10)))
    assert evaluate(request(), good).deferral_status == "allowed"
    bad = good.model_dump()
    bad["supplement_deadline"]["date_event"][field] = value
    result = evaluate(request(), bundles=(bad,))
    unavailable(result)
    assert result.reason == "INVALID_BUNDLE"


@pytest.mark.parametrize("forgery", ["copy", "construct", "nested_copy"])
def test_forged_policy_bundle_models_and_nested_dates_are_revalidated(forgery):
    good = bundle()
    if forgery == "copy":
        bad = good.model_copy(update={"application_deadline_required": "true"})
    elif forgery == "construct":
        bad = DeferralBundle.model_construct(**{**good.model_dump(), "policy_evidence_ids": ()})
    else:
        corrupted_date = good.supplement_deadline.date_event.model_copy(update={"review_state": "reviewed"})
        corrupted_binding = good.supplement_deadline.model_copy(update={"date_event": corrupted_date})
        bad = good.model_copy(update={"supplement_deadline": corrupted_binding})
    result = evaluate(request(), bundles=(bad,))
    unavailable(result)
    assert result.reason == "INVALID_BUNDLE"


@pytest.mark.parametrize("calendar", ["DEMO_UNKNOWN_CALENDAR", "../Europe/London", "+08:00", "Mars/Base"])
def test_unknown_reference_calendar_is_not_replaced_by_server_utc_or_target_country(calendar):
    result = evaluate(request(), bundle(supplement_deadline=deadline(reference_calendar=calendar)))
    unavailable(result)
    assert result.reason == "DEADLINE_UNCERTAIN"


@pytest.mark.parametrize("returned", [False, 1, 1.0, "true", None, [], {"reviewed": True}])
def test_verifier_requires_exact_bool_true_not_truthiness(returned):
    result = evaluate(request(), bundle(), verifier=lambda query, candidate: returned)
    unavailable(result)
    assert result.reason == "BINDING_UNVERIFIED"


def test_missing_or_exceptional_proof_port_returns_safe_unknown_without_exception_data():
    def fail(query, candidate):
        raise RuntimeError(SENTINEL + ": https://private.invalid/grades")
    for verifier in (None, fail):
        result = evaluate(request(), bundle(), verifier=verifier)
        unavailable(result)
        assert result.reason == "VERIFIER_UNAVAILABLE"
        assert SENTINEL not in result.model_dump_json()


@pytest.mark.parametrize("changed", ["query", "bundle", "nested_date"])
def test_callback_cannot_modify_the_binding_which_it_just_claimed_to_verify(changed):
    def alter(query, candidate):
        if changed == "query":
            object.__setattr__(query, "release_version", 2)
        elif changed == "bundle":
            object.__setattr__(candidate, "policy_version", "f" * 64)
        else:
            object.__setattr__(candidate.supplement_deadline.date_event, "original_text", SENTINEL)
        return True
    result = evaluate(request(), bundle(), verifier=alter)
    unavailable(result)
    assert result.reason == "BINDING_UNVERIFIED"
    assert SENTINEL not in result.model_dump_json()


def test_later_verifier_cannot_rewrite_earlier_bundle_to_hide_ambiguous_policy_identity():
    first, second = bundle(), bundle(bundle_id=UUID(int=300))
    baseline = evaluate(request(), first, second)
    unavailable(baseline)
    assert baseline.reason == "AMBIGUOUS_POLICIES"
    previous = []
    def hide_conflict(query, candidate):
        if previous:
            object.__setattr__(previous[0], "bundle_id", candidate.bundle_id)
        previous.append(candidate)
        return True
    result = evaluate(request(), first, second, verifier=hide_conflict)
    unavailable(result)
    assert result.reason == "BINDING_UNVERIFIED" and len(previous) == 2


class TrapTimezone(tzinfo):
    calls = 0
    def utcoffset(self, dt):
        type(self).calls += 1
        raise RuntimeError(SENTINEL)
    def dst(self, dt):
        type(self).calls += 1
        raise RuntimeError(SENTINEL)
    def tzname(self, dt):
        type(self).calls += 1
        raise RuntimeError(SENTINEL)


@pytest.mark.parametrize("location", ["request", "policy_window", "candidate_utc", "official_utc"])
def test_custom_timezone_code_is_never_called_before_native_input_is_rejected(location):
    TrapTimezone.calls = 0
    trap = datetime(2026, 10, 3, tzinfo=TrapTimezone())
    if location == "request":
        raw = raw_request()
        raw["assessment_at"] = trap
        input_error(raw)
    else:
        good = bundle(supplement_deadline=deadline(precision="minute", local_time=time(10)))
        assert evaluate(request(), good).deferral_status == "allowed"
        raw = good.model_dump()
        if location == "policy_window":
            raw["valid_from"] = trap
        else:
            field = "calculated_utc_instant" if location == "candidate_utc" else "utc_instant"
            raw["supplement_deadline"]["date_event"][field] = trap
        unavailable(evaluate(request(), bundles=(raw,)))
    assert TrapTimezone.calls == 0


@pytest.mark.parametrize("raw_native", [datetime(2026, 10, 8), "2026-10-08", [2026, 10, 8]])
def test_nested_local_date_must_be_exact_date_before_legacy_date_validator(raw_native):
    bad = raw_bundle()
    bad["supplement_deadline"]["date_event"]["local_date"] = raw_native
    result = evaluate(request(), bundles=(bad,))
    unavailable(result)
    assert result.reason == "INVALID_BUNDLE"


def test_evidence_merge_is_unique_and_bounded_and_unknown_cannot_keep_selected_authority():
    evidence = tuple(UUID(int=n) for n in range(1000, 1032))
    candidate = bundle(policy_evidence_ids=evidence,
        application_deadline=deadline(supplement=False).model_copy(update={"evidence_ids": evidence}),
        supplement_deadline=deadline().model_copy(update={"evidence_ids": evidence}))
    result = evaluate(request(), candidate)
    assert result.deferral_status == "allowed" and set(result.evidence_ids) == set(evidence)
    raw = result.model_dump()
    raw.update(deferral_status="unknown", reason="POLICY_UNAVAILABLE")
    with pytest.raises(ValueError):
        DeferralResult.model_validate(raw)


def test_import_and_closed_call_are_process_independent_and_do_not_load_business_or_network_modules():
    raw = request().model_dump(mode="json")
    code = r'''
import builtins, json, socket, sys
denied = ('sqlalchemy', 'httpx', 'psycopg', 'app.models', 'app.database',
          'app.auth', 'app.settings', 'app.seed', 'app.providers', 'app.profiles')
original_import = builtins.__import__
def bounded_import(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix + '.') for prefix in denied):
        raise AssertionError('unexpected business dependency: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = bounded_import
def deny(*args, **kwargs):
    raise AssertionError('unexpected network')
socket.socket.connect = socket.socket.connect_ex = deny
socket.create_connection = socket.getaddrinfo = deny
from app.rules.deferral import evaluate_deferral
result = evaluate_deferral(json.loads(sys.argv[1]))
assert result.deferral_status == 'unknown' and result.reason == 'POLICY_DISABLED'
assert not any(any(name == prefix or name.startswith(prefix + '.') for prefix in denied) for name in sys.modules)
print('pure closed call checked')
'''
    task_env = dict(os.environ)
    task_env["PYTHONPATH"] = str(Path(__file__).resolve().parents[3] / "services" / "api")
    task_env.update(V2_APP_ENVIRONMENT="production", V2_DATA_MODE="verified", DEMO_MODE="false")
    completed = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code, json.dumps(raw)],
        cwd=Path(__file__).resolve().parents[3], env=task_env, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "pure closed call checked"
