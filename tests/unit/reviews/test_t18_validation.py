"""DEMO human-check contracts; passing syntax does not perform human review."""

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.app.admissions_catalog.date_schemas import DateEventData, DateEventInput
from services.api.app.admissions_catalog.dates import normalize_date_event
from services.api.app.admissions_catalog.schemas import ScopeKey
from services.api.app.evidence.locators import extract_snippet
from services.api.app.evidence.schemas import EvidenceScope, SnippetData
from services.api.app.facts.schemas import Classification, DateResolutionSnapshot, TypedCandidate
from services.api.app.facts.typing import type_candidate
from services.api.app.ingestion.schemas import ParsedRow
from services.api.app.reviews.schemas import (
    CHECK_FIELDS, ConflictResolution, ReviewCaseData, ReviewCheck, ReviewDecisionData,
    ReviewPolicy, ReviewRequest, ReviewsError,
)
from services.api.app.reviews.validation import SCOPE_FIELDS, validate_review


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
DATASET, OFFERING, EVIDENCE = uuid4(), uuid4(), uuid4()


def classification(**changes):
    values = dict(claim_kind="minimum_requirement", unit_code="points", period="not_applicable",
        statistics_basis="not_applicable", statistic_population=None, statistic_denominator=None,
        cohort_year=None, survey_period=None, date_event_id=None)
    return Classification(**{**values, **changes})


def fact(*, interpretation=None, date_resolution=None, evidence_id=EVIDENCE, conflicts=(), **changes):
    values = dict(offering_id=OFFERING, offering_version=1, entry_year=2027,
        source_record_reference="DEMO_T18_record", fact_type="score", field_key="DEMO_score",
        value_kind="decimal", value_text="600.00", unit="DEMO_points", missing_reason=None,
        footnote_state="present", footnote_text="DEMO_conditions apply", locator=None, row_number=1)
    row = ParsedRow(**{**values, **changes})
    payload = type_candidate(row, interpretation if interpretation is not None else classification(),
        evidence_id=evidence_id, date_resolution=date_resolution)
    data = dict(**payload.model_dump(), id=uuid4(), version=1, import_id=uuid4(), import_row_id=uuid4(),
        dataset_id=DATASET, is_synthetic=True, created_at=NOW, conflicting_ids=conflicts)
    if conflicts:
        data["state"] = "conflicted"
    return TypedCandidate(**data)


def checks(*, statistics="not_applicable", date_context="not_applicable", **changes):
    values = {field: "accepted" for field in CHECK_FIELDS}
    values.update(statistics_context=statistics, date_context=date_context, **changes)
    return tuple(ReviewCheck(field=field, status=values[field]) for field in CHECK_FIELDS)


def request(candidate, **changes):
    values = dict(fact_id=candidate.id, expected_fact_version=1, expected_case_revision=0,
        action="approve", checks=checks(), conflict_resolutions=(), return_reason=None)
    return ReviewRequest(**{**values, **changes})


def evidence(candidate, *, text=None, **changes):
    source = json.dumps({"value_text": candidate.value_text, "unit": candidate.unit,
        "footnote": candidate.footnote_text}, ensure_ascii=False, indent=2).encode("utf-8")
    if text is not None:
        source = json.dumps({"excerpt": text}, ensure_ascii=False).encode("utf-8")
    located = extract_snippet(source, media_type="application/json", byte_start=0, byte_end=len(source))
    scope = EvidenceScope(dataset_id=DATASET, program_id=uuid4(), institution_id=uuid4(),
        country="CN", study_level="undergraduate", entry_year=candidate.entry_year,
        **{field: ScopeKey(status="not_applicable", value=None) for field in SCOPE_FIELDS})
    fields = dict(**located.model_dump(), id=EVIDENCE, document_id=uuid4(), document_version=1,
        offering_id=candidate.offering_id, offering_version=candidate.offering_version,
        entry_year=candidate.entry_year, language="und", document_sha256=sha256(source).hexdigest(),
        is_synthetic=True, created_at=NOW, scope=scope)
    return SnippetData(**{**fields, **changes})


