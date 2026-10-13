"""Independent T49 PG contention, current authority and failure acceptance.

Callbacks create synthetic registry metadata only; no import, release, real
profile or plan-confirmation business is implemented by these probes.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest
from alembic import command
from pydantic import SecretStr
from sqlalchemy import create_engine, event, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.audit.models import AuditEvent
from services.api.app.auth.authorization import Authorizer
from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from services.api.app.idempotency.models import IdempotencyBase, IdempotencyRecord
from services.api.app.idempotency.schemas import IdempotencyPolicy, ResourceReceipt
from services.api.app.idempotency.store import migrate_idempotency, migration_config
from services.api.app.privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from services.api.app.privacy.schemas import AgeDeclarationInput


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T49_SECRET_INPUT_SENTINEL"
KEY = SecretStr("DEMO_T49_OPAQUE_CLIENT_KEY")
PAYLOAD = {"DEMO_T49": {"b": [1, True, None], "a": SENTINEL}}


def denied(operation, status):
    with pytest.raises(ValueError) as failure:
        operation()
    assert getattr(failure.value, "status_code", None) in ((status,) if isinstance(status, int) else status)
    assert SENTINEL not in str(failure.value) and SENTINEL not in repr(failure.value)
    assert KEY.get_secret_value() not in str(failure.value)
    return failure.value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns)).mappings().all()


def success_ids(engine):
    return {row["id"] for row in rows(engine, AuditEvent) if row["outcome"] == "succeeded"}


def execute(service, principal, probe, *, operation="profile.create", key=KEY, payload=PAYLOAD, session=None):
    return service.execute(principal, operation, key, payload,
        perform=probe.perform, verify_resource=probe.verify, session=session)


def actor_case(admitted_actor_factory, service, **changes):
    actor = admitted_actor_factory(**changes)
    return actor, service.auth_service.get_principal(actor.cookie)


def wait_for_blocked_pid(engine, started, worker, blocker):
    assert started.wait(5), "Contending session did not reach the database"
    deadline = monotonic() + 5
    pause = Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            waiting = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE pid=:worker "
                "AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid))"),
                {"worker": worker[0], "blocker": blocker})
            if waiting:
                return
            pause.wait(0.01)
    pytest.fail("No actual PostgreSQL two-session lock contention observed")


def test_canonical_same_request_replays_only_reference_and_does_not_extend_expiry(idempotency_service,
        admitted_actor_factory, registry_probe, pg_engine, clock):
    _, principal = actor_case(admitted_actor_factory, idempotency_service)
    probe = registry_probe()
    first = execute(idempotency_service, principal, probe)
    clock.advance(1)
    reordered = {"DEMO_T49": {"a": SENTINEL, "b": [1, True, None]}}
    replay = execute(idempotency_service, principal, probe, payload=reordered)
    assert first.replayed is False and replay.replayed is True
    assert replay.resource == first.resource and replay.expires_at == first.expires_at
    assert probe.calls == 1 and probe.verified >= 4
    saved = rows(pg_engine, IdempotencyRecord)
    assert len(saved) == 1 and saved[0]["state"] == "completed"
    assert saved[0]["key_digest"] == sha256(KEY.get_secret_value().encode("ascii")).hexdigest()
    assert saved[0]["resource_id"] == first.resource.resource_id
    assert SENTINEL not in str(saved) and KEY.get_secret_value() not in str(saved)
    assert not {"payload", "response", "request_body"} & set(saved[0])


def test_different_content_same_key_conflicts_without_new_effect(idempotency_service,
        admitted_actor_factory, registry_probe, pg_engine):
    _, principal = actor_case(admitted_actor_factory, idempotency_service)
    probe = registry_probe()
    original = execute(idempotency_service, principal, probe)
    before = rows(pg_engine, IdempotencyRecord)
    error = denied(lambda: execute(idempotency_service, principal, probe, payload={"DEMO_T49": "different"}), 409)
    assert error.code == "IDEMPOTENCY_CONFLICT"
    assert probe.calls == 1 and rows(pg_engine, IdempotencyRecord) == before
    assert rows(pg_engine, AuthOwnedResource)[0]["id"] == original.resource.resource_id


def test_actor_and_operation_namespaces_are_isolated(idempotency_service,
        admitted_actor_factory, registry_probe, pg_engine):
    _, alice = actor_case(admitted_actor_factory, idempotency_service)
    _, bob = actor_case(admitted_actor_factory, idempotency_service)
    a = execute(idempotency_service, alice, registry_probe())
    b = execute(idempotency_service, bob, registry_probe())
    other_operation = execute(idempotency_service, alice, registry_probe("plan"), operation="plan.confirm")
    assert len({a.resource.resource_id, b.resource.resource_id, other_operation.resource.resource_id}) == 3
    assert len(rows(pg_engine, IdempotencyRecord)) == 3


@pytest.mark.parametrize("winner_commits", [True, False])
def test_real_two_sessions_serialize_and_rollback_frees_claim(winner_commits,
        idempotency_service, admitted_actor_factory, registry_probe, pg_engine):
    _, principal = actor_case(admitted_actor_factory, idempotency_service)
    probe = registry_probe()
    started, worker_pid = Event(), []
    def contender():
        with Session(pg_engine) as session, session.begin():
            worker_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
            started.set()
            return execute(idempotency_service, principal, probe, session=session)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with Session(pg_engine) as winner:
            transaction = winner.begin()
            blocker = winner.scalar(text("SELECT pg_backend_pid()"))
            first = execute(idempotency_service, principal, probe, session=winner)
            future = pool.submit(contender)
            try:
                wait_for_blocked_pid(pg_engine, started, worker_pid, blocker)
                assert not future.done() and probe.calls == 1
            finally:
                transaction.commit() if winner_commits else transaction.rollback()
            second = future.result(timeout=8)
    assert second.replayed is winner_commits
    assert probe.calls == (1 if winner_commits else 2)
    saved = rows(pg_engine, IdempotencyRecord)
    assert len(saved) == 1 and saved[0]["state"] == "completed"
    assert len(rows(pg_engine, AuthOwnedResource)) == 1
    assert (first.resource == second.resource) is winner_commits


def test_operation_failure_and_caller_rollback_are_retryable(idempotency_service,
        admitted_actor_factory, registry_probe, pg_engine):
    _, principal = actor_case(admitted_actor_factory, idempotency_service)
    probe = registry_probe()
    def broken(session, current):
        probe.perform(session, current)
        raise RuntimeError(SENTINEL)
    before = success_ids(pg_engine)
    denied(lambda: idempotency_service.execute(principal, "profile.create", KEY, PAYLOAD,
        perform=broken, verify_resource=probe.verify), 503)
    assert not rows(pg_engine, IdempotencyRecord) and not rows(pg_engine, AuthOwnedResource)
    assert success_ids(pg_engine) == before
    # Caller-owned failure requires the outer transaction to roll back. The
    # returned reference is provisional until the caller successfully commits.
    with pytest.raises(RuntimeError, match="DEMO_T49_OUTER_ROLLBACK"):
        with Session(pg_engine) as session, session.begin():
            execute(idempotency_service, principal, probe, session=session)
            raise RuntimeError("DEMO_T49_OUTER_ROLLBACK")
    assert not rows(pg_engine, IdempotencyRecord) and not rows(pg_engine, AuthOwnedResource)
    assert success_ids(pg_engine) == before
    result = execute(idempotency_service, principal, probe)
    assert not result.replayed and len(rows(pg_engine, AuthOwnedResource)) == 1


@pytest.mark.parametrize("winner_commits", [True, False])
def test_store_unique_index_contention_is_real_without_account_lock(winner_commits,
        idempotency_store, pg_engine, clock):
    """Exercise the SQL key constraint itself, apart from AuthUser locking."""
    actor, key_digest, request_hash = uuid4(), "c" * 64, "d" * 64
    first_reference = ResourceReceipt(kind="profile", resource_id=uuid4(), version=1)
    started, worker_pid = Event(), []
    def claim(session):
        return idempotency_store.claim(session, actor, "profile.create", key_digest, request_hash,
            is_synthetic=True, clock=clock, ttl_seconds=86400)
    def contender():
        with Session(pg_engine) as session, session.begin():
            worker_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
            started.set()
            row, replayed = claim(session)
            if not replayed:
                idempotency_store.complete(session, row,
                    ResourceReceipt(kind="profile", resource_id=uuid4(), version=1), now=clock())
            return replayed, row.resource_id
    with ThreadPoolExecutor(max_workers=1) as pool:
        with Session(pg_engine) as first:
            transaction = first.begin()
            blocker = first.scalar(text("SELECT pg_backend_pid()"))
            row, replayed = claim(first)
            assert not replayed
            idempotency_store.complete(first, row, first_reference, now=clock())
            future = pool.submit(contender)
            try:
                wait_for_blocked_pid(pg_engine, started, worker_pid, blocker)
                assert not future.done()
            finally:
                transaction.commit() if winner_commits else transaction.rollback()
            replayed, resource_id = future.result(timeout=8)
    assert replayed is winner_commits
    assert (resource_id == first_reference.resource_id) is winner_commits
    assert len(rows(pg_engine, IdempotencyRecord)) == 1


def test_actual_deferred_commit_failure_rolls_back_receipt_effect_and_success_audit(idempotency_service,
        admitted_actor_factory, registry_probe, pg_engine):
    _, principal = actor_case(admitted_actor_factory, idempotency_service)
    probe, before = registry_probe(), success_ids(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t49_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T49_SECRET_INPUT_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t49_commit_fault AFTER INSERT ON idempotency_records "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t49_fail_commit()"))
    denied(lambda: execute(idempotency_service, principal, probe), 503)
    assert probe.calls == 1
    assert not rows(pg_engine, IdempotencyRecord) and not rows(pg_engine, AuthOwnedResource)
    assert success_ids(pg_engine) == before
    with pg_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER t49_commit_fault ON idempotency_records"))
    assert not execute(idempotency_service, principal, probe).replayed


def test_database_cannot_commit_processing_claim(pg_engine, idempotency_store, clock):
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as session, session.begin():
            session.add(IdempotencyRecord(id=uuid4(), actor_user_id=uuid4(), operation="profile.create",
                key_digest="a" * 64, request_hash="b" * 64, is_synthetic=True, state="processing",
                created_at=clock(), expires_at=clock() + timedelta(hours=24), completed_at=None,
                resource_kind=None, resource_id=None, resource_version=None))
            session.flush()
            # The valid processing row exists during the business transaction;
            # it must fail specifically when the deferred COMMIT check runs.
            assert session.scalar(select(IdempotencyRecord.state)) == "processing"
    assert not rows(pg_engine, IdempotencyRecord)


def test_exact_expiry_replaces_receipt_without_deleting_previous_resource(idempotency_factory,
        admitted_actor_factory, registry_probe, pg_engine, clock):
    service = idempotency_factory(policy=IdempotencyPolicy(enabled=True, ttl_seconds=2))
    _, principal = actor_case(admitted_actor_factory, service)
    probe = registry_probe()
    first = execute(service, principal, probe)
    clock.advance(2)
    replacement = execute(service, principal, probe, payload={"DEMO_T49": "new after expiry"})
    assert not replacement.replayed and replacement.resource != first.resource
    assert replacement.expires_at == clock() + timedelta(seconds=2)
    assert len(rows(pg_engine, IdempotencyRecord)) == 1
    assert {row["id"] for row in rows(pg_engine, AuthOwnedResource)} == {
        first.resource.resource_id, replacement.resource.resource_id}


def test_replay_rechecks_session_role_core_notice_age_and_resource(idempotency_service,
        admitted_actor_factory, registry_probe, privacy_service, pg_engine, clock):
    for revoked in ("session", "role", "core", "age", "notice", "deleted", "version"):
        actor, principal = actor_case(admitted_actor_factory, idempotency_service)
        probe = registry_probe()
        receipt = execute(idempotency_service, principal, probe)
        old = rows(pg_engine, IdempotencyRecord)
        notice_hash = None
        if revoked == "core":
            admission = privacy_service.get_admission(principal)
            privacy_service.withdraw_core(principal, admission.consent_id)
        elif revoked == "age":
            admission = privacy_service.get_admission(principal)
            denied(lambda: privacy_service.declare_age(principal, AgeDeclarationInput(age_band="unknown",
                confirmed=True, notice_id=admission.notice_id, expected_revision=admission.revision)), 403)
        else:
            with Session(pg_engine) as session, session.begin():
                if revoked == "session":
                    session.get(AuthSession, actor.session_id).revoked_at = clock()
                elif revoked == "role":
                    session.get(AuthUserRole, (actor.user_id, "student")).revoked_at = clock()
                elif revoked == "notice":
                    notice = session.get(PrivacyNoticeVersion, privacy_service.settings.notice_id)
                    notice_hash, notice.text_sha256 = notice.text_sha256, "0" * 64
                else:
                    resource = session.get(AuthOwnedResource, receipt.resource.resource_id)
                    if revoked == "deleted":
                        resource.status = "deleted"
                    else:
                        resource.version += 1
        try:
            denied(lambda: execute(idempotency_service, principal, probe), (401, 403, 404, 409, 503))
            assert probe.calls == 1 and rows(pg_engine, IdempotencyRecord) == old
        finally:
            if notice_hash is not None:
                with Session(pg_engine) as session, session.begin():
                    session.get(PrivacyNoticeVersion, privacy_service.settings.notice_id).text_sha256 = notice_hash


def test_lock_wait_does_not_extend_session_before_replay(idempotency_service,
        admitted_actor_factory, registry_probe, pg_engine, clock):
    _, principal = actor_case(admitted_actor_factory, idempotency_service, lifetime=5)
    probe = registry_probe()
    started, worker_pid = Event(), []
    def contender():
        with Session(pg_engine) as session, session.begin():
            worker_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
            started.set()
            return execute(idempotency_service, principal, probe, session=session)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with Session(pg_engine) as winner:
            transaction = winner.begin()
            blocker = winner.scalar(text("SELECT pg_backend_pid()"))
            execute(idempotency_service, principal, probe, session=winner)
            future = pool.submit(contender)
            try:
                wait_for_blocked_pid(pg_engine, started, worker_pid, blocker)
                clock.advance(5)
            finally:
                transaction.commit()
            denied(lambda: future.result(timeout=8), 401)
    assert probe.calls == 1 and len(rows(pg_engine, IdempotencyRecord)) == 1


def test_required_audit_block_and_expiry_roll_back_all_business(idempotency_service, idempotency_factory,
        admitted_actor_factory, registry_probe, pg_engine, clock):
    # Only the required audit after completed receipt creation waits. Earlier
    # privacy/registry audit inserts are deliberately allowed through, so this
    # proves the new service's final guard, not merely existing pre-authorization.
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE TABLE demo_t49_final_audit_barrier (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO demo_t49_final_audit_barrier VALUES (1)"))
        connection.execute(text("CREATE FUNCTION t49_wait_final_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF EXISTS (SELECT 1 FROM idempotency_records WHERE actor_user_id=NEW.actor_user_id "
            "AND state='completed') THEN PERFORM id FROM demo_t49_final_audit_barrier WHERE id=1 FOR UPDATE; "
            "END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER t49_final_audit_wait BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION t49_wait_final_audit()"))
    for expiry in ("session", "role", "core", "receipt"):
        service = (idempotency_factory(policy=IdempotencyPolicy(enabled=True, ttl_seconds=5))
            if expiry == "receipt" else idempotency_service)
        actor, principal = actor_case(admitted_actor_factory, service)
        with Session(pg_engine) as session, session.begin():
            if expiry == "session":
                session.get(AuthSession, actor.session_id).expires_at = clock() + timedelta(seconds=5)
            elif expiry == "role":
                session.get(AuthUserRole, (actor.user_id, "student")).expires_at = clock() + timedelta(seconds=5)
            elif expiry == "core":
                session.execute(update(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == actor.user_id)
                    .values(declaration_expires_at=clock() + timedelta(seconds=5)))
        probe, before, started, worker_pid = registry_probe(), success_ids(pg_engine), Event(), []
        def run():
            with Session(pg_engine) as session, session.begin():
                worker_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
                started.set()
                return execute(service, principal, probe, session=session)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pg_engine.begin() as blocker:
                pid = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t49_final_audit_barrier WHERE id=1 FOR UPDATE"))
                future = pool.submit(run)
                wait_for_blocked_pid(pg_engine, started, worker_pid, pid)
                assert probe.calls == 1
                clock.advance(5)
            denied(lambda: future.result(timeout=8), {"session": 401, "role": 403, "core": 403, "receipt": 409}[expiry])
        assert not rows(pg_engine, IdempotencyRecord) and not rows(pg_engine, AuthOwnedResource)
        assert success_ids(pg_engine) == before


def test_resource_verifier_is_mandatory_strict_true_and_receipt_revalidated(idempotency_service,
        admitted_actor_factory, registry_probe, pg_engine):
    _, principal = actor_case(admitted_actor_factory, idempotency_service)
    probe = registry_probe()
    for value in (False, None, 1, "true"):
        denied(lambda: idempotency_service.execute(principal, "profile.create", KEY, PAYLOAD,
            perform=probe.perform, verify_resource=lambda *args: value), 403)
        assert not rows(pg_engine, IdempotencyRecord) and not rows(pg_engine, AuthOwnedResource)
    for missing in ("perform", "verify_resource"):
        functions = {"perform": probe.perform, "verify_resource": probe.verify}
        functions[missing] = None
        denied(lambda: idempotency_service.execute(principal, "profile.create", KEY, PAYLOAD, **functions), 503)
    def forged(session, current):
        return probe.perform(session, current).model_copy(update={"version": True})
    denied(lambda: idempotency_service.execute(principal, "profile.create", KEY, PAYLOAD,
        perform=forged, verify_resource=probe.verify), 422)
    assert not rows(pg_engine, IdempotencyRecord) and not rows(pg_engine, AuthOwnedResource)


def test_fixed_catalog_capability_and_current_signed_assurance(idempotency_factory,
        administrator_factory, pg_engine, clock):
    # A deliberately test-only effect table, not an implemented import/release.
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE TABLE demo_t49_import_effects (id UUID PRIMARY KEY, actor UUID NOT NULL)"))
    for expired in ("mfa", "role", "session"):
        administrator = administrator_factory()
        service = idempotency_factory(identity=administrator.service)
        def perform(session, current):
            reference = uuid4()
            session.execute(text("INSERT INTO demo_t49_import_effects VALUES (:id,:actor)"),
                {"id": reference, "actor": current.user_id})
            return ResourceReceipt(kind="import", resource_id=reference, version=1)
        def verify(session, current, receipt):
            return session.scalar(text("SELECT count(*) FROM demo_t49_import_effects WHERE id=:id AND actor=:actor"),
                {"id": receipt.resource_id, "actor": current.user_id}) == 1
        first = service.execute(administrator.principal, "catalog.import", KEY, PAYLOAD,
            perform=perform, verify_resource=verify)
        assert not first.replayed
        with Session(pg_engine) as session, session.begin():
            if expired == "mfa":
                session.get(AuthSession, administrator.actor.session_id).assurance_amr = ["pwd"]
            elif expired == "role":
                session.get(AuthUserRole, (administrator.actor.user_id, "data_admin")).revoked_at = clock()
            else:
                session.get(AuthSession, administrator.actor.session_id).revoked_at = clock()
        denied(lambda: service.execute(administrator.principal, "catalog.import", KEY, PAYLOAD,
            perform=perform, verify_resource=verify), 401 if expired == "session" else 403)
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM demo_t49_import_effects")) == 3


def test_session_mapper_and_actor_binding_cannot_cross_database_or_identity(idempotency_service,
        idempotency_store, admitted_actor_factory, registry_probe, pg_engine):
    _, alice = actor_case(admitted_actor_factory, idempotency_service)
    _, bob = actor_case(admitted_actor_factory, idempotency_service)
    probe = registry_probe()
    with Session(pg_engine) as inactive:
        denied(lambda: execute(idempotency_service, alice, probe, session=inactive), 503)
    other = create_engine(pg_engine.url, hide_parameters=True)
    def no_connect(*args, **kwargs):
        pytest.fail("Wrong engine must be rejected before any connection", pytrace=False)
    event.listen(other, "do_connect", no_connect)
    try:
        for model in (None, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                PrivacyNoticeVersion, PrivacyAdmissionRecord, AuditEvent, IdempotencyRecord):
            with Session(other if model is None else pg_engine,
                    binds=None if model is None else {model: other}) as session:
                session.begin()
                denied(lambda: execute(idempotency_service, alice, probe, session=session), 503)
                session.rollback()
        with Session(pg_engine) as session:
            session.begin()
            execute(idempotency_service, alice, probe, session=session)
            denied(lambda: execute(idempotency_service, bob, probe, session=session), 403)
            session.rollback()
    finally:
        other.dispose()
    assert not rows(pg_engine, IdempotencyRecord) and not rows(pg_engine, AuthOwnedResource)


def test_default_disabled_policy_and_forged_configuration_remain_closed(idempotency_factory,
        admitted_actor_factory, registry_probe, pg_engine, auth_service, runtime, idempotency_store):
    closed = idempotency_factory(policy=IdempotencyPolicy())
    _, principal = actor_case(admitted_actor_factory, closed)
    probe = registry_probe()
    denied(lambda: execute(closed, principal, probe), 503)
    forged = IdempotencyPolicy().model_copy(update={"enabled": True, "ttl_seconds": True})
    denied(lambda: idempotency_factory(policy=forged), 503)
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.service import AuthService
    from services.api.app.idempotency.service import IdempotencyService
    from services.api.app.privacy.config import PrivacySettings
    from services.api.app.privacy.service import PrivacyService
    production = runtime.model_copy(update={"app_environment": "production"})
    identity = AuthService(auth_service.settings, production, auth_service.store,
        KeycloakOidcAdapter(auth_service.settings, production), clock=auth_service._now)
    production_service = IdempotencyService(identity, PrivacyService(identity, PrivacySettings()),
        idempotency_store, IdempotencyPolicy(enabled=True, ttl_seconds=86400))
    denied(lambda: execute(production_service, principal, probe), 401)
    assert probe.calls == 0 and not rows(pg_engine, IdempotencyRecord)


def test_independent_migration_repeat_and_downgrade_preserve_parent_profiles(idempotency_service,
        idempotency_store, admitted_actor_factory, registry_probe, pg_engine, tmp_path, monkeypatch):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.seed import seed
    from services.api.app.admissions_catalog.store import migrate_catalog
    from services.api.app.storage.store import migrate_storage
    _, principal = actor_case(admitted_actor_factory, idempotency_service)
    execute(idempotency_service, principal, registry_probe())
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    migrate_catalog(pg_engine)
    migrate_storage(pg_engine)
    def preserved():
        with pg_engine.connect() as connection:
            tables = inspect(connection).get_table_names()
            return {name: connection.execute(text('SELECT * FROM "' + name + '" ORDER BY 1')).all()
                for name in tables if not name.startswith("idempotency_")}
    before = preserved()
    assert len(IdempotencyBase.metadata.tables) == 1
    migrate_idempotency(pg_engine)
    migrate_idempotency(pg_engine)
    idempotency_store.assert_schema_ready()
    assert preserved() == before
    with pg_engine.begin() as connection:
        configuration = migration_config()
        configuration.attributes["connection"] = connection
        command.downgrade(configuration, "base")
    assert "idempotency_records" not in inspect(pg_engine).get_table_names()
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM idempotency_alembic_version")) == 0
    assert preserved() == before
    migrate_idempotency(pg_engine)
    assert rows(pg_engine, IdempotencyRecord) == [] and preserved() == before
