"""Real ASGI, cookie/CSRF and PostgreSQL profile requests, with no route mocks."""

import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from services.api.app.api.profiles import create_profiles_app, create_profiles_v2_app
from services.api.app.auth.router import SESSION_COOKIE
from services.api.app.profiles.models import ProfileRoot, ProfileVersion
from services.api.app.profiles.schemas import AppendInput
from services.api.app.settings import V2RuntimeSettings

from .conftest import snapshot_payload
from .test_t23_service import KEY, SENTINEL, durable_state, rows


pytestmark = pytest.mark.postgres


@pytest.fixture
def client(profile_service, auth_service, runtime):
    with TestClient(create_profiles_v2_app(runtime, identity_service=auth_service, profile_service=profile_service),
                    base_url="https://app.test.invalid", follow_redirects=False) as http:
        yield http


def identify(client, actor):
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, actor.cookie.get_secret_value())
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return {"Origin": "https://app.test.invalid", "X-CSRF-Token": response.json()["data"]["csrf_token"]}


def safe(response, status):
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    body = response.json()
    identifier = body["meta"]["request_id"] if status < 400 else body["error"]["request_id"]
    assert identifier == response.headers["x-request-id"]
    if status >= 400:
        assert SENTINEL not in response.text and KEY.get_secret_value() not in response.text
    return body["data"] if status < 400 else body["error"]


def test_http_confirmed_create_append_and_precise_history_are_actual_versions(client, owner, pg_engine):
    headers = identify(client, owner)
    request = {"profile": snapshot_payload(), "confirmed": True}
    headers["Idempotency-Key"] = KEY.get_secret_value()
    first = safe(client.post("/profiles", json=request, headers=headers), 200)
    root, version_id = first["version"]["profile_id"], first["version"]["version_id"]
    assert first["replayed"] is False
    replay = safe(client.post("/profiles", json=request, headers=headers), 200)
    assert replay["replayed"] is True and replay["version"] == first["version"]
    payload = snapshot_payload()
    payload["weekly_hours"] = "0"
    headers.pop("Idempotency-Key")
    second = safe(client.post(f"/profiles/{root}/versions", json={"profile": payload,
        "confirmed": True, "expected_current_version": 1}, headers=headers), 200)
    assert second["version"]["version"] == 2
    assert safe(client.get(f"/profiles/{root}"), 200) == second["version"]
    assert safe(client.get(f"/profiles/{root}/versions/{version_id}"), 200) == first["version"]
    safe(client.post(f"/profiles/{root}/versions", json={"profile": payload,
        "confirmed": True, "expected_current_version": 1}, headers=headers), 409)
    assert len(rows(pg_engine, ProfileRoot)) == 1 and len(rows(pg_engine, ProfileVersion)) == 2


@pytest.mark.parametrize("target", ["create", "append"])
@pytest.mark.parametrize("attack", ["missing_csrf", "wrong_origin", "duplicate_csrf", "duplicate_origin"])
def test_every_new_write_rejects_missing_or_ambiguous_csrf_and_origin(target, attack, created,
        client, owner, pg_engine):
    headers = identify(client, owner)
    if attack == "missing_csrf":
        headers.pop("X-CSRF-Token")
    elif attack == "wrong_origin":
        headers["Origin"] = "https://foreign.test.invalid"
    else:
        name = "X-CSRF-Token" if attack == "duplicate_csrf" else "Origin"
        headers = list(headers.items()) + [(name, headers[name])]
    headers = list(headers.items()) if isinstance(headers, dict) else headers
    headers.append(("Idempotency-Key", KEY.get_secret_value()))
    payload = {"profile": snapshot_payload(), "confirmed": True}
    path = "/profiles"
    if target == "append":
        path = f"/profiles/{created.version.profile_id}/versions"
        payload["expected_current_version"] = 1
    before = durable_state(pg_engine)
    safe(client.post(path, json=payload, headers=headers), 403)
    assert durable_state(pg_engine) == before


