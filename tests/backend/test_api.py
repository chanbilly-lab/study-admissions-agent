from copy import deepcopy

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.app.models import EligibilityResultRecord, PlanDraftRecord
from .conftest import ALICE, BOB

OFFERINGS = ["DEMO_CN_MATH", "DEMO_GB_DEFERRED", "DEMO_GB_NO_DEFERRAL", "DEMO_GB_MISSING_DEADLINE"]


def test_mock_complete_flow_and_evidence(client, saved_profile):
    config = client.get("/v1/config").json()
    assert config["data"] == {"supported_province": "浙江", "demo_mode": True, "model_mode": "mock", "entry_year": 2027, "live_available": False}
    catalog = client.get("/v1/offerings").json()["data"]
    assert len(catalog) == 4
    for offering in catalog:
        assert offering["id"].startswith("DEMO_") and offering["title"].startswith("DEMO_")
        assert offering["institution_name"].startswith("DEMO_") and offering["is_synthetic"] is True
    payload = {"profile_version_id": saved_profile["id"], "offering_ids": OFFERINGS}
    check = client.post("/v1/eligibility/check", headers=ALICE, json=payload)
    assert check.status_code == 200
    assert all(item["status"] == "eligible" for item in check.json()["data"])
    assert check.json()["meta"]["profile_version"] == 1
    plan_response = client.post("/v1/plans/drafts", headers=ALICE, json=payload)
    assert plan_response.status_code == 201, plan_response.text
    draft = plan_response.json()["data"]
    assert draft["status"] == "draft" and draft["is_synthetic"] is True and draft["model_mode"] == "mock"
    assert all(not item["user_confirmed"] for item in draft["tasks"])
    assert "DEMO 演示模式" in draft["narrative"]
    assert client.get(f"/v1/plans/{draft['id']}", headers=ALICE).json()["data"] == draft
    for task in draft["tasks"]:
        if task["hard_deadline_id"]:
            assert task["hard_deadline_id"] in task["evidence_ids"]
            assert "T" not in task["target_date"]  # date-only source never invents a midnight instant.
        for identifier in task["evidence_ids"]:
            evidence = client.get(f"/v1/evidence/{identifier}").json()["data"]
            assert evidence["is_synthetic"] is True and evidence["source_url"].startswith("demo://")
            assert task["offering_id"] in evidence["offering_ids"]


def test_four_states_from_confirmed_profiles(client, profile_input):
    profile_input["assessments"]["math"]["value"] = 90
    del profile_input["assessments"]["english_language"]
    profile = client.post("/v1/profiles", headers=ALICE, json=profile_input).json()["data"]
    results = client.post("/v1/eligibility/check", headers=ALICE,
                          json={"profile_version_id": profile["id"], "offering_ids": OFFERINGS}).json()["data"]
    assert [item["status"] for item in results] == ["ineligible", "conditional", "unknown", "unknown"]
    assert results[1]["conditions"] and results[1]["missing_fields"] == ["assessments.english_language"]
    assert not results[2]["conditions"] and not results[3]["conditions"]
    assert all("录取概率" in item["competition_context"] for item in results)


@pytest.mark.parametrize("field,value", [("confirmed", False), ("confirmed", 1), ("is_synthetic", False), ("owner_id", "demo_bob"), ("study_level", "master")])
def test_profile_rejects_unconfirmed_real_or_client_owner(client, profile_input, field, value):
    profile_input[field] = value
    assert client.post("/v1/profiles", headers=ALICE, json=profile_input).status_code == 422
    assert client.get("/v1/profiles", headers=ALICE).json()["data"] == []


def test_rejects_unknown_assessment_key_and_over_scale(client, profile_input):
    unsupported = deepcopy(profile_input)
    unsupported["assessments"]["ielts"] = unsupported["assessments"].pop("english_language")
    assert client.post("/v1/profiles", headers=ALICE, json=unsupported).status_code == 422
    profile_input["assessments"]["math"]["value"] = 151
    assert client.post("/v1/profiles", headers=ALICE, json=profile_input).status_code == 422


