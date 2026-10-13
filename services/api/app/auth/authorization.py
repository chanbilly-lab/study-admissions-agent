"""Fixed server authorization over ownership metadata, without domain business APIs."""

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, ValidationError, field_validator
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from .assurance import check_admin_assurance
from .config import AuthFlowError
from .models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from .schemas import AuthModel
from .store import utc_time
from ..audit.context import audited


POLICY_VERSION = "T14_owner_v3"


class Role(StrEnum):
    student = "student"
    data_admin = "data_admin"
    operations = "operations"


class ResourceType(StrEnum):
    profile = "profile"
    plan = "plan"
    attachment = "attachment"
    export = "export"
    job = "job"


class PrivateAction(StrEnum):
    read = "read"
    list = "list"
    write = "write"
    download = "download"
    export = "export"
    execute = "execute"


class AuthorizationError(AuthFlowError):
    """Safe fixed errors; no identifiers, query contents or database diagnostics."""

    def __init__(self, status_code: int = 403, code: str | None = None):
        codes = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
                 409: "CONFLICT", 503: "SERVICE_UNAVAILABLE"}
        if status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        # AuthFlowError deliberately only supports the T05/T06 errors. This fixed
        # subclass adds object errors while retaining the HTTP safe-error boundary.
        ValueError.__init__(self, {401: "Authentication is required or invalid",
            403: "Access is not permitted", 404: "Resource was not found",
            409: "Resource version conflicts", 503: "Authorization service is unavailable"}[status_code])


class Principal(AuthModel):
    """Server-internal reference, never an HTTP credential or client input model."""

    user_id: UUID
    session_id: UUID
    roles: tuple[Role, ...]
    is_synthetic: bool = Field(strict=True)
    expires_at: datetime
    authorization_context: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value):
        return utc_time(value)

    @field_validator("roles")
    @classmethod
    def unique_roles(cls, value):
        if len(value) > 3 or len(set(value)) != len(value):
            raise ValueError("roles must be a unique fixed set")
        return value


class OwnedResource(AuthModel):
    id: UUID
    resource_type: ResourceType
    owner_user_id: UUID
    status: Literal["active", "deleted"]
    version: int = Field(ge=1, strict=True)
    is_synthetic: bool = Field(strict=True)
    parent_id: UUID | None


class OwnedPage(AuthModel):
    items: tuple[OwnedResource, ...]
    total: int = Field(ge=0, strict=True)
    next_cursor: UUID | None


_ROOTS = (ResourceType.profile, ResourceType.plan)
_ACTIONS = {
    PrivateAction.read: tuple(ResourceType), PrivateAction.list: tuple(ResourceType),
    PrivateAction.write: _ROOTS, PrivateAction.download: (ResourceType.attachment, ResourceType.export),
    PrivateAction.export: _ROOTS, PrivateAction.execute: (ResourceType.job,),
}
_CATALOG_CAPABILITIES = frozenset({"catalog.import", "catalog.review", "catalog.publish", "catalog.withdraw",
                                   "catalog.source.register", "catalog.source.read", "catalog.storage.write", "catalog.storage.read"})


