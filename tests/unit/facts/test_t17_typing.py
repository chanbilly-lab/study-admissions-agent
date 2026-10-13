"""Offline intrinsic classification tests, without approving any institution fact."""

from datetime import date, datetime, time, timezone
from decimal import Decimal, localcontext
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
from services.api.app.facts.schemas import (
    Classification, DateResolutionSnapshot, FactCreate, FactPolicy, FactsError,
    TypedCandidate, TypedPayload,
)
from services.api.app.facts.typing import normalize_decimal, type_candidate
from services.api.app.ingestion.schemas import ParsedRow


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
OFFERING = uuid4()
DATASET = uuid4()
EVIDENCE = uuid4()


def row(**changes):
    values = dict(offering_id=OFFERING, offering_version=1, entry_year=2027,
        source_record_reference="DEMO_T17_original_record", fact_type="score", field_key="DEMO_math",
        value_kind="decimal", value_text="600.00", unit="DEMO_original_points",
        missing_reason=None, footnote_state="none", footnote_text=None, locator=None, row_number=1)
    return ParsedRow(**{**values, **changes})


def classification(**changes):
    values = dict(claim_kind="minimum_requirement", unit_code="points", period="not_applicable",
        statistics_basis="not_applicable", statistic_population=None, statistic_denominator=None,
        cohort_year=None, survey_period=None, date_event_id=None)
    return Classification(**{**values, **changes})


def typed(source=None, interpretation=None, *, evidence_id=EVIDENCE, date_resolution=None):
    return type_candidate(source if source is not None else row(),
        interpretation if interpretation is not None else classification(),
        evidence_id=evidence_id, date_resolution=date_resolution)


def candidate(payload=None, **changes):
    payload = payload if payload is not None else typed()
    fields = dict(id=uuid4(), version=1, import_id=uuid4(), import_row_id=uuid4(), dataset_id=DATASET,
        is_synthetic=True, created_at=NOW, conflicting_ids=())
    return TypedCandidate(**{**payload.model_dump(), **fields, **changes})


def snapshot(**changes):
    fields = dict(id=uuid4(), dataset_id=DATASET, offering_id=OFFERING, offering_version=1,
        entry_year=2027, reference_key="DEMO_T17_date", is_synthetic=True,
        event_type="application_deadline", original_text="DEMO_2027-01-15 deadline",
        local_date=date(2027, 1, 15), local_time=time(12, 30), timezone="UTC", precision="minute",
        source_alignment="pending", evidence_reference=None)
    source = DateEventInput(**{**fields, **changes})
    resolved = normalize_date_event(source)
    return DateResolutionSnapshot.from_date_event(DateEventData(**source.model_dump(),
        **resolved.model_dump(), utc_instant=None, review_state="draft", evidence_state="unresolved"))


def date_payload(current):
    return typed(row(fact_type="date", field_key="DEMO_deadline", value_kind="text",
        value_text=current.original_text, unit="DEMO_local_date"),
        classification(unit_code="ISO_DATE", date_event_id=current.date_event_id), date_resolution=current)


def test_high_precision_canonical_equivalence_is_independent_of_decimal_context():
    raw = "1" * 60 + ".100"
    adjacent = "1" * 60 + ".101"
    assert len(raw) == len(adjacent) == 64
    with localcontext() as context:
        context.prec = 2
        first = typed(row(value_text=raw))
        equivalent = typed(row(value_text="1" * 60 + ".1"))
        second = typed(row(value_text=adjacent))
    assert first.normalized_value == equivalent.normalized_value == "1" * 60 + ".1"
    assert second.normalized_value == adjacent and second.normalized_value != first.normalized_value
    assert first.value_text == raw and first.unit == "DEMO_original_points"


@pytest.mark.parametrize("raw,normalized", [("0", "0"), ("-0.000", "0"), ("42.000", "42"),
    ("0.00000100", "0.000001"), ("9" * 64, "9" * 64)])
def test_exact_decimal_normalization_and_negative_zero(raw, normalized):
    assert normalize_decimal(raw) == normalized


