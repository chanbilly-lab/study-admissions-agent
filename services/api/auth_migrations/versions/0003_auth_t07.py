"""Application roles and private ownership metadata; no domain payload or users seeded."""

from alembic import op
import sqlalchemy as sa

revision = "0003_auth_t07"
down_revision = "0002_auth_t06"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auth_user_roles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("auth_users.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("role", sa.String(16), primary_key=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('student', 'data_admin', 'operations')", name="ck_auth_role_name"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > granted_at", name="ck_auth_role_lifetime"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= granted_at", name="ck_auth_role_revocation"))
    op.create_table("auth_owned_resources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resource_type", sa.String(16), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.UniqueConstraint("id", "owner_user_id", name="uq_auth_resource_id_owner"),
        sa.ForeignKeyConstraint(["parent_id", "owner_user_id"],
            ["auth_owned_resources.id", "auth_owned_resources.owner_user_id"],
            name="fk_auth_resource_parent_owner", ondelete="RESTRICT"),
        sa.CheckConstraint("resource_type IN ('profile', 'plan', 'attachment', 'export', 'job')", name="ck_auth_resource_type"),
        sa.CheckConstraint("status IN ('active', 'deleted')", name="ck_auth_resource_status"),
        sa.CheckConstraint("version > 0", name="ck_auth_resource_version"),
        sa.CheckConstraint("(resource_type IN ('profile', 'plan') AND parent_id IS NULL) OR "
                           "(resource_type IN ('attachment', 'export', 'job') AND parent_id IS NOT NULL)",
                           name="ck_auth_resource_parent_shape"),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_auth_resource_not_self_parent"))
    op.create_index("ix_auth_resource_owner_scope", "auth_owned_resources", ["owner_user_id", "resource_type", "status", "id"])
    op.create_index("ix_auth_resource_parent_owner", "auth_owned_resources", ["parent_id", "owner_user_id"])


def downgrade():
    op.drop_table("auth_owned_resources")
    op.drop_table("auth_user_roles")
