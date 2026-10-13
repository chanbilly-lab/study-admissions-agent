"""Independent authentication metadata, separate from the frozen M0 tables."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AuthBase(DeclarativeBase):
    pass


def exact_text(length: int):
    return String(length).with_variant(String(length, collation="C"), "postgresql")


class AuthUser(AuthBase):
    __tablename__ = "auth_users"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("status IN ('active', 'disabled')", name="ck_auth_user_status"),)


class AuthIdentity(AuthBase):
    __tablename__ = "auth_identities"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False)
    issuer: Mapped[str] = mapped_column(exact_text(2048), nullable=False)
    subject: Mapped[str] = mapped_column(exact_text(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_auth_identity_issuer_subject"),
        CheckConstraint("length(issuer) > 0 AND length(subject) > 0", name="ck_auth_identity_nonempty"),
        Index("ix_auth_identity_user", "user_id"),
    )


class LoginTransaction(AuthBase):
    __tablename__ = "auth_login_transactions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    state_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    browser_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str] = mapped_column(exact_text(2048), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    encrypted_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("length(state_digest) = 64 AND length(browser_digest) = 64", name="ck_auth_login_digests"),
        CheckConstraint("expires_at > issued_at", name="ck_auth_login_lifetime"),
        CheckConstraint("consumed_at IS NULL OR consumed_at >= issued_at", name="ck_auth_login_consumed_time"),
        CheckConstraint("(consumed_at IS NULL AND encrypted_context IS NOT NULL) OR "
                        "(consumed_at IS NOT NULL AND encrypted_context IS NULL)", name="ck_auth_login_consumption"),
        Index("ix_auth_login_expiry", "expires_at"),
    )


class AuthSession(AuthBase):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False)
    session_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    csrf_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    csrf_encrypted_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_issuer: Mapped[str | None] = mapped_column(exact_text(2048), nullable=True)
    verified_client_id: Mapped[str | None] = mapped_column(exact_text(255), nullable=True)
    assurance_acr: Mapped[str | None] = mapped_column(exact_text(255), nullable=True)
    assurance_amr: Mapped[list[str] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    assurance_auth_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("length(session_digest) = 64", name="ck_auth_session_digest"),
        CheckConstraint("expires_at > created_at", name="ck_auth_session_lifetime"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_auth_session_revocation"),
        CheckConstraint("(csrf_digest IS NULL AND csrf_encrypted_token IS NULL) OR "
                        "(csrf_digest IS NOT NULL AND length(csrf_digest) = 64 AND csrf_encrypted_token IS NOT NULL)",
                        name="ck_auth_session_csrf_pair"),
        CheckConstraint("(verified_issuer IS NULL AND verified_client_id IS NULL AND assurance_acr IS NULL "
                        "AND assurance_amr IS NULL AND assurance_auth_time IS NULL) OR "
                        "(verified_issuer IS NOT NULL AND length(verified_issuer) > 0 "
                        "AND verified_client_id IS NOT NULL AND length(verified_client_id) > 0)",
                        name="ck_auth_session_assurance_provenance"),
        CheckConstraint("assurance_auth_time IS NULL OR assurance_auth_time <= created_at",
                        name="ck_auth_session_assurance_time"),
        Index("ix_auth_session_user", "user_id"),
        Index("ix_auth_session_expiry", "expires_at"),
    )


class AuthUserRole(AuthBase):
    __tablename__ = "auth_user_roles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id", ondelete="RESTRICT"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("role IN ('student', 'data_admin', 'operations')", name="ck_auth_role_name"),
        CheckConstraint("expires_at IS NULL OR expires_at > granted_at", name="ck_auth_role_lifetime"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= granted_at", name="ck_auth_role_revocation"),
    )


class AuthOwnedResource(AuthBase):
    """Ownership authority only; domain content, paths and file bytes belong elsewhere."""

    __tablename__ = "auth_owned_resources"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    __table_args__ = (
        UniqueConstraint("id", "owner_user_id", name="uq_auth_resource_id_owner"),
        ForeignKeyConstraint(["parent_id", "owner_user_id"],
            ["auth_owned_resources.id", "auth_owned_resources.owner_user_id"],
            name="fk_auth_resource_parent_owner", ondelete="RESTRICT"),
        CheckConstraint("resource_type IN ('profile', 'plan', 'attachment', 'export', 'job')", name="ck_auth_resource_type"),
        CheckConstraint("status IN ('active', 'deleted')", name="ck_auth_resource_status"),
        CheckConstraint("version > 0", name="ck_auth_resource_version"),
        CheckConstraint("(resource_type IN ('profile', 'plan') AND parent_id IS NULL) OR "
                        "(resource_type IN ('attachment', 'export', 'job') AND parent_id IS NOT NULL)",
                        name="ck_auth_resource_parent_shape"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_auth_resource_not_self_parent"),
        Index("ix_auth_resource_owner_scope", "owner_user_id", "resource_type", "status", "id"),
        Index("ix_auth_resource_parent_owner", "parent_id", "owner_user_id"),
    )
