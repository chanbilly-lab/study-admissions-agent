"""T08 independent migration, real constraints, and preserved historical rows."""

from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.auth.models import AuthUser, AuthUserRole
from services.api.app.auth.store import AuthStore, migrate_auth, migration_config
from services.api.app.privacy.models import PrivacyAdmissionRecord


pytestmark = pytest.mark.postgres


def revision(engine, target, *, downgrade=False):
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        (command.downgrade if downgrade else command.upgrade)(config, target)


def snapshot(engine, tables):
    with engine.connect() as connection:
        return {table: connection.execute(text(f'SELECT * FROM "{table}" ORDER BY 1')).all() for table in tables}


def test_incremental_t08_preserves_t07_accounts_roles_metadata_and_m0(pg_engine, clock):
    from services.api.app.migrations import migrate
    from services.api.app.seed import seed
    migrate(pg_engine)
    seed(pg_engine)
    legacy = set(inspect(pg_engine).get_table_names())
    revision(pg_engine, "0003_auth_t07")
    user = uuid4()
    with Session(pg_engine) as session, session.begin():
        session.add(AuthUser(id=user, status="active", is_synthetic=True, created_at=clock()))
        session.flush()
        session.add(AuthUserRole(user_id=user, role="student", granted_at=clock(), revoked_at=None, expires_at=None))
    old = set(inspect(pg_engine).get_table_names()) - {"auth_alembic_version"}
    before = snapshot(pg_engine, old)
    # Freeze this milestone's delta instead of interpreting every later head as T08.
    revision(pg_engine, "0004_privacy_t08")
    revision(pg_engine, "0004_privacy_t08")
    assert snapshot(pg_engine, old) == before
    assert set(inspect(pg_engine).get_table_names()) - old == {"auth_alembic_version", "privacy_notice_versions", "privacy_admission_records"}
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM privacy_notice_versions")) == 0
        assert connection.scalar(text("SELECT count(*) FROM privacy_admission_records")) == 0
    # The current application still requires its explicitly upgraded full head.
    migrate_auth(pg_engine)
    AuthStore(pg_engine).assert_schema_ready()
    assert snapshot(pg_engine, old) == before
    revision(pg_engine, "0003_auth_t07", downgrade=True)
    assert snapshot(pg_engine, old) == before
    assert "privacy_notice_versions" not in inspect(pg_engine).get_table_names()
    migrate_auth(pg_engine)
    assert snapshot(pg_engine, legacy) == {table: before[table] for table in legacy}


def test_unupgraded_readiness_is_read_only(pg_engine):
    from services.api.app.auth.config import AuthFlowError
    revision(pg_engine, "0003_auth_t07")
    before = set(inspect(pg_engine).get_table_names())
    with pytest.raises(AuthFlowError) as caught:
        AuthStore(pg_engine).assert_schema_ready()
    assert caught.value.status_code == 503
    assert set(inspect(pg_engine).get_table_names()) == before


def test_head_label_with_missing_privacy_column_is_not_ready(auth_store, pg_engine):
    from services.api.app.auth.config import AuthFlowError
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE privacy_notice_versions DROP COLUMN controller_reference CASCADE"))
    with pytest.raises(AuthFlowError) as caught:
        auth_store.assert_schema_ready()
    assert caught.value.status_code == 503
    assert "controller_reference" not in {column["name"] for column in inspect(pg_engine).get_columns("privacy_notice_versions")}


@pytest.mark.parametrize("field,value", [("age_band", "14_17"), ("age_band", "under_14"),
    ("age_assurance", "verified"), ("declaration_expires_at", None), ("age_band", None),
    ("revision", 0), ("event_type", "guardian_verified"), ("consent_status", "marketing")])
def test_database_rejects_false_age_and_consent_states(privacy_service, principal_factory, pg_engine, field, value):
    from tests.security.privacy.test_service import declare
    principal = principal_factory()
    declare(privacy_service, principal)
    with Session(pg_engine) as session:
        original = session.scalar(select(PrivacyAdmissionRecord))
        values = {column.name: getattr(original, column.name) for column in PrivacyAdmissionRecord.__table__.columns}
    values.update(id=uuid4(), revision=2)
    values[field] = value
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as session, session.begin():
            session.add(PrivacyAdmissionRecord(**values))


def test_consent_composite_fk_rejects_other_user_reference(privacy_service, principal_factory, pg_engine):
    from tests.security.privacy.test_service import admit
    alice, bob = principal_factory(), principal_factory()
    consent = admit(privacy_service, alice)
    with Session(pg_engine) as session:
        original = session.get(PrivacyAdmissionRecord, consent.consent_id)
        values = {column.name: getattr(original, column.name) for column in PrivacyAdmissionRecord.__table__.columns}
    values.update(id=uuid4(), user_id=bob.user_id, revision=1)
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as session, session.begin():
            session.add(PrivacyAdmissionRecord(**values))
