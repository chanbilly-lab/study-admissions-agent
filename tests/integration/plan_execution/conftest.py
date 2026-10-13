"""T32 actual pipeline in a fresh dedicated loopback schema per test."""

import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.planning.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, evidence_store, evidence_factory, facts_store,
    facts_factory, classification_factory, reviews_store, releases_store, import_case_factory,
    isolate_releases_environment_and_network, profiles_store, assessments_store,
    assessment_case_factory, plans_store, plan_case_factory,
)


@pytest.fixture
def pg_engine():
    raw = os.getenv("T23_TEST_POSTGRES_URL")
    if not raw:
        pytest.fail("T32 PostgreSQL checks require T23_TEST_POSTGRES_URL", pytrace=False)
    parsed = urlsplit(raw)
    if (parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1"
        or parsed.port != 55438 or parsed.path != "/study_t23_20261003"):
        pytest.fail("T32 requires the dedicated loopback study_t23_20261003 database", pytrace=False)
    schema = "execution_t32_" + uuid4().hex
    admin = create_engine(raw, hide_parameters=True, connect_args={"connect_timeout":5})
    engine, created = None, False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(raw,hide_parameters=True,
            connect_args={"options":"-csearch_path="+schema,"connect_timeout":5})
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
def execution_store(plans_store, pg_engine):
    from services.api.app.plan_execution.store import ExecutionStore, migrate_execution
    migrate_execution(pg_engine)
    return ExecutionStore(pg_engine)


@pytest.fixture
def execution_case_factory(execution_store, plan_case_factory):
    from services.api.app.idempotency.schemas import IdempotencyPolicy
    from services.api.app.idempotency.service import IdempotencyService
    from services.api.app.plan_execution.schemas import ExecutionPolicy
    from services.api.app.plan_execution.service import ExecutionService

    def make(*, create=True, receipt_ttl_seconds=86400, **options):
        original = plan_case_factory(**options)
        plans = original.service
        profiles = plans.eligibility_service.profile_service
        idem = IdempotencyService(plans.auth_service,profiles.privacy_service,profiles.idempotency_service.store,
            IdempotencyPolicy(enabled=True,ttl_seconds=receipt_ttl_seconds))
        service = ExecutionService(plans,idem,execution_store,
            ExecutionPolicy(enabled=True,allow_test_execution=True))
        values=dict(vars(original))
        values.update(plans=plans,service=service,execution=service,idempotency=idem,
            plan=service.create_plan(original.principal,original.request) if create else None)
        return SimpleNamespace(**values)
    return make
