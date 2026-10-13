"""T10 fixtures: synthetic actors in one dedicated, randomly isolated PG schema."""

import os
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.security.grants.conftest import (Actor, privacy_environment_and_network, clock,
    session_settings_factory, session_settings, runtime, idp, oidc_adapter, auth_store,
    auth_service, actor_factory, privacy_settings, privacy_service, principal_factory,
    admitted_actor_factory, resource_factory, sharing_settings, sharing_service,
    create_request_factory, accepted_grant_factory, client)
from services.api.app.audit.service import AuditService


@pytest.fixture
def pg_engine():
    url = os.getenv("T10_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T10 PostgreSQL check not run: T10_TEST_POSTGRES_URL absent", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/audit_t10_test":
        pytest.fail("T10 requires the dedicated loopback audit_t10_test database", pytrace=False)
    schema = "audit_t10_" + uuid4().hex
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
def audit_writer(auth_store):
    return auth_store.audit


@pytest.fixture
def audit_service(auth_service):
    return AuditService(auth_service)
