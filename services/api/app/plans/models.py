"""Private draft identities and immutable snapshots, separate from M0 planning."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..auth.models import AuthOwnedResource
from ..profiles.models import ProfileRoot, ProfileVersion
from ..assessments.models import EligibilityAssessment


class PlansBase(DeclarativeBase):
    pass


class PlanRoot(PlansBase):
    __tablename__ = "plan_draft_roots"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    profile_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_version_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_version_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("id", "owner_user_id", "is_synthetic", name="uq_plan_root_owner_mode"),
        ForeignKeyConstraint(("id", "owner_user_id"), (AuthOwnedResource.id, AuthOwnedResource.owner_user_id),
            name="fk_plan_root_registry", ondelete="RESTRICT"),
        ForeignKeyConstraint(("profile_id", "owner_user_id", "is_synthetic"),
            (ProfileRoot.id, ProfileRoot.owner_user_id, ProfileRoot.is_synthetic), name="fk_plan_root_profile_owner", ondelete="RESTRICT"),
        ForeignKeyConstraint(("profile_version_id", "profile_id", "profile_version"),
            (ProfileVersion.id, ProfileVersion.profile_id, ProfileVersion.version), name="fk_plan_root_profile_version", ondelete="RESTRICT"),
        ForeignKeyConstraint(("current_version_id", "id", "current_version"),
            ("plan_draft_versions.id", "plan_draft_versions.plan_id", "plan_draft_versions.version"),
            name="fk_plan_root_current_version", deferrable=True, initially="DEFERRED"),
        CheckConstraint("profile_version BETWEEN 1 AND 2147483647 AND current_version BETWEEN 1 AND 2147483647", name="ck_plan_root_versions"),
        CheckConstraint("length(profile_sha256)=64 AND profile_sha256 ~ '^[0-9a-f]{64}$'", name="ck_plan_root_hash"),
        Index("ix_plan_root_owner_id", "owner_user_id", "id"),
    )


class PlanVersion(PlansBase):
    __tablename__ = "plan_draft_versions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    draft_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="uq_plan_version_number"),
        UniqueConstraint("id", "plan_id", "version", name="uq_plan_version_pointer"),
        UniqueConstraint("id", "plan_id", name="uq_plan_version_scope"),
        ForeignKeyConstraint(("plan_id", "owner_user_id", "is_synthetic"),
            (PlanRoot.id, PlanRoot.owner_user_id, PlanRoot.is_synthetic), name="fk_plan_version_owner", ondelete="RESTRICT"),
        CheckConstraint("version BETWEEN 1 AND 2147483647", name="ck_plan_version_positive"),
        CheckConstraint("length(draft_sha256)=64 AND draft_sha256 ~ '^[0-9a-f]{64}$'", name="ck_plan_version_hash"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=524288", name="ck_plan_version_payload"),
        CheckConstraint("payload @> jsonb_build_object('status','draft','confirmed',false,'scheduled',false,'schema_version','T30_v1','generator_version','T30_v1')", name="ck_plan_version_markers"),
        CheckConstraint("expires_at>created_at AND expires_at<=(((created_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')", name="ck_plan_version_retention"),
        Index("ix_plan_version_expiry", "expires_at", "id"),
    )


class PlanTask(PlansBase):
    __tablename__ = "plan_draft_tasks"
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    task_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        UniqueConstraint("version_id", "plan_id", "task_key", name="uq_plan_task_scope"),
        UniqueConstraint("version_id", "ordinal", name="uq_plan_task_ordinal"),
        ForeignKeyConstraint(("version_id", "plan_id"), (PlanVersion.id, PlanVersion.plan_id), name="fk_plan_task_version", ondelete="RESTRICT"),
        CheckConstraint("ordinal BETWEEN 1 AND 100", name="ck_plan_task_ordinal"),
        CheckConstraint("length(task_key)=64 AND task_key ~ '^[0-9a-f]{64}$' AND length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_plan_task_hashes"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=131072 AND payload @> jsonb_build_object('confirmed',false,'estimate_editable',true)", name="ck_plan_task_payload"),
    )


class PlanSourceAssessment(PlansBase):
    __tablename__ = "plan_draft_assessments"
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    assessment_id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(nullable=False)
    result_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("version_id", "plan_id"), (PlanVersion.id, PlanVersion.plan_id), name="fk_plan_assessment_version", ondelete="RESTRICT"),
        ForeignKeyConstraint(("assessment_id",), (EligibilityAssessment.id,), name="fk_plan_assessment_exact", ondelete="RESTRICT"),
        CheckConstraint("length(result_sha256)=64 AND result_sha256 ~ '^[0-9a-f]{64}$'", name="ck_plan_assessment_hash"),
    )


class PlanTaskDependency(PlansBase):
    __tablename__ = "plan_draft_dependencies"
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    task_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    dependency_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("version_id", "plan_id", "task_key"),
            (PlanTask.version_id, PlanTask.plan_id, PlanTask.task_key), name="fk_plan_dependency_task", ondelete="RESTRICT"),
        ForeignKeyConstraint(("version_id", "plan_id", "dependency_key"),
            (PlanTask.version_id, PlanTask.plan_id, PlanTask.task_key), name="fk_plan_dependency_same_version", ondelete="RESTRICT"),
        CheckConstraint("task_key<>dependency_key", name="ck_plan_dependency_not_self"),
    )
