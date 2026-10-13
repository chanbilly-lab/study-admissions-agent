"""Bounded owner rights and dedicated accepted-deletion authority.

No background thread, loop, startup migration or arbitrary handler is created.
Call claim/run explicitly from a supervised trusted worker.
"""
from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...audit.retention import expires_after_months
from ...auth.authorization import Principal
from ...auth.config import AuthFlowError
from ...auth.service import AuthService, ExecutionReference
from ...auth.models import AuthUser
from ...auth.store import database_time
from ...storage.protocol import StorageBackend, StorageNamespace
from .guard import RightsGuard
from .ledger import canonical
from .models import BackupRegistration, RightsRequest, RightsAttempt
from .resources import capture, erase_files, erase_rows, export_bytes, validate_scope
from .schemas import (ExportContent, Lease, OwnerConfirmation, RightsContext, RightsError,
    RightsPolicy, RightsRequestData, utc)
from .store import RightsStore


def request_data(row):
    return RightsRequestData(request_id=row.id, kind=row.kind, status=row.status, reason=row.reason,
        attempts=row.attempts, accepted_at=database_time(row.accepted_at),
        online_cleanup_due_at=database_time(row.due_at) if row.due_at is not None else None,
        completed_at=database_time(row.completed_at) if row.completed_at is not None else None,
        artifact_expires_at=database_time(row.artifact_expires_at) if row.artifact_expires_at is not None else None,
        online_cleanup_complete=row.kind == "deletion" and row.status == "completed",
        retained_responsibility_until=database_time(row.retained_until))


