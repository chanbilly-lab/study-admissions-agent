"""Five additive durable-processing tables, isolated from old outbox records."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..auth.models import AuthUser, AuthOwnedResource
from ..profiles.models import ProfileRoot, ProfileVersion
from ..assessments.models import EligibilityAssessment
from ..releases.models import ChangeEvent, OutboxEvent


class JobsBase(DeclarativeBase):
    pass


class CleanupPermit(JobsBase):
    __tablename__ = "cleanup_permits"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    watermark: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scope_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        UniqueConstraint("owner_user_id","watermark","scope_sha256",name="uq_cleanup_permit_scope"),
        UniqueConstraint("id","owner_user_id","is_synthetic",name="uq_cleanup_permit_owner"),
        ForeignKeyConstraint(("owner_user_id",),(AuthUser.id,),name="fk_cleanup_permit_owner",ondelete="RESTRICT"),
        CheckConstraint("purpose IN ('deletion_cleanup','retention_cleanup') AND watermark>=1",name="ck_cleanup_permit_scope"),
        CheckConstraint("length(scope_sha256)=64 AND scope_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(scope)='object' AND octet_length(scope::text)<=32768",name="ck_cleanup_permit_payload"),
        CheckConstraint("expires_at>accepted_at AND expires_at<=accepted_at+interval '30 days'",name="ck_cleanup_permit_ttl"),
    )


class DurableJob(JobsBase):
    __tablename__ = "durable_jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    natural_key: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    event_id: Mapped[UUID | None] = mapped_column(nullable=True)
    outbox_id: Mapped[UUID | None] = mapped_column(nullable=True)
    assessment_id: Mapped[UUID | None] = mapped_column(nullable=True)
    preference_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    permit_id: Mapped[UUID | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(9), nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("natural_key",name="uq_durable_job_natural"),
        UniqueConstraint("id","owner_user_id","is_synthetic",name="uq_durable_job_owner"),
        ForeignKeyConstraint(("event_id",),(ChangeEvent.id,),name="fk_durable_job_event",ondelete="RESTRICT"),
        ForeignKeyConstraint(("outbox_id",),(OutboxEvent.id,),name="fk_durable_job_outbox",ondelete="RESTRICT"),
        ForeignKeyConstraint(("assessment_id",),(EligibilityAssessment.id,),name="fk_durable_job_assessment",ondelete="RESTRICT"),
        ForeignKeyConstraint(("owner_user_id",),(AuthUser.id,),name="fk_durable_job_owner",ondelete="RESTRICT"),
        ForeignKeyConstraint(("permit_id","owner_user_id","is_synthetic"),(CleanupPermit.id,CleanupPermit.owner_user_id,CleanupPermit.is_synthetic),name="fk_durable_job_permit",ondelete="RESTRICT"),
        CheckConstraint("kind IN ('release_impact','notification','export','model','cleanup_probe') AND status IN ('queued','running','completed','cancelled','failed')",name="ck_durable_job_state"),
        CheckConstraint("attempts BETWEEN 0 AND 5 AND generation BETWEEN 0 AND 2147483647",name="ck_durable_job_attempts"),
        CheckConstraint("reason IN ('OK','AUTHORITY_REVOKED','PREFERENCE_CHANGED','PROFILE_CHANGED','EXPIRED','LEASE_LOST','RETRYABLE_FAILURE','HANDLER_UNAVAILABLE','PERMIT_INVALID','ATTEMPTS_EXHAUSTED')",name="ck_durable_job_reason"),
        CheckConstraint("(status='running' AND worker_id IS NOT NULL AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (status<>'running' AND worker_id IS NULL AND lease_token IS NULL AND lease_until IS NULL)",name="ck_durable_job_lease"),
        CheckConstraint("(kind='release_impact' AND owner_user_id IS NULL AND event_id IS NOT NULL AND outbox_id IS NOT NULL AND assessment_id IS NULL AND preference_version IS NULL AND permit_id IS NULL) OR (kind IN ('notification','export','model') AND owner_user_id IS NOT NULL AND event_id IS NOT NULL AND assessment_id IS NOT NULL AND preference_version>=1 AND permit_id IS NULL AND outbox_id IS NULL) OR (kind='cleanup_probe' AND permit_id IS NOT NULL AND owner_user_id IS NOT NULL AND event_id IS NULL AND assessment_id IS NULL AND outbox_id IS NULL AND preference_version IS NULL)",name="ck_durable_job_refs"),
        CheckConstraint("length(natural_key)=64 AND natural_key ~ '^[0-9a-f]{64}$' AND length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(payload)='object' AND octet_length(payload::text)<=8192",name="ck_durable_job_payload"),
        CheckConstraint("created_at<=updated_at AND expires_at>created_at AND expires_at<=created_at+interval '1 day' AND available_at>=created_at",name="ck_durable_job_times"),
        Index("ix_durable_job_claim","status","available_at","lease_until","id"),
        Index("ix_durable_job_event","event_id","kind","id"),
    )


class JobAttempt(JobsBase):
    __tablename__ = "job_attempts"
    job_id: Mapped[UUID] = mapped_column(primary_key=True)
    generation: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[UUID] = mapped_column(nullable=False)
    lease_token: Mapped[UUID] = mapped_column(nullable=False)
    outcome: Mapped[str] = mapped_column(String(9), nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("job_id",),(DurableJob.id,),name="fk_job_attempt_job",ondelete="RESTRICT"),
        CheckConstraint("generation>=1 AND outcome IN ('queued','completed','cancelled','failed')",name="ck_job_attempt_outcome"),
        CheckConstraint("reason IN ('OK','AUTHORITY_REVOKED','PREFERENCE_CHANGED','PROFILE_CHANGED','EXPIRED','RETRYABLE_FAILURE','HANDLER_UNAVAILABLE','PERMIT_INVALID','ATTEMPTS_EXHAUSTED')",name="ck_job_attempt_reason"),
    )


class NotificationPreference(JobsBase):
    __tablename__ = "notification_preferences"
    owner_user_id: Mapped[UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(nullable=True)
    profile_id: Mapped[UUID | None] = mapped_column(nullable=True)
    profile_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    profile_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    admission_id: Mapped[UUID | None] = mapped_column(nullable=True)
    consent_id: Mapped[UUID | None] = mapped_column(nullable=True)
    declaration_id: Mapped[UUID | None] = mapped_column(nullable=True)
    notice_id: Mapped[UUID | None] = mapped_column(nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notice_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("owner_user_id",),(AuthUser.id,),name="fk_notification_preference_owner",ondelete="RESTRICT"),
        ForeignKeyConstraint(("profile_id","owner_user_id","is_synthetic"),(ProfileRoot.id,ProfileRoot.owner_user_id,ProfileRoot.is_synthetic),name="fk_notification_preference_profile",ondelete="RESTRICT"),
        ForeignKeyConstraint(("profile_version_id",),(ProfileVersion.id,),name="fk_notification_preference_version",ondelete="RESTRICT"),
        CheckConstraint("version BETWEEN 1 AND 2147483647",name="ck_notification_preference_version"),
        CheckConstraint("(enabled AND session_id IS NOT NULL AND profile_id IS NOT NULL AND profile_version_id IS NOT NULL AND profile_sha256 IS NOT NULL AND admission_id IS NOT NULL AND consent_id IS NOT NULL AND declaration_id IS NOT NULL AND notice_id IS NOT NULL AND policy_version IS NOT NULL AND notice_sha256 IS NOT NULL) OR (NOT enabled AND session_id IS NULL AND profile_id IS NULL AND profile_version_id IS NULL AND profile_sha256 IS NULL AND admission_id IS NULL AND consent_id IS NULL AND declaration_id IS NULL AND notice_id IS NULL AND policy_version IS NULL AND notice_sha256 IS NULL)",name="ck_notification_preference_binding"),
        CheckConstraint("profile_sha256 IS NULL OR (length(profile_sha256)=64 AND profile_sha256 ~ '^[0-9a-f]{64}$' AND length(notice_sha256)=64 AND notice_sha256 ~ '^[0-9a-f]{64}$')",name="ck_notification_preference_hash"),
    )


class InboxNotification(JobsBase):
    __tablename__ = "inbox_notifications"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    job_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    event_id: Mapped[UUID] = mapped_column(nullable=False)
    assessment_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_version_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_version: Mapped[int] = mapped_column(Integer, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_request_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (
        UniqueConstraint("event_id","owner_user_id","assessment_id",name="uq_inbox_notification_event_owner"),
        UniqueConstraint("job_id",name="uq_inbox_notification_job"),
        ForeignKeyConstraint(("job_id","owner_user_id","is_synthetic"),(DurableJob.id,DurableJob.owner_user_id,DurableJob.is_synthetic),name="fk_inbox_notification_job_owner",ondelete="RESTRICT"),
        ForeignKeyConstraint(("event_id",),(ChangeEvent.id,),name="fk_inbox_notification_event",ondelete="RESTRICT"),
        ForeignKeyConstraint(("assessment_id",),(EligibilityAssessment.id,),name="fk_inbox_notification_assessment",ondelete="RESTRICT"),
        ForeignKeyConstraint(("profile_id","owner_user_id","is_synthetic"),(ProfileRoot.id,ProfileRoot.owner_user_id,ProfileRoot.is_synthetic),name="fk_inbox_notification_profile",ondelete="RESTRICT"),
        ForeignKeyConstraint(("profile_version_id",),(ProfileVersion.id,),name="fk_inbox_notification_version",ondelete="RESTRICT"),
        CheckConstraint("read_version IN (1,2) AND ((read_version=1 AND read_at IS NULL AND read_request_sha256 IS NULL) OR (read_version=2 AND read_at IS NOT NULL AND read_request_sha256 IS NOT NULL))",name="ck_inbox_notification_read"),
        CheckConstraint("expires_at>created_at AND expires_at<=(((created_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC') AND (read_at IS NULL OR (read_at>=created_at AND read_at<expires_at))",name="ck_inbox_notification_ttl"),
        CheckConstraint("length(profile_sha256)=64 AND profile_sha256 ~ '^[0-9a-f]{64}$' AND length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(payload)='object' AND octet_length(payload::text)<=8192",name="ck_inbox_notification_payload"),
        Index("ix_inbox_notification_owner","owner_user_id","id"),
    )
