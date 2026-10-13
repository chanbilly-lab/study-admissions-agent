"""Test-only routes prove dependencies and central guards; factories expose none."""

from contextlib import contextmanager
import re
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field
import pytest

from services.api.app.api.identity import create_identity_v2_app
from services.api.app.api.v2.router import no_config_query
from services.api.app.auth.dependencies import authorization_service, current_principal, owned_resource
from services.api.app.auth.router import SESSION_COOKIE

from .conftest import ORIGIN


class TouchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)


def private_query(request: Request, principal=Depends(current_principal)):
    # The private marker must be set even when strict query validation refuses input.
    no_config_query(request)


@contextmanager
def probe_http(harness, actor=None, *, mounted=False, closed=False):
    child = create_identity_v2_app(harness.service.runtime_settings,
        identity_service=None if closed else harness.service)
    original_paths = set(child.openapi()["paths"])

    @child.get("/probe/private/{resource_id}", include_in_schema=False,
               dependencies=[Depends(private_query)])
    def read_owned(resource=Depends(owned_resource("profile"))):
        return {"id": str(resource.id), "version": resource.version}

    @child.get("/probe/list", include_in_schema=False, dependencies=[Depends(private_query)])
    def list_owned(principal=Depends(current_principal), service=Depends(authorization_service)):
        page = service.list_owned(principal, "profile")
        return {"ids": [str(row.id) for row in page.items], "total": page.total}

    @child.post("/probe/private/{resource_id}", include_in_schema=False,
                dependencies=[Depends(private_query)])
    def touch_owned(body: TouchInput, resource=Depends(owned_resource("profile", "write")),
                    principal=Depends(current_principal), service=Depends(authorization_service)):
        touched = service.touch_owned(principal, "profile", resource.id, body.expected_version)
        return {"id": str(touched.id), "version": touched.version}

    assert set(child.openapi()["paths"]) == original_paths
    assert not any("probe" in path for path in original_paths)
    if mounted:
        app = FastAPI()
        app.mount("/v2", child)
        prefix = "/v2"
    else:
        app, prefix = child, ""
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as http:
        if actor is not None:
            http.cookies.set(SESSION_COOKIE, actor.cookie.get_secret_value(), domain="app.test.invalid", path="/")
        yield http, prefix


