"""Actual ASGI cookie/CSRF requests against isolated PostgreSQL T32 state."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import json
import re
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.api.plans import create_plans_v2_app
from services.api.app.auth.router import SESSION_COOKIE
from services.api.app.plans.models import PlanRoot, PlanVersion


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T32_PRIVATE_SENTINEL_DO_NOT_ECHO"
KEY = "DEMO_T32_HTTP_CONFIRM"


@contextmanager
def client_for(case, *, execution=True):
    service = case.service
    plans = service.plans_service
    eligibility = plans.eligibility_service
    app = create_plans_v2_app(plans.auth_service.runtime_settings,
        identity_service=plans.auth_service, profile_service=eligibility.profile_service,
        assessment_service=eligibility, execution_service=service if execution else None)
    with TestClient(app, base_url="https://app.test.invalid", follow_redirects=False) as client:
        yield client


def identify(client, actor):
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, actor.cookie.get_secret_value())
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return {"Origin": "https://app.test.invalid", "X-CSRF-Token": response.json()["data"]["csrf_token"]}


def safe(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
    body = response.json()
    identifier = body["meta"]["request_id"] if status == 200 else body["error"]["request_id"]
    assert identifier == response.headers["x-request-id"]
    if status != 200:
        assert SENTINEL not in response.text and KEY not in response.text
        return body["error"]
    data = body["data"]
    execution = data.get("execution", data)
    if "proposal" in execution:
        draft = execution["proposal"]["effective_draft"]
        assert body["meta"]["profile_version_id"] == draft["profile_version_id"]
        assert body["meta"]["profile_mode"] == "synthetic"
        assert body["meta"]["release_id"] is None
    else:
        assert body["meta"]["profile_version_id"] is None
    return data


def create(client, case, headers):
    return safe(client.post("/plans", json=case.request.model_dump(mode="json"), headers=headers), 200)


def workspace(data, clock, *, hours="0"):
    start, end = clock() + timedelta(seconds=1), clock() + timedelta(seconds=21)
    return {"expected_version": data["state_version"],
        "estimate_overrides": [{"task_key": task["task_key"], "estimated_hours": hours}
            for task in data["proposal"]["effective_draft"]["tasks"]],
        "schedule": {"horizon_start": start.isoformat(), "horizon_end": end.isoformat(),
            "display_timezone": "Asia/Hong_Kong", "weekly_hours": "1",
            "slots": [{"slot_id": str(uuid4()), "start_at": start.isoformat(), "end_at": end.isoformat()}],
            "internal_goals": [], "availability_confirmed": True, "rest_excluded": True}}


def confirm(data):
    return {"expected_version": data["state_version"],
        "expected_draft_sha256": data["proposal"]["effective_draft"]["draft_sha256"],
        "expected_schedule_sha256": data["proposal"]["schedule"]["schedule_sha256"],
        "confirmed": True, "acknowledge_unverified_deadlines": True}


def test_actual_http_create_workspace_history_confirmation_and_completion(execution_case_factory, clock, pg_engine):
    case = execution_case_factory(create=False)
    with client_for(case) as client:
        headers = identify(client, case.owner)
        context = safe(client.get("/plans/context"), 200)
        assert context["can_create"] is True
        original = create(client, case, headers)
        plan_id = original["plan_id"]
        assert original["state_version"] == 1 and original["state"] == "draft"
        assert original["proposal"]["schedule"] is None
        edited = safe(client.post(f"/plans/{plan_id}/workspace", json=workspace(original, clock), headers=headers), 200)
        assert edited["state_version"] == 2 and edited["source_draft_sha256"] == original["source_draft_sha256"]
        assert edited["proposal"]["schedule"]["status"] == "ready"
        assert edited["proposal"]["schedule"]["constraints_complete"] is False
        assert safe(client.get(f"/plans/{plan_id}/versions/1"), 200) == original
        page = safe(client.get("/plans?limit=1"), 200)
        assert [item["plan_id"] for item in page["items"]] == [plan_id]
        request, keyed = confirm(edited), headers | {"Idempotency-Key": KEY}
        first = safe(client.post(f"/plans/{plan_id}/confirm", json=request, headers=keyed), 200)
        assert first["replayed"] is False and first["confirmed_state_version"] == 3
        assert first["execution"]["completed_tasks"] == []  # zero hours is not automatic completion
        current = first["execution"]
        originals = []
        remaining = {task["task_key"]: task for task in current["proposal"]["effective_draft"]["tasks"]}
        completed = set()
        while remaining:
            task = next(task for task in remaining.values() if set(task["dependency_keys"]) <= completed)
            payload = {"expected_version": current["state_version"], "confirmed": True}
            path = f"/plans/{plan_id}/tasks/{task['task_key']}/complete"
            result = safe(client.post(path, json=payload, headers=headers), 200)
            assert result["replayed"] is False
            originals.append((path, payload))
            current = result["execution"]
            completed.add(task["task_key"])
            del remaining[task["task_key"]]
        replay = safe(client.post(f"/plans/{plan_id}/confirm", json=request, headers=keyed), 200)
        assert replay["replayed"] is True and replay["confirmed_state_version"] == 3
        assert replay["execution"]["completed_tasks"] == current["completed_tasks"]
        duplicate = safe(client.post(originals[0][0], json=originals[0][1], headers=headers), 200)
        assert duplicate["replayed"] is True and duplicate["execution"]["state_version"] == current["state_version"]
        assert safe(client.get(f"/plans/{plan_id}"), 200) == current
        confirmed_history = safe(client.get(f"/plans/{plan_id}/versions/3"), 200)
        assert confirmed_history["completed_tasks"] == []
        safe(client.post(f"/plans/{plan_id}/workspace", json=workspace(current, clock), headers=headers), 409)
    with Session(pg_engine) as session:
        assert session.get(PlanRoot, UUID(plan_id)).current_version == 1
        assert len(session.scalars(select(PlanVersion)).all()) == 1


def test_bounded_untrusted_http_bodies_queries_headers_and_paths(execution_case_factory, clock):
    case = execution_case_factory(create=False)
    with client_for(case) as client:
        headers = identify(client, case.owner)
        raw = case.request.model_dump(mode="json")
        variants = [raw | {"owner_user_id": SENTINEL}, raw | {"confirmed": 1},
            raw | {"assessment_ids": [str(uuid4()), str(uuid4())], "clock": SENTINEL},
            raw | {"rules": SENTINEL}, raw | {"assessment_ids": None}]
        for payload in variants:
            safe(client.post("/plans", json=payload, headers=headers), 422)
        for content in (json.dumps(raw).replace('"confirmed": true', '"confirmed": true, "confirmed": false'),
                        '{"confirmed":NaN}', "[{}]", "{", "\ufeff{}", " " * 65537):
            safe(client.post("/plans", content=content.encode("utf-8"),
                headers=headers | {"Content-Type": "application/json"}), 422)
        safe(client.post("/plans", json=raw, headers=headers | {"Idempotency-Key": KEY}), 422)
        original = create(client, case, headers)
        plan_id = original["plan_id"]
        for query in ("?owner=" + SENTINEL, "?limit=1&limit=2", "?limit=1.0", "?limit=0", "?limit=21",
                      "?cursor=", "?cursor=" + "a" * 1025):
            safe(client.get("/plans" + query), 422)
        for path in (f"/plans/{plan_id}?proof={SENTINEL}", "/plans/not-a-uuid",
                     f"/plans/{plan_id}/versions/01", f"/plans/{plan_id}/versions/2147483648"):
            safe(client.get(path), 422)
        good = workspace(original, clock)
        malformed = []
        for field, value in (("weekly_hours", 1.0), ("availability_confirmed", 1),
                             ("horizon_start", "2026-10-04T00:00:00+08:00")):
            candidate = deepcopy(good)
            candidate["schedule"][field] = value
            malformed.append(candidate)
        malformed.append(good | {"expected_version": True})
        for candidate in malformed:
            safe(client.post(f"/plans/{plan_id}/workspace", json=candidate, headers=headers), 422)
        safe(client.post(f"/plans/{plan_id}/tasks/{'A' * 64}/complete",
            json={"expected_version": 1, "confirmed": True}, headers=headers), 422)
        assert safe(client.get(f"/plans/{plan_id}"), 200) == original


def test_real_origin_and_csrf_apply_to_every_plan_write(execution_case_factory, clock):
    case = execution_case_factory(create=False)
    with client_for(case) as client:
        headers = identify(client, case.owner)
        original = create(client, case, headers)
        plan_id = original["plan_id"]
        task = original["proposal"]["effective_draft"]["tasks"][0]["task_key"]
        paths = [("/plans", case.request.model_dump(mode="json")),
            (f"/plans/{plan_id}/workspace", workspace(original, clock)),
            (f"/plans/{plan_id}/confirm", {"confirmed": True}),
            (f"/plans/{plan_id}/tasks/{task}/complete", {"expected_version": 1, "confirmed": True})]
        for path, payload in paths:
            for proof in ({"Origin": "https://app.test.invalid"}, headers | {"Origin": "https://foreign.test.invalid"},
                          list(headers.items()) + [("Origin", headers["Origin"])],
                          list(headers.items()) + [("X-CSRF-Token", headers["X-CSRF-Token"])]):
                safe(client.post(path, json=payload, headers=proof), 403)
        client.cookies.clear()
        safe(client.get(f"/plans/{plan_id}"), 401)
        safe(client.post("/plans", json=case.request.model_dump(mode="json"), headers=headers), 401)


def test_owner_filtering_and_configured_identity_closed_capabilities(execution_case_factory, actor_factory):
    case = execution_case_factory(create=False)
    with client_for(case) as client:
        headers = identify(client, case.owner)
        original = create(client, case, headers)
        other = actor_factory()
        identify(client, other)
        # This actor has no core purpose, so no private list/object capability is granted.
        safe(client.get("/plans"), 403)
        safe(client.get(f"/plans/{original['plan_id']}"), 403)
    with client_for(case, execution=False) as client:
        identify(client, case.owner)
        context = safe(client.get("/plans/context"), 200)
        assert context["reason"] == "processing_disabled"
        assert not any(context[name] for name in ("can_create", "can_read", "can_edit", "can_confirm", "can_complete"))
        safe(client.get("/plans"), 503)


def test_confirmation_and_completion_require_precise_current_state(execution_case_factory, clock):
    case = execution_case_factory(create=False, expression={"op":"gte", "field":{"name":"assessment","key":"math","basis":"achieved"},
        "value":{"kind":"decimal","value":"100","unit":"points","scale":"150"}}, deferral=True)
    with client_for(case) as client:
        headers = identify(client, case.owner)
        original = create(client, case, headers)
        plan_id = original["plan_id"]
        task = original["proposal"]["effective_draft"]["tasks"][0]["task_key"]
        safe(client.post(f"/plans/{plan_id}/tasks/{task}/complete",
            json={"expected_version": 1, "confirmed": True}, headers=headers), 409)
        edited = safe(client.post(f"/plans/{plan_id}/workspace", json=workspace(original, clock), headers=headers), 200)
        safe(client.post(f"/plans/{plan_id}/workspace", json=workspace(original, clock), headers=headers), 409)
        request, keyed = confirm(edited), headers | {"Idempotency-Key": KEY}
        for payload, proof, status in ((request | {"acknowledge_unverified_deadlines": False}, keyed, 422),
                                      (request | {"expected_draft_sha256": "f" * 64}, keyed, 409),
                                      (request, headers, 422)):
            safe(client.post(f"/plans/{plan_id}/confirm", json=payload, headers=proof), status)
        confirmed = safe(client.post(f"/plans/{plan_id}/confirm", json=request, headers=keyed), 200)["execution"]
        child = next(task for task in confirmed["proposal"]["effective_draft"]["tasks"] if task["dependency_keys"])
        safe(client.post(f"/plans/{plan_id}/tasks/{child['task_key']}/complete",
            json={"expected_version": confirmed["state_version"], "confirmed": True}, headers=headers), 409)
        safe(client.post(f"/plans/{plan_id}/confirm", json=request | {"expected_version": 1}, headers=keyed), 409)
        safe(client.post(f"/plans/{plan_id}/tasks/{task}/complete",
            json={"expected_version": 1, "confirmed": True}, headers=headers), 409)
