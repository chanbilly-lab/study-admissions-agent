"""T14 synthetic files and one required PostgreSQL DB, isolated per test."""

import os
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.auth.conftest import clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter
from tests.security.privacy.conftest import auth_store, auth_service, actor_factory, privacy_settings, privacy_service
from tests.security.grants.conftest import (admitted_actor_factory, resource_factory, principal_factory,
    sharing_settings, sharing_service, create_request_factory, accepted_grant_factory)
from tests.integration.sources.conftest import (catalog_store, catalog_tree, source_store,
    administrator_factory, source_request_factory)


@pytest.fixture(autouse=True)
def isolate_storage_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_", "STORAGE_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T14 forbids external sockets")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T14 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T14_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T14 PostgreSQL check not executed: T14_TEST_POSTGRES_URL absent", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/storage_t14_test":
        pytest.fail("T14 requires the dedicated loopback storage_t14_test database", pytrace=False)
    schema = "storage_t14_" + uuid4().hex
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


class IOProbe:
    """Wrap real local I/O; inject a failure only at the selected boundary."""
    def __init__(self, backend):
        self.backend = backend
        self.written = []
        self.read_count = 0
        self.deleted = []
        self.fail_write = self.fail_delete = False
        self.after_read = None
        self.after_write = None
    def verify_ready(self):
        return self.backend.verify_ready()
    def write(self, namespace, object_id, data):
        if self.fail_write:
            raise RuntimeError("DEMO_T14_PRIVATE_IO_SENTINEL")
        saved = self.backend.write(namespace, object_id, data)
        self.written.append(saved)
        if self.after_write is not None:
            self.after_write()
        return saved
    def read(self, namespace, object_id, expected_size, expected_sha256):
        data = self.backend.read(namespace, object_id, expected_size, expected_sha256)
        self.read_count += 1
        if self.after_read is not None:
            self.after_read()
        return data
    def delete(self, namespace, object_id):
        self.deleted.append((namespace, object_id))
        if self.fail_delete:
            raise RuntimeError("DEMO_T14_PRIVATE_IO_SENTINEL")
        return self.backend.delete(namespace, object_id)


@pytest.fixture
def blob_root(tmp_path):
    root = tmp_path / "DEMO_T14_STORAGE"
    root.mkdir()
    (root / "student_private").mkdir()
    (root / "source_quarantine").mkdir()
    return root


@pytest.fixture
def io_probe(blob_root):
    from services.api.app.storage.local import LocalStorageBackend
    return IOProbe(LocalStorageBackend(blob_root))


@pytest.fixture
def storage_store(auth_store, source_store, pg_engine):
    from services.api.app.storage.store import StorageStore, migrate_storage
    migrate_storage(pg_engine)
    return StorageStore(pg_engine)


@pytest.fixture
def storage_factory(auth_service, privacy_settings, source_store, storage_store, io_probe):
    from services.api.app.admin.sources.schemas import SourcePolicy
    from services.api.app.admin.sources.service import SourceService
    from services.api.app.privacy.service import PrivacyService
    from services.api.app.storage.schemas import StoragePolicy
    from services.api.app.storage.service import StorageService
    def make(*, identity=None, backend=None, policy=None, source_policy=None):
        identity = identity or auth_service
        privacy = PrivacyService(identity, privacy_settings)
        source = SourceService(identity, source_store, source_policy or SourcePolicy(enabled=True))
        return StorageService(identity, privacy, source, storage_store, backend or io_probe,
            policy if policy is not None else StoragePolicy(enabled=True, source_retention_days=1))
    return make


@pytest.fixture
def storage_service(storage_factory):
    return storage_factory()


@pytest.fixture
def private_file_factory(storage_service, admitted_actor_factory, resource_factory):
    def make(actor=None):
        actor = actor or admitted_actor_factory()
        principal = storage_service.auth_service.get_principal(actor.cookie)
        parent = resource_factory(actor)
        data = b'{"DEMO_T14":"synthetic file only"}'
        file = storage_service.upload_private(principal, parent_kind="profile", parent_resource_id=parent.id,
            filename="DEMO_T14.json", content_type="application/json", data=data)
        return SimpleNamespace(actor=actor, principal=principal, parent=parent, file=file, data=data)
    return make


@pytest.fixture
def source_file_factory(storage_factory, administrator_factory, source_request_factory, pg_engine, source_store):
    from sqlalchemy.orm import Session
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.admin.sources.schemas import SourcePolicy
    from services.api.app.admin.sources.service import SourceService
    def make(*, definition_updates=None, **actor_updates):
        admin = administrator_factory(**actor_updates)
        sources = SourceService(admin.service, source_store, SourcePolicy(enabled=True))
        values = dict(manual_import_permission="granted", publication_permission="denied",
            automated_fetch_permission="pending", license_basis="DEMO_MANUAL_ONLY_PERMISSION",
            permission_record_reference="DEMO_T14_PERMISSION", manual_import_enabled=True)
        values.update(definition_updates or {})
        request = source_request_factory(definition_updates=values)
        with Session(pg_engine) as session:
            expected = session.get(CatalogDataset, request.dataset_id).revision
        source = sources.register_source(admin.principal, request, expected_dataset_revision=expected)
        service = storage_factory(identity=admin.service)
        data = b'{"DEMO_T14":"synthetic source quarantine"}'
        file = service.upload_source(admin.principal, source.source_id, expected_source_version=source.version,
            filename="DEMO_source.json", content_type="application/json", data=data)
        return SimpleNamespace(admin=admin, sources=sources, source=source, request=request,
            service=service, file=file, data=data)
    return make