class Authorizer:
    def __init__(self, auth_service):
        self.auth_service = auth_service
        self._validate()

    def _validate(self):
        from .service import AuthService

        if not isinstance(self.auth_service, AuthService):
            raise AuthorizationError(503)
        self.auth_service._validate()
        return self.auth_service

    @property
    def _production(self):
        return self.auth_service.runtime_settings.app_environment == "production"

    @contextmanager
    def _transaction(self, supplied: Session | None = None):
        try:
            service = self._validate()
            if supplied is None:
                with Session(service.store.engine) as session, session.begin():
                    yield session
            else:
                if not isinstance(supplied, Session) or not supplied.in_transaction():
                    raise AuthorizationError(503)
                bind = supplied.get_bind()
                if getattr(bind, "engine", bind) is not service.store.engine:
                    raise AuthorizationError(503)
                yield supplied
        except AuthFlowError as error:
            if isinstance(error, AuthorizationError):
                raise
            raise AuthorizationError(error.status_code, error.code) from None
        except Exception:
            # Callbacks are trusted local application operations, but their errors
            # must neither disclose SQL nor commit partial work in our transaction.
            raise AuthorizationError(503) from None

    def _refresh(self, principal: Principal, session: Session):
        self._validate()
        try:
            reference = Principal.model_validate(principal)
        except (ValidationError, ValueError, TypeError):
            raise AuthorizationError(401) from None
        return self.auth_service.store.locked_principal(session, reference,
            clock=self.auth_service._now, production=self._production)

    @staticmethod
    def _pair(kind, action):
        try:
            kind, action = ResourceType(kind), PrivateAction(action)
            if kind not in _ACTIONS[action]:
                raise ValueError
            return kind, action
        except (ValueError, TypeError):
            raise AuthorizationError(403) from None

    @staticmethod
    def _id(value):
        if not isinstance(value, UUID):
            raise AuthorizationError(404)
        return value

    @staticmethod
    def _student(principal):
        if Role.student not in principal.roles:
            raise AuthorizationError(403)

    @staticmethod
    def _value(row):
        return OwnedResource(id=row.id, resource_type=row.resource_type, owner_user_id=row.owner_user_id,
            status=row.status, version=row.version, is_synthetic=row.is_synthetic, parent_id=row.parent_id)

    def _scope(self, current, kind, now):
        parent = aliased(AuthOwnedResource)
        role = exists(select(AuthUserRole.user_id).where(AuthUserRole.user_id == current.user_id,
            AuthUserRole.role == Role.student.value, AuthUserRole.revoked_at.is_(None),
            AuthUserRole.granted_at <= now,
            (AuthUserRole.expires_at.is_(None) | (AuthUserRole.expires_at > now))))
        conditions = [AuthOwnedResource.owner_user_id == current.user_id,
            AuthOwnedResource.resource_type == kind.value, AuthOwnedResource.status == "active", role]
        if self._production:
            conditions.append(AuthOwnedResource.is_synthetic.is_(False))
        if kind in _ROOTS:
            conditions.append(AuthOwnedResource.parent_id.is_(None))
        else:
            valid_parent = [parent.id == AuthOwnedResource.parent_id,
                parent.owner_user_id == current.user_id, parent.status == "active",
                parent.resource_type.in_([item.value for item in _ROOTS]), parent.parent_id.is_(None)]
            if self._production:
                valid_parent.append(parent.is_synthetic.is_(False))
            conditions.append(exists(select(parent.id).where(*valid_parent)))
        return conditions

    def _resource(self, session, principal, kind, resource_id, action):
        kind, action = self._pair(kind, action)
        resource_id = self._id(resource_id)
        current, _ = self._refresh(principal, session)
        self._student(current)
        row = session.scalar(select(AuthOwnedResource).where(*self._scope(current, kind, self.auth_service._now()),
            AuthOwnedResource.id == resource_id).with_for_update().execution_options(populate_existing=True))
        if row is None:
            raise AuthorizationError(404)
        parent = None
        if row.parent_id is not None:
            parent = session.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == row.parent_id,
                AuthOwnedResource.owner_user_id == current.user_id).with_for_update()
                .execution_options(populate_existing=True))
        # Resource/parent locks can wait. Re-read clock, roles and session validity
        # after those waits rather than authorizing at an earlier snapshot time.
        current, _ = self._refresh(current, session)
        self._student(current)
        if (row.owner_user_id != current.user_id or row.resource_type != kind.value or row.status != "active"
            or (self._production and row.is_synthetic)):
            raise AuthorizationError(404)
        if kind in _ROOTS:
            if row.parent_id is not None:
                raise AuthorizationError(404)
        elif (parent is None or parent.owner_user_id != current.user_id or parent.status != "active"
              or parent.resource_type not in _ROOTS or parent.parent_id is not None
              or (self._production and parent.is_synthetic)):
            raise AuthorizationError(404)
        return current, row

    def refresh(self, principal: Principal) -> Principal:
        with self._transaction() as session:
            return self._refresh(principal, session)[0]

    def _audit(self, session, current, action, row=None, kind=None):
        self.auth_service.store.audit.success(session, action, actor=current,
            object_type=row.resource_type if row is not None else kind,
            object_id=row.id if row is not None else None,
            object_version=row.version if row is not None else None, now=self.auth_service._now())
        # Required audit flush is additional I/O; absolute expiry and current
        # roles must be checked after it, with existing locks still held.
        fresh, _ = self._refresh(current, session)
        self._student(fresh)
        return fresh

    @audited("authorization.owned.check")
    def require_owned(self, principal: Principal, kind, resource_id: UUID, action="read") -> OwnedResource:
        with self._transaction() as session:
            current, row = self._resource(session, principal, kind, resource_id, action)
            self._audit(session, current, "authorization.owned.check", row)
            return self._value(row)

    @audited("authorization.owned.list")
    def list_owned(self, principal: Principal, kind, *, limit: int = 50,
                   after_id: UUID | None = None) -> OwnedPage:
        kind, _ = self._pair(kind, PrivateAction.list)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise AuthorizationError(403)
        if after_id is not None:
            self._id(after_id)
        with self._transaction() as session:
            current, _ = self._refresh(principal, session)
            self._student(current)
            # Trusted maintenance is serialized by the account lock. A privileged
            # SQL edit can still invalidate a page while its parent locks wait.
            # Only return a stable, fully locked window, with bounded retries.
            for _ in range(3):
                scope = self._scope(current, kind, self.auth_service._now())
                query = select(AuthOwnedResource).where(*scope)
                if after_id is not None:
                    query = query.where(AuthOwnedResource.id > after_id)
                rows = session.scalars(query.order_by(AuthOwnedResource.id).limit(limit + 1)
                    .with_for_update().execution_options(populate_existing=True)).all()
                locked_ids = tuple(row.id for row in rows)
                for parent_id in sorted({row.parent_id for row in rows if row.parent_id is not None}):
                    session.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == parent_id,
                        AuthOwnedResource.owner_user_id == current.user_id).with_for_update()
                        .execution_options(populate_existing=True))
                current, _ = self._refresh(current, session)
                self._student(current)
                scope = self._scope(current, kind, self.auth_service._now())
                query = select(AuthOwnedResource).where(*scope)
                if after_id is not None:
                    query = query.where(AuthOwnedResource.id > after_id)
                rows = session.scalars(query.order_by(AuthOwnedResource.id).limit(limit + 1)
                    .with_for_update().execution_options(populate_existing=True)).all()
                if tuple(row.id for row in rows) != locked_ids:
                    continue
                total = session.scalar(select(func.count()).select_from(AuthOwnedResource).where(*scope))
                current, _ = self._refresh(current, session)
                self._student(current)
                self._audit(session, current, "authorization.owned.list", kind=kind.value)
                return OwnedPage(items=tuple(self._value(row) for row in rows[:limit]), total=total,
                                 next_cursor=rows[limit - 1].id if len(rows) > limit else None)
            raise AuthorizationError(503)

    @audited("authorization.owned.register")
    def register_owned(self, principal: Principal, kind, *, resource_id: UUID | None = None,
                       parent_id: UUID | None = None, session: Session | None = None) -> OwnedResource:
        kind, _ = self._pair(kind, PrivateAction.read)
        resource_id = uuid4() if resource_id is None else self._id(resource_id)
        if (kind in _ROOTS) != (parent_id is None):
            raise AuthorizationError(403)
        with self._transaction(session) as active_session:
            current, _ = self._refresh(principal, active_session)
            self._student(current)
            if parent_id is not None:
                parent_id = self._id(parent_id)
                parent = active_session.scalar(select(AuthOwnedResource).where(
                    AuthOwnedResource.id == parent_id, AuthOwnedResource.owner_user_id == current.user_id,
                    AuthOwnedResource.status == "active", AuthOwnedResource.parent_id.is_(None),
                    AuthOwnedResource.resource_type.in_([item.value for item in _ROOTS])).with_for_update()
                    .execution_options(populate_existing=True))
                if parent is None or (self._production and parent.is_synthetic):
                    raise AuthorizationError(404)
            current, _ = self._refresh(current, active_session)
            self._student(current)
            row = AuthOwnedResource(id=resource_id, resource_type=kind.value, owner_user_id=current.user_id,
                                    status="active", version=1, is_synthetic=current.is_synthetic, parent_id=parent_id)
            active_session.add(row)
            try:
                active_session.flush()
            except IntegrityError:
                raise AuthorizationError(409) from None
            self._audit(active_session, current, "authorization.owned.register", row)
            return self._value(row)

    @audited("authorization.owned.execute")
    def execute_owned(self, principal: Principal, kind, resource_id: UUID, action,
                      operation: Callable, *, expected_version: int | None = None):
        if not callable(operation):
            raise AuthorizationError(403)
        if expected_version is not None and (isinstance(expected_version, bool)
            or not isinstance(expected_version, int) or expected_version < 1):
            raise AuthorizationError(409)
        with self._transaction() as session:
            current, row = self._resource(session, principal, kind, resource_id, action)
            if expected_version is not None and row.version != expected_version:
                raise AuthorizationError(409)
            immutable = (row.id, row.resource_type, row.owner_user_id, row.parent_id, row.is_synthetic)
            result = operation(session, current, self._value(row))
            session.flush()
            session.refresh(row)
            if immutable != (row.id, row.resource_type, row.owner_user_id, row.parent_id, row.is_synthetic):
                raise AuthorizationError(403)
            fresh, _ = self._refresh(current, session)
            self._student(fresh)
            self._audit(session, fresh, "authorization.owned.execute", row)
            return result

    def touch_owned(self, principal: Principal, kind, resource_id: UUID, expected_version: int) -> OwnedResource:
        def touch(session, current, resource):
            row = session.get(AuthOwnedResource, resource.id)
            row.version += 1
            session.flush()
            return self._value(row)
        return self.execute_owned(principal, kind, resource_id, PrivateAction.write, touch,
                                  expected_version=expected_version)

    def check_capability_in_transaction(self, session: Session, principal: Principal,
                                        capability: str) -> Principal:
        """Fresh strong administrator check without opening a second transaction.

        The caller owns business locks, mandatory audit, final revalidation and
        commit/rollback. This method grants no private student object access.
        """
        service = self._validate()
        if (not isinstance(session, Session) or not session.in_transaction()
            or not session.is_active or not session.get_transaction().is_active):
            raise AuthorizationError(503)
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not service.store.engine:
                    raise AuthorizationError(503)
        except AuthorizationError:
            raise
        except Exception:
            raise AuthorizationError(503) from None
        if not isinstance(capability, str) or capability not in _CATALOG_CAPABILITIES:
            raise AuthorizationError(403)
        current, stored = self._refresh(principal, session)
        settings = service._validate()
        if (Role.data_admin not in current.roles or stored.verified_issuer != settings.provider.issuer
            or stored.verified_client_id != settings.provider.client_id):
            raise AuthorizationError(403)
        check_admin_assurance(stored.assurance, issuer=stored.verified_issuer,
            client_id=stored.verified_client_id, policy=settings.admin_assurance_policy, now=service._now())
        return current

    def check_owned_in_transaction(self, session: Session, principal: Principal,
                                   kind, resource_id: UUID, action="read") -> tuple[Principal, OwnedResource]:
        """Fresh owner check in the caller's transaction, without another connection.

        Callers additionally enforce the purpose and mandatory audit, then repeat
        these checks after their I/O before committing or releasing any content.
        """
        service = self._validate()
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise AuthorizationError(503)
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not service.store.engine:
                    raise AuthorizationError(503)
        except AuthorizationError:
            raise
        except Exception:
            raise AuthorizationError(503) from None
        current, row = self._resource(session, principal, kind, resource_id, action)
        return current, self._value(row)

    @audited("authorization.capability.check")
    def require_capability(self, principal: Principal, capability: str) -> None:
        if not isinstance(capability, str):
            raise AuthorizationError(403)
        with self._transaction() as session:
            current, stored = self._refresh(principal, session)
            if capability == "operations.status":
                if Role.operations not in current.roles:
                    raise AuthorizationError(403)
                self.auth_service.store.audit.success(session, "authorization.capability.check", actor=current, now=self.auth_service._now())
                current, _ = self._refresh(current, session)
                if Role.operations not in current.roles:
                    raise AuthorizationError(403)
                return
            if capability not in _CATALOG_CAPABILITIES or Role.data_admin not in current.roles:
                raise AuthorizationError(403)
            settings = self.auth_service._validate()
            if (stored.verified_issuer != settings.provider.issuer
                or stored.verified_client_id != settings.provider.client_id):
                raise AuthorizationError(403)
            check_admin_assurance(stored.assurance, issuer=stored.verified_issuer,
                client_id=stored.verified_client_id, policy=settings.admin_assurance_policy,
                now=self.auth_service._now())
            self.auth_service.store.audit.success(session, "authorization.capability.check", actor=current, now=self.auth_service._now())
            current, stored = self._refresh(current, session)
            latest = self.auth_service._validate()
            if (Role.data_admin not in current.roles or latest.admin_assurance_policy != settings.admin_assurance_policy
                or stored.verified_issuer != latest.provider.issuer or stored.verified_client_id != latest.provider.client_id):
                raise AuthorizationError(403)
            check_admin_assurance(stored.assurance, issuer=stored.verified_issuer,
                client_id=stored.verified_client_id, policy=latest.admin_assurance_policy, now=self.auth_service._now())

    @staticmethod
    def _filters(filters):
        if not isinstance(filters, tuple) or len(filters) > 32 or any(not isinstance(item, str)
            or not 1 <= len(item) <= 255 or not item.isascii() or any(ord(c) < 32 for c in item) for item in filters):
            raise AuthorizationError(403)
        return filters

    def _cache_key(self, current, resource, action, filters):
        key = [POLICY_VERSION, str(current.user_id), str(current.session_id), current.authorization_context,
               resource.resource_type.value, action.value, str(resource.id), resource.version, filters]
        return "authz:" + sha256(json.dumps(key, separators=(",", ":")).encode("ascii")).hexdigest()

    @audited("authorization.owned.check")
    def cache_key(self, principal: Principal, kind, resource_id: UUID, action="read", *, filters=()) -> str:
        kind, action = self._pair(kind, action)
        filters = self._filters(filters)
        with self._transaction() as session:
            current, row = self._resource(session, principal, kind, resource_id, action)
            current = self._audit(session, current, "authorization.owned.check", row)
            return self._cache_key(current, self._value(row), action, filters)

    @audited("authorization.owned.check")
    def cached_value(self, principal: Principal, kind, resource_id: UUID, cache: Mapping,
                     action="read", *, filters=()):
        if not isinstance(cache, Mapping):
            raise AuthorizationError(403)
        kind, action = self._pair(kind, action)
        filters = self._filters(filters)
        with self._transaction() as session:
            current, row = self._resource(session, principal, kind, resource_id, action)
            key = self._cache_key(current, self._value(row), action, filters)
            result = cache.get(key)
            # A supplied server cache implementation can take time; its result is
            # only returned after one final current identity/role check.
            current = self._audit(session, current, "authorization.owned.check", row)
            if self._cache_key(current, self._value(row), action, filters) != key:
                return None
            return result


__all__ = ["Authorizer", "AuthorizationError", "Principal", "OwnedResource", "OwnedPage",
           "Role", "ResourceType", "PrivateAction", "POLICY_VERSION"]
