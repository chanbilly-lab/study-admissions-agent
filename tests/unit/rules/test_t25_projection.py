"""Project actual T23 declarations without synthesizing scores or scope."""

from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from services.api.app.profiles.schemas import ASSESSMENT_KEYS, ProfileSnapshot
from services.api.app.rules.evaluator import context_from_profile, evaluate_expression
from services.api.app.rules.expression import DateValue, InstantValue, RuleInputError


def profile():
    known = lambda value: {"status": "known", "value": value}
    return {"study_level": "bachelor", "entry_year": 2027,
        "residence_region": known("hk"), "course_system": known("gaokao"),
        "applicant_category": known("cn_mainland"), "exam_province": known("zhejiang"),
        "pathway": known("uk_undergraduate"), "subjects": ["physics", "chemistry"],
        "assessments": {"math": {
            "achieved": {"status": "provided", "value": "0", "scale": "150", "unit": "points"},
            "predicted": {"status": "provided", "value": "130.125", "scale": "150", "unit": "points"}},
            "ielts_overall": {
            "achieved": {"status": "pending", "value": None, "scale": None, "unit": None},
            "predicted": {"status": "provided", "value": "7.5", "scale": "9", "unit": "band"}}},
        "weekly_hours": "12", "preferences": {"preferred_fields": ["medicine"],
            "preferred_countries": ["GB"], "budget": {"amount": "100000", "currency": "CNY"}}}


def ref(name, **selectors):
    return {"name": name, **selectors}


def exists(field, context):
    return evaluate_expression({"op": "exists", "field": field}, context)


def test_projection_contains_only_the_closed_fields_and_all_fifteen_pairs():
    context = context_from_profile(ProfileSnapshot.model_validate(profile()))
    assert len(context.fields) == 38
    assert {item.field.key for item in context.fields if item.field.name == "assessment"} == set(ASSESSMENT_KEYS)
    assert not {"weekly_hours", "preferences", "budget"}.intersection(item.field.name for item in context.fields)
    assert "medicine" not in context.model_dump_json()
    scopes = {item.field.name: item.datum.value.value for item in context.fields
              if item.field.name in {"residence_region", "applicant_category", "exam_province", "pathway"}}
    assert scopes == {"residence_region": "hk", "applicant_category": "cn_mainland",
                      "exam_province": "zhejiang", "pathway": "uk_undergraduate"}


def test_zero_achieved_remains_known_and_prediction_cannot_replace_it():
    context = context_from_profile(profile())
    achieved = ref("assessment", key="math", basis="achieved")
    predicted = ref("assessment", key="math", basis="predicted")
    assert exists(achieved, context).truth == "true"
    assert evaluate_expression({"op": "eq", "field": achieved,
        "value": {"kind": "decimal", "value": "0", "scale": "150", "unit": "points"}}, context).truth == "true"
    assert exists(predicted, context).reason == "PREDICTED_NOT_ACHIEVED"


@pytest.mark.parametrize("status", ["missing", "pending", "not_applicable"])
def test_unusable_achieved_grade_is_unknown_even_with_a_prediction(status):
    raw = profile()
    raw["assessments"]["math"]["achieved"] = {"status": status, "value": None, "scale": None, "unit": None}
    context = context_from_profile(raw)
    field = ref("assessment", key="math", basis="achieved")
    assert exists(field, context).truth == "unknown"
    assert evaluate_expression({"op": "not", "child": {"op": "exists", "field": field}}, context).truth == "unknown"


def test_absent_grade_and_empty_profile_subjects_are_missing_not_false():
    raw = profile()
    raw["subjects"] = []
    context = context_from_profile(raw)
    assert exists(ref("subjects"), context).reason == "MISSING"
    assert exists(ref("assessment", key="chinese", basis="achieved"), context).reason == "MISSING"


def test_unknown_province_does_not_use_residence_and_subjects_match_any_intersection():
    raw = profile()
    raw["exam_province"] = {"status": "unknown", "value": None}
    context = context_from_profile(raw)
    assert exists(ref("exam_province"), context).truth == "unknown"
    assert exists(ref("residence_region"), context).truth == "true"
    assert evaluate_expression({"op": "in", "field": ref("subjects"), "values": [
        {"kind": "text", "value": "history"}, {"kind": "text", "value": "physics"}]}, context).truth == "true"


def test_projection_revalidates_an_entire_forged_profile_not_only_rule_fields():
    valid = ProfileSnapshot.model_validate(profile())
    bad = valid.model_copy(update={"weekly_hours": "999"})
    with pytest.raises(RuleInputError):
        context_from_profile(bad)
    raw = deepcopy(profile())
    raw["assessments"]["math"]["achieved"]["unit"] = "band"
    with pytest.raises(RuleInputError):
        context_from_profile(ProfileSnapshot.model_construct(**raw))


def test_projection_never_fabricates_assessment_dates_or_instants():
    raw = profile()
    context = context_from_profile(raw)
    assert context.assessment_date is None and context.assessment_at is None
    assert exists(ref("assessment_at"), context).truth == "unknown"
    explicit = context_from_profile(raw,
        assessment_date=DateValue(value=date(2027, 1, 1), calendar="admissions_calendar_v1"),
        assessment_at=InstantValue(value=datetime(2027, 1, 1, tzinfo=timezone.utc), precision="second"))
    assert exists(ref("assessment_date"), explicit).truth == "true"
    assert evaluate_expression({"op": "valid_at", "start": "2027-01-01T00:00:00Z",
        "end": "2027-01-02T00:00:00Z"}, explicit).truth == "true"
