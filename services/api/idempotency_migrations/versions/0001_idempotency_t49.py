"""Frozen local receipts and a deferred completed-at-commit constraint."""

from alembic import op
import sqlalchemy as sa

revision = "0001_idempotency_t49"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Also protects SQL emitted in offline mode when it is later applied.
    op.execute("""DO $$ BEGIN
        IF (SELECT count(*) FROM auth_alembic_version) <> 1
           OR (SELECT min(version_num) FROM auth_alembic_version) <> '0006_audit_t10'
        THEN RAISE EXCEPTION 'Required authentication schema is unavailable'; END IF;
    END $$""")
    op.create_table("idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(15), nullable=False),
        sa.Column("key_digest", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("resource_kind", sa.String(15), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("resource_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_user_id", "operation", "key_digest", name="uq_idempotency_actor_operation_key"),
        sa.CheckConstraint("operation IN ('catalog.import','catalog.publish','profile.create','plan.confirm')", name="ck_idempotency_operation"),
        sa.CheckConstraint("state IN ('processing','completed')", name="ck_idempotency_state"),
        sa.CheckConstraint("key_digest ~ '^[0-9a-f]{64}$' AND request_hash ~ '^[0-9a-f]{64}$'", name="ck_idempotency_hashes"),
        sa.CheckConstraint("expires_at > created_at AND expires_at <= (((created_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC')", name="ck_idempotency_expiry"),
        sa.CheckConstraint("(state = 'processing' AND resource_kind IS NULL AND resource_id IS NULL AND resource_version IS NULL AND completed_at IS NULL) OR (state = 'completed' AND resource_kind IS NOT NULL AND resource_id IS NOT NULL AND resource_version IS NOT NULL AND resource_version BETWEEN 1 AND 2147483647 AND completed_at IS NOT NULL AND completed_at >= created_at AND completed_at < expires_at)", name="ck_idempotency_completion"),
        sa.CheckConstraint("resource_kind IS NULL OR (operation = 'catalog.import' AND resource_kind = 'import') OR (operation = 'catalog.publish' AND resource_kind = 'catalog_release') OR (operation = 'profile.create' AND resource_kind = 'profile') OR (operation = 'plan.confirm' AND resource_kind = 'plan')", name="ck_idempotency_receipt_kind"),
    )
    op.create_index("ix_idempotency_expiry_id", "idempotency_records", ["expires_at", "id"])
    # TG_TABLE_SCHEMA/TG_TABLE_NAME bind this check to the actual triggering table,
    # even if trusted maintenance changes the connection's search_path.
    op.execute("""CREATE FUNCTION idempotency_require_completed() RETURNS trigger
    LANGUAGE plpgsql AS $$ DECLARE current_state text; BEGIN
        EXECUTE format('SELECT state FROM %I.%I WHERE id = $1', TG_TABLE_SCHEMA, TG_TABLE_NAME)
            INTO current_state USING NEW.id;
        IF current_state IS NOT NULL AND current_state <> 'completed' THEN
            RAISE EXCEPTION 'Idempotency receipt must complete in its transaction' USING ERRCODE = '23514';
        END IF;
        RETURN NULL;
    END $$""")
    op.execute("""CREATE CONSTRAINT TRIGGER idempotency_completed_at_commit
        AFTER INSERT OR UPDATE ON idempotency_records
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION idempotency_require_completed()""")


def downgrade():
    op.execute("DROP TRIGGER idempotency_completed_at_commit ON idempotency_records")
    op.execute("DROP FUNCTION idempotency_require_completed()")
    op.drop_index("ix_idempotency_expiry_id", table_name="idempotency_records")
    op.drop_table("idempotency_records")
