"""Observe actual PostgreSQL locks rather than infer ordering from sleeps."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, get_ident
import time
from uuid import UUID

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session


pytestmark = pytest.mark.postgres


def observe_wait(engine, reached, pids):
    def capture(connection, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement.upper():
            pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            reached.set()
    event.listen(engine, "before_cursor_execute", capture)
    return capture


def require_actual_lock_wait(engine, reached, pids):
    assert reached.wait(5), "Worker did not issue a row-lock query"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            waiting = connection.scalar(text(
                "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"), {"pid": pids[0]})
        if waiting:
            return
        time.sleep(0.01)
    pytest.fail("PostgreSQL never reported the worker blocked on the held row lock")


@pytest.mark.parametrize("change", ("session-expiry", "role-expiry", "role-revoked", "account-disabled",
                                  "owner-changed", "resource-deleted", "parent-deleted"))
def test_lock_wait_rechecks_current_time_roles_owner_and_parent(
    authorizer, student, other_student, owned_resources, pg_engine, clock, session_settings, change,
):
    from services.api.app.auth.authorization import AuthorizationError
    from services.api.app.auth.models import AuthOwnedResource, AuthUser, AuthUserRole

    kind = "attachment" if change == "parent-deleted" else "plan"
    resource = owned_resources["own"][kind]
    effects, pids = [], []
    reached = Event()

    def attempt():
        try:
            authorizer.execute_owned(student, kind, resource.id, "read",
                lambda database, current, row: effects.append(row.id))
            return 200
        except AuthorizationError as error:
            return error.status_code

    with Session(pg_engine) as locker:
        if change in ("session-expiry", "role-expiry", "role-revoked", "account-disabled"):
            locked = locker.scalar(select(AuthUser).where(AuthUser.id == student.user_id).with_for_update())
            if change == "role-expiry":
                locker.get(AuthUserRole, (student.user_id, "student")).expires_at = clock() + timedelta(seconds=1)
                locker.flush()
        else:
            target_id = owned_resources["own"]["profile"].id if change == "parent-deleted" else resource.id
            locked = locker.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == target_id).with_for_update())
        listener = observe_wait(pg_engine, reached, pids)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            pending = executor.submit(attempt)
            require_actual_lock_wait(pg_engine, reached, pids)
            if change == "session-expiry":
                clock.advance(session_settings.session_ttl_seconds)
            elif change == "role-expiry":
                clock.advance(1)
            elif change == "role-revoked":
                locker.get(AuthUserRole, (student.user_id, "student")).revoked_at = clock()
            elif change == "account-disabled":
                locked.status = "disabled"
            elif change == "owner-changed":
                locked.owner_user_id = other_student.user_id
            else:
                locked.status = "deleted"
            locker.commit()
            expected = 401 if change in ("session-expiry", "account-disabled") else (
                403 if change in ("role-expiry", "role-revoked") else 404)
            assert pending.result(timeout=10) == expected
            assert effects == []
        finally:
            locker.rollback()
            executor.shutdown(wait=True)
            event.remove(pg_engine, "before_cursor_execute", listener)


def test_local_execution_serializes_with_trusted_role_revocation(
    authorizer, student, owned_resources, auth_store, pg_engine, clock,
):
    from services.api.app.auth.authorization import AuthorizationError
    from services.api.app.auth.models import AuthOwnedResource

    resource = owned_resources["own"]["plan"]
    entered, release, revoke_reached = Event(), Event(), Event()
    pids, order = [], []

    def operation(database, current, row):
        assert database.in_transaction()
        entered.set()
        assert release.wait(10), "Test did not release the authorized operation"
        database.get(AuthOwnedResource, row.id).version = 2
        order.append("operation")
        return "committed"

    def execute():
        return authorizer.execute_owned(student, "plan", resource.id, "write", operation, expected_version=1)

    def revoke():
        result = auth_store.revoke_role(student.user_id, "student", now=clock())
        order.append("revoke")
        return result

    executor = ThreadPoolExecutor(max_workers=2)
    listener = None
    try:
        pending_operation = executor.submit(execute)
        assert entered.wait(5)
        listener = observe_wait(pg_engine, revoke_reached, pids)
        pending_revoke = executor.submit(revoke)
        require_actual_lock_wait(pg_engine, revoke_reached, pids)
        assert not pending_revoke.done()
        release.set()
        assert pending_operation.result(timeout=10) == "committed"
        assert pending_revoke.result(timeout=10) is True
    finally:
        release.set()
        executor.shutdown(wait=True)
        if listener is not None:
            event.remove(pg_engine, "before_cursor_execute", listener)
    assert order == ["operation", "revoke"]
    with Session(pg_engine) as database:
        assert database.get(AuthOwnedResource, resource.id).version == 2
    effects = []
    with pytest.raises(AuthorizationError) as denied:
        authorizer.execute_owned(student, "plan", resource.id, "read",
            lambda database, current, row: effects.append(row.id))
    assert denied.value.status_code == 403 and effects == []


def test_t07_execute_and_t06_logout_follow_account_first_lock_order(
    authorizer, principal_factory, auth_service, pg_engine,
):
    """Pause after account acquisition to expose a session-first logout cycle."""
    from services.api.app.auth.authorization import AuthorizationError
    from services.api.app.auth.models import AuthOwnedResource

    principal, cookie = principal_factory()
    resource = authorizer.register_owned(principal, "plan")
    token = auth_service.get_csrf_token(cookie).token
    execution_at_session, release_execution, logout_at_lock = Event(), Event(), Event()
    thread_ids, logout_pids, order = {}, [], []
    paused = []

    def observer(connection, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" not in statement.upper():
            return
        if get_ident() == thread_ids.get("execute") and "AUTH_SESSIONS" in statement.upper() and not paused:
            paused.append(True)
            execution_at_session.set()
            assert release_execution.wait(10), "Test did not release T07 session acquisition"
        elif get_ident() == thread_ids.get("logout"):
            logout_pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            logout_at_lock.set()

    def local_operation(database, current, row):
        database.get(AuthOwnedResource, row.id).version = 2
        order.append("operation")
        return "committed"

    def execute():
        thread_ids["execute"] = get_ident()
        return authorizer.execute_owned(principal, "plan", resource.id, "write",
            local_operation, expected_version=1)

    def logout():
        thread_ids["logout"] = get_ident()
        auth_service.logout(cookie, token)
        order.append("logout")

    event.listen(pg_engine, "before_cursor_execute", observer)
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        operation = executor.submit(execute)
        assert execution_at_session.wait(5), "T07 never reached account-then-session acquisition"
        pending_logout = executor.submit(logout)
        require_actual_lock_wait(pg_engine, logout_at_lock, logout_pids)
        assert not pending_logout.done()
        release_execution.set()
        assert operation.result(timeout=10) == "committed"
        assert pending_logout.result(timeout=10) is None
    finally:
        release_execution.set()
        executor.shutdown(wait=True)
        event.remove(pg_engine, "before_cursor_execute", observer)
    assert order == ["operation", "logout"]
    with Session(pg_engine) as database:
        assert database.get(AuthOwnedResource, resource.id).version == 2
    with pytest.raises(AuthorizationError) as revoked:
        authorizer.require_owned(principal, "plan", resource.id)
    assert revoked.value.status_code == 401


@pytest.mark.parametrize("change", ("owner-changed", "resource-deleted", "parent-deleted",
                                   "role-expiry", "session-expiry"))
def test_list_waits_for_resource_or_parent_then_rechecks_scope_and_count(
    authorizer, student, other_student, owned_resources, auth_store, pg_engine, clock,
    session_settings, change,
):
    from services.api.app.auth.authorization import AuthorizationError
    from services.api.app.auth.models import AuthOwnedResource

    kind = "attachment" if change == "parent-deleted" else "plan"
    target_id = owned_resources["own"]["profile" if change == "parent-deleted" else "plan"].id
    if change == "role-expiry":
        auth_store.assign_role(student.user_id, "student", now=clock(), expires_at=clock() + timedelta(seconds=1))
    reached, pids = Event(), []

    def read():
        try:
            return authorizer.list_owned(student, kind, limit=10)
        except AuthorizationError as error:
            return error.status_code

    with Session(pg_engine) as locker:
        row = locker.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == target_id).with_for_update())
        listener = observe_wait(pg_engine, reached, pids)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            pending = executor.submit(read)
            require_actual_lock_wait(pg_engine, reached, pids)
            if change == "owner-changed":
                row.owner_user_id = other_student.user_id
            elif change in ("resource-deleted", "parent-deleted"):
                row.status = "deleted"
            elif change == "role-expiry":
                clock.advance(1)
            else:
                clock.advance(session_settings.session_ttl_seconds)
            locker.commit()
            result = pending.result(timeout=10)
            if change in ("role-expiry", "session-expiry"):
                assert result == (403 if change == "role-expiry" else 401)
            else:
                assert result.items == () and result.total == 0 and result.next_cursor is None
        finally:
            locker.rollback()
            executor.shutdown(wait=True)
            event.remove(pg_engine, "before_cursor_execute", listener)


def test_list_refill_after_parent_withdrawal_locks_new_window_candidates(authorizer, student, pg_engine):
    """The replacement row was outside the original limit+1 locked window."""
    from services.api.app.auth.models import AuthOwnedResource

    roots = [authorizer.register_owned(student, "profile", resource_id=UUID(int=value))
             for value in (10, 20, 30)]
    children = [authorizer.register_owned(student, "attachment", resource_id=UUID(int=value), parent_id=root.id)
                for value, root in zip((100, 200, 300), roots)]
    reached, pids = Event(), []
    with Session(pg_engine) as first_locker, Session(pg_engine) as replacement_locker:
        first_parent = first_locker.scalar(select(AuthOwnedResource).where(
            AuthOwnedResource.id == roots[0].id).with_for_update())
        replacement = replacement_locker.scalar(select(AuthOwnedResource).where(
            AuthOwnedResource.id == children[2].id).with_for_update())
        replacement_pid = replacement_locker.connection().exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
        listener = observe_wait(pg_engine, reached, pids)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            pending = executor.submit(authorizer.list_owned, student, "attachment", limit=1)
            require_actual_lock_wait(pg_engine, reached, pids)
            first_parent.status = "deleted"
            first_locker.commit()
            deadline = time.monotonic() + 5
            blocked_on_replacement = False
            while time.monotonic() < deadline:
                with pg_engine.connect() as observer:
                    blocked_on_replacement = observer.scalar(text(
                        "SELECT :blocker = ANY(pg_blocking_pids(:worker))"),
                        {"blocker": replacement_pid, "worker": pids[0]})
                if blocked_on_replacement:
                    break
                if pending.done():
                    pytest.fail("List completed without locking the replacement candidate")
                time.sleep(0.01)
            assert blocked_on_replacement, "The newly included lookahead resource was not row-locked"
            replacement.status = "deleted"
            replacement_locker.commit()
            page = pending.result(timeout=10)
            assert [row.id for row in page.items] == [children[1].id]
            assert page.total == 1 and page.next_cursor is None
        finally:
            first_locker.rollback()
            replacement_locker.rollback()
            executor.shutdown(wait=True)
            event.remove(pg_engine, "before_cursor_execute", listener)
