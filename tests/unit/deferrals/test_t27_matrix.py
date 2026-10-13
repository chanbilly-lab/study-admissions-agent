"""Independent calendar and policy gold cases using only DEMO proof fixtures."""

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
import socket
from uuid import UUID

import pytest

from app.admissions_catalog.date_schemas import DateEventData, DateEventInput
from app.admissions_catalog.dates import normalize_date_event
from app.evidence.schemas import EvidenceScope
from app.rules.deferral import (
    DeadlineBinding, DeferralBundle, DeferralPolicy, DeferralRequest, evaluate_deferral,
)


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
DATASET, INSTITUTION, PROGRAM, OFFERING, RELEASE, BUNDLE, POLICY, APPLICATION, SUPPLEMENT, POLICY_EVIDENCE, APP_EVIDENCE, SUP_EVIDENCE = (
    UUID(f"00000000-0000-4000-8000-{n:012d}") for n in range(1, 13))
SCOPE_FIELDS = ("degree", "course", "campus", "teaching_language", "progression_pathway",
    "intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")


@pytest.fixture(autouse=True)
def offline_no_socket(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("T27 gold cases must not connect or resolve a host")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def known(value):
    return {"status": "known", "value": value}


def scope(**updates):
    payload = {"dataset_id": DATASET, "institution_id": INSTITUTION, "program_id": PROGRAM,
        "country": "GB", "study_level": "undergraduate", "entry_year": 2027,
        **{key: known("DEMO_" + key) for key in SCOPE_FIELDS},
        "course_system": known("gaokao"), "pathway": known("uk_undergraduate"),
        "applicant_category": known("cn_mainland"), "province": {"status": "not_applicable", "value": None}}
    payload.update(updates)
    return EvidenceScope.model_validate(payload)


def scope_hash(value):
    return sha256(json.dumps(value.model_dump(mode="json"), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def request(**updates):
    payload = {"target": {"dataset_id": DATASET, "institution_id": INSTITUTION,
        "program_id": PROGRAM, "offering_id": OFFERING, "offering_version": 1,
        "country": "GB", "scope_sha256": scope_hash(scope())},
        "entry_year": 2027, "stage": "application", "release_id": RELEASE, "release_version": 1,
        "requirements_version": "a" * 64, "ruleset_version": "b" * 64,
        "assessment_key": "ielts_overall", "basis": "achieved", "missing_state": "missing",
        "assessment_at": NOW}
    payload.update(updates)
    return DeferralRequest.model_validate(payload)


def event(*, supplement=True, precision="date", local_date=None, local_time=None,
        zone="Europe/London", event_type=None, **updates):
    payload = {"id": SUPPLEMENT if supplement else APPLICATION, "dataset_id": DATASET,
        "offering_id": OFFERING, "offering_version": 1, "entry_year": 2027,
        "reference_key": "DEMO_SUPPLEMENT_EVENT" if supplement else "DEMO_APPLICATION_EVENT",
        "is_synthetic": True, "event_type": event_type or ("language_supplement" if supplement else "application_deadline"),
        "original_text": "DEMO_合成政策日期；不是实际院校截止。",
        "precision": precision, "local_date": local_date or date(2026, 10, 8 if supplement else 10),
        "local_time": local_time, "timezone": zone, "source_alignment": "pending",
        "evidence_reference": "DEMO_T27_DATE_REFERENCE"}
    if precision == "unknown":
        payload.update(local_date=None, local_time=None, timezone=None)
    payload.update(updates)
    original = DateEventInput.model_validate(payload)
    calculated = normalize_date_event(original)
    return DateEventData(**original.model_dump(), **calculated.model_dump(),
        utc_instant=None, review_state="draft", evidence_state="unresolved")


def deadline(*, supplement=True, reference_calendar="Europe/London", **event_updates):
    return DeadlineBinding(date_event=event(supplement=supplement, **event_updates),
        evidence_ids=(SUP_EVIDENCE if supplement else APP_EVIDENCE,), reference_calendar=reference_calendar)


def bundle(supplied=None, **updates):
    current = request() if supplied is None else supplied
    payload = {"bundle_id": BUNDLE, "reference_key": "DEMO_T27_POLICY_FIXTURE", "policy_id": POLICY,
        "policy_version": "c" * 64, "release_id": RELEASE, "release_version": 1,
        "requirements_version": "a" * 64, "ruleset_version": "b" * 64, "is_synthetic": True,
        "scope": scope(), "scope_sha256": scope_hash(scope()), "offering_id": OFFERING,
        "offering_version": 1, "stage": current.stage, "assessment_keys": (current.assessment_key,),
        "allowed_missing_states": ("missing", "pending"),
        "valid_from": current.assessment_at - timedelta(days=1),
        "valid_until": current.assessment_at + timedelta(days=30), "policy_evidence_ids": (POLICY_EVIDENCE,),
        "application_deadline_required": True, "application_deadline": deadline(supplement=False),
        "supplement_deadline": deadline()}
    payload.update(updates)
    if "scope" in updates and "scope_sha256" not in updates:
        payload["scope_sha256"] = scope_hash(payload["scope"])
    return DeferralBundle.model_validate(payload)


def policy(**updates):
    return DeferralPolicy.model_validate({"enabled": True, "allow_test_bundles": True,
        "real_deferrals_ready": False, "app_environment": "test", "data_mode": "demo", **updates})


def evaluate(current=None, *policies, **updates):
    current = request() if current is None else current
    return evaluate_deferral(current, bundles=updates.pop("bundles", policies),
        policy=updates.pop("policy", policy()), verifier=updates.pop("verifier", lambda query, value: True), **updates)


def unavailable(result):
    assert result.deferral_status == "unknown"
    assert all(getattr(result, field) is None for field in ("bundle_id", "policy_id", "policy_version",
        "application_deadline_event_id", "supplement_deadline_event_id"))
    assert not result.evidence_ids


def bind_target(current, candidate):
    raw = current.model_dump()
    raw["target"]["scope_sha256"] = candidate.scope_sha256
    return DeferralRequest.model_validate(raw)


def test_explicit_synthetic_policy_can_allow_one_unresolved_achieved_item_without_changing_fact_status():
    candidate = bundle()
    before = candidate.model_dump()
    result = evaluate(request(), candidate)
    assert result.deferral_status == "allowed"
    assert result.application_deadline_status == result.supplement_deadline_status == "before"
    assert result.policy_id == POLICY and result.policy_version == "c" * 64
    assert result.application_deadline_event_id == APPLICATION and result.supplement_deadline_event_id == SUPPLEMENT
    assert set(result.evidence_ids) == {POLICY_EVIDENCE, APP_EVIDENCE, SUP_EVIDENCE}
    assert candidate.model_dump() == before
    for binding in (candidate.application_deadline, candidate.supplement_deadline):
        assert binding.date_event.review_state == "draft" and binding.date_event.utc_instant is None
        assert binding.date_event.evidence_state == "unresolved"


@pytest.mark.parametrize("status", ["missing", "pending"])
def test_policy_must_explicitly_allow_the_current_missing_state(status):
    current = request(missing_state=status)
    assert evaluate(current, bundle(current)).deferral_status == "allowed"
    other = "pending" if status == "missing" else "missing"
    unavailable(evaluate(current, bundle(current, allowed_missing_states=(other,))))


@pytest.mark.parametrize("basis,status", [("predicted", "missing"), ("predicted", "pending"),
    ("achieved", "known"), ("achieved", "not_applicable"), ("achieved", "conflicted")])
def test_predictions_failed_or_unusable_values_do_not_gain_deferral_as_missing(basis, status):
    current = request(basis=basis, missing_state=status)
    unavailable(evaluate(current, bundle(current)))


@pytest.mark.parametrize("key", ["ielts_overall", "ielts_listening", "ielts_reading", "ielts_writing", "ielts_speaking"])
def test_language_permission_is_bound_to_the_exact_required_component(key):
    current = request(assessment_key=key)
    assert evaluate(current, bundle(current)).deferral_status == "allowed"
    alternative = "ielts_listening" if key != "ielts_listening" else "ielts_writing"
    unavailable(evaluate(current, bundle(current, assessment_keys=(alternative,))))


@pytest.mark.parametrize("key", ["gaokao_total", "math", "physics", "gaokao_english"])
def test_non_language_achieved_scores_require_score_supplement_evidence(key):
    current = request(assessment_key=key)
    assert evaluate(current, bundle(current, supplement_deadline=deadline(event_type="score_supplement"))).deferral_status == "allowed"
    unavailable(evaluate(current, bundle(current)))


@pytest.mark.parametrize("event_type", ["application_deadline", "equal_consideration", "materials_deadline",
    "enrollment", "offer_acceptance", "scholarship_deadline", "score_supplement"])
def test_other_events_cannot_replace_a_language_supplement_deadline(event_type):
    unavailable(evaluate(request(), bundle(supplement_deadline=deadline(event_type=event_type))))


@pytest.mark.parametrize("event_type", ["equal_consideration", "materials_deadline", "language_supplement", "enrollment"])
def test_application_requirement_needs_its_own_application_deadline_event(event_type):
    unavailable(evaluate(request(), bundle(application_deadline=deadline(supplement=False, event_type=event_type))))


def test_application_cannot_borrow_a_later_supplement_window():
    current = request(assessment_at=datetime(2026, 10, 6, 12, tzinfo=timezone.utc))
    candidate = bundle(current, application_deadline=deadline(supplement=False, local_date=date(2026, 10, 5)))
    result = evaluate(current, candidate)
    unavailable(result)
    assert result.application_deadline_status == "expired"
    # The independent supplement deadline is still in the future.
    assert candidate.supplement_deadline.date_event.local_date == date(2026, 10, 8)


@pytest.mark.parametrize("missing", ["application_deadline", "supplement_deadline"])
def test_each_required_deadline_must_be_present(missing):
    unavailable(evaluate(request(), bundle(**{missing: None})))


def test_enrollment_explicitly_can_exclude_application_deadline_without_inferring_a_stage():
    current = request(stage="enrollment")
    candidate = bundle(current, application_deadline_required=False, application_deadline=None)
    result = evaluate(current, candidate)
    assert result.deferral_status == "allowed" and result.application_deadline_status == "not_applicable"
    assert result.supplement_deadline_status == "before"
    application = request()
    unavailable(evaluate(application, bundle(application, application_deadline_required=False, application_deadline=None)))


def test_enrollment_required_application_window_remains_independent_and_mandatory():
    current = request(stage="enrollment")
    assert evaluate(current, bundle(current)).deferral_status == "allowed"
    stale = deadline(supplement=False, local_date=date(2026, 10, 2))
    unavailable(evaluate(current, bundle(current, application_deadline=stale)))
    unavailable(evaluate(current, bundle(stage="application")))


@pytest.mark.parametrize("assessment,status", [
    (datetime(2026, 10, 7, 12, tzinfo=timezone.utc), "before"),
    (datetime(2026, 10, 8, 0, tzinfo=timezone.utc), "unknown"),
    (datetime(2026, 10, 8, 22, tzinfo=timezone.utc), "unknown"),
    (datetime(2026, 10, 9, 12, tzinfo=timezone.utc), "expired")])
def test_date_only_before_same_day_and_after_never_create_midnight_or_2359(assessment, status):
    current = request(assessment_at=assessment)
    result = evaluate(current, bundle(current))
    assert result.supplement_deadline_status == status
    if status == "before":
        assert result.deferral_status == "allowed"
    else:
        unavailable(result)


@pytest.mark.parametrize("zone,assessment,expected", [
    ("Europe/London", datetime(2026, 10, 7, 23, 30, tzinfo=timezone.utc), "unknown"),
    ("Europe/London", datetime(2026, 10, 7, 22, 30, tzinfo=timezone.utc), "before"),
    ("America/New_York", datetime(2026, 10, 8, 2, tzinfo=timezone.utc), "before"),
    ("Asia/Hong_Kong", datetime(2026, 10, 7, 18, tzinfo=timezone.utc), "unknown")])
def test_source_calendar_day_is_not_utc_day_or_inferred_from_uk_target_country(zone, assessment, expected):
    current = request(assessment_at=assessment)
    candidate = bundle(current, supplement_deadline=deadline(zone=zone, reference_calendar=zone))
    result = evaluate(current, candidate)
    assert result.supplement_deadline_status == expected
    if expected == "before":
        assert result.deferral_status == "allowed"
    else:
        unavailable(result)


@pytest.mark.parametrize("precision", ["minute", "second"])
@pytest.mark.parametrize("assessment,status", [
    (datetime(2026, 10, 8, 8, 59, 59, tzinfo=timezone.utc), "before"),
    (datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc), "unknown"),
    (datetime(2026, 10, 8, 9, 0, 1, tzinfo=timezone.utc), "expired")])
def test_precise_deadline_strictly_before_equal_and_after_requires_independent_review(precision, assessment, status):
    current = request(assessment_at=assessment)
    exact = deadline(precision=precision, local_time=time(10, 0))
    assert exact.date_event.calculated_utc_instant == datetime(2026, 10, 8, 9, tzinfo=timezone.utc)
    candidate = bundle(current, supplement_deadline=exact)
    result = evaluate(current, candidate)
    assert result.supplement_deadline_status == status
    if status == "before":
        assert result.deferral_status == "allowed"
    else:
        unavailable(result)
    unavailable(evaluate(current, candidate, verifier=None))


@pytest.mark.parametrize("precision,local_time", [("date", None), ("minute", time(10, 0)), ("second", time(10, 0, 1))])
def test_missing_reference_calendar_is_not_completed_from_event_or_country(precision, local_time):
    candidate = bundle(supplement_deadline=deadline(precision=precision, local_time=local_time, reference_calendar=None))
    unavailable(evaluate(request(), candidate))


@pytest.mark.parametrize("zone,local_date,local_time,expected", [
    ("Europe/London", date(2026, 3, 29), time(1, 30), "nonexistent"),
    ("Europe/London", date(2026, 10, 25), time(1, 30), "ambiguous"),
    ("Australia/Lord_Howe", date(2026, 4, 5), time(1, 45), "ambiguous")])
def test_dst_gap_or_fold_does_not_pick_a_candidate_instant(zone, local_date, local_time, expected):
    current = request(assessment_at=datetime(2026, 3, 20, tzinfo=timezone.utc))
    ambiguous = deadline(zone=zone, reference_calendar=zone, precision="minute", local_date=local_date, local_time=local_time)
    assert ambiguous.date_event.conversion_status == expected
    assert ambiguous.date_event.calculated_utc_instant is None
    unavailable(evaluate(current, bundle(current, supplement_deadline=ambiguous)))


@pytest.mark.parametrize("binding", [
    deadline(precision="unknown"),
    deadline(precision="minute", local_time=time(10), zone=None),
    deadline(source_alignment="conflict"),
    deadline(precision="minute", local_time=time(10), reference_calendar="Asia/Shanghai")])
def test_unknown_time_source_conflict_or_different_reference_calendar_cannot_allow(binding):
    unavailable(evaluate(request(), bundle(supplement_deadline=binding)))


@pytest.mark.parametrize("field,update", [("entry_year", 2026), ("release_version", 2),
    ("release_id", UUID(int=100)), ("requirements_version", "d" * 64), ("ruleset_version", "e" * 64)])
def test_other_release_or_year_is_not_current_supplement_policy(field, update):
    unavailable(evaluate(request(**{field: update}), bundle()))


@pytest.mark.parametrize("dimension", ["dataset_id", "institution_id", "program_id", "offering_id", "offering_version", "scope_sha256"])
def test_policy_exact_target_and_scope_pin_is_not_just_same_school_name(dimension):
    raw = request().model_dump()
    raw["target"][dimension] = (2 if dimension == "offering_version" else "f" * 64 if dimension == "scope_sha256" else UUID(int=100))
    unavailable(evaluate(DeferralRequest.model_validate(raw), bundle()))


@pytest.mark.parametrize("dimension", ["campus", "course_system", "province", "channel", "application_cycle", "subject_scope"])
def test_full_policy_scope_uses_raw_fingerprint_and_unknown_is_not_a_wildcard(dimension):
    current = request()
    changed = bundle(scope=scope(**{dimension: known("DEMO_other_scope")}))
    unavailable(evaluate(current, changed))
    incomplete = bundle(scope=scope(**{dimension: {"status": "unknown", "value": None}}))
    unavailable(evaluate(bind_target(current, incomplete), incomplete))


@pytest.mark.parametrize("field,update", [("dataset_id", UUID(int=100)), ("offering_id", UUID(int=100)),
    ("offering_version", 2), ("entry_year", 2026), ("is_synthetic", False)])
def test_date_event_must_belong_to_the_exact_policy_offering_year_and_mode(field, update):
    if field == "is_synthetic":
        update_data = {field: update, "reference_key": "UNBOUND_EVENT", "evidence_reference": None}
    else:
        update_data = {field: update}
    unavailable(evaluate(request(), bundle(supplement_deadline=deadline(**update_data))))


@pytest.mark.parametrize("assessment,allowed", [(NOW - timedelta(days=1), True), (NOW + timedelta(days=1), False)])
def test_policy_validity_window_is_half_open_and_separate_from_school_deadline(assessment, allowed):
    current = request(assessment_at=assessment)
    candidate = bundle(current, valid_from=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=1))
    result = evaluate(current, candidate)
    if allowed:
        assert result.deferral_status == "allowed"
    else:
        unavailable(result)


@pytest.mark.parametrize("invalidity", ["expired", "missing_ruleset", "withdrawn"])
def test_valid_policy_cannot_hide_an_invalid_same_binding_in_either_order(invalidity):
    current = request()
    good = bundle()
    second_id = UUID(int=100)
    updates = {"bundle_id": second_id}
    if invalidity == "expired":
        updates["valid_until"] = NOW
    elif invalidity == "missing_ruleset":
        updates["ruleset_version"] = None
    bad = bundle(**updates)
    for ordered in ((good, bad), (bad, good)):
        unavailable(evaluate(current, *ordered,
            verifier=lambda query, value: not (invalidity == "withdrawn" and value.bundle_id == second_id)))


def test_two_current_policy_versions_are_not_first_match_in_either_order():
    first = bundle()
    second = bundle(bundle_id=UUID(int=100), policy_version="d" * 64)
    for ordered in ((first, second), (second, first)):
        unavailable(evaluate(request(), *ordered))


def test_unrelated_stage_or_item_can_be_filtered_without_hiding_current_binding_failures():
    current = request()
    unrelated_stage = bundle(stage="enrollment", application_deadline_required=False, application_deadline=None)
    unrelated_item = bundle(assessment_keys=("ielts_reading",))
    for other in (unrelated_stage, unrelated_item):
        assert evaluate(current, bundle(), other).deferral_status == "allowed"
        assert evaluate(current, other, bundle()).deferral_status == "allowed"


def test_query_and_result_are_minimum_references_not_grades_or_a_four_state_conclusion():
    seen = []
    def verifier(query, value):
        seen.append(query.model_dump(mode="json"))
        return True
    result = evaluate(request(missing_state="pending"), bundle(), verifier=verifier)
    assert result.deferral_status == "allowed"
    assert len(seen) == 1
    assert set(seen[0]) == {"target", "entry_year", "stage", "release_id", "release_version",
        "requirements_version", "ruleset_version", "assessment_key", "basis"}
    assert set(result.model_dump()) == {"deferral_status", "reason", "application_deadline_status",
        "supplement_deadline_status", "bundle_id", "policy_id", "policy_version",
        "application_deadline_event_id", "supplement_deadline_event_id", "evidence_ids"}
    assert "missing_state" not in seen[0] and "assessment_at" not in seen[0]
