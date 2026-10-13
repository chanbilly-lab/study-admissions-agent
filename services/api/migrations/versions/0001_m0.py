"""Frozen initial M0 schema, portable between PostgreSQL and the offline test stand-in."""
from alembic import op
import sqlalchemy as sa

revision = "0001_m0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "institutions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "offerings",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("institution_id", sa.String(100), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("entry_year", sa.Integer(), nullable=False),
        sa.Column("province", sa.String(30), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_offerings_country", "offerings", ["country"])
    op.create_index("ix_offerings_entry_year", "offerings", ["entry_year"])
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("document_version_id", sa.String(100), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("raw_document", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "rules",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("offering_id", sa.String(100), sa.ForeignKey("offerings.id"), nullable=False),
        sa.Column("evidence_id", sa.String(100), sa.ForeignKey("evidence.id"), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_rules_offering_id", "rules", ["offering_id"])
    op.create_table(
        "profile_versions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("profile_id", sa.String(100), nullable=False),
        sa.Column("owner_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("profile_id", "version", name="uq_profile_version"),
    )
    op.create_index("ix_profile_versions_owner_id", "profile_versions", ["owner_id"])
    op.create_table(
        "eligibility_results",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("owner_id", sa.String(100), nullable=False),
        sa.Column("profile_version_id", sa.String(100), sa.ForeignKey("profile_versions.id"), nullable=False),
        sa.Column("offering_id", sa.String(100), sa.ForeignKey("offerings.id"), nullable=False),
        sa.Column("ruleset_version", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_eligibility_results_owner_id", "eligibility_results", ["owner_id"])
    op.create_index("ix_eligibility_results_profile_version_id", "eligibility_results", ["profile_version_id"])
    op.create_table(
        "plan_drafts",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("owner_id", sa.String(100), nullable=False),
        sa.Column("profile_version_id", sa.String(100), sa.ForeignKey("profile_versions.id"), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_plan_drafts_owner_id", "plan_drafts", ["owner_id"])
    op.create_index("ix_plan_drafts_profile_version_id", "plan_drafts", ["profile_version_id"])


def downgrade():
    for table in ("plan_drafts", "eligibility_results", "profile_versions", "rules", "evidence", "offerings", "institutions"):
        op.drop_table(table)
