"""T25 strict native input and pre-serialization resource boundaries."""

from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from services.api.app.rules import expression
from services.api.app.rules.expression import (
    DateValue, InstantValue, RuleInputError, StringSetValue, TextValue, parse_expression,
    validate_context,
)


def leaf():
    return {"op": "exists", "field": {"name": "entry_year"}}


@pytest.mark.parametrize("raw", [
    {"op": "eq", "field": {"name": "course_system"},
     "value": {"kind": "text", "value": "x" * 65537}},
    {"op": "eq", "field": {"name": "entry_year"},
     "value": {"kind": "integer", "value": 10**10000}},
    {"op": "all", "children": [
        {"op": "eq", "field": {"name": "course_system"},
         "value": {"kind": "text", "value": "x" * 40000}} for _ in range(2)]},
    {"op": "eq", "field": {"name": "course_system"},
     "value": {"kind": "text", "value": "\n" * 40000}},
])
def test_native_budget_rejects_before_json_allocation(monkeypatch, raw):
    def forbidden(*args, **kwargs):
        pytest.fail("Unbounded input reached JSON serialization")

    monkeypatch.setattr(expression.json, "dumps", forbidden)
    with pytest.raises(RuleInputError):
        parse_expression(raw)


def test_context_copy_uses_the_same_bounded_budget():
    raw = {"fields": [{"field": {"name": "subjects"}, "datum": {"status": "known",
        "value": {"kind": "string_set", "value": ["x" * 40000, "y" * 40000]}}}]}
    with pytest.raises(RuleInputError):
        validate_context(raw)


class ForeignString(str):
    pass


@pytest.mark.parametrize("item", [b"physics", ForeignString("physics"), 1, True])
def test_direct_string_set_rejects_items_before_pydantic_coercion(item):
    with pytest.raises(ValidationError):
        StringSetValue(value=[item])


def test_rule_model_errors_hide_input_and_validate_defaults():
    sentinel = "DEMO_SECRET_T25_SENTINEL"
    with pytest.raises(ValidationError) as caught:
        TextValue(value=sentinel + "\n")
    assert sentinel not in str(caught.value)
    assert expression.RuleModel.model_config["validate_default"] is True
    assert expression.RuleModel.model_config["allow_inf_nan"] is False


def test_calendar_domain_is_explicit_and_does_not_infer_a_timezone():
    calendar = DateValue(value=date(2027, 1, 1), calendar="admissions_calendar_v1")
    parsed = parse_expression({"op": "date_before", "field": {"name": "assessment_date"},
                               "value": calendar})
    assert parsed.value.calendar == "admissions_calendar_v1"
    assert parsed.value.value == date(2027, 1, 1)


def test_json_whitespace_budget_and_native_copy_do_not_change_the_rule():
    raw = '{"op":"exists","field":{"name":"entry_year"}}'
    parsed = parse_expression(raw + " " * (65536 - len(raw)))
    assert parse_expression(parsed) == parse_expression(leaf())
    with pytest.raises(RuleInputError):
        parse_expression(raw + " " * (65537 - len(raw)))


def test_native_datetime_rejects_custom_timezone_before_any_python_hook():
    calls = []

    class ForeignTimezone(tzinfo):
        def utcoffset(self, value):
            calls.append("offset")
            raise RuntimeError("DEMO_SECRET_TZ_HOOK")

    value = datetime(2027, 1, 1, tzinfo=ForeignTimezone())
    with pytest.raises(ValidationError):
        InstantValue(value=value, precision="second")
    with pytest.raises(RuleInputError):
        parse_expression({"op": "date_before", "field": {"name": "assessment_at"},
            "value": {"kind": "instant", "value": value, "precision": "second"}})
    with pytest.raises(RuleInputError):
        validate_context({"assessment_at": InstantValue.model_construct(
            kind="instant", value=value, precision="second")})
    assert calls == []
    for zone in (timezone(timedelta(hours=8)), ZoneInfo("UTC")):
        native = datetime(2027, 1, 1, tzinfo=zone)
        parsed = parse_expression({"op": "date_before", "field": {"name": "assessment_at"},
            "value": {"kind": "instant", "value": native, "precision": "second"}})
        assert parsed.value.value == native.astimezone(timezone.utc)
