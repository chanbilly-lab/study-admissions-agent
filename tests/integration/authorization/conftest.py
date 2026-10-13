"""Explicit synthetic SQLite substitute; no production data or external I/O."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import os
import secrets
import socket
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from services.api.app.auth.config import SessionAuthSettings
from services.api.app.auth.models import AuthSession, AuthUser
from services.api.app.auth.schemas import AuthProviderSettings
from services.api.app.auth.service import AuthService, digest_secret
from services.api.app.auth.store import AuthStore, migrate_auth
from services.api.app.settings import V2RuntimeSettings


ORIGIN = "https://app.test.invalid"


class UnusedProvider:
    def prepare_authorization(self, context):
        raise AssertionError("T07 authorization checks do not perform login")

    def exchange_code(self, code, context, *, now):
        raise AssertionError("T07 authorization checks do not exchange OIDC tokens")


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    session_id: UUID
    cookie: SecretStr = field(repr=False)


@dataclass
class Harness:
    service: AuthService
    engine: object
    clock: list[datetime]
    authorizer: object

    def account(self, *, status="active", is_synthetic=True, lifetime=3600, proof=None):
        actor = Actor(uuid4(), uuid4(), SecretStr(secrets.token_urlsafe(32)))
        now = self.clock[0]
        values = proof or {}
        with Session(self.engine) as db, db.begin():
            db.add(AuthUser(id=actor.user_id, status=status, is_synthetic=is_synthetic, created_at=now))
            db.flush()
            db.add(AuthSession(id=actor.session_id, user_id=actor.user_id,
                session_digest=digest_secret(actor.cookie, "session"), created_at=now,
                expires_at=now + timedelta(seconds=lifetime), revoked_at=None, **values))
        return actor

    def principal(self, actor):
        return self.service.get_principal(actor.cookie)

    def role(self, actor, role="student", *, expires_at=None):
        self.service.store.assign_role(actor.user_id, role, now=self.clock[0], expires_at=expires_at)

    def owned(self, actor, kind="profile", *, parent_id=None, resource_id=None):
        if kind in {"attachment", "export", "job"} and parent_id is None:
            parent_id = self.owned(actor, "profile").id
        return self.authorizer.register_owned(self.principal(actor), kind,
            resource_id=resource_id, parent_id=parent_id)


@pytest.fixture(autouse=True)
def isolate_authorization_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("AUTH_", "OIDC_", "KEYCLOAK_", "IDENTITY_", "V2_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY",
        }:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def prohibit_external_authorization_io(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T07 authorization tests prohibit external sockets")

        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo

    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T07 authorization tests prohibit external DNS")

    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def harness():
    from services.api.app.auth.authorization import Authorizer

    engine = create_engine("sqlite+pysqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False}, hide_parameters=True)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    migrate_auth(engine)
    provider = AuthProviderSettings(provider_mode="oidc_boundary", provider_id="T07_SYNTHETIC_PROVIDER",
        issuer="https://idp.test.invalid/realms/students", client_id="T07_SYNTHETIC_STUDENT_CLIENT",
        callback_allowlist=(ORIGIN + "/v2/auth/callback",), client_secret="T07_SYNTHETIC_SECRET")
    settings = SessionAuthSettings(enabled=True, provider=provider,
        redirect_uri=provider.callback_allowlist[0], context_encryption_key=Fernet.generate_key().decode("ascii"))
    runtime = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    clock = [datetime.now(timezone.utc).replace(microsecond=0)]
    service = AuthService(settings, runtime, AuthStore(engine), UnusedProvider(), clock=lambda: clock[0])
    try:
        yield Harness(service, engine, clock, Authorizer(service))
    finally:
        engine.dispose()


def rejected(call, status, code=None):
    from services.api.app.auth.authorization import AuthorizationError
    from services.api.app.auth.config import AuthFlowError

    with pytest.raises((AuthorizationError, AuthFlowError)) as error:
        call()
    assert error.value.status_code == status
    if code is not None:
        assert error.value.code == code
    return error.value
