"""Same-transaction adult-purpose admission. No guardian or business processing."""

from contextlib import contextmanager
from datetime import timedelta
import hmac
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.authorization import Principal, Role
from ..auth.config import AuthFlowError
from ..auth.service import AuthService
from ..auth.store import database_time
from ..auth.models import AuthUser, AuthUserRole
from .config import PrivacySettings
from .errors import PrivacyError
from .models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from .schemas import AdmissionData, AgeDeclarationInput, CoreConsentInput, PrivacyNoticeData
from .policy import hash_text, notice_data
from .proofs import DeclaredAdultProof, PurposeProof
from ..audit.context import audited


class PrivacyService:
    def __init__(self, auth_service: AuthService, settings: PrivacySettings | None = None):
        self.auth_service = auth_service
        self.settings = settings if settings is not None else PrivacySettings()
        self._validate()

    def _validate(self):
        try:
            if not isinstance(self.auth_service, AuthService):
                raise ValueError
            self.auth_service._validate()
            settings = PrivacySettings.model_validate(self.settings)
            if settings.fixture_mode and self.auth_service.runtime_settings.app_environment != "test":
                raise ValueError
            return settings
        except (ValidationError, ValueError, TypeError):
            raise PrivacyError(503) from None

    @contextmanager
    def _transaction(self, supplied=None):
        self._validate()
        try:
            if supplied is None:
                with Session(self.auth_service.store.engine) as session, session.begin():
                    yield session
            else:
                if not isinstance(supplied, Session) or not supplied.in_transaction():
                    raise PrivacyError(503)
                bind = supplied.get_bind()
                if getattr(bind, "engine", bind) is not self.auth_service.store.engine:
                    raise PrivacyError(503)
                yield supplied
        except AuthFlowError:
            raise
        except Exception:
            raise PrivacyError(503) from None

    def _refresh(self, session, principal):
        self._validate()
        try:
            principal = Principal.model_validate(principal)
        except (ValidationError, ValueError, TypeError):
            raise PrivacyError(401) from None
        current, _ = self.auth_service.store.locked_principal(session, principal,
            clock=self.auth_service._now,
            production=self.auth_service.runtime_settings.app_environment == "production")
        return current

    def _rights_owner(self, session, owner):
        guard = self.auth_service.store.rights_guard
        if guard is not None:
            guard.reject_owner(session, owner)

    def _notice(self, session, principal=None):
        settings = self._validate()
        if not settings.fixture_mode:
            return None
        if principal is not None and not principal.is_synthetic:
            raise PrivacyError(503)
        row = session.scalar(select(PrivacyNoticeVersion).where(PrivacyNoticeVersion.id == settings.notice_id)
            .with_for_update().execution_options(populate_existing=True))
        if (row is None or not row.is_synthetic or row.review_status != "test_reviewed"
            or row.controller_reference != settings.controller_reference or row.policy_version != settings.policy_version
            or not row.version or not row.text or database_time(row.reviewed_at) > self.auth_service._now()
            or not hmac.compare_digest(hash_text(row.text), row.text_sha256)):
            raise PrivacyError(503)
        return row

    @staticmethod
    def _latest(session, principal):
        return session.scalar(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == principal.user_id)
            .order_by(PrivacyAdmissionRecord.revision.desc()).limit(1).with_for_update()
            .execution_options(populate_existing=True))

    def current_notice(self) -> PrivacyNoticeData:
        settings = self._validate()
        if not settings.fixture_mode:
            return notice_data(settings)
        with self._transaction() as session:
            return notice_data(settings, notice=self._notice(session))

    def _result(self, principal, row, notice) -> AdmissionData:
        settings, now = self._validate(), self.auth_service._now()
        status = row.consent_status if row is not None else "not_confirmed"
        reason = "allowed"
        if notice is None:
            reason = "processing_disabled"
        elif row is None or row.age_band is None:
            reason = "age_missing"
        elif row.age_band != "18_plus" or row.age_assurance != "declared":
            raise PrivacyError(503)
        elif not database_time(row.declared_at) <= now < database_time(row.declaration_expires_at):
            reason = "age_expired"
        elif row.policy_version != settings.policy_version:
            reason = "policy_changed"
        elif row.declaration_notice_id != notice.id:
            reason = "notice_changed"
        elif status == "not_confirmed":
            reason = "consent_missing"
        elif status == "withdrawn":
            reason = "consent_withdrawn"
        elif status == "invalidated":
            reason = "consent_invalidated"
        elif status != "active" or row.consent_id is None:
            raise PrivacyError(503)
        elif row.consent_notice_id != notice.id:
            reason = "notice_changed"
        elif Role.student not in principal.roles:
            reason = "role_missing"
        return AdmissionData(user_id=principal.user_id, revision=row.revision if row is not None else 0,
            age_band=row.age_band if row is not None else None, age_assurance=row.age_assurance if row is not None else "unknown",
            declared_at=database_time(row.declared_at) if row is not None and row.declared_at is not None else None,
            declaration_expires_at=database_time(row.declaration_expires_at) if row is not None and row.declaration_expires_at is not None else None,
            policy_version=settings.policy_version, notice_id=notice.id if notice is not None else None,
            notice_version=notice.version if notice is not None else None,
            consent_id=row.consent_id if row is not None else None, consent_status=status,
            core_consultation_allowed=reason == "allowed", reason=reason, readiness=notice is not None,
            is_synthetic=principal.is_synthetic, private_business_available=False)

    def get_admission(self, principal: Principal) -> AdmissionData:
        with self._transaction() as session:
            current = self._refresh(session, principal)
            notice, row = self._notice(session, current), self._latest(session, current)
            result = self._result(self._refresh(session, current), row, notice)
            guard = self.auth_service.store.rights_guard
            if guard is not None and current.user_id in guard.blocked_owners(session):
                result = AdmissionData.model_validate({**result.model_dump(), "core_consultation_allowed": False,
                    "reason": "processing_disabled"})
            return result

    @staticmethod
    def _revision(row, expected):
        if expected != (row.revision if row is not None else 0):
            raise PrivacyError(409)

    def _append(self, session, principal, previous, event, **updates):
        values = dict(age_band=None, age_assurance="unknown", declared_at=None, declaration_expires_at=None,
            declaration_notice_id=None, consent_id=None, consent_status="not_confirmed",
            consent_notice_id=None, consent_confirmed_at=None, consent_withdrawn_at=None)
        if previous is not None:
            values.update({name: getattr(previous, name) for name in values})
        values.update(updates)
        row = PrivacyAdmissionRecord(id=uuid4(), user_id=principal.user_id,
            revision=(previous.revision if previous is not None else 0) + 1, event_type=event,
            recorded_at=self.auth_service._now(), policy_version=self.settings.policy_version, **values)
        if event == "consent_confirmed":
            row.consent_id = row.id
        session.add(row)
        session.flush()
        actions = {"adult_declared": "privacy.adult.declare", "admission_invalidated": "privacy.admission.invalidate",
                   "consent_confirmed": "privacy.core.confirm", "consent_withdrawn": "privacy.core.withdraw"}
        self.auth_service.store.audit.success(session, actions[event], actor=principal,
            object_type="consent" if event.startswith("consent_") else "admission",
            object_id=row.id, object_version=row.revision, now=self.auth_service._now())
        self._refresh(session, principal)
        return row

    @audited("privacy.adult.declare")
    def declare_age(self, principal: Principal, request: AgeDeclarationInput) -> AdmissionData:
        try:
            request = AgeDeclarationInput.model_validate(request)
        except (ValidationError, ValueError, TypeError):
            raise PrivacyError(403) from None
        refused = False
        with self._transaction() as session:
            current = self._refresh(session, principal)
            previous = self._latest(session, current)
            current = self._refresh(session, current)
            if request.age_band != "18_plus":
                # A rejection never records its child/unknown band. A pre-existing
                # positive declaration is invalidated before returning refusal,
                # even from a stale UI or when the current notice is unavailable.
                # Removing permission cannot be blocked by a positive-write
                # revision/notice proof. No new declaration is accepted here.
                if previous is not None and previous.age_band is not None:
                    self._append(session, current, previous, "admission_invalidated", age_band=None,
                        age_assurance="unknown", declared_at=None, declaration_expires_at=None,
                        declaration_notice_id=None, consent_status="invalidated" if previous.consent_id else "not_confirmed",
                        consent_withdrawn_at=None)
                self._refresh(session, current)
                refused = True
            else:
                self._rights_owner(session, current.user_id)
                notice = self._notice(session, current)
                if notice is None:
                    raise PrivacyError(503)
                if request.notice_id != notice.id:
                    raise PrivacyError(409)
                self._revision(previous, request.expected_revision)
                current = self._refresh(session, current)
                now = self.auth_service._now()
                row = self._append(session, current, previous, "adult_declared", age_band="18_plus",
                    age_assurance="declared", declared_at=now,
                    declaration_expires_at=now + timedelta(seconds=self.settings.declaration_validity_seconds),
                    declaration_notice_id=notice.id,
                    consent_status="invalidated" if previous is not None and previous.consent_id else "not_confirmed",
                    consent_withdrawn_at=None)
                result = self._result(self._refresh(session, current), row, notice)
        if refused:
            raise PrivacyError(403)
        return result

    @audited("privacy.core.confirm")
    def confirm_core(self, principal: Principal, request: CoreConsentInput) -> AdmissionData:
        try:
            request = CoreConsentInput.model_validate(request)
        except (ValidationError, ValueError, TypeError):
            raise PrivacyError(403) from None
        with self._transaction() as session:
            current = self._refresh(session, principal)
            self._rights_owner(session, current.user_id)
            notice, previous = self._notice(session, current), self._latest(session, current)
            if notice is None:
                raise PrivacyError(503)
            if request.notice_id != notice.id:
                raise PrivacyError(409)
            self._revision(previous, request.expected_revision)
            current = self._refresh(session, current)
            now = self.auth_service._now()
            # Confirm the current declaration independently of any superseded
            # consent. A new notice needs a new declaration first, after which
            # its explicit consent can replace an old invalidated reference.
            if (previous is None or previous.age_band != "18_plus" or previous.age_assurance != "declared"
                or previous.policy_version != self.settings.policy_version
                or previous.declaration_notice_id != notice.id
                or previous.declared_at is None or previous.declaration_expires_at is None
                or not database_time(previous.declared_at) <= now < database_time(previous.declaration_expires_at)):
                raise PrivacyError(403)
            row = self._append(session, current, previous, "consent_confirmed", consent_status="active",
                consent_notice_id=notice.id, consent_confirmed_at=self.auth_service._now(), consent_withdrawn_at=None)
            return self._result(self._refresh(session, current), row, notice)

    @audited("privacy.core.withdraw")
    def withdraw_core(self, principal: Principal, consent_id: UUID) -> AdmissionData:
        if not isinstance(consent_id, UUID):
            raise PrivacyError(404)
        with self._transaction() as session:
            current = self._refresh(session, principal)
            target = session.scalar(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.id == consent_id,
                PrivacyAdmissionRecord.user_id == current.user_id,
                PrivacyAdmissionRecord.event_type == "consent_confirmed")
                .with_for_update().execution_options(populate_existing=True))
            if target is None:
                raise PrivacyError(404)
            previous = self._latest(session, current)
            current = self._refresh(session, current)
            if previous.consent_id == consent_id and previous.consent_status == "active":
                guard = self.auth_service.store.rights_guard
                if guard is not None:
                    guard.record(session, "core_withdrawn", current.user_id, resource_id=consent_id)
                previous = self._append(session, current, previous, "consent_withdrawn",
                    consent_status="withdrawn", consent_withdrawn_at=self.auth_service._now())
            try:
                notice = self._notice(session, current)
            except PrivacyError as error:
                if error.status_code != 503:
                    raise
                # Withdraw never depends on a current notice being publishable.
                # Damaged/missing policy leaves processing closed, while the
                # owner's withdrawal still commits with its original reference.
                notice = None
            return self._result(self._refresh(session, current), previous, notice)

    @audited("authorization.owned.check")
    def require_purpose(self, session: Session, principal: Principal, purpose: str) -> AdmissionData:
        """Combine with object authorization inside its current SQL transaction.

        Caller supplies the current authenticated actor, never an object owner or
        cached permission. This checks at the operation boundary; it is not a
        worker, grant, deletion workflow or a transaction around external I/O.
        """
        if purpose != "core_consultation":
            raise PrivacyError(403)
        with self._transaction(session) as same_session:
            current = self._refresh(same_session, principal)
            self._rights_owner(same_session, current.user_id)
            notice, row = self._notice(same_session, current), self._latest(same_session, current)
            result = self._result(self._refresh(same_session, current), row, notice)
            if not result.core_consultation_allowed:
                raise PrivacyError(503 if not result.readiness else 403)
            return result

    def _subject_adult(self, session, user_id):
        """Sharing's derived subject, only after all sorted account locks.

        The marker is a trusted same-transaction composition boundary, not a
        permission cache or a defence against malicious local Python code.
        No alternate actor Principal is constructed or bound.
        """
        marker = session.info.get("sharing_accounts_locked")
        if (not isinstance(user_id, UUID) or marker is None or marker[0] is not session.get_transaction()
            or user_id not in marker[1]):
            raise PrivacyError(403)
        user = session.get(AuthUser, user_id, populate_existing=True)
        self._rights_owner(session, user_id)
        if user is None or user.status != "active" or not user.is_synthetic:
            raise PrivacyError(403)
        notice = self._notice(session)
        if notice is None:
            raise PrivacyError(503)
        row = session.scalar(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == user_id)
            .order_by(PrivacyAdmissionRecord.revision.desc()).limit(1).with_for_update()
            .execution_options(populate_existing=True))
        now = self.auth_service._now()
        if (row is None or row.age_band != "18_plus" or row.age_assurance != "declared"
            or row.policy_version != self.settings.policy_version or row.declaration_notice_id != notice.id
            or row.declared_at is None or row.declaration_expires_at is None
            or not database_time(row.declared_at) <= now < database_time(row.declaration_expires_at)):
            raise PrivacyError(403)
        declaration = session.scalar(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == user_id,
            PrivacyAdmissionRecord.event_type == "adult_declared", PrivacyAdmissionRecord.revision <= row.revision)
            .order_by(PrivacyAdmissionRecord.revision.desc()).limit(1).with_for_update()
            .execution_options(populate_existing=True))
        if (declaration is None or declaration.age_band != "18_plus"
            or declaration.declaration_notice_id != row.declaration_notice_id
            or declaration.policy_version != row.policy_version or declaration.declared_at != row.declared_at
            or declaration.declaration_expires_at != row.declaration_expires_at):
            raise PrivacyError(403)
        proof = DeclaredAdultProof(user_id=user_id, declaration_id=declaration.id, notice_id=notice.id,
            policy_version=row.policy_version, expires_at=database_time(row.declaration_expires_at), is_synthetic=user.is_synthetic)
        if not self.auth_service._now() < proof.expires_at:
            raise PrivacyError(403)
        return proof, row, notice

    def declared_adult_subject(self, session, user_id) -> DeclaredAdultProof:
        with self._transaction(session) as same_session:
            return self._subject_adult(same_session, user_id)[0]

    def require_declared_adult(self, session, principal) -> DeclaredAdultProof:
        with self._transaction(session) as same_session:
            current = self._refresh(same_session, principal)
            # Current-actor-only callers may compose without a foreign owner.
            marker = same_session.info.get("sharing_accounts_locked")
            if marker is None or marker[0] is not same_session.get_transaction():
                same_session.info["sharing_accounts_locked"] = (same_session.get_transaction(), frozenset({current.user_id}))
            proof = self._subject_adult(same_session, current.user_id)[0]
            self._refresh(same_session, current)
            if not self.auth_service._now() < proof.expires_at:
                raise PrivacyError(403)
            return proof

    def require_owner_purpose(self, session, owner_user_id) -> PurposeProof:
        with self._transaction(session) as same_session:
            proof, row, notice = self._subject_adult(same_session, owner_user_id)
            roles = same_session.scalars(select(AuthUserRole).where(AuthUserRole.user_id == owner_user_id)
                .order_by(AuthUserRole.role).with_for_update().execution_options(populate_existing=True)).all()
            if (row.consent_status != "active" or row.consent_id is None or row.consent_notice_id != notice.id):
                raise PrivacyError(403)
            original = same_session.scalar(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.id == row.consent_id,
                PrivacyAdmissionRecord.user_id == owner_user_id, PrivacyAdmissionRecord.event_type == "consent_confirmed")
                .with_for_update().execution_options(populate_existing=True))
            if (original is None or original.consent_id != original.id or original.consent_status != "active"
                or original.consent_notice_id != notice.id or original.policy_version != self.settings.policy_version
                or not self.auth_service._now() < proof.expires_at):
                raise PrivacyError(403)
            now = self.auth_service._now()
            student = next((role for role in roles if role.role == "student" and role.revoked_at is None
                and database_time(role.granted_at) <= now
                and (role.expires_at is None or now < database_time(role.expires_at))), None)
            if student is None or not now < proof.expires_at:
                raise PrivacyError(403)
            values = proof.model_dump()
            if student.expires_at is not None:
                values["expires_at"] = min(proof.expires_at, database_time(student.expires_at))
            return PurposeProof(**values, consent_id=row.consent_id)
