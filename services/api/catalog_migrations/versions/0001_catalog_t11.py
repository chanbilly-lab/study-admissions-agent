"""Frozen T11 candidate catalog; independent of M0 and auth migration chains."""

from alembic import op
import sqlalchemy as sa


revision = "0001_catalog_t11"
down_revision = None
branch_labels = None
depends_on = None


PROGRAM_SCOPES = ("degree", "course", "campus", "teaching_language", "progression_pathway")
OFFERING_SCOPES = ("intake", "application_cycle", "channel", "course_system", "pathway",
                   "applicant_category", "province", "exam_system", "subject_scope", "batch_group")


def text_type(length):
    return sa.String(length).with_variant(sa.String(length, collation="C"), "postgresql")


def reference_checks(prefix, *, name=False):
    checks = []
    for field in (("reference_key", "name") if name else ("reference_key",)):
        maximum = 200 if field == "name" else 100
        checks.append(sa.CheckConstraint(f"length({field}) BETWEEN 1 AND {maximum}",
                                         name=f"ck_{prefix}_{field}_length"))
        checks.append(sa.CheckConstraint(
            f"(is_synthetic = true AND substr({field}, 1, 5) = 'DEMO_') OR "
            f"(is_synthetic = false AND upper(substr({field}, 1, 5)) <> 'DEMO_')",
            name=f"ck_{prefix}_{field}_synthetic"))
    checks.append(sa.CheckConstraint("reference_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'",
                                     name=f"ck_{prefix}_reference_ascii"))
    return checks


def scopes(prefix, fields):
    entries = []
    for field in fields:
        column = f"{field}_key"
        entries.append(sa.Column(column, text_type(106), nullable=False))
        entries.append(sa.CheckConstraint(
            f"length({column}) BETWEEN 1 AND 106 AND "
            f"({column} IN ('unknown', 'not_applicable') OR "
            f"(substr({column}, 1, 6) = 'known:' AND length({column}) > 6))",
            name=f"ck_{prefix}_{field}_key"))
        entries.append(sa.CheckConstraint(
            f"octet_length({column}) <= 106 AND "
            f"{column} ~ '^(unknown|not_applicable|known:[A-Za-z0-9][A-Za-z0-9_.:+-]{{0,99}})$'",
            name=f"ck_{prefix}_{field}_ascii"))
    return entries


def upgrade():
    op.create_table("catalog_datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reference_key", text_type(100), nullable=False),
        sa.Column("data_mode", sa.String(8), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("visibility", sa.String(7), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint("reference_key", name="uq_catalog_dataset_reference"),
        sa.UniqueConstraint("id", "is_synthetic", name="uq_catalog_dataset_mode"),
        sa.CheckConstraint("(data_mode = 'demo' AND is_synthetic = true) OR "
                           "(data_mode = 'verified' AND is_synthetic = false)", name="ck_catalog_dataset_mode"),
        sa.CheckConstraint("visibility = 'private'", name="ck_catalog_dataset_visibility"),
        sa.CheckConstraint("revision BETWEEN 1 AND 2147483647", name="ck_catalog_dataset_revision"),
        *reference_checks("catalog_dataset"))
    op.create_table("catalog_institutions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("reference_key", text_type(100), nullable=False),
        sa.Column("name", text_type(200), nullable=False),
        sa.Column("country", text_type(2), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(("dataset_id", "is_synthetic"),
            ("catalog_datasets.id", "catalog_datasets.is_synthetic"),
            ondelete="RESTRICT", name="fk_catalog_institution_dataset"),
        sa.UniqueConstraint("dataset_id", "id", "is_synthetic", name="uq_catalog_institution_parent"),
        sa.UniqueConstraint("dataset_id", "reference_key", name="uq_catalog_institution_reference"),
        sa.CheckConstraint("length(country) = 2 AND country = upper(country)", name="ck_catalog_institution_country"),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_catalog_institution_country_ascii"),
        *reference_checks("catalog_institution", name=True))
    op.create_table("catalog_programs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("reference_key", text_type(100), nullable=False),
        sa.Column("name", text_type(200), nullable=False),
        sa.Column("study_level", text_type(16), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        *scopes("catalog_program", PROGRAM_SCOPES),
        sa.ForeignKeyConstraint(("dataset_id", "institution_id", "is_synthetic"),
            ("catalog_institutions.dataset_id", "catalog_institutions.id", "catalog_institutions.is_synthetic"),
            ondelete="RESTRICT", name="fk_catalog_program_institution"),
        sa.UniqueConstraint("dataset_id", "id", "is_synthetic", name="uq_catalog_program_parent"),
        sa.UniqueConstraint("dataset_id", "institution_id", "reference_key", "study_level",
            *(f"{field}_key" for field in PROGRAM_SCOPES), name="uq_catalog_program_scope"),
        sa.CheckConstraint("study_level = 'undergraduate'", name="ck_catalog_program_level"),
        *reference_checks("catalog_program", name=True))
    op.create_table("catalog_offerings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("reference_key", text_type(100), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("entry_year", sa.Integer(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        *scopes("catalog_offering", OFFERING_SCOPES),
        sa.ForeignKeyConstraint(("dataset_id", "program_id", "is_synthetic"),
            ("catalog_programs.dataset_id", "catalog_programs.id", "catalog_programs.is_synthetic"),
            ondelete="RESTRICT", name="fk_catalog_offering_program"),
        sa.UniqueConstraint("dataset_id", "id", "is_synthetic", name="uq_catalog_offering_parent"),
        sa.UniqueConstraint("dataset_id", "program_id", "entry_year",
            *(f"{field}_key" for field in OFFERING_SCOPES), name="uq_catalog_offering_scope"),
        sa.CheckConstraint("entry_year BETWEEN 1 AND 9999", name="ck_catalog_offering_year"),
        sa.CheckConstraint("current_version BETWEEN 1 AND 2147483647", name="ck_catalog_offering_current_version"),
        *reference_checks("catalog_offering"))
    op.create_table("catalog_offering_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("offering_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(("dataset_id", "offering_id", "is_synthetic"),
            ("catalog_offerings.dataset_id", "catalog_offerings.id", "catalog_offerings.is_synthetic"),
            ondelete="RESTRICT", name="fk_catalog_version_offering"),
        sa.UniqueConstraint("dataset_id", "offering_id", "version", name="uq_catalog_offering_version"),
        sa.CheckConstraint("version BETWEEN 1 AND 2147483647", name="ck_catalog_offering_version"))


def downgrade():
    for table in ("catalog_offering_versions", "catalog_offerings", "catalog_programs",
                  "catalog_institutions", "catalog_datasets"):
        op.drop_table(table)
