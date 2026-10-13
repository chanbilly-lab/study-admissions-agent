"""Frozen independent immutable typed candidates and conflict discovery."""

from alembic import op

revision = "0001_facts_t17"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
IF (SELECT count(*) FROM auth_alembic_version) <> 1 OR (SELECT min(version_num) FROM auth_alembic_version) <> '0006_audit_t10' THEN RAISE EXCEPTION 'Required facts prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM catalog_alembic_version) <> 1 OR (SELECT min(version_num) FROM catalog_alembic_version) <> '0003_catalog_sources_t13' THEN RAISE EXCEPTION 'Required facts prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM storage_alembic_version) <> 1 OR (SELECT min(version_num) FROM storage_alembic_version) <> '0001_storage_t14' THEN RAISE EXCEPTION 'Required facts prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM imports_alembic_version) <> 1 OR (SELECT min(version_num) FROM imports_alembic_version) <> '0001_imports_t15' THEN RAISE EXCEPTION 'Required facts prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM evidence_alembic_version) <> 1 OR (SELECT min(version_num) FROM evidence_alembic_version) <> '0001_evidence_t16' THEN RAISE EXCEPTION 'Required facts prerequisite is unavailable'; END IF;
END $$""")
    op.execute("""CREATE TABLE fact_candidates (
	id UUID NOT NULL,
	version INTEGER NOT NULL,
	import_id UUID NOT NULL,
	import_row_id UUID NOT NULL,
	dataset_id UUID NOT NULL,
	offering_id UUID NOT NULL,
	offering_version INTEGER NOT NULL,
	entry_year INTEGER NOT NULL,
	evidence_id UUID,
	date_event_id UUID,
	payload JSONB NOT NULL,
	classification_hash VARCHAR(64) NOT NULL,
	natural_key_hash VARCHAR(64) NOT NULL,
	logical_key_hash VARCHAR(64) NOT NULL,
	value_hash VARCHAR(64) NOT NULL,
	row_sha256 VARCHAR(64) NOT NULL,
	scope_sha256 VARCHAR(64) NOT NULL,
	date_sha256 VARCHAR(64),
	evidence_sha256 VARCHAR(64),
	is_synthetic BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_fact_batch_mode FOREIGN KEY(import_id, dataset_id, is_synthetic) REFERENCES import_batches (id, dataset_id, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT fk_fact_import_row FOREIGN KEY(import_row_id) REFERENCES import_candidate_rows (id) ON DELETE RESTRICT,
	CONSTRAINT fk_fact_offering_version FOREIGN KEY(dataset_id, offering_id, offering_version) REFERENCES catalog_offering_versions (dataset_id, offering_id, version) ON DELETE RESTRICT,
	CONSTRAINT fk_fact_offering_mode FOREIGN KEY(dataset_id, offering_id, is_synthetic) REFERENCES catalog_offerings (dataset_id, id, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT fk_fact_evidence FOREIGN KEY(evidence_id) REFERENCES evidence_snippets (id) ON DELETE RESTRICT,
	CONSTRAINT fk_fact_date FOREIGN KEY(date_event_id) REFERENCES catalog_date_events (id) ON DELETE RESTRICT,
	CONSTRAINT uq_fact_natural UNIQUE (natural_key_hash),
	CONSTRAINT uq_fact_conflict_parent UNIQUE (id, logical_key_hash),
	CONSTRAINT ck_fact_versions CHECK (version = 1 AND offering_version BETWEEN 1 AND 2147483647 AND entry_year BETWEEN 1 AND 9999),
	CONSTRAINT ck_fact_payload CHECK (jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 262144),
	CONSTRAINT ck_fact_hashes CHECK (classification_hash ~ '^[0-9a-f]{64}$' AND natural_key_hash ~ '^[0-9a-f]{64}$' AND logical_key_hash ~ '^[0-9a-f]{64}$' AND value_hash ~ '^[0-9a-f]{64}$' AND row_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_fact_date_hash CHECK ((date_event_id IS NULL AND date_sha256 IS NULL) OR (date_event_id IS NOT NULL AND date_sha256 IS NOT NULL AND date_sha256 ~ '^[0-9a-f]{64}$')),
	CONSTRAINT ck_fact_evidence_hash CHECK ((evidence_id IS NULL AND evidence_sha256 IS NULL) OR (evidence_id IS NOT NULL AND evidence_sha256 IS NOT NULL AND evidence_sha256 ~ '^[0-9a-f]{64}$'))
)""")
    op.execute("""CREATE TABLE fact_conflicts (
	id UUID NOT NULL,
	left_id UUID NOT NULL,
	right_id UUID NOT NULL,
	logical_key_hash VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_fact_conflict_left FOREIGN KEY(left_id, logical_key_hash) REFERENCES fact_candidates (id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT fk_fact_conflict_right FOREIGN KEY(right_id, logical_key_hash) REFERENCES fact_candidates (id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT uq_fact_conflict_pair UNIQUE (left_id, right_id),
	CONSTRAINT ck_fact_conflict_pair CHECK (left_id < right_id AND logical_key_hash ~ '^[0-9a-f]{64}$')
)""")
    op.execute("CREATE INDEX ix_fact_logical_key ON fact_candidates (logical_key_hash, id)")
    op.execute("CREATE INDEX ix_fact_conflict_right ON fact_conflicts (right_id, left_id)")
    op.execute("""CREATE FUNCTION facts_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable facts cannot be changed' USING ERRCODE='23514'; END $$""")
    op.execute("CREATE TRIGGER facts_candidates_immutable BEFORE UPDATE OR DELETE ON fact_candidates FOR EACH ROW EXECUTE FUNCTION facts_reject_mutation()")
    op.execute("CREATE TRIGGER facts_conflicts_immutable BEFORE UPDATE OR DELETE ON fact_conflicts FOR EACH ROW EXECUTE FUNCTION facts_reject_mutation()")


def downgrade():
    op.execute("DROP TRIGGER facts_conflicts_immutable ON fact_conflicts")
    op.execute("DROP TRIGGER facts_candidates_immutable ON fact_candidates")
    op.execute("DROP FUNCTION facts_reject_mutation()")
    op.drop_table("fact_conflicts")
    op.drop_table("fact_candidates")