@pytest.mark.parametrize("invalid", [0.1, Decimal("1"), True, "1e2", "NaN", "01", "1.", "+1", "1" * 65])
def test_decimal_helper_rejects_nonlexical_or_unbounded_values(invalid):
    with pytest.raises(FactsError) as error:
        normalize_decimal(invalid)
    assert str(error.value) == "INVALID_FACT_INPUT"


def test_claim_interpretations_are_explicit_separate_and_never_executable():
    interpretations = [classification(), classification(claim_kind="typical_offer"),
        classification(claim_kind="historical_statistic", statistics_basis="admission",
            statistic_population="DEMO_admitted students", statistic_denominator="DEMO_all enrolled",
            cohort_year=2025, survey_period="DEMO_2025 survey")]
    outputs = [typed(interpretation=value) for value in interpretations]
    assert {value.classification.claim_kind for value in outputs} == {
        "minimum_requirement", "typical_offer", "historical_statistic"}
    assert all(value.state == "review_required" and value.hard_rule is False
        and value.publication_eligible is False for value in outputs)


@pytest.mark.parametrize("source,interpretation", [
    (row(fact_type="fee"), classification()),
    (row(fact_type="statistic"), classification()),
    (row(fact_type="fee"), classification(claim_kind="information", unit_code="points")),
    (row(fact_type="score", value_kind="text", value_text="DEMO_high"), classification(unit_code="text")),
    (row(fact_type="requirement"), classification(claim_kind="historical_statistic")),
])
def test_closed_fact_claim_unit_matrix_rejects_category_mixups(source, interpretation):
    with pytest.raises(FactsError):
        typed(source, interpretation)


def test_requirement_subject_language_material_and_fee_remain_informational_candidates():
    sources = [
        (row(fact_type="requirement", value_kind="text", value_text="DEMO_math and physics"),
            classification(unit_code="text")),
        (row(fact_type="requirement", value_kind="text", value_text="DEMO_language score report"),
            classification(unit_code="text", claim_kind="typical_offer")),
        (row(fact_type="material", value_kind="text", value_text="DEMO_personal statement"),
            classification(unit_code="text")),
        (row(fact_type="material", value_text="2.00"), classification(unit_code="item")),
        (row(fact_type="fee", value_text="4600.00", unit="DEMO_currency/year"),
            classification(claim_kind="information", unit_code="CNY", period="academic_year")),
    ]
    for source, interpretation in sources:
        found = typed(source, interpretation)
        assert found.state == "review_required" and found.hard_rule is False
        assert found.unit == source.unit and found.classification.period == interpretation.period


def test_numeric_unit_boundaries_do_not_guess_a_score_scale():
    for unit, valid, invalid in (("percent", "100.000", "100.0001"),
                               ("fraction", "1.000", "1.0001")):
        assert typed(row(value_text=valid), classification(unit_code=unit)).normalized_value == valid.split(".")[0]
        with pytest.raises(FactsError):
            typed(row(value_text=invalid), classification(unit_code=unit))
    assert typed(row(value_text="9000000.125")).normalized_value == "9000000.125"
    with pytest.raises(FactsError):
        typed(row(value_text="-0.01"))
    with pytest.raises(FactsError):
        typed(row(fact_type="material", value_text="2.01"), classification(unit_code="item"))


def test_missing_zero_and_footnotes_are_distinct_without_inference():
    zero = typed(row(value_text="0.000"))
    assert zero.normalized_value == "0" and zero.state == "review_required"
    for reason in ("not_provided", "not_applicable", "not_published", "unavailable", "ambiguous"):
        absent = typed(row(value_text=None, missing_reason=reason))
        assert absent.normalized_value is None and absent.missing_reason == reason and absent.state == "draft"
    unknown = typed(row(footnote_state="unknown"))
    present = typed(row(footnote_state="present", footnote_text="DEMO_subject to review"))
    assert unknown.state == "draft" and present.state == "review_required"
    assert present.footnote_text == "DEMO_subject to review"


