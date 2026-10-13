"""First authentication increment; independent of the retained M0 migration chain."""

from alembic import op
import sqlalchemy as sa

revision = "0001_auth_t05"
down_revision = None
branch_labels = None
depends_on = None


def exact_text(length):
    return sa.String(length).with_variant(sa.String(length, collation="C"), "postgresql")


def upgrade():
    op.create_table("auth_users", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_auth_user_status"))
    op.create_table("auth_identities", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("issuer", exact_text(2048), nullable=False), sa.Column("subject", exact_text(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_auth_identity_issuer_subject"),
        sa.CheckConstraint("length(issuer) > 0 AND length(subject) > 0", name="ck_auth_identity_nonempty"))
    op.create_index("ix_auth_identity_user", "auth_identities", ["user_id"])
    op.create_table("auth_login_transactions", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("state_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("browser_digest", sa.String(64), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False), sa.Column("issuer", exact_text(2048), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False), sa.Column("redirect_uri", sa.String(2048), nullable=False),
        sa.Column("encrypted_context", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(state_digest) = 64 AND length(browser_digest) = 64", name="ck_auth_login_digests"),
        sa.CheckConstraint("expires_at > issued_at", name="ck_auth_login_lifetime"),
        sa.CheckConstraint("consumed_at IS NULL OR consumed_at >= issued_at", name="ck_auth_login_consumed_time"),
        sa.CheckConstraint("(consumed_at IS NULL AND encrypted_context IS NOT NULL) OR "
                           "(consumed_at IS NOT NULL AND encrypted_context IS NULL)", name="ck_auth_login_consumption"))
    op.create_index("ix_auth_login_expiry", "auth_login_transactions", ["expires_at"])
    op.create_table("auth_sessions", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(session_digest) = 64", name="ck_auth_session_digest"),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_session_lifetime"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_auth_session_revocation"))
    op.create_index("ix_auth_session_user", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_session_expiry", "auth_sessions", ["expires_at"])


def downgrade():
    op.drop_table("auth_sessions")
    op.drop_table("auth_login_transactions")
    op.drop_table("auth_identities")
    op.drop_table("auth_users")
