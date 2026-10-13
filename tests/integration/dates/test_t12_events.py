"""Independent T12 persistence checks; every saved deadline is synthetic."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
from threading import Barrier
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import create_engine, delete, event, inspect, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from services.api.app.admissions_catalog.date_models import CatalogDateEvent, DatesBase
from services.api.app.admissions_catalog.date_store import DateEventStore
from services.api.app.admissions_catalog.models import (
    AdmissionOffering, AdmissionOfferingVersion, CatalogBase, CatalogDataset, CatalogInstitution, CatalogProgram,
)
from services.api.app.admissions_catalog.schemas import DatasetInput
from services.api.app.admissions_catalog.store import CatalogStore, CatalogStoreError, migrate_catalog, migration_config


pytestmark = pytest.mark.postgres
CATALOG_TABLES = {"catalog_datasets", "catalog_institutions", "catalog_programs", "catalog_offerings", "catalog_offering_versions"}


def revision(store, session, tree):
    return store.get_dataset(session, tree.dataset.id).revision


def save(store, catalog_store, engine, tree, request):
    with Session(engine) as session, session.begin():
        return store.create_date_event(session, request,
            expected_dataset_revision=revision(catalog_store, session, tree))


def raw_rejects(engine, statement, sqlstate="23514"):
    with pytest.raises(DBAPIError) as failure:
        with engine.begin() as connection:
            connection.execute(statement)
    assert failure.value.orig.sqlstate == sqlstate, getattr(failure.value.orig.diag, "constraint_name", None)


def row_values(engine, model, identifier):
    with Session(engine) as session:
        row = session.get(model, identifier)
        return {column.name: getattr(row, column.name) for column in model.__table__.columns}


def test_explicit_date_upgrade_keeps_metadata_separate_and_does_no_startup_ddl(pg_engine):
    assert set(CatalogBase.metadata.tables) == CATALOG_TABLES
    assert set(DatesBase.metadata.tables) == {"catalog_date_events"}
    CatalogStore(pg_engine)
    DateEventStore(pg_engine)
    assert inspect(pg_engine).get_table_names() == []
    migrate_catalog(pg_engine, target="0001_catalog_t11")
    CatalogStore(pg_engine).assert_schema_ready(required_head="0001_catalog_t11")
    before = set(inspect(pg_engine).get_table_names())
    with pytest.raises(CatalogStoreError) as failure:
        CatalogStore(pg_engine).assert_schema_ready(required_head="0002_catalog_dates_t12")
    assert failure.value.status_code == 503
    assert set(inspect(pg_engine).get_table_names()) == before
    migrate_catalog(pg_engine, target="0002_catalog_dates_t12")
    migrate_catalog(pg_engine, target="0002_catalog_dates_t12")
    CatalogStore(pg_engine).assert_schema_ready(required_head="0002_catalog_dates_t12")
    assert set(inspect(pg_engine).get_table_names()) == CATALOG_TABLES | {"catalog_date_events", "catalog_alembic_version"}
    assert "entry_year" not in {column["name"] for column in inspect(pg_engine).get_columns("catalog_date_events")}
    assert set(CatalogBase.metadata.tables) == CATALOG_TABLES


def test_old_exact_version_remains_valid_and_parent_year_is_asserted(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    with Session(pg_engine) as session, session.begin():
        catalog_store.append_offering_version(session, catalog_tree.offering.id, version_id=uuid4(),
            expected_dataset_revision=revision(catalog_store, session, catalog_tree), expected_version=1)
    request = date_request_factory(offering_version=1)
    saved = save(date_store, catalog_store, pg_engine, catalog_tree, request)
    assert saved.offering_version == 1 and saved.entry_year == catalog_tree.offering.entry_year
    assert saved.review_state == "draft" and saved.evidence_state == "unresolved" and saved.utc_instant is None
    before = row_values(pg_engine, CatalogDataset, catalog_tree.dataset.id)
    for bad, expected in ((date_request_factory(entry_year=2027), 409),
                          (date_request_factory(offering_version=99), 404)):
        with pytest.raises(CatalogStoreError) as failure:
            save(date_store, catalog_store, pg_engine, catalog_tree, bad)
        assert failure.value.status_code == expected
        assert row_values(pg_engine, CatalogDataset, catalog_tree.dataset.id) == before
    with Session(pg_engine) as session, session.begin():
        assert date_store.get_date_event(session, saved.id) == saved


def test_raw_sql_cannot_cross_dataset_synthetic_or_exact_version_parent(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    saved = save(date_store, catalog_store, pg_engine, catalog_tree, date_request_factory())
    other = DatasetInput(id=uuid4(), reference_key="DEMO_OTHER_DATE_DATASET", data_mode="demo", is_synthetic=True)
    with Session(pg_engine) as session, session.begin():
        catalog_store.create_dataset(session, other)
        version_id = session.scalar(select(AdmissionOfferingVersion.id).where(
            AdmissionOfferingVersion.offering_id == catalog_tree.offering.id, AdmissionOfferingVersion.version == 1))
    target = CatalogDateEvent.id == saved.id
    for changes in ({"dataset_id": other.id}, {"offering_id": uuid4()}, {"offering_version": 99},
                    {"is_synthetic": False, "reference_key": "T12_REJECTED_FALSE_MARKER",
                     "evidence_reference": "T12_REJECTED_FALSE_EVIDENCE"}):
        raw_rejects(pg_engine, update(CatalogDateEvent).where(target).values(**changes), "23503")
    raw_rejects(pg_engine, delete(AdmissionOfferingVersion).where(AdmissionOfferingVersion.id == version_id), "23503")
    with Session(pg_engine) as session:
        assert session.get(CatalogDateEvent, saved.id) is not None
        assert session.get(AdmissionOfferingVersion, version_id) is not None


def test_duplicate_identity_rolls_back_but_distinct_events_can_coexist(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    request = date_request_factory(reference_key="DEMO_SHARED_REFERENCE")
    first = save(date_store, catalog_store, pg_engine, catalog_tree, request)
    before = row_values(pg_engine, CatalogDataset, catalog_tree.dataset.id)
    # Merely changing event kind must not circumvent the same candidate identity.
    with pytest.raises(CatalogStoreError) as failure:
        save(date_store, catalog_store, pg_engine, catalog_tree,
            request.model_copy(update={"id": uuid4(), "event_type": "equal_consideration"}))
    assert failure.value.status_code == 409
    assert row_values(pg_engine, CatalogDataset, catalog_tree.dataset.id) == before
    second = save(date_store, catalog_store, pg_engine, catalog_tree,
        date_request_factory(event_type="equal_consideration"))
    third = save(date_store, catalog_store, pg_engine, catalog_tree, date_request_factory())
    assert len({first.id, second.id, third.id}) == 3
    assert first.event_type != second.event_type and first.event_type == third.event_type


def test_concurrent_expected_revision_has_one_commit_and_no_partial_candidate(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    with Session(pg_engine) as session, session.begin():
        expected = revision(catalog_store, session, catalog_tree)
    requests = [date_request_factory(reference_key="DEMO_CONCURRENT_DATE") for _ in range(2)]
    barrier = Barrier(2)
    def write(request):
        barrier.wait(timeout=5)
        try:
            with Session(pg_engine) as session, session.begin():
                date_store.create_date_event(session, request, expected_dataset_revision=expected)
            return "committed"
        except CatalogStoreError as failure:
            assert failure.status_code == 409
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write, request) for request in requests]
        assert sorted(future.result(timeout=10) for future in futures) == ["committed", "conflict"]
    with Session(pg_engine) as session, session.begin():
        assert revision(catalog_store, session, catalog_tree) == expected + 1
        assert len(session.scalars(select(CatalogDateEvent)).all()) == 1


def test_caller_transaction_rolls_back_date_catalog_version_and_revision(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    before = row_values(pg_engine, CatalogDataset, catalog_tree.dataset.id)
    request = date_request_factory()
    with pytest.raises(RuntimeError, match="DEMO_T12_ABORT"):
        with Session(pg_engine) as session, session.begin():
            date_store.create_date_event(session, request,
                expected_dataset_revision=revision(catalog_store, session, catalog_tree))
            catalog_store.append_offering_version(session, catalog_tree.offering.id, version_id=uuid4(),
                expected_dataset_revision=revision(catalog_store, session, catalog_tree), expected_version=1)
            raise RuntimeError("DEMO_T12_ABORT")
    assert row_values(pg_engine, CatalogDataset, catalog_tree.dataset.id) == before
    with Session(pg_engine) as session:
        assert session.get(CatalogDateEvent, request.id) is None
        assert session.get(AdmissionOffering, catalog_tree.offering.id).current_version == 1
        assert session.scalars(select(AdmissionOfferingVersion.version)).all() == [1]


def test_postgresql_rejects_fake_review_utc_and_null_precision_loopholes(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    saved = save(date_store, catalog_store, pg_engine, catalog_tree, date_request_factory())
    target = CatalogDateEvent.id == saved.id
    for changes in ({"utc_instant": datetime(2026, 7, 15, 14, 30, tzinfo=timezone.utc)},
                    {"review_state": "ready"}, {"evidence_state": "resolved"},
                    {"conversion_status": "unknown_status"}, {"tzdata_version": "unverified"},
                    {"local_date": None}, {"local_time": None},
                    {"local_time": time(15, 30, 1)}, {"local_time": time(15, 30, microsecond=1)},
                    {"calculated_utc_instant": None},
                    {"timezone": None}, {"source_alignment": "conflict"}, {"offering_version": 0}):
        raw_rejects(pg_engine, update(CatalogDateEvent).where(target).values(**changes))
    raw_rejects(pg_engine, update(CatalogDateEvent).where(target).values(review_state="reviewed"), "22001")
    with Session(pg_engine) as session, session.begin():
        assert date_store.get_date_event(session, saved.id) == saved


def test_unresolved_candidates_persist_without_official_instant(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    cases = (
        (dict(source_alignment="conflict"), "source_conflict"),
        (dict(precision="date", local_time=None), "date_only"),
        (dict(timezone=None), "missing_timezone"),
        (dict(precision="unknown", local_date=None, local_time=None, timezone=None), "unknown"),
    )
    for fields, status in cases:
        saved = save(date_store, catalog_store, pg_engine, catalog_tree, date_request_factory(**fields))
        assert saved.conversion_status == status
        assert saved.calculated_utc_instant is None and saved.utc_instant is None
        assert saved.review_state == "draft" and saved.evidence_state == "unresolved"
        with Session(pg_engine) as session, session.begin():
            assert date_store.get_date_event(session, saved.id) == saved


def test_read_recomputes_and_denies_tampered_candidate_without_repair(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    saved = save(date_store, catalog_store, pg_engine, catalog_tree, date_request_factory())
    assert saved.conversion_status == "unique" and saved.calculated_utc_instant is not None
    altered = saved.calculated_utc_instant + timedelta(minutes=1)
    with pg_engine.begin() as connection:
        connection.execute(update(CatalogDateEvent).where(CatalogDateEvent.id == saved.id)
            .values(calculated_utc_instant=altered))
    with Session(pg_engine) as session, session.begin(), pytest.raises(CatalogStoreError) as failure:
        date_store.get_date_event(session, saved.id)
    assert failure.value.status_code == 503
    assert row_values(pg_engine, CatalogDateEvent, saved.id)["calculated_utc_instant"] == altered


def test_date_store_rejects_implicit_transaction_and_every_redirected_mapper(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory):
    request = date_request_factory()
    with Session(pg_engine) as session, pytest.raises(CatalogStoreError) as failure:
        date_store.create_date_event(session, request, expected_dataset_revision=1)
    assert failure.value.status_code == 503
    second = create_engine(pg_engine.url, hide_parameters=True)
    attempted = []
    def forbid_connect(*args):
        attempted.append(True)
        raise AssertionError("Wrong date mapper engine must be rejected before I/O")
    event.listen(second, "do_connect", forbid_connect)
    before = row_values(pg_engine, CatalogDataset, catalog_tree.dataset.id)
    try:
        for model in (CatalogDataset, CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion, CatalogDateEvent):
            with Session(pg_engine, binds={model: second}) as session, session.begin(), pytest.raises(CatalogStoreError) as failure:
                date_store.create_date_event(session, request, expected_dataset_revision=before["revision"])
            assert failure.value.status_code == 503
        assert attempted == []
    finally:
        second.dispose()
    assert row_values(pg_engine, CatalogDataset, catalog_tree.dataset.id) == before
    with Session(pg_engine) as session:
        assert session.get(CatalogDateEvent, request.id) is None


def test_upgrade_and_isolated_downgrade_preserve_existing_m0_auth_catalog(date_store, catalog_store, catalog_tree, pg_engine, date_request_factory, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.models import Base as M0Base
    from services.api.app.seed import seed
    from services.api.app.auth.models import AuthBase, AuthUser, AuthSession
    from services.api.app.auth.store import AuthStore, migrate_auth

    def downgrade_to_t11():
        config = migration_config()
        with pg_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0001_catalog_t11")

    downgrade_to_t11()
    monkeypatch.chdir(tmp_path)  # Never allow a user's M0 dotenv to choose policy.
    migrate_m0(pg_engine)
    seed(pg_engine)
    migrate_auth(pg_engine)
    now, user_id = datetime.now(timezone.utc), uuid4()
    with Session(pg_engine) as session, session.begin():
        session.add(AuthUser(id=user_id, status="active", is_synthetic=True, created_at=now))
        session.flush()
        session.add(AuthSession(id=uuid4(), user_id=user_id,
            session_digest=sha256(b"DEMO_T12_FROZEN_SESSION").hexdigest(), created_at=now,
            expires_at=now + timedelta(hours=1), revoked_at=None))
    def existing_snapshot():
        with pg_engine.connect() as connection:
            rows = {table.name: connection.execute(select(table).order_by(*table.primary_key.columns)).all()
                for metadata in (M0Base.metadata, AuthBase.metadata, CatalogBase.metadata)
                for table in metadata.tables.values()}
            heads = (connection.scalar(text("SELECT version_num FROM alembic_version")),
                connection.scalar(text("SELECT version_num FROM auth_alembic_version")))
        return rows, heads

    before = existing_snapshot()
    migrate_catalog(pg_engine, target="0002_catalog_dates_t12")
    migrate_catalog(pg_engine, target="0002_catalog_dates_t12")
    assert existing_snapshot() == before
    saved = save(date_store, catalog_store, pg_engine, catalog_tree, date_request_factory())
    before_downgrade = existing_snapshot()
    downgrade_to_t11()
    assert "catalog_date_events" not in inspect(pg_engine).get_table_names()
    assert existing_snapshot() == before_downgrade
    AuthStore(pg_engine).assert_schema_ready()
    CatalogStore(pg_engine).assert_schema_ready(required_head="0001_catalog_t11")
    migrate_catalog(pg_engine, target="0002_catalog_dates_t12")
    assert existing_snapshot() == before_downgrade
    with Session(pg_engine) as session:
        assert session.get(CatalogDateEvent, saved.id) is None  # Only the new date table was dropped.
    assert set(CatalogBase.metadata.tables) == CATALOG_TABLES
