"""Session-bound CSRF and signed authentication assurance; no invented backfill."""

from alembic import op
import sqlalchemy as sa

revision = "0002_auth_t06"
down_revision = "0001_auth_t05"
branch_labels = None
depends_on = None


def exact_text(length):
    return sa.String(length).with_variant(sa.String(length, collation="C"), "postgresql")


def upgrade():
    # Batch mode also supports the explicit SQLite offline test substitute.
    with op.batch_alter_table("auth_sessions") as batch:
        batch.add_column(sa.Column("csrf_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("csrf_encrypted_token", sa.Text(), nullable=True))
        batch.add_column(sa.Column("verified_issuer", exact_text(2048), nullable=True))
        batch.add_column(sa.Column("verified_client_id", exact_text(255), nullable=True))
        batch.add_column(sa.Column("assurance_acr", exact_text(255), nullable=True))
        batch.add_column(sa.Column("assurance_amr", sa.JSON(none_as_null=True), nullable=True))
        batch.add_column(sa.Column("assurance_auth_time", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("ck_auth_session_csrf_pair",
            "(csrf_digest IS NULL AND csrf_encrypted_token IS NULL) OR "
            "(csrf_digest IS NOT NULL AND length(csrf_digest) = 64 AND csrf_encrypted_token IS NOT NULL)")
        batch.create_check_constraint("ck_auth_session_assurance_provenance",
            "(verified_issuer IS NULL AND verified_client_id IS NULL AND assurance_acr IS NULL "
            "AND assurance_amr IS NULL AND assurance_auth_time IS NULL) OR "
            "(verified_issuer IS NOT NULL AND length(verified_issuer) > 0 "
            "AND verified_client_id IS NOT NULL AND length(verified_client_id) > 0)")
        batch.create_check_constraint("ck_auth_session_assurance_time",
                                      "assurance_auth_time IS NULL OR assurance_auth_time <= created_at")


def downgrade():
    with op.batch_alter_table("auth_sessions") as batch:
        batch.drop_constraint("ck_auth_session_assurance_time", type_="check")
        batch.drop_constraint("ck_auth_session_assurance_provenance", type_="check")
        batch.drop_constraint("ck_auth_session_csrf_pair", type_="check")
        for column in ("assurance_auth_time", "assurance_amr", "assurance_acr",
                       "verified_client_id", "verified_issuer", "csrf_encrypted_token", "csrf_digest"):
            batch.drop_column(column)
