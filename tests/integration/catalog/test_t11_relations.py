"""Independent PostgreSQL invariants for unpublished, explicitly DEMO candidates."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Barrier
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import create_engine, delete, event, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from services.api.app.admissions_catalog.models import (
    CatalogBase, CatalogDataset, CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion,
)
from services.api.app.admissions_catalog.schemas import DatasetInput, OfferingVersionRef, ScopeKey
from services.api.app.admissions_catalog.store import CatalogStore, CatalogStoreError, migrate_catalog, migration_config


pytestmark = pytest.mark.postgres
OFFERING_SCOPES = ("intake", "application_cycle", "channel", "course_system", "pathway", "applicant_category",
                   "province", "exam_system", "subject_scope", "batch_group")
CATALOG_TABLES = {"catalog_datasets", "catalog_institutions", "catalog_programs", "catalog_offerings",
                  "catalog_offering_versions", "catalog_alembic_version"}


def known(value):
    return ScopeKey(status="known", value=value)


def current_revision(store, session, tree):
    return store.get_dataset(session, tree.dataset.id).revision


def stored_row(engine, model, identifier):
    with Session(engine) as session:
        row = session.get(model, identifier)
        return {column.name: getattr(row, column.name) for column in model.__table__.columns}


def constraint_rejects(engine, statement, sqlstate):
    with pytest.raises(DBAPIError) as failure:
        with engine.begin() as connection:
            connection.execute(statement)
    assert failure.value.orig.sqlstate == sqlstate


def register_offering(store, engine, tree, **changes):
    changes = {"id": uuid4(), "reference_key": "DEMO_ALTERNATE_" + uuid4().hex, **changes}
    request = tree.offering.model_copy(update=changes)
    with Session(engine) as session, session.begin():
        return store.create_offering(session, request, expected_dataset_revision=current_revision(store, session, tree),
            version_id=uuid4())


def test_empty_explicit_upgrade_and_repeat_are_non_destructive(pg_engine):
    assert inspect(pg_engine).get_table_names() == []
    store = CatalogStore(pg_engine)
    # Constructor cannot create persistence implicitly.
    assert inspect(pg_engine).get_table_names() == []
    migrate_catalog(pg_engine, target="0001_catalog_t11")
    assert set(inspect(pg_engine).get_table_names()) == CATALOG_TABLES
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM catalog_alembic_version")) == "0001_catalog_t11"
    migrate_catalog(pg_engine, target="0001_catalog_t11")
    assert set(inspect(pg_engine).get_table_names()) == CATALOG_TABLES
    assert set(CatalogBase.metadata.tables) == CATALOG_TABLES - {"catalog_alembic_version"}


def test_identical_institution_names_do_not_merge_ids(catalog_store, catalog_tree, pg_engine):
    first = catalog_tree.institution
    second = first.model_copy(update={"id": uuid4(), "reference_key": "DEMO_SECOND_INSTITUTION"})
    with Session(pg_engine) as session, session.begin():
        catalog_store.create_institution(session, second,
            expected_dataset_revision=current_revision(catalog_store, session, catalog_tree))
    with Session(pg_engine) as session:
        rows = session.scalars(select(CatalogInstitution).where(CatalogInstitution.name == first.name)).all()
        assert {row.id for row in rows} == {first.id, second.id}


@pytest.mark.parametrize("field", ("entry_year", *OFFERING_SCOPES))
def test_each_admissions_dimension_can_coexist_without_collision(catalog_store, catalog_tree, pg_engine, field):
    value = 2027 if field == "entry_year" else known("DEMO_DISTINCT_" + field.upper())
    second = register_offering(catalog_store, pg_engine, catalog_tree, **{field: value})
    with Session(pg_engine) as session:
        assert session.get(AdmissionOffering, catalog_tree.offering.id) is not None
        assert session.get(AdmissionOffering, second.id) is not None
        assert session.scalar(select(AdmissionOfferingVersion.id).where(AdmissionOfferingVersion.offering_id == second.id,
            AdmissionOfferingVersion.version == 1)) is not None


def test_program_campus_and_other_scope_changes_preserve_distinct_projects(catalog_store, catalog_tree, pg_engine):
    identifiers = {catalog_tree.program.id}
    for field in ("degree", "course", "campus", "teaching_language", "progression_pathway"):
        request = catalog_tree.program.model_copy(update={"id": uuid4(), field: known("DEMO_SECOND_" + field.upper())})
        with Session(pg_engine) as session, session.begin():
            item = catalog_store.create_program(session, request,
                expected_dataset_revision=current_revision(catalog_store, session, catalog_tree))
        identifiers.add(item.id)
    with Session(pg_engine) as session:
        rows = session.scalars(select(CatalogProgram).where(CatalogProgram.reference_key == catalog_tree.program.reference_key)).all()
        assert {row.id for row in rows} == identifiers


def test_missing_and_not_applicable_keys_are_nonnull_distinct_and_case_exact(catalog_store, catalog_tree, pg_engine):
    values = [ScopeKey(status="unknown", value=None), ScopeKey(status="not_applicable", value=None),
        known("DEMO_CASE"), known("demo_case")]
    ids = [register_offering(catalog_store, pg_engine, catalog_tree, province=value).id for value in values]
    with Session(pg_engine) as session:
        rows = session.scalars(select(AdmissionOffering).where(AdmissionOffering.id.in_(ids))).all()
        assert {row.province_key for row in rows} == {"unknown", "not_applicable", "known:DEMO_CASE", "known:demo_case"}
        assert all(getattr(row, field + "_key") is not None for row in rows for field in OFFERING_SCOPES)


def test_changing_reference_cannot_bypass_complete_business_key_duplicate(catalog_store, catalog_tree, pg_engine):
    old_revision = stored_row(pg_engine, CatalogDataset, catalog_tree.dataset.id)["revision"]
    with pytest.raises(CatalogStoreError) as error:
        register_offering(catalog_store, pg_engine, catalog_tree)
    assert error.value.status_code == 409
    assert stored_row(pg_engine, CatalogDataset, catalog_tree.dataset.id)["revision"] == old_revision
    with Session(pg_engine) as session:
        assert len(session.scalars(select(AdmissionOffering)).all()) == 1
        assert len(session.scalars(select(AdmissionOfferingVersion)).all()) == 1


def test_raw_sql_concurrent_complete_key_duplicates_have_one_committed_winner(catalog_tree, pg_engine):
    values = stored_row(pg_engine, AdmissionOffering, catalog_tree.offering.id)
    values["entry_year"] = 2030
    start = Barrier(2)
    def write_candidate(index):
        candidate = {**values, "id": uuid4(), "reference_key": f"DEMO_CONCURRENT_{index}"}
        start.wait(timeout=5)
        try:
            with pg_engine.begin() as connection:
                connection.execute(AdmissionOffering.__table__.insert().values(**candidate))
                connection.execute(AdmissionOfferingVersion.__table__.insert().values(id=uuid4(),
                    dataset_id=candidate["dataset_id"], offering_id=candidate["id"], version=1, is_synthetic=True))
            return "committed"
        except IntegrityError as failure:
            assert failure.orig.sqlstate == "23505"
            return "duplicate"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write_candidate, index) for index in (1, 2)]
        assert sorted(future.result(timeout=10) for future in futures) == ["committed", "duplicate"]
    with Session(pg_engine) as session:
        rows = session.scalars(select(AdmissionOffering).where(AdmissionOffering.entry_year == 2030)).all()
        assert len(rows) == 1
        assert session.scalar(select(AdmissionOfferingVersion.id).where(AdmissionOfferingVersion.offering_id == rows[0].id)) is not None


@pytest.mark.parametrize("model", (CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion),
    ids=("institution", "program", "offering", "version"))
def test_composite_dataset_and_synthetic_foreign_keys_reject_raw_sql(catalog_store, catalog_tree, pg_engine, model):
    other = DatasetInput(id=uuid4(), reference_key="DEMO_SECOND_DATASET", data_mode="demo", is_synthetic=True)
    with Session(pg_engine) as session, session.begin():
        catalog_store.create_dataset(session, other)
    with Session(pg_engine) as session:
        row = session.scalars(select(model)).one()
        identifier = row.id
    constraint_rejects(pg_engine, update(model).where(model.id == identifier).values(dataset_id=other.id), "23503")
    changes = {"is_synthetic": False}
    if model is not AdmissionOfferingVersion:
        changes["reference_key"] = "T11_REJECTED_FALSE_MARKER"
    if model in (CatalogInstitution, CatalogProgram):
        changes["name"] = "T11_REJECTED_FALSE_MARKER"
    constraint_rejects(pg_engine, update(model).where(model.id == identifier).values(**changes), "23503")
    if model is CatalogProgram:
        changes = {"institution_id": uuid4()}
    elif model is AdmissionOffering:
        changes = {"program_id": uuid4()}
    elif model is AdmissionOfferingVersion:
        changes = {"offering_id": uuid4()}
    else:
        changes = {"dataset_id": uuid4()}
    constraint_rejects(pg_engine, update(model).where(model.id == identifier).values(**changes), "23503")


def test_dataset_mode_visibility_and_revision_are_checked_by_postgresql(catalog_tree, pg_engine):
    for changes in ({"data_mode": "verified"}, {"visibility": "public"}, {"revision": 0},
        {"is_synthetic": False}, {"reference_key": "UNCHECKED_REAL_NAMESPACE"}):
        constraint_rejects(pg_engine, update(CatalogDataset).where(CatalogDataset.id == catalog_tree.dataset.id)
            .values(**changes), "23514")


@pytest.mark.parametrize("model,field", ((CatalogDataset, "dataset"), (CatalogInstitution, "institution"), (CatalogProgram, "program")),
    ids=("dataset", "institution", "program"))
def test_parent_deletion_cannot_cascade_away_opportunity_history(catalog_tree, pg_engine, model, field):
    identifier = getattr(catalog_tree, field).id
    constraint_rejects(pg_engine, delete(model).where(model.id == identifier), "23503")
    with Session(pg_engine) as session:
        assert session.get(model, identifier) is not None
        assert session.get(AdmissionOffering, catalog_tree.offering.id) is not None
        assert len(session.scalars(select(AdmissionOfferingVersion)).all()) == 1


def test_append_has_exact_version_references_and_stale_proofs_rollback(catalog_store, catalog_tree, pg_engine):
    old_ref = OfferingVersionRef(dataset_id=catalog_tree.dataset.id, offering_id=catalog_tree.offering.id, version=1)
    with Session(pg_engine) as session, session.begin():
        old = catalog_store.get_offering_version(session, old_ref)
        new = catalog_store.append_offering_version(session, catalog_tree.offering.id, version_id=uuid4(),
            expected_dataset_revision=current_revision(catalog_store, session, catalog_tree), expected_version=1)
    assert new.version == 2 and new.id != old.id
    for stale in ("dataset", "version"):
        with pytest.raises(CatalogStoreError) as error:
            with Session(pg_engine) as session, session.begin():
                revision = current_revision(catalog_store, session, catalog_tree)
                catalog_store.append_offering_version(session, catalog_tree.offering.id, version_id=uuid4(),
                    expected_dataset_revision=revision - 1 if stale == "dataset" else revision,
                    expected_version=1 if stale == "version" else 2)
        assert error.value.status_code == 409
    with Session(pg_engine) as session, session.begin():
        assert catalog_store.get_offering_version(session, old_ref) == old
        assert catalog_store.get_offering(session, catalog_tree.offering.id).current_version == 2
        assert session.scalars(select(AdmissionOfferingVersion.version).order_by(AdmissionOfferingVersion.version)).all() == [1, 2]


def test_external_transaction_rollback_preserves_rows_and_version_counter(catalog_store, catalog_tree, pg_engine):
    before = stored_row(pg_engine, CatalogDataset, catalog_tree.dataset.id)
    extra_id = uuid4()
    with pytest.raises(RuntimeError, match="DEMO_T11_ROLLBACK"):
        with Session(pg_engine) as session, session.begin():
            catalog_store.create_institution(session, catalog_tree.institution.model_copy(update={
                "id": extra_id, "reference_key": "DEMO_ROLLBACK_INSTITUTION"}),
                expected_dataset_revision=current_revision(catalog_store, session, catalog_tree))
            catalog_store.append_offering_version(session, catalog_tree.offering.id, version_id=uuid4(),
                expected_dataset_revision=current_revision(catalog_store, session, catalog_tree), expected_version=1)
            raise RuntimeError("DEMO_T11_ROLLBACK")
    assert stored_row(pg_engine, CatalogDataset, catalog_tree.dataset.id) == before
    with Session(pg_engine) as session:
        assert session.get(CatalogInstitution, extra_id) is None
        assert session.get(AdmissionOffering, catalog_tree.offering.id).current_version == 1
        assert session.scalars(select(AdmissionOfferingVersion.version)).all() == [1]


def test_store_requires_explicit_transaction_and_same_engine(catalog_store, pg_engine):
    request = DatasetInput(id=uuid4(), reference_key="DEMO_NO_TRANSACTION", data_mode="demo", is_synthetic=True)
    with Session(pg_engine) as session, pytest.raises(CatalogStoreError) as error:
        catalog_store.create_dataset(session, request)
    assert error.value.status_code == 503
    other = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with Session(other) as session, session.begin(), pytest.raises(CatalogStoreError) as error:
            catalog_store.create_dataset(session, request)
        assert error.value.status_code == 503
        assert inspect(other).get_table_names() == []
    finally:
        other.dispose()
    # A correct default bind is insufficient: per-mapper routing can redirect
    # catalog reads/writes into another engine even inside the same Session.
    routed_engine = create_engine(pg_engine.url, hide_parameters=True)
    attempted_connections = []
    def refuse_connection(*args):
        attempted_connections.append(True)
        raise AssertionError("Catalog mapper routing must be rejected before I/O")
    event.listen(routed_engine, "do_connect", refuse_connection)
    try:
        for model in (CatalogDataset, CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion):
            with Session(pg_engine, binds={model: routed_engine}) as session, session.begin():
                assert session.get_bind() is pg_engine
                assert session.get_bind(mapper=model) is routed_engine
                with pytest.raises(CatalogStoreError) as error:
                    catalog_store.create_dataset(session, request)
                assert error.value.status_code == 503
        assert attempted_connections == []
    finally:
        routed_engine.dispose()
    with Session(pg_engine) as session:
        assert session.get(CatalogDataset, request.id) is None


def test_raw_scope_keys_and_versions_cannot_bypass_canonical_checks(catalog_tree, pg_engine):
    target = AdmissionOffering.id == catalog_tree.offering.id
    constraint_rejects(pg_engine, update(AdmissionOffering).where(target).values(province_key=None), "23502")
    for value in ("", "known:", "KNOWN:DEMO_SCOPE", "unknown:DEMO_SCOPE", "known: DEMO_SCOPE", "known:DEMO_SCOPE\n",
                  "known:" + "汉" * 90):
        constraint_rejects(pg_engine, update(AdmissionOffering).where(target).values(province_key=value), "23514")
    # PostgreSQL's varchar bound rejects the overlong value before CHECK evaluation.
    constraint_rejects(pg_engine, update(AdmissionOffering).where(target)
        .values(province_key="known:" + "x" * 101), "22001")
    constraint_rejects(pg_engine, update(AdmissionOffering).where(target).values(current_version=0), "23514")
    with Session(pg_engine) as session:
        version_id = session.scalars(select(AdmissionOfferingVersion.id)).one()
    constraint_rejects(pg_engine, update(AdmissionOfferingVersion).where(AdmissionOfferingVersion.id == version_id).values(version=0), "23514")


def test_catalog_upgrade_repeat_and_isolated_downgrade_preserve_m0_and_auth(pg_engine, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.seed import seed
    from services.api.app.models import Base as M0Base
    from services.api.app.auth.models import AuthUser, AuthSession
    from services.api.app.auth.store import migrate_auth, AuthStore
    monkeypatch.chdir(tmp_path)  # User dotenv cannot alter this isolated seed context.
    migrate_m0(pg_engine)
    seed(pg_engine)
    migrate_auth(pg_engine)
    now, user_id, session_id = datetime.now(timezone.utc), uuid4(), uuid4()
    with Session(pg_engine) as session, session.begin():
        session.add(AuthUser(id=user_id, status="active", is_synthetic=True, created_at=now))
        session.flush()
        session.add(AuthSession(id=session_id, user_id=user_id, session_digest=sha256(b"DEMO_T11_EXISTING_COOKIE").hexdigest(),
            created_at=now, expires_at=now + timedelta(hours=1), revoked_at=None))
    def snapshot():
        with pg_engine.connect() as connection:
            legacy = {name: connection.execute(select(table).order_by(*table.primary_key.columns)).all()
                for name, table in M0Base.metadata.tables.items()}
            heads = (connection.scalar(text("SELECT version_num FROM alembic_version")),
                connection.scalar(text("SELECT version_num FROM auth_alembic_version")))
            users = connection.execute(select(AuthUser).order_by(AuthUser.id)).all()
            sessions = connection.execute(select(AuthSession).order_by(AuthSession.id)).all()
        return legacy, heads, users, sessions
    before = snapshot()
    migrate_catalog(pg_engine, target="0001_catalog_t11")
    migrate_catalog(pg_engine, target="0001_catalog_t11")
    assert snapshot() == before
    config = migration_config()
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert not (set(inspect(pg_engine).get_table_names()) & (CATALOG_TABLES - {"catalog_alembic_version"}))
    assert snapshot() == before
    AuthStore(pg_engine).assert_schema_ready()
    migrate_catalog(pg_engine, target="0001_catalog_t11")
    assert snapshot() == before
    assert CATALOG_TABLES.issubset(inspect(pg_engine).get_table_names())
