"""T11 synthetic-only tests in a dedicated, randomly isolated PostgreSQL schema."""

import os
import socket
from urllib.parse import urlsplit
from uuid import uuid4
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.fixture(autouse=True)
def isolate_catalog_environment_and_network(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "IDENTITY_", "AUTH_", "OIDC_", "PRIVACY_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY",
        }:
            monkeypatch.delenv(name, raising=False)
    for method in ("connect", "connect_ex"):
        original = getattr(socket.socket, method)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T11 forbids external connections")
        monkeypatch.setattr(socket.socket, method, guarded)
    original_dns = socket.getaddrinfo
    def guarded_dns(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_dns(host, *args, **kwargs)
        raise AssertionError("T11 forbids external DNS")
    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)


@pytest.fixture
def pg_engine():
    url = os.getenv("T11_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T11 PostgreSQL check not executed: T11_TEST_POSTGRES_URL missing", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/catalog_t11_test":
        pytest.fail("T11 requires the dedicated loopback catalog_t11_test database", pytrace=False)
    schema = "catalog_t11_" + uuid4().hex
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
def catalog_store(pg_engine):
    from services.api.app.admissions_catalog.store import CatalogStore, migrate_catalog
    migrate_catalog(pg_engine)
    return CatalogStore(pg_engine)


@pytest.fixture
def catalog_tree(catalog_store, pg_engine):
    """Every persisted catalog identity is explicitly synthetic and DEMO-labelled."""
    from sqlalchemy.orm import Session
    from services.api.app.admissions_catalog.schemas import (
        DatasetInput, InstitutionInput, ProgramInput, OfferingInput, ScopeKey,
    )
    def known(value):
        return ScopeKey(status="known", value=value)
    dataset = DatasetInput(id=uuid4(), reference_key="DEMO_DATASET", data_mode="demo", is_synthetic=True)
    institution = InstitutionInput(id=uuid4(), dataset_id=dataset.id, reference_key="DEMO_INSTITUTION",
        name="DEMO_SHARED_DISPLAY_NAME", country="CN", is_synthetic=True)
    program = ProgramInput(id=uuid4(), dataset_id=dataset.id, institution_id=institution.id,
        reference_key="DEMO_PROGRAM", name="DEMO_PROGRAM_NAME", study_level="undergraduate",
        degree=known("DEMO_DEGREE"), course=known("DEMO_COURSE"), campus=known("DEMO_CAMPUS"),
        teaching_language=known("DEMO_LANGUAGE"), progression_pathway=known("DEMO_PROGRESSION"), is_synthetic=True)
    offering = OfferingInput(id=uuid4(), dataset_id=dataset.id, program_id=program.id,
        reference_key="DEMO_OFFERING", is_synthetic=True, entry_year=2026,
        **{name: known("DEMO_" + name.upper()) for name in (
            "intake", "application_cycle", "channel", "course_system", "pathway", "applicant_category",
            "province", "exam_system", "subject_scope", "batch_group")})
    with Session(pg_engine) as session, session.begin():
        catalog_store.create_dataset(session, dataset)
        catalog_store.create_institution(session, institution,
            expected_dataset_revision=catalog_store.get_dataset(session, dataset.id).revision)
        catalog_store.create_program(session, program,
            expected_dataset_revision=catalog_store.get_dataset(session, dataset.id).revision)
        current = catalog_store.create_offering(session, offering,
            expected_dataset_revision=catalog_store.get_dataset(session, dataset.id).revision, version_id=uuid4())
    return SimpleNamespace(dataset=dataset, institution=institution, program=program, offering=offering, current=current)
