"""Project only explicit applicant scope from the existing complete profile."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

import pytest

from services.api.app.profiles.schemas import ProfileSnapshot
from services.api.app.rules.adapters import AdapterInputError, scope_request_from_profile


EXTRA = ("intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")
NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)


def profile():
    known = lambda value: {"status": "known", "value": value}
    return {"study_level": "bachelor", "entry_year": 2027,
        "residence_region": known("HK"), "course_system": known("gaokao"),
        "applicant_category": known("cn_mainland"), "exam_province": known("zhejiang"),
        "pathway": known("uk_undergraduate"), "subjects": ["physics", "chemistry"],
        "assessments": {"math": {
            "achieved": {"status": "provided", "value": "0", "scale": "150", "unit": "points"},
            "predicted": {"status": "provided", "value": "130", "scale": "150", "unit": "points"}}},
        "weekly_hours": "10", "preferences": {"preferred_fields": ["medicine"],
            "preferred_countries": ["GB"], "budget": {"amount": "120000", "currency": "CNY"}}}


def project(current, **extras):
    target = {name: UUID(int=n) for n, name in enumerate(
        ("dataset_id", "institution_id", "program_id", "offering_id"), start=1)}
    target.update(offering_version=1, country="GB", scope_sha256="a" * 64)
    return scope_request_from_profile(current, target=target, stage="application", assessment_at=NOW,
        **{name: extras.get(name) for name in EXTRA})


def test_projection_preserves_raw_province_and_independent_applicant_scopes():
    raw = profile()
    before = deepcopy(raw)
    request = project(raw)
    assert request.exam_province.value == "zhejiang"
    assert request.residence_region.value == "HK" and request.applicant_category.value == "cn_mainland"
    assert request.pathway.value == "uk_undergraduate"
    assert raw == before
    assert request.assessment_at == NOW


def test_unavailable_dimensions_remain_explicit_null_without_subject_inference():
    request = project(profile())
    assert all(getattr(request, name) is None for name in EXTRA)
    assert not {"assessments", "subjects", "preferences", "budget", "weekly_hours"}.intersection(request.model_dump())
    encoded = request.model_dump_json()
    assert "medicine" not in encoded and "130" not in encoded and "120000" not in encoded


def test_explicit_extra_scopes_are_not_replaced_with_year_or_default_codes():
    request = project(profile(), intake={"status": "not_applicable", "value": None},
        channel={"status": "known", "value": "DEMO_confirmed_channel"})
    assert request.intake.status == "not_applicable"
    assert request.channel.value == "DEMO_confirmed_channel"
    assert request.application_cycle is None


@pytest.mark.parametrize("field,value", [("weekly_hours", "999"), ("entry_year", True),
    ("subjects", ["physics", "physics"]), ("owner_id", UUID(int=20))])
def test_full_profile_is_revalidated_even_for_fields_not_projected(field, value):
    valid = ProfileSnapshot.model_validate(profile())
    with pytest.raises(AdapterInputError):
        project(valid.model_copy(update={field: value}))


def test_achievement_and_prediction_remain_in_the_original_snapshot_only():
    valid = ProfileSnapshot.model_validate(profile())
    before = valid.model_dump()
    project(valid)
    assert valid.model_dump() == before
    assert valid.assessments["math"].achieved.value == "0"
    assert valid.assessments["math"].predicted.value == "130"
