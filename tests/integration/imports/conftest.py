"""T15 synthetic JSON/CSV assets in a dedicated, randomly isolated PG schema."""

import csv
import io
import json
import os
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from tests.integration.auth.conftest import (clock, session_settings_factory,
    session_settings, runtime, idp, oidc_adapter)
from tests.security.privacy.conftest import (auth_store, auth_service, actor_factory,
    privacy_settings, privacy_service)
from tests.integration.sources.conftest import (catalog_store, catalog_tree, source_store,
    administrator_factory, source_request_factory)
from tests.security.storage.conftest import (blob_root, io_probe, storage_store, storage_factory)


ROW_FIELDS = ("offering_id", "offering_version", "entry_year", "source_record_reference", "fact_type",
    "field_key", "value_kind", "value_text", "unit", "missing_reason", "footnote_state", "footnote_text", "locator")


@pytest.fixture(autouse=True)
def isolate_import_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_", "IMPORTS_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL", "STORAGE_DATABASE_URL",
            "IDEMPOTENCY_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T15 forbids external connections")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T15 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T15_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T15 PostgreSQL check not executed: T15_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/import_t15_test":
        pytest.fail("T15 requires the dedicated loopback import_t15_test database", pytrace=False)
    schema = "imports_t15_" + uuid4().hex
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
def imports_store(storage_store, idempotency_store, pg_engine):
    from services.api.app.admin.imports.store import ImportsStore, migrate_imports
    migrate_imports(pg_engine)
    return ImportsStore(pg_engine)


@pytest.fixture
def imports_factory(imports_store, idempotency_store):
    from services.api.app.admin.imports.service import ImportService
    from services.api.app.idempotency.schemas import IdempotencyPolicy
    from services.api.app.idempotency.service import IdempotencyService
    from services.api.app.ingestion.schemas import ImportsPolicy
    def make(storage, *, policy=None, ttl_seconds=86400):
        idempotency = IdempotencyService(storage.auth_service, storage.privacy_service, idempotency_store,
            IdempotencyPolicy(enabled=True, ttl_seconds=ttl_seconds))
        return ImportService(storage.source_service, storage, idempotency, imports_store,
            policy if policy is not None else ImportsPolicy(enabled=True))
    return make


@pytest.fixture
def candidate_factory(catalog_tree):
    def make(**changes):
        values = dict(offering_id=str(catalog_tree.offering.id), offering_version=1, entry_year=2026,
            source_record_reference="DEMO_T15_RECORD", fact_type="score", field_key="total_threshold",
            value_kind="decimal", value_text="600.00", unit="points", missing_reason=None,
            footnote_state="none", footnote_text=None, locator=None)
        values.update(changes)
        return values
    return make


def serialize_rows(rows, format):
    if format == "json":
        return json.dumps(rows, ensure_ascii=False, allow_nan=False).encode("utf-8")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: r"\N" if value is None else value for key, value in row.items()})
    return stream.getvalue().encode("utf-8")


@pytest.fixture
def import_case_factory(administrator_factory, storage_factory, source_request_factory,
        source_store, pg_engine, imports_factory, candidate_factory):
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.ingestion.schemas import ImportRequest
    def make(*, rows=None, format="json", ttl_seconds=86400, data=None, **admin_changes):
        administrator = administrator_factory(**admin_changes)
        storage = storage_factory(identity=administrator.service)
        source_request = source_request_factory(definition_updates={"manual_import_permission": "granted",
            "manual_import_enabled": True, "publication_permission": "denied",
            "license_basis": "DEMO_T15_MANUAL_ONLY", "permission_record_reference": "DEMO_T15_PERMISSION"})
        with Session(pg_engine) as session:
            revision = session.get(CatalogDataset, source_request.dataset_id).revision
        source = storage.source_service.register_source(administrator.principal, source_request,
            expected_dataset_revision=revision)
        body = data if data is not None else serialize_rows(rows if rows is not None else [candidate_factory()], format)
        def upload(content=body, selected_format=format):
            return storage.upload_source(administrator.principal, source.source_id, expected_source_version=source.version,
                filename="DEMO_T15." + selected_format,
                content_type="application/json" if selected_format == "json" else "text/csv", data=content)
        file = upload()
        def request(asset=file, **changes):
            fields = dict(dataset_id=source.dataset_id, source_id=source.source_id, source_version=source.version,
                file_id=asset.id, file_sha256=asset.sha256, format=format)
            fields.update(changes)
            return ImportRequest(**fields)
        return SimpleNamespace(admin=administrator, storage=storage, source=source, source_request=source_request,
            service=imports_factory(storage, ttl_seconds=ttl_seconds), file=file, request=request,
            data=body, upload=upload)
    return make
