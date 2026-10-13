"""Explicit database operations; never create schema or provision accounts on login."""

from dataclasses import dataclass, field
from collections.abc import Callable
from datetime import datetime, timezone
import hmac
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from .assurance import SessionAssurance
from .config import AuthFlowError
from .models import AuthIdentity, AuthSession, AuthUser, AuthUserRole, LoginTransaction
from .schemas import IdentityKey
from ..audit.context import audited, observe_actor


AUTH_REVISION = "0006_audit_t10"


def utc_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AuthFlowError()
    return value.astimezone(timezone.utc)


def database_time(value: datetime) -> datetime:
    # SQLite is an explicit offline stand-in and drops timezone information.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ClaimedLogin:
    provider_id: str
    issuer: str
    client_id: str
    redirect_uri: str
    encrypted_context: str = field(repr=False)


@dataclass(frozen=True)
class StoredSession:
    user_id: UUID
    expires_at: datetime
    is_synthetic: bool
    session_id: UUID
    verified_issuer: str | None = None
    verified_client_id: str | None = None
    assurance: SessionAssurance | None = None


@dataclass(frozen=True)
class StoredCsrf:
    encrypted_token: str = field(repr=False)
    digest: str = field(repr=False)
    expires_at: datetime


def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[2] / "auth_alembic.ini"))


def migrate_auth(engine) -> None:
    """Explicit independent migration entry point, never invoked by application startup."""
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


