"""Responsibility references have no foreign keys and never grant permission."""

from datetime import datetime
from uuid import UUID
from typing import get_args

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..auth.models import AuthBase
from .schemas import Action, ObjectType, Reason


def _choices(column, values):
    return column + " IN (" + ",".join("'" + value + "'" for value in values) + ")"


class AuditEvent(AuthBase):
    __tablename__ = "auth_audit_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    actor_session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    object_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    object_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str] = mapped_column(String(32), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint(_choices("action", get_args(Action)), name="ck_audit_action_whitelist"),
        CheckConstraint(_choices("reason_code", get_args(Reason)), name="ck_audit_reason_whitelist"),
        CheckConstraint("object_type IS NULL OR " + _choices("object_type", get_args(ObjectType)), name="ck_audit_type_whitelist"),
        CheckConstraint("(actor_kind = 'user' AND actor_user_id IS NOT NULL) OR "
                        "(actor_kind IN ('anonymous', 'system') AND actor_user_id IS NULL AND actor_session_id IS NULL)", name="ck_audit_actor"),
        CheckConstraint("outcome IN ('succeeded', 'denied', 'failed')", name="ck_audit_outcome"),
        CheckConstraint("(outcome = 'succeeded' AND reason_code = 'OK') OR (outcome <> 'succeeded' AND reason_code <> 'OK')", name="ck_audit_reason"),
        CheckConstraint("object_id IS NULL OR object_type IS NOT NULL", name="ck_audit_object_type"),
        CheckConstraint("object_version IS NULL OR (object_id IS NOT NULL AND object_version > 0)", name="ck_audit_version"),
        CheckConstraint("outcome = 'succeeded' OR (object_id IS NULL AND object_version IS NULL)", name="ck_audit_failed_reference"),
        CheckConstraint("length(request_id) = 32 AND policy_version = 'T10_audit_v1'", name="ck_audit_context"),
        CheckConstraint("expires_at > occurred_at", name="ck_audit_retention"),
        Index("ix_audit_actor", "actor_user_id", "occurred_at", "id"),
        Index("ix_audit_action", "action", "occurred_at", "id"),
        Index("ix_audit_expiry", "expires_at", "id"),
        Index("ix_audit_request", "request_id"),
    )
