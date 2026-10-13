"""Own network guard; PostgreSQL fixtures fail if their required environment is absent."""

from datetime import datetime, timedelta, timezone
import os
import socket
from urllib.parse import urlsplit
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def isolate_auth_process_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("AUTH_", "OIDC_", "KEYCLOAK_", "IDENTITY_", "V2_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY",
        }:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def guarded(sock, address, original=original):
            # Isolated PostgreSQL and Windows asyncio's internal socketpair.
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("External connection forbidden in T05 auth tests")

        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo

    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("External DNS forbidden in T05 auth tests")

    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


class MutableClock:
    def __init__(self):
        self.instant = datetime.now(timezone.utc).replace(microsecond=0)

    def __call__(self):
        return self.instant

    def advance(self, seconds):
        self.instant += timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return MutableClock()


@pytest.fixture
def session_settings_factory():
    from cryptography.fernet import Fernet
    from services.api.app.auth.config import SessionAuthSettings
    from services.api.app.auth.schemas import AuthProviderSettings

    def make(**changes):
        provider = AuthProviderSettings(provider_mode="oidc_boundary", provider_id="T05_PINNED_KEYCLOAK",
            issuer="https://idp.test.invalid/realms/students", client_id="T05_TEST_CLIENT",
            client_secret="T05_SYNTHETIC_CLIENT_SECRET", callback_allowlist=("https://app.test.invalid/auth/callback",))
        values = {"provider": provider, "enabled": True, "redirect_uri": provider.callback_allowlist[0],
                  "context_encryption_key": Fernet.generate_key().decode("ascii"),
                  "login_ttl_seconds": 300, "session_ttl_seconds": 3600}
        values.update(changes)
        return SessionAuthSettings(**values)

    return make


@pytest.fixture
def session_settings(session_settings_factory):
    return session_settings_factory()


@pytest.fixture
def runtime():
    from services.api.app.settings import V2RuntimeSettings

    return V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
                             database_url=None, legacy_demo_mode=None, _env_file=None)


@pytest.fixture
def idp(session_settings, clock):
    from .fake_idp import FakeIdP

    return FakeIdP(session_settings, clock)


@pytest.fixture
def oidc_adapter(session_settings, runtime, idp):
    from services.api.app.auth.oidc import KeycloakOidcAdapter

    return KeycloakOidcAdapter(session_settings, runtime, transport=idp.transport)


@pytest.fixture
def pg_engine():
    from sqlalchemy import create_engine, inspect, text

    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T05 PostgreSQL check cannot run: TEST_POSTGRES_URL is absent", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/auth_t05_test":
        pytest.fail("T05 database must be the dedicated loopback auth_t05_test database", pytrace=False)
    schema = "auth_t05_" + uuid4().hex
    admin = create_engine(url, connect_args={"connect_timeout": 5})
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(url, connect_args={"options": "-csearch_path=" + schema, "connect_timeout": 5})
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


@pytest.fixture
def auth_store(pg_engine):
    from services.api.app.auth.store import AuthStore, migrate_auth

    migrate_auth(pg_engine)
    return AuthStore(pg_engine)


@pytest.fixture
def auth_service(session_settings, runtime, auth_store, oidc_adapter, clock):
    from services.api.app.auth.service import AuthService

    return AuthService(session_settings, runtime, auth_store, oidc_adapter, clock=clock)


@pytest.fixture
def account_factory(pg_engine, session_settings, clock):
    from sqlalchemy.orm import Session
    from services.api.app.auth.models import AuthIdentity, AuthUser

    def make(subject="T05_SYNTHETIC_STUDENT_A", *, issuer=None, status="active", is_synthetic=True):
        user_id = uuid4()
        with Session(pg_engine) as session, session.begin():
            session.add(AuthUser(id=user_id, status=status, is_synthetic=is_synthetic, created_at=clock()))
            session.flush()
            session.add(AuthIdentity(id=uuid4(), user_id=user_id, issuer=issuer or session_settings.provider.issuer,
                                     subject=subject, created_at=clock()))
        return user_id

    return make


@pytest.fixture
def active_account(account_factory):
    return account_factory()


@pytest.fixture
def client(auth_service, runtime):
    from fastapi.testclient import TestClient
    from services.api.app.api.identity import create_identity_v2_app

    with TestClient(create_identity_v2_app(runtime, identity_service=auth_service),
                    base_url="https://app.test.invalid", follow_redirects=False) as http:
        yield http