def test_two_users_cannot_read_check_or_plan_each_others_profiles(client, saved_profile):
    assert saved_profile["owner_id"] == "demo_alice"
    assert len(client.get("/v1/profiles", headers=ALICE).json()["data"]) == 1
    assert client.get("/v1/profiles", headers=BOB).json()["data"] == []
    assert client.get(f"/v1/profiles/{saved_profile['id']}", headers=BOB).status_code == 404
    payload = {"profile_version_id": saved_profile["id"], "offering_ids": [OFFERINGS[0]]}
    for endpoint in ("/v1/eligibility/check", "/v1/plans/drafts"):
        assert client.post(endpoint, headers=BOB, json=payload).status_code == 404
    plan = client.post("/v1/plans/drafts", headers=ALICE, json=payload).json()["data"]
    assert client.get(f"/v1/plans/{plan['id']}", headers=BOB).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}, {"Authorization": "Bearer demo_alice"}])
def test_private_endpoints_require_server_credentials(client, profile_input, headers):
    assert client.get("/v1/profiles", headers=headers).status_code == 401
    assert client.post("/v1/profiles", headers=headers, json=profile_input).status_code == 401


def test_scope_filters_and_cross_year_unknown(client, profile_input):
    assert len(client.get("/v1/offerings?country=CN").json()["data"]) == 1
    assert len(client.get("/v1/offerings?country=GB").json()["data"]) == 3
    assert client.get("/v1/offerings?entry_year=2028").json()["data"] == []
    assert client.get("/v1/offerings?province=广东").status_code == 422
    profile_input["province"] = "广东"
    assert client.post("/v1/profiles", headers=ALICE, json=profile_input).status_code == 422
    profile_input["province"] = "浙江"
    profile_input["entry_year"] = 2028
    profile = client.post("/v1/profiles", headers=ALICE, json=profile_input).json()["data"]
    response = client.post("/v1/eligibility/check", headers=ALICE,
                           json={"profile_version_id": profile["id"], "offering_ids": [OFFERINGS[0]]})
    assert response.json()["data"][0]["status"] == "unknown"


def test_no_deadlines_are_not_fabricated(client, saved_profile):
    plan = client.post("/v1/plans/drafts", headers=ALICE,
                       json={"profile_version_id": saved_profile["id"], "offering_ids": [OFFERINGS[0], OFFERINGS[2], OFFERINGS[3]]}).json()["data"]
    assert all(task["target_date"] is None and task["hard_deadline_id"] is None for task in plan["tasks"])


def test_plan_recomputes_and_rejects_client_results(client, saved_profile):
    payload = {"profile_version_id": saved_profile["id"], "offering_ids": [OFFERINGS[0]], "eligibility_results": [{"status": "eligible"}]}
    assert client.post("/v1/plans/drafts", headers=ALICE, json=payload).status_code == 422


def test_health_and_cors(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    for origin in ("http://127.0.0.1:5173", "http://localhost:5173"):
        response = client.options("/v1/profiles", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_live_mode_explicitly_unavailable_without_fallback(app, saved_profile):
    from fastapi.testclient import TestClient
    from services.api.app.providers import LiveProvider
    app.state.settings.model_mode = "live"
    app.state.provider = LiveProvider()
    with TestClient(app) as client:
        assert client.get("/v1/config").json()["data"]["model_mode"] == "live"
        response = client.post("/v1/plans/drafts", headers=ALICE,
                               json={"profile_version_id": saved_profile["id"], "offering_ids": [OFFERINGS[0]]})
        assert response.status_code == 503 and "不会回退" in response.json()["detail"]
    with Session(app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(PlanDraftRecord)) == 0
        assert session.scalar(select(func.count()).select_from(EligibilityResultRecord)) == 0
