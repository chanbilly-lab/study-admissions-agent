"""T20 anonymous reads of explicitly synthetic releases in a dedicated PG DB."""

import os
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from tests.integration.releases.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, evidence_store, evidence_factory,
    facts_store, facts_factory, classification_factory, fact_case_factory,
    reviews_store, review_case_factory, releases_store, release_case_factory,
)
from tests.integration.imports.conftest import serialize_rows


@pytest.fixture(autouse=True)
def isolate_public_catalog_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_", "PUBLIC_CATALOG_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL", "STORAGE_DATABASE_URL",
            "IMPORTS_DATABASE_URL", "EVIDENCE_DATABASE_URL", "IDEMPOTENCY_DATABASE_URL", "FACTS_DATABASE_URL",
            "REVIEWS_DATABASE_URL", "RELEASES_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T20 forbids external connections")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T20 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T20_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T20 PostgreSQL check not executed: T20_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/study_t20_20261003":
        pytest.fail("T20 requires the dedicated loopback study_t20_20261003 database", pytrace=False)
    schema = "public_catalog_t20_" + uuid4().hex
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
def import_case_factory(administrator_factory, storage_factory, source_request_factory,
        pg_engine, imports_factory, candidate_factory):
    """Create rights before snapshots; the private URL is deliberately not public-safe."""
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.ingestion.schemas import ImportRequest
    def make(*, rows=None, format="json", ttl_seconds=86400, data=None,
            publication_permission="granted", definition_updates=None, **admin_changes):
        administrator = administrator_factory(**admin_changes)
        storage = storage_factory(identity=administrator.service)
        definitions = dict(manual_import_permission="granted", manual_import_enabled=True,
            publication_permission=publication_permission,
            license_basis="DEMO_T20_EXPLICIT_MANUAL_AND_PUBLIC_LICENSE",
            permission_record_reference="DEMO_T20_PERMISSION",
            entry_url="https://127.0.0.1/DEMO_PRIVATE?token=DEMO_T20_PRIVATE_URL_SENTINEL")
        definitions.update(definition_updates or {})
        source_request = source_request_factory(definition_updates=definitions)
        with Session(pg_engine) as session:
            revision = session.get(CatalogDataset, source_request.dataset_id).revision
        source = storage.source_service.register_source(administrator.principal, source_request,
            expected_dataset_revision=revision)
        body = data if data is not None else serialize_rows(rows if rows is not None else [candidate_factory()], format)
        def upload(content=body, selected_format=format):
            return storage.upload_source(administrator.principal, source.source_id, expected_source_version=source.version,
                filename="DEMO_T20." + selected_format,
                content_type="application/json" if selected_format == "json" else "text/csv", data=content)
        file = upload()
        def request(asset=file, **changes):
            fields = dict(dataset_id=source.dataset_id, source_id=source.source_id, source_version=source.version,
                file_id=asset.id, file_sha256=asset.sha256, format=format)
            fields.update(changes)
            return ImportRequest(**fields)
        return SimpleNamespace(admin=administrator, storage=storage, source=source, source_request=source_request,
            service=imports_factory(storage, ttl_seconds=ttl_seconds), file=file, request=request, data=body, upload=upload)
    return make


@pytest.fixture
def public_case_factory(release_case_factory):
    from pydantic import SecretStr
    from services.api.app.public_catalog.reader import CatalogReader
    from services.api.app.public_catalog.schemas import PublicCatalogPolicy
    from services.api.app.releases.schemas import PublishMember
    from services.api.app.settings import V2RuntimeSettings
    def make(*, published=True, public_evidence=True, **changes):
        case = release_case_factory(**changes)
        settings = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled",
            database_url=None, legacy_demo_mode=None, _env_file=None)
        reader = CatalogReader(case.releases, settings,
            PublicCatalogPolicy(enabled=True, allow_test_fixture_read=True))
        release = None
        if published:
            members = tuple(PublishMember(fact_id=decision.fact_id, expected_case_revision=decision.case_revision,
                expected_decision_id=decision.decision_id, public_evidence=public_evidence) for decision in case.decisions)
            release = case.releases.publish(case.reviewer.principal, case.publish_request(members=members),
                SecretStr("DEMO_T20_PUBLISH_" + uuid4().hex))
        return SimpleNamespace(**vars(case), reader=reader, public_settings=settings, release=release)
    return make


@pytest.fixture
def extra_offering_factory(catalog_store, catalog_tree, pg_engine):
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.admissions_catalog.schemas import OfferingInput, ScopeKey
    def make(**changes):
        values = catalog_tree.offering.model_dump(exclude={"current_version"})
        values.update(id=uuid4(), reference_key="DEMO_T20_OFFERING_" + uuid4().hex,
            channel=ScopeKey(status="known", value="DEMO_CHANNEL_" + uuid4().hex))
        values.update(changes)
        with Session(pg_engine) as session, session.begin():
            revision = session.get(CatalogDataset, catalog_tree.dataset.id).revision
            return catalog_store.create_offering(session, OfferingInput(**values),
                expected_dataset_revision=revision, version_id=uuid4())
    return make