def date_snapshot(**changes):
    values = dict(id=uuid4(), dataset_id=DATASET, offering_id=OFFERING, offering_version=1,
        entry_year=2027, reference_key="DEMO_T18_date", is_synthetic=True,
        event_type="application_deadline", original_text="DEMO_2027 deadline", local_date=date(2027, 1, 15),
        local_time=time(12, 30), timezone="UTC", precision="minute", source_alignment="pending",
        evidence_reference=None)
    original = DateEventInput(**{**values, **changes})
    resolved = normalize_date_event(original)
    return DateResolutionSnapshot.from_date_event(DateEventData(**original.model_dump(),
        **resolved.model_dump(), utc_instant=None, review_state="draft", evidence_state="unresolved"))


def test_valid_checks_and_literal_reference_do_not_mutate_candidate_into_a_rule():
    candidate = fact()
    before = candidate.model_dump()
    assert validate_review(request(candidate), candidate, evidence(candidate)) is None
    assert candidate.model_dump() == before and candidate.hard_rule is False and candidate.publication_eligible is False


def test_request_requires_all_ten_unique_explicit_checks_even_for_return():
    candidate = fact()
    original = request(candidate)
    for bad in (original.checks[:-1], (*original.checks[:-1], original.checks[0]), (*original.checks, original.checks[0])):
        with pytest.raises(ValidationError):
            ReviewRequest.model_validate(original.model_copy(update={"checks": bad}))
    returned = original.model_copy(update={"action": "return", "return_reason": "INVALID_VALUE", "checks": original.checks[:-1]})
    with pytest.raises(ValidationError):
        ReviewRequest.model_validate(returned)


@pytest.mark.parametrize("change", [{"original_value": "rejected"}, {"scope": "not_applicable"},
                                  {"evidence_location": "rejected"}, {"date_context": "rejected"}])
def test_approve_needs_explicit_accepted_critical_checks(change):
    with pytest.raises(ValidationError):
        request(fact(), checks=checks(**change))


def test_unknown_or_freeform_status_reason_role_and_timestamp_inputs_are_rejected():
    original = request(fact())
    for changes in ({"expected_fact_version": True}, {"expected_case_revision": "0"},
        {"expected_case_revision": -1}, {"reviewer_user_id": uuid4()}, {"created_at": NOW},
        {"role": "data_admin"}, {"return_reason": "SENTINEL_reason"}, {"action": "publish"}):
        with pytest.raises(ValidationError):
            ReviewRequest.model_validate(original.model_copy(update=changes))
    with pytest.raises(ValidationError):
        ReviewCheck(field="original_value", status=True)
    with pytest.raises(ValidationError):
        ConflictResolution(fact_id=uuid4(), reason_code="SENTINEL_freeform")


def test_return_records_a_finite_human_reason_without_fabricating_completeness():
    candidate = fact(value_text=None, missing_reason="not_published", footnote_state="unknown", footnote_text=None)
    returned = request(candidate, action="return", return_reason="MISSING_CONTEXT",
        checks=checks(original_value="rejected", missingness="rejected", footnote="rejected"))
    assert validate_review(returned, candidate, None) is None
    for changes in ({"return_reason": None}, {"conflict_resolutions": (ConflictResolution(fact_id=uuid4(), reason_code="WRONG_CONTEXT"),)}):
        with pytest.raises(ValidationError):
            ReviewRequest.model_validate(returned.model_copy(update=changes))
    with pytest.raises(ValidationError):
        request(fact(), return_reason="INVALID_VALUE")


