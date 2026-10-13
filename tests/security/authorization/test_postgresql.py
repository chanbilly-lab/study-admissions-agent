"""T07 incremental migration, PostgreSQL constraints and SQL authorization."""

from datetime import timedelta
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import event, inspect, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


pytestmark = pytest.mark.postgres
KINDS = ("profile", "plan", "attachment", "export", "job")


def upgrade(engine, target):
    from services.api.app.auth.store import migration_config

    configuration = migration_config()
    with engine.begin() as connection:
        configuration.attributes["connection"] = connection
        command.upgrade(configuration, target)


def snapshot(engine, names):
    with engine.connect() as connection:
        return {name: sorted(
            [dict(row) for row in connection.execute(text(f'SELECT * FROM "{name}"')).mappings()], key=repr)
            for name in names}


def test_t06_upgrade_preserves_sessions_csrf_assurance_and_no_auto_roles(
    pg_engine, clock, session_settings, runtime, oidc_adapter,
):
    from cryptography.fernet import Fernet
    from services.api.app.auth.models import AuthSession, AuthUser
    from services.api.app.auth.service import AuthService, digest_secret
    from services.api.app.auth.store import AuthStore, migrate_auth

    upgrade(pg_engine, "0002_auth_t06")
    user_id, session_id = uuid4(), uuid4()
    cookie = "T07_SYNTHETIC_EXISTING_COOKIE_" + uuid4().hex
    token = "A" * 43
    cipher = Fernet(session_settings.context_encryption_key.get_secret_value().encode("ascii"))
    with Session(pg_engine) as database, database.begin():
        database.add(AuthUser(id=user_id, status="active", is_synthetic=True, created_at=clock()))
        database.flush()
        database.add(AuthSession(id=session_id, user_id=user_id,
            session_digest=digest_secret(cookie, "session"), created_at=clock(),
            expires_at=clock() + timedelta(hours=1), revoked_at=None,
            csrf_digest=digest_secret(token, "csrf"),
            csrf_encrypted_token=cipher.encrypt(token.encode("ascii")).decode("ascii"),
            verified_issuer=session_settings.provider.issuer, verified_client_id=session_settings.provider.client_id,
            assurance_acr="T07_SYNTHETIC_MFA", assurance_amr=["pwd", "otp"], assurance_auth_time=clock()))
    names = ("auth_users", "auth_identities", "auth_login_transactions", "auth_sessions")
    before = snapshot(pg_engine, names)
    migrate_auth(pg_engine)
    migrate_auth(pg_engine)
    assert snapshot(pg_engine, names) == before
    assert set(inspect(pg_engine).get_table_names()) == {
        *names, "auth_user_roles", "auth_owned_resources", "auth_alembic_version",
        "privacy_notice_versions", "privacy_admission_records",
        "auth_sharing_states", "auth_access_grants", "grant_fields", "grant_actions", "auth_audit_events",
    }
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM auth_alembic_version")) == "0006_audit_t10"
        assert connection.scalar(text("SELECT count(*) FROM auth_user_roles")) == 0
        assert connection.scalar(text("SELECT count(*) FROM auth_owned_resources")) == 0
    service = AuthService(session_settings, runtime, AuthStore(pg_engine), oidc_adapter, clock=clock)
    assert service.get_session(cookie).user_id == user_id
    assert service.get_csrf_token(cookie).token.get_secret_value() == token
    principal = service.get_principal(cookie)
    assert principal.user_id == user_id and principal.roles == ()


def test_unupgraded_identity_factory_is_503_without_ddl(pg_engine, session_settings, runtime):
    from services.api.app.api.identity import create_identity_app
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.store import AuthStore
    from services.api.app.settings import V2RuntimeSettings

    upgrade(pg_engine, "0002_auth_t06")
    before = {name: [column["name"] for column in inspect(pg_engine).get_columns(name)]
              for name in inspect(pg_engine).get_table_names()}
    with pytest.raises(AuthFlowError) as readiness:
        AuthStore(pg_engine).assert_schema_ready()
    assert readiness.value.status_code == 503
    with pg_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    configured = V2RuntimeSettings(**{**runtime.model_dump(),
        "database_url": pg_engine.url.set(query={"options": "-csearch_path=" + schema}).render_as_string(hide_password=False)},
        _env_file=None)
    ddl = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ")):
            ddl.append(statement)

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        with pytest.raises(AuthFlowError) as startup:
            create_identity_app(configured, session_settings)
        assert startup.value.status_code == 503
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert ddl == []
    assert before == {name: [column["name"] for column in inspect(pg_engine).get_columns(name)]
                      for name in inspect(pg_engine).get_table_names()}


