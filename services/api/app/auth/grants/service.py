"""Explicit metadata sharing, with all participants locked before actor binding.

No business payload or file download is authorized. Local operations are trusted
readonly composition, not a sandbox or a transaction around external delivery.
"""

from collections.abc import Mapping
from contextlib import contextmanager
from hashlib import sha256
import json
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, aliased

from ..authorization import AuthorizationError, Authorizer, Principal
from ..config import AuthFlowError
from ..models import AuthOwnedResource, AuthUser, AuthUserRole
from ..service import AuthService
from ..store import database_time
from ...privacy.models import PrivacyAdmissionRecord
from ...privacy.service import PrivacyService
from .models import AccessGrant, GrantAction, GrantField, SharingState
from .policy import MAX_DURATION_SECONDS, POLICY_HASH, POLICY_VERSION, sharing_policy
from .schemas import AcceptGrantInput, CreateGrantInput, GrantData, GrantListData, GrantMutationData, SharedPage, SharedProjection, SharingSettings
from ...api.v2.schemas import PageInfo
from ...audit.context import audited


class SharingError(AuthorizationError):
    pass


class SharingService:
    def __init__(self, auth_service, privacy_service, settings=None):
        self.auth_service, self.privacy_service = auth_service, privacy_service
        self.settings = settings if settings is not None else SharingSettings()
        self._validate()

    def _validate(self):
        try:
            if not isinstance(self.auth_service, AuthService) or not isinstance(self.privacy_service, PrivacyService):
                raise ValueError
            self.auth_service._validate()
            privacy = self.privacy_service._validate()
            settings = SharingSettings.model_validate(self.settings)
            if self.privacy_service.auth_service is not self.auth_service:
                raise ValueError
            if settings.fixture_mode and (self.auth_service.runtime_settings.app_environment != "test" or not privacy.fixture_mode):
                raise ValueError
            return settings
        except (AuthFlowError, ValidationError, ValueError, TypeError):
            raise SharingError(503) from None

    @contextmanager
    def _transaction(self):
        self._validate()
        try:
            with Session(self.auth_service.store.engine) as session, session.begin():
                yield session
        except AuthFlowError as error:
            raise SharingError(error.status_code, error.code) from None
        except Exception:
            raise SharingError(503) from None

    @staticmethod
    def _id(value):
        if not isinstance(value, UUID):
            raise SharingError(404)
        return value

    @staticmethod
    def _reference(principal):
        try:
            return Principal.model_validate(principal)
        except (ValidationError, ValueError, TypeError):
            raise SharingError(401) from None

    def _accounts(self, session, ids):
        ids = frozenset(self._id(item) for item in ids)
        marker = session.info.get("sharing_accounts_locked")
        if marker is not None and marker[0] is session.get_transaction():
            if not ids.issubset(marker[1]):
                raise SharingError(503)
            return [session.get(AuthUser, item, populate_existing=True) for item in sorted(ids)]
        # Account locks always precede session/role/admission/resource locks.
        rows = session.scalars(select(AuthUser).where(AuthUser.id.in_(ids)).order_by(AuthUser.id)
            .with_for_update().execution_options(populate_existing=True)).all()
        if {row.id for row in rows} != ids:
            raise SharingError(404)
        session.info["sharing_accounts_locked"] = (session.get_transaction(), ids)
        return rows

    def _refresh(self, session, principal):
        return self.auth_service.store.locked_principal(session, self._reference(principal),
            clock=self.auth_service._now, production=self.auth_service.runtime_settings.app_environment == "production")[0]

    def _ready(self, session):
        if not self._validate().fixture_mode:
            raise SharingError(503)
        if self.privacy_service._notice(session) is None:
            raise SharingError(503)

    def get_policy(self):
        self._validate()
        if not self.settings.fixture_mode:
            return sharing_policy(False)
        with self._transaction() as session:
            self._ready(session)
            return sharing_policy(True)

    @staticmethod
    def _policy(request):
        if request.sharing_policy_version != POLICY_VERSION or request.sharing_policy_hash != POLICY_HASH:
            raise SharingError(409)

    def _revision(self, session, user_id, increment=False):
        row = session.scalar(select(SharingState).where(SharingState.owner_user_id == user_id).with_for_update()
            .execution_options(populate_existing=True))
        if row is None:
            if not increment:
                return 0
            row = SharingState(owner_user_id=user_id, revision=0)
            session.add(row)
        if increment:
            row.revision += 1
            session.flush()
        return row.revision

    @staticmethod
    def _scope(fields, action):
        if (not isinstance(fields, tuple) or not 1 <= len(fields) <= 2
            or any(not isinstance(field, str) or field not in {"status", "version"} for field in fields)
            or len(set(fields)) != len(fields) or not isinstance(action, str) or action not in {"read", "list"}):
            raise SharingError(403)
        return tuple(sorted(fields)), action

    def _resource(self, session, resource_id, owner_id, kind):
        row = session.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == resource_id)
            .with_for_update().execution_options(populate_existing=True))
        parent = None
        if row is not None and row.parent_id is not None:
            parent = session.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == row.parent_id)
                .with_for_update().execution_options(populate_existing=True))
        if (row is None or row.owner_user_id != owner_id or row.resource_type != kind or row.status != "active"
            or not row.is_synthetic):
            raise SharingError(404)
        if kind in {"profile", "plan"}:
            if row.parent_id is not None:
                raise SharingError(404)
        elif (parent is None or parent.owner_user_id != owner_id or parent.status != "active"
            or parent.resource_type not in {"profile", "plan"} or parent.parent_id is not None or not parent.is_synthetic):
            raise SharingError(404)
        return row

    @staticmethod
    def _grant(session, grant_id):
        return session.scalar(select(AccessGrant).where(AccessGrant.id == grant_id).with_for_update()
            .execution_options(populate_existing=True))

    @staticmethod
    def _fields(session, row):
        fields = session.scalars(select(GrantField.field).where(GrantField.grant_id == row.id).order_by(GrantField.field)
            .with_for_update()).all()
        actions = session.scalars(select(GrantAction.action).where(GrantAction.grant_id == row.id).order_by(GrantAction.action)
            .with_for_update()).all()
        if not fields or not actions or any(field not in {"status", "version"} for field in fields) or any(action not in {"read", "list"} for action in actions):
            raise SharingError(503)
        return fields, actions

    def _effective(self, session, current, row, *, pending=False):
        self._ready(session)
        resource = self._resource(session, row.resource_id, row.owner_user_id, row.resource_type)
        owner = self.privacy_service.require_owner_purpose(session, row.owner_user_id)
        recipient = self.privacy_service.declared_adult_subject(session, row.grantee_user_id)
        self._fields(session, row)
        current = self._refresh(session, current)
        # Field, role and proof row locks may wait. Re-evaluate both subjects
        # after all locks are held, using current time rather than prior proof.
        owner = self.privacy_service.require_owner_purpose(session, row.owner_user_id)
        recipient = self.privacy_service.declared_adult_subject(session, row.grantee_user_id)
        now = self.auth_service._now()
        if (not current.is_synthetic or not row.is_synthetic or row.state not in ({"pending", "accepted"} if pending else {"accepted"})
            or row.revoked_at is not None or (not pending and row.accepted_at is None)
            or not database_time(row.created_at) <= now < database_time(row.expires_at)
            or row.sharing_policy_version != POLICY_VERSION or row.sharing_policy_hash != POLICY_HASH
            or row.owner_consent_id != owner.consent_id or row.grantee_declaration_id != recipient.declaration_id
            or row.resource_version != resource.version or not now < owner.expires_at or not now < recipient.expires_at):
            raise SharingError(404)
        return current, resource

    def _value(self, session, current, row):
        if self.auth_service.runtime_settings.app_environment == "production" and row.is_synthetic:
            raise SharingError(503)
        fields, actions = self._fields(session, row)
        try:
            self._effective(session, current, row)
            active = True
        except AuthFlowError:
            active = False
        return GrantData(id=row.id, resource_id=row.resource_id, resource_type=row.resource_type,
            resource_version=row.resource_version, owner_user_id=row.owner_user_id, grantee_user_id=row.grantee_user_id,
            fields=fields, actions=actions, created_at=database_time(row.created_at), expires_at=database_time(row.expires_at),
            accepted_at=database_time(row.accepted_at) if row.accepted_at is not None else None,
            revoked_at=database_time(row.revoked_at) if row.revoked_at is not None else None, state=row.state,
            version=row.version, sharing_policy_version=row.sharing_policy_version, is_synthetic=row.is_synthetic, access_active=active)

    def _audit(self, session, current, action, *, row=None, resource=None, kind=None):
        self.auth_service.store.audit.success(session, action, actor=current,
            object_type="access_grant" if row is not None and resource is None else resource.resource_type if resource is not None else kind,
            object_id=row.id if row is not None and resource is None else resource.id if resource is not None else None,
            object_version=row.version if row is not None and resource is None else resource.version if resource is not None else None,
            now=self.auth_service._now())
        return self._refresh(session, current)

    @audited("sharing.grant.create")
    def create_grant(self, principal, request):
        try:
            request = CreateGrantInput.model_validate(request)
        except (ValidationError, ValueError, TypeError):
            raise SharingError(403) from None
        principal = self._reference(principal)
        with self._transaction() as session:
            self._accounts(session, {principal.user_id, request.grantee_user_id})
            current = self._refresh(session, principal)
            self._ready(session)
            if current.user_id == request.grantee_user_id:
                raise SharingError(403)
            self._policy(request)
            resource = self._resource(session, request.resource_id, current.user_id, request.resource_type)
            owner = self.privacy_service.require_owner_purpose(session, current.user_id)
            recipient = self.privacy_service.declared_adult_subject(session, request.grantee_user_id)
            if (owner.consent_id != request.owner_consent_id or resource.version != request.expected_resource_version
                or self._revision(session, current.user_id) != request.expected_revision):
                raise SharingError(409)
            current = self._refresh(session, current)
            now = self.auth_service._now()
            if not now < request.expires_at or (request.expires_at - now).total_seconds() > MAX_DURATION_SECONDS:
                raise SharingError(403)
            row = AccessGrant(id=uuid4(), resource_id=resource.id, resource_type=resource.resource_type,
                resource_version=resource.version, owner_user_id=current.user_id, grantee_user_id=request.grantee_user_id,
                owner_consent_id=owner.consent_id, grantee_declaration_id=recipient.declaration_id,
                created_at=now, expires_at=request.expires_at, accepted_at=None, revoked_at=None, state="pending",
                version=1, sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH,
                is_synthetic=current.is_synthetic and recipient.is_synthetic and resource.is_synthetic)
            session.add(row)
            session.flush()
            session.add_all([GrantField(grant_id=row.id, field=field) for field in request.fields] +
                            [GrantAction(grant_id=row.id, action=action) for action in request.actions])
            session.flush()
            revision = self._revision(session, current.user_id, True)
            # Locks may have taken time; a positive transition needs fresh proof.
            current = self._audit(session, current, "sharing.grant.create", row=row)
            value = self._value(session, current, row)
            current, _ = self._effective(session, current, row, pending=True)
            return GrantMutationData(user_id=current.user_id, revision=revision, grant=value)

    def _related(self, session, principal, grant_id):
        snapshot = session.execute(select(AccessGrant.owner_user_id, AccessGrant.grantee_user_id).where(AccessGrant.id == grant_id)).first()
        if snapshot is None or principal.user_id not in snapshot:
            raise SharingError(404)
        self._accounts(session, {principal.user_id, snapshot.owner_user_id, snapshot.grantee_user_id})
        current = self._refresh(session, principal)
        # Match object -> parent -> grant lock order used by reading and creation.
        data = session.execute(select(AccessGrant.resource_id, AccessGrant.owner_user_id, AccessGrant.resource_type).where(AccessGrant.id == grant_id)).first()
        if data is None:
            raise SharingError(404)
        # Revoke must remain possible when the resource is deleted or changed.
        resource = session.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == data.resource_id).with_for_update()
            .execution_options(populate_existing=True))
        if resource is not None and resource.parent_id is not None:
            session.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == resource.parent_id).with_for_update()
                .execution_options(populate_existing=True))
        row = self._grant(session, grant_id)
        if row is None or current.user_id not in {row.owner_user_id, row.grantee_user_id} or {row.owner_user_id, row.grantee_user_id} != set(snapshot):
            raise SharingError(404)
        return self._refresh(session, current), row

    @audited("sharing.grant.accept")
    def accept_grant(self, principal, grant_id, request):
        principal, grant_id = self._reference(principal), self._id(grant_id)
        try:
            request = AcceptGrantInput.model_validate(request)
        except (ValidationError, ValueError, TypeError):
            raise SharingError(403) from None
        with self._transaction() as session:
            current, row = self._related(session, principal, grant_id)
            if current.user_id != row.grantee_user_id:
                raise SharingError(404)
            self._policy(request)
            if request.expected_version != row.version:
                raise SharingError(409)
            current, _ = self._effective(session, current, row, pending=True)
            if row.state == "pending":
                row.state, row.accepted_at, row.version = "accepted", self.auth_service._now(), row.version + 1
                session.flush()
            current = self._audit(session, current, "sharing.grant.accept", row=row)
            value, revision = self._value(session, current, row), self._revision(session, current.user_id)
            current, _ = self._effective(session, current, row)
            return GrantMutationData(user_id=current.user_id, revision=revision, grant=value)

    @audited("sharing.grant.revoke")
    def revoke_grant(self, principal, grant_id):
        principal, grant_id = self._reference(principal), self._id(grant_id)
        with self._transaction() as session:
            current, row = self._related(session, principal, grant_id)
            if row.state != "revoked":
                guard = self.auth_service.store.rights_guard
                if guard is not None:
                    guard.record(session, "grant_revoked", row.owner_user_id, resource_id=row.id)
                row.state, row.revoked_at, row.version = "revoked", self.auth_service._now(), row.version + 1
                self._revision(session, row.owner_user_id, True)
                session.flush()
            current = self._audit(session, current, "sharing.grant.revoke", row=row)
            value, revision = self._value(session, current, row), self._revision(session, current.user_id)
            current = self._refresh(session, current)
            return GrantMutationData(user_id=current.user_id, revision=revision, grant=value)

    @staticmethod
    def _page(limit, after_id):
        if type(limit) is not int or not 1 <= limit <= 100 or (after_id is not None and not isinstance(after_id, UUID)):
            raise SharingError(403)

    def _list_accounts(self, session, principal, direction=None):
        condition = AccessGrant.grantee_user_id == principal.user_id if direction == "received" else AccessGrant.owner_user_id == principal.user_id
        if direction is None:
            condition = AccessGrant.grantee_user_id == principal.user_id
        pairs = session.execute(select(AccessGrant.owner_user_id, AccessGrant.grantee_user_id).where(condition)).all()
        ids = {principal.user_id} | {value for pair in pairs for value in pair}
        self._accounts(session, ids)
        # A concurrent create can commit between initial lookup and account locks.
        # Never append out-of-order locks; retry at a new call if scope changed.
        fresh = session.execute(select(AccessGrant.owner_user_id, AccessGrant.grantee_user_id).where(condition)).all()
        if any(value not in ids for pair in fresh for value in pair):
            raise SharingError(503)
        return self._refresh(session, principal)

    @audited("sharing.list")
    def list_grants(self, principal, direction="issued", limit=20, after_id=None):
        principal = self._reference(principal)
        self._page(limit, after_id)
        if not isinstance(direction, str) or direction not in {"issued", "received"}:
            raise SharingError(403)
        with self._transaction() as session:
            current = self._list_accounts(session, principal, direction)
            condition = AccessGrant.owner_user_id == current.user_id if direction == "issued" else AccessGrant.grantee_user_id == current.user_id
            total = session.scalar(select(func.count()).select_from(AccessGrant).where(condition))
            query = select(AccessGrant.id).where(condition)
            if after_id is not None:
                query = query.where(AccessGrant.id > after_id)
            ids = session.scalars(query.order_by(AccessGrant.id).limit(limit + 1)).all()
            values = []
            for grant_id in ids[:limit]:
                current, row = self._related(session, current, grant_id)
                values.append(self._value(session, current, row))
            current = self._audit(session, current, "sharing.list", kind="access_grant")
            # Management history stays visible, but current permission labels
            # and subject references are rebuilt after required audit I/O.
            values = [self._value(session, current, self._grant(session, item.id)) for item in values]
            declaration, consent = None, None
            if self.settings.fixture_mode:
                try:
                    declaration = self.privacy_service.require_declared_adult(session, current).declaration_id
                except AuthFlowError:
                    pass
                try:
                    consent = self.privacy_service.require_owner_purpose(session, current.user_id).consent_id
                except AuthFlowError:
                    pass
            current = self._refresh(session, current)
            return GrantListData(user_id=current.user_id, revision=self._revision(session, current.user_id),
                actor_declaration_id=declaration, owner_consent_id=consent, sharing_available=self.settings.fixture_mode,
                total=total, items=values, page=PageInfo(limit=limit, next_cursor=str(ids[limit - 1]) if len(ids) > limit else None,
                    has_more=len(ids) > limit))

    def _sql_scope(self, actor_id, kind, fields, action, now):
        """Every permission predicate is applied before COUNT or pagination."""
        owner, receiver, parent = aliased(AuthUser), aliased(AuthUser), aliased(AuthOwnedResource)
        latest_owner, latest_receiver = aliased(PrivacyAdmissionRecord), aliased(PrivacyAdmissionRecord)
        newer_owner, newer_receiver, declaration, newer_decl, original_consent = (aliased(PrivacyAdmissionRecord) for _ in range(5))
        owner_current = exists(select(latest_owner.id).where(latest_owner.user_id == AccessGrant.owner_user_id,
            ~exists(select(newer_owner.id).where(newer_owner.user_id == latest_owner.user_id, newer_owner.revision > latest_owner.revision)),
            latest_owner.age_band == "18_plus", latest_owner.age_assurance == "declared", latest_owner.declared_at <= now,
            latest_owner.declaration_expires_at > now, latest_owner.declaration_notice_id == self.privacy_service.settings.notice_id,
            latest_owner.policy_version == self.privacy_service.settings.policy_version, latest_owner.consent_status == "active",
            latest_owner.consent_id == AccessGrant.owner_consent_id,
            latest_owner.consent_notice_id == self.privacy_service.settings.notice_id,
            exists(select(original_consent.id).where(original_consent.id == AccessGrant.owner_consent_id,
                original_consent.user_id == AccessGrant.owner_user_id, original_consent.event_type == "consent_confirmed",
                original_consent.consent_id == original_consent.id, original_consent.consent_status == "active",
                original_consent.consent_notice_id == self.privacy_service.settings.notice_id,
                original_consent.policy_version == self.privacy_service.settings.policy_version))))
        receiver_current = exists(select(latest_receiver.id).where(latest_receiver.user_id == AccessGrant.grantee_user_id,
            ~exists(select(newer_receiver.id).where(newer_receiver.user_id == latest_receiver.user_id, newer_receiver.revision > latest_receiver.revision)),
            latest_receiver.age_band == "18_plus", latest_receiver.age_assurance == "declared", latest_receiver.declared_at <= now,
            latest_receiver.declaration_expires_at > now, latest_receiver.declaration_notice_id == self.privacy_service.settings.notice_id,
            latest_receiver.policy_version == self.privacy_service.settings.policy_version,
            exists(select(declaration.id).where(declaration.id == AccessGrant.grantee_declaration_id,
                declaration.user_id == latest_receiver.user_id, declaration.event_type == "adult_declared",
                declaration.age_band == "18_plus", declaration.age_assurance == "declared",
                declaration.declaration_notice_id == latest_receiver.declaration_notice_id,
                declaration.policy_version == latest_receiver.policy_version,
                declaration.declared_at == latest_receiver.declared_at, declaration.declaration_expires_at == latest_receiver.declaration_expires_at,
                ~exists(select(newer_decl.id).where(newer_decl.user_id == declaration.user_id,
                    newer_decl.event_type == "adult_declared", newer_decl.revision > declaration.revision))))))
        conditions = [AccessGrant.grantee_user_id == actor_id, AccessGrant.state == "accepted", AccessGrant.revoked_at.is_(None),
            AccessGrant.accepted_at.is_not(None), AccessGrant.created_at <= now, AccessGrant.expires_at > now,
            AccessGrant.is_synthetic.is_(True), AccessGrant.sharing_policy_version == POLICY_VERSION,
            AccessGrant.sharing_policy_hash == POLICY_HASH,
            AccessGrant.resource_id == AuthOwnedResource.id, AccessGrant.owner_user_id == AuthOwnedResource.owner_user_id,
            AccessGrant.resource_type == kind, AuthOwnedResource.resource_type == kind,
            AccessGrant.resource_version == AuthOwnedResource.version, AuthOwnedResource.status == "active",
            AuthOwnedResource.is_synthetic.is_(True), owner_current, receiver_current,
            exists(select(owner.id).where(owner.id == AccessGrant.owner_user_id, owner.status == "active", owner.is_synthetic.is_(True))),
            exists(select(receiver.id).where(receiver.id == actor_id, receiver.status == "active", receiver.is_synthetic.is_(True))),
            exists(select(AuthUserRole.user_id).where(AuthUserRole.user_id == AccessGrant.owner_user_id,
                AuthUserRole.role == "student", AuthUserRole.revoked_at.is_(None), AuthUserRole.granted_at <= now,
                (AuthUserRole.expires_at.is_(None) | (AuthUserRole.expires_at > now)))),
            exists(select(GrantAction.grant_id).where(GrantAction.grant_id == AccessGrant.id, GrantAction.action == action))]
        for field in fields:
            conditions.append(exists(select(GrantField.grant_id).where(GrantField.grant_id == AccessGrant.id, GrantField.field == field)))
        if kind in {"profile", "plan"}:
            conditions.append(AuthOwnedResource.parent_id.is_(None))
        else:
            conditions.append(exists(select(parent.id).where(parent.id == AuthOwnedResource.parent_id,
                parent.owner_user_id == AccessGrant.owner_user_id, parent.status == "active", parent.is_synthetic.is_(True),
                parent.resource_type.in_(["profile", "plan"]), parent.parent_id.is_(None))))
        return conditions

    @staticmethod
    def _projection(resource, fields):
        return SharedProjection(resource_id=resource.id, resource_type=resource.resource_type, is_synthetic=resource.is_synthetic,
            requested_fields=fields, status=resource.status if "status" in fields else None,
            version=resource.version if "version" in fields else None)

    def _shared(self, session, principal, kind, resource_id, fields, action):
        if not isinstance(kind, str) or kind not in {"profile", "plan", "attachment", "export", "job"}:
            raise SharingError(403)
        candidates = session.execute(select(AccessGrant.id, AccessGrant.owner_user_id).where(
            AccessGrant.resource_id == resource_id, AccessGrant.resource_type == kind, AccessGrant.grantee_user_id == principal.user_id)
            .order_by(AccessGrant.id)).all()
        if not candidates:
            # Validate actor even when the object reference is not visible.
            self._accounts(session, {principal.user_id})
            self._refresh(session, principal)
            raise SharingError(404)
        self._accounts(session, {principal.user_id} | {row.owner_user_id for row in candidates})
        current = self._refresh(session, principal)
        self._ready(session)
        resource = self._resource(session, resource_id, candidates[0].owner_user_id, kind)
        query = select(AccessGrant).where(*self._sql_scope(current.user_id, kind, fields, action, self.auth_service._now()),
            AccessGrant.resource_id == resource_id).order_by(AccessGrant.id)
        row = session.scalar(query.with_for_update(of=AccessGrant).execution_options(populate_existing=True))
        if row is None or row.owner_user_id not in session.info["sharing_accounts_locked"][1]:
            raise SharingError(404)
        current, resource = self._effective(session, current, row)
        granted_fields, actions = self._fields(session, row)
        if not set(fields).issubset(granted_fields) or action not in actions:
            raise SharingError(404)
        return current, resource, row

    @audited("sharing.read")
    def require_shared(self, principal, kind, resource_id, fields, action="read"):
        principal, resource_id = self._reference(principal), self._id(resource_id)
        fields, action = self._scope(fields, action)
        with self._transaction() as session:
            current, resource, row = self._shared(session, principal, kind, resource_id, fields, action)
            current = self._audit(session, current, "sharing.read", resource=resource)
            _, resource = self._effective(session, current, row)
            return self._projection(resource, fields)

    @audited("sharing.list")
    def list_shared(self, principal, kind, fields, action="list", limit=20, after_id=None):
        principal = self._reference(principal)
        fields, action = self._scope(fields, action)
        self._page(limit, after_id)
        if not isinstance(kind, str) or kind not in {"profile", "plan", "attachment", "export", "job"}:
            raise SharingError(403)
        with self._transaction() as session:
            current = self._list_accounts(session, principal)
            self._ready(session)
            for _ in range(3):
                scope = self._sql_scope(current.user_id, kind, fields, action, self.auth_service._now())
                query = select(AuthOwnedResource).join(AccessGrant, AccessGrant.resource_id == AuthOwnedResource.id).where(*scope).distinct()
                if after_id is not None:
                    query = query.where(AuthOwnedResource.id > after_id)
                # DISTINCT FOR UPDATE is forbidden in PostgreSQL; obtain an
                # exact UUID window first, then lock each object and parent.
                ids = session.scalars(query.with_only_columns(AuthOwnedResource.id).order_by(AuthOwnedResource.id).limit(limit + 1)).all()
                for resource_id in ids:
                    owner_id = session.scalar(select(AuthOwnedResource.owner_user_id).where(AuthOwnedResource.id == resource_id))
                    if owner_id not in session.info["sharing_accounts_locked"][1]:
                        raise SharingError(503)
                    try:
                        self._resource(session, resource_id, owner_id, kind)
                    except SharingError as error:
                        if error.status_code != 404:
                            raise
                current = self._refresh(session, current)
                scope = self._sql_scope(current.user_id, kind, fields, action, self.auth_service._now())
                fresh_query = select(AuthOwnedResource.id).join(AccessGrant, AccessGrant.resource_id == AuthOwnedResource.id).where(*scope).distinct()
                if after_id is not None:
                    fresh_query = fresh_query.where(AuthOwnedResource.id > after_id)
                fresh_ids = session.scalars(fresh_query.order_by(AuthOwnedResource.id).limit(limit + 1)).all()
                if fresh_ids != ids:
                    continue
                total = session.scalar(select(func.count()).select_from(select(AuthOwnedResource.id).join(AccessGrant,
                    AccessGrant.resource_id == AuthOwnedResource.id).where(*scope).distinct().subquery()))
                projections = []
                for resource_id in ids[:limit]:
                    _, resource, _ = self._shared(session, current, kind, resource_id, fields, action)
                    projections.append(self._projection(resource, fields))
                current = self._refresh(session, current)
                # Even a later row's lock wait can cross an earlier grant's
                # absolute expiry. Rebuild the complete SQL scope at return.
                scope = self._sql_scope(current.user_id, kind, fields, action, self.auth_service._now())
                final_query = select(AuthOwnedResource.id).join(AccessGrant, AccessGrant.resource_id == AuthOwnedResource.id).where(*scope).distinct()
                if after_id is not None:
                    final_query = final_query.where(AuthOwnedResource.id > after_id)
                if session.scalars(final_query.order_by(AuthOwnedResource.id).limit(limit + 1)).all() != ids:
                    continue
                total = session.scalar(select(func.count()).select_from(select(AuthOwnedResource.id).join(AccessGrant,
                    AccessGrant.resource_id == AuthOwnedResource.id).where(*scope).distinct().subquery()))
                current = self._audit(session, current, "sharing.list", kind=kind)
                scope = self._sql_scope(current.user_id, kind, fields, action, self.auth_service._now())
                audit_query = select(AuthOwnedResource.id).join(AccessGrant, AccessGrant.resource_id == AuthOwnedResource.id).where(*scope).distinct()
                if after_id is not None:
                    audit_query = audit_query.where(AuthOwnedResource.id > after_id)
                if session.scalars(audit_query.order_by(AuthOwnedResource.id).limit(limit + 1)).all() != ids:
                    continue
                total = session.scalar(select(func.count()).select_from(select(AuthOwnedResource.id).join(AccessGrant,
                    AccessGrant.resource_id == AuthOwnedResource.id).where(*scope).distinct().subquery()))
                return SharedPage(items=tuple(projections), total=total,
                    next_cursor=ids[limit - 1] if len(ids) > limit else None)
            raise SharingError(503)

    @audited("sharing.execute_read")
    def execute_shared(self, principal, kind, resource_id, fields, operation, action="read"):
        if not callable(operation):
            raise SharingError(403)
        principal, resource_id = self._reference(principal), self._id(resource_id)
        fields, action = self._scope(fields, action)
        with self._transaction() as session:
            current, resource, row = self._shared(session, principal, kind, resource_id, fields, action)
            projection = self._projection(resource, fields)
            current, resource = self._effective(session, current, row)
            result = operation(session, current, projection)
            # Catch accidental unflushed ORM writes. This trusted local callback
            # is not a SQL sandbox: raw SQL/explicit flush is not policed here.
            if session.new or session.dirty or session.deleted:
                raise SharingError(403)
            current = self._audit(session, current, "sharing.execute_read", resource=resource)
            self._effective(session, current, row)
            return result

    @staticmethod
    def _key(current, resource, row, fields, action, filters):
        values = [POLICY_VERSION, POLICY_HASH, str(current.user_id), str(current.session_id), current.authorization_context,
            str(resource.id), resource.resource_type, resource.version, str(row.id), row.version, str(row.owner_consent_id),
            str(row.grantee_declaration_id), fields, action, filters]
        return "shared:" + sha256(json.dumps(values, separators=(",", ":")).encode("ascii")).hexdigest()

    @audited("sharing.read")
    def cache_key(self, principal, kind, resource_id, fields, action="read", *, filters=()):
        principal, resource_id = self._reference(principal), self._id(resource_id)
        fields, action = self._scope(fields, action)
        filters = Authorizer._filters(filters)
        with self._transaction() as session:
            current, resource, row = self._shared(session, principal, kind, resource_id, fields, action)
            current = self._audit(session, current, "sharing.read", resource=resource)
            current, resource = self._effective(session, current, row)
            return self._key(current, resource, row, fields, action, filters)

    @audited("sharing.read")
    def cached_value(self, principal, kind, resource_id, fields, cache: Mapping, action="read", *, filters=()):
        if not isinstance(cache, Mapping):
            raise SharingError(403)
        principal, resource_id = self._reference(principal), self._id(resource_id)
        fields, action = self._scope(fields, action)
        filters = Authorizer._filters(filters)
        with self._transaction() as session:
            current, resource, row = self._shared(session, principal, kind, resource_id, fields, action)
            key = self._key(current, resource, row, fields, action, filters)
            value = cache.get(key)
            current = self._audit(session, current, "sharing.read", resource=resource)
            current, resource = self._effective(session, current, row)
            if self._key(current, resource, row, fields, action, filters) != key:
                return None
            try:
                cached = SharedProjection.model_validate(value)
            except (ValidationError, ValueError, TypeError):
                return None
            fresh = self._projection(resource, fields)
            return fresh if cached == fresh else None