def test_conflicted_history_cannot_approve_an_underlying_draft():
    other = uuid4()
    candidate = fact(conflicts=(other,), value_text=None, missing_reason="unavailable")
    proposed = request(candidate, conflict_resolutions=(ConflictResolution(fact_id=other, reason_code="SELECTED_SUPPORTED"),))
    assert candidate.state == "conflicted"
    with pytest.raises(ReviewsError) as error:
        validate_review(proposed, candidate, evidence(candidate))
    assert error.value.status_code == 422


def test_complete_conflicts_require_exact_other_candidate_set_not_a_default_winner():
    peers = (uuid4(), uuid4())
    candidate = fact(conflicts=peers)
    resolutions = tuple(ConflictResolution(fact_id=peer, reason_code="SELECTED_SUPPORTED") for peer in peers)
    assert validate_review(request(candidate, conflict_resolutions=resolutions), candidate, evidence(candidate)) is None
    for proposed in ((), resolutions[:1], (*resolutions, ConflictResolution(fact_id=uuid4(), reason_code="INCORRECT_VALUE"))):
        with pytest.raises(ReviewsError) as error:
            validate_review(request(candidate, conflict_resolutions=proposed), candidate, evidence(candidate))
        assert error.value.status_code == 409
    for proposed in ((resolutions[0], resolutions[0]), (ConflictResolution(fact_id=candidate.id, reason_code="WRONG_CONTEXT"),)):
        with pytest.raises(ValidationError):
            request(candidate, conflict_resolutions=proposed)


def test_every_program_and_offering_scope_must_be_explicitly_nonunknown():
    candidate = fact()
    original = evidence(candidate)
    assert len(SCOPE_FIELDS) == 15
    for field in SCOPE_FIELDS:
        changed_scope = original.scope.model_copy(update={field: ScopeKey(status="unknown", value=None)})
        with pytest.raises(ReviewsError):
            validate_review(request(candidate), candidate, original.model_copy(update={"scope": changed_scope}))


def test_evidence_binding_location_and_bounded_copy_constructs_are_revalidated():
    candidate, proposed = fact(), None
    proposed = request(candidate)
    original = evidence(candidate)
    for changed in (None, original.model_copy(update={"id": uuid4()}),
        original.model_copy(update={"offering_id": uuid4()}), original.model_copy(update={"offering_version": 2}),
        original.model_copy(update={"is_synthetic": False}),
        original.model_copy(update={"scope": original.scope.model_copy(update={"dataset_id": uuid4()})}),
        original.model_copy(update={"snippet_sha256": "a" * 64}),
        original.model_copy(update={"locator": original.locator.model_copy(update={"page": 1})}),
        SnippetData.model_construct(**{**original.model_dump(), "text": "SENTINEL_forged"})):
        with pytest.raises(ReviewsError) as error:
            validate_review(proposed, candidate, changed)
        assert error.value.status_code == 422 and "SENTINEL" not in str(error.value)
    with pytest.raises(ReviewsError) as error:
        validate_review(proposed.model_copy(update={"fact_id": uuid4()}), candidate, original)
    assert error.value.status_code == 409


@pytest.mark.parametrize("other", ["160.00", "-60.00", "60.001", "60.00e2", "+60.00", ".60.00", "−60.00", "６60.00"])
def test_decimal_literal_match_rejects_longer_negative_or_exponent_tokens(other):
    candidate = fact(value_text="60.00")
    with pytest.raises(ReviewsError):
        validate_review(request(candidate), candidate, evidence(candidate,
            text=f"DEMO_value {other} DEMO_points DEMO_conditions apply"))


def test_raw_decimal_literal_is_not_replaced_by_its_normalized_equivalent():
    candidate = fact(value_text="60.00")
    assert candidate.normalized_value == "60"
    with pytest.raises(ReviewsError):
        validate_review(request(candidate), candidate, evidence(candidate,
            text="DEMO_value 60 DEMO_points DEMO_conditions apply"))
    assert validate_review(request(candidate), candidate, evidence(candidate,
        text="DEMO_value 60.00 DEMO_points DEMO_conditions apply")) is None