def test_new_auth_chain_downgrade_keeps_frozen_m0_and_t06_rows(pg_engine, clock):
    from services.api.app.auth.store import migrate_auth, migration_config
    from services.api.app.migrations import migrate
    from services.api.app.seed import seed

    migrate(pg_engine)
    seed(pg_engine)
    legacy_names = inspect(pg_engine).get_table_names()
    assert len(legacy_names) == 8
    legacy = snapshot(pg_engine, legacy_names)
    upgrade(pg_engine, "0002_auth_t06")
    with pg_engine.begin() as connection:
        connection.execute(text("INSERT INTO auth_users (id,status,is_synthetic,created_at) "
                                "VALUES (:id,'active',true,:now)"), {"id": uuid4(), "now": clock()})
    t06 = snapshot(pg_engine, ("auth_users", "auth_identities", "auth_login_transactions", "auth_sessions"))
    migrate_auth(pg_engine)
    assert snapshot(pg_engine, legacy_names) == legacy
    configuration = migration_config()
    with pg_engine.begin() as connection:
        configuration.attributes["connection"] = connection
        command.downgrade(configuration, "0002_auth_t06")
    assert snapshot(pg_engine, legacy_names) == legacy
    assert snapshot(pg_engine, t06) == t06
    assert "auth_user_roles" not in inspect(pg_engine).get_table_names()
    assert "auth_owned_resources" not in inspect(pg_engine).get_table_names()
    migrate_auth(pg_engine)
    assert snapshot(pg_engine, legacy_names) == legacy and snapshot(pg_engine, t06) == t06


@pytest.mark.parametrize("case", ("unknown-role", "missing-user", "duplicate", "invalid-expiry", "invalid-revocation"))
def test_postgresql_role_constraints(authorizer, student, pg_engine, clock, case):
    from services.api.app.auth.models import AuthUserRole

    values = dict(user_id=student.user_id, role="operations", granted_at=clock(), expires_at=None, revoked_at=None)
    if case == "unknown-role":
        values["role"] = "super_admin"
    elif case == "missing-user":
        values["user_id"] = uuid4()
    elif case == "duplicate":
        values["role"] = "student"
    elif case == "invalid-expiry":
        values["expires_at"] = clock()
    else:
        values["revoked_at"] = clock() - timedelta(seconds=1)
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as database, database.begin():
            database.add(AuthUserRole(**values))


@pytest.mark.parametrize("case", ("unknown-kind", "unknown-status", "zero-version", "orphan-owner",
                                  "root-with-parent", "child-no-parent", "foreign-parent"))
def test_postgresql_resource_constraints(authorizer, student, other_student, owned_resources, pg_engine, case):
    from services.api.app.auth.models import AuthOwnedResource

    own, foreign = owned_resources["own"], owned_resources["foreign"]
    values = dict(id=uuid4(), resource_type="profile", owner_user_id=student.user_id,
                  status="active", version=1, is_synthetic=True, parent_id=None)
    if case == "unknown-kind":
        values["resource_type"] = "all_students"
    elif case == "unknown-status":
        values["status"] = "public"
    elif case == "zero-version":
        values["version"] = 0
    elif case == "orphan-owner":
        values["owner_user_id"] = uuid4()
    elif case == "root-with-parent":
        values["parent_id"] = own["profile"].id
    elif case == "child-no-parent":
        values["resource_type"] = "attachment"
    elif case == "foreign-parent":
        values.update(resource_type="attachment", parent_id=foreign["profile"].id)
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as database, database.begin():
            database.add(AuthOwnedResource(**values))


@pytest.mark.parametrize("kind", KINDS)
def test_sql_scoped_lists_page_before_materialization(
    authorizer, student, other_student, owned_resources, pg_engine, kind,
):
    records = [owned_resources["own"][kind]]
    for _ in range(2):
        records.append(authorizer.register_owned(student, kind,
            parent_id=None if kind in ("profile", "plan") else owned_resources["own"]["profile"].id))
        authorizer.register_owned(other_student, kind,
            parent_id=None if kind in ("profile", "plan") else owned_resources["foreign"]["profile"].id)
    expected = sorted((row.id for row in records), key=lambda value: value.int)
    sql = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and "auth_owned_resources" in statement.lower():
            sql.append(statement.lower())

    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        first = authorizer.list_owned(student, kind, limit=1)
        second = authorizer.list_owned(student, kind, limit=1, after_id=first.next_cursor)
        third = authorizer.list_owned(student, kind, limit=1, after_id=second.next_cursor)
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
    assert [page.items[0].id for page in (first, second, third)] == expected
    assert [page.total for page in (first, second, third)] == [3, 3, 3]
    assert first.next_cursor is not None and second.next_cursor is not None and third.next_cursor is None
    assert all(row.owner_user_id == student.user_id for page in (first, second, third) for row in page.items)
    assert sql and all("where" in query and "owner_user_id" in query.split("where", 1)[1] for query in sql)
    assert any("limit" in query for query in sql)


