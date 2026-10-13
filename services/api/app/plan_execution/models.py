"""T32 sidecar state; immutable T30 drafts and registry versions stay unchanged."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKeyConstraint,
    Index, Integer, String, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..plans.models import PlanRoot, PlanTask, PlanVersion


class ExecutionBase(DeclarativeBase):
    pass


class ExecutionHead(ExecutionBase):
    __tablename__ = "plan_execution_heads"
    plan_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_version_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    current_proposal_id: Mapped[UUID] = mapped_column(nullable=False)
    confirmation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("plan_id", "source_version_id", "owner_user_id", "is_synthetic", name="uq_execution_scope"),
        ForeignKeyConstraint(("plan_id", "owner_user_id", "is_synthetic"),
            (PlanRoot.id, PlanRoot.owner_user_id, PlanRoot.is_synthetic), name="fk_execution_root_owner", ondelete="RESTRICT"),
        ForeignKeyConstraint(("source_version_id", "plan_id"), (PlanVersion.id, PlanVersion.plan_id),
            name="fk_execution_source", ondelete="RESTRICT"),
        ForeignKeyConstraint(("current_proposal_id", "plan_id"),
            ("plan_execution_proposals.id", "plan_execution_proposals.plan_id"),
            name="fk_execution_current_proposal", deferrable=True, initially="DEFERRED", use_alter=True),
        ForeignKeyConstraint(("confirmation_id", "plan_id"),
            ("plan_execution_confirmations.id", "plan_execution_confirmations.plan_id"),
            name="fk_execution_confirmation", deferrable=True, initially="DEFERRED", use_alter=True),
        CheckConstraint("state_version BETWEEN 1 AND 2147483647", name="ck_execution_state_version"),
        CheckConstraint("state IN ('draft','confirmed') AND ((state='draft' AND confirmation_id IS NULL) OR (state='confirmed' AND confirmation_id IS NOT NULL))", name="ck_execution_state"),
        CheckConstraint("expires_at>created_at AND expires_at<=(((created_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')", name="ck_execution_retention"),
        Index("ix_execution_owner_id", "owner_user_id", "plan_id"),
        Index("ix_execution_expiry", "expires_at", "plan_id"),
    )


class ExecutionProposal(ExecutionBase):
    __tablename__ = "plan_execution_proposals"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(nullable=False)
    source_version_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    draft_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    schedule_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        UniqueConstraint("id", "plan_id", name="uq_execution_proposal_pointer"),
        UniqueConstraint("plan_id", "state_version", name="uq_execution_proposal_version"),
        UniqueConstraint("id", "plan_id", "source_version_id", "owner_user_id", "is_synthetic", name="uq_execution_proposal_scope"),
        ForeignKeyConstraint(("plan_id", "source_version_id", "owner_user_id", "is_synthetic"),
            (ExecutionHead.plan_id, ExecutionHead.source_version_id, ExecutionHead.owner_user_id, ExecutionHead.is_synthetic),
            name="fk_execution_proposal_scope", ondelete="RESTRICT"),
        CheckConstraint("state_version BETWEEN 1 AND 2147483647", name="ck_execution_proposal_version"),
        CheckConstraint("length(draft_sha256)=64 AND draft_sha256 ~ '^[0-9a-f]{64}$' AND (schedule_sha256 IS NULL OR (length(schedule_sha256)=64 AND schedule_sha256 ~ '^[0-9a-f]{64}$'))", name="ck_execution_proposal_hashes"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=1048576", name="ck_execution_proposal_payload"),
        CheckConstraint("expires_at>created_at AND expires_at<=(((created_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')", name="ck_execution_proposal_retention"),
    )


class ExecutionConfirmation(ExecutionBase):
    __tablename__ = "plan_execution_confirmations"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(nullable=False)
    source_version_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(nullable=False)
    confirmed_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    acknowledge_unverified_deadlines: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_execution_confirmation_once"),
        UniqueConstraint("id", "plan_id", name="uq_execution_confirmation_pointer"),
        UniqueConstraint("id", "plan_id", "source_version_id", "owner_user_id", "is_synthetic", name="uq_execution_confirmation_scope"),
        ForeignKeyConstraint(("proposal_id", "plan_id", "source_version_id", "owner_user_id", "is_synthetic"),
            (ExecutionProposal.id, ExecutionProposal.plan_id, ExecutionProposal.source_version_id,
             ExecutionProposal.owner_user_id, ExecutionProposal.is_synthetic), name="fk_execution_confirmation_proposal", ondelete="RESTRICT"),
        CheckConstraint("confirmed_state_version BETWEEN 2 AND 2147483647 AND acknowledge_unverified_deadlines=true", name="ck_execution_confirmation_explicit"),
        CheckConstraint("length(request_sha256)=64 AND request_sha256 ~ '^[0-9a-f]{64}$'", name="ck_execution_confirmation_hash"),
        CheckConstraint("expires_at>confirmed_at AND expires_at<=(((confirmed_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')", name="ck_execution_confirmation_retention"),
    )


class TaskCompletion(ExecutionBase):
    __tablename__ = "plan_task_completions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(nullable=False)
    source_version_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmation_id: Mapped[UUID] = mapped_column(nullable=False)
    task_key: Mapped[str] = mapped_column(String(64), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        UniqueConstraint("confirmation_id", "task_key", name="uq_execution_task_completion"),
        UniqueConstraint("plan_id", "state_version", name="uq_execution_completion_version"),
        ForeignKeyConstraint(("confirmation_id", "plan_id", "source_version_id", "owner_user_id", "is_synthetic"),
            (ExecutionConfirmation.id, ExecutionConfirmation.plan_id, ExecutionConfirmation.source_version_id,
             ExecutionConfirmation.owner_user_id, ExecutionConfirmation.is_synthetic), name="fk_execution_completion_confirmation", ondelete="RESTRICT"),
        ForeignKeyConstraint(("source_version_id", "plan_id", "task_key"),
            (PlanTask.version_id, PlanTask.plan_id, PlanTask.task_key), name="fk_execution_completion_task", ondelete="RESTRICT"),
        CheckConstraint("state_version BETWEEN 3 AND 2147483647 AND source='student_declared'", name="ck_execution_completion_state"),
        CheckConstraint("length(task_key)=64 AND task_key ~ '^[0-9a-f]{64}$' AND length(request_sha256)=64 AND request_sha256 ~ '^[0-9a-f]{64}$'", name="ck_execution_completion_hashes"),
        CheckConstraint("expires_at>completed_at AND expires_at<=(((completed_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')", name="ck_execution_completion_retention"),
    )