def test_unit_and_footnote_text_require_the_same_literal_excerpt_with_word_boundaries():
    candidate = fact(unit="point")
    for text in ("600.00 points DEMO_conditions apply", "600.00 point", "600.00 point DEMO_conditions applied"):
        with pytest.raises(ReviewsError):
            validate_review(request(candidate), candidate, evidence(candidate, text=text))
    assert validate_review(request(candidate), candidate, evidence(candidate,
        text="600.00 point DEMO_conditions apply")) is None
    chinese_unit = fact(unit="分")
    assert validate_review(request(chinese_unit), chinese_unit, evidence(chinese_unit,
        text="600.00分；DEMO_conditions apply")) is None


def test_complex_json_escapes_and_separate_footnotes_are_not_automatically_decoded():
    candidate = fact(fact_type="requirement", value_kind="text", value_text='DEMO_quoted "condition"',
        interpretation=classification(unit_code="text"))
    with pytest.raises(ReviewsError):
        validate_review(request(candidate), candidate, evidence(candidate))
    returned = request(candidate, action="return", return_reason="UNSUPPORTED_LITERAL")
    assert validate_review(returned, candidate, evidence(candidate)) is None


def test_chinese_unit_prefixes_are_not_exact_units_but_quoted_units_can_be_compared():
    for unit, other in (("元", "万元"), ("元", "港元"), ("港币", "万港币"), ("分", "分数")):
        candidate = fact(unit=unit)
        with pytest.raises(ReviewsError):
            validate_review(request(candidate), candidate, evidence(candidate,
                text=f"600.00 {other} DEMO_conditions apply"))
    quoted = fact(fact_type="fee", unit="元", interpretation=classification(claim_kind="information", unit_code="CNY"))
    assert validate_review(request(quoted), quoted, evidence(quoted)) is None


def test_zero_is_valid_but_missing_unknown_claim_period_or_footnote_cannot_be_approved():
    zero = fact(value_text="0.00")
    assert validate_review(request(zero), zero, evidence(zero)) is None
    drafts = [fact(value_text=None, missing_reason="not_provided"), fact(evidence_id=None),
        fact(interpretation=classification(claim_kind="unknown")),
        fact(interpretation=classification(period="unknown")),
        fact(interpretation=classification(unit_code="unknown")),
        fact(footnote_state="unknown", footnote_text=None)]
    for candidate in drafts:
        with pytest.raises(ReviewsError):
            validate_review(request(candidate), candidate, evidence(candidate))


def test_statistics_applicability_and_complete_context_are_independent_checks():
    interpretation = classification(claim_kind="historical_statistic", statistics_basis="admission",
        statistic_population="DEMO_admitted", statistic_denominator="DEMO_total students",
        cohort_year=2025, survey_period="DEMO_2025 survey")
    candidate = fact(interpretation=interpretation)
    approved = request(candidate, checks=checks(statistics="accepted"))
    assert validate_review(approved, candidate, evidence(candidate)) is None
    with pytest.raises(ReviewsError):
        validate_review(request(candidate), candidate, evidence(candidate))
    ordinary = fact()
    with pytest.raises(ReviewsError):
        validate_review(request(ordinary, checks=checks(statistics="accepted")), ordinary, evidence(ordinary))
    incomplete = fact(interpretation=interpretation.model_copy(update={"statistic_denominator": None}))
    with pytest.raises(ReviewsError):
        validate_review(request(incomplete, checks=checks(statistics="accepted")), incomplete, evidence(incomplete))


