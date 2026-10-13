"""T13 synthetic maintenance in a dedicated, randomly isolated PostgreSQL schema."""

from datetime import timedelta
import os
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from tests.integration.auth.conftest import clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter
from tests.security.privacy.conftest import auth_store, auth_service, actor_factory
from tests.integration.catalog.conftest import catalog_tree


@pytest.fixture(autouse=True)
def isolate_source_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for method in ("connect", "connect_ex"):
        original = getattr(socket.socket, method)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T13 forbids external connections")
        monkeypatch.setattr(socket.socket, method, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T13 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T13_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T13 PostgreSQL check not executed: T13_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/source_t13_test":
        pytest.fail("T13 requires the dedicated loopback source_t13_test database", pytrace=False)
    schema = "source_t13_" + uuid4().hex
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
def catalog_store(pg_engine):
    from services.api.app.admissions_catalog.store import CatalogStore, migrate_catalog
    migrate_catalog(pg_engine)
    return CatalogStore(pg_engine)


@pytest.fixture
def source_store(catalog_store, pg_engine):
    from services.api.app.admin.sources.store import SourceStore
    return SourceStore(pg_engine)


@pytest.fixture
def administrator_factory(auth_store, session_settings_factory, runtime, clock, actor_factory, pg_engine):
    """Fixed synthetic DB provenance, not a new signed-token verification claim."""
    from services.api.app.auth.assurance import AdminAssurancePolicy
    from services.api.app.auth.models import AuthSession, AuthUserRole
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.service import AuthService
    def make(*, role="data_admin", lifetime=3600, assurance_age_limit=60, role_lifetime=None, is_synthetic=True):
        base = session_settings_factory()
        provider = base.provider.model_copy(update={"client_id": "T13_ADMIN_CLIENT"})
        policy = AdminAssurancePolicy(enabled=True, trusted_issuer=provider.issuer,
            admin_client_id=provider.client_id, student_client_id="T13_STUDENT_CLIENT",
            allowed_acr=("T13_SYNTHETIC_MFA",), required_amr=("pwd", "otp"),
            max_auth_age_seconds=assurance_age_limit)
        settings = base.model_copy(update={"provider": provider, "admin_assurance_policy": policy})
        def forbidden_io(request):
            raise AssertionError("T13 source registration must not call an identity provider")
        adapter = KeycloakOidcAdapter(settings, runtime, transport=httpx.MockTransport(forbidden_io))
        service = AuthService(settings, runtime, auth_store, adapter, clock=clock)
        actor = actor_factory(role=role, lifetime=lifetime, is_synthetic=is_synthetic)
        with Session(pg_engine) as session, session.begin():
            row = session.get(AuthSession, actor.session_id)
            row.verified_issuer, row.verified_client_id = provider.issuer, provider.client_id
            row.assurance_acr, row.assurance_amr, row.assurance_auth_time = "T13_SYNTHETIC_MFA", ["pwd", "otp"], clock()
            if role is not None and role_lifetime is not None:
                session.get(AuthUserRole, (actor.user_id, role)).expires_at = clock() + timedelta(seconds=role_lifetime)
        return SimpleNamespace(service=service, actor=actor, principal=service.get_principal(actor.cookie))
    return make


@pytest.fixture
def administrator(administrator_factory):
    return administrator_factory()


@pytest.fixture
def source_service(source_store, administrator):
    from services.api.app.admin.sources.schemas import SourcePolicy
    from services.api.app.admin.sources.service import SourceService
    return SourceService(administrator.service, source_store, SourcePolicy(enabled=True))


@pytest.fixture
def source_request_factory(catalog_tree):
    from services.api.app.admin.sources.schemas import SourceCreateInput, SourceDefinition
    def request(*, definition_updates=None, **updates):
        values = dict(publisher="DEMO_T13_SYNTHETIC_PUBLISHER", entry_url="https://sources.test.invalid/DEMO_2026",
            purpose="admissions_reference", data_type="entry_requirements", scope_note="DEMO_T13 synthetic scope only",
            authority_claim="claimed_official", manual_import_permission="pending", publication_permission="pending",
            automated_fetch_permission="pending", license_basis=None, permission_record_reference=None,
            recheck_days=1, manual_import_enabled=False)
        values.update(definition_updates or {})
        fields = dict(id=uuid4(), dataset_id=catalog_tree.dataset.id, reference_key="DEMO_SOURCE_" + uuid4().hex,
            is_synthetic=True, definition=SourceDefinition(**values))
        fields.update(updates)
        return SourceCreateInput(**fields)
    return request