def test_unknown_classification_evidence_and_period_stay_draft_without_defaults():
    for change in ({"claim_kind": "unknown"}, {"unit_code": "unknown"}, {"period": "unknown"}):
        assert typed(interpretation=classification(**change)).state == "draft"
    assert typed(evidence_id=None).state == "draft"
    assert classification().cohort_year is None and classification().survey_period is None
    with pytest.raises(ValidationError):
        Classification(**{name: value for name, value in classification().model_dump().items() if name != "period"})


def test_statistics_information_also_requires_its_own_population_and_denominator():
    complete = classification(claim_kind="information", unit_code="people", period="survey_period",
        statistics_basis="employment", statistic_population="DEMO_2025 graduates",
        statistic_denominator="0", cohort_year=2025, survey_period="DEMO_2026-01 survey")
    source = row(fact_type="statistic", value_text="0.0")
    assert typed(source, complete).state == "review_required"
    for missing in ("statistic_population", "statistic_denominator", "cohort_year", "survey_period"):
        assert typed(source, complete.model_copy(update={missing: None})).state == "draft"
    assert typed(source, complete.model_copy(update={"statistics_basis": "unknown"})).state == "draft"
    with pytest.raises(FactsError):
        typed(row(fact_type="statistic", value_text="0.1"), complete)


def test_context_bounds_are_utf8_bytes_and_do_not_trim_or_normalize_original_text():
    good = classification(statistic_population="界" * 170, survey_period="界" * 33)
    assert good.statistic_population == "界" * 170
    for changes in ({"statistic_population": "界" * 171}, {"survey_period": "界" * 34},
                    {"statistic_denominator": "\ud800"}, {"cohort_year": True}, {"cohort_year": "2025"}):
        with pytest.raises(ValidationError):
            Classification.model_validate(good.model_copy(update=changes))
    original = " DEMO_é  e\u0301\n "
    found = typed(row(fact_type="requirement", value_kind="text", value_text=original), classification(unit_code="text"))
    assert found.normalized_value == found.value_text == original


def test_date_snapshot_preserves_original_identity_precision_and_never_official_utc():
    current = snapshot()
    found = date_payload(current)
    assert found.state == "review_required" and found.date_resolution.calculated_utc_instant is not None
    assert found.date_resolution.utc_instant is None and current.reference_key == "DEMO_T17_date"
    assert current.is_synthetic is True and current.evidence_reference is None
    date_only = snapshot(precision="date", local_time=None, timezone=None)
    assert date_payload(date_only).state == "review_required"
    assert date_only.local_time is None and date_only.timezone is None and date_only.calculated_utc_instant is None


def test_ambiguous_nonexistent_unknown_and_conflicting_dates_stay_draft():
    dates = [snapshot(local_date=date(2026, 10, 25), local_time=time(1, 30), timezone="Europe/London"),
        snapshot(local_date=date(2026, 3, 29), local_time=time(1, 30), timezone="Europe/London"),
        snapshot(precision="unknown", local_date=None, local_time=None, timezone=None),
        snapshot(source_alignment="conflict")]
    assert {current.conversion_status for current in dates} == {"ambiguous", "nonexistent", "unknown", "source_conflict"}
    for current in dates:
        assert current.calculated_utc_instant is None and current.utc_instant is None
        assert date_payload(current).state == "draft"


def test_date_snapshot_copies_cannot_inject_utc_fold_timezone_or_wrong_namespace():
    current = snapshot()
    for changes in ({"utc_instant": NOW}, {"calculated_utc_instant": NOW},
        {"local_time": time(12, 30, fold=1)}, {"timezone": "EST"},
        {"is_synthetic": False}, {"evidence_reference": "real_evidence"}):
        with pytest.raises(ValidationError):
            DateResolutionSnapshot.model_validate(current.model_copy(update=changes))
    forged = DateResolutionSnapshot.model_construct(**{**current.model_dump(), "conversion_status": "ambiguous"})
    with pytest.raises(ValidationError):
        DateResolutionSnapshot.model_validate(forged)


