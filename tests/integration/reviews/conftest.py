"""T18 synthetic reviewers in one dedicated, randomly isolated PG schema."""

import os
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.integration.facts.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, import_case_factory, evidence_store, evidence_factory,
    facts_store, facts_factory, classification_factory, fact_case_factory,
)


@pytest.fixture(autouse=True)
def isolate_reviews_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_", "REVIEWS_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL", "STORAGE_DATABASE_URL",
            "IMPORTS_DATABASE_URL", "EVIDENCE_DATABASE_URL", "IDEMPOTENCY_DATABASE_URL", "FACTS_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T18 forbids external connections")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T18 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T18_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T18 PostgreSQL check not executed: T18_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/reviews_t18_test":
        pytest.fail("T18 requires the dedicated loopback reviews_t18_test database", pytrace=False)
    schema = "reviews_t18_" + uuid4().hex
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
def reviews_store(facts_store, pg_engine):
    from services.api.app.reviews.store import ReviewsStore, migrate_reviews
    migrate_reviews(pg_engine)
    return ReviewsStore(pg_engine)


@pytest.fixture
def review_case_factory(fact_case_factory, classification_factory, candidate_factory,
        administrator_factory, reviews_store):
    """Whole original rows, explicit fields, and a separate synthetic reviewer."""
    from services.api.app.evidence.schemas import DocumentCreate, VersionCreate, SnippetCreate
    from services.api.app.reviews.schemas import ReviewPolicy
    from services.api.app.reviews.service import ReviewService
    def make(*, rows=None, classification=None, with_evidence=True, value_only=False, **changes):
        raw = rows if rows is not None else [candidate_factory(footnote_state="present",
            footnote_text="DEMO_Explicit source footnote for a synthetic manual review")]
        case = fact_case_factory(rows=raw, with_evidence=False, **changes)
        snippets = []
        if with_evidence:
            document = case.evidence.create_document(case.admin.principal, DocumentCreate(
                dataset_id=case.source.dataset_id, source_id=case.source.source_id, source_version=case.source.version,
                document_reference="DEMO_T18_DOCUMENT_" + uuid4().hex, language="und"))
            version = case.evidence.create_version(case.admin.principal, VersionCreate(document_id=document.id,
                expected_current_version=0, file_id=case.file.id, file_sha256=case.file.sha256))
            for row in raw:
                if value_only:
                    needle = row["value_text"].encode("utf-8")
                    start, end = case.data.index(needle), case.data.index(needle) + len(needle)
                else:
                    start, end = 0, len(case.data)
                snippets.append(case.evidence.create_snippet(case.admin.principal, SnippetCreate(
                    document_id=document.id, document_version=version.version, offering_id=row["offering_id"],
                    offering_version=row["offering_version"], entry_year=row["entry_year"], byte_start=start, byte_end=end)))
        selected = classification if classification is not None else classification_factory()
        candidates = tuple(case.facts.create_fact(case.admin.principal, case.fact_request(selected, index=index,
            evidence_id=snippets[index].id if snippets else None)) for index in range(len(raw)))
        reviewer = administrator_factory()
        assert reviewer.actor.user_id != case.admin.actor.user_id
        service = ReviewService(case.facts, reviews_store, ReviewPolicy(enabled=True))
        return SimpleNamespace(**vars(case), candidates=candidates, review_snippets=tuple(snippets),
            reviewer=reviewer, reviews=service)
    return make
