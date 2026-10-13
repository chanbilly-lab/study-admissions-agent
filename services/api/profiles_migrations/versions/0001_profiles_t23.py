"""Frozen declared profile roots and immutable-by-update confirmation history."""

from alembic import op

revision = "0001_profiles_t23"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
IF (SELECT count(*) FROM auth_alembic_version) <> 1 OR (SELECT min(version_num) FROM auth_alembic_version) <> '0006_audit_t10' THEN RAISE EXCEPTION 'Required profiles prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM idempotency_alembic_version) <> 1 OR (SELECT min(version_num) FROM idempotency_alembic_version) <> '0001_idempotency_t49' THEN RAISE EXCEPTION 'Required profiles prerequisite is unavailable'; END IF;
END $$""")
    op.execute("""CREATE TABLE student_profiles (
    id UUID NOT NULL,
    owner_user_id UUID NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    current_version INTEGER NOT NULL,
    current_version_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_student_profile_owner_mode UNIQUE (id, owner_user_id, is_synthetic),
    CONSTRAINT fk_student_profile_registry_owner FOREIGN KEY(id, owner_user_id) REFERENCES auth_owned_resources (id, owner_user_id) ON DELETE RESTRICT,
    CONSTRAINT ck_student_profile_version CHECK (current_version BETWEEN 1 AND 2147483647)
)""")
    op.execute("CREATE INDEX ix_student_profile_owner_id ON student_profiles (owner_user_id, id)")
    op.execute("""CREATE TABLE student_profile_versions (
    id UUID NOT NULL,
    profile_id UUID NOT NULL,
    owner_user_id UUID NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    version INTEGER NOT NULL,
    payload JSONB NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source VARCHAR(24) NOT NULL,
    admission_id UUID NOT NULL,
    consent_id UUID NOT NULL,
    declaration_id UUID NOT NULL,
    notice_id UUID NOT NULL,
    policy_version VARCHAR(100) NOT NULL,
    notice_sha256 VARCHAR(64) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_student_profile_version UNIQUE (profile_id, version),
    CONSTRAINT uq_student_profile_version_pointer UNIQUE (id, profile_id, version),
    CONSTRAINT fk_student_profile_version_owner_mode FOREIGN KEY(profile_id, owner_user_id, is_synthetic) REFERENCES student_profiles (id, owner_user_id, is_synthetic) ON DELETE RESTRICT,
    CONSTRAINT fk_student_profile_admission FOREIGN KEY(admission_id, owner_user_id) REFERENCES privacy_admission_records (id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_student_profile_consent FOREIGN KEY(consent_id, owner_user_id) REFERENCES privacy_admission_records (id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_student_profile_declaration FOREIGN KEY(declaration_id, owner_user_id) REFERENCES privacy_admission_records (id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_student_profile_notice FOREIGN KEY(notice_id) REFERENCES privacy_notice_versions (id) ON DELETE RESTRICT,
    CONSTRAINT ck_student_profile_snapshot_version CHECK (version BETWEEN 1 AND 2147483647),
    CONSTRAINT ck_student_profile_hashes CHECK (payload_sha256 ~ '^[0-9a-f]{64}$' AND notice_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_student_profile_payload CHECK (jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 65536),
    CONSTRAINT ck_student_profile_declaration_source CHECK (source = 'student_declared' AND length(policy_version) > 0),
    CONSTRAINT ck_student_profile_retention CHECK (expires_at > confirmed_at AND expires_at <= (((confirmed_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC'))
)""")
    op.execute("CREATE INDEX ix_student_profile_version_expiry ON student_profile_versions (expires_at, id)")
    op.execute("ALTER TABLE student_profiles ADD CONSTRAINT fk_student_profile_current_version FOREIGN KEY(current_version_id, id, current_version) REFERENCES student_profile_versions (id, profile_id, version) DEFERRABLE INITIALLY DEFERRED")
    op.execute("""CREATE FUNCTION profiles_reject_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Confirmed profile history cannot be changed' USING ERRCODE='23514'; END $$""")
    op.execute("CREATE TRIGGER student_profile_versions_no_update BEFORE UPDATE ON student_profile_versions FOR EACH ROW EXECUTE FUNCTION profiles_reject_update()")


def downgrade():
    op.execute("DROP TRIGGER student_profile_versions_no_update ON student_profile_versions")
    op.execute("DROP FUNCTION profiles_reject_update()")
    op.execute("ALTER TABLE student_profiles DROP CONSTRAINT fk_student_profile_current_version")
    op.drop_table("student_profile_versions")
    op.drop_table("student_profiles")
