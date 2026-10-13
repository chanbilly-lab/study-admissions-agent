"""T17 synthetic candidates in one dedicated, randomly isolated PG schema."""

import os
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from tests.integration.auth.conftest import (clock, session_settings_factory,
    session_settings, runtime, idp, oidc_adapter)
from tests.security.privacy.conftest import (auth_store, auth_service, actor_factory,
    privacy_settings, privacy_service)
from tests.integration.sources.conftest import (catalog_store, catalog_tree, source_store,
    administrator_factory, source_request_factory)
from tests.security.storage.conftest import (blob_root, io_probe, storage_store, storage_factory)
from tests.integration.imports.conftest import (idempotency_store, imports_store, imports_factory,
    candidate_factory, import_case_factory)
from tests.integration.evidence.conftest import evidence_store, evidence_factory


@pytest.fixture(autouse=True)
def isolate_facts_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_", "FACTS_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL", "STORAGE_DATABASE_URL",
            "IMPORTS_DATABASE_URL", "EVIDENCE_DATABASE_URL", "IDEMPOTENCY_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T17 forbids external connections")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T17 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T17_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T17 PostgreSQL check not executed: T17_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/facts_t17_test":
        pytest.fail("T17 requires the dedicated loopback facts_t17_test database", pytrace=False)
    schema = "facts_t17_" + uuid4().hex
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
def facts_store(imports_store, evidence_store, pg_engine):
    from services.api.app.facts.store import FactsStore, migrate_facts
    migrate_facts(pg_engine)
    return FactsStore(pg_engine)


@pytest.fixture
def facts_factory(facts_store, imports_factory, evidence_factory):
    from services.api.app.facts.schemas import FactPolicy
    from services.api.app.facts.service import FactService
    def make(storage, *, imports=None, evidence=None, policy=None):
        return FactService(imports or imports_factory(storage), evidence or evidence_factory(storage), facts_store,
            policy if policy is not None else FactPolicy(enabled=True))
    return make


@pytest.fixture
def classification_factory():
    from services.api.app.facts.schemas import Classification
    def make(**changes):
        values = dict(claim_kind="minimum_requirement", unit_code="points", period="not_applicable",
            statistics_basis="not_applicable", statistic_population=None, statistic_denominator=None,
            cohort_year=None, survey_period=None, date_event_id=None)
        values.update(changes)
        return Classification(**values)
    return make


@pytest.fixture
def fact_case_factory(import_case_factory, facts_factory, evidence_factory, pg_engine, candidate_factory):
    from services.api.app.admin.imports.models import ImportCandidateRow
    from services.api.app.evidence.schemas import DocumentCreate, VersionCreate, SnippetCreate
    from services.api.app.facts.schemas import FactCreate
    def make(*, rows=None, format="json", with_evidence=True, **admin_changes):
        raw = rows if rows is not None else [candidate_factory()]
        case = import_case_factory(rows=raw, format=format, **admin_changes)
        imported = case.service.import_file(case.admin.principal, case.request(), SecretStr("DEMO_T17_IMPORT_" + uuid4().hex))
        assert imported.status == "staged"
        with Session(pg_engine) as session:
            stored = session.scalars(select(ImportCandidateRow).where(ImportCandidateRow.import_id == imported.id)
                .order_by(ImportCandidateRow.row_number)).all()
            row_ids = tuple(row.id for row in stored)
        evidence = evidence_factory(case.storage)
        snippets, document, version = [], None, None
        if with_evidence:
            document = evidence.create_document(case.admin.principal, DocumentCreate(dataset_id=case.source.dataset_id,
                source_id=case.source.source_id, source_version=case.source.version,
                document_reference="DEMO_T17_DOCUMENT_" + uuid4().hex, language="und"))
            version = evidence.create_version(case.admin.principal, VersionCreate(document_id=document.id,
                expected_current_version=0, file_id=case.file.id, file_sha256=case.file.sha256))
            for row in raw:
                needle = (row["value_text"] or row["source_record_reference"]).encode("utf-8")
                start = case.data.find(needle)
                assert start >= 0
                snippets.append(evidence.create_snippet(case.admin.principal, SnippetCreate(document_id=document.id,
                    document_version=version.version, offering_id=row["offering_id"], offering_version=row["offering_version"],
                    entry_year=row["entry_year"], byte_start=start, byte_end=start + len(needle))))
        service = facts_factory(case.storage, imports=case.service, evidence=evidence)
        def request(classification, *, index=0, evidence_id=..., **changes):
            fields = dict(import_id=imported.id, import_row_id=row_ids[index], classification=classification,
                evidence_id=(snippets[index].id if snippets else None) if evidence_id is ... else evidence_id)
            fields.update(changes)
            return FactCreate(**fields)
        return SimpleNamespace(**vars(case), imported=imported, row_ids=row_ids, raw_rows=raw,
            facts=service, evidence=evidence, snippets=tuple(snippets), document=document,
            version=version, fact_request=request)
    return make
