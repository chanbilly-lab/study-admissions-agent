"""Dedicated T07 schemas; required PostgreSQL checks never silently skip."""

import os
import socket
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from tests.integration.auth.conftest import (
    account_factory, auth_service, auth_store, clock, idp, oidc_adapter, runtime,
    session_settings, session_settings_factory,
)


@pytest.fixture(autouse=True)
def isolate_t07_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("AUTH_", "OIDC_", "KEYCLOAK_", "IDENTITY_", "V2_")) or name in {
            "DEMO_MODE", "OPENAI_API_KEY", "LLM_API_KEY",
        }:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def prohibit_external_t07_network(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T07 forbids external sockets")

        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo

    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T07 forbids external DNS")

    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    from sqlalchemy import create_engine, inspect, text

    url = os.getenv("T07_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T07 PostgreSQL check unexecuted: T07_TEST_POSTGRES_URL absent", pytrace=False)
    parsed = urlsplit(url)
    if (parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1"
            or parsed.path != "/auth_t07_test" or parsed.query or parsed.fragment):
        pytest.fail("T07 requires its dedicated loopback auth_t07_test database", pytrace=False)
    schema = "auth_t07_" + uuid4().hex
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
            assert connection.scalar(text("SELECT current_database()")) == "auth_t07_test"
        assert inspect(engine).get_table_names() == []
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def authorizer(auth_service):
    from services.api.app.auth.authorization import Authorizer

    return Authorizer(auth_service)


@pytest.fixture
def principal_factory(auth_service, auth_store, account_factory, idp, clock):
    """Actual RSA-signed offline OIDC login, followed by server role lookup."""
    def make(*, roles=("student",), subject=None):
        subject = subject or "T07_SYNTHETIC_" + uuid4().hex
        user_id = account_factory(subject)
        for role in roles:
            auth_store.assign_role(user_id, role, now=clock())
        started = auth_service.start_login()
        code, state = idp.issue_from_authorization(started.authorization_url.get_secret_value(), subject)
        established = auth_service.complete_login(
            code=code, state=state, browser_binding=started.browser_binding,
        )
        return auth_service.get_principal(established.session_cookie), established.session_cookie
    return make


@pytest.fixture
def student(principal_factory):
    return principal_factory()[0]


@pytest.fixture
def other_student(principal_factory):
    return principal_factory()[0]


@pytest.fixture
def owned_resources(authorizer, student, other_student):
    records = {}
    for label, actor in (("own", student), ("foreign", other_student)):
        profile = authorizer.register_owned(actor, "profile")
        records[label] = {
            "profile": profile,
            "plan": authorizer.register_owned(actor, "plan"),
            **{kind: authorizer.register_owned(actor, kind, parent_id=profile.id)
               for kind in ("attachment", "export", "job")},
        }
    return records