class AuthStore:
    def __init__(self, engine):
        self.engine = engine
        from ..audit.service import AuditWriter
        self.audit = AuditWriter(engine)
        self.rights_guard = None
        self._rights_guard_binding = None

    def install_rights_guard(self, guard):
        """Explicit one-time composition; a restored DB cannot supply the guard."""
        from ..privacy.rights.guard import RightsGuard
        if type(guard) is not RightsGuard or guard.engine is not self.engine or self._rights_guard_binding is not None:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        guard.validate_configuration()
        self.rights_guard = guard
        self._rights_guard_binding = guard

    def validate_rights_configuration(self, *, production=False):
        if self.rights_guard is not self._rights_guard_binding or (production and self.rights_guard is None):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        if self.rights_guard is not None:
            try:
                self.rights_guard.validate_configuration()
                if self.rights_guard.engine is not self.engine:
                    raise ValueError()
            except Exception:
                raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def _rights_check(self, session):
        self.validate_rights_configuration()
        if self.rights_guard is not None:
            if not session.in_transaction():
                session.begin()  # Read paths normally use SQLAlchemy autobegin.
            self.rights_guard.auth_check(session)

    def assert_schema_ready(self) -> None:
        try:
            required = {"auth_alembic_version", "auth_users", "auth_identities",
                        "auth_login_transactions", "auth_sessions", "auth_user_roles", "auth_owned_resources",
                        "privacy_notice_versions", "privacy_admission_records", "auth_sharing_states", "auth_access_grants",
                        "grant_fields", "grant_actions", "auth_audit_events"}
            if not required.issubset(inspect(self.engine).get_table_names()):
                raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
            columns = {column["name"] for column in inspect(self.engine).get_columns("auth_sessions")}
            if not {"csrf_digest", "csrf_encrypted_token", "verified_issuer", "verified_client_id",
                    "assurance_acr", "assurance_amr", "assurance_auth_time"}.issubset(columns):
                raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
            # A revision label alone must not make a partially damaged privacy
            # schema look ready. This remains inspection only, with no DDL.
            from ..privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
            from .grants.models import SharingState, AccessGrant, GrantField, GrantAction
            from ..audit.models import AuditEvent
            for model in (PrivacyAdmissionRecord, PrivacyNoticeVersion, SharingState, AccessGrant, GrantField, GrantAction, AuditEvent):
                actual = {column["name"] for column in inspect(self.engine).get_columns(model.__tablename__)}
                if not set(model.__table__.columns.keys()).issubset(actual):
                    raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
            with self.engine.connect() as connection:
                revisions = connection.execute(text("SELECT version_num FROM auth_alembic_version")).scalars().all()
            if revisions != [AUTH_REVISION]:
                raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
            self.validate_rights_configuration()
            if self.rights_guard is not None:
                self.rights_guard.ensure_ready()
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    @audited("auth.login.start")
    def save_login(self, *, state_digest: str, browser_digest: str, provider_id: str,
                   issuer: str, client_id: str, redirect_uri: str, encrypted_context: str,
                   issued_at: datetime, expires_at: datetime) -> None:
        try:
            with Session(self.engine) as session, session.begin():
                self._rights_check(session)
                identifier = uuid4()
                session.add(LoginTransaction(id=identifier, state_digest=state_digest,
                    browser_digest=browser_digest, provider_id=provider_id, issuer=issuer,
                    client_id=client_id, redirect_uri=redirect_uri, encrypted_context=encrypted_context,
                    issued_at=utc_time(issued_at), expires_at=utc_time(expires_at), consumed_at=None))
                self.audit.success(session, "auth.login.start", object_type="login_transaction", object_id=identifier, now=issued_at)
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def claim_login(self, state_digest: str, browser_digest: str, *, now: datetime,
                    audit_action: str = "auth.login.consume") -> ClaimedLogin:
        now = utc_time(now)
        conditions = (LoginTransaction.state_digest == state_digest,
                      LoginTransaction.browser_digest == browser_digest,
                      LoginTransaction.consumed_at.is_(None), LoginTransaction.encrypted_context.is_not(None),
                      LoginTransaction.issued_at <= now, LoginTransaction.expires_at > now)
        try:
            with Session(self.engine) as session, session.begin():
                self._rights_check(session)
                row = session.execute(select(LoginTransaction.id, LoginTransaction.provider_id,
                    LoginTransaction.issuer, LoginTransaction.client_id, LoginTransaction.redirect_uri,
                    LoginTransaction.encrypted_context).where(*conditions).with_for_update()).first()
                if row is None:
                    raise AuthFlowError()
                claimed = ClaimedLogin(row.provider_id, row.issuer, row.client_id, row.redirect_uri,
                                       row.encrypted_context)
                result = session.execute(update(LoginTransaction).where(LoginTransaction.id == row.id,
                    *conditions).values(consumed_at=now, encrypted_context=None))
                if result.rowcount != 1:
                    raise AuthFlowError()
                self.audit.success(session, audit_action, object_type="login_transaction", object_id=row.id, now=now)
            # The successful claim is committed before the caller performs any external I/O.
            return claimed
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def establish_session(self, identity: IdentityKey, *, session_digest: str,
                          previous_digest: str | None, now: datetime, expires_at: datetime,
                          production: bool, verified_client_id: str | None = None,
                          assurance: SessionAssurance | None = None,
                          clock: Callable[[], datetime] | None = None,
                          login_expires_at: datetime | None = None) -> StoredSession:
        identity = IdentityKey.model_validate(identity)
        now, expires_at = utc_time(now), utc_time(expires_at)
        if verified_client_id is None and assurance is not None:
            raise AuthFlowError()
        if assurance is not None:
            try:
                assurance = SessionAssurance.model_validate(assurance)
                if assurance.auth_time is not None and assurance.auth_time > now:
                    raise ValueError
            except (ValidationError, ValueError, TypeError):
                raise AuthFlowError() from None
        try:
            with Session(self.engine) as session, session.begin():
                self._rights_check(session)
                user = session.scalar(select(AuthUser).join(AuthIdentity, AuthIdentity.user_id == AuthUser.id)
                    .where(AuthIdentity.issuer == identity.issuer, AuthIdentity.subject == identity.subject)
                    .with_for_update(of=AuthUser))
                if user is None or user.status != "active" or (production and user.is_synthetic):
                    raise AuthFlowError(403, "FORBIDDEN")
                if previous_digest is not None:
                    self.validate_rights_configuration()
                    if self.rights_guard is not None:
                        previous = session.scalar(select(AuthSession).where(AuthSession.session_digest == previous_digest,
                            AuthSession.revoked_at.is_(None), AuthSession.created_at <= now).with_for_update())
                        if previous is not None:
                            self.rights_guard.record(session, "session_revoked", previous.user_id, resource_id=previous.id)
                    session.execute(update(AuthSession).where(AuthSession.session_digest == previous_digest,
                        AuthSession.revoked_at.is_(None), AuthSession.created_at <= now)
                        .values(revoked_at=now, csrf_digest=None, csrf_encrypted_token=None))
                row = AuthSession(id=uuid4(), user_id=user.id, session_digest=session_digest,
                    created_at=now, expires_at=expires_at, revoked_at=None,
                    verified_issuer=identity.issuer if verified_client_id is not None else None,
                    verified_client_id=verified_client_id,
                    assurance_acr=assurance.acr if assurance is not None else None,
                    assurance_amr=list(assurance.amr) if assurance is not None else None,
                    assurance_auth_time=assurance.auth_time if assurance is not None else None)
                session.add(row)
                result = self._stored(row, user)
                observe_actor(result)
                self.audit.success(session, "auth.login.complete", actor=result, object_type="session", object_id=row.id, now=now)
                final_at = utc_time(clock()) if clock is not None else now
                if not now <= final_at < expires_at or (login_expires_at is not None and final_at >= utc_time(login_expires_at)):
                    raise AuthFlowError()
            return result
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def read_session(self, session_digest: str, *, now: datetime, production: bool) -> StoredSession:
        now = utc_time(now)
        try:
            with Session(self.engine) as session:
                row, user = self._current(session, now, production, session_digest=session_digest)
                result = self._stored(row, user)
                observe_actor(result)
                return result
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    @staticmethod
    def _stored(row: AuthSession, user: AuthUser) -> StoredSession:
        assurance = None
        if row.verified_issuer is not None and row.verified_client_id is not None:
            try:
                # Do not coerce a corrupted JSON string/object into method labels.
                if row.assurance_amr is not None and not isinstance(row.assurance_amr, list):
                    raise ValueError
                assurance = SessionAssurance(acr=row.assurance_acr, amr=row.assurance_amr or (),
                    auth_time=database_time(row.assurance_auth_time) if row.assurance_auth_time is not None else None)
            except (ValidationError, ValueError, TypeError):
                assurance = None  # Ordinary login remains valid; strength checks deny malformed proof.
        return StoredSession(user.id, database_time(row.expires_at), user.is_synthetic, row.id,
                             row.verified_issuer, row.verified_client_id, assurance)

    def _current(self, session: Session, now: datetime, production: bool, *, session_digest=None,
                 session_id=None, user_id=None, lock=False) -> tuple[AuthSession, AuthUser]:
        self._rights_check(session)
        if lock:
            # T07 authorization and role maintenance lock the account before the
            # session. A joined FOR UPDATE can acquire these in planner order and
            # deadlock with that path, so T06 CSRF/logout/execution share this order.
            identity = select(AuthSession.user_id)
            if session_digest is not None:
                identity = identity.where(AuthSession.session_digest == session_digest)
            elif session_id is not None and user_id is not None:
                identity = identity.where(AuthSession.id == session_id, AuthSession.user_id == user_id)
            else:
                raise AuthFlowError()
            account_id = session.scalar(identity)
            if account_id is None:
                raise AuthFlowError()
            user = session.scalar(select(AuthUser).where(AuthUser.id == account_id).with_for_update())
            query = select(AuthSession).where(AuthSession.user_id == account_id)
            query = (query.where(AuthSession.session_digest == session_digest) if session_digest is not None
                     else query.where(AuthSession.id == session_id))
            row = session.scalar(query.with_for_update())
            if (user is None or row is None or user.status != "active" or (production and user.is_synthetic)
                or row.revoked_at is not None
                or not database_time(row.created_at) <= now < database_time(row.expires_at)):
                raise AuthFlowError()
            self._rights_check(session)
            return row, user
        query = select(AuthSession, AuthUser).join(AuthUser, AuthUser.id == AuthSession.user_id).where(
            AuthSession.revoked_at.is_(None), AuthSession.created_at <= now,
            AuthSession.expires_at > now, AuthUser.status == "active")
        if session_digest is not None:
            query = query.where(AuthSession.session_digest == session_digest)
        elif session_id is not None and user_id is not None:
            query = query.where(AuthSession.id == session_id, AuthSession.user_id == user_id)
        else:
            raise AuthFlowError()
        result = session.execute(query).first()
        if result is None or (production and result[1].is_synthetic):
            raise AuthFlowError()
        self._rights_check(session)
        return result[0], result[1]

    def get_or_create_csrf(self, session_digest: str, *, now: datetime, production: bool,
                           mint: Callable[[], tuple[str, str]], clock: Callable[[], datetime] | None = None) -> StoredCsrf:
        now = utc_time(now)
        try:
            with Session(self.engine) as session, session.begin():
                row, _ = self._current(session, now, production, session_digest=session_digest, lock=True)
                checked_at = utc_time(clock()) if clock is not None else now
                if not database_time(row.created_at) <= checked_at < database_time(row.expires_at):
                    raise AuthFlowError()
                if row.csrf_digest is None and row.csrf_encrypted_token is None:
                    digest, encrypted = mint()
                    # The predicate also prevents a lost initialization on an explicit SQLite test substitute.
                    result = session.execute(update(AuthSession).where(AuthSession.id == row.id,
                        AuthSession.csrf_digest.is_(None), AuthSession.csrf_encrypted_token.is_(None))
                        .values(csrf_digest=digest, csrf_encrypted_token=encrypted))
                    if result.rowcount != 1:
                        session.refresh(row)
                    else:
                        row.csrf_digest, row.csrf_encrypted_token = digest, encrypted
                if row.csrf_digest is None or row.csrf_encrypted_token is None:
                    raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
                stored = StoredCsrf(row.csrf_encrypted_token, row.csrf_digest, database_time(row.expires_at))
            return stored
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def verify_csrf(self, session_digest: str, csrf_digest: str, *, now: datetime,
                    production: bool, revoke: bool = False,
                    clock: Callable[[], datetime] | None = None) -> StoredSession:
        now = utc_time(now)
        try:
            with Session(self.engine) as session, session.begin():
                row, user = self._current(session, now, production, session_digest=session_digest, lock=True)
                checked_at = utc_time(clock()) if clock is not None else now
                if not database_time(row.created_at) <= checked_at < database_time(row.expires_at):
                    raise AuthFlowError()
                if (row.csrf_digest is None or row.csrf_encrypted_token is None
                    or not hmac.compare_digest(row.csrf_digest, csrf_digest)):
                    raise AuthFlowError(403, "FORBIDDEN")
                stored = self._stored(row, user)
                observe_actor(stored)
                if revoke:
                    if self.rights_guard is not None:
                        self.rights_guard.record(session, "session_revoked", user.id, resource_id=row.id)
                    row.revoked_at = checked_at
                    row.csrf_digest = row.csrf_encrypted_token = None
                    self.audit.success(session, "auth.logout", actor=stored, object_type="session", object_id=row.id, now=checked_at)
                    final_at = utc_time(clock()) if clock is not None else checked_at
                    if not database_time(row.created_at) <= final_at < database_time(row.expires_at):
                        raise AuthFlowError()
            return stored
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def read_execution(self, session_id: UUID, user_id: UUID, *, now: datetime,
                       production: bool) -> StoredSession:
        try:
            with Session(self.engine) as session:
                row, user = self._current(session, utc_time(now), production, session_id=session_id, user_id=user_id)
                return self._stored(row, user)
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def execute_current(self, session_id: UUID, user_id: UUID, *, now: Callable[[], datetime],
                        production: bool, operation: Callable[[StoredSession], object]):
        try:
            with Session(self.engine) as session, session.begin():
                row, user = self._current(session, utc_time(now()), production,
                                         session_id=session_id, user_id=user_id, lock=True)
                # A lock wait must not turn a stale pre-lock timestamp into valid execution.
                checked_at = utc_time(now())
                if not database_time(row.created_at) <= checked_at < database_time(row.expires_at):
                    raise AuthFlowError()
                return operation(self._stored(row, user))
        except SQLAlchemyError:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    @staticmethod
    def principal_value(row: AuthSession, user: AuthUser, roles, *, now: datetime):
        from hashlib import sha256
        import json
        from .authorization import POLICY_VERSION, Principal, Role

        active = [grant for grant in roles if grant.revoked_at is None
                  and database_time(grant.granted_at) <= now
                  and (grant.expires_at is None or now < database_time(grant.expires_at))]
        active.sort(key=lambda grant: grant.role)
        context = [POLICY_VERSION, [(grant.role, database_time(grant.granted_at).isoformat(),
            database_time(grant.expires_at).isoformat() if grant.expires_at is not None else None) for grant in active]]
        return Principal(user_id=user.id, session_id=row.id, roles=tuple(Role(grant.role) for grant in active),
            is_synthetic=user.is_synthetic, expires_at=database_time(row.expires_at),
            authorization_context=sha256(json.dumps(context, separators=(",", ":")).encode("ascii")).hexdigest())

    def read_principal(self, session_digest: str, *, now: datetime, production: bool):
        now = utc_time(now)
        try:
            with Session(self.engine) as session:
                row, user = self._current(session, now, production, session_digest=session_digest)
                roles = session.scalars(select(AuthUserRole).where(AuthUserRole.user_id == user.id)).all()
                result = self.principal_value(row, user, roles, now=now)
                observe_actor(result)
                return result
        except AuthFlowError:
            raise
        except (SQLAlchemyError, ValidationError, ValueError, TypeError):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def locked_principal(self, session: Session, reference, *, clock: Callable[[], datetime], production: bool):
        """The shared account lock serializes role maintenance and private execution."""
        from .authorization import AuthorizationError
        self._rights_check(session)

        # Composition keeps one authenticated actor per root transaction. This
        # is a consistency guard for trusted local modules, never cached consent
        # or a defense against application code editing Session.info itself.
        transaction = session.get_transaction()
        binding = session.info.get("authenticated_actor_transaction")
        actor = (reference.user_id, reference.session_id)
        if binding is not None and binding[0] is transaction and binding[1] != actor:
            raise AuthorizationError(403)
        session.info["authenticated_actor_transaction"] = (transaction, actor)
        user = session.scalar(select(AuthUser).where(AuthUser.id == reference.user_id).with_for_update()
                              .execution_options(populate_existing=True))
        if user is None:
            raise AuthorizationError(401)
        row = session.scalar(select(AuthSession).where(AuthSession.id == reference.session_id,
            AuthSession.user_id == user.id).with_for_update().execution_options(populate_existing=True))
        if row is None:
            raise AuthorizationError(401)
        roles = session.scalars(select(AuthUserRole).where(AuthUserRole.user_id == user.id)
                                .order_by(AuthUserRole.role).with_for_update()
                                .execution_options(populate_existing=True)).all()
        now = utc_time(clock())
        self._rights_check(session)
        if (user.status != "active" or (production and user.is_synthetic) or row.revoked_at is not None
            or not database_time(row.created_at) <= now < database_time(row.expires_at)):
            raise AuthorizationError(401)
        current, stored = self.principal_value(row, user, roles, now=now), self._stored(row, user)
        observe_actor(current)
        return current, stored

    @audited("auth.role.assign")
    def assign_role(self, user_id: UUID, role: str, *, now: datetime, expires_at: datetime | None = None) -> None:
        """Trusted maintenance only; no role-registration HTTP endpoint exists."""
        from .authorization import AuthorizationError, Role

        try:
            role, now = Role(role), utc_time(now)
            expires_at = utc_time(expires_at) if expires_at is not None else None
            if expires_at is not None and expires_at <= now:
                raise AuthorizationError(403)
            with Session(self.engine) as session, session.begin():
                self._rights_check(session)
                user = session.scalar(select(AuthUser).where(AuthUser.id == user_id).with_for_update())
                if user is None or user.status != "active":
                    raise AuthorizationError(404)
                grant = session.get(AuthUserRole, (user_id, role.value), with_for_update=True)
                if grant is None:
                    session.add(AuthUserRole(user_id=user_id, role=role.value, granted_at=now,
                                              expires_at=expires_at, revoked_at=None))
                else:
                    grant.granted_at, grant.expires_at, grant.revoked_at = now, expires_at, None
                self.audit.success(session, "auth.role.assign", actor_kind="system", object_type="user", object_id=user.id, now=now)
        except AuthFlowError:
            raise
        except (SQLAlchemyError, ValidationError, ValueError, TypeError):
            raise AuthorizationError(503) from None

    @audited("auth.role.revoke")
    def revoke_role(self, user_id: UUID, role: str, *, now: datetime) -> bool:
        """Uses the same account-first lock order as authorized local operations."""
        from .authorization import AuthorizationError, Role

        try:
            role, now = Role(role), utc_time(now)
            with Session(self.engine) as session, session.begin():
                self._rights_check(session)
                user = session.scalar(select(AuthUser).where(AuthUser.id == user_id).with_for_update())
                if user is None:
                    raise AuthorizationError(404)
                grant = session.get(AuthUserRole, (user_id, role.value), with_for_update=True)
                if grant is None or grant.revoked_at is not None:
                    return False
                if now < database_time(grant.granted_at):
                    raise AuthorizationError(403)
                if self.rights_guard is not None:
                    self.rights_guard.record(session, "role_revoked", user_id, role=role.value,
                        role_granted_at=database_time(grant.granted_at))
                grant.revoked_at = now
                self.audit.success(session, "auth.role.revoke", actor_kind="system", object_type="user", object_id=user.id, now=now)
            return True
        except AuthFlowError:
            raise
        except (SQLAlchemyError, ValidationError, ValueError, TypeError):
            raise AuthorizationError(503) from None