@pytest.mark.parametrize("attack", ["owner", "confirmed_integer", "duplicate_key", "unknown_grade", "bad_numeric"])
def test_http_untrusted_identity_and_ambiguous_body_never_reach_profile_storage(attack, client, owner, pg_engine):
    headers = identify(client, owner)
    headers.update({"Idempotency-Key": KEY.get_secret_value(), "Content-Type": "application/json"})
    request = {"profile": snapshot_payload(), "confirmed": True}
    if attack == "owner":
        request.update(owner_user_id=str(uuid4()), roles=["data_admin"], is_synthetic=False, verified=True)
    elif attack == "confirmed_integer":
        request["confirmed"] = 1
    elif attack == "unknown_grade":
        request["profile"]["assessments"]["DEMO_unknown"] = request["profile"]["assessments"]["math"]
    elif attack == "bad_numeric":
        request["profile"]["assessments"]["gaokao_total"]["achieved"]["value"] = SENTINEL
    body = json.dumps(request)
    if attack == "duplicate_key":
        body = body.replace('"confirmed": true', '"confirmed": true, "confirmed": false')
    before = durable_state(pg_engine)
    safe(client.post("/profiles", content=body, headers=headers), 422)
    assert durable_state(pg_engine) == before


def test_http_actor_switch_and_history_uuid_never_leak_other_students(created, client, owner,
        admitted_actor_factory, pg_engine):
    bob = admitted_actor_factory()
    identify(client, bob)
    root, version = created.version.profile_id, created.version.version_id
    safe(client.get(f"/profiles/{root}"), 404)
    safe(client.get(f"/profiles/{root}/versions/{version}"), 404)
    page = safe(client.get("/profiles"), 200)
    assert page["items"] == [] and str(root) not in json.dumps(page)
    client.cookies.clear()
    safe(client.get(f"/profiles/{root}"), 401)
    assert len(rows(pg_engine, ProfileRoot)) == 1


def test_http_pagination_binds_current_actor_filters_and_cursor_to_current_version_window(client,
        owner, admitted_actor_factory, profile_service, principal, create_input):
    for number in range(3):
        profile_service.create_profile(principal, create_input, type(KEY)("DEMO_T23_PAGE_" + str(number)))
    identify(client, owner)
    first = safe(client.get("/profiles?limit=1"), 200)
    assert len(first["items"]) == 1 and first["next_cursor"]
    second = safe(client.get("/profiles", params={"limit": 1, "cursor": first["next_cursor"]}), 200)
    assert second["items"][0]["profile_id"] != first["items"][0]["profile_id"]
    for query in ("limit=0", "limit=21", "limit=1.0", "limit=1&limit=1", "owner=" + str(uuid4())):
        safe(client.get("/profiles?" + query), 422)
    safe(client.get("/profiles?cursor=bad"), 409)
    identify(client, admitted_actor_factory())
    safe(client.get("/profiles", params={"limit": 1, "cursor": first["next_cursor"]}), 409)
    identify(client, owner)
    profile_service.append_version(principal, UUID(first["items"][0]["profile_id"]), AppendInput(
            profile=snapshot_payload(), confirmed=True, expected_current_version=1))
    safe(client.get("/profiles", params={"limit": 1, "cursor": first["next_cursor"]}), 409)


def test_closed_factory_and_production_do_not_access_database_or_old_v1(profile_service, auth_service, pg_engine):
    calls = []
    def capture(*args):
        calls.append(True)
    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        runtime = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
            database_url=None, legacy_demo_mode=None, _env_file=None)
        with TestClient(create_profiles_app(runtime), base_url="https://app.test.invalid", follow_redirects=False) as client:
            for path in ("/v2/profiles/context", "/v2/profiles", "/v2/profiles/" + str(uuid4())):
                response = client.get(path)
                assert response.status_code == 503 and response.headers["cache-control"] == "no-store"
            assert client.get("/v1/profiles").status_code == 404
            assert client.get("/v2/profiles", headers={"Authorization": "Bearer demo-alice-token"}).status_code == 401
        assert calls == []
        with pytest.raises(ValueError):
            create_profiles_app(runtime, identity_service=auth_service, profile_service=profile_service)
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)
