"""Owned T28 engine seams: exact grade domain and coherent bounded receipts."""

from decimal import localcontext
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.rules.assessment_engine import (CompletionObligation, EligibilityEngineResult,
                                        evaluate_eligibility)
from app.rules.deferral import DeferralResult
from app.rules.evaluator import evaluate_expression
from app.rules.expression import EvaluationContext, RuleInputError


def field(key="math"):
    return {"name": "assessment", "key": key, "basis": "achieved"}


def comparison(value="100", *, key="math", scale="150", op="gte", unit="points"):
    return {"op": op, "field": field(key), "value": {
        "kind": "decimal", "value": value, "unit": unit, "scale": scale}}


def permission():
    # A synthetic already-verified internal T27 result, not a policy verification.
    return DeferralResult(deferral_status="allowed", reason="ALLOWED",
        application_deadline_status="before", supplement_deadline_status="before",
        bundle_id=UUID(int=1), policy_id=UUID(int=2), policy_version="a" * 64,
        application_deadline_event_id=UUID(int=3), supplement_deadline_event_id=UUID(int=4),
        evidence_ids=(UUID(int=5),))


def context(status="missing", value=None):
    return EvaluationContext.model_validate({"fields": [{"field": field(),
        "datum": {"status": status, "value": value}}]})


def conditional():
    return evaluate_eligibility(comparison(), context(), deferrals={"math": permission()})


def test_receipt_keeps_actual_unknown_trace_and_only_original_deferral_obligation():
    expression, supplied, allowed = comparison(), context(), permission()
    before = supplied.model_dump()
    original = evaluate_expression(expression, supplied)
    result = evaluate_eligibility(expression, supplied, deferrals={"math": allowed})
    assert result.status == "conditional" and result.evaluation == original
    assert result.obligations == (CompletionObligation(
        assessment_key="math", basis="achieved", deferral=allowed),)
    assert supplied.model_dump() == before
    assert set(result.obligations[0].model_dump()) == {"assessment_key", "basis", "deferral"}


def test_omitted_achieved_record_is_missing_but_prediction_is_never_completed():
    supplied = EvaluationContext.model_validate({"fields": [{"field": {
        "name": "assessment", "key": "math", "basis": "predicted"},
        "datum": {"status": "known", "value": {
            "kind": "decimal", "value": "120", "unit": "points", "scale": "150"}}}]})
    result = evaluate_eligibility(comparison(), supplied, deferrals={"math": permission()})
    assert result.status == "conditional"
    assert result.obligations[0].basis == "achieved"
    assert supplied.fields[0].datum.value.value == "120"


@pytest.mark.parametrize("threshold,scale,expected", [
    ("0.000001", "0.000001", "conditional"),
    ("9999999.999999", "9999999.999999", "conditional"),
    ("10000000", "10000000", "unknown"),
    ("0.0000001", "0.0000001", "unknown"),
    ("1", "150.0000001", "unknown"),
])
def test_future_grade_and_scale_stay_inside_the_confirmable_profile_domain(threshold, scale, expected):
    result = evaluate_eligibility(comparison(threshold, scale=scale), context(),
        deferrals={"math": permission()})
    assert result.status == expected
    if expected == "unknown":
        assert result.reason == "DOMAIN_UNAVAILABLE" and not result.obligations


def test_equivalent_numeric_scales_do_not_require_identical_decimal_spelling():
    expression = {"op": "all", "children": [comparison("100", scale="150.0000000"),
        comparison("100.000000", scale="150", op="lte")]}
    assert evaluate_eligibility(expression, context(), deferrals={"math": permission()}).status == "conditional"


def test_quantized_search_is_exact_even_under_a_low_process_decimal_precision():
    low = "100.000000" + "0" * 50 + "1"
    upper = "100.000000" + "0" * 50 + "2"
    expression = {"op": "all", "children": [comparison(low), comparison(upper, op="lte")]}
    with localcontext() as decimal_context:
        decimal_context.prec = 2
        result = evaluate_eligibility(expression, context(), deferrals={"math": permission()})
    assert result.status == "unknown" and result.reason == "RULE_UNKNOWN"
    assert not result.obligations


