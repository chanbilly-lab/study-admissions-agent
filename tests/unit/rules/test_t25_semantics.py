"""Independent T25 truth tables and typed boundary examples; no DB or providers."""

from itertools import permutations, product
import socket

import pytest

from app.rules.expression import EvaluationContext
from app.rules.evaluator import context_from_profile, evaluate_expression


@pytest.fixture(autouse=True)
def offline_no_socket(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("The T25 semantic examples must not use external or loopback networking")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def field(name="entry_year", **extra):
    return {"name": name, **extra}


def value(kind, data, **extra):
    return {"kind": kind, "value": data, **extra}


def context(*entries, assessment_date=None, assessment_at=None):
    return EvaluationContext.model_validate({"fields": [
        {"field": reference, "datum": {"status": status, "value": supplied}}
        for reference, status, supplied in entries],
        "assessment_date": assessment_date, "assessment_at": assessment_at})


def known(reference, supplied):
    return context((reference, "known", supplied))


def atom(truth):
    if truth == "unknown":
        return {"op": "eq", "field": field("course_system"), "value": value("text", "gaokao")}
    return {"op": "eq", "field": field(), "value": value("integer", 2027 if truth == "true" else 2028)}


def year_context():
    return known(field(), value("integer", 2027))


def result(expr, supplied):
    return evaluate_expression(expr, supplied)


ALL_TABLE = {
    ("true", "true"): "true", ("true", "false"): "false", ("true", "unknown"): "unknown",
    ("false", "true"): "false", ("false", "false"): "false", ("false", "unknown"): "false",
    ("unknown", "true"): "unknown", ("unknown", "false"): "false", ("unknown", "unknown"): "unknown",
}
ANY_TABLE = {
    ("true", "true"): "true", ("true", "false"): "true", ("true", "unknown"): "true",
    ("false", "true"): "true", ("false", "false"): "false", ("false", "unknown"): "unknown",
    ("unknown", "true"): "true", ("unknown", "false"): "unknown", ("unknown", "unknown"): "unknown",
}


@pytest.mark.parametrize("operator,table", [("all", ALL_TABLE), ("any", ANY_TABLE)])
@pytest.mark.parametrize("left,right", list(product(("true", "false", "unknown"), repeat=2)))
def test_complete_three_value_tables_and_all_branch_trace(operator, table, left, right):
    evaluated = result({"op": operator, "children": [atom(left), atom(right)]}, year_context())
    assert evaluated.truth == table[left, right]
    assert len(evaluated.trace) == 3
    assert evaluated.trace[0].children == (1, 2)
    assert [node.outcome for node in evaluated.trace[1:]] == [left, right]


@pytest.mark.parametrize("initial,expected", [("true", "false"), ("false", "true"), ("unknown", "unknown")])
def test_not_does_not_coerce_unknown(initial, expected):
    evaluated = result({"op": "not", "child": atom(initial)}, year_context())
    assert evaluated.truth == expected
    assert [node.outcome for node in evaluated.trace] == [expected, initial]


@pytest.mark.parametrize("operator,expected", [("all", "false"), ("any", "true")])
def test_permutations_and_nested_branches_are_not_atom_failure_counts(operator, expected):
    for ordered in permutations(("true", "false", "unknown")):
        nested = {"op": operator, "children": [atom(ordered[0]),
            {"op": operator, "children": [atom(ordered[1]), atom(ordered[2])]}]}
        evaluated = result(nested, year_context())
        assert evaluated.truth == expected
        assert len(evaluated.trace) == 5
    selected_alternative = {"op": "all", "children": [
        {"op": "any", "children": [atom("false"), atom("true"), atom("unknown")]}, atom("true")]}
    assert result(selected_alternative, year_context()).truth == "true"


@pytest.mark.parametrize("status", ["missing", "pending", "not_applicable", "conflicted"])
@pytest.mark.parametrize("operator", ["exists", "eq"])
def test_missing_states_and_negation_remain_unknown(status, operator):
    reference = field("assessment", key="math", basis="achieved")
    expr = {"op": operator, "field": reference}
    if operator == "eq":
        expr["value"] = value("decimal", "0", unit="points", scale="150")
    supplied = context((reference, status, None))
    assert result(expr, supplied).truth == "unknown"
    assert result({"op": "not", "child": expr}, supplied).truth == "unknown"


@pytest.mark.parametrize("supplied", [value("integer", 0), value("text", "false"), value("string_set", [])])
def test_known_values_are_not_tested_by_python_truthiness(supplied):
    reference = field("subjects") if supplied["kind"] == "string_set" else field("study_level") if supplied["kind"] == "text" else field()
    assert result({"op": "exists", "field": reference}, known(reference, supplied)).truth == "true"


@pytest.mark.parametrize("basis", ["achieved", "predicted"])
def test_explicit_prediction_never_substitutes_for_achieved(basis):
    achieved = field("assessment", key="ielts_overall", basis="achieved")
    predicted = field("assessment", key="ielts_overall", basis="predicted")
    supplied = context((achieved, "missing", None),
        (predicted, "known", value("decimal", "9", unit="band", scale="9")))
    for operator in ("exists", "gte"):
        expr = {"op": operator, "field": achieved if basis == "achieved" else predicted}
        if operator == "gte":
            expr["value"] = value("decimal", "6.5", unit="band", scale="9")
        evaluated = result(expr, supplied)
        assert evaluated.truth == "unknown"
        if basis == "predicted":
            assert "PREDICTED_NOT_ACHIEVED" in {node.reason for node in evaluated.trace}


@pytest.mark.parametrize("operator,left,right,expected", [
    ("eq", "600", "600.000000", "true"),
    ("gte", "600.000001", "600.000002", "false"),
    ("lte", "600.000001", "600.000002", "true"),
    ("gte", "0", "0", "true"), ("lte", "0", "0", "true"),
    ("eq", "9" * 63 + "8", "9" * 64, "false"),
    ("gte", "9" * 63 + "8", "9" * 64, "false"),
    ("lte", "9" * 63 + "8", "9" * 64, "true"),
])
def test_decimal_comparison_retains_sixty_four_digit_precision(operator, left, right, expected):
    reference = field("assessment", key="gaokao_total", basis="achieved")
    scale = "9" * 64
    supplied = known(reference, value("decimal", left, unit="points", scale=scale))
    expr = {"op": operator, "field": reference, "value": value("decimal", right, unit="points", scale=scale)}
    assert result(expr, supplied).truth == expected


@pytest.mark.parametrize("literal", [
    value("decimal", "80", unit="percent", scale="100"),
    value("decimal", "0.8", unit="fraction", scale="1"),
    value("decimal", "6", unit="band", scale="9"),
    value("decimal", "600", unit="points", scale="700"),
    value("integer", 600), value("text", "600"),
])
@pytest.mark.parametrize("operator", ["eq", "gte", "lte"])
def test_legal_type_unit_or_scale_mismatch_is_unknown_not_false(operator, literal):
    reference = field("assessment", key="gaokao_total", basis="achieved")
    expr = {"op": operator, "field": reference, "value": literal}
    supplied = known(reference, value("decimal", "600", unit="points", scale="750"))
    assert result(expr, supplied).truth == "unknown"
    assert result({"op": "not", "child": expr}, supplied).truth == "unknown"


def test_numeric_scale_tail_zero_equivalence_is_exact_without_conversion():
    reference = field("assessment", key="gaokao_total", basis="achieved")
    supplied = known(reference, value("decimal", "600.0", unit="points", scale="750.000"))
    assert result({"op": "eq", "field": reference,
        "value": value("decimal", "600", unit="points", scale="750")}, supplied).truth == "true"


@pytest.mark.parametrize("reference,bad_value", [
    (field(), value("text", "2027")),
    (field("course_system"), value("integer", 2027)),
    (field("subjects"), value("text", "physics")),
    (field("assessment", key="math", basis="achieved"), value("decimal", "6", unit="band", scale="9")),
    (field("assessment", key="ielts_overall", basis="achieved"), value("decimal", "600", unit="points", scale="750")),
])
def test_matching_wrong_field_kind_or_grade_unit_cannot_conspire_to_pass(reference, bad_value):
    supplied = known(reference, bad_value)
    for expr in [{"op": "exists", "field": reference},
        {"op": "eq", "field": reference, "value": bad_value}]:
        assert result(expr, supplied).truth == "unknown"
        assert result({"op": "not", "child": expr}, supplied).truth == "unknown"


@pytest.mark.parametrize("members,expected", [(["chemistry"], "false"), (["math"], "true"),
    (["chemistry", "physics"], "true")])
def test_subject_membership_is_any_intersection_not_subset(members, expected):
    expr = {"op": "in", "field": field("subjects"), "values": [value("text", member) for member in members]}
    supplied = known(field("subjects"), value("string_set", ["math", "physics"]))
    assert result(expr, supplied).truth == expected
    assert result(expr, known(field("subjects"), value("string_set", []))).truth == "false"


def test_scalar_membership_is_exact_case_sensitive_text():
    expr = {"op": "in", "field": field("course_system"), "values": [value("text", "gaokao")]}
    assert result(expr, known(field("course_system"), value("text", "gaokao"))).truth == "true"
    assert result(expr, known(field("course_system"), value("text", "Gaokao"))).truth == "false"


def test_membership_match_cannot_hide_a_later_unit_or_scale_mismatch():
    reference = field("assessment", key="gaokao_total", basis="achieved")
    supplied = known(reference, value("decimal", "600", unit="points", scale="750"))
    for incompatible in [value("decimal", "80", unit="percent", scale="100"),
        value("decimal", "600", unit="points", scale="700")]:
        matching = value("decimal", "600", unit="points", scale="750")
        for values in ([matching, incompatible], [incompatible, matching]):
            assert result({"op": "in", "field": reference, "values": values}, supplied).truth == "unknown"


@pytest.mark.parametrize("left,right,expected", [("2027-01-01", "2027-01-02", "true"),
    ("2027-01-02", "2027-01-02", "false"), ("2027-01-03", "2027-01-02", "false")])
def test_date_before_uses_strict_order_on_one_explicit_calendar(left, right, expected):
    supplied = context(assessment_date=value("date", left, calendar="Europe/London"))
    expr = {"op": "date_before", "field": field("assessment_date"),
        "value": value("date", right, calendar="Europe/London")}
    assert result(expr, supplied).truth == expected
    expr["value"]["calendar"] = "Asia/Shanghai"
    assert result(expr, supplied).truth == "unknown"


def test_date_and_instant_precision_do_not_mix_or_gain_a_guessed_midnight():
    supplied = context(assessment_date=value("date", "2027-01-01", calendar="Europe/London"),
        assessment_at=value("instant", "2027-01-01T00:00:00Z", precision="second"))
    for reference, literal in [
        (field("assessment_date"), value("instant", "2027-01-02T00:00:00Z", precision="second")),
        (field("assessment_at"), value("date", "2027-01-02", calendar="Europe/London")),
        (field("assessment_at"), value("instant", "2027-01-02T00:00:00Z", precision="minute")),
    ]:
        assert result({"op": "date_before", "field": reference, "value": literal}, supplied).truth == "unknown"


@pytest.mark.parametrize("instant,expected", [("2026-12-31T23:59:59Z", "false"),
    ("2027-01-01T00:00:00Z", "true"), ("2027-01-01T23:59:59Z", "true"),
    ("2027-01-02T00:00:00Z", "false")])
def test_valid_at_is_explicit_utc_half_open_interval(instant, expected):
    expr = {"op": "valid_at", "start": "2027-01-01T00:00:00Z", "end": "2027-01-02T00:00:00Z"}
    supplied = context(assessment_at=value("instant", instant, precision="second"))
    assert result(expr, supplied).truth == expected
    assert result(expr, context()).truth == "unknown"
    assert result(expr, context(assessment_date=value("date", "2027-01-01", calendar="UTC"))).truth == "unknown"


def profile_snapshot():
    known_scope = lambda supplied: {"status": "known", "value": supplied}
    return {"study_level": "bachelor", "entry_year": 2027,
        "residence_region": known_scope("hk"), "course_system": known_scope("gaokao"),
        "applicant_category": known_scope("cn_mainland"), "exam_province": known_scope("zhejiang"),
        "pathway": known_scope("uk_undergraduate"), "subjects": [], "assessments": {"math": {
            "achieved": {"status": "provided", "value": "0", "scale": "150", "unit": "points"},
            "predicted": {"status": "provided", "value": "130", "scale": "150", "unit": "points"}}},
        "weekly_hours": "2", "preferences": None}


def test_actual_profile_projection_does_not_infer_identity_or_confirm_empty_subjects():
    supplied = context_from_profile(profile_snapshot())
    for name, expected in [("residence_region", "hk"), ("applicant_category", "cn_mainland"),
        ("exam_province", "zhejiang"), ("course_system", "gaokao"), ("pathway", "uk_undergraduate")]:
        assert result({"op": "eq", "field": field(name), "value": value("text", expected)}, supplied).truth == "true"
    for expr in [{"op": "exists", "field": field("subjects")},
        {"op": "in", "field": field("subjects"), "values": [value("text", "math")]},
        {"op": "gte", "field": field("assessment", key="chinese", basis="achieved"),
         "value": value("decimal", "0", unit="points", scale="150")},
    ]:
        assert result({"op": "not", "child": expr}, supplied).truth == "unknown"
    zero = {"op": "gte", "field": field("assessment", key="math", basis="achieved"),
        "value": value("decimal", "0", unit="points", scale="150")}
    assert result(zero, supplied).truth == "true"
    # Context dates are explicit inputs. The current day and enrollment year supply neither.
    assert supplied.assessment_date is None and supplied.assessment_at is None


def test_trace_contains_only_closed_reasons_references_and_tree_structure():
    sentinel = "DEMO_PRIVATE_LITERAL_SENTINEL"
    expr = {"op": "any", "children": [{"op": "eq", "field": field("course_system"),
        "value": value("text", sentinel)}, atom("true")]}
    supplied = context((field("course_system"), "known", value("text", sentinel)),
        (field(), "known", value("integer", 2027)))
    evaluated = result(expr, supplied)
    assert evaluated.truth == "true"
    wire = evaluated.model_dump(mode="json")
    assert set(wire) == {"truth", "reason", "trace"}
    assert sentinel not in str(wire)
    assert all(set(node) == {"op", "field", "outcome", "reason", "children"} for node in wire["trace"])
    assert evaluated.truth in {"true", "false", "unknown"}
