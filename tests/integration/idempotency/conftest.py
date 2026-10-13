"""T49 synthetic transaction probes in one dedicated PostgreSQL database."""

import os
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.auth.conftest import (clock, session_settings_factory,
    session_settings, runtime, idp, oidc_adapter)
from tests.security.privacy.conftest import (auth_store, auth_service, actor_factory,
    privacy_settings, privacy_service)
from tests.security.grants.conftest import admitted_actor_factory
from tests.integration.sources.conftest import administrator_factory


@pytest.fixture(autouse=True)
def isolated_idempotency_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_", "IDEMPOTENCY_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL", "STORAGE_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T49 forbids external connections")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T49 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T49_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T49 PostgreSQL check not executed: T49_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/idempotency_t49_test":
        pytest.fail("T49 requires the dedicated loopback idempotency_t49_test database", pytrace=False)
    schema = "idempotency_t49_" + uuid4().hex
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
def idempotency_store(auth_store, pg_engine):
    from services.api.app.idempotency.store import IdempotencyStore, migrate_idempotency
    migrate_idempotency(pg_engine)
    return IdempotencyStore(pg_engine)


@pytest.fixture
def idempotency_factory(auth_service, privacy_settings, idempotency_store):
    from services.api.app.idempotency.schemas import IdempotencyPolicy
    from services.api.app.idempotency.service import IdempotencyService
    from services.api.app.privacy.service import PrivacyService
    def make(*, identity=None, policy=None):
        identity = identity or auth_service
        return IdempotencyService(identity, PrivacyService(identity, privacy_settings), idempotency_store,
            policy or IdempotencyPolicy(enabled=True, ttl_seconds=86400))
    return make


@pytest.fixture
def idempotency_service(idempotency_factory):
    return idempotency_factory()


@pytest.fixture
def registry_probe(idempotency_service):
    """Only existing synthetic ownership metadata, never real profile/plan data."""
    from services.api.app.auth.authorization import Authorizer
    from services.api.app.idempotency.schemas import ResourceReceipt
    def make(kind="profile"):
        state = SimpleNamespace(calls=0, verified=0, created=[])
        authorizer = Authorizer(idempotency_service.auth_service)
        def perform(session, current):
            state.calls += 1
            resource = authorizer.register_owned(current, kind, session=session)
            state.created.append(resource.id)
            return ResourceReceipt(kind=kind, resource_id=resource.id, version=resource.version)
        def verify(session, current, receipt):
            state.verified += 1
            _, resource = authorizer.check_owned_in_transaction(session, current, kind,
                receipt.resource_id, "write")
            return resource.version == receipt.version and receipt.kind == kind
        state.perform, state.verify = perform, verify
        return state
    return make
