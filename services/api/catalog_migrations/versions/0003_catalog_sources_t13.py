"""Frozen T13 source registration; metadata declarations do not grant publication."""

from alembic import op
import sqlalchemy as sa


revision = "0003_catalog_sources_t13"
down_revision = "0002_catalog_dates_t12"
branch_labels = None
depends_on = None


def exact_text(length):
    return sa.String(length).with_variant(sa.String(length, collation="C"), "postgresql")


def upgrade():
    op.create_table("catalog_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("reference_key", exact_text(100), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(("dataset_id", "is_synthetic"),
            ("catalog_datasets.id", "catalog_datasets.is_synthetic"), ondelete="RESTRICT", name="fk_catalog_source_dataset"),
        sa.UniqueConstraint("dataset_id", "id", "is_synthetic", name="uq_catalog_source_parent"),
        sa.UniqueConstraint("dataset_id", "reference_key", name="uq_catalog_source_reference"),
        sa.CheckConstraint("current_version BETWEEN 1 AND 2147483647", name="ck_catalog_source_current_version"),
        sa.CheckConstraint("length(reference_key) BETWEEN 1 AND 100", name="ck_catalog_source_reference_key_length"),
        sa.CheckConstraint("(is_synthetic = true AND substr(reference_key, 1, 5) = 'DEMO_') OR "
                           "(is_synthetic = false AND upper(substr(reference_key, 1, 5)) <> 'DEMO_')", name="ck_catalog_source_reference_key_synthetic"),
        sa.CheckConstraint("reference_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_catalog_source_reference_ascii"))
    op.create_table("catalog_source_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("publisher", exact_text(200), nullable=False),
        sa.Column("entry_url", exact_text(2048), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("data_type", sa.String(32), nullable=False),
        sa.Column("scope_note", sa.String(1000), nullable=False),
        sa.Column("authority_claim", sa.String(16), nullable=False),
        sa.Column("manual_import_permission", sa.String(7), nullable=False),
        sa.Column("publication_permission", sa.String(7), nullable=False),
        sa.Column("automated_fetch_permission", sa.String(7), nullable=False),
        sa.Column("license_basis", sa.String(2000), nullable=True),
        sa.Column("permission_record_reference", exact_text(100), nullable=True),
        sa.Column("recheck_days", sa.Integer(), nullable=False),
        sa.Column("manual_import_enabled", sa.Boolean(), nullable=False),
        sa.Column("responsible_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("permission_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recheck_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("auto_fetch_enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(("dataset_id", "source_id", "is_synthetic"),
            ("catalog_sources.dataset_id", "catalog_sources.id", "catalog_sources.is_synthetic"),
            ondelete="RESTRICT", name="fk_catalog_source_version_root"),
        sa.UniqueConstraint("dataset_id", "source_id", "version", name="uq_catalog_source_version"),
        sa.CheckConstraint("version BETWEEN 1 AND 2147483647", name="ck_catalog_source_version"),
        sa.CheckConstraint("length(publisher) BETWEEN 1 AND 200", name="ck_catalog_source_publisher"),
        sa.CheckConstraint("(is_synthetic = true AND substr(publisher, 1, 5) = 'DEMO_') OR "
                           "(is_synthetic = false AND upper(substr(publisher, 1, 5)) <> 'DEMO_')", name="ck_catalog_source_publisher_synthetic"),
        sa.CheckConstraint("length(entry_url) BETWEEN 1 AND 2048 AND entry_url ~* '^https?://' "
                           "AND entry_url !~ '[[:space:]\\\\#]'", name="ck_catalog_source_url"),
        sa.CheckConstraint("purpose = 'admissions_reference'", name="ck_catalog_source_purpose"),
        sa.CheckConstraint("data_type IN ('entry_requirements', 'application_dates', 'regional_cutoffs', "
                           "'admission_observations', 'curriculum', 'outcomes', 'institution_directory')", name="ck_catalog_source_data_type"),
        sa.CheckConstraint("length(scope_note) BETWEEN 1 AND 1000", name="ck_catalog_source_scope_note"),
        sa.CheckConstraint("authority_claim IN ('unclassified', 'claimed_official', 'not_official')", name="ck_catalog_source_authority"),
        sa.CheckConstraint("manual_import_permission IN ('pending', 'denied', 'granted')", name="ck_catalog_source_manual_import_permission"),
        sa.CheckConstraint("publication_permission IN ('pending', 'denied', 'granted')", name="ck_catalog_source_publication_permission"),
        sa.CheckConstraint("automated_fetch_permission IN ('pending', 'denied', 'granted')", name="ck_catalog_source_automated_fetch_permission"),
        sa.CheckConstraint("(manual_import_permission = 'pending' AND publication_permission = 'pending' AND "
                           "automated_fetch_permission = 'pending' AND license_basis IS NULL AND permission_record_reference IS NULL "
                           "AND permission_reviewed_at IS NULL) OR "
                           "((manual_import_permission <> 'pending' OR publication_permission <> 'pending' OR "
                           "automated_fetch_permission <> 'pending') AND license_basis IS NOT NULL AND "
                           "permission_record_reference IS NOT NULL AND permission_reviewed_at IS NOT NULL "
                           "AND permission_reviewed_at = created_at)", name="ck_catalog_source_permission_basis"),
        sa.CheckConstraint("license_basis IS NULL OR length(license_basis) BETWEEN 1 AND 2000", name="ck_catalog_source_license_basis"),
        sa.CheckConstraint("permission_record_reference IS NULL OR "
                           "permission_record_reference ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_catalog_source_permission_reference"),
        sa.CheckConstraint("permission_record_reference IS NULL OR "
                           "(is_synthetic = true AND substr(permission_record_reference, 1, 5) = 'DEMO_') OR "
                           "(is_synthetic = false AND upper(substr(permission_record_reference, 1, 5)) <> 'DEMO_')", name="ck_catalog_source_permission_synthetic"),
        sa.CheckConstraint("recheck_days BETWEEN 1 AND 730", name="ck_catalog_source_recheck_days"),
        sa.CheckConstraint("recheck_due_at > created_at AND recheck_due_at = "
                           "least(((created_at AT TIME ZONE 'UTC') + recheck_days * interval '1 day') AT TIME ZONE 'UTC', "
                           "((created_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC')", name="ck_catalog_source_recheck_due"),
        sa.CheckConstraint("manual_import_enabled = false OR manual_import_permission = 'granted'", name="ck_catalog_source_manual_enabled"),
        sa.CheckConstraint("auto_fetch_enabled = false", name="ck_catalog_source_no_fetch"))


def downgrade():
    op.drop_table("catalog_source_versions")
    op.drop_table("catalog_sources")
