"""Actual auth HTTP routes, independent signed IdP, and isolated PostgreSQL."""

from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session


pytestmark = pytest.mark.postgres
LOGIN_COOKIE = "__Host-admissions-login"
SESSION_COOKIE = "__Host-admissions-session"
SENSITIVE = "T05_SENSITIVE_CALLBACK_INPUT"


def start(client, idp, subject="T05_SYNTHETIC_STUDENT_A"):
    response = client.get("/auth/login")
    assert response.status_code == 302, response.text
    code, state = idp.issue_from_authorization(response.headers["location"], subject)
    return response, code, state, client.cookies.get(LOGIN_COOKIE)


def finish(client, code, state, **changes):
    return client.get("/auth/callback", params={"code": code, "state": state, **changes})


def assert_private_headers(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers.get("x-request-id")
    if response.headers.get("content-type", "").startswith("application/json"):
        body = response.json()
        identifier = body.get("meta", body.get("error"))["request_id"]
        assert identifier == response.headers["x-request-id"]


def assert_secure_cookie(response, name):
    parsed = SimpleCookie()
    for value in response.headers.get_list("set-cookie"):
        parsed.load(value)
    morsel = parsed[name]
    assert morsel["secure"] and morsel["httponly"]
    assert morsel["samesite"].lower() == "lax" and morsel["path"] == "/" and not morsel["domain"]
    return morsel.value


def test_real_signed_login_cookie_and_session_only_disclose_minimal_identity(
    client, idp, active_account, pg_engine,
):
    from services.api.app.auth.models import AuthSession, LoginTransaction

    login, code, state, binding = start(client, idp)
    assert_secure_cookie(login, LOGIN_COOKIE)
    assert_private_headers(login)
    completed = finish(client, code, state)
    assert completed.status_code == 303 and completed.headers["location"] == "/"
    session_cookie = assert_secure_cookie(completed, SESSION_COOKIE)
    assert_private_headers(completed)
    assert LOGIN_COOKIE not in client.cookies
    response = client.get("/auth/session")
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "authenticated": True, "user_id": str(active_account), "expires_at": response.json()["data"]["expires_at"],
        "is_synthetic": True, "private_business_available": False,
    }
    assert_private_headers(response)
    visible = completed.text + response.text + str(response.headers)
    for secret in (code, state, binding, session_cookie, idp.last_token, "T05_SENSITIVE_ACCESS_TOKEN"):
        assert secret not in visible
    with Session(pg_engine) as session:
        row = session.scalar(select(LoginTransaction))
        assert row.consumed_at is not None and row.encrypted_context is None
        stored = session.scalar(select(AuthSession))
        assert stored.user_id == active_account and len(stored.session_digest) == 64
        assert stored.session_digest != session_cookie


def test_transaction_context_is_encrypted_and_raw_proofs_not_stored(client, idp, pg_engine):
    from services.api.app.auth.models import LoginTransaction

    login, code, state, binding = start(client, idp)
    query = parse_qs(urlsplit(login.headers["location"]).query)
    with Session(pg_engine) as session:
        row = session.scalar(select(LoginTransaction))
        serialized = repr({column.name: getattr(row, column.name) for column in LoginTransaction.__table__.columns})
        assert row.encrypted_context and row.consumed_at is None
        for raw in (state, binding, code, query["nonce"][0]):
            assert raw not in serialized


def test_missing_or_wrong_browser_binding_cannot_burn_legitimate_transaction(client, idp, active_account):
    _, code, state, binding = start(client, idp)
    client.cookies.clear()
    assert finish(client, code, state).status_code == 401
    client.cookies.set(LOGIN_COOKIE, "x" * 43, domain="app.test.invalid", path="/")
    assert finish(client, code, state).status_code == 401
    assert idp.requests == []
    client.cookies.clear()
    client.cookies.set(LOGIN_COOKIE, binding, domain="app.test.invalid", path="/")
    assert finish(client, code, state).status_code == 303


def test_consumed_state_is_not_reusable_even_with_original_binding(client, idp, active_account):
    _, code, state, binding = start(client, idp)
    assert finish(client, code, state).status_code == 303
    count = len(idp.requests)
    client.cookies.set(LOGIN_COOKIE, binding, domain="app.test.invalid", path="/")
    replay = finish(client, code, state)
    assert replay.status_code == 401 and len(idp.requests) == count
    assert_private_headers(replay)


