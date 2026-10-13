"""Current authority and minimal receipts around local, same-transaction work."""

from contextlib import contextmanager
from hashlib import sha256
import re

from pydantic import SecretStr, ValidationError
from sqlalchemy.orm import Session

from ..api.v2.idempotency_canonical import CanonicalRequestError, canonical_request_hash
from ..audit.context import audited
from ..audit.models import AuditEvent
from ..auth.authorization import Authorizer, AuthorizationError, Role
from ..auth.config import AuthFlowError
from ..auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from ..auth.service import AuthService
from ..privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from ..privacy.service import PrivacyService
from .models import IdempotencyRecord
from .schemas import IdempotencyError, IdempotencyPolicy, IdempotencyResult, ResourceReceipt
from .store import IdempotencyStore, OPERATION_KINDS, utc_time

_AUDIT_ACTIONS = {"catalog.import": "catalog.import", "catalog.publish": "catalog.publish",
                  "profile.create": "authorization.owned.register", "plan.confirm": "authorization.owned.execute"}


class IdempotencyService:
    def __init__(self, auth_service: AuthService, privacy_service: PrivacyService,
                 store: IdempotencyStore, policy: IdempotencyPolicy = IdempotencyPolicy()):
        self.auth_service, self.privacy_service, self.store = auth_service, privacy_service, store
        try:
            self.policy = IdempotencyPolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise IdempotencyError() from None
        self._initial_policy = self.policy
        self._validate()
        self.authorizer = Authorizer(self.auth_service)

    def _validate(self):
        if (not isinstance(self.auth_service, AuthService) or not isinstance(self.privacy_service, PrivacyService)
            or not isinstance(self.store, IdempotencyStore)
            or self.privacy_service.auth_service is not self.auth_service
            or self.store.engine is not self.auth_service.store.engine):
            raise IdempotencyError()
        settings = self.auth_service._validate()
        self.privacy_service._validate()
        try:
            policy = IdempotencyPolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise IdempotencyError() from None
        if policy != self._initial_policy:
            raise IdempotencyError()
        return settings, policy

    def _guard_session(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise IdempotencyError()
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                           PrivacyNoticeVersion, PrivacyAdmissionRecord, AuditEvent, IdempotencyRecord):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise IdempotencyError()
        except IdempotencyError:
            raise
        except Exception:
            raise IdempotencyError() from None

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
        except (AuthFlowError, IdempotencyError):
            raise
        except Exception:
            raise IdempotencyError() from None

    @staticmethod
    def _key_digest(key):
        if not isinstance(key, SecretStr):
            raise IdempotencyError(422)
        value = key.get_secret_value()
        if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
            raise IdempotencyError(422)
        return sha256(value.encode("ascii")).hexdigest()

    def _authorize(self, session, principal, operation, expected_policy):
        settings, policy = self._validate()
        self._guard_session(session)
        if not policy.enabled:
            raise IdempotencyError()
        if operation.startswith("catalog."):
            if settings.admin_assurance_policy != expected_policy:
                raise AuthorizationError(403)
            current = self.authorizer.check_capability_in_transaction(session, principal, operation)
        else:
            current, _ = self.authorizer._refresh(principal, session)
            if Role.student not in current.roles:
                raise AuthorizationError(403)
            self.privacy_service.require_purpose(session, current, "core_consultation")
            current, _ = self.authorizer._refresh(current, session)
            if Role.student not in current.roles:
                raise AuthorizationError(403)
        runtime = self.auth_service.runtime_settings
        if current.is_synthetic:
            if runtime.app_environment != "test":
                raise IdempotencyError()
        elif not policy.real_idempotency_ready:
            raise IdempotencyError()
        return current

    @staticmethod
    def _receipt(value, operation):
        try:
            receipt = ResourceReceipt.model_validate(value)
        except (ValidationError, ValueError, TypeError):
            raise IdempotencyError(422) from None
        if receipt.kind != OPERATION_KINDS[operation]:
            raise IdempotencyError(422)
        return receipt

    @staticmethod
    def _unchanged_payload(payload, expected_hash):
        try:
            current_hash = canonical_request_hash(payload)
        except CanonicalRequestError:
            raise IdempotencyError(422) from None
        if current_hash != expected_hash:
            raise IdempotencyError(409)

    @staticmethod
    def _verify(verifier, session, current, receipt):
        # Trusted local code supplies current domain authorization and locking.
        # A truthy object, missing verifier or old receipt is not an authorization.
        try:
            snapshot = ResourceReceipt.model_validate(receipt)
        except (ValidationError, ValueError, TypeError):
            raise IdempotencyError() from None
        if verifier(session, current, receipt) is not True:
            raise AuthorizationError(403)
        try:
            if ResourceReceipt.model_validate(receipt) != snapshot:
                raise IdempotencyError()
        except (ValidationError, ValueError, TypeError):
            raise IdempotencyError() from None

    @audited("administrator.action")
    def execute(self, principal, operation, key: SecretStr, payload, *, perform,
                verify_resource, session=None) -> IdempotencyResult:
        """Own-TX returns only after COMMIT; caller-TX results remain uncommitted.

        A supplied transaction must roll back any exception. Callbacks run in the
        same Session, with account locks held; they are trusted code, not a SQL or
        external-side-effect sandbox. Domain modules must validate their exact
        current source/owner/purpose references and lock resources in the verifier.
        """
        if type(operation) is not str or operation not in OPERATION_KINDS:
            raise IdempotencyError(422)
        if not callable(perform) or not callable(verify_resource):
            raise IdempotencyError()
        digest = self._key_digest(key)
        try:
            request_hash = canonical_request_hash(payload)
        except CanonicalRequestError:
            raise IdempotencyError(422) from None
        settings, policy = self._validate()
        expected_policy = settings.admin_assurance_policy
        with self._transaction(session) as active:
            current = self._authorize(active, principal, operation, expected_policy)
            row, replayed = self.store.claim(active, current.user_id, operation, digest, request_hash,
                is_synthetic=current.is_synthetic, clock=self.auth_service._now, ttl_seconds=policy.ttl_seconds)
            current = self._authorize(active, current, operation, expected_policy)
            self._unchanged_payload(payload, request_hash)
            receipt = self._receipt(self.store.receipt(row) if replayed else perform(active, current), operation)
            current = self._authorize(active, current, operation, expected_policy)
            self._unchanged_payload(payload, request_hash)
            self._verify(verify_resource, active, current, receipt)
            current = self._authorize(active, current, operation, expected_policy)
            if not replayed:
                self.store.complete(active, row, receipt, now=self.auth_service._now())
            self.auth_service.store.audit.success(active, _AUDIT_ACTIONS[operation], actor=current,
                object_type=receipt.kind, object_id=receipt.resource_id, object_version=receipt.version,
                now=self.auth_service._now())
            current = self._authorize(active, current, operation, expected_policy)
            self._verify(verify_resource, active, current, receipt)
            self._authorize(active, current, operation, expected_policy)
            self._unchanged_payload(payload, request_hash)
            self.store._validate_row(row)
            persisted_receipt = self._receipt(self.store.receipt(row), operation)
            if (row.actor_user_id != current.user_id or row.operation != operation or row.key_digest != digest
                or row.request_hash != request_hash or row.is_synthetic != current.is_synthetic
                or persisted_receipt != receipt):
                raise IdempotencyError()
            if not utc_time(row.created_at) <= self.auth_service._now() < utc_time(row.expires_at):
                raise IdempotencyError(409)
            result = IdempotencyResult(resource=persisted_receipt, replayed=replayed, expires_at=utc_time(row.expires_at))
        return result
