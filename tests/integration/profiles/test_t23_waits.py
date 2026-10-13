"""Observe PostgreSQL waits at the last SQL, not just advance a mock in a getter."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import event, insert, select, text, update
from sqlalchemy.orm import Session

from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUserRole
from services.api.app.privacy.models import PrivacyAdmissionRecord
from services.api.app.profiles.models import ProfileRoot, ProfileVersion

from .test_t23_service import KEY, append_input, denied, durable_state, require_blocked, rows


pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("operation,expiry,status", [
    ("create", "role", 403),
    ("append", "age", 403),
    ("read", "session", 401),
    ("read", "version", 409),
    ("create", "receipt", 409),
])
def test_actual_wait_after_final_role_query_cannot_commit_or_return_past_deadline(operation, expiry, status,
        created, profile_service, principal, create_input, pg_engine, clock, monkeypatch):
    if expiry == "receipt":
        from services.api.app.idempotency.schemas import IdempotencyPolicy
        from services.api.app.idempotency.service import IdempotencyService
        from services.api.app.profiles.service import ProfileService
        from services.api.app.profiles.schemas import ProfilePolicy
        # Explicit 1-second fixture TTL, not a production policy or a changed
        # frozen service. The original file/profile deadlines remain untouched.
        idempotency = IdempotencyService(profile_service.auth_service, profile_service.privacy_service,
            profile_service.idempotency_service.store, IdempotencyPolicy(enabled=True, ttl_seconds=1))
        profile_service = ProfileService(profile_service.auth_service, profile_service.privacy_service,
            idempotency, profile_service.store, ProfilePolicy(enabled=True))
    target = created.version.profile_id
    with Session(pg_engine) as session, session.begin():
        deadline = clock() + timedelta(seconds=1)
        if expiry == "session":
            session.get(AuthSession, principal.session_id).expires_at = deadline
        elif expiry == "role":
            session.get(AuthUserRole, (principal.user_id, "student")).expires_at = deadline
        elif expiry == "age":
            session.execute(update(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == principal.user_id)
                            .values(declaration_expires_at=deadline))
        elif expiry == "version":
            original = dict(next(r for r in rows(pg_engine, ProfileVersion) if r["id"] == created.version.version_id))
            original.update(id=uuid4(), version=2, expires_at=deadline)
            session.execute(insert(ProfileVersion).values(**original))
            session.get(ProfileRoot, target).current_version_id = original["id"]
            session.get(ProfileRoot, target).current_version = 2
            session.get(AuthOwnedResource, target).version = 2
    before = durable_state(pg_engine)
    final_calls, reached, worker_pid = [], Event(), []
    original_final = profile_service._final
    target_call = 3 if operation == "create" else 1
    def observed_final(session, *args, **kwargs):
        final_calls.append(True)
        connection = session.connection()
        active = len(final_calls) == target_call
        if active:
            connection.info["t23_final_roles_seen"] = 0
        try:
            return original_final(session, *args, **kwargs)
        finally:
            if active:
                connection.info.pop("t23_final_roles_seen", None)
    monkeypatch.setattr(profile_service, "_final", observed_final)
    lock_id = uuid4().int % (2 ** 62)
    def wait_after_roles(connection, cursor, statement, parameters, context, executemany):
        if ("t23_final_roles_seen" in connection.info and "FROM auth_user_roles" in statement
                and "FOR UPDATE" in statement.upper()):
            connection.info["t23_final_roles_seen"] += 1
            # _final refreshes the Principal and then explicitly re-reads roles:
            # hold after that second SQL result, before its SQL-free fresh clock.
            if connection.info["t23_final_roles_seen"] == 2:
                worker_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                reached.set()
                connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
    event.listen(pg_engine, "after_cursor_execute", wait_after_roles)
    def attempt():
        if operation == "create":
            return profile_service.create_profile(principal, create_input, type(KEY)("DEMO_T23_WAIT_KEY"))
        if operation == "append":
            return profile_service.append_version(principal, target, append_input())
        return profile_service.get_profile(principal, target)
    with Session(pg_engine) as blocker:
        blocker.begin()
        blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        blocker.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(attempt)
            try:
                assert reached.wait(20), "Operation did not reach its final role SQL"
                require_blocked(pg_engine, worker_pid, blocker_pid, pending)
                clock.advance(2 if expiry == "receipt" else 1)
                blocker.commit()
                denied(lambda: pending.result(timeout=30), status)
            finally:
                blocker.rollback()
                event.remove(pg_engine, "after_cursor_execute", wait_after_roles)
    assert len(final_calls) >= target_call
    assert durable_state(pg_engine) == before


def test_waiting_on_required_success_audit_does_not_extend_adult_permission(created, profile_service,
        principal, pg_engine, clock):
    lock_id = uuid4().int % (2 ** 62)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t23_wait_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF NEW.action='authorization.owned.execute' AND NEW.object_type='profile' THEN "
            f"PERFORM pg_advisory_xact_lock({lock_id}); END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER t23_audit_wait BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION t23_wait_audit()"))
        connection.execute(update(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == principal.user_id)
            .values(declaration_expires_at=clock() + timedelta(seconds=1)))
    before = durable_state(pg_engine)
    reached, worker_pid = Event(), []
    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO auth_audit_events"):
            worker_pid[:] = [connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()]
            reached.set()
    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        with Session(pg_engine) as blocker:
            blocker.begin()
            pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            blocker.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(profile_service.append_version, principal, created.version.profile_id, append_input())
                try:
                    assert reached.wait(15)
                    require_blocked(pg_engine, worker_pid, pid, pending)
                    clock.advance(1)
                    blocker.commit()
                    denied(lambda: pending.result(timeout=30), 403)
                finally:
                    blocker.rollback()
        assert durable_state(pg_engine) == before
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)
        with pg_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER t23_audit_wait ON auth_audit_events"))
            connection.execute(text("DROP FUNCTION t23_wait_audit()"))
