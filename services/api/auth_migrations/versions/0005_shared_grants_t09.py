"""Frozen T09 exact metadata grants, separate from core consultation consent."""

from alembic import op
import sqlalchemy as sa

revision = "0005_shared_grants_t09"
down_revision = "0004_privacy_t08"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auth_sharing_states",
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("auth_users.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("revision >= 0", name="ck_sharing_revision"))
    op.create_table("auth_access_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(16), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("grantee_user_id", sa.Uuid(), sa.ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("owner_consent_id", sa.Uuid(), nullable=False),
        sa.Column("grantee_declaration_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("sharing_policy_version", sa.String(100), nullable=False),
        sa.Column("sharing_policy_hash", sa.String(64), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["resource_id", "owner_user_id"], ["auth_owned_resources.id", "auth_owned_resources.owner_user_id"],
                                name="fk_grant_resource_owner", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_consent_id", "owner_user_id"], ["privacy_admission_records.id", "privacy_admission_records.user_id"],
                                name="fk_grant_consent_owner", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["grantee_declaration_id", "grantee_user_id"], ["privacy_admission_records.id", "privacy_admission_records.user_id"],
                                name="fk_grant_declaration_recipient", ondelete="RESTRICT"),
        sa.CheckConstraint("owner_user_id <> grantee_user_id", name="ck_grant_distinct_subjects"),
        sa.CheckConstraint("resource_type IN ('profile', 'plan', 'attachment', 'export', 'job')", name="ck_grant_resource_type"),
        sa.CheckConstraint("resource_version > 0 AND version > 0", name="ck_grant_versions"),
        sa.CheckConstraint("expires_at > created_at", name="ck_grant_expiry"),
        sa.CheckConstraint("length(sharing_policy_version) > 0 AND length(sharing_policy_hash) = 64", name="ck_grant_policy"),
        sa.CheckConstraint("(state = 'pending' AND accepted_at IS NULL AND revoked_at IS NULL) OR "
                           "(state = 'accepted' AND accepted_at IS NOT NULL AND revoked_at IS NULL) OR "
                           "(state = 'revoked' AND revoked_at IS NOT NULL)", name="ck_grant_state"),
        sa.CheckConstraint("accepted_at IS NULL OR (accepted_at >= created_at AND accepted_at < expires_at)", name="ck_grant_accept_time"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_grant_revoke_time"))
    op.create_index("ix_grant_received", "auth_access_grants", ["grantee_user_id", "state", "expires_at", "id"])
    op.create_index("ix_grant_issued", "auth_access_grants", ["owner_user_id", "id"])
    op.create_index("ix_grant_resource", "auth_access_grants", ["resource_id", "id"])
    op.create_table("grant_fields",
        sa.Column("grant_id", sa.Uuid(), sa.ForeignKey("auth_access_grants.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("field", sa.String(16), primary_key=True),
        sa.CheckConstraint("field IN ('status', 'version')", name="ck_grant_field"))
    op.create_table("grant_actions",
        sa.Column("grant_id", sa.Uuid(), sa.ForeignKey("auth_access_grants.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("action", sa.String(16), primary_key=True),
        sa.CheckConstraint("action IN ('read', 'list')", name="ck_grant_action"))


def downgrade():
    op.drop_table("grant_actions")
    op.drop_table("grant_fields")
    op.drop_table("auth_access_grants")
    op.drop_table("auth_sharing_states")