@pytest.mark.parametrize("failure", ["signature", "nonce", "timeout", "invalid_code", "unregistered"])
def test_matched_failed_callback_remains_consumed_and_creates_no_session(
    client, idp, active_account, pg_engine, failure,
):
    from services.api.app.auth.models import AuthSession, LoginTransaction

    _, code, state, binding = start(client, idp, "UNKNOWN_SUBJECT" if failure == "unregistered" else "T05_SYNTHETIC_STUDENT_A")
    if failure == "signature":
        idp.wrong_signature = True
    elif failure == "nonce":
        idp.claim_changes["nonce"] = SENSITIVE
    elif failure == "timeout":
        idp.timeout = True
    elif failure == "invalid_code":
        code = SENSITIVE
    response = finish(client, code, state)
    expected = {"signature": 401, "nonce": 401, "timeout": 503, "invalid_code": 401, "unregistered": 403}[failure]
    assert response.status_code == expected, response.text
    assert SENSITIVE not in response.text
    assert_private_headers(response)
    count = len(idp.requests)
    client.cookies.set(LOGIN_COOKIE, binding, domain="app.test.invalid", path="/")
    assert finish(client, code, state).status_code == 401
    assert len(idp.requests) == count
    with Session(pg_engine) as session:
        assert session.scalar(select(LoginTransaction)).consumed_at is not None
        assert session.scalar(select(LoginTransaction)).encrypted_context is None
        assert session.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_idp_error_consumes_transaction_without_token_exchange(client, idp, active_account):
    _, code, state, binding = start(client, idp)
    response = client.get("/auth/callback", params={"error": SENSITIVE, "state": state})
    assert response.status_code == 401 and SENSITIVE not in response.text
    assert_private_headers(response)
    assert idp.requests == []
    client.cookies.set(LOGIN_COOKIE, binding, domain="app.test.invalid", path="/")
    assert finish(client, code, state).status_code == 401
    assert idp.requests == []


@pytest.mark.parametrize("parameters", [
    [("state", "x" * 43)], [("code", "c"), ("error", "e"), ("state", "x" * 43)],
    [("code", "c"), ("code", "d"), ("state", "x" * 43)],
    [("code", "c"), ("state", "x" * 43), ("state", "y" * 43)],
    [("code", "c"), ("state", "x" * 43), ("issuer", SENSITIVE)],
    [("code", "c"), ("state", "x" * 43), ("nonce", SENSITIVE)],
    [("code", "c"), ("state", "x" * 43), ("code_verifier", SENSITIVE)],
    [("code", "c"), ("state", "x" * 43), ("jku", "https://attacker.invalid/keys")],
    [("code", "c"), ("state", "x" * 43), ("return_to", "https://attacker.invalid/")],
])
def test_callback_rejects_ambiguous_and_extra_parameters_without_echo(client, idp, parameters):
    response = client.get("/auth/callback", params=parameters)
    assert response.status_code == 422, response.text
    assert SENSITIVE not in response.text
    assert_private_headers(response)
    assert idp.requests == []


def test_wrong_issuer_and_duplicate_binding_cookies_reject_before_idp_io(client, idp, active_account):
    _, code, state, binding = start(client, idp)
    assert finish(client, code, state, iss="https://attacker.invalid/").status_code == 401
    response = client.get("/auth/callback", params={"code": code, "state": state},
                          headers={"Cookie": f"{LOGIN_COOKIE}={binding}; {LOGIN_COOKIE}={binding}"})
    assert response.status_code == 401
    assert idp.requests == []
    assert finish(client, code, state, iss=idp.settings.provider.issuer).status_code == 303


def test_login_and_session_do_not_accept_return_url_owner_or_role_parameters(client, idp):
    for path in ("/auth/login", "/auth/session"):
        for name in ("return_to", "owner_id", "role", "issuer"):
            response = client.get(path, params={name: SENSITIVE})
            assert response.status_code == 422 and SENSITIVE not in response.text
            assert_private_headers(response)
    assert idp.requests == []


