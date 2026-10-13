"""Same-transaction successes, post-rollback failures and privileged reading."""

from datetime import datetime, timezone
from typing import get_args
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..auth.assurance import check_admin_assurance
from ..auth.authorization import AuthorizationError, Principal, Role
from ..auth.config import AuthFlowError
from ..auth.store import database_time, utc_time
from .context import audited, current_request_id, mark_failure_recorded
from .logging import emit
from .models import AuditEvent
from .retention import expires_after_months
from .schemas import AuditActor, AuditEventData, AuditEventInput, AuditPage, POLICY_VERSION, Reason


class AuditError(AuthorizationError):
    pass


class AuditWriter:
    def __init__(self, engine):
        self.engine = engine
        self.is_synthetic_default = False

    def append(self, session, event, *, actor=None, actor_kind=None, now=None):
        """Caller owns current authorization and transaction; UUIDs are traces."""
        try:
            if not isinstance(session, Session) or not session.in_transaction():
                raise ValueError
            bind = session.get_bind()
            if getattr(bind, "engine", bind) is not self.engine:
                raise ValueError
            event = AuditEventInput.model_validate(event)
            if actor is not None:
                actor = AuditActor.model_validate(actor if isinstance(actor, AuditActor) else
                    {"user_id": actor.user_id, "session_id": actor.session_id, "is_synthetic": actor.is_synthetic})
            kind = actor_kind if actor_kind is not None else ("user" if actor is not None else "anonymous")
            occurred_at = utc_time(now if now is not None else datetime.now(timezone.utc))
            data = AuditEventData(**event.model_dump(), id=uuid4(), occurred_at=occurred_at,
                actor_kind=kind, actor_user_id=actor.user_id if actor is not None else None,
                actor_session_id=actor.session_id if actor is not None else None, request_id=current_request_id(),
                is_synthetic=actor.is_synthetic if actor is not None else self.is_synthetic_default,
                policy_version=POLICY_VERSION, expires_at=expires_after_months(occurred_at))
            session.add(AuditEvent(**data.model_dump()))
            session.flush()
            return data
        except Exception:
            raise AuditError(503) from None

    def success(self, session, action, *, actor=None, actor_kind=None, object_type=None, object_id=None, object_version=None, now=None):
        return self.append(session, AuditEventInput(action=action, outcome="succeeded", reason_code="OK",
            object_type=object_type, object_id=object_id, object_version=object_version), actor=actor,
            actor_kind=actor_kind, now=now)

    def failure(self, action, error, *, actor=None):
        """Best effort after the business boundary. Never stringify the error."""
        mark_failure_recorded()
        try:
            status = getattr(error, "status_code", 500)
            code = getattr(error, "code", "INTERNAL_ERROR")
            if code not in get_args(Reason) or code == "OK":
                code = "INTERNAL_ERROR"
            event = AuditEventInput(action=action, outcome="denied" if status in {401, 403, 404, 409, 422} else "failed", reason_code=code)
            with Session(self.engine) as session, session.begin():
                self.append(session, event, actor=actor)
        except Exception:
            try:
                emit("audit.write.failed", reason_code="SERVICE_UNAVAILABLE")
            except Exception:
                pass


class AuditService:
    def __init__(self, auth_service):
        from ..auth.service import AuthService
        if not isinstance(auth_service, AuthService):
            raise AuditError(503)
        self.auth_service = auth_service
        self._validate()

    def _validate(self):
        self.auth_service._validate()
        return self.auth_service

    def _operator(self, session, principal):
        try:
            principal = Principal.model_validate(principal)
        except (ValidationError, ValueError, TypeError):
            raise AuditError(401) from None
        current, stored = self.auth_service.store.locked_principal(session, principal, clock=self.auth_service._now,
            production=self.auth_service.runtime_settings.app_environment == "production")
        if Role.operations not in current.roles:
            raise AuditError(403)
        settings = self.auth_service._validate()
        if stored.verified_issuer != settings.provider.issuer or stored.verified_client_id != settings.provider.client_id:
            raise AuditError(403)
        check_admin_assurance(stored.assurance, issuer=stored.verified_issuer, client_id=stored.verified_client_id,
            policy=settings.admin_assurance_policy, now=self.auth_service._now())
        return current

    @staticmethod
    def _limit(limit, maximum=100):
        if type(limit) is not int or not 1 <= limit <= maximum:
            raise AuditError(403)

    @staticmethod
    def _data(row):
        values = {column.name: getattr(row, column.name) for column in AuditEvent.__table__.columns}
        values["occurred_at"], values["expires_at"] = database_time(row.occurred_at), database_time(row.expires_at)
        return AuditEventData.model_validate(values)

    @audited("audit.read")
    def list_events(self, principal, *, limit=50, after_id=None):
        self._validate()
        self._limit(limit)
        if after_id is not None and not isinstance(after_id, UUID):
            raise AuditError(403)
        try:
            with Session(self.auth_service.store.engine) as session, session.begin():
                current = self._operator(session, principal)
                query = select(AuditEvent).where(AuditEvent.expires_at > self.auth_service._now())
                if after_id is not None:
                    query = query.where(AuditEvent.id > after_id)
                if self.auth_service.runtime_settings.app_environment == "production":
                    query = query.where(AuditEvent.is_synthetic.is_(False))
                rows = session.scalars(query.order_by(AuditEvent.id).limit(limit + 1)).all()
                current = self._operator(session, current)
                now = self.auth_service._now()
                # Requery at the current locked authorization time, before paging.
                rows = session.scalars(query.where(AuditEvent.expires_at > now).order_by(AuditEvent.id).limit(limit + 1)).all()
                values = tuple(self._data(row) for row in rows[:limit])
                self.auth_service.store.audit.success(session, "audit.read", actor=current, now=now)
                self._operator(session, current)
                final_now = self.auth_service._now()
                if any(final_now >= item.expires_at for item in values):
                    # No stale cursor or expired event is served after the flush.
                    return AuditPage(items=(), next_cursor=None)
                return AuditPage(items=values, next_cursor=rows[limit - 1].id if len(rows) > limit else None)
        except AuthFlowError:
            raise
        except Exception:
            raise AuditError(503) from None

    @audited("audit.purge")
    def purge_expired(self, principal, *, limit=100):
        self._validate()
        self._limit(limit, 1000)
        try:
            with Session(self.auth_service.store.engine) as session, session.begin():
                current = self._operator(session, principal)
                rows = session.scalars(select(AuditEvent.id).where(AuditEvent.expires_at <= self.auth_service._now())
                    .order_by(AuditEvent.expires_at, AuditEvent.id).limit(limit).with_for_update()).all()
                current = self._operator(session, current)
                deleted = 0
                if rows:
                    deleted = session.execute(delete(AuditEvent).where(AuditEvent.id.in_(rows), AuditEvent.expires_at <= self.auth_service._now())).rowcount
                self.auth_service.store.audit.success(session, "audit.purge", actor=current, now=self.auth_service._now())
                self._operator(session, current)
                return deleted
        except AuthFlowError:
            raise
        except Exception:
            raise AuditError(503) from None
