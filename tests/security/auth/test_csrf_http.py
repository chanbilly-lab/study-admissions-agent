"""Actual HTTP acceptance for session-bound CSRF and logout."""

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from .conftest import ORIGIN, SENSITIVE, login_cookie, private_response


pytestmark = pytest.mark.postgres


def write_headers(token, **extra):
    return {"Origin": ORIGIN, "X-CSRF-Token": token, **extra}


def session_rows(engine):
    from services.api.app.auth.models import AuthSession

    with Session(engine) as database:
        return [dict(row) for row in database.execute(select(AuthSession.__table__)).mappings()]


def test_csrf_is_stable_encrypted_session_bound_and_does_not_extend_expiry(
    client, logged_in, auth_service, pg_engine, clock,
):
    from cryptography.fernet import Fernet

    original = client.get("/auth/session").json()["data"]
    first = client.get("/auth/csrf")
    private_response(first)
    assert set(first.json()["data"]) == {"csrf_token", "expires_at"}
    token = first.json()["data"]["csrf_token"]
    assert len(token) >= 32 and token != logged_in
    assert first.json()["data"]["expires_at"] == original["expires_at"]
    clock.advance(120)
    second = client.get("/auth/csrf")
    assert second.json()["data"] == first.json()["data"]
    assert client.get("/auth/session").json()["data"] == original
    row = session_rows(pg_engine)[0]
    assert len(row["csrf_digest"]) == 64 and token not in str(row)
    cipher = Fernet(auth_service.settings.context_encryption_key.get_secret_value().encode("ascii"))
    assert cipher.decrypt(row["csrf_encrypted_token"].encode("ascii")).decode("utf-8") == token
    assert datetime.fromisoformat(first.json()["data"]["expires_at"].replace("Z", "+00:00")).tzinfo is not None


@pytest.mark.parametrize("headers", [
    [("Origin", ORIGIN)],
    [("Origin", ORIGIN), ("X-CSRF-Token", SENSITIVE)],
    [("Origin", ORIGIN), ("X-CSRF-Token", "")],
    [("Origin", ORIGIN), ("X-CSRF-Token", "duplicate"), ("x-csrf-token", "duplicate")],
], ids=["missing", "wrong", "empty", "duplicate"])
def test_invalid_csrf_cannot_revoke_a_valid_session(client, logged_in, csrf_token, pg_engine, headers):
    before = session_rows(pg_engine)
    response = client.post("/auth/logout", headers=headers)
    assert response.status_code == 403
    private_response(response)
    assert SENSITIVE not in response.text
    assert session_rows(pg_engine) == before
    assert client.get("/auth/session").status_code == 200


@pytest.mark.parametrize("origin", [
    None, "null", "http://app.test.invalid", "https://app.test.invalid:444",
    "https://app.test.invalid.attacker.invalid", "https://child.app.test.invalid",
    "https://app.test.invalid/path", "https://app.test.invalid?x=1", "https://app.test.invalid#fragment",
    "https://user@app.test.invalid", ORIGIN + ", " + ORIGIN,
], ids=["missing", "null", "scheme", "port", "suffix", "subdomain", "path", "query", "fragment", "userinfo", "combined"])
def test_origin_must_match_fixed_server_origin(client, csrf_token, pg_engine, origin):
    before = session_rows(pg_engine)
    headers = {"X-CSRF-Token": csrf_token}
    if origin is not None:
        headers["Origin"] = origin
    response = client.post("/auth/logout", headers=headers)
    assert response.status_code == 403
    private_response(response)
    assert session_rows(pg_engine) == before
    assert client.get("/auth/session").status_code == 200


def test_duplicate_origin_and_forged_proxy_trust_are_rejected(client, csrf_token):
    duplicated = client.post("/auth/logout", headers=[("Origin", ORIGIN), ("origin", ORIGIN),
        ("X-CSRF-Token", csrf_token)])
    assert duplicated.status_code == 403
    forged = client.post("/auth/logout", headers=write_headers(csrf_token,
        Origin="https://attacker.invalid", Host="attacker.invalid",
        Forwarded="proto=https;host=attacker.invalid", **{"X-Forwarded-Host": "attacker.invalid"}))
    assert forged.status_code == 403
    assert client.get("/auth/session").status_code == 200


@pytest.mark.parametrize("placement", ["query", "body", "cookie"])
def test_token_in_other_places_does_not_replace_required_header(client, csrf_token, placement):
    kwargs = {"headers": {"Origin": ORIGIN}}
    if placement == "query":
        kwargs["params"] = {"csrf_token": csrf_token}
    elif placement == "body":
        kwargs["json"] = {"csrf_token": csrf_token}
    else:
        kwargs["headers"]["Cookie"] = "; ".join(f"{cookie.name}={cookie.value}" for cookie in client.cookies.jar)
        kwargs["headers"]["Cookie"] += "; csrf_token=" + csrf_token
    response = client.post("/auth/logout", **kwargs)
    assert response.status_code == 403
    assert client.get("/auth/session").status_code == 200


