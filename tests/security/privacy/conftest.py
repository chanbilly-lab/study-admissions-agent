"""T08 synthetic fixtures on one required isolated loopback PostgreSQL database."""

from dataclasses import dataclass, field
from datetime import timedelta
import os
import secrets
import socket
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from tests.integration.auth.conftest import clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter
from services.api.app.auth.models import AuthSession, AuthUser
from services.api.app.auth.service import AuthService, digest_secret
from services.api.app.auth.store import AuthStore, migrate_auth
from services.api.app.privacy.config import DRAFT_NOTICE_TEXT, PrivacySettings
from services.api.app.privacy.models import PrivacyNoticeVersion
from services.api.app.privacy.policy import hash_text
from services.api.app.privacy.service import PrivacyService


@pytest.fixture(autouse=True)
def privacy_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("IDENTITY_", "V2_", "PRIVACY_")) or name in {"DEMO_MODE", "OPENAI_API_KEY", "LLM_API_KEY"}:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T08 forbids external sockets")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def local_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T08 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", local_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T08_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T08 PostgreSQL check not run: T08_TEST_POSTGRES_URL absent", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/privacy_t08_test":
        pytest.fail("T08 requires the dedicated loopback privacy_t08_test database", pytrace=False)
    schema = "privacy_t08_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine, created = None, False
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


@pytest.fixture
def auth_store(pg_engine):
    migrate_auth(pg_engine)
    return AuthStore(pg_engine)


@pytest.fixture
def auth_service(session_settings, runtime, auth_store, oidc_adapter, clock):
    return AuthService(session_settings, runtime, auth_store, oidc_adapter, clock=clock)


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    session_id: UUID
    cookie: SecretStr = field(repr=False)


@pytest.fixture
def actor_factory(auth_service, clock):
    def make(*, is_synthetic=True, role="student", lifetime=3600, status="active"):
        actor = Actor(uuid4(), uuid4(), SecretStr(secrets.token_urlsafe(32)))
        with Session(auth_service.store.engine) as session, session.begin():
            session.add(AuthUser(id=actor.user_id, status=status, is_synthetic=is_synthetic, created_at=clock()))
            session.flush()
            session.add(AuthSession(id=actor.session_id, user_id=actor.user_id,
                session_digest=digest_secret(actor.cookie, "session"), created_at=clock(),
                expires_at=clock() + timedelta(seconds=lifetime), revoked_at=None))
        if role is not None:
            auth_service.store.assign_role(actor.user_id, role, now=clock())
        return actor
    return make


@pytest.fixture
def principal_factory(auth_service, actor_factory):
    def make(**kwargs):
        return auth_service.get_principal(actor_factory(**kwargs).cookie)
    return make


@pytest.fixture
def privacy_settings(auth_store, clock):
    settings = PrivacySettings(fixture_mode=True, notice_id=uuid4(), controller_reference="T08_SYNTHETIC_CONTROLLER",
        age_assurance_method="adult_self_declaration", declaration_validity_seconds=7200)
    with Session(auth_store.engine) as session, session.begin():
        session.add(PrivacyNoticeVersion(id=settings.notice_id, version="T08_SYNTHETIC_NOTICE_v1",
            policy_version=settings.policy_version, text=DRAFT_NOTICE_TEXT, text_sha256=hash_text(DRAFT_NOTICE_TEXT),
            controller_reference=settings.controller_reference, review_status="test_reviewed",
            reviewed_at=clock(), is_synthetic=True))
    return settings


@pytest.fixture
def privacy_service(auth_service, privacy_settings):
    return PrivacyService(auth_service, privacy_settings)


@pytest.fixture
def client(auth_service, privacy_settings, runtime):
    from fastapi.testclient import TestClient
    from services.api.app.api.identity import create_identity_v2_app
    with TestClient(create_identity_v2_app(runtime, identity_service=auth_service, privacy_settings=privacy_settings),
                    base_url="https://app.test.invalid", follow_redirects=False) as http:
        yield http
