"""Private roots and declared snapshots, independent of the frozen M0 tables."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..auth.models import AuthOwnedResource
from ..privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion


class ProfilesBase(DeclarativeBase):
    pass


class ProfileRoot(ProfilesBase):
    __tablename__ = "student_profiles"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_version_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("id", "owner_user_id", "is_synthetic", name="uq_student_profile_owner_mode"),
        ForeignKeyConstraint(["id", "owner_user_id"], [AuthOwnedResource.id, AuthOwnedResource.owner_user_id],
            name="fk_student_profile_registry_owner", ondelete="RESTRICT"),
        ForeignKeyConstraint(["current_version_id", "id", "current_version"],
            ["student_profile_versions.id", "student_profile_versions.profile_id", "student_profile_versions.version"],
            name="fk_student_profile_current_version", deferrable=True, initially="DEFERRED", use_alter=True),
        CheckConstraint("current_version BETWEEN 1 AND 2147483647", name="ck_student_profile_version"),
        Index("ix_student_profile_owner_id", "owner_user_id", "id"),
    )


class ProfileVersion(ProfilesBase):
    __tablename__ = "student_profile_versions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    admission_id: Mapped[UUID] = mapped_column(nullable=False)
    consent_id: Mapped[UUID] = mapped_column(nullable=False)
    declaration_id: Mapped[UUID] = mapped_column(nullable=False)
    notice_id: Mapped[UUID] = mapped_column(nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    notice_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        UniqueConstraint("profile_id", "version", name="uq_student_profile_version"),
        UniqueConstraint("id", "profile_id", "version", name="uq_student_profile_version_pointer"),
        ForeignKeyConstraint(["profile_id", "owner_user_id", "is_synthetic"],
            [ProfileRoot.id, ProfileRoot.owner_user_id, ProfileRoot.is_synthetic],
            name="fk_student_profile_version_owner_mode", ondelete="RESTRICT"),
        ForeignKeyConstraint(["admission_id", "owner_user_id"],
            [PrivacyAdmissionRecord.id, PrivacyAdmissionRecord.user_id], name="fk_student_profile_admission", ondelete="RESTRICT"),
        ForeignKeyConstraint(["consent_id", "owner_user_id"],
            [PrivacyAdmissionRecord.id, PrivacyAdmissionRecord.user_id], name="fk_student_profile_consent", ondelete="RESTRICT"),
        ForeignKeyConstraint(["declaration_id", "owner_user_id"],
            [PrivacyAdmissionRecord.id, PrivacyAdmissionRecord.user_id], name="fk_student_profile_declaration", ondelete="RESTRICT"),
        ForeignKeyConstraint(["notice_id"], [PrivacyNoticeVersion.id], name="fk_student_profile_notice", ondelete="RESTRICT"),
        CheckConstraint("version BETWEEN 1 AND 2147483647", name="ck_student_profile_snapshot_version"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$' AND notice_sha256 ~ '^[0-9a-f]{64}$'", name="ck_student_profile_hashes"),
        CheckConstraint("jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 65536", name="ck_student_profile_payload"),
        CheckConstraint("source = 'student_declared' AND length(policy_version) > 0", name="ck_student_profile_declaration_source"),
        CheckConstraint("expires_at > confirmed_at AND expires_at <= (((confirmed_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC')",
            name="ck_student_profile_retention"),
        Index("ix_student_profile_version_expiry", "expires_at", "id"),
    )
