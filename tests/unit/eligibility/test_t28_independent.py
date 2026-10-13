"""Independent T28 gold cases, without storing any completion witness as a grade."""

from datetime import datetime, timezone
from itertools import permutations, product
import socket
from uuid import UUID

import pytest

from app.rules.assessment_engine import evaluate_eligibility
from app.rules.deferral import DeferralResult
from app.rules.expression import EvaluationContext, RuleInputError


@pytest.fixture(autouse=True)
def offline_no_socket(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("T28 independent engine cases must not use networking")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def field(key="math", basis="achieved"):
    return {"name": "assessment", "key": key, "basis": basis}


def decimal(value="100", unit="points", scale="150"):
    return {"kind": "decimal", "value": value, "unit": unit, "scale": scale}


def comparison(op="gte", value="100", *, key="math", unit="points", scale="150", basis="achieved"):
    return {"op": op, "field": field(key, basis), "value": decimal(value, unit, scale)}


def context(*records, assessment_at=None):
    supplied = [{"field": {"name": "entry_year"}, "datum": {"status": "known",
        "value": {"kind": "integer", "value": 2027}}}]
    supplied.extend({"field": reference, "datum": {"status": status, "value": value}}
        for reference, status, value in records)
    return EvaluationContext.model_validate({"fields": supplied,
        "assessment_date": None, "assessment_at": assessment_at})


def allowed():
    # This is only a synthetic result at the already-verified T27 internal seam.
    # T28 service tests separately prove its exact policy/release/evidence origin.
    return DeferralResult(deferral_status="allowed", reason="ALLOWED",
        application_deadline_status="before", supplement_deadline_status="before",
        bundle_id=UUID(int=1), policy_id=UUID(int=2), policy_version="a" * 64,
        application_deadline_event_id=UUID(int=3), supplement_deadline_event_id=UUID(int=4),
        evidence_ids=(UUID(int=5),))


def unresolved():
    return DeferralResult(deferral_status="unknown", reason="POLICY_UNAVAILABLE",
        application_deadline_status="unknown", supplement_deadline_status="unknown",
        bundle_id=None, policy_id=None, policy_version=None,
        application_deadline_event_id=None, supplement_deadline_event_id=None, evidence_ids=())


def atom(symbol):
    if symbol == "D":
        return comparison()
    if symbol == "U":
        return {"op": "eq", "field": {"name": "course_system"},
            "value": {"kind": "text", "value": "gaokao"}}
    return {"op": "eq", "field": {"name": "entry_year"},
        "value": {"kind": "integer", "value": 2027 if symbol == "T" else 2028}}


ALL_GOLD = {
    "TT": "eligible", "TF": "ineligible", "TU": "unknown", "TD": "conditional",
    "FT": "ineligible", "FF": "ineligible", "FU": "ineligible", "FD": "ineligible",
    "UT": "unknown", "UF": "ineligible", "UU": "unknown", "UD": "unknown",
    "DT": "conditional", "DF": "ineligible", "DU": "unknown", "DD": "conditional",
}
ANY_GOLD = {
    "TT": "eligible", "TF": "eligible", "TU": "eligible", "TD": "eligible",
    "FT": "eligible", "FF": "ineligible", "FU": "unknown", "FD": "conditional",
    "UT": "eligible", "UF": "unknown", "UU": "unknown", "UD": "conditional",
    "DT": "eligible", "DF": "conditional", "DU": "conditional", "DD": "conditional",
}


@pytest.mark.parametrize("operator,table", [("all", ALL_GOLD), ("any", ANY_GOLD)])
@pytest.mark.parametrize("left,right", list(product("TFUD", repeat=2)))
def test_full_four_state_gold_tables_select_only_a_complete_satisfiable_path(operator, table, left, right):
    supplied = context((field(), "missing", None))
    result = evaluate_eligibility({"op": operator, "children": [atom(left), atom(right)]},
        supplied, deferrals={"math": allowed()})
    assert result.status == table[left + right]
    assert len(result.evaluation.trace) == 3
    assert result.evaluation.trace[0].children == (1, 2)
    if result.status == "conditional":
        assert [(item.assessment_key, item.basis) for item in result.obligations] == [("math", "achieved")]
    else:
        assert result.obligations == ()


@pytest.mark.parametrize("symbol,expected", [("T", "ineligible"), ("F", "eligible"),
    ("U", "unknown"), ("D", "conditional")])
def test_not_keeps_the_original_predicate_polarity_instead_of_setting_unknown_to_true(symbol, expected):
    result = evaluate_eligibility({"op": "not", "child": atom(symbol)},
        context((field(), "missing", None)), deferrals={"math": allowed()})
    assert result.status == expected
    assert len(result.evaluation.trace) == 2


@pytest.mark.parametrize("negations,expected", [(0, "conditional"), (1, "unknown"),
    (2, "conditional"), (3, "unknown")])
def test_exists_completion_is_presence_only_and_cannot_fulfil_not_exists(negations, expected):
    expression = {"op": "exists", "field": field()}
    for _ in range(negations):
        expression = {"op": "not", "child": expression}
    result = evaluate_eligibility(expression, context((field(), "pending", None)), deferrals={"math": allowed()})
    assert result.status == expected
    assert result.evaluation.truth == "unknown"


@pytest.mark.parametrize("expression,expected", [
    ({"op": "not", "child": {"op": "not", "child": comparison()}}, "conditional"),
    ({"op": "all", "children": [comparison("gte", "100"), comparison("lte", "90")]}, "unknown"),
    ({"op": "all", "children": [comparison("eq", "100"), {"op": "not", "child": comparison("eq", "100")}]}, "unknown"),
    ({"op": "all", "children": [comparison("gte", "120"), {"op": "not", "child": comparison("gte", "100")}]}, "unknown"),
    ({"op": "all", "children": [comparison("gte", "100"), comparison("lte", "120")]}, "conditional"),
    ({"op": "all", "children": [{"op": "not", "child": comparison("gte", "120")}, comparison("gte", "100")]}, "conditional"),
])
def test_one_future_grade_is_shared_across_repeated_and_negated_numeric_conditions(expression, expected):
    supplied = context((field(), "missing", None))
    before = supplied.model_dump()
    result = evaluate_eligibility(expression, supplied, deferrals={"math": allowed()})
    assert result.status == expected
    assert result.evaluation.truth == "unknown"
    assert supplied.model_dump() == before
    assert "value" not in {name for item in result.obligations for name in item.model_dump()}


@pytest.mark.parametrize("lower,upper,expected", [
    ("100.0000001", "100.0000002", "unknown"),
    ("100.0000001", "100.000001", "conditional"),
    ("0.0000001", "0.0000009", "unknown"),
    ("0", "0", "conditional"),
    ("150", "150", "conditional"),
])
def test_future_grade_must_exist_on_the_confirmable_t23_micro_quantum(lower, upper, expected):
    expression = {"op": "all", "children": [comparison("gte", lower), comparison("lte", upper)]}
    result = evaluate_eligibility(expression, context((field(), "missing", None)), deferrals={"math": allowed()})
    assert result.status == expected


@pytest.mark.parametrize("expression", [
    {"op": "not", "child": comparison("gte", "0")},
    {"op": "not", "child": comparison("lte", "150")},
    {"op": "all", "children": [comparison("gte", "0"), {"op": "not", "child": {"op": "exists", "field": field()}}]},
])
def test_domain_edges_and_presence_cannot_be_satisfied_by_negative_or_out_of_scale_values(expression):
    result = evaluate_eligibility(expression, context((field(), "missing", None)), deferrals={"math": allowed()})
    assert result.status == "unknown" and not result.obligations


@pytest.mark.parametrize("status", ["missing", "pending"])
def test_only_exact_effective_deferral_for_the_achieved_key_can_provide_a_completion(status):
    supplied = context((field(), status, None))
    assert evaluate_eligibility(comparison(), supplied, deferrals={"math": allowed()}).status == "conditional"
    for evidence in (None, {}, {"math": unresolved()}, {"physics": allowed()}):
        result = evaluate_eligibility(comparison(), supplied, deferrals=evidence)
        assert result.status == "unknown" and not result.obligations


@pytest.mark.parametrize("status", ["not_applicable", "conflicted"])
def test_other_unknown_causes_are_not_missing_scores_even_if_the_item_has_a_deferral(status):
    result = evaluate_eligibility(comparison(), context((field(), status, None)), deferrals={"math": allowed()})
    assert result.status == "unknown" and not result.obligations


@pytest.mark.parametrize("expression", [
    {"op": "gte", "field": field(), "value": {"kind": "text", "value": "100"}},
    comparison(key="ielts_overall", value="6", unit="points", scale="9"),
    comparison(unit="band"),
    {"op": "all", "children": [comparison(), comparison(scale="1000")]},
    {"op": "all", "children": [{"op": "exists", "field": field()}, comparison(unit="band")]},
    {"op": "in", "field": field(), "values": [decimal("100"), decimal("100", scale="1000")]},
])
def test_missing_trace_does_not_authorize_wrong_types_units_or_inconsistent_scales(expression):
    result = evaluate_eligibility(expression, context((field(), "missing", None),
        (field("ielts_overall"), "missing", None)), deferrals={"math": allowed(), "ielts_overall": allowed()})
    assert result.status == "unknown" and not result.obligations


@pytest.mark.parametrize("known_value", [decimal("99"), decimal("100", unit="band"), decimal("100", scale="1000")])
def test_provided_failed_or_incompatible_grades_are_never_replaced_with_hypothetical_ones(known_value):
    supplied = context((field(), "known", known_value))
    result = evaluate_eligibility(comparison(), supplied, deferrals={"math": allowed()})
    assert result.status == ("ineligible" if known_value["unit"] == "points" and known_value["scale"] == "150" else "unknown")
    assert not result.obligations


@pytest.mark.parametrize("provided", [False, True])
def test_predicted_reference_remains_unknown_even_if_a_prediction_or_achieved_policy_exists(provided):
    supplied = context((field(basis="predicted"), "known" if provided else "missing",
        decimal("120") if provided else None))
    result = evaluate_eligibility(comparison(basis="predicted"), supplied, deferrals={"math": allowed()})
    assert result.status == "unknown" and not result.obligations


def test_minimal_obligations_do_not_include_an_unused_any_branch_or_duplicate_conditions():
    expression = {"op": "any", "children": [
        {"op": "all", "children": [comparison(key="math"), comparison(key="physics")]},
        {"op": "all", "children": [comparison(key="math"), comparison(key="math")]}]}
    supplied = context((field(), "missing", None), (field("physics"), "missing", None))
    result = evaluate_eligibility(expression, supplied, deferrals={"math": allowed(), "physics": allowed()})
    assert result.status == "conditional"
    assert [(item.assessment_key, item.basis) for item in result.obligations] == [("math", "achieved")]


def test_selected_true_alternative_carries_no_future_score_or_policy_obligation():
    for children in permutations([atom("T"), atom("F"), atom("D"), atom("U")]):
        result = evaluate_eligibility({"op": "any", "children": list(children)},
            context((field(), "missing", None)), deferrals={"math": allowed()})
        assert result.status == "eligible" and not result.obligations


def test_finite_numeric_membership_and_its_complement_use_the_same_shared_grade():
    member = {"op": "in", "field": field(), "values": [decimal("100"), decimal("120")]}
    feasible = {"op": "all", "children": [member, comparison("gte", "110")]}
    impossible = {"op": "all", "children": [member, {"op": "not", "child": member}]}
    supplied = context((field(), "pending", None))
    assert evaluate_eligibility(feasible, supplied, deferrals={"math": allowed()}).status == "conditional"
    assert evaluate_eligibility(impossible, supplied, deferrals={"math": allowed()}).status == "unknown"


def test_date_reference_missing_does_not_gain_a_score_deferral():
    window = {"op": "valid_at", "start": "2026-10-01T00:00:00Z", "end": "2026-11-01T00:00:00Z"}
    expression = {"op": "all", "children": [comparison(), window]}
    result = evaluate_eligibility(expression, context((field(), "missing", None)), deferrals={"math": allowed()})
    assert result.status == "unknown" and not result.obligations
    supplied = context((field(), "missing", None), assessment_at={"kind": "instant",
        "value": datetime(2026, 10, 3, tzinfo=timezone.utc), "precision": "second"})
    assert evaluate_eligibility(expression, supplied, deferrals={"math": allowed()}).status == "conditional"


def test_search_budget_is_finite_and_cannot_return_partial_unverified_obligations():
    keys = ("gaokao_total", "chinese", "math", "gaokao_english", "physics", "chemistry",
        "biology", "politics", "history", "geography", "ielts_overall", "ielts_listening",
        "ielts_reading", "ielts_writing", "ielts_speaking")
    expression = {"op": "all", "children": [comparison(value="6" if key.startswith("ielts_") else "100",
        key=key, unit="band" if key.startswith("ielts_") else "points",
        scale="9" if key.startswith("ielts_") else "750" if key == "gaokao_total" else "150") for key in keys]}
    supplied = context(*[(field(key), "missing", None) for key in keys])
    result = evaluate_eligibility(expression, supplied, deferrals={key: allowed() for key in keys})
    assert result.status == "unknown" and not result.obligations
    assert "BUDGET" in result.reason


def test_invalid_unused_branch_is_rejected_before_eligible_short_circuit():
    expression = {"op": "any", "children": [atom("T"),
        {"op": "python", "field": {"name": "owner_user_id"}, "value": "DEMO_SENSITIVE_SENTINEL"}]}
    with pytest.raises(RuleInputError) as caught:
        evaluate_eligibility(expression, context())
    assert caught.value.status_code == 422
    assert "DEMO_SENSITIVE_SENTINEL" not in str(caught.value) + repr(caught.value)
