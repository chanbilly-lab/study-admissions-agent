"""T30 uses actual T28 proofs in a new isolated loopback PostgreSQL schema."""

import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.eligibility.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, evidence_store, evidence_factory, facts_store,
    facts_factory, classification_factory, reviews_store, releases_store, import_case_factory,
    isolate_releases_environment_and_network, profiles_store, assessments_store, assessment_case_factory,
)


@pytest.fixture
def pg_engine():
    raw = os.getenv("T23_TEST_POSTGRES_URL")
    if not raw:
        pytest.fail("T30 PostgreSQL checks require T23_TEST_POSTGRES_URL", pytrace=False)
    parsed = urlsplit(raw)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/study_t23_20261003":
        pytest.fail("T30 requires the dedicated loopback study_t23_20261003 database", pytrace=False)
    schema = "planning_t30_" + uuid4().hex
    admin = create_engine(raw, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine, created = None, False
    try:
        with admin.begin() as connection:
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
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def plans_store(assessments_store, pg_engine):
    from services.api.app.plans.store import PlansStore, migrate_plans
    migrate_plans(pg_engine)
    return PlansStore(pg_engine)


@pytest.fixture
def plan_case_factory(plans_store, assessment_case_factory):
    from services.api.app.plans.schemas import PlanCreateInput, PlanPolicy
    from services.api.app.plans.service import PlansService

    def make(**options):
        original = assessment_case_factory(**options)
        assessment = original.service.evaluate(original.principal, original.request)
        values = dict(vars(original))
        values.update(eligibility=original.service, assessment=assessment,
            service=PlansService(original.service, plans_store, PlanPolicy(enabled=True, allow_test_drafts=True)),
            request=PlanCreateInput(assessment_ids=(assessment.assessment_id,), confirmed=True))
        return SimpleNamespace(**values)
    return make
