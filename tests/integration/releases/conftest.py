"""T19 explicit DEMO test releases in one dedicated random PG schema."""

import os
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from tests.integration.reviews.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, evidence_store, evidence_factory,
    facts_store, facts_factory, classification_factory, fact_case_factory, reviews_store, review_case_factory,
)
from tests.integration.imports.conftest import serialize_rows


@pytest.fixture(autouse=True)
def isolate_releases_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_", "KEYCLOAK_", "RELEASES_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY", "CATALOG_DATABASE_URL", "STORAGE_DATABASE_URL",
            "IMPORTS_DATABASE_URL", "EVIDENCE_DATABASE_URL", "IDEMPOTENCY_DATABASE_URL", "FACTS_DATABASE_URL", "REVIEWS_DATABASE_URL",
        }:
            monkeypatch.delenv(name, raising=False)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T19 forbids external connections")
        monkeypatch.setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T19 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T19_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T19 PostgreSQL check not executed: T19_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/releases_t19_test":
        pytest.fail("T19 requires the dedicated loopback releases_t19_test database", pytrace=False)
    schema = "releases_t19_" + uuid4().hex
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
        source_store, pg_engine, imports_factory, candidate_factory):
    """Register an explicit synthetic manual AND public license before creating facts."""
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.ingestion.schemas import ImportRequest
    def make(*, rows=None, format="json", ttl_seconds=86400, data=None,
            publication_permission="granted", **admin_changes):
        administrator = administrator_factory(**admin_changes)
        storage = storage_factory(identity=administrator.service)
        source_request = source_request_factory(definition_updates={"manual_import_permission": "granted",
            "manual_import_enabled": True, "publication_permission": publication_permission,
            "license_basis": "DEMO_T19_EXPLICIT_MANUAL_AND_PUBLIC_LICENSE",
            "permission_record_reference": "DEMO_T19_PERMISSION"})
        with Session(pg_engine) as session:
            revision = session.get(CatalogDataset, source_request.dataset_id).revision
        source = storage.source_service.register_source(administrator.principal, source_request,
            expected_dataset_revision=revision)
        body = data if data is not None else serialize_rows(rows if rows is not None else [candidate_factory()], format)
        def upload(content=body, selected_format=format):
            return storage.upload_source(administrator.principal, source.source_id, expected_source_version=source.version,
                filename="DEMO_T19." + selected_format,
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
def releases_store(reviews_store, idempotency_store, pg_engine):
    from services.api.app.releases.store import ReleasesStore, migrate_releases
    migrate_releases(pg_engine)
    return ReleasesStore(pg_engine)


@pytest.fixture
def release_case_factory(review_case_factory, releases_store, pg_engine, clock):
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.idempotency.schemas import IdempotencyPolicy
    from services.api.app.idempotency.service import IdempotencyService
    from services.api.app.releases.schemas import PublishMember, PublishRequest, ReleasePolicy
    from services.api.app.releases.service import ReleaseService
    from services.api.app.reviews.schemas import CHECK_FIELDS, ReviewCheck, ReviewRequest, ConflictResolution
    from datetime import timedelta

    def make(*, approve=True, ttl_seconds=1, policy=None, **changes):
        case = review_case_factory(**changes)
        decisions = []
        if approve:
            for candidate in case.candidates:
                # Conflict sets are current server records, never supplied proof.
                current = case.facts.get_fact(case.reviewer.principal, candidate.id)
                decisions.append(case.reviews.decide(case.reviewer.principal, ReviewRequest(
                    fact_id=current.id, expected_fact_version=1, expected_case_revision=0, action="approve",
                    checks=tuple(ReviewCheck(field=field,
                        status="not_applicable" if field in ("statistics_context", "date_context") else "accepted")
                        for field in CHECK_FIELDS),
                    conflict_resolutions=tuple(ConflictResolution(fact_id=identifier, reason_code="INCORRECT_VALUE")
                        for identifier in current.conflicting_ids), return_reason=None)))
        old_idempotency = case.service.idempotency_service
        idem = IdempotencyService(old_idempotency.auth_service, old_idempotency.privacy_service,
            old_idempotency.store, IdempotencyPolicy(enabled=True, ttl_seconds=ttl_seconds))
        service = ReleaseService(case.reviews, idem, releases_store,
            policy=policy if policy is not None else ReleasePolicy(enabled=True, allow_test_releases=True))
        def request(*, members=None, **updates):
            with Session(pg_engine) as session:
                revision = session.get(CatalogDataset, case.source.dataset_id).revision
            values = dict(dataset_id=case.source.dataset_id, expected_dataset_revision=revision,
                entry_year=2026, kind="test_fixture", valid_from=clock(), valid_until=clock() + timedelta(hours=1),
                members=tuple(PublishMember(fact_id=decision.fact_id, expected_case_revision=decision.case_revision,
                    expected_decision_id=decision.decision_id, public_evidence=False) for decision in decisions)
                    if members is None else members,
                replaces_release_id=None, expected_replaced_state_revision=None)
            values.update(updates)
            return PublishRequest(**values)
        return SimpleNamespace(**vars(case), releases=service, release_idempotency=idem,
            decisions=tuple(decisions), publish_request=request)
    return make
