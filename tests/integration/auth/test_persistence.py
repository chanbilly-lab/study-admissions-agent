"""Real PostgreSQL constraints and concurrent authentication transactions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


pytestmark = pytest.mark.postgres


def test_empty_database_readiness_does_not_create_auth_tables(pg_engine):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.store import AuthStore

    with pytest.raises(AuthFlowError) as caught:
        AuthStore(pg_engine).assert_schema_ready()
    assert caught.value.status_code == 503
    assert inspect(pg_engine).get_table_names() == []


def test_auth_migration_is_independent_repeatable_and_does_not_provision_users(pg_engine):
    from services.api.app.auth.models import AuthIdentity, AuthSession, AuthUser, LoginTransaction
    from services.api.app.auth.store import AuthStore, migrate_auth

    migrate_auth(pg_engine)
    before = set(inspect(pg_engine).get_table_names())
    assert before == {"auth_alembic_version", "auth_users", "auth_identities", "auth_login_transactions", "auth_sessions",
                      "auth_user_roles", "auth_owned_resources", "privacy_notice_versions", "privacy_admission_records",
                      "auth_sharing_states", "auth_access_grants", "grant_fields", "grant_actions", "auth_audit_events"}
    migrate_auth(pg_engine)
    assert set(inspect(pg_engine).get_table_names()) == before
    AuthStore(pg_engine).assert_schema_ready()
    with Session(pg_engine) as session:
        assert session.execute(text("SELECT version_num FROM auth_alembic_version")).scalars().all() == ["0006_audit_t10"]
        for model in (AuthUser, AuthIdentity, AuthSession, LoginTransaction):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        for table in ("auth_user_roles", "auth_owned_resources", "privacy_notice_versions", "privacy_admission_records",
                      "auth_sharing_states", "auth_access_grants", "grant_fields", "grant_actions", "auth_audit_events"):
            assert session.scalar(text(f'SELECT count(*) FROM "{table}"')) == 0
    identity_constraints = inspect(pg_engine).get_unique_constraints("auth_identities")
    assert ("issuer", "subject") in {tuple(item["column_names"]) for item in identity_constraints}
    for table in ("auth_identities", "auth_sessions"):
        foreign_keys = inspect(pg_engine).get_foreign_keys(table)
        assert len(foreign_keys) == 1
        assert foreign_keys[0]["referred_table"] == "auth_users"
        assert foreign_keys[0]["constrained_columns"] == ["user_id"]


def test_auth_upgrade_downgrade_only_changes_its_own_tables_and_preserves_m0(pg_engine):
    from services.api.app.migrations import migrate
    from services.api.app.seed import seed
    from services.api.app.auth.store import migrate_auth, migration_config

    migrate(pg_engine)
    seed(pg_engine)
    old_tables = set(inspect(pg_engine).get_table_names())
    with pg_engine.connect() as connection:
        before = {table: connection.execute(text(f'SELECT * FROM "{table}" ORDER BY 1')).all() for table in old_tables}
    migrate_auth(pg_engine)
    configuration = migration_config()
    with pg_engine.begin() as connection:
        configuration.attributes["connection"] = connection
        command.downgrade(configuration, "base")
    assert old_tables.issubset(inspect(pg_engine).get_table_names())
    assert not {"auth_users", "auth_identities", "auth_sessions", "auth_login_transactions",
                "auth_user_roles", "auth_owned_resources", "privacy_notice_versions", "privacy_admission_records",
                      "auth_sharing_states", "auth_access_grants", "grant_fields", "grant_actions", "auth_audit_events"} & set(inspect(pg_engine).get_table_names())
    with pg_engine.connect() as connection:
        assert {table: connection.execute(text(f'SELECT * FROM "{table}" ORDER BY 1')).all() for table in old_tables} == before
    migrate_auth(pg_engine)
    with pg_engine.connect() as connection:
        assert {table: connection.execute(text(f'SELECT * FROM "{table}" ORDER BY 1')).all() for table in old_tables} == before


def test_database_unique_identity_is_case_sensitive_and_rejects_duplicate_pair(auth_store, account_factory, pg_engine, session_settings, clock):
    from services.api.app.auth.models import AuthIdentity

    owner = account_factory("CaseSubject")
    account_factory("casesubject")
    account_factory("CaseSubject", issuer="https://other.test.invalid/realms/students")
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as session, session.begin():
            session.add(AuthIdentity(id=uuid4(), user_id=owner, issuer=session_settings.provider.issuer,
                                     subject="CaseSubject", created_at=clock()))
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuthIdentity)) == 3


@pytest.mark.parametrize("constraint", ["foreign_key", "bad_status", "session_expiry", "short_digest", "spent_context"])
def test_database_constraints_reject_invalid_auth_records(auth_store, pg_engine, active_account, clock, constraint):
    from services.api.app.auth.models import AuthIdentity, AuthSession, AuthUser, LoginTransaction

    now = clock()
    if constraint == "foreign_key":
        row = AuthIdentity(id=uuid4(), user_id=uuid4(), issuer="https://idp.test.invalid/realms/students",
                           subject="unowned", created_at=now)
    elif constraint == "bad_status":
        row = AuthUser(id=uuid4(), status="client-enabled", is_synthetic=True, created_at=now)
    elif constraint in ("session_expiry", "short_digest"):
        row = AuthSession(id=uuid4(), user_id=active_account, session_digest="short" if constraint == "short_digest" else "a" * 64,
                          created_at=now, expires_at=now if constraint == "session_expiry" else now + timedelta(hours=1), revoked_at=None)
    else:
        row = LoginTransaction(id=uuid4(), state_digest="a" * 64, browser_digest="b" * 64,
            provider_id="p", issuer="https://idp.test.invalid/realms/students", client_id="c", redirect_uri="https://app.test.invalid/cb",
            encrypted_context="retained_secret", issued_at=now, expires_at=now + timedelta(minutes=5), consumed_at=now)
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as session, session.begin():
            session.add(row)


def test_exactly_one_concurrent_callback_consumes_state_and_creates_session(auth_service, idp, active_account, pg_engine):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.models import AuthSession, LoginTransaction

    started = auth_service.start_login()
    code, state = idp.issue_from_authorization(started.authorization_url.get_secret_value())
    gate = Barrier(2)

    def compete():
        gate.wait(timeout=10)
        try:
            return auth_service.complete_login(code, state, started.browser_binding)
        except AuthFlowError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(compete) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sum(not isinstance(result, AuthFlowError) for result in results) == 1
    assert [result.status_code for result in results if isinstance(result, AuthFlowError)] == [401]
    assert sum(method == "POST" for method, _ in idp.requests) == 1
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuthSession)) == 1
        row = session.scalar(select(LoginTransaction))
        assert row.consumed_at is not None and row.encrypted_context is None


def test_state_claim_is_committed_before_provider_io(auth_service, idp, active_account, pg_engine):
    from services.api.app.auth.models import LoginTransaction

    started = auth_service.start_login()
    code, state = idp.issue_from_authorization(started.authorization_url.get_secret_value())
    observed = []

    def check_commit(request):
        with Session(pg_engine) as session:
            row = session.scalar(select(LoginTransaction))
            observed.append(row.consumed_at is not None and row.encrypted_context is None)

    idp.before_request = check_commit
    auth_service.complete_login(code, state, started.browser_binding)
    assert observed and all(observed)


def test_expiry_during_io_consumes_state_but_never_establishes_session(auth_service, idp, active_account, clock, pg_engine):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.models import AuthSession

    started = auth_service.start_login()
    code, state = idp.issue_from_authorization(started.authorization_url.get_secret_value())
    idp.before_request = lambda request: clock.advance(300) if request.method == "POST" else None
    with pytest.raises(AuthFlowError):
        auth_service.complete_login(code, state, started.browser_binding)
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuthSession)) == 0
    idp.before_request = None
    count = len(idp.requests)
    with pytest.raises(AuthFlowError):
        auth_service.complete_login(code, state, started.browser_binding)
    assert len(idp.requests) == count


def test_production_store_never_accepts_synthetic_pre_registered_account(auth_store, active_account, session_settings, clock):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.schemas import IdentityKey

    with pytest.raises(AuthFlowError) as caught:
        auth_store.establish_session(IdentityKey(issuer=session_settings.provider.issuer, subject="T05_SYNTHETIC_STUDENT_A"),
            session_digest="a" * 64, previous_digest=None, now=clock(), expires_at=clock() + timedelta(hours=1), production=True)
    assert caught.value.status_code == 403