class RightsService:
    def __init__(self, auth_service, store, guard, policy=RightsPolicy()):
        if not isinstance(auth_service, AuthService) or type(store) is not RightsStore or type(guard) is not RightsGuard:
            raise RightsError()
        self.auth_service, self.store, self.guard = auth_service, store, guard
        self.policy = RightsPolicy.model_validate(policy)
        self._initial = (auth_service, auth_service.store, auth_service.clock, auth_service.runtime_settings,
            store, guard, guard.backend, self.policy)
        self._validate()

    def _validate(self):
        try:
            auth, auth_store, clock, runtime, store, guard, backend, policy = self._initial
            if (self.auth_service is not auth or auth.store is not auth_store or auth.clock is not clock
                or auth.runtime_settings != runtime or self.store is not store or self.guard is not guard
                or guard.backend is not backend or guard.clock is not clock
                or RightsPolicy.model_validate(self.policy) != policy or store.engine is not guard.engine
                or auth_store.engine is not store.engine or auth_store.rights_guard is not guard):
                raise ValueError()
            auth._validate()
            guard.validate_configuration()
            return policy
        except Exception:
            raise RightsError() from None

    def _ready(self):
        policy = self._validate()
        if not policy.enabled or not policy.allow_test_rights or self.auth_service.runtime_settings.app_environment != "test":
            raise RightsError()
        return policy

    def _current(self, session, principal):
        self._ready()
        try:
            principal = Principal.model_validate(principal)
            current, _ = self.auth_service.store.locked_principal(session, principal, clock=self.auth_service._now, production=False)
            if not current.is_synthetic:
                raise ValueError()
            return current
        except AuthFlowError:
            raise
        except Exception as error:
            status = getattr(error, "status_code", None)
            raise RightsError(status if status in {401, 403, 404} else 503) from None

    def preflight(self, principal):
        self._ready()  # Deny before any connection if closed.
        with Session(self.store.engine) as session, session.begin():
            self._current(session, principal)

    def context(self, principal):
        policy = self._validate()
        if not policy.enabled:
            return RightsContext(enabled=False, reason="RIGHTS_DISABLED")
        self._ready()
        with Session(self.store.engine) as session, session.begin():
            current = self._current(session, principal)
            blocked = current.user_id in self.guard.blocked_owners(session)
            self._current(session, current)
            return RightsContext(enabled=True, reason="OWNER_DELETED" if blocked else "OK",
                deletion_accepted=blocked, max_export_bytes=policy.max_export_bytes)

    def create(self, principal, kind, confirmation):
        self._ready()
        try:
            confirmation = OwnerConfirmation.model_validate(confirmation)
            if kind not in {"export", "deletion"}:
                raise ValueError()
        except Exception:
            raise RightsError(422, "VALIDATION_ERROR") from None
        with Session(self.store.engine) as session, session.begin():
            current = self._current(session, principal)
            now = self.auth_service._now()
            key = sha256(canonical([kind, str(current.user_id)])).hexdigest()
            if kind == "deletion":
                previous = session.scalar(select(RightsRequest).where(RightsRequest.natural_key == key).with_for_update())
                if previous is not None:
                    self._current(session, current)
                    return request_data(previous)
            self.guard.reject_owner(session, current.user_id)
            scope = capture(session, current.user_id, max_rows=self.policy.max_rows)
            identifier = uuid4()
            proof = self.guard.ensure_business(session)[0]
            if kind == "deletion":
                _, proof = self.guard.record(session, "owner_deleted", current.user_id, resource_id=identifier)
            else:
                # Exact server capture + session permits retrying this request;
                # another explicitly confirmed export creates a new request.
                key = sha256(canonical([kind, str(current.user_id), str(identifier)])).hexdigest()
            audit = self.auth_service.store.audit.success(session, "deletion.accept" if kind == "deletion" else "export.create",
                actor=current, object_type="deletion_job" if kind == "deletion" else "export", object_id=identifier, now=now)
            row = RightsRequest(id=identifier, owner_user_id=current.user_id,
                session_id=current.session_id if kind == "export" else None, is_synthetic=True,
                kind=kind, natural_key=key, scope=scope, scope_sha256=sha256(canonical(scope)).hexdigest(),
                ledger_sequence=proof.sequence, status="queued", reason="OK", attempts=0, generation=0,
                accepted_at=now, available_at=now, due_at=now + timedelta(days=30) if kind == "deletion" else None,
                retained_until=expires_after_months(now), completed_at=None, audit_event_id=audit.id)
            session.add(row)
            session.flush()
            self._current(session, current)
            return request_data(row)

    def get(self, principal, identifier, kind):
        self._ready()
        if type(identifier) is not UUID or kind not in {"export", "deletion"}:
            raise RightsError(404, "NOT_FOUND")
        with Session(self.store.engine) as session, session.begin():
            current = self._current(session, principal)
            row = session.scalar(select(RightsRequest).where(RightsRequest.id == identifier,
                RightsRequest.owner_user_id == current.user_id, RightsRequest.kind == kind).with_for_update())
            if row is None:
                raise RightsError(404, "NOT_FOUND")
            if self.auth_service._now() >= database_time(row.retained_until):
                raise RightsError(404, "NOT_FOUND")
            self._current(session, current)
            return request_data(row)

    def content(self, principal, identifier):
        self._ready()
        if type(identifier) is not UUID:
            raise RightsError(404, "NOT_FOUND")
        with Session(self.store.engine) as session, session.begin():
            current = self._current(session, principal)
            self.guard.reject_owner(session, current.user_id)
            row = session.scalar(select(RightsRequest).where(RightsRequest.id == identifier,
                RightsRequest.owner_user_id == current.user_id, RightsRequest.kind == "export").with_for_update())
            now = self.auth_service._now()
            if row is None:
                raise RightsError(404, "NOT_FOUND")
            if row.status != "completed" or row.artifact_id is None or now >= database_time(row.artifact_expires_at):
                raise RightsError(409, "CONFLICT")
            data = self.guard.backend.read(StorageNamespace.student_private, row.artifact_id,
                expected_size=row.artifact_size, expected_sha256=row.artifact_sha256)
            self._current(session, current)
            self.guard.reject_owner(session, current.user_id)
            if self.auth_service._now() >= database_time(row.artifact_expires_at):
                raise RightsError(409, "CONFLICT")
            return ExportContent(request_id=row.id, content_json=data.decode("utf-8"), size_bytes=len(data),
                sha256=row.artifact_sha256, expires_at=database_time(row.artifact_expires_at))

    def claim(self, worker_id):
        self._ready()
        if type(worker_id) is not UUID:
            raise RightsError()
        with Session(self.store.engine) as session, session.begin():
            self.guard.ensure_business(session)
            now = self.auth_service._now()
            exhausted = tuple(session.scalars(select(RightsRequest).where(RightsRequest.status == "running",
                RightsRequest.lease_until <= now, RightsRequest.attempts >= self.policy.max_attempts)
                .order_by(RightsRequest.id).limit(20).with_for_update(skip_locked=True)).all())
            for expired in exhausted:
                expired.status, expired.reason = "failed", "ATTEMPTS_EXHAUSTED"
                expired.worker_id = expired.lease_token = expired.lease_until = None
                session.add(RightsAttempt(request_id=expired.id, generation=expired.generation, outcome="failed",
                    reason="ATTEMPTS_EXHAUSTED", finished_at=now))
            session.flush()
            row = session.scalar(select(RightsRequest).where(
                or_((RightsRequest.status == "queued") & (RightsRequest.available_at <= now),
                    (RightsRequest.status == "running") & (RightsRequest.lease_until <= now)),
                RightsRequest.attempts < self.policy.max_attempts).order_by(RightsRequest.accepted_at, RightsRequest.id)
                .limit(1).with_for_update(skip_locked=True))
            if row is None:
                return None
            row.status, row.reason = "running", "OK"
            row.attempts, row.generation = row.attempts + 1, row.generation + 1
            row.worker_id, row.lease_token = worker_id, uuid4()
            row.lease_until = now + timedelta(seconds=self.policy.lease_seconds)
            session.flush()
            return Lease(request_id=row.id, kind=row.kind, generation=row.generation,
                worker_id=worker_id, token=row.lease_token, until=database_time(row.lease_until))

    def _lease(self, row, lease):
        if (row is None or row.kind != lease.kind or row.status != "running" or row.generation != lease.generation
            or row.worker_id != lease.worker_id or row.lease_token != lease.token
            or database_time(row.lease_until) != lease.until or self.auth_service._now() >= lease.until):
            raise RightsError(409, "CONFLICT")

    def run(self, lease):
        self._ready()
        try:
            lease = Lease.model_validate(lease)
        except Exception:
            raise RightsError() from None
        artifact = None
        try:
            with Session(self.store.engine) as session, session.begin():
                self.guard.ensure_business(session)
                # Owner lock precedes job lock, matching interactive acceptance.
                owner = session.scalar(select(RightsRequest.owner_user_id).where(RightsRequest.id == lease.request_id))
                user = session.get(AuthUser, owner, with_for_update=True) if owner is not None else None
                row = session.get(RightsRequest, lease.request_id, with_for_update=True, populate_existing=True)
                self._lease(row, lease)
                if user is None or not user.is_synthetic:
                    raise RightsError()
                if row.kind == "export":
                    self.guard.reject_owner(session, owner)
                    current, _ = self.auth_service.store.locked_principal(session,
                        ExecutionReference(user_id=owner, session_id=row.session_id),
                        clock=self.auth_service._now, production=False)
                    if sha256(canonical(row.scope)).hexdigest() != row.scope_sha256:
                        raise RightsError()
                    data = export_bytes(session, owner, row.scope, self.guard.backend, limit=self.policy.max_export_bytes)
                    artifact = uuid4()
                    written = self.guard.backend.write(StorageNamespace.student_private, artifact, data)
                    if written.size_bytes != len(data) or written.sha256 != sha256(data).hexdigest():
                        raise RightsError()
                    self._current(session, current)
                    self.guard.reject_owner(session, owner)
                    row.artifact_id, row.artifact_sha256, row.artifact_size = artifact, written.sha256, len(data)
                    row.artifact_expires_at = min(self.auth_service._now() + timedelta(seconds=self.policy.export_ttl_seconds),
                        database_time(row.accepted_at) + timedelta(days=1))
                    if self.auth_service._now() >= database_time(row.artifact_expires_at):
                        raise RightsError(409, "CONFLICT")
                else:
                    proof, events = self.guard.ensure_business(session)
                    if not any(event.kind == "owner_deleted" and event.owner_user_id == owner
                        and event.resource_id == row.id and index == row.ledger_sequence
                        for index, event in enumerate(events, 1)):
                        raise RightsError()
                    scope = validate_scope(session, owner, row.scope, row.scope_sha256,
                        max_rows=self.policy.max_rows, allow_subset=True)
                    erase_files(self.guard.backend, scope)
                    self._lease(row, lease)
                    self.guard.ensure_business(session)
                    erase_rows(session, owner, scope)
                self._lease(row, lease)
                self._ready()
                self.guard.ensure_business(session)
                completed = self.auth_service._now()
                self.auth_service.store.audit.success(session, "administrator.action", actor_kind="system",
                    object_type="deletion_job" if row.kind == "deletion" else "export", object_id=row.id, now=completed)
                self._lease(row, lease)
                if row.kind == "deletion":
                    row.scope, row.scope_sha256 = {}, sha256(canonical({})).hexdigest()
                row.status, row.reason, row.completed_at = "completed", "OK", completed
                row.worker_id = row.lease_token = row.lease_until = None
                session.add(RightsAttempt(request_id=row.id, generation=row.generation, outcome="completed", reason="OK", finished_at=completed))
                session.flush()
                result = request_data(row)
            return result
        except Exception as error:
            if artifact is not None:
                try:
                    self.guard.backend.delete(StorageNamespace.student_private, artifact)
                except Exception:
                    pass  # Unregistered orphan has no download capability.
            return self._failure(lease, error)

    def _failure(self, lease, error):
        self._ready()
        with Session(self.store.engine) as session, session.begin():
            self.guard.ensure_business(session)
            row = session.get(RightsRequest, lease.request_id, with_for_update=True, populate_existing=True)
            self._lease(row, lease)
            code, status = getattr(error, "code", None), getattr(error, "status_code", None)
            if row.kind == "export" and status in {401, 403}:
                outcome, reason = "cancelled", "AUTHORITY_REVOKED"
            elif code == "EXPORT_LIMIT":
                outcome, reason = "failed", "EXPORT_LIMIT"
            elif row.attempts >= self.policy.max_attempts:
                outcome, reason = "failed", "ATTEMPTS_EXHAUSTED"
            else:
                outcome, reason = "queued", "RETRYABLE_FAILURE"
            row.status, row.reason = outcome, reason
            row.available_at = self.auth_service._now() + timedelta(seconds=self.policy.retry_seconds)
            row.worker_id = row.lease_token = row.lease_until = None
            session.add(RightsAttempt(request_id=row.id, generation=row.generation, outcome=outcome,
                reason=reason, finished_at=self.auth_service._now()))
            session.flush()
            return request_data(row)

    def retry_deletion(self, request_id):
        """Trusted bounded maintenance after a terminal failure, never new authority."""
        self._ready()
        if type(request_id) is not UUID:
            raise RightsError()
        with Session(self.store.engine) as session, session.begin():
            self.guard.ensure_business(session)
            row = session.get(RightsRequest, request_id, with_for_update=True)
            if row is None or row.kind != "deletion" or row.status != "failed" or row.attempts >= 5:
                raise RightsError(409, "CONFLICT")
            # A subsequent explicit policy can allow the remaining finite attempts.
            if row.attempts >= self.policy.max_attempts:
                raise RightsError(409, "CONFLICT")
            row.status, row.reason, row.available_at = "queued", "OK", self.auth_service._now()

    def register_backup(self, digest, *, captured_at, expires_at):
        self._ready()
        import re
        captured_at, expires_at = utc(captured_at), utc(expires_at)
        if (type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not captured_at < expires_at <= captured_at + timedelta(days=35) or captured_at > self.auth_service._now()):
            raise RightsError(422, "VALIDATION_ERROR")
        with Session(self.store.engine) as session, session.begin():
            proof = self.guard.ensure_business(session)[0]
            row = BackupRegistration(id=uuid4(), content_sha256=digest, captured_at=captured_at,
                expires_at=expires_at, ledger_id=proof.ledger_id, ledger_sequence=proof.sequence)
            session.add(row)
            session.flush()
            return row.id
