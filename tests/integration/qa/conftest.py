"""T38 reuses T20 authority fixtures in its own random T23-only PG schema."""

import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.public_catalog.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter, auth_store, auth_service,
    actor_factory, privacy_settings, privacy_service, catalog_store, catalog_tree, source_store,
    administrator_factory, source_request_factory, blob_root, io_probe, storage_store, storage_factory,
    idempotency_store, imports_store, imports_factory, candidate_factory, evidence_store, evidence_factory,
    facts_store, facts_factory, classification_factory, fact_case_factory, reviews_store, review_case_factory,
    releases_store, release_case_factory, import_case_factory, public_case_factory, extra_offering_factory,
    isolate_public_catalog_environment_and_network,
)


@pytest.fixture
def pg_engine():
    raw = os.getenv("T23_TEST_POSTGRES_URL")
    if not raw:
        pytest.fail("T38 requires the dedicated T23 loopback test database", pytrace=False)
    parsed = urlsplit(raw)
    if (parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.port != 55438
        or parsed.path != "/study_t23_20261003"):
        pytest.fail("T38 requires the dedicated T23 loopback test database", pytrace=False)
    schema = "qa_t38_" + uuid4().hex
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
def qa_case_factory(public_case_factory, catalog_tree):
    from services.api.app.qa import QAPolicy, RequestScope, RetrievalRequest
    from services.api.app.qa.retrieval import ScopedRetriever
    def make(**changes):
        case = public_case_factory(**changes)
        scope = case.review_snippets[0].scope
        request = RetrievalRequest(release_id=case.release.release_id if case.release is not None else uuid4(),
            offering_id=catalog_tree.offering.id, offering_version=1, entry_year=2026,
            scope=RequestScope.model_validate(scope.model_dump(exclude={"dataset_id"})), intent="requirements")
        retriever = ScopedRetriever(case.reader, QAPolicy(enabled=True, allow_test_fixture_read=True))
        return SimpleNamespace(**{**vars(case), "retriever": retriever, "request": request})
    return make
