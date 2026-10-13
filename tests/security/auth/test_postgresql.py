"""Incremental migration, stable token initialization and revocation on real PG."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
import time
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import event, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


pytestmark = pytest.mark.postgres


def revision(engine, target):
    from services.api.app.auth.store import migration_config

    configuration = migration_config()
    with engine.begin() as connection:
        configuration.attributes["connection"] = connection
        command.upgrade(configuration, target)


def old_session(engine, clock):
    from services.api.app.auth.service import digest_secret

    user_id, session_id = uuid4(), uuid4()
    cookie = "T06_EXISTING_SESSION_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO auth_users (id,status,is_synthetic,created_at) VALUES (:id,'active',true,:created)"),
                           {"id": user_id, "created": clock()})
        connection.execute(text("INSERT INTO auth_sessions (id,user_id,session_digest,created_at,expires_at,revoked_at) "
            "VALUES (:id,:user,:digest,:created,:expiry,NULL)"),
            {"id": session_id, "user": user_id, "digest": digest_secret(cookie, "session"),
             "created": clock(), "expiry": clock() + timedelta(seconds=3600)})
    return user_id, session_id, cookie


def test_t05_session_upgrade_preserves_old_values_and_lazily_initializes_csrf(
    pg_engine, clock, session_settings, runtime, oidc_adapter,
):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.service import AuthService
    from services.api.app.auth.store import AuthStore, migrate_auth

    revision(pg_engine, "0001_auth_t05")
    user_id, _, cookie = old_session(pg_engine, clock)
    with pg_engine.connect() as connection:
        before = dict(connection.execute(text("SELECT * FROM auth_sessions")).mappings().one())
    migrate_auth(pg_engine)
    migrate_auth(pg_engine)
    with pg_engine.connect() as connection:
        after = dict(connection.execute(text("SELECT * FROM auth_sessions")).mappings().one())
        assert connection.scalar(text("SELECT version_num FROM auth_alembic_version")) == "0006_audit_t10"
    assert {field: after[field] for field in before} == before
    assert all(after[field] is None for field in set(after) - set(before))
    service = AuthService(session_settings, runtime, AuthStore(pg_engine), oidc_adapter, clock=clock)
    assert service.get_session(cookie).user_id == user_id
    proof = service.get_csrf_token(cookie)
    assert service.get_csrf_token(cookie) == proof
    assert proof.expires_at == before["expires_at"]
    with pytest.raises(AuthFlowError) as caught:
        service.check_admin_assurance(cookie, permission_verifier=lambda _: True)
    assert caught.value.status_code == 403


def test_unupgraded_schema_readiness_is_503_and_does_not_run_ddl(pg_engine, session_settings, runtime):
    from sqlalchemy.engine import Engine
    from services.api.app.api.identity import create_identity_app
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.store import AuthStore
    from services.api.app.settings import V2RuntimeSettings

    revision(pg_engine, "0001_auth_t05")
    before = {name: inspect(pg_engine).get_columns(name) for name in inspect(pg_engine).get_table_names()}
    with pytest.raises(AuthFlowError) as caught:
        AuthStore(pg_engine).assert_schema_ready()
    assert caught.value.status_code == 503
    with pg_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    url = pg_engine.url.set(query={"options": "-csearch_path=" + schema}).render_as_string(hide_password=False)
    configured = V2RuntimeSettings(**{**runtime.model_dump(), "database_url": url}, _env_file=None)
    ddl = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ")):
            ddl.append(statement)

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        with pytest.raises(AuthFlowError) as startup:
            create_identity_app(configured, session_settings)
        assert startup.value.status_code == 503
        assert str(startup.value) == "Authentication service is unavailable"
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert ddl == []
    after = {name: inspect(pg_engine).get_columns(name) for name in inspect(pg_engine).get_table_names()}
    assert {name: [column["name"] for column in columns] for name, columns in before.items()} == {
        name: [column["name"] for column in columns] for name, columns in after.items()}
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM auth_alembic_version")) == "0001_auth_t05"


def snapshot(engine, names):
    with engine.connect() as connection:
        return {name: sorted([dict(row) for row in connection.execute(text(f'SELECT * FROM "{name}"')).mappings()],
                             key=repr) for name in names}


def test_t06_migration_and_rollback_preserve_legacy_m0_data(pg_engine, clock):
    from services.api.app.migrations import migrate
    from services.api.app.seed import seed
    from services.api.app.auth.store import migration_config, migrate_auth

    migrate(pg_engine)
    seed(pg_engine)
    names = inspect(pg_engine).get_table_names()
    assert len(names) == 8 and "alembic_version" in names
    baseline = snapshot(pg_engine, names)
    revision(pg_engine, "0001_auth_t05")
    old_session(pg_engine, clock)
    legacy_sessions = snapshot(pg_engine, ["auth_sessions"])
    migrate_auth(pg_engine)
    assert snapshot(pg_engine, names) == baseline
    config = migration_config()
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_auth_t05")
    assert snapshot(pg_engine, names) == baseline
    assert snapshot(pg_engine, ["auth_sessions"]) == legacy_sessions
    migrate_auth(pg_engine)
    assert snapshot(pg_engine, names) == baseline


@pytest.mark.parametrize("case", ["digest-only", "cipher-only", "short-digest", "orphan-strength", "issuer-only", "future-auth"])
def test_database_rejects_partial_or_impossible_proofs(auth_store, pg_engine, clock, case):
    from services.api.app.auth.models import AuthSession

    _, session_id, _ = old_session(pg_engine, clock)
    values = {
        "digest-only": {"csrf_digest": "d" * 64},
        "cipher-only": {"csrf_encrypted_token": "cipher"},
        "short-digest": {"csrf_digest": "short", "csrf_encrypted_token": "cipher"},
        "orphan-strength": {"assurance_acr": "T06_MFA"},
        "issuer-only": {"verified_issuer": "https://idp.test.invalid/realms/students"},
        "future-auth": {"verified_issuer": "https://idp.test.invalid/realms/students", "verified_client_id": "client",
                        "assurance_auth_time": clock() + timedelta(seconds=1)},
    }[case]
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as database, database.begin():
            database.execute(update(AuthSession).where(AuthSession.id == session_id).values(**values))


def test_concurrent_csrf_initialization_returns_one_stable_token(auth_service, logged_in, pg_engine):
    from services.api.app.auth.models import AuthSession

    barrier = Barrier(2)

    def retrieve():
        barrier.wait(timeout=5)
        return auth_service.get_csrf_token(logged_in).token.get_secret_value()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(retrieve) for _ in range(2)]
        tokens = [future.result(timeout=10) for future in futures]
    assert tokens[0] == tokens[1]
    with Session(pg_engine) as database:
        row = database.scalar(select(AuthSession))
        assert row.csrf_digest is not None and row.csrf_encrypted_token is not None


def test_concurrent_logout_has_one_atomic_winner(auth_service, logged_in, csrf_token, pg_engine):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.models import AuthSession

    barrier = Barrier(2)

    def leave():
        barrier.wait(timeout=5)
        try:
            auth_service.logout(logged_in, csrf_token)
            return 200
        except AuthFlowError as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(leave) for _ in range(2)]
        assert sorted(future.result(timeout=10) for future in futures) == [200, 401]
    with Session(pg_engine) as database:
        row = database.scalar(select(AuthSession))
        assert row.revoked_at is not None and row.csrf_digest is None and row.csrf_encrypted_token is None


@pytest.mark.parametrize("operation", ["csrf", "logout"])
def test_expiry_while_waiting_for_session_lock_cannot_mint_or_revoke(
    auth_service, logged_in, pg_engine, clock, session_settings, operation,
):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.models import AuthSession

    token = auth_service.get_csrf_token(logged_in).token if operation == "logout" else None
    queued = Event()
    worker_pid = []

    def capture_pid(connection, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement.upper() and "AUTH_SESSIONS" in statement.upper():
            worker_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            queued.set()

    def attempt():
        try:
            if operation == "csrf":
                auth_service.get_csrf_token(logged_in)
            else:
                auth_service.logout(logged_in, token)
            return "unexpected success"
        except AuthFlowError as error:
            return error.status_code

    with Session(pg_engine) as locker:
        row = locker.scalar(select(AuthSession).with_for_update())
        event.listen(pg_engine, "before_cursor_execute", capture_pid)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            pending = executor.submit(attempt)
            assert queued.wait(5), "Worker never reached the locked session query"
            deadline = time.monotonic() + 5
            waiting = False
            while time.monotonic() < deadline:
                with pg_engine.connect() as observer:
                    waiting = observer.scalar(text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"),
                                              {"pid": worker_pid[0]})
                if waiting:
                    break
                time.sleep(0.01)
            assert waiting, "Did not observe PostgreSQL blocking the worker on the held row lock"
            clock.advance(session_settings.session_ttl_seconds)
            locker.commit()
            assert pending.result(timeout=10) == 401
        finally:
            locker.rollback()
            executor.shutdown(wait=True)
            event.remove(pg_engine, "before_cursor_execute", capture_pid)
    with Session(pg_engine) as database:
        current = database.scalar(select(AuthSession))
        assert current.revoked_at is None
        if operation == "csrf":
            assert current.csrf_digest is None and current.csrf_encrypted_token is None
        else:
            assert current.csrf_digest is not None and current.csrf_encrypted_token is not None