@pytest.mark.parametrize("change", ("role-revoked", "owner-changed", "deleted", "parent-deleted", "wrong-parent-kind",
                                   "account-disabled", "session-revoked"))
def test_delayed_reference_and_cache_revalidate_persisted_changes(
    authorizer, student, other_student, owned_resources, pg_engine, auth_store, clock, change,
):
    from services.api.app.auth.authorization import AuthorizationError
    from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUser

    kind = "attachment" if change in ("parent-deleted", "wrong-parent-kind") else (
        "plan" if change == "owner-changed" else "profile")
    resource = owned_resources["own"][kind]
    key = authorizer.cache_key(student, kind, resource.id)
    cache = {key: "T07_SYNTHETIC_PRIVATE_CACHED_VALUE"}
    assert authorizer.cached_value(student, kind, resource.id, cache) == cache[key]
    if change == "role-revoked":
        assert auth_store.revoke_role(student.user_id, "student", now=clock())
    else:
        with Session(pg_engine) as database, database.begin():
            if change == "owner-changed":
                database.get(AuthOwnedResource, resource.id).owner_user_id = other_student.user_id
            elif change == "deleted":
                database.get(AuthOwnedResource, resource.id).status = "deleted"
            elif change == "parent-deleted":
                database.get(AuthOwnedResource, owned_resources["own"]["profile"].id).status = "deleted"
            elif change == "wrong-parent-kind":
                # Same-owner FK is valid, but a derived child cannot authorize another child.
                database.get(AuthOwnedResource, resource.id).parent_id = owned_resources["own"]["export"].id
            elif change == "account-disabled":
                database.get(AuthUser, student.user_id).status = "disabled"
            else:
                database.get(AuthSession, student.session_id).revoked_at = clock()
    effects = []
    for call in (
        lambda: authorizer.cached_value(student, kind, resource.id, cache),
        lambda: authorizer.execute_owned(student, kind, resource.id, "read",
            lambda session, principal, row: effects.append(row.id)),
    ):
        with pytest.raises(AuthorizationError) as caught:
            call()
        assert caught.value.status_code in (401, 403, 404)
        assert "T07_SYNTHETIC_PRIVATE_CACHED_VALUE" not in str(caught.value)
    assert effects == []


def test_owned_operation_uses_the_same_postgresql_transaction(authorizer, student, owned_resources, pg_engine):
    from services.api.app.auth.authorization import AuthorizationError
    from services.api.app.auth.models import AuthOwnedResource

    resource = owned_resources["own"]["profile"]
    seen = []

    def operation(database, current, row):
        assert database.in_transaction() and database.get_bind() is pg_engine
        assert current.user_id == student.user_id and row.owner_user_id == student.user_id
        seen.append(database.scalar(select(AuthOwnedResource.version).where(AuthOwnedResource.id == row.id)))
        database.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == row.id).values(version=7))
        return "local-commit"

    assert authorizer.execute_owned(student, "profile", resource.id, "write", operation,
                                    expected_version=1) == "local-commit"
    with Session(pg_engine) as database:
        assert database.get(AuthOwnedResource, resource.id).version == 7
    assert seen == [1]
    with pytest.raises(AuthorizationError) as stale:
        authorizer.execute_owned(student, "profile", resource.id, "write", operation, expected_version=1)
    assert stale.value.status_code == 409 and seen == [1]

    def rollback(database, current, row):
        database.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == row.id).values(version=9))
        raise RuntimeError("T07_SYNTHETIC_OPERATION_FAILURE")

    with pytest.raises(AuthorizationError) as failure:
        authorizer.execute_owned(student, "profile", resource.id, "write", rollback, expected_version=7)
    assert failure.value.status_code == 503
    assert "T07_SYNTHETIC_OPERATION_FAILURE" not in str(failure.value) + repr(failure.value)
    with Session(pg_engine) as database:
        assert database.get(AuthOwnedResource, resource.id).version == 7
