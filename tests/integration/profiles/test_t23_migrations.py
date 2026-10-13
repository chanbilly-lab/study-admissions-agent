"""Real PostgreSQL history constraints and isolated migration preservation."""

from copy import deepcopy
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import delete, inspect, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.auth.models import AuthOwnedResource, AuthUser
from services.api.app.auth.store import migrate_auth
from services.api.app.idempotency.store import migrate_idempotency
from services.api.app.models import Base as M0Base
from services.api.app.privacy.models import PrivacyAdmissionRecord
from services.api.app.profiles.models import ProfilesBase, ProfileRoot, ProfileVersion
from services.api.app.profiles.store import ProfilesStore, migrate_profiles, migration_config

from .test_t23_service import KEY, append_input, denied, rows


pytestmark = pytest.mark.postgres


def rejects(engine, statement, sqlstate):
    with pytest.raises(IntegrityError) as failed:
        with engine.begin() as connection:
            connection.execute(statement)
    assert failed.value.orig.sqlstate == sqlstate


def test_profile_foreign_keys_cannot_cross_roots_owners_or_modes(created, profile_service, principal,
        create_input, admitted_actor_factory, auth_service, pg_engine):
    bob = auth_service.get_principal(admitted_actor_factory().cookie)
    other = profile_service.create_profile(bob, create_input, KEY).version
    original = next(r for r in rows(pg_engine, ProfileVersion) if r["id"] == created.version.version_id)
    rejects(pg_engine, update(ProfileRoot).where(ProfileRoot.id == created.version.profile_id).values(
        current_version_id=other.version_id), "23503")
    rejects(pg_engine, update(ProfileRoot).where(ProfileRoot.id == created.version.profile_id).values(
        owner_user_id=bob.user_id), "23503")
    rejects(pg_engine, update(ProfileRoot).where(ProfileRoot.id == created.version.profile_id).values(
        is_synthetic=False), "23503")
    other_consent = next(r for r in rows(pg_engine, PrivacyAdmissionRecord)
                         if r["user_id"] == bob.user_id and r["event_type"] == "consent_confirmed")
    for values in ({"owner_user_id": bob.user_id}, {"is_synthetic": False}, {"consent_id": other_consent["id"]}):
        forged = deepcopy(dict(original))
        forged.update(id=uuid4(), version=2, **values)
        rejects(pg_engine, insert(ProfileVersion).values(**forged), "23503")
    assert profile_service.get_profile(principal, created.version.profile_id) == created.version


def test_version_update_is_database_rejected_but_future_trusted_history_delete_is_not_prohibited(created,
        profile_service, principal, create_input, pg_engine):
    old = created.version
    appended = profile_service.append_version(principal, old.profile_id, append_input())
    before = rows(pg_engine, ProfileVersion)
    for values in ({"payload_sha256": "0" * 64}, {"expires_at": old.expires_at}, {"version": 100}):
        rejects(pg_engine, update(ProfileVersion).where(ProfileVersion.id == old.version_id).values(**values), "23514")
    assert rows(pg_engine, ProfileVersion) == before
    with pg_engine.begin() as connection:
        trigger = connection.execute(text("SELECT tgtype FROM pg_trigger WHERE tgrelid='student_profile_versions'::regclass "
            "AND tgname='student_profile_versions_no_update' AND NOT tgisinternal")).scalar_one()
        assert trigger & 16 and not trigger & 8  # UPDATE, not DELETE: no permanent retention promise.
        connection.execute(delete(ProfileVersion).where(ProfileVersion.id == old.version_id))
    assert profile_service.get_profile(principal, old.profile_id) == appended.version
    denied(lambda: profile_service.get_version(principal, old.profile_id, old.version_id), 404)
    denied(lambda: profile_service.create_profile(principal, create_input, KEY), (403, 404, 503))
    assert len(rows(pg_engine, ProfileVersion)) == 1


def test_registry_shape_change_and_disabled_history_trigger_fail_closed(created, profile_service,
        principal, profiles_store, pg_engine):
    with pg_engine.begin() as connection:
        connection.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == created.version.profile_id)
                           .values(resource_type="plan"))
    denied(lambda: profile_service.get_profile(principal, created.version.profile_id), 404)
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE student_profile_versions DISABLE TRIGGER student_profile_versions_no_update"))
    denied(profiles_store.assert_schema_ready, 503)


def test_migration_without_required_parent_heads_does_not_create_tables(pg_engine):
    denied(lambda: migrate_profiles(pg_engine), 503)
    assert inspect(pg_engine).get_table_names() == []
    migrate_auth(pg_engine)
    before = set(inspect(pg_engine).get_table_names())
    denied(lambda: migrate_profiles(pg_engine), 503)
    assert set(inspect(pg_engine).get_table_names()) == before


def test_upgrade_repeat_and_profile_only_downgrade_preserve_m0_auth_and_receipts(created,
        profiles_store, profile_service, principal, pg_engine, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.seed import seed
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    old_tables = list(M0Base.metadata.sorted_tables)
    from services.api.app.auth.models import AuthBase
    from services.api.app.idempotency.models import IdempotencyRecord
    old_tables.extend(AuthBase.metadata.sorted_tables)
    old_tables.append(IdempotencyRecord.__table__)
    def snapshot():
        with pg_engine.connect() as connection:
            return {t.name: connection.execute(select(t).order_by(*t.primary_key.columns)).mappings().all() for t in old_tables}
    before = snapshot()
    assert len(ProfilesBase.metadata.tables) == 2 and len(M0Base.metadata.tables) == 7
    migrate_profiles(pg_engine)
    migrate_profiles(pg_engine)
    assert profile_service.get_profile(principal, created.version.profile_id) == created.version
    # Read adds its minimal audit; snapshot the parents after that intentional operation.
    before = snapshot()
    with pg_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert snapshot() == before
    assert not {"student_profiles", "student_profile_versions"} & set(inspect(pg_engine).get_table_names())
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM pg_trigger WHERE tgname='student_profile_versions_no_update'")) == 0
        assert connection.scalar(text("SELECT count(*) FROM pg_proc WHERE proname='profiles_reject_update' AND pronamespace=current_schema()::regnamespace")) == 0
    migrate_profiles(pg_engine)
    profiles_store.assert_schema_ready()
    assert snapshot() == before
    assert rows(pg_engine, ProfileRoot) == rows(pg_engine, ProfileVersion) == []
