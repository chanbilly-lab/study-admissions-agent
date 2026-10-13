"""T08 append-only admission snapshots and actual immutable notice versions.

The trusted service creates versions; these models do not collect a rejected
child age band, student facts, guardian identity or third-party permission.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..auth.models import AuthBase


class PrivacyNoticeVersion(AuthBase):
    __tablename__ = "privacy_notice_versions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    controller_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (
        CheckConstraint("length(version) > 0 AND length(policy_version) > 0 AND length(text) > 0 "
                        "AND length(controller_reference) > 0", name="ck_privacy_notice_nonempty"),
        CheckConstraint("length(text_sha256) = 64", name="ck_privacy_notice_hash"),
        CheckConstraint("review_status IN ('test_reviewed', 'reviewed')", name="ck_privacy_notice_review"),
    )


class PrivacyAdmissionRecord(AuthBase):
    """Every adult change, confirmation and withdrawal creates a new snapshot."""

    __tablename__ = "privacy_admission_records"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    age_band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    age_assurance: Mapped[str] = mapped_column(String(16), nullable=False)
    declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declaration_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declaration_notice_id: Mapped[UUID | None] = mapped_column(ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"), nullable=True)
    consent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    consent_status: Mapped[str] = mapped_column(String(16), nullable=False)
    consent_notice_id: Mapped[UUID | None] = mapped_column(ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"), nullable=True)
    consent_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("user_id", "revision", name="uq_privacy_admission_revision"),
        UniqueConstraint("id", "user_id", name="uq_privacy_admission_id_user"),
        ForeignKeyConstraint(["consent_id", "user_id"], ["privacy_admission_records.id", "privacy_admission_records.user_id"],
                             name="fk_privacy_consent_owner", ondelete="RESTRICT"),
        CheckConstraint("revision > 0 AND length(policy_version) > 0", name="ck_privacy_admission_revision"),
        CheckConstraint("event_type IN ('adult_declared', 'consent_confirmed', 'consent_withdrawn', 'admission_invalidated')",
                        name="ck_privacy_admission_event"),
        CheckConstraint("(age_band IS NULL AND age_assurance = 'unknown' AND declared_at IS NULL "
                        "AND declaration_expires_at IS NULL AND declaration_notice_id IS NULL) OR "
                        "(age_band IS NOT NULL AND age_band = '18_plus' AND age_assurance = 'declared' AND declared_at IS NOT NULL "
                        "AND declaration_expires_at IS NOT NULL AND declaration_expires_at > declared_at AND declaration_notice_id IS NOT NULL)",
                        name="ck_privacy_admission_age"),
        CheckConstraint("consent_status IN ('not_confirmed', 'active', 'withdrawn', 'invalidated')", name="ck_privacy_consent_status"),
        CheckConstraint("(consent_id IS NULL AND consent_notice_id IS NULL AND consent_confirmed_at IS NULL "
                        "AND consent_withdrawn_at IS NULL AND consent_status = 'not_confirmed') OR "
                        "(consent_id IS NOT NULL AND consent_notice_id IS NOT NULL AND consent_confirmed_at IS NOT NULL "
                        "AND consent_status IN ('active', 'withdrawn', 'invalidated'))", name="ck_privacy_consent_reference"),
        CheckConstraint("(consent_status = 'withdrawn' AND consent_withdrawn_at IS NOT NULL "
                        "AND consent_withdrawn_at >= consent_confirmed_at) OR "
                        "(consent_status <> 'withdrawn' AND consent_withdrawn_at IS NULL)", name="ck_privacy_consent_withdrawal"),
        CheckConstraint("consent_status <> 'active' OR (age_band IS NOT NULL AND age_band = '18_plus')", name="ck_privacy_active_adult"),
        Index("ix_privacy_admission_current", "user_id", "revision"),
        Index("ix_privacy_admission_consent", "consent_id", "user_id"),
    )
