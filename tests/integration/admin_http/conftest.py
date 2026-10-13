"""T21 dedicated PostgreSQL schemas and the real frozen service pipeline."""

import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.imports.conftest import (clock, session_settings_factory, session_settings,
    runtime, idp, oidc_adapter, auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, import_case_factory, isolate_import_environment_and_network)


@pytest.fixture
def pg_engine():
    url = os.getenv("T21_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T21 PostgreSQL acceptance not executed: T21_TEST_POSTGRES_URL absent", pytrace=False)
    parsed = urlsplit(url)
    if (parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1"
        or parsed.path != "/study_t21_20261003"):
        pytest.fail("T21 requires the dedicated loopback study_t21_20261003 database", pytrace=False)
    schema = "admin_t21_" + uuid4().hex
    maintenance = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine, created = None, False
    try:
        with maintenance.begin() as connection:
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
            with maintenance.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        maintenance.dispose()


@pytest.fixture
def admin_case_factory(import_case_factory):
    from services.api.app.api.admin import create_admin_app
    def make(**changes):
        case = import_case_factory(**changes)
        app = create_admin_app(case.admin.service.runtime_settings, identity_service=case.admin.service,
            source_service=case.storage.source_service, storage_service=case.storage, import_service=case.service)
        return SimpleNamespace(**vars(case), app=app)
    return make
