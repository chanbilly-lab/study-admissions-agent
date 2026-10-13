"""Exercise published schemas and actual HTTP JSON against the shared TS declarations."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from scripts.verify_contract import assert_openapi_contract, assert_schema_matches, load_contract
from services.api.app.main import create_app
from services.api.app.migrations import migrate
from services.api.app.seed import seed
from services.api.app.settings import Settings


ALICE = {"Authorization": "Bearer demo-alice-token"}
BOB = {"Authorization": "Bearer demo-bob-token"}


@pytest.fixture
def contract():
    return load_contract()


@pytest.fixture
def api():
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        sqlite_test_mode=True,
        supported_province="浙江",
        entry_year=2027,
        model_mode="mock",
        assessment_date=date(2026, 9, 30),
    )
    app = create_app(settings)
    migrate(app.state.engine)
    seed(app.state.engine)
    with TestClient(app) as client:
        yield client
    app.state.engine.dispose()


def success(response):
    assert response.status_code in {200, 201}, response.text
    return response.json()


def test_published_models_match_typescript(api, contract):
    openapi = success(api.get("/openapi.json"))
    assert_openapi_contract(contract, openapi)


@pytest.mark.parametrize(
    ("path", "method", "declaration"),
    [
        ("/v1/config", "get", "Envelope<RuntimeConfig>"),
        ("/v1/profiles", "get", "Envelope<Profile[]>"),
        ("/v1/profiles", "post", "Envelope<Profile>"),
        ("/v1/offerings", "get", "Envelope<Offering[]>"),
        ("/v1/profiles/{identifier}", "get", "Envelope<Profile>"),
        ("/v1/offerings/{identifier}", "get", "Envelope<Offering>"),
        ("/v1/evidence/{identifier}", "get", "Envelope<Evidence>"),
        ("/v1/eligibility/check", "post", "Envelope<Eligibility[]>"),
        ("/v1/plans/drafts", "post", "Envelope<PlanDraft>"),
        ("/v1/plans/{identifier}", "get", "Envelope<PlanDraft>"),
    ],
)
def test_endpoint_declares_the_actual_envelope(api, contract, path, method, declaration):
    openapi = success(api.get("/openapi.json"))
    operation = openapi["paths"][path][method]
    responses = operation["responses"]
    success_codes = [code for code in ("200", "201") if code in responses]
    assert success_codes, f"{method.upper()} {path} has no success response"
    schema = responses[success_codes[0]]["content"]["application/json"]["schema"]
    assert_schema_matches(contract, declaration, schema, openapi)


def test_profile_request_body_matches_typescript(api, contract):
    openapi = success(api.get("/openapi.json"))
    schema = openapi["paths"]["/v1/profiles"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert_schema_matches(contract, "ProfileInput", schema, openapi)


def test_http_roundtrip_keeps_demo_evidence_nulls_and_draft_types(api, contract):
    config = success(api.get("/v1/config"))
    contract.assert_payload("Envelope<RuntimeConfig>", config)
    assert config["meta"]["model_mode"] == "mock"
    assert config["data"]["demo_mode"] is True

    offerings = success(api.get("/v1/offerings"))
    contract.assert_payload("Envelope<Offering[]>", offerings)
    assert offerings["data"], "M0 must have actual DEMO project fixtures"
    assert any(item["deadline"] is None for item in offerings["data"]), "Missing-deadline fixture must survive JSON serialization"
    for offering in offerings["data"]:
        assert offering["id"].startswith("DEMO_")
        assert offering["institution_id"].startswith("DEMO_")
        assert offering["institution_name"].startswith("DEMO_")
        assert offering["is_synthetic"] is True
        detail = success(api.get(f"/v1/offerings/{offering['id']}"))
        contract.assert_payload("Envelope<Offering>", detail)

    profile_input = {
        "display_name": "DEMO_contract_roundtrip",
        "is_synthetic": True,
        "confirmed": True,
        "study_level": "bachelor",
        "course_system": "gaokao",
        "entry_year": config["data"]["entry_year"],
        "province": config["data"]["supported_province"],
        "applicant_category": "cn_mainland",
        "subjects": ["physics", "chemistry"],
        "assessments": {},
        "weekly_hours": 8,
    }
    contract.assert_payload("ProfileInput", profile_input)
    created = success(api.post("/v1/profiles", json=profile_input, headers=ALICE))
    contract.assert_payload("Envelope<Profile>", created)
    profile = created["data"]
    assert profile["owner_id"] == "demo_alice"
    assert created["meta"]["profile_version"] == profile["version"]
    own = success(api.get(f"/v1/profiles/{profile['id']}", headers=ALICE))
    contract.assert_payload("Envelope<Profile>", own)
    assert api.get(f"/v1/profiles/{profile['id']}", headers=BOB).status_code == 404
    profiles = success(api.get("/v1/profiles", headers=ALICE))
    contract.assert_payload("Envelope<Profile[]>", profiles)

    request = {"profile_version_id": profile["id"], "offering_ids": [item["id"] for item in offerings["data"]]}
    checked = success(api.post("/v1/eligibility/check", json=request, headers=ALICE))
    contract.assert_payload("Envelope<Eligibility[]>", checked)
    for result in checked["data"]:
        assert result["profile_version_id"] == profile["id"]
        assert result["status"] in {"eligible", "ineligible", "conditional", "unknown"}
        for evidence_id in result["evidence_ids"]:
            evidence = success(api.get(f"/v1/evidence/{evidence_id}"))
            contract.assert_payload("Envelope<Evidence>", evidence)
            assert evidence["data"]["source_url"].startswith("demo://")
            assert evidence["data"]["is_synthetic"] is True
            assert len(evidence["data"]["document_sha256"]) == 64

    draft = success(api.post("/v1/plans/drafts", json=request, headers=ALICE))
    contract.assert_payload("Envelope<PlanDraft>", draft)
    assert draft["data"]["status"] == "draft"
    assert draft["data"]["model_mode"] == "mock"
    assert all(task["user_confirmed"] is False for task in draft["data"]["tasks"])
    read_draft = success(api.get(f"/v1/plans/{draft['data']['id']}", headers=ALICE))
    contract.assert_payload("Envelope<PlanDraft>", read_draft)
    assert api.get(f"/v1/plans/{draft['data']['id']}", headers=BOB).status_code == 404


@pytest.mark.parametrize("bad_value", [False, None])
def test_runtime_rejects_unconfirmed_or_non_synthetic_profile(api, bad_value):
    payload = {
        "display_name": "DEMO_invalid_contract",
        "is_synthetic": True,
        "confirmed": True,
        "study_level": "bachelor",
        "course_system": "gaokao",
        "entry_year": 2027,
        "province": "浙江",
        "applicant_category": "cn_mainland",
        "subjects": [],
        "assessments": {},
        "weekly_hours": 8,
    }
    payload["confirmed"] = bad_value
    assert api.post("/v1/profiles", json=payload, headers=ALICE).status_code == 422
    payload["confirmed"] = True
    payload["is_synthetic"] = bad_value
    assert api.post("/v1/profiles", json=payload, headers=ALICE).status_code == 422


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("achieved", {"DEMO_CN_MATH": "eligible", "DEMO_GB_DEFERRED": "eligible", "DEMO_GB_NO_DEFERRAL": "eligible", "DEMO_GB_MISSING_DEADLINE": "eligible"}),
        ("low_math", {"DEMO_CN_MATH": "ineligible", "DEMO_GB_DEFERRED": "eligible", "DEMO_GB_NO_DEFERRAL": "eligible", "DEMO_GB_MISSING_DEADLINE": "eligible"}),
        ("missing_language", {"DEMO_CN_MATH": "eligible", "DEMO_GB_DEFERRED": "conditional", "DEMO_GB_NO_DEFERRAL": "unknown", "DEMO_GB_MISSING_DEADLINE": "unknown"}),
        ("low_total_missing_language", {"DEMO_CN_MATH": "ineligible", "DEMO_GB_DEFERRED": "ineligible", "DEMO_GB_NO_DEFERRAL": "ineligible", "DEMO_GB_MISSING_DEADLINE": "ineligible"}),
    ],
)
def test_four_statuses_are_serialized_from_actual_deterministic_results(api, contract, scenario, expected):
    assessments = {
        "gaokao_total": {"value": 620, "scale": 750, "unit": "points", "kind": "achieved"},
        "math": {"value": 120, "scale": 150, "unit": "points", "kind": "achieved"},
        "english_language": {"value": 7, "scale": 9, "unit": "band", "kind": "achieved"},
    }
    if scenario == "low_math":
        assessments["math"]["value"] = 90
    if scenario in {"missing_language", "low_total_missing_language"}:
        del assessments["english_language"]
    if scenario == "low_total_missing_language":
        assessments["gaokao_total"]["value"] = 500
    payload = {
        "display_name": f"DEMO_contract_{scenario}", "is_synthetic": True, "confirmed": True,
        "study_level": "bachelor", "course_system": "gaokao", "entry_year": 2027,
        "province": "浙江", "applicant_category": "cn_mainland", "subjects": ["physics"],
        "assessments": assessments, "weekly_hours": 8,
    }
    created = success(api.post("/v1/profiles", json=payload, headers=ALICE))
    contract.assert_payload("Envelope<Profile>", created)
    request = {"profile_version_id": created["data"]["id"], "offering_ids": list(expected)}
    checked = success(api.post("/v1/eligibility/check", json=request, headers=ALICE))
    contract.assert_payload("Envelope<Eligibility[]>", checked)
    assert {result["offering_id"]: result["status"] for result in checked["data"]} == expected
    if scenario == "missing_language":
        conditional = next(result for result in checked["data"] if result["status"] == "conditional")
        assert conditional["conditions"]
        assert {"DEMO_EVIDENCE_GB_DEFERRED_POLICY", "DEMO_EVIDENCE_GB_DEFERRED_DEADLINE"} <= set(conditional["evidence_ids"])
