"""Synthetic T16 files in a dedicated, randomly isolated PostgreSQL schema."""

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


TARGET = "DEMO_升学"
ORIGINALS = {
    "json": ('{\r\n"DEMO_ascii":"DEMO_ALPHA",\r\n"DEMO_unicode":"' + TARGET
        + '",\r\n"DEMO_html":"<script>DEMO_no_execution()</script>"\r\n}\r\n').encode("utf-8"),
    "csv": ('DEMO_column,DEMO_note\r\nDEMO_ALPHA,"' + TARGET
        + '"\r\nDEMO_BETA,"<script>DEMO_no_execution()</script>"\r\n').encode("utf-8"),
}


@pytest.fixture(autouse=True)
def isolate_evidence_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_", "EVIDENCE_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL", "STORAGE_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T16 forbids external connections")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T16 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T16_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T16 PostgreSQL check not executed: T16_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/evidence_t16_test":
        pytest.fail("T16 requires the dedicated loopback evidence_t16_test database", pytrace=False)
    schema = "evidence_t16_" + uuid4().hex
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
def evidence_store(storage_store, pg_engine):
    from services.api.app.evidence.store import EvidenceStore, migrate_evidence
    migrate_evidence(pg_engine)
    return EvidenceStore(pg_engine)


@pytest.fixture
def evidence_factory(evidence_store):
    from services.api.app.evidence.schemas import EvidencePolicy
    from services.api.app.evidence.service import EvidenceService
    def make(storage, *, policy=None):
        return EvidenceService(storage.source_service, storage, evidence_store,
            policy if policy is not None else EvidencePolicy(enabled=True))
    return make


@pytest.fixture
def evidence_case_factory(administrator_factory, storage_factory, source_request_factory,
        pg_engine, evidence_factory, catalog_tree):
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.evidence.models import Document
    from services.api.app.evidence.schemas import DocumentCreate, VersionCreate, SnippetCreate
    def make(*, format="json", data=None, create_version=True, **administrator_changes):
        administrator = administrator_factory(**administrator_changes)
        storage = storage_factory(identity=administrator.service)
        source_request = source_request_factory(definition_updates={"manual_import_permission": "granted",
            "manual_import_enabled": True, "publication_permission": "denied",
            "license_basis": "DEMO_T16_MANUAL_ONLY", "permission_record_reference": "DEMO_T16_PERMISSION"})
        with Session(pg_engine) as session:
            revision = session.get(CatalogDataset, source_request.dataset_id).revision
        source = storage.source_service.register_source(administrator.principal, source_request,
            expected_dataset_revision=revision)
        content = ORIGINALS[format] if data is None else data
        def upload(content=content, selected_format=format):
            return storage.upload_source(administrator.principal, source.source_id, expected_source_version=source.version,
                filename="DEMO_T16." + selected_format,
                content_type={"json": "application/json", "csv": "text/csv", "pdf": "application/pdf"}[selected_format],
                data=content)
        file = upload()
        service = evidence_factory(storage)
        request = DocumentCreate(dataset_id=source.dataset_id, source_id=source.source_id,
            source_version=source.version, document_reference="DEMO_DOCUMENT_" + uuid4().hex, language="zh-Hans")
        document = service.create_document(administrator.principal, request)
        def version_request(asset=file, *, expected=None, **updates):
            if expected is None:
                with Session(pg_engine) as session:
                    expected = session.get(Document, document.id).current_version
            fields = dict(document_id=document.id, expected_current_version=expected,
                file_id=asset.id, file_sha256=asset.sha256)
            fields.update(updates)
            return VersionCreate(**fields)
        version = service.create_version(administrator.principal, version_request()) if create_version else None
        def snippet_request(*, version_number=None, offering=None, span=None, **updates):
            target = catalog_tree.offering if offering is None else offering
            start = content.find(TARGET.encode("utf-8")) if span is None else span[0]
            end = start + len(TARGET.encode("utf-8")) if span is None else span[1]
            fields = dict(document_id=document.id, document_version=version_number or version.version,
                offering_id=target.id, offering_version=1, entry_year=target.entry_year,
                byte_start=start, byte_end=end)
            fields.update(updates)
            return SnippetCreate(**fields)
        return SimpleNamespace(admin=administrator, storage=storage, source=source, source_request=source_request,
            service=service, file=file, document=document, request=request, version=version,
            version_request=version_request, snippet_request=snippet_request, content=content, upload=upload)
    return make