def test_date_binding_is_exact_and_not_inferred_from_year_or_field_name():
    current = snapshot()
    for changes in ({"offering_id": uuid4()}, {"offering_version": 2}, {"entry_year": 2028},
                    {"value_text": current.original_text + " "}):
        with pytest.raises(FactsError):
            typed(row(**{**dict(fact_type="date", value_kind="text", value_text=current.original_text), **changes}),
                classification(unit_code="ISO_DATE", date_event_id=current.date_event_id), date_resolution=current)
    with pytest.raises(FactsError):
        typed(row(), classification(date_event_id=current.date_event_id), date_resolution=current)
    assert typed(row(fact_type="date", value_kind="text", value_text="DEMO_date missing"),
        classification(unit_code="ISO_DATE")).state == "draft"


def test_candidate_revalidates_derived_state_scope_namespace_and_strict_markers():
    valid = candidate()
    assert valid.state == "review_required" and valid.version == 1
    with pytest.raises(ValidationError):
        valid.state = "draft"
    for changes in ({"version": True}, {"version": 1.0}, {"normalized_value": "601"},
        {"hard_rule": True}, {"publication_eligible": 0}, {"state": "published"},
        {"is_synthetic": False}, {"owner_id": uuid4()}, {"created_at": NOW.replace(tzinfo=None)}):
        with pytest.raises(ValidationError):
            TypedCandidate.model_validate(valid.model_copy(update=changes))
    dated = candidate(date_payload(snapshot()))
    for changes in ({"dataset_id": uuid4()}, {"is_synthetic": False}):
        with pytest.raises(ValidationError):
            TypedCandidate.model_validate(dated.model_copy(update=changes))


def test_conflict_output_requires_distinct_other_ids_and_never_rewrites_payload():
    current = candidate()
    other = uuid4()
    conflicted = TypedCandidate.model_validate(current.model_copy(update={"state": "conflicted", "conflicting_ids": (other,)}))
    assert conflicted.value_text == current.value_text and conflicted.publication_eligible is False
    for changes in ({"state": "conflicted"}, {"conflicting_ids": (other,)},
        {"state": "conflicted", "conflicting_ids": (other, other)},
        {"state": "conflicted", "conflicting_ids": (current.id,)},
        {"state": "conflicted", "conflicting_ids": tuple(uuid4() for _ in range(201))}):
        with pytest.raises(ValidationError):
            TypedCandidate.model_validate(current.model_copy(update=changes))


def test_payload_and_input_constructs_do_not_bypass_original_validation_or_leak_errors():
    good = typed()
    for changes in ({"value_text": "NaN_SENTINEL"}, {"offering_version": True},
                    {"classification": classification().model_copy(update={"unit_code": "SENTINEL"})}):
        with pytest.raises(FactsError) as error:
            source = row().model_copy(update=changes) if "classification" not in changes else row()
            typed(source, changes.get("classification"))
        assert str(error.value) == "INVALID_FACT_INPUT" and "SENTINEL" not in str(error.value)
    forged = TypedPayload.model_construct(**{**good.model_dump(), "publication_eligible": True})
    with pytest.raises(ValidationError):
        TypedPayload.model_validate(forged)
    request = FactCreate(import_id=uuid4(), import_row_id=uuid4(), classification=classification(), evidence_id=None)
    with pytest.raises(ValidationError):
        FactCreate.model_validate(request.model_copy(update={"evidence_id": "DEMO_not_uuid"}))
    assert FactPolicy().model_dump() == {"enabled": False, "real_facts_ready": False}


def test_fresh_pure_import_has_no_database_model_network_or_ambient_enablement():
    code = """
import json, sys
from services.api.app.facts.schemas import FactPolicy
from services.api.app.facts.typing import normalize_decimal
for prefix in ('sqlalchemy', 'httpx', 'services.api.app.auth', 'services.api.app.main', 'services.api.app.database', 'services.api.app.providers'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
assert FactPolicy().enabled is False and FactPolicy().real_facts_ready is False
assert normalize_decimal('1.000') == '1'
print(json.dumps({'pure': True}))
"""
    environment = {**os.environ, "FACTS_ENABLED": "true", "REAL_FACTS_READY": "true", "V2_DATA_MODE": "DEMO_SENTINEL"}
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(__file__).resolve().parents[3],
        env=environment, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"pure": True}
