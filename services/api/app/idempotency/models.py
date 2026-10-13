"""Independent PostgreSQL receipt metadata; actor references are not permissions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class IdempotencyBase(DeclarativeBase):
    pass


class IdempotencyRecord(IdempotencyBase):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "operation", "key_digest", name="uq_idempotency_actor_operation_key"),
        CheckConstraint("operation IN ('catalog.import','catalog.publish','profile.create','plan.confirm')", name="ck_idempotency_operation"),
        CheckConstraint("state IN ('processing','completed')", name="ck_idempotency_state"),
        CheckConstraint("key_digest ~ '^[0-9a-f]{64}$' AND request_hash ~ '^[0-9a-f]{64}$'", name="ck_idempotency_hashes"),
        CheckConstraint("expires_at > created_at AND expires_at <= (((created_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC')", name="ck_idempotency_expiry"),
        CheckConstraint("(state = 'processing' AND resource_kind IS NULL AND resource_id IS NULL AND resource_version IS NULL AND completed_at IS NULL) OR (state = 'completed' AND resource_kind IS NOT NULL AND resource_id IS NOT NULL AND resource_version IS NOT NULL AND resource_version BETWEEN 1 AND 2147483647 AND completed_at IS NOT NULL AND completed_at >= created_at AND completed_at < expires_at)", name="ck_idempotency_completion"),
        CheckConstraint("resource_kind IS NULL OR (operation = 'catalog.import' AND resource_kind = 'import') OR (operation = 'catalog.publish' AND resource_kind = 'catalog_release') OR (operation = 'profile.create' AND resource_kind = 'profile') OR (operation = 'plan.confirm' AND resource_kind = 'plan')", name="ck_idempotency_receipt_kind"),
        Index("ix_idempotency_expiry_id", "expires_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    actor_user_id: Mapped[UUID] = mapped_column(nullable=False)
    operation: Mapped[str] = mapped_column(String(15), nullable=False)
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    resource_kind: Mapped[str | None] = mapped_column(String(15))
    resource_id: Mapped[UUID | None] = mapped_column()
    resource_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