def test_ielts_presence_and_numeric_completion_use_explicit_band_units():
    expression = comparison("6.5", key="ielts_overall", scale="9", unit="band")
    result = evaluate_eligibility(expression, EvaluationContext(), deferrals={"ielts_overall": permission()})
    assert result.status == "conditional"
    assert result.obligations[0].assessment_key == "ielts_overall"


def test_known_zero_is_an_actual_result_and_never_a_missing_grade():
    supplied = context("known", {"kind": "decimal", "value": "0", "unit": "points", "scale": "150"})
    result = evaluate_eligibility(comparison(), supplied, deferrals={"math": permission()})
    assert result.status == "ineligible" and result.reason == "RULE_FALSE" and not result.obligations


@pytest.mark.parametrize("tampered", [
    lambda allowed: {"math": allowed.model_copy(update={"supplement_deadline_status": "expired"})},
    lambda allowed: {"math": DeferralResult.model_construct(**{
        **allowed.model_dump(), "policy_id": None})},
    lambda allowed: {"not_a_grade": allowed},
    lambda allowed: {"math": True},
    lambda allowed: [("math", allowed)],
])
def test_bad_unused_permission_is_rejected_before_an_eligible_short_circuit(tampered):
    definite = {"op": "eq", "field": {"name": "entry_year"},
        "value": {"kind": "integer", "value": 2027}}
    supplied = EvaluationContext.model_validate({"fields": [{"field": {"name": "entry_year"},
        "datum": {"status": "known", "value": {"kind": "integer", "value": 2027}}}]})
    with pytest.raises(RuleInputError) as caught:
        evaluate_eligibility(definite, supplied, deferrals=tampered(permission()))
    assert caught.value.code == "INVALID_RULE_INPUT"


@pytest.mark.parametrize("method", ["model_copy", "model_construct"])
def test_copied_or_constructed_original_input_is_revalidated(method):
    supplied = context()
    forged = (supplied.model_copy(update={"fields": "DEMO_BAD_CONTEXT"}) if method == "model_copy"
        else EvaluationContext.model_construct(fields="DEMO_BAD_CONTEXT"))
    with pytest.raises(RuleInputError) as caught:
        evaluate_eligibility(comparison(), forged, deferrals={"math": permission()})
    assert "DEMO_BAD_CONTEXT" not in str(caught.value)


@pytest.mark.parametrize("patch", [
    {"status": "eligible"}, {"reason": "RULE_TRUE"}, {"evaluation": None}, {"obligations": ()},
])
def test_conditional_receipt_cannot_be_revalidated_after_incoherent_copy(patch):
    with pytest.raises(ValidationError):
        EligibilityEngineResult.model_validate(conditional().model_copy(update=patch))


def test_obligations_cannot_duplicate_or_replace_the_allowed_item_proof():
    result = conditional()
    with pytest.raises(ValidationError):
        EligibilityEngineResult.model_validate(result.model_copy(update={
            "obligations": result.obligations * 2}))
    with pytest.raises(ValidationError):
        CompletionObligation.model_validate(result.obligations[0].model_copy(update={
            "deferral": permission().model_copy(update={"deferral_status": "unknown"})}))


@pytest.mark.parametrize("reason", ["RULESET_UNAVAILABLE", "BINDING_UNAVAILABLE", "SCOPE_UNAVAILABLE"])
def test_unavailable_rule_receipt_has_no_invented_expression_trace(reason):
    result = EligibilityEngineResult(status="unknown", reason=reason, evaluation=None, obligations=())
    assert result.model_dump()["evaluation"] is None


@pytest.mark.parametrize("reason", ["RULE_TRUE", "DEFERRAL_SATISFIABLE", "RULESET_UNAVAILABLE"])
def test_an_evaluated_unknown_receipt_cannot_claim_a_different_reason(reason):
    unknown = evaluate_eligibility(comparison(), context())
    with pytest.raises(ValidationError):
        EligibilityEngineResult.model_validate(unknown.model_copy(update={"reason": reason}))
