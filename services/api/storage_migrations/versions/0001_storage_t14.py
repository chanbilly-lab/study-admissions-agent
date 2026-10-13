"""Frozen T14 quarantine references; no file I/O or automatic release."""

from alembic import op
import sqlalchemy as sa


revision = "0001_storage_t14"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("storage_objects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("namespace", sa.String(17), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(14), nullable=False),
        sa.Column("media_type", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("owned_resource_id", sa.Uuid(), nullable=True),
        sa.Column("resource_version", sa.Integer(), nullable=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_version", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(("owned_resource_id", "owner_user_id"),
            ("auth_owned_resources.id", "auth_owned_resources.owner_user_id"),
            ondelete="RESTRICT", name="fk_storage_private_resource_owner"),
        sa.ForeignKeyConstraint(("dataset_id", "source_id", "source_version"),
            ("catalog_source_versions.dataset_id", "catalog_source_versions.source_id", "catalog_source_versions.version"),
            ondelete="RESTRICT", name="fk_storage_source_version"),
        sa.ForeignKeyConstraint(("dataset_id", "source_id", "is_synthetic"),
            ("catalog_sources.dataset_id", "catalog_sources.id", "catalog_sources.is_synthetic"),
            ondelete="RESTRICT", name="fk_storage_source_mode"),
        sa.CheckConstraint("namespace IN ('student_private', 'source_quarantine')", name="ck_storage_namespace"),
        sa.CheckConstraint("status IN ('quarantined', 'delete_pending', 'deleted')", name="ck_storage_status"),
        sa.CheckConstraint("media_type IN ('application/pdf', 'text/csv', 'application/json')", name="ck_storage_media_type"),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 10485760", name="ck_storage_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_storage_hash"),
        sa.CheckConstraint("expires_at > created_at AND expires_at <= "
                           "((created_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC'", name="ck_storage_expiry"),
        sa.CheckConstraint("(namespace = 'student_private' AND owner_user_id IS NOT NULL AND "
                           "owned_resource_id IS NOT NULL AND resource_version IS NOT NULL AND "
                           "owned_resource_id = id AND resource_version > 0 AND "
                           "dataset_id IS NULL AND source_id IS NULL AND source_version IS NULL) OR "
                           "(namespace = 'source_quarantine' AND owner_user_id IS NULL AND "
                           "owned_resource_id IS NULL AND resource_version IS NULL AND "
                           "dataset_id IS NOT NULL AND source_id IS NOT NULL AND source_version IS NOT NULL "
                           "AND source_version BETWEEN 1 AND 2147483647)", name="ck_storage_reference_shape"))
    op.create_index("ix_storage_owner_state", "storage_objects", ("owner_user_id", "status", "id"))
    op.create_index("ix_storage_source_version", "storage_objects", ("dataset_id", "source_id", "source_version"))
    op.create_index("ix_storage_expiry", "storage_objects", ("status", "expires_at"))


def downgrade():
    op.drop_table("storage_objects")
