"""Reuse the signed offline IdP while isolating every T06 database schema."""

import os
import socket
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from tests.integration.auth.conftest import (
    account_factory, active_account, auth_service, auth_store, client, clock, idp,
    oidc_adapter, runtime, session_settings, session_settings_factory,
)


@pytest.fixture(autouse=True)
def isolate_t06_process(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("AUTH_", "OIDC_", "KEYCLOAK_", "IDENTITY_", "V2_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY",
        }:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def prohibit_t06_external_network(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T06 tests prohibit external sockets")

        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo

    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T06 tests prohibit external DNS")

    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    from sqlalchemy import create_engine, inspect, text

    url = os.getenv("T06_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T06 PostgreSQL check not executed: T06_TEST_POSTGRES_URL is absent", pytrace=False)
    parsed = urlsplit(url)
    if (parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1"
        or parsed.path != "/auth_t06_test"):
        pytest.fail("T06 tests require the new dedicated loopback auth_t06_test database", pytrace=False)
    schema = "auth_t06_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(url, hide_parameters=True,
            connect_args={"options": "-csearch_path=" + schema, "connect_timeout": 5})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
        assert inspect(engine).get_table_names() == []
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def login_cookie(http, fake_idp, subject="T05_SYNTHETIC_STUDENT_A"):
    from services.api.app.auth.router import SESSION_COOKIE

    started = http.get("/auth/login")
    assert started.status_code == 302
    code, state = fake_idp.issue_from_authorization(started.headers["location"], subject)
    completed = http.get("/auth/callback", params={"code": code, "state": state})
    assert completed.status_code == 303
    cookie = http.cookies.get(SESSION_COOKIE)
    assert cookie is not None
    return cookie


@pytest.fixture
def logged_in(client, idp, active_account):
    return login_cookie(client, idp)


@pytest.fixture
def csrf_token(client, logged_in):
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return response.json()["data"]["csrf_token"]


def private_response(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    if response.content:
        body = response.json()
        identifier = body.get("meta", body.get("error", {}))["request_id"]
        assert response.headers["x-request-id"] == identifier


ORIGIN = "https://app.test.invalid"
SENSITIVE = "T06_SYNTHETIC_SENSITIVE_INPUT"
