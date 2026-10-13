"""Exact test bindings and callback/native-input safety for deferrals."""

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from uuid import UUID

import pytest

from services.api.app.admissions_catalog.date_schemas import DateEventData, DateEventInput
from services.api.app.admissions_catalog.dates import normalize_date_event
from services.api.app.evidence.schemas import EvidenceScope
from services.api.app.rules.adapters import scope_fingerprint
from services.api.app.rules.deferral import (
    DeadlineBinding, DeferralBundle, DeferralInputError, DeferralPolicy,
    DeferralRequest, evaluate_deferral,
)


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def deadline(kind, *, identifier=20, day=date(2026, 10, 10), clock=None,
        precision="date", calendar="Europe/London", zone=None, alignment="pending"):
    source = DateEventInput(id=UUID(int=identifier), dataset_id=UUID(int=1), offering_id=UUID(int=4),
        offering_version=1, entry_year=2027, reference_key="DEMO_DEADLINE_" + str(identifier),
        is_synthetic=True, event_type=kind, original_text="DEMO independent deadline",
        local_date=day, local_time=clock, precision=precision, timezone=zone,
        source_alignment=alignment, evidence_reference=None)
    resolution = normalize_date_event(source)
    event = DateEventData(**source.model_dump(), **resolution.model_dump(),
        utc_instant=None, review_state="draft", evidence_state="unresolved")
    return DeadlineBinding(date_event=event, reference_calendar=calendar, evidence_ids=(UUID(int=identifier + 100),))


def values(*, stage="application", key="ielts_overall", application_required=True):
    known = lambda value: {"status": "known", "value": value}
    scope = EvidenceScope(dataset_id=UUID(int=1), institution_id=UUID(int=2), program_id=UUID(int=3),
        country="GB", entry_year=2027, study_level="undergraduate",
        **{name: known("DEMO_" + name) for name in ("degree", "course", "campus", "teaching_language",
            "progression_pathway", "intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")},
        course_system=known("gaokao"), pathway=known("uk_undergraduate"),
        applicant_category=known("cn_mainland"), province={"status": "not_applicable", "value": None})
    request = DeferralRequest(target={"dataset_id": UUID(int=1), "institution_id": UUID(int=2),
        "program_id": UUID(int=3), "offering_id": UUID(int=4), "offering_version": 1,
        "country": "GB", "scope_sha256": scope_fingerprint(scope)},
        entry_year=2027, stage=stage, release_id=UUID(int=5), release_version=1,
        requirements_version="a" * 64, ruleset_version="b" * 64,
        assessment_key=key, basis="achieved", missing_state="pending", assessment_at=NOW)
    bundle = DeferralBundle(bundle_id=UUID(int=6), reference_key="DEMO_T27_POLICY",
        policy_id=UUID(int=7), policy_version="c" * 64, release_id=request.release_id, release_version=1,
        requirements_version=request.requirements_version, ruleset_version=request.ruleset_version,
        is_synthetic=True, scope=scope, scope_sha256=scope_fingerprint(scope), offering_id=UUID(int=4),
        offering_version=1, stage=stage, assessment_keys=(key,), allowed_missing_states=("missing", "pending"),
        valid_from=NOW - timedelta(days=2), valid_until=NOW + timedelta(days=30),
        policy_evidence_ids=(UUID(int=100),), application_deadline_required=application_required,
        application_deadline=deadline("application_deadline", identifier=20) if application_required else None,
        supplement_deadline=deadline("language_supplement" if key.startswith("ielts_") else "score_supplement", identifier=21))
    policy = DeferralPolicy(enabled=True, allow_test_bundles=True, app_environment="test", data_mode="demo")
    return request, bundle, policy


def decide(request, bundle, policy, **overrides):
    return evaluate_deferral(request, bundles=(bundle,), policy=policy,
        verifier=overrides.get("verifier", lambda query, current: True))


def test_result_is_one_item_permission_with_minimal_refs_and_no_four_state():
    request, bundle, policy = values()
    visited = []
    def verify(query, current):
        visited.append(set(query.model_dump()))
        assert query.basis == "achieved" and query.assessment_key == "ielts_overall"
        assert current.supplement_deadline.date_event.utc_instant is None
        return True
    result = decide(request, bundle, policy, verifier=verify)
    assert result.deferral_status == "allowed" and result.reason == "ALLOWED"
    assert visited == [{"target", "entry_year", "stage", "release_id", "release_version",
        "requirements_version", "ruleset_version", "assessment_key", "basis"}]
    assert result.evidence_ids == (UUID(int=100), UUID(int=120), UUID(int=121))
    assert not {"eligible", "conditional", "assessment_at", "missing_state", "grade"}.intersection(result.model_dump())


@pytest.mark.parametrize("change", [{"release_version": True}, {"assessment_at": "2026-10-03"},
    {"requirements_version": "a" * 64 + "\n"}, {"assessment_key": "general_language"},
    {"reviewed": True}])
def test_malformed_request_has_only_the_fixed_safe_input_error(change):
    request, bundle, policy = values()
    with pytest.raises(DeferralInputError) as caught:
        evaluate_deferral(request.model_copy(update=change), bundles=(bundle,), policy=policy)
    assert caught.value.status_code == 422 and caught.value.code == "INVALID_DEFERRAL_INPUT"
    assert str(caught.value) == "Deferral input is invalid"


def test_current_group_policy_expiry_is_not_hidden_by_another_valid_bundle():
    request, good, policy = values()
    bad = good.model_copy(update={"bundle_id": UUID(int=9), "valid_until": NOW})
    for ordered in ((good, bad), (bad, good)):
        result = evaluate_deferral(request, bundles=ordered, policy=policy, verifier=lambda query, bundle: True)
        assert result.deferral_status == "unknown" and result.reason == "POLICY_EXPIRED"


def test_later_callback_cannot_rewrite_a_previous_verified_binding():
    request, first, policy = values()
    second = first.model_copy(update={"bundle_id": UUID(int=10)})
    retained = []
    def verifier(query, bundle):
        if retained:
            object.__setattr__(retained[0], "bundle_id", bundle.bundle_id)
        retained.append(bundle)
        return True
    result = evaluate_deferral(request, bundles=(first, second), policy=policy, verifier=verifier)
    assert len(retained) == 2
    assert result.deferral_status == "unknown" and result.reason == "BINDING_UNVERIFIED"


def test_a_forged_custom_timezone_never_executes_older_date_validator_callbacks():
    touched = []
    class HostileTimezone(tzinfo):
        def utcoffset(self, value):
            touched.append(True)
            raise RuntimeError("DEMO_SECRET_CALLBACK")
    request, bundle, policy = values()
    binding = bundle.supplement_deadline
    event = binding.date_event.model_copy(update={"calculated_utc_instant": datetime(2026, 10, 3, tzinfo=HostileTimezone())})
    forged = bundle.model_copy(update={"supplement_deadline": binding.model_copy(update={"date_event": event})})
    result = decide(request, forged, policy)
    assert result.deferral_status == "unknown" and result.reason == "INVALID_BUNDLE"
    assert touched == []
    with pytest.raises(DeferralInputError):
        decide(request.model_copy(update={"assessment_at": datetime(2026, 10, 3, tzinfo=HostileTimezone())}), bundle, policy)
    assert touched == []
