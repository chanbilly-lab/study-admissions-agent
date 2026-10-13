"""Business records contain private scope; external ledger contains only minimal reductions."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ...auth.models import AuthUser
from ...changes.models import ChangeEventReceipt


class RightsBase(DeclarativeBase):
    pass


class RightsWatermark(RightsBase):
    __tablename__ = "rights_restore_watermark"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chain_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (CheckConstraint("id=1 AND sequence BETWEEN 0 AND 10000 AND chain_sha256 ~ '^[0-9a-f]{64}$'", name="ck_rights_watermark"),)


class RightsRequest(RightsBase):
    __tablename__ = "privacy_rights_requests"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    natural_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scope_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ledger_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(9), nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retained_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    artifact_id: Mapped[UUID | None] = mapped_column(nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifact_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("owner_user_id",), (AuthUser.id,), name="fk_rights_owner", ondelete="RESTRICT"),
        CheckConstraint("is_synthetic=true AND kind IN ('export','deletion') AND status IN ('queued','running','completed','failed','cancelled')", name="ck_rights_mode_state"),
        CheckConstraint("attempts BETWEEN 0 AND 5 AND generation BETWEEN 0 AND 2147483647 AND ledger_sequence BETWEEN 0 AND 10000", name="ck_rights_attempts"),
        CheckConstraint("reason IN ('OK','AUTHORITY_REVOKED','OWNER_DELETED','EXPIRED','EXPORT_LIMIT','RETRYABLE_FAILURE','ATTEMPTS_EXHAUSTED','LEASE_LOST','LEDGER_UNAVAILABLE')", name="ck_rights_reason"),
        CheckConstraint("natural_key ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(scope)='object' AND octet_length(scope::text)<=262144", name="ck_rights_scope"),
        CheckConstraint("(status='running' AND worker_id IS NOT NULL AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (status<>'running' AND worker_id IS NULL AND lease_token IS NULL AND lease_until IS NULL)", name="ck_rights_lease"),
        CheckConstraint("(kind='deletion' AND due_at=accepted_at+interval '30 days' AND session_id IS NULL AND ledger_sequence>=1) OR (kind='export' AND due_at IS NULL AND session_id IS NOT NULL)", name="ck_rights_authority"),
        CheckConstraint("available_at>=accepted_at AND retained_until>accepted_at AND retained_until<=(((accepted_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')", name="ck_rights_retention"),
        CheckConstraint("(status='completed' AND completed_at>=accepted_at) OR (status<>'completed' AND completed_at IS NULL)", name="ck_rights_completion"),
        CheckConstraint("(artifact_id IS NULL AND artifact_sha256 IS NULL AND artifact_size IS NULL AND artifact_expires_at IS NULL) OR (kind='export' AND artifact_id IS NOT NULL AND artifact_sha256 ~ '^[0-9a-f]{64}$' AND artifact_size BETWEEN 1 AND 10485760 AND artifact_expires_at>accepted_at AND artifact_expires_at<=accepted_at+interval '1 day')", name="ck_rights_artifact"),
        Index("ix_rights_claim", "status", "available_at", "lease_until", "id"),
        Index("ix_rights_owner", "owner_user_id", "kind", "id"),
    )


class RightsAttempt(RightsBase):
    __tablename__ = "privacy_rights_attempts"
    request_id: Mapped[UUID] = mapped_column(primary_key=True)
    generation: Mapped[int] = mapped_column(Integer, primary_key=True)
    outcome: Mapped[str] = mapped_column(String(9), nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("request_id",), (RightsRequest.id,), name="fk_rights_attempt", ondelete="RESTRICT"),
        CheckConstraint("generation>=1 AND outcome IN ('queued','completed','cancelled','failed') AND reason IN ('OK','AUTHORITY_REVOKED','OWNER_DELETED','EXPIRED','EXPORT_LIMIT','RETRYABLE_FAILURE','ATTEMPTS_EXHAUSTED')", name="ck_rights_attempt"),
    )


class ErasedImpactCount(RightsBase):
    __tablename__ = "rights_erased_impact_counts"
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    assessment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_count: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("event_id",), (ChangeEventReceipt.event_id,), name="fk_rights_erased_event", ondelete="RESTRICT"),
        CheckConstraint("assessment_count>=0 AND plan_count>=0", name="ck_rights_erased_counts"),
    )


class BackupRegistration(RightsBase):
    __tablename__ = "rights_backup_registrations"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ledger_id: Mapped[UUID] = mapped_column(nullable=False)
    ledger_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    __table_args__ = (CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$' AND expires_at>captured_at AND expires_at<=captured_at+interval '35 days' AND ledger_sequence BETWEEN 0 AND 10000", name="ck_rights_backup"),)


class LedgerBase(DeclarativeBase):
    pass


class LedgerHead(LedgerBase):
    __tablename__ = "privacy_ledger_head"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chain_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (CheckConstraint("id=1 AND sequence BETWEEN 0 AND 10000 AND chain_sha256 ~ '^[0-9a-f]{64}$'", name="ck_privacy_ledger_head"),)


class LedgerEvent(LedgerBase):
    __tablename__ = "privacy_ledger_events"
    sequence: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    event: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    chain_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        CheckConstraint("sequence BETWEEN 1 AND 10000 AND jsonb_typeof(event)='object' AND octet_length(event::text)<=2048 AND previous_sha256 ~ '^[0-9a-f]{64}$' AND chain_sha256 ~ '^[0-9a-f]{64}$'", name="ck_privacy_ledger_event"),
    )
