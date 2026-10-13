"""Required isolated PostgreSQL fixtures for synthetic T23 profile acceptance."""

import os
import socket
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.idempotency.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    admitted_actor_factory, idempotency_store, idempotency_factory,
)


@pytest.fixture(autouse=True)
def isolated_profiles_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_",
                            "PROFILES_", "IDEMPOTENCY_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T23 forbids external connections")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def local_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T23 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", local_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T23_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T23 PostgreSQL check not executed: T23_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if (parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1"
            or parsed.path != "/study_t23_20261003"):
        pytest.fail("T23 requires its dedicated loopback study_t23_20261003 database", pytrace=False)
    schema = "profiles_t23_" + uuid4().hex
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


def snapshot_payload():
    """Independent explicit self-declared input, not verified admissions facts."""
    missing = {"status": "missing", "value": None, "scale": None, "unit": None}
    return {
        "study_level": "bachelor", "entry_year": 2027,
        "residence_region": {"status": "known", "value": "hk"},
        "course_system": {"status": "known", "value": "gaokao"},
        "applicant_category": {"status": "known", "value": "cn_mainland"},
        "exam_province": {"status": "known", "value": "zhejiang"},
        "pathway": {"status": "known", "value": "gaokao"},
        "subjects": ["math", "physics"],
        "assessments": {
            "gaokao_total": {
                "achieved": {"status": "provided", "value": "625.25", "scale": "750", "unit": "points"},
                "predicted": {"status": "provided", "value": "700.000001", "scale": "750", "unit": "points"},
            },
            "math": {"achieved": missing.copy(), "predicted": {
                "status": "provided", "value": "0", "scale": "150", "unit": "points"}},
            "ielts_overall": {"achieved": {
                "status": "pending", "value": None, "scale": None, "unit": None}, "predicted": missing.copy()},
        },
        "weekly_hours": None, "preferences": None,
    }


@pytest.fixture
def create_input():
    from services.api.app.profiles.schemas import CreateInput
    return CreateInput(profile=snapshot_payload(), confirmed=True)


@pytest.fixture
def idempotency_service(auth_service, privacy_service, idempotency_store):
    from services.api.app.idempotency.schemas import IdempotencyPolicy
    from services.api.app.idempotency.service import IdempotencyService
    return IdempotencyService(auth_service, privacy_service, idempotency_store,
        IdempotencyPolicy(enabled=True, ttl_seconds=86400))


@pytest.fixture
def profiles_store(idempotency_store, pg_engine):
    from services.api.app.profiles.store import ProfilesStore, migrate_profiles
    migrate_profiles(pg_engine)
    return ProfilesStore(pg_engine)


@pytest.fixture
def profile_factory(auth_service, privacy_service, idempotency_service, profiles_store):
    from services.api.app.profiles.schemas import ProfilePolicy
    from services.api.app.profiles.service import ProfileService
    def make(*, policy=None):
        return ProfileService(auth_service, privacy_service, idempotency_service, profiles_store,
            policy=policy if policy is not None else ProfilePolicy(enabled=True))
    return make


@pytest.fixture
def profile_service(profile_factory):
    return profile_factory()


@pytest.fixture
def owner(admitted_actor_factory):
    return admitted_actor_factory()


@pytest.fixture
def principal(auth_service, owner):
    return auth_service.get_principal(owner.cookie)


@pytest.fixture
def created(profile_service, principal, create_input):
    from pydantic import SecretStr
    return profile_service.create_profile(principal, create_input, SecretStr("DEMO_T23_CREATE_KEY"))
