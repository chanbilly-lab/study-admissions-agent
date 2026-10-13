"""T12 isolated PostgreSQL date candidates; no external network or real facts."""

import os
import socket
from datetime import date, time
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.catalog.conftest import catalog_tree


@pytest.fixture(autouse=True)
def isolate_date_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for method in ("connect", "connect_ex"):
        original = getattr(socket.socket, method)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T12 forbids external connections")
        monkeypatch.setattr(socket.socket, method, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T12 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T12_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T12 PostgreSQL check not executed: T12_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/date_t12_test":
        pytest.fail("T12 requires the dedicated loopback date_t12_test database", pytrace=False)
    schema = "date_t12_" + uuid4().hex
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
def date_store(catalog_store, pg_engine):
    from services.api.app.admissions_catalog.date_store import DateEventStore
    return DateEventStore(pg_engine)


@pytest.fixture
def date_request_factory(catalog_tree):
    from services.api.app.admissions_catalog.date_schemas import DateEventInput
    def request(**updates):
        fields = dict(id=uuid4(), dataset_id=catalog_tree.dataset.id, offering_id=catalog_tree.offering.id,
            offering_version=1, reference_key="DEMO_DATE_" + uuid4().hex, is_synthetic=True,
            entry_year=catalog_tree.offering.entry_year, event_type="application_deadline",
            original_text="DEMO_2026-07-15 15:30 Europe/London synthetic candidate",
            local_date=date(2026, 7, 15), local_time=time(15, 30), timezone="Europe/London",
            precision="minute", source_alignment="pending", evidence_reference="DEMO_UNRESOLVED_EVIDENCE")
        fields.update(updates)
        return DateEventInput(**fields)
    return request
