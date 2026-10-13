"""Frozen T12 candidate dates; calculation cannot establish official evidence."""

from alembic import op
import sqlalchemy as sa


revision = "0002_catalog_dates_t12"
down_revision = "0001_catalog_t11"
branch_labels = None
depends_on = None


def exact_text(length):
    return sa.String(length).with_variant(sa.String(length, collation="C"), "postgresql")


def upgrade():
    op.create_table("catalog_date_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("offering_id", sa.Uuid(), nullable=False),
        sa.Column("offering_version", sa.Integer(), nullable=False),
        sa.Column("reference_key", exact_text(100), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("precision", sa.String(7), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=True),
        sa.Column("local_time", sa.Time(timezone=False), nullable=True),
        sa.Column("timezone", exact_text(100), nullable=True),
        sa.Column("source_alignment", sa.String(8), nullable=False),
        sa.Column("evidence_reference", exact_text(100), nullable=True),
        sa.Column("conversion_status", sa.String(20), nullable=False),
        sa.Column("calculated_utc_instant", sa.DateTime(timezone=True), nullable=True),
        sa.Column("utc_instant", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_state", sa.String(5), nullable=False),
        sa.Column("evidence_state", sa.String(10), nullable=False),
        sa.Column("tzdata_version", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(("dataset_id", "offering_id", "offering_version"),
            ("catalog_offering_versions.dataset_id", "catalog_offering_versions.offering_id", "catalog_offering_versions.version"),
            ondelete="RESTRICT", name="fk_catalog_date_version"),
        sa.ForeignKeyConstraint(("dataset_id", "offering_id", "is_synthetic"),
            ("catalog_offerings.dataset_id", "catalog_offerings.id", "catalog_offerings.is_synthetic"),
            ondelete="RESTRICT", name="fk_catalog_date_offering"),
        sa.UniqueConstraint("dataset_id", "offering_id", "offering_version", "reference_key", name="uq_catalog_date_reference"),
        sa.CheckConstraint("offering_version BETWEEN 1 AND 2147483647", name="ck_catalog_date_version"),
        sa.CheckConstraint("event_type IN ('application_open', 'application_deadline', 'equal_consideration', "
                           "'materials_deadline', 'language_supplement', 'score_supplement', 'offer_acceptance', "
                           "'scholarship_deadline', 'enrollment')", name="ck_catalog_date_event_type"),
        sa.CheckConstraint("length(original_text) BETWEEN 1 AND 4000", name="ck_catalog_date_original_text"),
        sa.CheckConstraint("precision IN ('date', 'minute', 'second', 'unknown')", name="ck_catalog_date_precision"),
        sa.CheckConstraint("(precision = 'unknown' AND local_date IS NULL AND local_time IS NULL AND timezone IS NULL) OR "
                           "(precision = 'date' AND local_date IS NOT NULL AND local_time IS NULL) OR "
                           "(precision IN ('minute', 'second') AND local_date IS NOT NULL AND local_time IS NOT NULL)",
                           name="ck_catalog_date_local_fields"),
        sa.CheckConstraint("local_time IS NULL OR (local_time >= TIME '00:00:00' AND local_time < TIME '24:00:00' AND "
                           "((precision = 'minute' AND extract(second FROM local_time) = 0) OR "
                           "(precision = 'second' AND extract(second FROM local_time) = floor(extract(second FROM local_time)))))",
                           name="ck_catalog_date_time_precision"),
        sa.CheckConstraint("timezone IS NULL OR (length(timezone) BETWEEN 1 AND 100 AND "
                           "(timezone = 'UTC' OR timezone ~ '^(Africa|America|Antarctica|Arctic|Asia|Atlantic|Australia|Europe|Indian|Pacific)/[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$'))", name="ck_catalog_date_timezone"),
        sa.CheckConstraint("source_alignment IN ('pending', 'conflict')", name="ck_catalog_date_source_alignment"),
        sa.CheckConstraint("evidence_reference IS NULL OR "
                           "evidence_reference ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_catalog_date_evidence_reference"),
        sa.CheckConstraint("evidence_reference IS NULL OR "
                           "(is_synthetic = true AND substr(evidence_reference, 1, 5) = 'DEMO_') OR "
                           "(is_synthetic = false AND upper(substr(evidence_reference, 1, 5)) <> 'DEMO_')",
                           name="ck_catalog_date_evidence_synthetic"),
        sa.CheckConstraint("conversion_status IN ('unique', 'date_only', 'unknown', 'missing_timezone', 'ambiguous', "
                           "'nonexistent', 'source_conflict', 'out_of_range')", name="ck_catalog_date_conversion_status"),
        sa.CheckConstraint("(source_alignment = 'conflict' AND conversion_status = 'source_conflict' AND calculated_utc_instant IS NULL) OR "
                           "(source_alignment = 'pending' AND conversion_status <> 'source_conflict')", name="ck_catalog_date_conflict"),
        sa.CheckConstraint("(conversion_status = 'unique' AND calculated_utc_instant IS NOT NULL AND "
                           "precision IN ('minute', 'second') AND local_date IS NOT NULL AND local_time IS NOT NULL AND timezone IS NOT NULL) OR "
                           "(conversion_status <> 'unique' AND calculated_utc_instant IS NULL)", name="ck_catalog_date_calculated_utc"),
        sa.CheckConstraint("utc_instant IS NULL AND review_state = 'draft' AND evidence_state = 'unresolved'", name="ck_catalog_date_unreviewed"),
        sa.CheckConstraint("tzdata_version = '2026.4'", name="ck_catalog_date_tzdata_version"),
        sa.CheckConstraint("length(reference_key) BETWEEN 1 AND 100", name="ck_catalog_date_reference_key_length"),
        sa.CheckConstraint("(is_synthetic = true AND substr(reference_key, 1, 5) = 'DEMO_') OR "
                           "(is_synthetic = false AND upper(substr(reference_key, 1, 5)) <> 'DEMO_')", name="ck_catalog_date_reference_key_synthetic"),
        sa.CheckConstraint("reference_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_catalog_date_reference_ascii"))


def downgrade():
    op.drop_table("catalog_date_events")
