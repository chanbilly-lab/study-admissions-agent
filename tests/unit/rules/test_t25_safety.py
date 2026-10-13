"""Untrusted AST/context attacks against the T25 public pure-function boundary."""

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from pydantic import ValidationError
import pytest

from app.rules.expression import EvaluationContext, RuleInputError, parse_expression
from app.rules.evaluator import context_from_profile, evaluate_expression


SENTINEL = "DEMO_SECRET_RULE_ATTACK_SENTINEL"
ROOT = Path(__file__).resolve().parents[3]


def leaf():
    return {"op": "eq", "field": {"name": "entry_year"}, "value": {"kind": "integer", "value": 2027}}


def year_context():
    return EvaluationContext.model_validate({"fields": [{"field": {"name": "entry_year"},
        "datum": {"status": "known", "value": {"kind": "integer", "value": 2027}}}],
        "assessment_date": None, "assessment_at": None})


def rejected(expression, supplied=None):
    with pytest.raises(RuleInputError) as caught:
        evaluate_expression(expression, year_context() if supplied is None else supplied)
    error = caught.value
    assert error.status_code == 422 and error.code == "INVALID_RULE_INPUT"
    assert SENTINEL not in str(error) and SENTINEL not in repr(error)
    return error


@pytest.fixture(autouse=True)
def offline_no_socket(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("The T25 unit tests must not open any socket or resolve a host")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


@pytest.mark.parametrize("bad", [
    {"op": "eval", "code": SENTINEL},
    {"op": "exec", "code": SENTINEL},
    {"op": "gte", "field": {"name": "__class__"}, "value": {"kind": "integer", "value": 2027}},
    {"op": "eq", "field": {"name": "owner_user_id"}, "value": {"kind": "text", "value": SENTINEL}},
    {"op": "exists", "field": {"name": "profile.assessments.math.value"}},
    {"op": "exists", "field": {"name": "preferences"}},
    {"op": "exists", "field": {"name": "weekly_hours"}},
    {"op": "eq", "field": {"name": "entry_year"}, "value": {"kind": "integer", "value": 2027}, "template": SENTINEL},
    {"op": "not", "child": leaf(), "children": [leaf()]},
    {"op": "all", "children": []}, {"op": "any", "children": []},
    {"op": "not", "child": None},
    {"op": "eq", "field": {"name": ["entry_year"]}, "value": {"kind": "integer", "value": 2027}},
    {"op": "exists", "field": {"name": "entry_year", "basis": "achieved"}},
    {"op": "exists", "field": {"name": "assessment", "key": "language_exam_expiry", "basis": "achieved"}},
])
def test_invalid_subtree_cannot_hide_behind_a_true_alternative(bad):
    rejected({"op": "any", "children": [leaf(), bad]})
    rejected({"op": "any", "children": [bad, leaf()]})


@pytest.mark.parametrize("bad", [True, 1.0, "2027", None, 9007199254740992, -9007199254740992])
def test_integer_literals_are_exact_and_bounded(bad):
    invalid = leaf()
    invalid["value"]["value"] = bad
    rejected(invalid)


@pytest.mark.parametrize("bad", [True, 0, 0.0, -1, "-1", "01", "+1", "1e2", "1.", ".5", "NaN", "Infinity",
    "1\n", "1 " , "9" * 65, "１", "١", SENTINEL])
def test_decimal_literals_never_gain_float_or_non_decimal_coercion(bad):
    rejected({"op": "gte", "field": {"name": "assessment", "key": "math", "basis": "achieved"},
        "value": {"kind": "decimal", "value": bad, "unit": "points", "scale": "150"}})


@pytest.mark.parametrize("changes", [{"scale": "0"}, {"scale": None}, {"scale": 150},
    {"unit": "GPA"}, {"unit": None}, {"value": "151"}, {"scale": "01"}])
def test_decimal_unit_and_scale_shape_is_validated_even_without_a_grade(changes):
    literal = {"kind": "decimal", "value": "0", "unit": "points", "scale": "150", **changes}
    rejected({"op": "gte", "field": {"name": "assessment", "key": "math", "basis": "achieved"}, "value": literal})


@pytest.mark.parametrize("encoded", [
    '{"op":"eq","op":"exists","field":{"name":"entry_year"},"value":{"kind":"integer","value":2027}}',
    '{"op":"eq","field":{"name":"entry_year","name":"owner_user_id"},"value":{"kind":"text","value":"' + SENTINEL + '"}}',
    '{"op":"eq","field":{"name":"entry_year"},"value":{"kind":"integer","value":NaN}}',
    '{"op":"eq","field":{"name":"entry_year"},"value":{"kind":"integer","value":Infinity}}',
    '{"op":"eq","field":{"name":"entry_year"},"value":{"kind":"integer","value":2027,"value":2028}}',
])
def test_json_duplicate_keys_or_nonfinite_numbers_are_not_last_value_wins(encoded):
    rejected(encoded)
    rejected(encoded.encode("utf-8"))


def test_json_entrypoint_preserves_valid_utf8_and_rejects_malformed_encoding():
    encoded = json.dumps(leaf(), separators=(",", ":")).encode("utf-8")
    assert evaluate_expression(encoded, year_context()).truth == "true"
    rejected(b'{"op":"exists","field":{"name":"\xff"}}')
    rejected('{"op":"exists",')


def test_depth_limit_is_checked_before_recursion_or_short_circuit():
    expr = leaf()
    for _ in range(15):
        expr = {"op": "not", "child": expr}
    assert len(evaluate_expression(expr, year_context()).trace) == 16
    rejected({"op": "not", "child": expr})
    rejected({"op": "any", "children": [leaf(), expr]})


def test_node_budget_and_per_group_children_have_exact_closed_boundaries():
    bounded = {"op": "all", "children": [
        {"op": "any", "children": [leaf() for _ in range(31 if i < 7 else 30)]}
        for i in range(8)]}
    evaluated = evaluate_expression(bounded, year_context())
    assert evaluated.truth == "true" and len(evaluated.trace) == 256
    too_many = deepcopy(bounded)
    too_many["children"][-1]["children"].append(leaf())
    rejected(too_many)
    assert len(evaluate_expression({"op": "all", "children": [leaf() for _ in range(32)]}, year_context()).trace) == 33
    rejected({"op": "all", "children": [leaf() for _ in range(33)]})


def test_dsl_bytes_are_measured_at_the_actual_json_entrypoint():
    small = json.dumps(leaf(), separators=(",", ":")).encode("utf-8")
    exact = small + b" " * (65536 - len(small))
    assert evaluate_expression(exact, year_context()).truth == "true"
    rejected(exact + b" ")


def test_oversized_native_input_is_rejected_before_json_serialization(monkeypatch):
    import app.rules.expression as syntax
    oversized = leaf()
    oversized["unexpected"] = SENTINEL * 4000
    def no_large_copy(*args, **kwargs):
        pytest.fail("Oversized untrusted native input reached JSON serialization")
    with monkeypatch.context() as patch:
        patch.setattr(syntax.json, "dumps", no_large_copy)
        rejected(oversized)


def test_member_count_and_text_unicode_limits_do_not_truncate():
    expr = {"op": "in", "field": {"name": "entry_year"},
        "values": [{"kind": "integer", "value": 2027 + i} for i in range(32)]}
    assert evaluate_expression(expr, year_context()).truth == "true"
    rejected({**expr, "values": []})
    rejected({**expr, "values": expr["values"] + [{"kind": "integer", "value": 2059}]})
    text_expr = {"op": "eq", "field": {"name": "course_system"}, "value": {"kind": "text", "value": "😀" * 256}}
    parsed = parse_expression(text_expr)
    assert parsed.value.value == "😀" * 256
    rejected({**text_expr, "value": {"kind": "text", "value": "😀" * 257}})
    rejected({**text_expr, "value": {"kind": "text", "value": SENTINEL + "\ud800"}})


@pytest.mark.parametrize("bad", [
    {"status": "pending", "value": {"kind": "integer", "value": 2027}},
    {"status": "known", "value": None},
    {"status": "verified", "value": {"kind": "integer", "value": 2027}},
    {"status": "known", "value": {"kind": "integer", "value": True}},
    {"status": "known", "value": {"kind": "integer", "value": 2027}, "owner": SENTINEL},
])
def test_illegal_context_coupling_is_rejected_instead_of_becoming_truth(bad):
    supplied = {"fields": [{"field": {"name": "entry_year"}, "datum": bad}],
        "assessment_date": None, "assessment_at": None}
    rejected(leaf(), supplied)


def test_context_duplicate_reference_is_not_a_last_value_wins_override():
    supplied = year_context().model_dump(mode="json")
    supplied["fields"].append(deepcopy(supplied["fields"][0]))
    supplied["fields"][-1]["datum"]["value"]["value"] = 2028
    rejected(leaf(), supplied)


def test_frozen_ast_and_context_are_revalidated_after_copy_or_construct():
    expr = parse_expression(leaf())
    with pytest.raises(ValidationError):
        expr.op = "exec"
    rejected(expr.model_copy(update={"op": "exec"}))
    rejected(type(expr).model_construct(**{**expr.model_dump(), "value": {"kind": "integer", "value": True}}))
    supplied = year_context()
    bad_item = supplied.fields[0].model_copy(update={"datum": {"status": "known", "value": None}})
    rejected(expr, supplied.model_copy(update={"fields": (bad_item,)}))
    rejected(expr, EvaluationContext.model_construct(**{**supplied.model_dump(), "assessment_at": SENTINEL}))


def test_cyclic_or_custom_objects_never_execute_their_python_hooks():
    cyclic = {"op": "not"}
    cyclic["child"] = cyclic
    rejected(cyclic)

    class Trap:
        def __str__(self):
            pytest.fail("Untrusted object string conversion was executed")
        def __eq__(self, other):
            pytest.fail("Untrusted object equality was executed")

    invalid = leaf()
    invalid["value"]["value"] = Trap()
    rejected(invalid)
    class ForeignMapping(dict):
        def items(self):
            pytest.fail("Custom mapping code was executed")
    rejected(ForeignMapping(leaf()))


@pytest.mark.parametrize("start,end", [
    ("2027-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
    ("2027-01-02T00:00:00Z", "2027-01-01T00:00:00Z"),
    ("2027-01-01", "2027-01-02"),
    ("2027-01-01T00:00:00", "2027-01-02T00:00:00Z"),
    (1735689600, "2027-01-02T00:00:00Z"),
])
def test_validity_window_cannot_invent_zone_or_accept_an_empty_interval(start, end):
    rejected({"op": "valid_at", "start": start, "end": end})


def test_explicit_time_model_cannot_hide_naive_or_forged_precision():
    for supplied in [
        {"kind": "instant", "value": datetime(2027, 1, 1), "precision": "second"},
        {"kind": "instant", "value": "2027-01-01T00:00:01Z", "precision": "minute"},
        {"kind": "instant", "value": "2027-01-01T00:00:00Z", "precision": "date"},
    ]:
        rejected({"op": "date_before", "field": {"name": "assessment_at"}, "value": supplied})
    rejected({"op": "date_before", "field": {"name": "assessment_date"},
        "value": {"kind": "date", "value": "2027-01-01", "calendar": "Europe/London " + SENTINEL}})


def test_pure_evaluation_does_not_read_environment_clock_files_or_network(monkeypatch):
    expr, supplied = parse_expression(leaf()), year_context()
    import builtins

    def deny(*args, **kwargs):
        raise AssertionError("Pure T25 evaluation attempted an external effect")
    with monkeypatch.context() as patch:
        patch.setattr(os, "getenv", deny)
        patch.setattr(builtins, "open", deny)
        patch.setattr(os, "open", deny)
        patch.setattr(builtins, "eval", deny)
        patch.setattr(builtins, "exec", deny)
        assert evaluate_expression(expr, supplied).truth == "true"


def test_fresh_process_import_and_evaluation_have_no_model_m0_or_database_dependency():
    code = r'''
import importlib.abc, json, socket, sys
class ForbiddenImport(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('sqlalchemy', 'psycopg', 'httpx', 'requests', 'openai',
            'app.providers', 'app.main', 'app.models', 'app.database', 'app.seed', 'app.settings',
            'services.api.app.providers', 'services.api.app.main', 'services.api.app.models',
            'services.api.app.database', 'services.api.app.seed', 'services.api.app.settings')
        if any(fullname == x or fullname.startswith(x + '.') for x in forbidden):
            raise AssertionError('Forbidden dependency reached')
sys.meta_path.insert(0, ForbiddenImport())
def deny(*args, **kwargs):
    raise AssertionError('Network use is forbidden')
socket.socket.connect = socket.socket.connect_ex = deny
socket.create_connection = socket.getaddrinfo = deny
sys.path.insert(0, 'services/api')
from app.rules.expression import EvaluationContext
from app.rules.evaluator import evaluate_expression
context = EvaluationContext(fields=[], assessment_date=None, assessment_at=None)
expression = {'op':'not','child':{'op':'exists','field':{'name':'entry_year'}}}
result = evaluate_expression(expression, context)
assert result.truth == 'unknown'
assert not any(name.startswith(('sqlalchemy', 'psycopg', 'app.providers', 'app.database', 'app.main')) for name in sys.modules)
print('T25 fresh-process pure boundary passed')
'''
    completed = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
        text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "T25 fresh-process pure boundary passed"
