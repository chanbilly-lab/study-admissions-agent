"""Exact metadata grants. No student content, file paths or guardian authority."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..models import AuthBase


class SharingState(AuthBase):
    __tablename__ = "auth_sharing_states"
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id", ondelete="RESTRICT"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (CheckConstraint("revision >= 0", name="ck_sharing_revision"),)


class AccessGrant(AuthBase):
    __tablename__ = "auth_access_grants"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    grantee_user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False)
    owner_consent_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    grantee_declaration_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    sharing_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    sharing_policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["resource_id", "owner_user_id"], ["auth_owned_resources.id", "auth_owned_resources.owner_user_id"],
                             name="fk_grant_resource_owner", ondelete="RESTRICT"),
        ForeignKeyConstraint(["owner_consent_id", "owner_user_id"], ["privacy_admission_records.id", "privacy_admission_records.user_id"],
                             name="fk_grant_consent_owner", ondelete="RESTRICT"),
        ForeignKeyConstraint(["grantee_declaration_id", "grantee_user_id"], ["privacy_admission_records.id", "privacy_admission_records.user_id"],
                             name="fk_grant_declaration_recipient", ondelete="RESTRICT"),
        CheckConstraint("owner_user_id <> grantee_user_id", name="ck_grant_distinct_subjects"),
        CheckConstraint("resource_type IN ('profile', 'plan', 'attachment', 'export', 'job')", name="ck_grant_resource_type"),
        CheckConstraint("resource_version > 0 AND version > 0", name="ck_grant_versions"),
        CheckConstraint("expires_at > created_at", name="ck_grant_expiry"),
        CheckConstraint("length(sharing_policy_version) > 0 AND length(sharing_policy_hash) = 64", name="ck_grant_policy"),
        CheckConstraint("(state = 'pending' AND accepted_at IS NULL AND revoked_at IS NULL) OR "
                        "(state = 'accepted' AND accepted_at IS NOT NULL AND revoked_at IS NULL) OR "
                        "(state = 'revoked' AND revoked_at IS NOT NULL)", name="ck_grant_state"),
        CheckConstraint("accepted_at IS NULL OR (accepted_at >= created_at AND accepted_at < expires_at)", name="ck_grant_accept_time"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_grant_revoke_time"),
        Index("ix_grant_received", "grantee_user_id", "state", "expires_at", "id"),
        Index("ix_grant_issued", "owner_user_id", "id"),
        Index("ix_grant_resource", "resource_id", "id"),
    )


class GrantField(AuthBase):
    __tablename__ = "grant_fields"
    grant_id: Mapped[UUID] = mapped_column(ForeignKey("auth_access_grants.id", ondelete="RESTRICT"), primary_key=True)
    field: Mapped[str] = mapped_column(String(16), primary_key=True)
    __table_args__ = (CheckConstraint("field IN ('status', 'version')", name="ck_grant_field"),)


class GrantAction(AuthBase):
    __tablename__ = "grant_actions"
    grant_id: Mapped[UUID] = mapped_column(ForeignKey("auth_access_grants.id", ondelete="RESTRICT"), primary_key=True)
    action: Mapped[str] = mapped_column(String(16), primary_key=True)
    __table_args__ = (CheckConstraint("action IN ('read', 'list')", name="ck_grant_action"),)
