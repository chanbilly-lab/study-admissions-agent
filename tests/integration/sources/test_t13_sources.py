"""Independent T13 PostgreSQL trust, concurrency and migration acceptance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from threading import Barrier, Event
from time import monotonic
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, delete, event, func, inspect, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion, SourceBase
from services.api.app.admin.sources.schemas import SourcePolicy, SourceRevisionInput
from services.api.app.admin.sources.service import SourceService
from services.api.app.admissions_catalog.models import (
    AdmissionOffering, AdmissionOfferingVersion, CatalogBase, CatalogDataset, CatalogInstitution, CatalogProgram,
)
from services.api.app.admissions_catalog.date_models import CatalogDateEvent, DatesBase
from services.api.app.admissions_catalog.store import CatalogStore, CatalogStoreError, migrate_catalog, migration_config
from services.api.app.audit.models import AuditEvent
from services.api.app.auth.assurance import AdminAssurancePolicy
from services.api.app.auth.authorization import AuthorizationError
from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.models import AuthSession, AuthUser, AuthUserRole


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T13_PRIVATE_SOURCE_URL_AND_LICENSE_SENTINEL"


def status(operation, expected):
    with pytest.raises((AuthFlowError, CatalogStoreError)) as failure:
        operation()
    assert failure.value.status_code == expected
    assert SENTINEL not in str(failure.value) and SENTINEL not in repr(failure.value)
    return failure.value


def revision(engine, dataset_id):
    with Session(engine) as session:
        return session.get(CatalogDataset, dataset_id).revision


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns)).mappings().all()


def successes(engine):
    return [row for row in rows(engine, AuditEvent) if row["action"] == "administrator.action" and row["outcome"] == "succeeded"]


def register(service, principal, engine, request):
    return service.register_source(principal, request, expected_dataset_revision=revision(engine, request.dataset_id))


def granted_request(factory, **updates):
    return factory(definition_updates=dict(manual_import_permission="granted", publication_permission="denied",
        automated_fetch_permission="granted", license_basis="DEMO_EXPLICIT_SYNTHETIC_PERMISSION_STATEMENT",
        permission_record_reference="DEMO_PERMISSION_RECORD", manual_import_enabled=True), **updates)


def test_official_claim_never_grants_rights_and_audit_contains_only_verified_actor(source_service,
        administrator, source_request_factory, catalog_tree, pg_engine, clock):
    request = source_request_factory()
    saved = register(source_service, administrator.principal, pg_engine, request)
    assert saved.source_id == request.id and saved.version == 1 and saved.dataset_id == request.dataset_id
    assert saved.responsible_user_id == administrator.actor.user_id
    assert saved.authority_claim == "claimed_official"
    assert (saved.manual_import_permission, saved.publication_permission, saved.automated_fetch_permission) == ("pending",) * 3
    assert saved.manual_import_enabled is False and saved.auto_fetch_enabled is False
    assert saved.permission_reviewed_at is None and saved.created_at == clock()
    assert saved.recheck_due_at == clock() + timedelta(days=1)
    assert revision(pg_engine, catalog_tree.dataset.id) == 5
    record = successes(pg_engine)[-1]
    assert record["actor_user_id"] == administrator.actor.user_id
    assert record["actor_session_id"] == administrator.actor.session_id
    assert record["object_type"] is None and record["object_id"] is None and record["object_version"] is None
    assert "sources.test.invalid" not in repr(record) and "SYNTHETIC_PUBLISHER" not in repr(record)


def test_revision_appends_exact_snapshot_and_old_version_survives(source_service, administrator,
        source_request_factory, pg_engine, clock):
    request = source_request_factory()
    first = register(source_service, administrator.principal, pg_engine, request)
    next_request = granted_request(source_request_factory)
    second = source_service.revise_source(administrator.principal,
        SourceRevisionInput(source_id=first.source_id, definition=next_request.definition),
        expected_dataset_revision=revision(pg_engine, first.dataset_id), expected_source_version=1)
    assert second.source_id == first.source_id and second.id != first.id and second.version == 2
    assert second.permission_reviewed_at == clock() and second.responsible_user_id == administrator.actor.user_id
    assert second.manual_import_enabled is True and second.publication_permission == "denied" and second.auto_fetch_enabled is False
    assert source_service.get_source_version(administrator.principal, first.source_id, 1) == first
    assert source_service.get_source_version(administrator.principal, first.source_id) == second
    assert len(rows(pg_engine, CatalogSourceVersion)) == 2
    status(lambda: source_service.revise_source(administrator.principal,
        SourceRevisionInput(source_id=first.source_id, definition=request.definition),
        expected_dataset_revision=revision(pg_engine, first.dataset_id), expected_source_version=1), 409)
    assert len(rows(pg_engine, CatalogSourceVersion)) == 2
    # Privileged SQL installs a historical snapshot; this is not a permission
    # promotion. Reading its declaration does not authorize later use/import.
    with pg_engine.begin() as connection:
        connection.execute(update(CatalogSourceVersion).where(CatalogSourceVersion.id == second.id).values(
            created_at=clock() - timedelta(days=1), permission_reviewed_at=clock() - timedelta(days=1),
            recheck_due_at=clock()))
    historical = source_service.get_source_version(administrator.principal, first.source_id, 2)
    assert historical.manual_import_enabled is True and historical.recheck_due_at == clock()


@pytest.mark.parametrize("role", [None, "student", "operations"])
def test_current_data_admin_role_is_required_even_with_valid_mfa(source_store, administrator_factory,
        source_request_factory, pg_engine, role):
    actor = administrator_factory(role=role)
    service = SourceService(actor.service, source_store, SourcePolicy(enabled=True))
    request = source_request_factory()
    forged = actor.principal.model_copy(update={"roles": ("data_admin",)})
    before = revision(pg_engine, request.dataset_id)
    status(lambda: service.register_source(forged, request, expected_dataset_revision=before), 403)
    assert rows(pg_engine, CatalogSource) == [] and revision(pg_engine, request.dataset_id) == before


def test_current_role_session_and_signed_provenance_override_stale_principal(source_store, administrator_factory,
        source_request_factory, pg_engine, clock):
    for change in ("role", "session", "issuer", "client", "assurance", "policy"):
        actor = administrator_factory()
        service = SourceService(actor.service, source_store, SourcePolicy(enabled=True))
        request = source_request_factory()
        if change == "role":
            actor.service.store.revoke_role(actor.actor.user_id, "data_admin", now=clock())
        elif change == "policy":
            actor.service.settings = actor.service.settings.model_copy(update={"admin_assurance_policy": AdminAssurancePolicy()})
        else:
            with Session(pg_engine) as session, session.begin():
                row = session.get(AuthSession, actor.actor.session_id)
                if change == "session":
                    row.revoked_at = clock()
                elif change == "issuer":
                    row.verified_issuer = "https://foreign.test.invalid/realms/students"
                elif change == "client":
                    row.verified_client_id = "T13_STUDENT_CLIENT"
                else:
                    row.assurance_amr = ["pwd"]
        status(lambda: register(service, actor.principal, pg_engine, request), 401 if change == "session" else 403)
    assert rows(pg_engine, CatalogSource) == []


def test_closed_policy_and_real_responsibility_are_not_implicit(source_store, administrator,
        administrator_factory, source_request_factory, catalog_store, pg_engine):
    from services.api.app.admissions_catalog.schemas import DatasetInput
    request = source_request_factory()
    closed = SourceService(administrator.service, source_store)
    status(lambda: register(closed, administrator.principal, pg_engine, request), 503)
    # A synthetic negative fixture representing an unready real-data namespace,
    # with no fetched institution, admissions fact or real user's information.
    dataset = DatasetInput(id=uuid4(), reference_key="T13_UNREADY_CANDIDATE", data_mode="verified", is_synthetic=False)
    with Session(pg_engine) as session, session.begin():
        catalog_store.create_dataset(session, dataset)
    actor = administrator_factory(is_synthetic=False)
    real_request = source_request_factory(dataset_id=dataset.id, reference_key="T13_UNREADY_SOURCE", is_synthetic=False,
        definition_updates={"publisher": "T13 unready candidate label"})
    missing = SourceService(actor.service, source_store, SourcePolicy(enabled=True))
    status(lambda: register(missing, actor.principal, pg_engine, real_request), 503)
    wrong_list = SourceService(actor.service, source_store,
        SourcePolicy(enabled=True, real_sources_ready=True, responsible_user_ids=(uuid4(),)))
    status(lambda: register(wrong_list, actor.principal, pg_engine, real_request), 503)
    assert rows(pg_engine, CatalogSource) == [] and revision(pg_engine, dataset.id) == 1


def test_caller_transaction_owns_source_dataset_and_success_audit_rollback(source_service, administrator,
        source_request_factory, pg_engine):
    request = source_request_factory()
    before = revision(pg_engine, request.dataset_id), successes(pg_engine)
    with pytest.raises(RuntimeError, match="caller rollback"):
        with Session(pg_engine) as session, session.begin():
            saved = source_service.register_source(administrator.principal, request,
                expected_dataset_revision=before[0], session=session)
            assert session.get(CatalogSourceVersion, saved.id) is not None
            assert session.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.action == "administrator.action", AuditEvent.outcome == "succeeded")) == len(before[1]) + 1
            raise RuntimeError("caller rollback")
    assert rows(pg_engine, CatalogSource) == [] and rows(pg_engine, CatalogSourceVersion) == []
    assert (revision(pg_engine, request.dataset_id), successes(pg_engine)) == before


def test_required_audit_database_failure_rolls_back_source_and_hides_sensitive_input(source_service,
        administrator, source_request_factory, pg_engine):
    request = source_request_factory(definition_updates={"entry_url": "https://sources.test.invalid/" + SENTINEL})
    before = revision(pg_engine, request.dataset_id), successes(pg_engine)
    def fault(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO auth_audit_events") and parameters.get("action") == "administrator.action":
            raise RuntimeError(SENTINEL)
    event.listen(pg_engine, "before_cursor_execute", fault)
    try:
        status(lambda: source_service.register_source(administrator.principal, request, expected_dataset_revision=before[0]), 503)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fault)
    assert rows(pg_engine, CatalogSource) == [] and rows(pg_engine, CatalogSourceVersion) == []
    assert (revision(pg_engine, request.dataset_id), successes(pg_engine)) == before


def test_explicit_transaction_and_all_mapper_bindings_rejected_before_foreign_io(source_service,
        administrator, source_request_factory, pg_engine):
    request = source_request_factory()
    before = revision(pg_engine, request.dataset_id)
    with Session(pg_engine) as session:
        status(lambda: source_service.register_source(administrator.principal, request,
            expected_dataset_revision=before, session=session), 503)
    foreign = create_engine(pg_engine.url, hide_parameters=True)
    attempted = []
    def forbidden_connect(*args):
        attempted.append(True)
        raise AssertionError("A redirected mapper must be rejected before any foreign connection")
    event.listen(foreign, "do_connect", forbidden_connect)
    try:
        for model in (AuthUser, AuthSession, AuthUserRole, AuditEvent, CatalogDataset, CatalogInstitution,
                CatalogProgram, AdmissionOffering, AdmissionOfferingVersion, CatalogDateEvent, CatalogSource, CatalogSourceVersion):
            with Session(pg_engine, binds={model: foreign}) as session, session.begin():
                status(lambda: source_service.register_source(administrator.principal, request,
                    expected_dataset_revision=before, session=session), 503)
        assert attempted == []
    finally:
        foreign.dispose()
    assert rows(pg_engine, CatalogSource) == [] and revision(pg_engine, request.dataset_id) == before


def test_two_concurrent_revisions_have_one_winner_and_no_lost_history(source_service, administrator,
        source_request_factory, pg_engine):
    first = register(source_service, administrator.principal, pg_engine, source_request_factory())
    expected = revision(pg_engine, first.dataset_id)
    barrier = Barrier(2)
    def revise(label):
        definition = source_request_factory(definition_updates={"scope_note": "DEMO_" + label}).definition
        barrier.wait(timeout=5)
        try:
            result = source_service.revise_source(administrator.principal,
                SourceRevisionInput(source_id=first.source_id, definition=definition),
                expected_dataset_revision=expected, expected_source_version=1)
            return result.version
        except CatalogStoreError as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(revise, ("CONCURRENT_A", "CONCURRENT_B")))
    assert sorted(results) == [2, 409]
    assert revision(pg_engine, first.dataset_id) == expected + 1
    assert len(rows(pg_engine, CatalogSourceVersion)) == 2
    assert rows(pg_engine, CatalogSource)[0]["current_version"] == 2
    assert source_service.get_source_version(administrator.principal, first.source_id, 1) == first


def test_raw_sql_composite_foreign_keys_permissions_and_parent_delete_are_enforced(source_service,
        administrator, source_request_factory, catalog_store, pg_engine):
    from services.api.app.admissions_catalog.schemas import DatasetInput
    saved = register(source_service, administrator.principal, pg_engine, source_request_factory())
    another = DatasetInput(id=uuid4(), reference_key="DEMO_OTHER_SOURCE_DATASET", data_mode="demo", is_synthetic=True)
    with Session(pg_engine) as session, session.begin():
        catalog_store.create_dataset(session, another)
    invalid = (
        (update(CatalogSource).where(CatalogSource.id == saved.source_id).values(dataset_id=uuid4()), "23503"),
        (update(CatalogSource).where(CatalogSource.id == saved.source_id).values(is_synthetic=False, reference_key="UNREADY_SOURCE"), "23503"),
        (update(CatalogSourceVersion).where(CatalogSourceVersion.id == saved.id).values(dataset_id=another.id), "23503"),
        (update(CatalogSourceVersion).where(CatalogSourceVersion.id == saved.id).values(manual_import_permission="granted"), "23514"),
        (update(CatalogSourceVersion).where(CatalogSourceVersion.id == saved.id).values(auto_fetch_enabled=True), "23514"),
        (delete(CatalogSource).where(CatalogSource.id == saved.source_id), "23503"),
        (delete(CatalogDataset).where(CatalogDataset.id == saved.dataset_id), "23503"),
    )
    for statement, sqlstate in invalid:
        with pytest.raises(DBAPIError) as failure:
            with pg_engine.begin() as connection:
                connection.execute(statement)
        assert failure.value.orig.sqlstate == sqlstate
    assert len(rows(pg_engine, CatalogSourceVersion)) == 1


def test_persisted_bad_url_is_denied_without_repair_or_sensitive_error(source_service,
        administrator, source_request_factory, pg_engine):
    saved = register(source_service, administrator.principal, pg_engine, source_request_factory())
    damaged = "https://" + SENTINEL + "@sources.test.invalid/path"
    with pg_engine.begin() as connection:
        connection.execute(update(CatalogSourceVersion).where(CatalogSourceVersion.id == saved.id).values(entry_url=damaged))
    status(lambda: source_service.get_source_version(administrator.principal, saved.source_id), 503)
    assert rows(pg_engine, CatalogSourceVersion)[0]["entry_url"] == damaged


def wait_for_audit_insert_lock(engine, started, blocker_pid):
    assert started.wait(5)
    deadline = monotonic() + 8
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        while monotonic() < deadline:
            connection.execute(text("SELECT pg_stat_clear_snapshot()"))
            waiting = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                "AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)) "
                "AND query ILIKE '%auth_audit_events%'"), {"blocker": blocker_pid})
            if waiting:
                return
            started.wait(0.01)
    pytest.fail("No actual PostgreSQL audit INSERT lock wait observed")


@pytest.mark.parametrize("expiry", ["session", "role", "assurance", "permission"])
def test_pg_audit_flush_wait_rechecks_expiry_before_business_commit(source_store, administrator_factory,
        source_request_factory, pg_engine, clock, expiry):
    actor = administrator_factory(lifetime=172800 if expiry == "permission" else 3600,
        assurance_age_limit=86400 if expiry == "permission" else 60,
        role_lifetime=5 if expiry == "role" else None)
    service = SourceService(actor.service, source_store, SourcePolicy(enabled=True))
    request = granted_request(source_request_factory)
    if expiry == "session":
        with Session(pg_engine) as session, session.begin():
            session.get(AuthSession, actor.actor.session_id).expires_at = clock() + timedelta(seconds=5)
    before = revision(pg_engine, request.dataset_id), successes(pg_engine)
    started = Event()
    def target_success_insert(connection, cursor, statement, parameters, context, many):
        if (statement.lstrip().startswith("INSERT INTO auth_audit_events")
            and parameters.get("action") == "administrator.action" and parameters.get("outcome") == "succeeded"):
            started.set()
    def operation():
        return service.register_source(actor.principal, request, expected_dataset_revision=before[0])
    event.listen(pg_engine, "before_cursor_execute", target_success_insert)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pg_engine.begin() as blocker:
                blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("LOCK TABLE auth_audit_events IN SHARE MODE"))
                future = pool.submit(operation)
                wait_for_audit_insert_lock(pg_engine, started, blocker_pid)
                clock.advance({"session": 5, "role": 5, "assurance": 61, "permission": 86400}[expiry])
            status(lambda: future.result(timeout=8), 401 if expiry == "session" else 409 if expiry == "permission" else 403)
    finally:
        event.remove(pg_engine, "before_cursor_execute", target_success_insert)
    assert rows(pg_engine, CatalogSource) == [] and rows(pg_engine, CatalogSourceVersion) == []
    assert (revision(pg_engine, request.dataset_id), successes(pg_engine)) == before


def test_incremental_upgrade_repeat_and_isolated_downgrade_preserve_three_domains(source_store,
        administrator, catalog_store, catalog_tree, pg_engine, clock, monkeypatch, tmp_path):
    from services.api.app.admissions_catalog.date_schemas import DateEventInput
    from services.api.app.admissions_catalog.date_store import DateEventStore
    from services.api.app.auth.models import AuthBase
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.models import Base as M0Base
    from services.api.app.seed import seed

    def downgrade():
        config = migration_config()
        with pg_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0002_catalog_dates_t12")
    downgrade()
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    date_request = DateEventInput(id=uuid4(), dataset_id=catalog_tree.dataset.id,
        offering_id=catalog_tree.offering.id, offering_version=1, reference_key="DEMO_T13_PRESERVED_DATE",
        is_synthetic=True, entry_year=2026, event_type="application_deadline", original_text="DEMO_2026-07-15 15:30 London",
        precision="minute", local_date=date(2026, 7, 15), local_time=time(15, 30), timezone="Europe/London",
        source_alignment="pending", evidence_reference=None)
    with Session(pg_engine) as session, session.begin():
        DateEventStore(pg_engine).create_date_event(session, date_request,
            expected_dataset_revision=revision(pg_engine, catalog_tree.dataset.id))
    def preserved():
        with pg_engine.connect() as connection:
            saved = {table.name: connection.execute(select(table).order_by(*table.primary_key.columns)).all()
                for metadata in (M0Base.metadata, AuthBase.metadata, CatalogBase.metadata, DatesBase.metadata)
                for table in metadata.tables.values()}
            heads = (connection.scalar(text("SELECT version_num FROM alembic_version")),
                connection.scalar(text("SELECT version_num FROM auth_alembic_version")))
        return saved, heads
    before = preserved()
    migrate_catalog(pg_engine)
    migrate_catalog(pg_engine)
    assert preserved() == before
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM catalog_alembic_version")) == "0003_catalog_sources_t13"
    assert set(SourceBase.metadata.tables) == {"catalog_sources", "catalog_source_versions"}
    assert len(CatalogBase.metadata.tables) == 5 and len(DatesBase.metadata.tables) == 1
    downgrade()
    assert not {"catalog_sources", "catalog_source_versions"} & set(inspect(pg_engine).get_table_names())
    assert preserved() == before
    CatalogStore(pg_engine).assert_schema_ready(required_head="0002_catalog_dates_t12")
    administrator.service.store.assert_schema_ready()
    migrate_catalog(pg_engine)
    assert preserved() == before and rows(pg_engine, CatalogSource) == []
