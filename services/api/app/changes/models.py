"""Additive impact history; existing release and private domain rows stay intact."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..assessments.models import EligibilityAssessment
from ..plans.models import PlanRoot, PlanVersion, PlanSourceAssessment
from ..releases.models import CatalogRelease, ChangeEvent


class ChangesBase(DeclarativeBase):
    pass


class ChangeEventReceipt(ChangesBase):
    __tablename__ = "change_event_receipts"
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    event_type: Mapped[str] = mapped_column(String(12), nullable=False)
    before_release_id: Mapped[UUID | None] = mapped_column(nullable=True)
    after_release_id: Mapped[UUID | None] = mapped_column(nullable=True)
    event_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    assessment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_count: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("event_id",), (ChangeEvent.id,), name="fk_change_receipt_event", ondelete="RESTRICT"),
        ForeignKeyConstraint(("before_release_id", "dataset_id", "entry_year", "is_synthetic"),
            (CatalogRelease.id, CatalogRelease.dataset_id, CatalogRelease.entry_year, CatalogRelease.is_synthetic), name="fk_change_receipt_before", ondelete="RESTRICT"),
        ForeignKeyConstraint(("after_release_id", "dataset_id", "entry_year", "is_synthetic"),
            (CatalogRelease.id, CatalogRelease.dataset_id, CatalogRelease.entry_year, CatalogRelease.is_synthetic), name="fk_change_receipt_after", ondelete="RESTRICT"),
        CheckConstraint("entry_year BETWEEN 1 AND 9999 AND assessment_count>=0 AND plan_count>=0", name="ck_change_receipt_counts"),
        CheckConstraint("(event_type='published' AND before_release_id IS NULL AND after_release_id IS NOT NULL) OR (event_type='replaced' AND before_release_id IS NOT NULL AND after_release_id IS NOT NULL AND before_release_id<>after_release_id) OR (event_type='withdrawn' AND before_release_id IS NOT NULL AND after_release_id IS NULL)", name="ck_change_receipt_type"),
        CheckConstraint("length(event_sha256)=64 AND event_sha256 ~ '^[0-9a-f]{64}$' AND length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_change_receipt_hashes"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=262144", name="ck_change_receipt_payload"),
        Index("ix_change_receipt_dataset", "dataset_id", "entry_year", "event_id"),
    )


class AssessmentChangeImpact(ChangesBase):
    __tablename__ = "assessment_change_impacts"
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    assessment_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("event_id", "assessment_id", "owner_user_id", "is_synthetic", name="uq_assessment_change_scope"),
        ForeignKeyConstraint(("event_id",), (ChangeEventReceipt.event_id,), name="fk_assessment_change_receipt", deferrable=True, initially="DEFERRED", ondelete="RESTRICT"),
        ForeignKeyConstraint(("assessment_id",), (EligibilityAssessment.id,), name="fk_assessment_change_assessment", ondelete="RESTRICT"),
        CheckConstraint("length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_assessment_change_hash"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=65536", name="ck_assessment_change_payload"),
        Index("ix_assessment_change_owner", "owner_user_id", "assessment_id", "event_id"),
    )


class PlanChangeImpact(ChangesBase):
    __tablename__ = "plan_change_impacts"
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    assessment_id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("event_id", "assessment_id", "owner_user_id", "is_synthetic"),
            (AssessmentChangeImpact.event_id, AssessmentChangeImpact.assessment_id, AssessmentChangeImpact.owner_user_id, AssessmentChangeImpact.is_synthetic), name="fk_plan_change_assessment_scope", ondelete="RESTRICT"),
        ForeignKeyConstraint(("plan_version_id", "assessment_id"), (PlanSourceAssessment.version_id, PlanSourceAssessment.assessment_id), name="fk_plan_change_source", ondelete="RESTRICT"),
        ForeignKeyConstraint(("plan_version_id", "plan_id"), (PlanVersion.id, PlanVersion.plan_id), name="fk_plan_change_version", ondelete="RESTRICT"),
        ForeignKeyConstraint(("plan_id", "owner_user_id", "is_synthetic"), (PlanRoot.id, PlanRoot.owner_user_id, PlanRoot.is_synthetic), name="fk_plan_change_owner", ondelete="RESTRICT"),
        CheckConstraint("length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_plan_change_hash"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=65536", name="ck_plan_change_payload"),
        Index("ix_plan_change_owner", "owner_user_id", "plan_id", "event_id"),
    )