def test_login_and_session_exact_expiry_are_enforced(client, idp, active_account, clock, session_settings):
    _, code, state, _ = start(client, idp)
    clock.advance(session_settings.login_ttl_seconds)
    assert finish(client, code, state).status_code == 401 and idp.requests == []
    _, code, state, _ = start(client, idp)
    assert finish(client, code, state).status_code == 303
    clock.advance(session_settings.session_ttl_seconds - 1)
    assert client.get("/auth/session").status_code == 200
    clock.advance(1)
    expired = client.get("/auth/session")
    assert expired.status_code == 401
    assert_private_headers(expired)


def test_login_rotates_real_previous_session_and_rejects_fixed_attacker_cookie(client, idp, active_account):
    client.cookies.set(SESSION_COOKIE, "T05_ATTACKER_FIXED_" + "x" * 32, domain="app.test.invalid", path="/")
    assert client.get("/auth/session").status_code == 401
    _, code, state, _ = start(client, idp)
    first = finish(client, code, state)
    old = assert_secure_cookie(first, SESSION_COOKIE)
    _, code, state, _ = start(client, idp)
    second = finish(client, code, state)
    new = assert_secure_cookie(second, SESSION_COOKIE)
    assert new != old and new != "T05_ATTACKER_FIXED_" + "x" * 32
    assert client.get("/auth/session").status_code == 200
    assert client.get("/auth/session", headers={"Cookie": SESSION_COOKIE + "=" + old}).status_code == 401


def test_account_disabled_after_login_invalidates_read_without_accepting_idp_roles(
    client, idp, active_account, pg_engine,
):
    from services.api.app.auth.models import AuthUser

    idp.claim_changes.update(email="someone@invalid.test", roles=["data_admin"], realm_access={"roles": ["admin"]})
    _, code, state, _ = start(client, idp)
    assert finish(client, code, state).status_code == 303
    response = client.get("/auth/session")
    assert not {"roles", "email", "owner_id", "issuer", "subject"} & set(response.json()["data"])
    with Session(pg_engine) as session, session.begin():
        session.get(AuthUser, active_account).status = "disabled"
    assert client.get("/auth/session").status_code == 401


def test_subject_case_and_issuer_are_not_merged_by_email(client, idp, account_factory, pg_engine):
    from services.api.app.auth.models import AuthUser

    account_factory("student")
    account_factory("Student", issuer="https://other.test.invalid/realms/students")
    idp.claim_changes["email"] = "same@invalid.test"
    _, code, state, _ = start(client, idp, "Student")
    response = finish(client, code, state)
    assert response.status_code == 403
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuthUser)) == 2


def test_authentication_does_not_open_registration_or_private_business(client):
    for path in ("/auth/register", "/profiles", "/plans", "/admin", "/v1/profiles"):
        assert client.get(path).status_code == 404
        # T06 centrally denies every unauthenticated write, even to a missing
        # route. This does not provision registration or private business.
        assert client.post(path).status_code == 401
    assert client.get("/auth/logout").status_code == 405
    assert client.post("/auth/logout").status_code == 401


def test_duplicate_session_cookie_headers_do_not_select_a_valid_identity(client, idp, active_account):
    _, code, state, _ = start(client, idp)
    response = finish(client, code, state)
    cookie = assert_secure_cookie(response, SESSION_COOKIE)
    duplicated = client.get("/auth/session", headers=[("Cookie", SESSION_COOKIE + "=" + cookie),
        ("Cookie", SESSION_COOKIE + "=" + "x" * 43)])
    assert duplicated.status_code == 401
    assert_private_headers(duplicated)


def test_unexpected_provider_failure_is_safe_and_keeps_state_consumed(
    client, idp, active_account, oidc_adapter, monkeypatch, pg_engine,
):
    from services.api.app.auth.models import AuthSession, LoginTransaction

    _, code, state, _ = start(client, idp)

    def fail_unexpectedly(*args, **kwargs):
        raise RuntimeError(SENSITIVE)

    monkeypatch.setattr(oidc_adapter, "exchange_code", fail_unexpectedly)
    response = finish(client, code, state)
    assert response.status_code == 500 and SENSITIVE not in response.text
    assert_private_headers(response)
    with Session(pg_engine) as session:
        assert session.scalar(select(LoginTransaction)).consumed_at is not None
        assert session.scalar(select(func.count()).select_from(AuthSession)) == 0
