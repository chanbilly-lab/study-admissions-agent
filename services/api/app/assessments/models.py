"""Immutable results have separate ownership and catalogue provenance."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..profiles.models import ProfileRoot, ProfileVersion
from ..releases.models import CatalogRelease


class AssessmentsBase(DeclarativeBase):
    pass


class EligibilityAssessment(AssessmentsBase):
    __tablename__ = "eligibility_assessments"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_version_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(nullable=False)
    release_id: Mapped[UUID] = mapped_column(nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    catalogue_is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    assessment_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    binding_mode: Mapped[str] = mapped_column(String(12), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    replay_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("profile_id", "owner_user_id", "profile_is_synthetic"),
            (ProfileRoot.id, ProfileRoot.owner_user_id, ProfileRoot.is_synthetic),
            name="fk_assessment_profile_owner", ondelete="RESTRICT"),
        ForeignKeyConstraint(("profile_version_id", "profile_id", "profile_version"),
            (ProfileVersion.id, ProfileVersion.profile_id, ProfileVersion.version),
            name="fk_assessment_profile_version", ondelete="RESTRICT"),
        ForeignKeyConstraint(("release_id", "dataset_id", "entry_year", "catalogue_is_synthetic"),
            (CatalogRelease.id, CatalogRelease.dataset_id, CatalogRelease.entry_year, CatalogRelease.is_synthetic),
            name="fk_assessment_release_scope", ondelete="RESTRICT"),
        CheckConstraint("version = 1 AND profile_version BETWEEN 1 AND 2147483647 AND entry_year BETWEEN 1 AND 9999",
            name="ck_assessment_versions"),
        CheckConstraint("engine_version = 'T28_v1' AND binding_mode IN ('unavailable','test_fixture')",
            name="ck_assessment_engine_binding"),
        CheckConstraint("binding_mode <> 'test_fixture' OR (profile_is_synthetic = true AND catalogue_is_synthetic = true)",
            name="ck_assessment_test_binding"),
        CheckConstraint("expires_at > assessment_at AND expires_at <= (((assessment_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC')",
            name="ck_assessment_retention"),
        CheckConstraint("length(result_sha256)=64 AND result_sha256 ~ '^[0-9a-f]{64}$' AND length(snapshot_sha256)=64 AND snapshot_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_assessment_hashes"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=262144 AND jsonb_typeof(replay_snapshot)='object' AND octet_length(replay_snapshot::text)<=524288",
            name="ck_assessment_payload"),
        Index("ix_assessment_owner_id", "owner_user_id", "id"),
        Index("ix_assessment_expiry", "expires_at", "id"),
    )
