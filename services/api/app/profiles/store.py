"""Caller-transaction PostgreSQL storage; ownership remains in the auth registry."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..api.v2.idempotency_canonical import canonical_request_hash
from ..audit.retention import expires_after_months
from ..auth.models import AuthOwnedResource
from .models import ProfileRoot, ProfileVersion, ProfilesBase
from .schemas import (MAX_PROFILE_BYTES, PROFILES_HEAD, ProfileError, ProfileSnapshot,
                      ProfileVersionData, adaptation, server_time)


def database_time(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    raise ProfileError()


def migration_config():
    directory = Path(__file__).resolve().parents[2]
    config = Config(str(directory / "profiles_alembic.ini"))
    config.set_main_option("script_location", str(directory / "profiles_migrations"))
    return config


def migrate_profiles(engine):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
        raise ProfileError()
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    except Exception:
        raise ProfileError() from None


class ProfilesStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise ProfileError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            if not {"student_profiles", "student_profile_versions", "profiles_alembic_version"}.issubset(inspector.get_table_names()):
                raise ProfileError()
            for table in ProfilesBase.metadata.tables.values():
                if {c["name"] for c in inspector.get_columns(table.name)} != set(table.columns.keys()):
                    raise ProfileError()
            with self.engine.connect() as connection:
                for table, expected in (("auth_alembic_version", "0006_audit_t10"),
                    ("idempotency_alembic_version", "0001_idempotency_t49"), ("profiles_alembic_version", PROFILES_HEAD)):
                    if connection.execute(text("SELECT version_num FROM " + table)).scalars().all() != [expected]:
                        raise ProfileError()
                trigger = connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid = 'student_profile_versions'::regclass AND tgname = 'student_profile_versions_no_update' AND NOT tgisinternal")).scalar_one_or_none()
                if trigger not in {"O", "A"}:
                    raise ProfileError()
        except SQLAlchemyError:
            raise ProfileError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise ProfileError()
        try:
            for mapper in (None, AuthOwnedResource, ProfileRoot, ProfileVersion):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise ProfileError()
            yield
        except IntegrityError as error:
            if getattr(getattr(error, "orig", None), "sqlstate", None) == "23505":
                raise ProfileError(409) from None
            raise ProfileError() from None
        except SQLAlchemyError:
            raise ProfileError() from None

    def get_root(self, session, profile_id, owner_user_id):
        with self._work(session):
            if not isinstance(profile_id, UUID) or not isinstance(owner_user_id, UUID):
                raise ProfileError(404)
            row = session.scalar(select(ProfileRoot).where(ProfileRoot.id == profile_id,
                ProfileRoot.owner_user_id == owner_user_id).with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise ProfileError(404)
            return row

    def get_version(self, session, root, *, version_id=None, number=None):
        with self._work(session):
            statement = select(ProfileVersion).where(ProfileVersion.profile_id == root.id,
                ProfileVersion.owner_user_id == root.owner_user_id, ProfileVersion.is_synthetic == root.is_synthetic)
            if version_id is not None:
                statement = statement.where(ProfileVersion.id == version_id)
            elif number is not None:
                statement = statement.where(ProfileVersion.version == number)
            else:
                statement = statement.where(ProfileVersion.id == root.current_version_id)
            row = session.scalar(statement.with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise ProfileError(404)
            return row

    def create_version(self, session, current, profile, proof, *, now, root=None, expected_version=None):
        with self._work(session):
            try:
                profile = ProfileSnapshot.model_validate(profile)
                now = server_time(now)
            except (ValueError, ValidationError, TypeError):
                raise ProfileError(422) from None
            payload = profile.model_dump(mode="json")
            if len(profile.model_dump_json().encode("utf-8")) > MAX_PROFILE_BYTES:
                raise ProfileError(422)
            version_id = uuid4()
            if root is None:
                root = ProfileRoot(id=proof.profile_id, owner_user_id=current.user_id, is_synthetic=current.is_synthetic,
                    current_version=1, current_version_id=version_id, created_at=now)
                session.add(root)
                session.flush()
                number = 1
            else:
                if root.current_version != expected_version or root.current_version >= 2147483647:
                    raise ProfileError(409)
                number = root.current_version + 1
            row = ProfileVersion(id=version_id, profile_id=root.id, owner_user_id=current.user_id,
                is_synthetic=current.is_synthetic, version=number, payload=payload,
                payload_sha256=canonical_request_hash(payload), confirmed_at=now, expires_at=expires_after_months(now),
                source="student_declared", admission_id=proof.admission.id, consent_id=proof.admission.consent_id,
                declaration_id=proof.declaration.id, notice_id=proof.notice.id,
                policy_version=proof.notice.policy_version, notice_sha256=proof.notice.text_sha256)
            session.add(row)
            session.flush()
            root.current_version, root.current_version_id = number, version_id
            session.flush()
            return root, row

    @staticmethod
    def version_data(row):
        try:
            profile = ProfileSnapshot.model_validate(row.payload)
            if profile.model_dump(mode="json") != row.payload:
                raise ProfileError()
            return ProfileVersionData(profile_id=row.profile_id, version_id=row.id, version=row.version,
                profile=profile, profile_sha256=row.payload_sha256, confirmed_at=database_time(row.confirmed_at),
                source=row.source, expires_at=database_time(row.expires_at), is_synthetic=row.is_synthetic,
                adaptation=adaptation(profile))
        except (ValidationError, ValueError, TypeError):
            raise ProfileError() from None

    def list_window(self, session, current, proof, *, now, limit, after_id=None):
        with self._work(session):
            conditions = [ProfileRoot.owner_user_id == current.user_id,
                ProfileRoot.is_synthetic == current.is_synthetic, AuthOwnedResource.resource_type == "profile",
                AuthOwnedResource.status == "active", AuthOwnedResource.parent_id.is_(None),
                AuthOwnedResource.owner_user_id == current.user_id, AuthOwnedResource.is_synthetic == current.is_synthetic,
                AuthOwnedResource.version == ProfileRoot.current_version,
                ProfileVersion.admission_id == proof.admission.id, ProfileVersion.consent_id == proof.admission.consent_id,
                ProfileVersion.declaration_id == proof.declaration.id, ProfileVersion.notice_id == proof.notice.id,
                ProfileVersion.policy_version == proof.notice.policy_version, ProfileVersion.notice_sha256 == proof.notice.text_sha256,
                ProfileVersion.confirmed_at <= now, ProfileVersion.expires_at > now, ProfileRoot.created_at <= now]
            if after_id is not None:
                conditions.append(ProfileRoot.id > after_id)
            rows = session.execute(select(ProfileRoot, ProfileVersion).join(AuthOwnedResource,
                AuthOwnedResource.id == ProfileRoot.id).join(ProfileVersion,
                (ProfileVersion.id == ProfileRoot.current_version_id) & (ProfileVersion.profile_id == ProfileRoot.id)
                & (ProfileVersion.version == ProfileRoot.current_version)).where(*conditions)
                .order_by(ProfileRoot.id).limit(limit + 1).with_for_update(of=(AuthOwnedResource, ProfileRoot, ProfileVersion))
                .execution_options(populate_existing=True)).all()
            return rows