def private_headers(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["referrer-policy"] == "no-referrer"
    identifier = response.headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", identifier)
    if response.status_code >= 400:
        assert response.json()["error"]["request_id"] == identifier


def student(harness):
    actor = harness.account()
    harness.role(actor)
    return actor


@pytest.mark.parametrize("mounted", (False, True), ids=("standalone", "mounted"))
def test_private_gets_are_no_store_and_foreign_missing_are_safe(harness, mounted):
    actor, other = student(harness), student(harness)
    ours, theirs = harness.owned(actor), harness.owned(other)
    with probe_http(harness, actor, mounted=mounted) as (http, prefix):
        listed = http.get(prefix + "/probe/list")
        assert listed.status_code == 200
        assert listed.json() == {"ids": [str(ours.id)], "total": 1}
        private_headers(listed)
        own = http.get(prefix + "/probe/private/" + str(ours.id), headers={"X-Request-ID": "client-forged"})
        assert own.status_code == 200 and own.json()["id"] == str(ours.id)
        private_headers(own)
        denied = http.get(prefix + "/probe/private/" + str(theirs.id))
        missing = http.get(prefix + "/probe/private/" + str(uuid4()))
        for response in (denied, missing):
            assert response.status_code == 404
            private_headers(response)
            assert response.json()["error"]["code"] == "NOT_FOUND"
            assert str(theirs.id) not in response.text and str(other.user_id) not in response.text
        assert denied.json()["error"]["message"] == missing.json()["error"]["message"]


@pytest.mark.parametrize("mounted", (False, True))
@pytest.mark.parametrize("state,status", (("anonymous", 401), ("role_missing", 403), ("closed", 503)))
def test_private_get_failures_have_same_cache_and_request_id_guards(harness, mounted, state, status):
    actor = harness.account() if state == "role_missing" else None
    with probe_http(harness, actor, mounted=mounted, closed=state == "closed") as (http, prefix):
        response = http.get(prefix + "/probe/list")
        assert response.status_code == status
        private_headers(response)


@pytest.mark.parametrize("mounted", (False, True))
def test_cookie_write_requires_csrf_origin_and_current_owner(harness, mounted):
    actor, other = student(harness), student(harness)
    ours, theirs = harness.owned(actor), harness.owned(other)
    with probe_http(harness, actor, mounted=mounted) as (http, prefix):
        token = http.get(prefix + "/auth/csrf").json()["data"]["csrf_token"]
        path = prefix + "/probe/private/" + str(ours.id)
        body = {"expected_version": ours.version}
        for headers in ({}, {"Origin": ORIGIN}, {"X-CSRF-Token": token},
            {"Origin": "https://attacker.test.invalid", "X-CSRF-Token": token},
            {"Origin": ORIGIN, "X-CSRF-Token": "x" * 43}):
            refused = http.post(path, headers=headers, json=body)
            assert refused.status_code == 403
            private_headers(refused)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": token}
        foreign = http.post(prefix + "/probe/private/" + str(theirs.id), headers=headers, json=body)
        assert foreign.status_code == 404
        private_headers(foreign)
        changed = http.post(path, headers=headers, json=body)
        assert changed.status_code == 200 and changed.json()["version"] == ours.version + 1
        private_headers(changed)
        duplicate = http.post(path, headers=headers, json=body)
        assert duplicate.status_code == 409
        private_headers(duplicate)


@pytest.mark.parametrize("mounted", (False, True))
def test_client_role_owner_injection_never_assigns_authority(harness, mounted):
    actor, other = student(harness), student(harness)
    ours = harness.owned(actor)
    with probe_http(harness, actor, mounted=mounted) as (http, prefix):
        token = http.get(prefix + "/auth/csrf").json()["data"]["csrf_token"]
        headers = {"Origin": ORIGIN, "X-CSRF-Token": token,
            "X-Owner-ID": str(other.user_id), "X-Role": "data_admin", "X-User-ID": str(other.user_id)}
        for extra in ({"owner_user_id": str(other.user_id)}, {"owner_id": str(other.user_id)},
            {"role": "data_admin"}, {"roles": ["student", "data_admin"]}):
            response = http.post(prefix + "/probe/private/" + str(ours.id), headers=headers,
                json={"expected_version": ours.version, **extra})
            assert response.status_code == 422
            private_headers(response)
            assert str(other.user_id) not in response.text
        injected_query = http.get(prefix + "/probe/private/" + str(ours.id), params={"owner": str(other.user_id),
            "role": "data_admin"})
        assert injected_query.status_code == 422
        private_headers(injected_query)
        ignored_headers = http.get(prefix + "/probe/private/" + str(ours.id), headers=headers)
        assert ignored_headers.status_code == 200
    refreshed = harness.principal(actor)
    assert refreshed.user_id == actor.user_id and refreshed.roles == ("student",)
    assert harness.authorizer.require_owned(refreshed, "profile", ours.id).version == ours.version


@pytest.mark.parametrize("mounted", (False, True))
def test_anonymous_unsafe_probe_never_reaches_resource_or_side_effect(harness, mounted):
    actor = student(harness)
    resource = harness.owned(actor)
    with probe_http(harness, mounted=mounted) as (http, prefix):
        response = http.post(prefix + "/probe/private/" + str(resource.id),
            headers={"Origin": ORIGIN, "X-CSRF-Token": "a" * 43}, json={"expected_version": resource.version})
        assert response.status_code == 401
        private_headers(response)
    assert harness.authorizer.require_owned(harness.principal(actor), "profile", resource.id).version == resource.version


def test_runtime_schema_and_session_wire_do_not_expose_test_resources(harness):
    actor = student(harness)
    child = create_identity_v2_app(harness.service.runtime_settings, identity_service=harness.service)
    assert set(child.openapi()["paths"]) == {"/config", "/offerings", "/auth/login", "/auth/callback",
        "/auth/session", "/auth/csrf", "/auth/logout", "/privacy/notices/current", "/me/admission",
        "/me/age-declarations", "/me/consents", "/me/consents/{consent_id}",
        "/sharing/policy", "/access-grants", "/access-grants/{grant_id}", "/access-grants/{grant_id}/accept"}
    with TestClient(child, base_url=ORIGIN) as http:
        http.cookies.set(SESSION_COOKIE, actor.cookie.get_secret_value(), domain="app.test.invalid", path="/")
        response = http.get("/auth/session")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["private_business_available"] is False
        assert set(data) == {"authenticated", "user_id", "expires_at", "is_synthetic", "private_business_available"}
        assert http.get("/profiles").status_code == 404
