"""Owner-confirmed private versions, with current purpose and transactional receipts."""

import base64
from contextlib import contextmanager
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import String, case, func, select
from sqlalchemy.orm import Session

from ..audit.context import audited
from ..audit.models import AuditEvent
from ..auth.authorization import Authorizer, AuthorizationError, Principal, Role
from ..auth.config import AuthFlowError
from ..auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from ..auth.service import AuthService
from ..idempotency.models import IdempotencyRecord
from ..idempotency.schemas import IdempotencyError, ResourceReceipt
from ..idempotency.service import IdempotencyService
from ..privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from ..privacy.service import PrivacyService
from .models import ProfileRoot, ProfileVersion
from .schemas import (AppendInput, CreateInput, ProfileContextData, ProfileError, ProfilePage,
                      ProfilePolicy, ProfileRef, ProfileWriteData)
from .store import ProfilesStore, database_time


class ProfileService:
    def __init__(self, auth_service: AuthService, privacy_service: PrivacyService,
                 idempotency_service: IdempotencyService, store: ProfilesStore,
                 policy: ProfilePolicy = ProfilePolicy()):
        self.auth_service, self.privacy_service, self.idempotency_service, self.store = (
            auth_service, privacy_service, idempotency_service, store)
        try:
            self.policy = ProfilePolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise ProfileError() from None
        self._initial_policy = self.policy
        self._initial_runtime = getattr(auth_service, "runtime_settings", None)
        self._initial_clock = getattr(auth_service, "clock", None)
        self._validate()
        self.authorizer = Authorizer(auth_service)

    def _validate(self):
        if (not isinstance(self.auth_service, AuthService) or not isinstance(self.privacy_service, PrivacyService)
            or not isinstance(self.idempotency_service, IdempotencyService) or not isinstance(self.store, ProfilesStore)
            or self.privacy_service.auth_service is not self.auth_service
            or self.idempotency_service.auth_service is not self.auth_service
            or self.idempotency_service.privacy_service is not self.privacy_service
            or self.store.engine is not self.auth_service.store.engine
            or self.idempotency_service.store.engine is not self.store.engine
            or self.auth_service.runtime_settings != self._initial_runtime
            or self.auth_service.clock is not self._initial_clock):
            raise ProfileError()
        self.auth_service._validate()
        self.privacy_service._validate()
        self.idempotency_service._validate()
        try:
            current = ProfilePolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise ProfileError() from None
        if current != self._initial_policy:
            raise ProfileError()
        return current

    def _guard_session(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise ProfileError()
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                PrivacyNoticeVersion, PrivacyAdmissionRecord, AuditEvent, IdempotencyRecord, ProfileRoot, ProfileVersion):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise ProfileError()
        except ProfileError:
            raise
        except Exception:
            raise ProfileError() from None

    def _abort(self, supplied):
        try:
            if isinstance(supplied, Session) and supplied.in_transaction():
                bind = supplied.get_bind()
                if getattr(bind, "engine", bind) is self.store.engine:
                    supplied.rollback()
        except Exception:
            pass

    @contextmanager
    def _transaction(self, supplied=None):
        try:
            self._validate()
            if supplied is None:
                with Session(self.store.engine) as session, session.begin():
                    self._guard_session(session)
                    yield session
            else:
                self._guard_session(supplied)
                yield supplied
        except (ProfileError, AuthFlowError, IdempotencyError):
            self._abort(supplied)
            raise
        except Exception:
            self._abort(supplied)
            raise ProfileError() from None

    @staticmethod
    def _input(model, value):
        try:
            return model.model_validate(value)
        except (ValueError, ValidationError, TypeError):
            raise ProfileError(422) from None

    def _authorize(self, session, principal):
        self._guard_session(session)
        policy = self._validate()
        current, _ = self.authorizer._refresh(principal, session)
        if Role.student not in current.roles:
            raise AuthorizationError(403)
        if not policy.enabled:
            raise ProfileError()
        if current.is_synthetic:
            if self.auth_service.runtime_settings.app_environment != "test":
                raise ProfileError()
        elif not policy.real_profiles_ready:
            raise ProfileError()
        self.privacy_service.require_purpose(session, current, "core_consultation")
        return current

    def _proof(self, session, current):
        # Privacy remains the single current-actor guard. These rows retain the
        # exact proof and deadlines for the final, SQL-free validation boundary.
        self.privacy_service.require_purpose(session, current, "core_consultation")
        notice = self.privacy_service._notice(session, current)
        admission = self.privacy_service._latest(session, current)
        declaration = session.scalar(select(PrivacyAdmissionRecord).where(
            PrivacyAdmissionRecord.user_id == current.user_id,
            PrivacyAdmissionRecord.event_type == "adult_declared",
            PrivacyAdmissionRecord.revision <= admission.revision)
            .order_by(PrivacyAdmissionRecord.revision.desc()).limit(1).with_for_update()
            .execution_options(populate_existing=True))
        if declaration is None or notice is None or admission.consent_id is None:
            raise AuthorizationError(403)
        return SimpleNamespace(admission=admission, declaration=declaration, notice=notice)

    @staticmethod
    def _binding(row, proof):
        if (row.admission_id != proof.admission.id or row.consent_id != proof.admission.consent_id
            or row.declaration_id != proof.declaration.id or row.notice_id != proof.notice.id
            or row.policy_version != proof.notice.policy_version or row.notice_sha256 != proof.notice.text_sha256):
            raise AuthorizationError(403)

    def _root(self, session, current, profile_id, *, action="read"):
        current, owned = self.authorizer.check_owned_in_transaction(session, current, "profile", profile_id, action)
        root = self.store.get_root(session, profile_id, current.user_id)
        if (root.is_synthetic != current.is_synthetic or owned.is_synthetic != current.is_synthetic
            or owned.parent_id is not None or root.current_version != owned.version):
            raise ProfileError()
        return current, root

    def _read(self, session, current, profile_id, *, version_id=None, number=None):
        current, root = self._root(session, current, profile_id)
        row = self.store.get_version(session, root, version_id=version_id, number=number)
        proof = self._proof(session, current)
        self._binding(row, proof)
        data = self.store.version_data(row)
        return current, root, row, proof, data

    def _final(self, session, current, proof, rows=(), roots=()):
        # Refresh binding/identity first; the following role query is the last
        # SQL. All deadlines share one fresh time, including secondary-role I/O.
        current, _ = self.authorizer._refresh(current, session)
        identity = session.execute(select(AuthUser, AuthSession).join(AuthSession,
            AuthSession.user_id == AuthUser.id).where(AuthUser.id == current.user_id,
            AuthSession.id == current.session_id).with_for_update(of=(AuthUser, AuthSession))
            .execution_options(populate_existing=True)).one_or_none()
        roles = session.scalars(select(AuthUserRole).where(AuthUserRole.user_id == current.user_id)
            .order_by(AuthUserRole.role).with_for_update().execution_options(populate_existing=True)).all()
        now = self.auth_service._now()
        policy = self._validate()
        if identity is None:
            raise AuthorizationError(401)
        user, login = identity
        if (user.status != "active" or login.revoked_at is not None or user.is_synthetic != current.is_synthetic
            or not database_time(login.created_at) <= now < database_time(login.expires_at)):
            raise AuthorizationError(401)
        student = [r for r in roles if r.role == "student" and r.revoked_at is None
            and database_time(r.granted_at) <= now and (r.expires_at is None or now < database_time(r.expires_at))]
        if not student:
            raise AuthorizationError(403)
        if not policy.enabled or (not current.is_synthetic and not policy.real_profiles_ready):
            raise ProfileError()
        privacy_settings = self.privacy_service._validate()
        admission, declaration, notice = proof.admission, proof.declaration, proof.notice
        if not privacy_settings.fixture_mode:
            raise ProfileError()
        if (notice.id != privacy_settings.notice_id or notice.controller_reference != privacy_settings.controller_reference
            or notice.review_status != "test_reviewed" or not notice.is_synthetic
            or admission.user_id != current.user_id or declaration.user_id != current.user_id
            or admission.age_band != "18_plus" or admission.age_assurance != "declared"
            or admission.consent_status != "active" or admission.policy_version != privacy_settings.policy_version
            or admission.policy_version != notice.policy_version
            or admission.declaration_notice_id != notice.id or admission.consent_notice_id != notice.id
            or notice.text_sha256 != sha256(notice.text.encode("utf-8")).hexdigest()
            or declaration.declared_at != admission.declared_at or declaration.declaration_notice_id != notice.id
            or not database_time(admission.declared_at) <= now < database_time(admission.declaration_expires_at)
            or database_time(admission.recorded_at) > now or database_time(declaration.recorded_at) > now
            or database_time(notice.reviewed_at) > now or database_time(admission.consent_confirmed_at) > now):
            raise AuthorizationError(403)
        for root in roots:
            if database_time(root.created_at) > now:
                raise ProfileError(409)
        for row in rows:
            self._binding(row, proof)
            if not database_time(row.confirmed_at) <= now < database_time(row.expires_at):
                raise ProfileError(409)
        return now

    def preflight(self, principal):
        with self._transaction() as session:
            current = self._authorize(session, principal)
            proof = self._proof(session, current)
            self._final(session, current, proof)

    def context(self, principal, *, session=None):
        with self._transaction(session) as same:
            current, _ = self.authorizer._refresh(principal, same)
            policy = self._validate()
            if not policy.enabled:
                result = ProfileContextData(schema_version="v2.t23", can_create=False, can_read=False,
                    can_append=False, reason="processing_disabled", is_synthetic=current.is_synthetic)
            else:
                current = self._authorize(same, current)
                proof = self._proof(same, current)
                self._final(same, current, proof)
                receipt_policy = self.idempotency_service.policy
                can_create = receipt_policy.enabled and (current.is_synthetic or receipt_policy.real_idempotency_ready)
                result = ProfileContextData(schema_version="v2.t23", can_create=can_create, can_read=True,
                    can_append=True, reason="allowed", is_synthetic=current.is_synthetic)
        return result

    @audited("authorization.owned.register")
    def create_profile(self, principal, request, key, *, session=None):
        with self._transaction(session) as same:
            request = self._input(CreateInput, request)
            current = self._authorize(same, principal)
            slot = {}

            def perform(transaction, actor):
                try:
                    proof = self._proof(transaction, actor)
                    owned = self.authorizer.register_owned(actor, "profile", session=transaction)
                    proof.profile_id = owned.id
                    _, row = self.store.create_version(transaction, actor, request.profile, proof, now=self.auth_service._now())
                    return ResourceReceipt(kind="profile", resource_id=row.profile_id, version=row.version)
                except (ProfileError, AuthFlowError) as error:
                    slot.setdefault("error", error)
                    raise

            def verify(transaction, actor, receipt):
                try:
                    actor, root, row, proof, data = self._read(transaction, actor, receipt.resource_id, number=receipt.version)
                    self._final(transaction, actor, proof, (row,), (root,))
                    return True
                except (ProfileError, AuthFlowError) as error:
                    slot.setdefault("error", error)
                    raise

            try:
                receipt = self.idempotency_service.execute(current, "profile.create", key,
                    request.model_dump(mode="json"), perform=perform, verify_resource=verify, session=same)
            except (IdempotencyError, AuthFlowError):
                if "error" in slot:
                    raise slot["error"] from None
                raise
            current, root, row, proof, data = self._read(same, current, receipt.resource.resource_id, number=receipt.resource.version)
            result = ProfileWriteData(version=data, replayed=receipt.replayed)
            final_now = self._final(same, current, proof, (row,), (root,))
            if final_now >= receipt.expires_at:
                raise ProfileError(409)
        return result

    @audited("authorization.owned.execute")
    def append_version(self, principal, profile_id, request, *, session=None):
        with self._transaction(session) as same:
            request = self._input(AppendInput, request)
            current = self._authorize(same, principal)
            current, root = self._root(same, current, profile_id, action="write")
            proof = self._proof(same, current)
            root, row = self.store.create_version(same, current, request.profile, proof,
                now=self.auth_service._now(), root=root, expected_version=request.expected_current_version)
            registry = same.get(AuthOwnedResource, root.id)
            registry.version = root.current_version
            same.flush()
            self.auth_service.store.audit.success(same, "authorization.owned.execute", actor=current,
                object_type="profile", object_id=root.id, object_version=row.version, now=self.auth_service._now())
            proof = self._proof(same, current)
            result = ProfileWriteData(version=self.store.version_data(row), replayed=False)
            self._final(same, current, proof, (row,), (root,))
        return result

    @audited("authorization.owned.check")
    def get_profile(self, principal, profile_id, *, session=None):
        return self.get_version(principal, profile_id, None, session=session)

    @audited("authorization.owned.check")
    def get_version(self, principal, profile_id, version_id, *, session=None):
        with self._transaction(session) as same:
            if version_id is not None and not isinstance(version_id, UUID):
                raise ProfileError(404)
            current = self._authorize(same, principal)
            current, root, row, proof, data = self._read(same, current, profile_id, version_id=version_id)
            self.auth_service.store.audit.success(same, "authorization.owned.check", actor=current,
                object_type="profile", object_id=root.id, object_version=row.version, now=self.auth_service._now())
            proof = self._proof(same, current)
            self._final(same, current, proof, (row,), (root,))
        return data

    def _window(self, session, current, proof):
        # A count/max window fingerprint invalidates traversal after create or
        # append. It carries references only, never students' payload values.
        values = session.execute(select(func.count(ProfileRoot.id), func.max(ProfileRoot.current_version_id.cast(String)),
            func.coalesce(func.sum(case((AuthOwnedResource.status == "active", 1), else_=0)), 0))
            .join(AuthOwnedResource, AuthOwnedResource.id == ProfileRoot.id)
            .where(ProfileRoot.owner_user_id == current.user_id)).one()
        count, marker, active = values
        # Sum versions catches an append on a root whose UUID is not MAX.
        total = session.scalar(select(func.coalesce(func.sum(ProfileRoot.current_version), 0)).where(ProfileRoot.owner_user_id == current.user_id))
        return sha256(json.dumps([str(current.user_id), current.authorization_context, str(proof.admission.id),
            count, marker, total, active], separators=(",", ":")).encode("ascii")).hexdigest()

    @staticmethod
    def _cursor(value, *, actor, window, limit):
        try:
            if type(value) is not str or len(value) > 2048:
                raise ValueError()
            raw = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
            data = json.loads(raw)
            if (type(data) is not dict or set(data) != {"actor", "window", "limit", "after"}
                or data["actor"] != str(actor) or data["window"] != window or type(data["limit"]) is not int
                or data["limit"] != limit or type(data["after"]) is not str):
                raise ValueError()
            after = UUID(data["after"])
            if str(after) != data["after"]:
                raise ValueError()
            return after
        except (ValueError, TypeError, UnicodeError):
            raise ProfileError(409) from None

    @audited("authorization.owned.list")
    def list_profiles(self, principal, *, limit=20, cursor=None, session=None):
        with self._transaction(session) as same:
            if type(limit) is not int or not 1 <= limit <= 20:
                raise ProfileError(422)
            current = self._authorize(same, principal)
            proof = self._proof(same, current)
            window = self._window(same, current, proof)
            after = self._cursor(cursor, actor=current.user_id, window=window, limit=limit) if cursor is not None else None
            rows = self.store.list_window(same, current, proof, now=self.auth_service._now(), limit=limit, after_id=after)
            selected = rows[:limit]
            items = tuple(ProfileRef(profile_id=root.id, version_id=row.id, version=row.version,
                confirmed_at=database_time(row.confirmed_at), expires_at=database_time(row.expires_at),
                is_synthetic=row.is_synthetic) for root, row in selected)
            next_cursor = None
            if len(rows) > limit:
                next_cursor = base64.urlsafe_b64encode(json.dumps({"actor": str(current.user_id), "window": window,
                    "limit": limit, "after": str(selected[-1][0].id)}, sort_keys=True, separators=(",", ":")).encode("ascii")).decode("ascii")
            result = ProfilePage(items=items, next_cursor=next_cursor)
            self.auth_service.store.audit.success(same, "authorization.owned.list", actor=current, now=self.auth_service._now())
            proof = self._proof(same, current)
            self._final(same, current, proof, tuple(row for _, row in rows), tuple(root for root, _ in rows))
        return result
