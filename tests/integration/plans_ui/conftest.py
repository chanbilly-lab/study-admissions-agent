"""T33's actual synthetic pipeline; plans and evaluations start empty."""

import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.catalog_ui.conftest import (
    clock, runtime, idp, oidc_adapter, auth_store, auth_service, actor_factory,
    privacy_settings, privacy_service, catalog_store, catalog_tree, source_store,
    administrator_factory, source_request_factory, blob_root, io_probe, storage_store,
    storage_factory, idempotency_store, imports_store, imports_factory, candidate_factory,
    evidence_store, evidence_factory, facts_store, facts_factory, classification_factory,
    reviews_store, releases_store, import_case_factory, profiles_store, assessments_store,
    assessment_case_factory, isolate_releases_environment_and_network,
    browser_origin, session_settings_factory, session_settings,
    workspace_factory as catalog_workspace_factory,
)
from tests.integration.planning.conftest import plans_store
from tests.integration.plan_execution.conftest import execution_store


@pytest.fixture
def pg_engine():
    raw = os.getenv("T23_TEST_POSTGRES_URL")
    if not raw:
        pytest.fail("T33 requires T23_TEST_POSTGRES_URL", pytrace=False)
    parsed = urlsplit(raw)
    if (parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1"
            or parsed.port != 55438 or parsed.path != "/study_t23_20261003"):
        pytest.fail("T33 requires its dedicated loopback database", pytrace=False)
    schema = "plans_ui_t33_" + uuid4().hex
    maintenance = create_engine(raw, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine, created = None, False
    try:
        with maintenance.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(raw, hide_parameters=True,
            connect_args={"options": "-csearch_path=" + schema, "connect_timeout": 5})
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
def workspace_factory(catalog_workspace_factory, plans_store, execution_store):
    from fastapi import FastAPI
    from services.api.app.api.plans import create_plans_v2_app
    from services.api.app.api.public_catalog import create_public_catalog_v2_app
    from services.api.app.plan_execution.schemas import ExecutionPolicy
    from services.api.app.plan_execution.service import ExecutionService
    from services.api.app.plans.schemas import PlanPolicy
    from services.api.app.plans.service import PlansService

    def make():
        original = catalog_workspace_factory()
        plans = PlansService(original.service, plans_store,
            PlanPolicy(enabled=True, allow_test_drafts=True))
        execution = ExecutionService(plans, original.case.profiles.idempotency_service,
            execution_store, ExecutionPolicy(enabled=True, allow_test_execution=True))
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        app.mount("/v2", create_plans_v2_app(original.auth.runtime_settings,
            identity_service=original.auth, profile_service=original.case.profiles,
            assessment_service=original.service, execution_service=execution))
        app.mount("/public/v2", create_public_catalog_v2_app(original.reader.settings,
            reader=original.reader))
        values = dict(vars(original))
        values.update(app=app, plans=plans, execution=execution)
        return SimpleNamespace(**values)
    return make
