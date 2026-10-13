"""Middleware must protect actual future routes even without route dependencies."""

import pytest

from .conftest import ORIGIN, SENSITIVE, private_response


@pytest.mark.postgres
@pytest.mark.parametrize("mounted", [False, True], ids=["standalone", "mounted"])
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_dynamic_write_route_is_protected_by_default(
    auth_service, runtime, idp, active_account, mounted, method,
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.api.app.api.identity import create_identity_v2_app

    child = create_identity_v2_app(runtime, identity_service=auth_service)
    effects = []

    def future_write():
        effects.append("executed")
        return {"accepted": True}

    child.add_api_route("/future/write", future_write, methods=[method])
    if mounted:
        parent = FastAPI()
        parent.mount("/v2", child)
        app, prefix = parent, "/v2"
    else:
        app, prefix = child, ""
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as http:
        started = http.get(prefix + "/auth/login")
        code, state = idp.issue_from_authorization(started.headers["location"])
        assert http.get(prefix + "/auth/callback", params={"code": code, "state": state}).status_code == 303
        token = http.get(prefix + "/auth/csrf").json()["data"]["csrf_token"]
        for path in ("/future/write", "/auth/logout/", "/does-not-exist"):
            response = http.request(method, prefix + path, headers={"Origin": ORIGIN}, content=SENSITIVE)
            assert response.status_code == 403
            private_response(response)
            assert SENSITIVE not in response.text
        assert effects == []
        valid = http.request(method, prefix + "/future/write", headers={"Origin": ORIGIN, "X-CSRF-Token": token})
        assert valid.status_code == 200 and effects == ["executed"]
        assert valid.headers["cache-control"] == "no-store"


@pytest.mark.postgres
def test_valid_csrf_duplicate_cookie_does_not_choose_one_identity(client, csrf_token, logged_in):
    from services.api.app.auth.router import SESSION_COOKIE

    response = client.post("/auth/logout", headers=[("Origin", ORIGIN), ("X-CSRF-Token", csrf_token),
        ("Cookie", SESSION_COOKIE + "=" + logged_in), ("Cookie", SESSION_COOKIE + "=" + logged_in)])
    assert response.status_code == 401
    private_response(response)
    assert client.get("/auth/session", headers={"Cookie": SESSION_COOKIE + "=" + logged_in}).status_code == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("path", ["/auth/logout", "/future/write", "/auth/logout/"])
def test_closed_profile_cannot_accept_any_unsafe_route(runtime, method, path):
    from fastapi.testclient import TestClient
    from services.api.app.api.identity import create_identity_v2_app

    with TestClient(create_identity_v2_app(runtime), base_url=ORIGIN) as http:
        response = http.request(method, path, headers={"Origin": ORIGIN, "X-CSRF-Token": SENSITIVE})
    assert response.status_code == 503
    private_response(response)
    assert SENSITIVE not in response.text


@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_verified_demo_credential_remains_rejected_before_new_write_guards(runtime, method):
    from fastapi.testclient import TestClient
    from services.api.app.api.identity import create_identity_v2_app

    with TestClient(create_identity_v2_app(runtime), base_url=ORIGIN) as http:
        response = http.request(method, "/does-not-exist", headers={"Authorization": "Bearer demo-alice-token"})
    assert response.status_code == 401
    private_response(response)


def test_get_cannot_trigger_logout(runtime):
    from fastapi.testclient import TestClient
    from services.api.app.api.identity import create_identity_v2_app

    with TestClient(create_identity_v2_app(runtime), base_url=ORIGIN) as http:
        response = http.get("/auth/logout")
    assert response.status_code == 405
