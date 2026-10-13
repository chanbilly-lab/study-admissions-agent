"""Frozen T10 responsibility events, without user/content foreign keys."""

from alembic import op
import sqlalchemy as sa

revision = "0006_audit_t10"
down_revision = "0005_shared_grants_t09"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auth_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_kind", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_session_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("object_type", sa.String(24), nullable=True),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("object_version", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(32), nullable=False),
        sa.Column("request_id", sa.String(32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('auth.login.start','auth.login.consume','auth.login.complete','auth.login.cancel','auth.logout','auth.role.assign','auth.role.revoke','authorization.owned.check','authorization.owned.list','authorization.owned.register','authorization.owned.execute','authorization.capability.check','privacy.adult.declare','privacy.admission.invalidate','privacy.core.confirm','privacy.core.withdraw','sharing.grant.create','sharing.grant.accept','sharing.grant.revoke','sharing.read','sharing.list','sharing.execute_read','audit.read','audit.purge','catalog.import','catalog.review','catalog.publish','catalog.withdraw','export.create','deletion.accept','administrator.action')", name="ck_audit_action_whitelist"),
        sa.CheckConstraint("reason_code IN ('OK','UNAUTHORIZED','FORBIDDEN','NOT_FOUND','CONFLICT','VALIDATION_ERROR','SERVICE_UNAVAILABLE','INTERNAL_ERROR')", name="ck_audit_reason_whitelist"),
        sa.CheckConstraint("object_type IS NULL OR object_type IN ('login_transaction','session','user','profile','plan','attachment','export','job','admission','consent','access_grant','catalog_release','import','deletion_job','audit_event')", name="ck_audit_type_whitelist"),
        sa.CheckConstraint("(actor_kind = 'user' AND actor_user_id IS NOT NULL) OR "
                           "(actor_kind IN ('anonymous', 'system') AND actor_user_id IS NULL AND actor_session_id IS NULL)", name="ck_audit_actor"),
        sa.CheckConstraint("outcome IN ('succeeded', 'denied', 'failed')", name="ck_audit_outcome"),
        sa.CheckConstraint("(outcome = 'succeeded' AND reason_code = 'OK') OR (outcome <> 'succeeded' AND reason_code <> 'OK')", name="ck_audit_reason"),
        sa.CheckConstraint("object_id IS NULL OR object_type IS NOT NULL", name="ck_audit_object_type"),
        sa.CheckConstraint("object_version IS NULL OR (object_id IS NOT NULL AND object_version > 0)", name="ck_audit_version"),
        sa.CheckConstraint("outcome = 'succeeded' OR (object_id IS NULL AND object_version IS NULL)", name="ck_audit_failed_reference"),
        sa.CheckConstraint("length(request_id) = 32 AND policy_version = 'T10_audit_v1'", name="ck_audit_context"),
        sa.CheckConstraint("expires_at > occurred_at", name="ck_audit_retention"))
    op.create_index("ix_audit_actor", "auth_audit_events", ["actor_user_id", "occurred_at", "id"])
    op.create_index("ix_audit_action", "auth_audit_events", ["action", "occurred_at", "id"])
    op.create_index("ix_audit_expiry", "auth_audit_events", ["expires_at", "id"])
    op.create_index("ix_audit_request", "auth_audit_events", ["request_id"])


def downgrade():
    op.drop_table("auth_audit_events")