@pytest.mark.parametrize("payload", ["query", "json", "plain"])
def test_logout_has_no_business_input(client, csrf_token, payload):
    kwargs = {"headers": write_headers(csrf_token)}
    if payload == "query":
        kwargs["params"] = {"owner": SENSITIVE}
    elif payload == "json":
        kwargs["json"] = {"owner": SENSITIVE}
    else:
        kwargs["content"] = SENSITIVE
    response = client.post("/auth/logout", **kwargs)
    assert response.status_code == 422
    private_response(response)
    assert SENSITIVE not in response.text
    assert client.get("/auth/session").status_code == 200


def test_logout_revokes_on_server_clears_secure_cookies_and_repeated_request_is_401(
    client, logged_in, csrf_token, pg_engine,
):
    from services.api.app.auth.router import LOGIN_COOKIE, SESSION_COOKIE

    response = client.post("/auth/logout", headers=write_headers(csrf_token))
    assert response.status_code == 200 and response.json()["data"] == {"logged_out": True}
    private_response(response)
    cookies = response.headers.get_list("set-cookie")
    for name in (LOGIN_COOKIE, SESSION_COOKIE):
        deletion = next(value for value in cookies if value.startswith(name + "="))
        assert "Max-Age=0" in deletion and "Secure" in deletion and "HttpOnly" in deletion
        assert "Path=/" in deletion and "SameSite=lax" in deletion and "Domain=" not in deletion
    before = session_rows(pg_engine)
    assert len(before) == 1 and before[0]["revoked_at"] is not None
    assert client.get("/auth/session").status_code == 401
    repeated = client.post("/auth/logout", headers=write_headers(csrf_token,
        Cookie=SESSION_COOKIE + "=" + logged_in))
    assert repeated.status_code == 401
    private_response(repeated)
    assert session_rows(pg_engine) == before


def test_other_session_and_other_account_tokens_cannot_logout_current_session(
    client, csrf_token, auth_service, runtime, idp, account_factory,
):
    from fastapi.testclient import TestClient
    from services.api.app.api.identity import create_identity_v2_app

    account_factory("T06_SYNTHETIC_BOB")
    with TestClient(create_identity_v2_app(runtime, identity_service=auth_service),
                    base_url=ORIGIN, follow_redirects=False) as other:
        login_cookie(other, idp)
        other_token = other.get("/auth/csrf").json()["data"]["csrf_token"]
        assert other_token != csrf_token
        assert client.post("/auth/logout", headers=write_headers(other_token)).status_code == 403
        login_cookie(other, idp, "T06_SYNTHETIC_BOB")
        bob_token = other.get("/auth/csrf").json()["data"]["csrf_token"]
        assert client.post("/auth/logout", headers=write_headers(bob_token)).status_code == 403
        assert client.post("/auth/logout", headers=write_headers(csrf_token)).status_code == 200
        assert other.get("/auth/session").status_code == 200


@pytest.mark.parametrize("state", ["expired", "disabled", "revoked"])
def test_expired_disabled_or_revoked_sessions_cannot_read_csrf_or_write(
    client, logged_in, csrf_token, pg_engine, clock, session_settings, active_account, state,
):
    from services.api.app.auth.models import AuthSession, AuthUser
    from services.api.app.auth.router import SESSION_COOKIE

    if state == "expired":
        clock.advance(session_settings.session_ttl_seconds)
    else:
        with Session(pg_engine) as database, database.begin():
            if state == "disabled":
                database.get(AuthUser, active_account).status = "disabled"
            else:
                database.scalar(select(AuthSession)).revoked_at = clock()
    headers = write_headers(csrf_token, Cookie=SESSION_COOKIE + "=" + logged_in)
    assert client.get("/auth/csrf", headers={"Cookie": headers["Cookie"]}).status_code == 401
    response = client.post("/auth/logout", headers=headers)
    assert response.status_code == 401
    assert any("Max-Age=0" in value for value in response.headers.get_list("set-cookie"))
    private_response(response)


@pytest.mark.parametrize("path", ["/auth/csrf?owner=unsafe", "/auth/csrf?x=1&x=2"])
def test_csrf_read_rejects_query_and_never_leaks_session_cookie(client, logged_in, path):
    response = client.get(path)
    assert response.status_code == 422
    assert logged_in not in response.text
    private_response(response)
