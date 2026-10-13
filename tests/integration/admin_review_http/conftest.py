"""Fresh T22 schema; all facts and evidence are prepared through HTTP in tests."""

import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from tests.integration.releases.conftest import (
    isolate_releases_environment_and_network, clock, session_settings_factory, session_settings,
    runtime, idp, oidc_adapter, auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store, imports_factory,
    candidate_factory, evidence_store, evidence_factory, facts_store, facts_factory,
    classification_factory, reviews_store, releases_store,
)


@pytest.fixture
def pg_engine():
    url = os.getenv("T22_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T22 PostgreSQL check not executed: T22_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/study_t22_20261003":
        pytest.fail("T22 requires its dedicated loopback study_t22_20261003 database", pytrace=False)
    schema = "admin_review_t22_" + uuid4().hex
    maintenance = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine, created = None, False
    try:
        with maintenance.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(url, hide_parameters=True,
            connect_args={"options": "-csearch_path=" + schema, "connect_timeout": 5})
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with maintenance.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        maintenance.dispose()


@pytest.fixture
def reviews_factory(reviews_store):
    from services.api.app.reviews.schemas import ReviewPolicy
    from services.api.app.reviews.service import ReviewService
    def make(facts, *, policy=None):
        return ReviewService(facts, reviews_store, policy or ReviewPolicy(enabled=True))
    return make


@pytest.fixture
def releases_factory(releases_store):
    from services.api.app.releases.schemas import ReleasePolicy
    from services.api.app.releases.service import ReleaseService
    def make(reviews, imports, *, policy=None):
        return ReleaseService(reviews, imports.idempotency_service, releases_store,
            policy or ReleasePolicy(enabled=True, allow_test_releases=True))
    return make


@pytest.fixture
def workspace_factory(administrator_factory, storage_factory, imports_factory,
    evidence_factory, facts_factory, reviews_factory, releases_factory):
    from services.api.app.api.admin_review import create_admin_review_app
    from services.api.app.public_catalog.reader import CatalogReader
    from services.api.app.public_catalog.schemas import PublicCatalogPolicy
    from services.api.app.settings import V2RuntimeSettings
    def make(*, administrator=None, reader=True):
        selected = administrator or administrator_factory()
        identity = selected.service
        storage = storage_factory(identity=identity)
        imports = imports_factory(storage)
        evidence = evidence_factory(storage)
        facts = facts_factory(storage, imports=imports, evidence=evidence)
        reviews = reviews_factory(facts)
        releases = releases_factory(reviews, imports)
        public_runtime = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled",
            database_url=None, legacy_demo_mode=None, _env_file=None)
        public = CatalogReader(releases, public_runtime,
            PublicCatalogPolicy(enabled=True, allow_test_fixture_read=True)) if reader else None
        app = create_admin_review_app(identity.runtime_settings, identity_service=identity,
            source_service=storage.source_service, storage_service=storage, import_service=imports,
            evidence_service=evidence, fact_service=facts, review_service=reviews, release_service=releases, reader=public)
        return SimpleNamespace(app=app, admin=selected, auth=identity, source=storage.source_service,
            storage=storage, imports=imports, evidence=evidence, facts=facts, reviews=reviews, releases=releases, reader=public)
    return make
