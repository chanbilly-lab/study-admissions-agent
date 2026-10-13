"""Frozen private assessment results; UPDATE immutable, trusted DELETE available."""

from alembic import op

revision = "0001_assessments_t28"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
IF (SELECT count(*) FROM auth_alembic_version) <> 1 OR (SELECT min(version_num) FROM auth_alembic_version) <> '0006_audit_t10' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM idempotency_alembic_version) <> 1 OR (SELECT min(version_num) FROM idempotency_alembic_version) <> '0001_idempotency_t49' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM catalog_alembic_version) <> 1 OR (SELECT min(version_num) FROM catalog_alembic_version) <> '0003_catalog_sources_t13' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM storage_alembic_version) <> 1 OR (SELECT min(version_num) FROM storage_alembic_version) <> '0001_storage_t14' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM imports_alembic_version) <> 1 OR (SELECT min(version_num) FROM imports_alembic_version) <> '0001_imports_t15' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM evidence_alembic_version) <> 1 OR (SELECT min(version_num) FROM evidence_alembic_version) <> '0001_evidence_t16' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM facts_alembic_version) <> 1 OR (SELECT min(version_num) FROM facts_alembic_version) <> '0001_facts_t17' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM reviews_alembic_version) <> 1 OR (SELECT min(version_num) FROM reviews_alembic_version) <> '0001_reviews_t18' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM releases_alembic_version) <> 1 OR (SELECT min(version_num) FROM releases_alembic_version) <> '0001_releases_t19' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM profiles_alembic_version) <> 1 OR (SELECT min(version_num) FROM profiles_alembic_version) <> '0001_profiles_t23' THEN RAISE EXCEPTION 'Required assessment prerequisite is unavailable'; END IF;
END $$""")
    op.execute("""CREATE TABLE eligibility_assessments (
	id UUID NOT NULL,
	version INTEGER NOT NULL,
	owner_user_id UUID NOT NULL,
	profile_id UUID NOT NULL,
	profile_version_id UUID NOT NULL,
	profile_version INTEGER NOT NULL,
	profile_is_synthetic BOOLEAN NOT NULL,
	dataset_id UUID NOT NULL,
	release_id UUID NOT NULL,
	entry_year INTEGER NOT NULL,
	catalogue_is_synthetic BOOLEAN NOT NULL,
	assessment_at TIMESTAMP WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	engine_version VARCHAR(20) NOT NULL,
	binding_mode VARCHAR(12) NOT NULL,
	payload JSONB NOT NULL,
	replay_snapshot JSONB NOT NULL,
	result_sha256 VARCHAR(64) NOT NULL,
	snapshot_sha256 VARCHAR(64) NOT NULL,
	audit_event_id UUID NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_assessment_profile_owner FOREIGN KEY(profile_id, owner_user_id, profile_is_synthetic) REFERENCES student_profiles (id, owner_user_id, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT fk_assessment_profile_version FOREIGN KEY(profile_version_id, profile_id, profile_version) REFERENCES student_profile_versions (id, profile_id, version) ON DELETE RESTRICT,
	CONSTRAINT fk_assessment_release_scope FOREIGN KEY(release_id, dataset_id, entry_year, catalogue_is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT ck_assessment_versions CHECK (version = 1 AND profile_version BETWEEN 1 AND 2147483647 AND entry_year BETWEEN 1 AND 9999),
	CONSTRAINT ck_assessment_engine_binding CHECK (engine_version = 'T28_v1' AND binding_mode IN ('unavailable','test_fixture')),
	CONSTRAINT ck_assessment_test_binding CHECK (binding_mode <> 'test_fixture' OR (profile_is_synthetic = true AND catalogue_is_synthetic = true)),
	CONSTRAINT ck_assessment_retention CHECK (expires_at > assessment_at AND expires_at <= (((assessment_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC')),
	CONSTRAINT ck_assessment_hashes CHECK (length(result_sha256)=64 AND result_sha256 ~ '^[0-9a-f]{64}$' AND length(snapshot_sha256)=64 AND snapshot_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_assessment_payload CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=262144 AND jsonb_typeof(replay_snapshot)='object' AND octet_length(replay_snapshot::text)<=524288)
)""")
    op.execute("""CREATE INDEX ix_assessment_expiry ON eligibility_assessments (expires_at, id)""")
    op.execute("""CREATE INDEX ix_assessment_owner_id ON eligibility_assessments (owner_user_id, id)""")
    op.execute("""CREATE FUNCTION assessments_reject_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Assessment results cannot be updated' USING ERRCODE = '23514'; END $$""")
    op.execute("""CREATE TRIGGER eligibility_assessments_no_update BEFORE UPDATE ON eligibility_assessments FOR EACH ROW EXECUTE FUNCTION assessments_reject_update()""")


def downgrade():
    op.execute("DROP TRIGGER eligibility_assessments_no_update ON eligibility_assessments")
    op.execute("DROP FUNCTION assessments_reject_update()")
    op.execute("DROP TABLE eligibility_assessments")