def test_date_precision_context_and_candidate_utc_remain_t12_values_after_approval_gate():
    current = date_snapshot()
    candidate = fact(fact_type="date", value_kind="text", value_text=current.original_text,
        unit="DEMO_local_date", interpretation=classification(unit_code="ISO_DATE", date_event_id=current.date_event_id),
        date_resolution=current)
    assert validate_review(request(candidate, checks=checks(date_context="accepted")), candidate, evidence(candidate)) is None
    assert candidate.date_resolution.utc_instant is None
    with pytest.raises(ReviewsError):
        validate_review(request(candidate), candidate, evidence(candidate))
    ambiguous = date_snapshot(local_date=date(2026, 10, 25), local_time=time(1, 30), timezone="Europe/London")
    draft = fact(fact_type="date", value_kind="text", value_text=ambiguous.original_text,
        unit="DEMO_local_date", interpretation=classification(unit_code="ISO_DATE", date_event_id=ambiguous.date_event_id),
        date_resolution=ambiguous)
    with pytest.raises(ReviewsError):
        validate_review(request(draft, checks=checks(date_context="accepted")), draft, evidence(draft))


def test_decision_server_utc_projection_is_frozen_and_cannot_approve_a_return():
    candidate = fact()
    actions = request(candidate).model_dump(exclude={"expected_fact_version", "expected_case_revision"})
    decision = ReviewDecisionData(**actions, decision_id=uuid4(), case_id=uuid4(), case_revision=1,
        reviewer_user_id=uuid4(), created_at=NOW.astimezone(timezone(timedelta(hours=8))),
        is_synthetic=True, current_approved=True)
    assert decision.created_at == NOW and decision.created_at.utcoffset() == timedelta(0)
    with pytest.raises(ValidationError):
        decision.current_approved = False
    for changes in ({"case_revision": True}, {"is_synthetic": "true"}, {"current_approved": 1},
        {"created_at": NOW.replace(tzinfo=None)}, {"action": "return", "return_reason": "INVALID_VALUE"},
        {"path": "SENTINEL_path"}):
        with pytest.raises(ValidationError):
            ReviewDecisionData.model_validate(decision.model_copy(update=changes))


def test_case_projection_retains_history_but_does_not_promote_missing_or_stale_decisions():
    missing = ReviewCaseData(case_id=None, logical_key_hash="a" * 64, case_revision=0,
        chosen_fact_id=None, current_decision_id=None, current_approved=False, is_synthetic=True)
    old = ReviewCaseData(**{**missing.model_dump(), "case_id": uuid4(), "case_revision": 1,
        "chosen_fact_id": uuid4(), "current_decision_id": uuid4()})
    assert old.chosen_fact_id is not None and old.current_approved is False
    for value in (missing.model_copy(update={"current_approved": True}),
        old.model_copy(update={"case_revision": 0}), old.model_copy(update={"current_decision_id": None}),
        old.model_copy(update={"current_approved": True, "chosen_fact_id": None})):
        with pytest.raises(ValidationError):
            ReviewCaseData.model_validate(value)


def test_forged_fact_request_and_decision_constructs_are_strictly_revalidated():
    candidate = fact()
    original = request(candidate)
    forged = ReviewRequest.model_construct(**{**original.model_dump(), "expected_fact_version": True})
    with pytest.raises(ReviewsError):
        validate_review(forged, candidate, evidence(candidate))
    for changes in ({"normalized_value": "601"}, {"hard_rule": True}, {"is_synthetic": False}):
        with pytest.raises(ReviewsError):
            validate_review(original, candidate.model_copy(update=changes), evidence(candidate))
    assert ReviewPolicy().model_dump() == {"enabled": False, "real_reviews_ready": False}


def test_fresh_pure_import_has_no_database_network_or_ambient_policy_enablement():
    code = """
import sys
from services.api.app.reviews.schemas import ReviewPolicy
from services.api.app.reviews.validation import validate_review
for prefix in ('sqlalchemy', 'httpx', 'services.api.app.auth', 'services.api.app.main', 'services.api.app.database', 'services.api.app.providers'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
assert ReviewPolicy().enabled is False and ReviewPolicy().real_reviews_ready is False
print('pure reviews')
"""
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(__file__).resolve().parents[3],
        env={**os.environ, "REVIEWS_ENABLED": "true", "REAL_REVIEWS_READY": "true"},
        text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "pure reviews"
