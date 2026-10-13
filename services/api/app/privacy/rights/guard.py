"""Trusted current-ledger barrier and explicit maintenance replay."""
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from ...audit.retention import expires_after_months
from ...auth.config import AuthFlowError
from ...auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from ...auth.grants.models import AccessGrant
from ...auth.store import database_time
from ...privacy.models import PrivacyAdmissionRecord
from ...storage.models import StorageObject
from ...storage.protocol import StorageNamespace
from .ledger import ExternalLedger, canonical
from .models import RightsWatermark, RightsRequest, RightsBase, ErasedImpactCount
from .resources import capture, erase_files, erase_rows
from .schemas import LedgerEventData, LedgerProof, RightsError, utc
from hashlib import sha256


class RightsGuard:
    def __init__(self, engine, ledger: ExternalLedger, backend, *, clock):
        from ...storage.protocol import StorageBackend
        if engine.dialect.name != "postgresql" or type(ledger) is not ExternalLedger or not isinstance(backend, StorageBackend) or not callable(clock):
            raise RightsError()
        # A separate connection alone is insufficient: business dumps must not
        # include the ledger. Separate databases or explicit schema allowlists.
        if engine is ledger.engine or engine.url == ledger.engine.url and engine.pool._creator is ledger.engine.pool._creator:
            raise RightsError()
        self.engine, self.ledger, self.backend, self.clock = engine, ledger, backend, clock
        self._initial = (engine, ledger, backend, clock)

    def validate_configuration(self):
        if (self.engine, self.ledger, self.backend, self.clock) != self._initial or any(
            current is not original for current, original in zip((self.engine, self.ledger, self.backend, self.clock), self._initial)):
            raise RightsError()
        self.ledger.validate_configuration()

    def _session(self, session):
        self.validate_configuration()
        if not isinstance(session, Session) or not session.in_transaction() or not session.get_transaction().is_active:
            raise RightsError()
        for mapper in (None, *RightsBase.registry.mappers, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                       AccessGrant, PrivacyAdmissionRecord, StorageObject):
            bind = session.get_bind(mapper=mapper)
            if getattr(bind, "engine", bind) is not self.engine:
                raise RightsError()
        business = (self.engine.url.host, self.engine.url.port, self.engine.url.database,
            session.scalar(text("SELECT current_schema()")))
        if business == self.ledger.location():
            raise RightsError()  # A different pool pointing at the same schema is not independence.
        if session.execute(text("SELECT version_num FROM rights_alembic_version")).scalars().all() != ["0001_rights_t40"]:
            raise RightsError()

    @staticmethod
    def _proof(row):
        if row is None:
            raise RightsError()
        return LedgerProof(ledger_id=row.ledger_id, sequence=row.sequence, chain_sha256=row.chain_sha256)

    def ensure_business(self, session):
        self._session(session)
        proof, events = self.ledger.snapshot()
        marker = session.get(RightsWatermark, 1, populate_existing=True)
        if self._proof(marker) != proof:
            raise RightsError()
        return proof, events

    def ensure_ready(self):
        try:
            with Session(self.engine) as session, session.begin():
                return self.ensure_business(session)[0]
        except Exception:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def auth_check(self, session):
        try:
            self.ensure_business(session)
        except Exception:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def reject_owner(self, session, owner):
        _, events = self.ensure_business(session)
        if any(event.kind == "owner_deleted" and event.owner_user_id == owner for event in events):
            raise AuthFlowError(403, "FORBIDDEN")

    def blocked_owners(self, session):
        return frozenset(event.owner_user_id for event in self.ensure_business(session)[1] if event.kind == "owner_deleted")

    def erased_counts(self, session, event_id):
        self.ensure_business(session)
        value = session.get(ErasedImpactCount, event_id, populate_existing=True)
        return (value.assessment_count, value.plan_count) if value is not None else (0, 0)

    def record(self, session, kind, owner, *, resource_id=None, role=None, role_granted_at=None, event_id=None):
        self.ensure_business(session)
        now = utc(self.clock())
        event = LedgerEventData(event_id=event_id or uuid4(), kind=kind, owner_user_id=owner,
            resource_id=resource_id, role=role, role_granted_at=role_granted_at,
            recorded_at=now, expires_at=expires_after_months(now))
        proof = self.ledger.append(event)
        marker = session.get(RightsWatermark, 1)
        marker.sequence, marker.chain_sha256 = proof.sequence, proof.chain_sha256
        session.flush()
        return event, proof

    def bootstrap_business(self):
        """Explicit fresh-schema initialization, never startup or restore fallback."""
        proof, events = self.ledger.snapshot()
        if proof.sequence != 0 or events:
            raise RightsError()
        with Session(self.engine) as session, session.begin():
            self._session(session)
            if session.get(RightsWatermark, 1) is not None:
                raise RightsError()
            session.add(RightsWatermark(id=1, **proof.model_dump()))

    def replay(self):
        """Trusted maintenance; no actor input. Traffic remains closed until commit.

        File effects are idempotent and may precede rollback. Neither a file
        failure nor a failed SQL transaction advances the business watermark.
        """
        self.validate_configuration()
        proof, events = self.ledger.snapshot()
        with Session(self.engine) as session, session.begin():
            self._session(session)
            marker = session.get(RightsWatermark, 1, with_for_update=True, populate_existing=True)
            old = self._proof(marker)
            if old.ledger_id != proof.ledger_id or old.sequence > proof.sequence:
                raise RightsError()
            expected = "0" * 64 if old.sequence == 0 else self._chain_at(old.sequence, events)
            if old.chain_sha256 != expected:
                raise RightsError()
            for event in events[old.sequence:]:
                user = session.get(AuthUser, event.owner_user_id, with_for_update=True)
                if user is None:
                    # An old backup may predate an account, but cannot revive it.
                    continue
                if not user.is_synthetic:
                    raise RightsError()
                self._apply(session, event)
            if self.ledger.snapshot()[0] != proof:
                raise RightsError()
            marker.sequence, marker.chain_sha256 = proof.sequence, proof.chain_sha256
            session.flush()
        self.ensure_ready()
        return proof

    @staticmethod
    def _chain_at(sequence, events):
        from .ledger import chain_hash
        previous = "0" * 64
        for index, event in enumerate(events[:sequence], 1):
            previous = chain_hash(previous, index, event.model_dump(mode="json"))
        return previous

    def _apply(self, session, event):
        at, owner, identifier = event.recorded_at, event.owner_user_id, event.resource_id
        if event.kind == "session_revoked":
            row = session.get(AuthSession, identifier, with_for_update=True)
            if row is not None:
                if row.user_id != owner or database_time(row.created_at) > at:
                    raise RightsError()
                if row.revoked_at is None:
                    row.revoked_at = at
                    row.csrf_digest = row.csrf_encrypted_token = None
        elif event.kind == "role_revoked":
            row = session.get(AuthUserRole, (owner, event.role), with_for_update=True)
            if row is not None and database_time(row.granted_at) == event.role_granted_at and row.revoked_at is None:
                row.revoked_at = at
        elif event.kind == "grant_revoked":
            row = session.get(AccessGrant, identifier, with_for_update=True)
            if row is not None:
                if row.owner_user_id != owner or database_time(row.created_at) > at:
                    raise RightsError()
                if row.state != "revoked":
                    row.state, row.revoked_at, row.version = "revoked", at, row.version + 1
        elif event.kind == "core_withdrawn":
            row = session.scalar(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == owner)
                .order_by(PrivacyAdmissionRecord.revision.desc()).limit(1).with_for_update())
            if row is not None and row.consent_id == identifier and row.consent_status == "active":
                values = {column.name: getattr(row, column.name) for column in row.__table__.columns}
                values.update(id=uuid4(), revision=row.revision + 1, event_type="consent_withdrawn", recorded_at=at,
                    consent_status="withdrawn", consent_withdrawn_at=at)
                session.add(PrivacyAdmissionRecord(**values))
        elif event.kind == "file_deleted":
            row = session.get(StorageObject, identifier, with_for_update=True)
            if row is not None:
                if row.owner_user_id != owner or row.namespace != "student_private" or database_time(row.created_at) > at:
                    raise RightsError()
                erase_files(self.backend, {"files": [{"id": str(row.id), "size_bytes": row.size_bytes, "sha256": row.sha256}], "artifacts": []})
                row.status = "deleted"
                session.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == identifier,
                    AuthOwnedResource.owner_user_id == owner).values(status="deleted"))
        elif event.kind == "owner_deleted":
            scope = capture(session, owner, max_rows=5000, cutoff=at)
            row = session.get(RightsRequest, identifier, with_for_update=True)
            if row is not None and (row.owner_user_id != owner or row.kind != "deletion"):
                raise RightsError()
            erase_files(self.backend, scope)
            erase_rows(session, owner, scope)
            now = utc(self.clock())
            if row is None:
                from ...audit.service import AuditWriter
                audit = AuditWriter(self.engine)
                audit.is_synthetic_default = True
                receipt = audit.success(session, "administrator.action", actor_kind="system",
                    object_type="deletion_job", object_id=identifier, now=now)
                row = RightsRequest(id=identifier, owner_user_id=owner, session_id=None, is_synthetic=True,
                    kind="deletion", natural_key=sha256(canonical(["deletion", str(owner)])).hexdigest(),
                    scope={}, scope_sha256=sha256(canonical({})).hexdigest(), ledger_sequence=0,
                    status="completed", reason="OK", attempts=0, generation=0,
                    accepted_at=at, available_at=at, due_at=at + timedelta(days=30),
                    retained_until=event.expires_at, completed_at=now, audit_event_id=receipt.id)
                # Authoritative sequence is obtained from the verified chain.
                _, events = self.ledger.snapshot()
                row.ledger_sequence = next(i for i, value in enumerate(events, 1) if value.event_id == event.event_id)
                session.add(row)
            else:
                row.status, row.reason, row.completed_at = "completed", "OK", now
                row.worker_id = row.lease_token = row.lease_until = None
                row.scope, row.scope_sha256 = {}, sha256(canonical({})).hexdigest()
        session.flush()
