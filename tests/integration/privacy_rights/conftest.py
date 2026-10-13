"""Dedicated real PG business schema and a separate ledger schema per test."""
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from pydantic import SecretBytes
from sqlalchemy import create_engine, inspect, text

from tests.integration.jobs.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, evidence_store, evidence_factory, facts_store,
    facts_factory, classification_factory, reviews_store, releases_store, import_case_factory,
    isolate_releases_environment_and_network, profiles_store, assessments_store,
    assessment_case_factory, plans_store, plan_case_factory, execution_store, execution_case_factory,
    changes_store, change_case_factory, revisions_store, jobs_store, notifications_store, job_case_factory,
)
from tests.integration.plan_revisions.conftest import revision_case_factory


@pytest.fixture
def schema_pair():
    raw = os.getenv("T23_TEST_POSTGRES_URL")
    parsed = urlsplit(raw or "")
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.port != 55438 or parsed.path != "/study_t23_20261003":
        pytest.fail("T40 requires dedicated loopback T23_TEST_POSTGRES_URL", pytrace=False)
    names = ("rights_t40_" + uuid4().hex, "ledger_t40_" + uuid4().hex)
    admin = create_engine(raw, hide_parameters=True, connect_args={"connect_timeout": 5})
    engines = []
    created = []
    try:
        for name in names:
            with admin.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{name}"'))
            created.append(name)
            engine = create_engine(raw, hide_parameters=True,
                connect_args={"options": "-csearch_path=" + name, "connect_timeout": 5})
            engines.append(engine)
            assert inspect(engine).get_table_names() == []
        yield SimpleNamespace(business=engines[0], ledger=engines[1], business_schema=names[0], ledger_schema=names[1], admin=admin)
    finally:
        for engine in engines:
            engine.dispose()
        for name in reversed(created):
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg_engine(schema_pair):
    return schema_pair.business


@pytest.fixture
def rights_store(jobs_store, pg_engine):
    from services.api.app.privacy.rights.store import RightsStore, migrate
    migrate(pg_engine)
    return RightsStore(pg_engine)


@pytest.fixture
def external_ledger(schema_pair, tmp_path):
    from services.api.app.privacy.rights.ledger import ExternalLedger, FileAnchor
    from services.api.app.privacy.rights.store import migrate
    migrate(schema_pair.ledger, ledger=True)
    root = tmp_path / "outside-business-backup"
    root.mkdir()
    ledger = ExternalLedger(schema_pair.ledger, FileAnchor(root, SecretBytes(b"DEMO_T40_ONLY_32_BYTE_ANCHOR_KEY__")))
    ledger.bootstrap()
    return ledger


@pytest.fixture
def rights_case_factory(rights_store, external_ledger, job_case_factory, io_probe):
    from services.api.app.privacy.rights.guard import RightsGuard
    from services.api.app.privacy.rights.schemas import RightsPolicy
    from services.api.app.privacy.rights.service import RightsService
    def make(*, policy=None, **options):
        original = job_case_factory(**options)
        guard = RightsGuard(rights_store.engine, external_ledger, io_probe, clock=original.auth.clock)
        guard.bootstrap_business()
        original.auth.store.install_rights_guard(guard)
        rights = RightsService(original.auth, rights_store, guard,
            policy or RightsPolicy(enabled=True, allow_test_rights=True))
        return SimpleNamespace(**{**vars(original), "service": rights, "rights": rights,
            "guard": guard, "ledger": external_ledger, "io": io_probe})
    return make


@pytest.fixture
def rights_revision_case_factory(rights_store, external_ledger, revision_case_factory, io_probe):
    from services.api.app.privacy.rights.guard import RightsGuard
    from services.api.app.privacy.rights.schemas import RightsPolicy
    from services.api.app.privacy.rights.service import RightsService
    def make():
        original = revision_case_factory()
        guard = RightsGuard(rights_store.engine, external_ledger, io_probe, clock=original.auth.clock)
        guard.bootstrap_business()
        original.auth.store.install_rights_guard(guard)
        rights = RightsService(original.auth, rights_store, guard, RightsPolicy(enabled=True, allow_test_rights=True))
        return SimpleNamespace(**{**vars(original), "revisions": original.service, "rights": rights,
            "guard": guard, "ledger": external_ledger, "io": io_probe})
    return make
