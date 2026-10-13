"""Exact declarations and closed factory boundaries; no external dependencies."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from services.api.app.api.profiles import create_profiles_app, create_profiles_v2_app
from services.api.app.api.v2.idempotency_canonical import canonical_request_hash
from services.api.app.profiles.schemas import (ASSESSMENT_KEYS, AppendInput, CreateInput,
    GradeSlot, ProfileEnvelope, ProfileMeta, ProfilePolicy, ProfileSnapshot, ProfileVersionData, adaptation)
from services.api.app.settings import V2RuntimeSettings


def snapshot():
    known = lambda value: {"status": "known", "value": value}
    return {"study_level": "bachelor", "entry_year": 2027,
        "residence_region": known("hk"), "course_system": known("gaokao"),
        "applicant_category": known("cn_mainland"), "exam_province": known("zhejiang"),
        "pathway": known("gaokao"), "subjects": ["math"], "assessments": {"math": {
            "achieved": {"status": "provided", "value": "0", "scale": "150", "unit": "points"},
            "predicted": {"status": "provided", "value": "130.125", "scale": "150", "unit": "points"}}},
        "weekly_hours": None, "preferences": None}


def runtime():
    return V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)


@pytest.mark.parametrize("bad", [1, 1.0, "true", False, None])
def test_confirmation_requires_exact_boolean(bad):
    with pytest.raises(ValidationError):
        CreateInput(profile=snapshot(), confirmed=bad)


@pytest.mark.parametrize("bad", [0, -1, 1.0, True, "1", 2147483648])
def test_append_requires_integer_cas(bad):
    with pytest.raises(ValidationError):
        AppendInput(profile=snapshot(), confirmed=True, expected_current_version=bad)


@pytest.mark.parametrize("bad", [0, 0.0, "01", "1e2", "-1", "+1", "1.", ".5", "1.0000001", "10000000", "1\n", "NaN"])
def test_grade_decimal_wire_is_exact(bad):
    with pytest.raises(ValidationError):
        GradeSlot(status="provided", value=bad, scale="150", unit="points")


@pytest.mark.parametrize("status", ["missing", "pending", "not_applicable"])
def test_missing_grade_retains_null_instead_of_zero(status):
    value = GradeSlot(status=status, value=None, scale=None, unit=None)
    assert value.value is None
    with pytest.raises(ValidationError):
        GradeSlot(status=status, value="0", scale=None, unit=None)


def test_values_and_predictions_do_not_replace_each_other():
    data = ProfileSnapshot.model_validate(snapshot())
    assert data.assessments["math"].achieved.value == "0"
    assert data.assessments["math"].predicted.value == "130.125"
    assert data.weekly_hours is None
    zero = snapshot()
    zero["weekly_hours"] = "0"
    assert ProfileSnapshot.model_validate(zero).weekly_hours == "0"
    for scale, value in (("0", "0"), ("150", "151")):
        with pytest.raises(ValidationError):
            GradeSlot(status="provided", value=value, scale=scale, unit="points")


def test_closed_assessment_keys_match_schema_and_preserve_explicit_units():
    schema = ProfileSnapshot.model_json_schema()["$defs"]["GradeAssessments"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(ASSESSMENT_KEYS)
    bad = snapshot()
    bad["assessments"]["other"] = bad["assessments"]["math"]
    with pytest.raises(ValidationError):
        ProfileSnapshot.model_validate(bad)
    bad = snapshot()
    bad["assessments"]["math"]["achieved"]["unit"] = "band"
    with pytest.raises(ValidationError):
        ProfileSnapshot.model_validate(bad)


@pytest.mark.parametrize("extra", ["owner_user_id", "is_synthetic", "verified", "consent_id", "roles"])
def test_client_cannot_inject_server_authority(extra):
    with pytest.raises(ValidationError):
        CreateInput.model_validate({"profile": snapshot(), "confirmed": True, extra: "SENTINEL"})


def test_forged_models_are_revalidated_and_no_input_in_text_errors():
    valid = CreateInput(profile=snapshot(), confirmed=True)
    with pytest.raises(ValidationError):
        CreateInput.model_validate(valid.model_copy(update={"confirmed": 1}))
    with pytest.raises(ValidationError) as caught:
        ProfileSnapshot.model_validate({**snapshot(), "weekly_hours": "SECRET_SENTINEL"})
    assert "SECRET_SENTINEL" not in str(caught.value)
    assert ProfilePolicy().enabled is False
    with pytest.raises(ValidationError):
        ProfilePolicy.model_validate(ProfilePolicy().model_copy(update={"enabled": 1}))


def test_scopes_are_independent_and_adaptation_does_not_claim_rules():
    raw = snapshot()
    value = ProfileSnapshot.model_validate(raw)
    assert value.residence_region.value == "hk" and value.exam_province.value == "zhejiang"
    assert adaptation(value).reason == "ADAPTER_NOT_IMPLEMENTED"
    raw["course_system"] = {"status": "known", "value": "hkdse"}
    assert adaptation(ProfileSnapshot.model_validate(raw)).status == "unsupported"
    raw["course_system"] = {"status": "unknown", "value": None}
    assert adaptation(ProfileSnapshot.model_validate(raw)).reason == "MISSING_SCOPE"


def test_private_metadata_references_actual_immutable_snapshot():
    profile = ProfileSnapshot.model_validate(snapshot())
    data = ProfileVersionData(profile_id=uuid4(), version_id=uuid4(), version=1, profile=profile,
        profile_sha256=canonical_request_hash(profile.model_dump(mode="json")),
        confirmed_at=datetime(2026, 10, 3, tzinfo=timezone.utc), source="student_declared",
        expires_at=datetime(2028, 10, 3, tzinfo=timezone.utc), is_synthetic=True, adaptation=adaptation(profile))
    meta = ProfileMeta(api_version="v2", request_id="a" * 32, data_as_of=None,
        profile_version_id=data.version_id, profile_mode="synthetic", release_id=None,
        ruleset_version=None, data_mode="verified", model_mode="disabled")
    assert ProfileEnvelope[ProfileVersionData](data=data, meta=meta).meta.profile_version_id == data.version_id
    with pytest.raises(ValidationError):
        ProfileEnvelope[ProfileVersionData](data=data, meta=meta.model_copy(update={"profile_version_id": uuid4()}))
    with pytest.raises(ValidationError):
        ProfileVersionData.model_validate(data.model_copy(update={"profile_sha256": "0" * 64}))


def test_closed_profile_factory_has_safe_private_routes_and_no_body_collection():
    with TestClient(create_profiles_app(runtime())) as client:
        for path in ("/v2/profiles/context", "/v2/profiles", "/v2/profiles/" + str(uuid4())):
            result = client.get(path)
            assert result.status_code == 503
            assert result.headers["cache-control"] == "no-store"
        assert client.get("/v1/profiles").status_code == 404
    schema = create_profiles_v2_app(runtime()).openapi()
    assert len([path for path in schema["paths"] if path.startswith("/profiles")]) == 5
    assert len([param for param in schema["paths"]["/profiles"]["post"]["parameters"]
                if param["name"] == "Idempotency-Key"]) == 1
    assert all(param["name"] != "Idempotency-Key" for param in schema["paths"]["/profiles/{profile_id}/versions"]["post"].get("parameters", []))
