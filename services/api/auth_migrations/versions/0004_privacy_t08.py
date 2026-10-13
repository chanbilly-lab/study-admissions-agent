"""Frozen T08 notice versions and append-only adult admission snapshots."""

from alembic import op
import sqlalchemy as sa

revision = "0004_privacy_t08"
down_revision = "0003_auth_t07"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("privacy_notice_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.String(100), nullable=False, unique=True),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("controller_reference", sa.String(255), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.CheckConstraint("length(version) > 0 AND length(policy_version) > 0 AND length(text) > 0 "
                           "AND length(controller_reference) > 0", name="ck_privacy_notice_nonempty"),
        sa.CheckConstraint("length(text_sha256) = 64", name="ck_privacy_notice_hash"),
        sa.CheckConstraint("review_status IN ('test_reviewed', 'reviewed')", name="ck_privacy_notice_review"))
    op.create_table("privacy_admission_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("age_band", sa.String(16), nullable=True),
        sa.Column("age_assurance", sa.String(16), nullable=False),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declaration_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declaration_notice_id", sa.Uuid(), sa.ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("consent_id", sa.Uuid(), nullable=True),
        sa.Column("consent_status", sa.String(16), nullable=False),
        sa.Column("consent_notice_id", sa.Uuid(), sa.ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("consent_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "revision", name="uq_privacy_admission_revision"),
        sa.UniqueConstraint("id", "user_id", name="uq_privacy_admission_id_user"),
        sa.ForeignKeyConstraint(["consent_id", "user_id"], ["privacy_admission_records.id", "privacy_admission_records.user_id"],
                                name="fk_privacy_consent_owner", ondelete="RESTRICT"),
        sa.CheckConstraint("revision > 0 AND length(policy_version) > 0", name="ck_privacy_admission_revision"),
        sa.CheckConstraint("event_type IN ('adult_declared', 'consent_confirmed', 'consent_withdrawn', 'admission_invalidated')",
                           name="ck_privacy_admission_event"),
        sa.CheckConstraint("(age_band IS NULL AND age_assurance = 'unknown' AND declared_at IS NULL "
                           "AND declaration_expires_at IS NULL AND declaration_notice_id IS NULL) OR "
                           "(age_band IS NOT NULL AND age_band = '18_plus' AND age_assurance = 'declared' AND declared_at IS NOT NULL "
                           "AND declaration_expires_at IS NOT NULL AND declaration_expires_at > declared_at AND declaration_notice_id IS NOT NULL)", name="ck_privacy_admission_age"),
        sa.CheckConstraint("consent_status IN ('not_confirmed', 'active', 'withdrawn', 'invalidated')", name="ck_privacy_consent_status"),
        sa.CheckConstraint("(consent_id IS NULL AND consent_notice_id IS NULL AND consent_confirmed_at IS NULL "
                           "AND consent_withdrawn_at IS NULL AND consent_status = 'not_confirmed') OR "
                           "(consent_id IS NOT NULL AND consent_notice_id IS NOT NULL AND consent_confirmed_at IS NOT NULL "
                           "AND consent_status IN ('active', 'withdrawn', 'invalidated'))", name="ck_privacy_consent_reference"),
        sa.CheckConstraint("(consent_status = 'withdrawn' AND consent_withdrawn_at IS NOT NULL "
                           "AND consent_withdrawn_at >= consent_confirmed_at) OR "
                           "(consent_status <> 'withdrawn' AND consent_withdrawn_at IS NULL)", name="ck_privacy_consent_withdrawal"),
        sa.CheckConstraint("consent_status <> 'active' OR (age_band IS NOT NULL AND age_band = '18_plus')", name="ck_privacy_active_adult"))
    op.create_index("ix_privacy_admission_current", "privacy_admission_records", ["user_id", "revision"])
    op.create_index("ix_privacy_admission_consent", "privacy_admission_records", ["consent_id", "user_id"])


def downgrade():
    op.drop_table("privacy_admission_records")
    op.drop_table("privacy_notice_versions")
