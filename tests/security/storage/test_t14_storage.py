"""T14 independent PostgreSQL/file I/O trust and failure acceptance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, event, inspect, select, text, update
from sqlalchemy.orm import Session

from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion, SourceBase
from services.api.app.admin.sources.schemas import SourcePolicy, SourceRevisionInput
from services.api.app.admissions_catalog.models import (CatalogBase, CatalogDataset, CatalogInstitution,
    CatalogProgram, AdmissionOffering, AdmissionOfferingVersion)
from services.api.app.admissions_catalog.date_models import CatalogDateEvent, DatesBase
from services.api.app.audit.models import AuditEvent
from services.api.app.auth.authorization import Authorizer
from services.api.app.auth.models import AuthBase, AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from services.api.app.privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from services.api.app.privacy.schemas import AgeDeclarationInput
from services.api.app.storage.models import StorageBase, StorageObject
from services.api.app.storage.schemas import StoragePolicy
from services.api.app.storage.store import StorageStore, migrate_storage, migration_config


pytestmark = pytest.mark.postgres
PAYLOAD = b'{"DEMO_T14":"synthetic bytes"}'
SENTINEL = "DEMO_T14_PRIVATE_IO_SENTINEL"


def denied(operation, expected):
    with pytest.raises(ValueError) as failure:
        operation()
    allowed = (expected,) if isinstance(expected, int) else expected
    assert failure.value.status_code in allowed
    assert SENTINEL not in str(failure.value) and SENTINEL not in repr(failure.value)
    return failure.value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns)).mappings().all()


def success_ids(engine):
    return {row["id"] for row in rows(engine, AuditEvent) if row["outcome"] == "succeeded"}


def file_paths(root):
    return [path for path in root.rglob("*") if path.is_file()]


def upload(service, principal, parent):
    return service.upload_private(principal, parent_kind="profile", parent_resource_id=parent.id,
        filename="DEMO_T14.json", content_type="application/json", data=PAYLOAD)


def test_private_upload_registry_blob_and_minimal_audit_commit_together(private_file_factory,
        storage_service, pg_engine, blob_root):
    case = private_file_factory()
    assert case.file.namespace == "student_private" and case.file.status == "quarantined" and case.file.is_synthetic is True
    assert case.file.id.version == 4 and case.file.sha256 == sha256(case.data).hexdigest()
    assert case.file.size_bytes == len(case.data)
    with Session(pg_engine) as session:
        record = session.get(StorageObject, case.file.id)
        attachment = session.get(AuthOwnedResource, case.file.id)
        assert record.owner_user_id == case.actor.user_id and record.owned_resource_id == case.file.id
        assert record.resource_version == attachment.version == 1 and attachment.parent_id == case.parent.id
        assert attachment.owner_user_id == case.actor.user_id and attachment.resource_type == "attachment"
    assert storage_service.read_private(case.principal, case.file.id) == case.data
    assert len(file_paths(blob_root)) == 1
    assert not {"path", "key", "filename", "owner_user_id"} & set(case.file.model_dump())
    records = rows(pg_engine, AuditEvent)
    assert all("DEMO_T14.json" not in repr(record) and "synthetic file only" not in repr(record) for record in records)


def test_foreign_owner_and_management_roles_never_receive_private_bytes(private_file_factory,
        storage_service, admitted_actor_factory, actor_factory, io_probe):
    case = private_file_factory()
    before = io_probe.read_count
    for role in ("student", "data_admin", "operations", None):
        actor = admitted_actor_factory() if role == "student" else actor_factory(role=role)
        principal = storage_service.auth_service.get_principal(actor.cookie)
        denied(lambda: storage_service.read_private(principal, case.file.id), (403, 404))
        denied(lambda: storage_service.delete_private(principal, case.file.id), (403, 404))
    assert io_probe.read_count == before


def test_accepted_metadata_grant_cannot_authorize_attachment_bytes(private_file_factory,
        storage_service, admitted_actor_factory, accepted_grant_factory, sharing_service, io_probe):
    case = private_file_factory()
    recipient = admitted_actor_factory()
    with Session(storage_service.store.engine) as session:
        attachment = session.get(AuthOwnedResource, case.file.id)
        reference = attachment.id
    owner, recipient, resource, grant = accepted_grant_factory(owner=case.actor, recipient=recipient,
        resource=Authorizer(storage_service.auth_service).require_owned(case.principal, "attachment", reference))
    receiver = storage_service.auth_service.get_principal(recipient.cookie)
    projection = sharing_service.require_shared(receiver, "attachment", reference, ("status", "version"))
    assert projection.resource_id == reference
    before = io_probe.read_count
    denied(lambda: storage_service.read_private(receiver, case.file.id), 404)
    assert io_probe.read_count == before


def test_each_private_read_rechecks_current_identity_core_notice_and_owner(private_file_factory,
        storage_service, privacy_service, privacy_settings, pg_engine, clock, io_probe):
    for change in ("core", "session", "role", "account", "age", "notice", "parent"):
        case = private_file_factory()
        if change == "core":
            current = privacy_service.get_admission(case.principal)
            privacy_service.withdraw_core(case.principal, current.consent_id)
        elif change == "role":
            storage_service.auth_service.store.revoke_role(case.actor.user_id, "student", now=clock())
        elif change == "age":
            current = privacy_service.get_admission(case.principal)
            denied(lambda: privacy_service.declare_age(case.principal, AgeDeclarationInput(age_band="unknown",
                confirmed=True, notice_id=current.notice_id, expected_revision=current.revision)), 403)
        else:
            with Session(pg_engine) as session, session.begin():
                if change == "session":
                    session.get(AuthSession, case.actor.session_id).revoked_at = clock()
                elif change == "account":
                    session.get(AuthUser, case.actor.user_id).status = "disabled"
                elif change == "parent":
                    session.get(AuthOwnedResource, case.parent.id).status = "deleted"
                else:
                    session.get(PrivacyNoticeVersion, privacy_settings.notice_id).text_sha256 = "0" * 64
        before = io_probe.read_count
        denied(lambda: storage_service.read_private(case.principal, case.file.id), (401, 403, 404, 503))
        assert io_probe.read_count == before
        if change == "notice":
            from services.api.app.privacy.config import DRAFT_NOTICE_TEXT
            from services.api.app.privacy.policy import hash_text
            with Session(pg_engine) as session, session.begin():
                session.get(PrivacyNoticeVersion, privacy_settings.notice_id).text_sha256 = hash_text(DRAFT_NOTICE_TEXT)


def test_closed_policy_and_production_do_not_open_synthetic_storage(storage_factory, private_file_factory,
        source_file_factory, storage_service, runtime, io_probe):
    case = private_file_factory()
    closed = storage_factory(policy=StoragePolicy())
    before = io_probe.read_count
    denied(lambda: closed.read_private(case.principal, case.file.id), 503)
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.service import AuthService
    production = runtime.model_copy(update={"app_environment": "production"})
    identity = AuthService(storage_service.auth_service.settings, production, storage_service.auth_service.store,
        KeycloakOidcAdapter(storage_service.auth_service.settings, production), clock=storage_service.auth_service._now)
    denied(lambda: storage_factory(identity=identity).read_private(case.principal, case.file.id), (401, 403, 503))
    assert io_probe.read_count == before


def test_source_is_quarantined_current_responsible_admin_only(source_file_factory,
        administrator_factory, storage_factory, io_probe, clock):
    case = source_file_factory()
    assert case.file.namespace == "source_quarantine" and case.file.status == "quarantined"
    assert case.file.expires_at == clock() + timedelta(days=1)
    assert case.service.read_source(case.admin.principal, case.file.id) == case.data
    assert case.source.publication_permission == "denied"
    other = administrator_factory()
    other_service = storage_factory(identity=other.service)
    before = io_probe.read_count
    denied(lambda: other_service.read_source(other.principal, case.file.id), 403)
    denied(lambda: other_service.upload_source(other.principal, case.source.source_id,
        expected_source_version=1, filename="DEMO_other.json", content_type="application/json", data=PAYLOAD), 403)
    assert io_probe.read_count == before


def test_source_exact_consumer_binding_and_new_version_cannot_reuse_old_asset(source_file_factory,
        source_request_factory, pg_engine, io_probe):
    case = source_file_factory()
    expected = dict(expected_dataset_id=case.source.dataset_id, expected_source_id=case.source.source_id,
        expected_source_version=1)
    before = io_probe.read_count
    with Session(pg_engine) as session, session.begin():
        assert case.service.get_source_file_in_transaction(session, case.admin.principal, case.file.id, **expected) == case.file
    for updates in ({"expected_source_id": uuid4()}, {"expected_dataset_id": uuid4()}, {"expected_source_version": 2}):
        with Session(pg_engine) as session, session.begin():
            denied(lambda: case.service.get_source_file_in_transaction(session, case.admin.principal,
                case.file.id, **(expected | updates)), 409)
    with Session(pg_engine) as session, session.begin():
        denied(lambda: case.service.get_source_file_in_transaction(session, case.admin.principal,
            case.file.id, expected_source_id=case.source.source_id), 409)
    assert io_probe.read_count == before
    with Session(pg_engine) as session:
        revision = session.get(CatalogDataset, case.source.dataset_id).revision
    denied_definition = source_request_factory(definition_updates={"manual_import_permission": "denied",
        "license_basis": "DEMO_NEW_DENIAL", "permission_record_reference": "DEMO_NEW_PERMISSION"}).definition
    case.sources.revise_source(case.admin.principal,
        SourceRevisionInput(source_id=case.source.source_id, definition=denied_definition),
        expected_dataset_revision=revision, expected_source_version=1)
    denied(lambda: case.service.read_source(case.admin.principal, case.file.id), (403, 409))
    denied(lambda: case.service.upload_source(case.admin.principal, case.source.source_id,
        expected_source_version=1, filename="DEMO_old.json", content_type="application/json", data=PAYLOAD), 409)
    assert io_probe.read_count == before


def test_source_mfa_role_permission_and_policy_are_current_for_every_read(source_file_factory,
        storage_factory, pg_engine, clock, io_probe):
    for change in ("mfa", "role", "permission", "policy"):
        case = source_file_factory()
        if change == "role":
            case.admin.service.store.revoke_role(case.admin.actor.user_id, "data_admin", now=clock())
        elif change == "policy":
            case.service = storage_factory(identity=case.admin.service, source_policy=SourcePolicy())
        else:
            with Session(pg_engine) as session, session.begin():
                if change == "mfa":
                    session.get(AuthSession, case.admin.actor.session_id).assurance_amr = ["pwd"]
                else:
                    row = session.get(CatalogSourceVersion, case.source.id)
                    row.manual_import_permission = "denied"
                    row.manual_import_enabled = False
        before = io_probe.read_count
        denied(lambda: case.service.read_source(case.admin.principal, case.file.id), (403, 409, 503))
        assert io_probe.read_count == before


def test_wrong_engine_for_every_actual_mapper_is_rejected_before_io(source_file_factory, pg_engine, io_probe):
    case = source_file_factory()
    foreign = create_engine(pg_engine.url, hide_parameters=True)
    attempted = []
    def no_connect(*args):
        attempted.append(True)
        raise AssertionError("wrong storage mapper must be rejected before foreign I/O")
    event.listen(foreign, "do_connect", no_connect)
    before = io_probe.read_count
    try:
        for model in (AuthUser, AuthSession, AuthUserRole, AuthOwnedResource, AuditEvent,
                PrivacyAdmissionRecord, PrivacyNoticeVersion, CatalogDataset, CatalogInstitution, CatalogProgram,
                AdmissionOffering, AdmissionOfferingVersion, CatalogDateEvent, CatalogSource, CatalogSourceVersion, StorageObject):
            with Session(pg_engine, binds={model: foreign}) as session, session.begin():
                denied(lambda: case.service.get_source_file_in_transaction(session, case.admin.principal, case.file.id), 503)
        assert attempted == [] and io_probe.read_count == before
    finally:
        foreign.dispose()


def test_write_fault_leaves_no_registry_metadata_or_success_audit(storage_service, admitted_actor_factory,
        resource_factory, io_probe, pg_engine, blob_root):
    actor = admitted_actor_factory()
    principal = storage_service.auth_service.get_principal(actor.cookie)
    parent = resource_factory(actor)
    before = rows(pg_engine, AuthOwnedResource), success_ids(pg_engine)
    io_probe.fail_write = True
    denied(lambda: upload(storage_service, principal, parent), 503)
    assert rows(pg_engine, StorageObject) == [] and file_paths(blob_root) == []
    assert (rows(pg_engine, AuthOwnedResource), success_ids(pg_engine)) == before


def test_required_audit_insert_failure_rolls_back_and_deletes_written_blob(storage_service,
        admitted_actor_factory, resource_factory, io_probe, pg_engine, blob_root):
    actor = admitted_actor_factory()
    principal = storage_service.auth_service.get_principal(actor.cookie)
    parent = resource_factory(actor)
    before = rows(pg_engine, AuthOwnedResource), success_ids(pg_engine)
    def fault(connection, cursor, statement, parameters, context, many):
        if (statement.lstrip().startswith("INSERT INTO auth_audit_events")
            and parameters.get("object_type") == "attachment" and parameters.get("outcome") == "succeeded"
            and io_probe.written):
            raise RuntimeError(SENTINEL)
    event.listen(pg_engine, "before_cursor_execute", fault)
    try:
        denied(lambda: upload(storage_service, principal, parent), 503)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fault)
    assert len(io_probe.written) == 1 and io_probe.deleted
    assert rows(pg_engine, StorageObject) == [] and file_paths(blob_root) == []
    assert (rows(pg_engine, AuthOwnedResource), success_ids(pg_engine)) == before


def test_real_postgresql_commit_failure_compensates_and_orphan_never_authorizes_read(storage_service,
        admitted_actor_factory, resource_factory, io_probe, pg_engine, blob_root):
    actor = admitted_actor_factory()
    principal = storage_service.auth_service.get_principal(actor.cookie)
    parent = resource_factory(actor)
    # A real deferred PostgreSQL trigger fails at COMMIT, after successful I/O
    # and INSERT/flush; it does not merely monkeypatch Session.commit.
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t14_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T14_PRIVATE_IO_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t14_commit_fault AFTER INSERT ON storage_objects "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t14_fail_commit()"))
    before = rows(pg_engine, AuthOwnedResource), success_ids(pg_engine)
    for cleanup_fails in (False, True):
        io_probe.fail_delete = cleanup_fails
        denied(lambda: upload(storage_service, principal, parent), 503)
        orphan_id = io_probe.written[-1].object_id
        assert rows(pg_engine, StorageObject) == []
        assert (rows(pg_engine, AuthOwnedResource), success_ids(pg_engine)) == before
        denied(lambda: storage_service.read_private(principal, orphan_id), 404)
        assert len(file_paths(blob_root)) == (1 if cleanup_fails else 0)


def test_missing_and_tampered_physical_blob_never_return_bytes(private_file_factory,
        storage_service, pg_engine, blob_root):
    case = private_file_factory()
    path, = file_paths(blob_root)
    path.write_bytes(b'{"DEMO_T14":"tampered"}')
    denied(lambda: storage_service.read_private(case.principal, case.file.id), (404, 503))
    path.unlink()
    denied(lambda: storage_service.read_private(case.principal, case.file.id), (404, 503))
    assert rows(pg_engine, StorageObject)[0]["status"] == "quarantined"


def test_read_rechecks_after_actual_io_before_return(private_file_factory, source_file_factory,
        storage_service, io_probe, pg_engine, clock):
    for expires in ("session", "role", "core"):
        case = private_file_factory()
        with Session(pg_engine) as session, session.begin():
            if expires == "session":
                session.get(AuthSession, case.actor.session_id).expires_at = clock() + timedelta(seconds=5)
            elif expires == "role":
                session.get(AuthUserRole, (case.actor.user_id, "student")).expires_at = clock() + timedelta(seconds=5)
            else:
                session.execute(update(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == case.actor.user_id)
                    .values(declaration_expires_at=clock() + timedelta(seconds=5)))
        before = io_probe.read_count, success_ids(pg_engine)
        io_probe.after_read = lambda: clock.advance(5)
        try:
            denied(lambda: storage_service.read_private(case.principal, case.file.id), 401 if expires == "session" else 403)
        finally:
            io_probe.after_read = None
        assert io_probe.read_count == before[0] + 1 and success_ids(pg_engine) == before[1]
    source = source_file_factory(lifetime=172800, assurance_age_limit=86400)
    before = io_probe.read_count, success_ids(pg_engine)
    io_probe.after_read = lambda: clock.advance(86400)
    try:
        denied(lambda: source.service.read_source(source.admin.principal, source.file.id), (403, 404, 409))
    finally:
        io_probe.after_read = None
    assert io_probe.read_count == before[0] + 1 and success_ids(pg_engine) == before[1]


def wait_for_audit_lock(engine, target, blocker_pid):
    assert target.wait(5), "no required succeeded audit INSERT reached"
    end = monotonic() + 8
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        while monotonic() < end:
            connection.execute(text("SELECT pg_stat_clear_snapshot()"))
            found = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                "AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)) "
                "AND query ILIKE '%auth_audit_events%'"), {"blocker": blocker_pid})
            if found:
                return
            target.wait(0.01)
    pytest.fail("No actual PostgreSQL required audit lock wait observed")


def test_read_audit_lock_wait_does_not_extend_private_or_source_authority(private_file_factory,
        source_file_factory, storage_service, pg_engine, clock):
    for expires in ("session", "core", "mfa", "source"):
        if expires in {"session", "core"}:
            case = private_file_factory()
            with Session(pg_engine) as session, session.begin():
                if expires == "session":
                    session.get(AuthSession, case.actor.session_id).expires_at = clock() + timedelta(seconds=5)
                else:
                    session.execute(update(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == case.actor.user_id)
                        .values(declaration_expires_at=clock() + timedelta(seconds=5)))
            read = lambda: storage_service.read_private(case.principal, case.file.id)
        else:
            source = source_file_factory(lifetime=172800, assurance_age_limit=86400 if expires == "source" else 60)
            read = lambda: source.service.read_source(source.admin.principal, source.file.id)
        before = success_ids(pg_engine)
        target = Event()
        def audit_insert(connection, cursor, statement, parameters, context, many):
            if statement.lstrip().startswith("INSERT INTO auth_audit_events") and parameters.get("outcome") == "succeeded":
                target.set()
        event.listen(pg_engine, "before_cursor_execute", audit_insert)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                with pg_engine.begin() as blocker:
                    blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
                    blocker.execute(text("LOCK TABLE auth_audit_events IN SHARE MODE"))
                    future = pool.submit(read)
                    wait_for_audit_lock(pg_engine, target, blocker_pid)
                    clock.advance({"session": 5, "core": 5, "mfa": 61, "source": 86400}[expires])
                denied(lambda: future.result(timeout=8), 401 if expires == "session" else (403, 404, 409))
        finally:
            event.remove(pg_engine, "before_cursor_execute", audit_insert)
        assert success_ids(pg_engine) == before


def test_owner_can_delete_after_core_and_role_revocation_and_retry_physical_failure(private_file_factory,
        storage_service, privacy_service, io_probe, pg_engine, blob_root, clock):
    case = private_file_factory()
    current = privacy_service.get_admission(case.principal)
    privacy_service.withdraw_core(case.principal, current.consent_id)
    storage_service.auth_service.store.revoke_role(case.actor.user_id, "student", now=clock())
    io_probe.fail_delete = True
    result = storage_service.delete_private(case.principal, case.file.id)
    assert result.status == "delete_pending" and len(file_paths(blob_root)) == 1
    with Session(pg_engine) as session:
        assert session.get(StorageObject, case.file.id).status == "delete_pending"
        assert session.get(AuthOwnedResource, case.file.id).status == "deleted"
    denied(lambda: storage_service.read_private(case.principal, case.file.id), (403, 404))
    io_probe.fail_delete = False
    # The second transaction confirms physical deletion. Its real deferred
    # commit can fail even though the first tombstone transaction committed.
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t14_fail_deleted_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T14_PRIVATE_IO_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t14_deleted_commit_fault AFTER UPDATE ON storage_objects "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.status = 'deleted') "
            "EXECUTE FUNCTION t14_fail_deleted_commit()"))
    assert storage_service.delete_private(case.principal, case.file.id).status == "delete_pending"
    assert file_paths(blob_root) == []
    with Session(pg_engine) as session:
        assert session.get(StorageObject, case.file.id).status == "delete_pending"
        assert session.get(AuthOwnedResource, case.file.id).status == "deleted"
    with pg_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER t14_deleted_commit_fault ON storage_objects"))
    assert storage_service.delete_private(case.principal, case.file.id).status == "deleted"
    assert storage_service.delete_private(case.principal, case.file.id).status == "deleted"
    assert file_paths(blob_root) == []


def test_storage_profile_repeat_and_downgrade_preserve_existing_five_domains(private_file_factory,
        storage_store, pg_engine, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.models import Base as M0Base
    from services.api.app.seed import seed
    case = private_file_factory()
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    def preserved():
        with pg_engine.connect() as connection:
            data = {table.name: connection.execute(select(table).order_by(*table.primary_key.columns)).all()
                for metadata in (M0Base.metadata, AuthBase.metadata, CatalogBase.metadata, DatesBase.metadata, SourceBase.metadata)
                for table in metadata.tables.values()}
            heads = tuple(connection.scalar(text("SELECT version_num FROM " + name))
                for name in ("alembic_version", "auth_alembic_version", "catalog_alembic_version"))
        return data, heads
    before = preserved()
    migrate_storage(pg_engine)
    migrate_storage(pg_engine)
    assert preserved() == before and len(StorageBase.metadata.tables) == 1
    config = migration_config()
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert "storage_objects" not in inspect(pg_engine).get_table_names()
    assert preserved() == before
    denied(lambda: StorageStore(pg_engine).assert_schema_ready(), 503)
    migrate_storage(pg_engine)
    assert rows(pg_engine, StorageObject) == [] and preserved() == before
    assert (before[1][1], before[1][2]) == ("0006_audit_t10", "0003_catalog_sources_t13")
