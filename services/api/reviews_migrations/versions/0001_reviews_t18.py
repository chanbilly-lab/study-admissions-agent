"""Frozen current review selection and immutable human decision histories."""

from alembic import op

revision = "0001_reviews_t18"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
IF (SELECT count(*) FROM auth_alembic_version) <> 1 OR (SELECT min(version_num) FROM auth_alembic_version) <> '0006_audit_t10' THEN RAISE EXCEPTION 'Required reviews prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM catalog_alembic_version) <> 1 OR (SELECT min(version_num) FROM catalog_alembic_version) <> '0003_catalog_sources_t13' THEN RAISE EXCEPTION 'Required reviews prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM storage_alembic_version) <> 1 OR (SELECT min(version_num) FROM storage_alembic_version) <> '0001_storage_t14' THEN RAISE EXCEPTION 'Required reviews prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM imports_alembic_version) <> 1 OR (SELECT min(version_num) FROM imports_alembic_version) <> '0001_imports_t15' THEN RAISE EXCEPTION 'Required reviews prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM evidence_alembic_version) <> 1 OR (SELECT min(version_num) FROM evidence_alembic_version) <> '0001_evidence_t16' THEN RAISE EXCEPTION 'Required reviews prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM facts_alembic_version) <> 1 OR (SELECT min(version_num) FROM facts_alembic_version) <> '0001_facts_t17' THEN RAISE EXCEPTION 'Required reviews prerequisite is unavailable'; END IF;
END $$""")
    op.execute("""CREATE TABLE review_cases (
	id UUID NOT NULL,
	logical_key_hash VARCHAR(64) NOT NULL,
	revision INTEGER NOT NULL,
	chosen_fact_id UUID,
	current_decision_id UUID,
	is_synthetic BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_review_logical_key UNIQUE (logical_key_hash),
	CONSTRAINT uq_review_case_scope UNIQUE (id, logical_key_hash),
	CONSTRAINT fk_review_case_chosen_fact FOREIGN KEY(chosen_fact_id, logical_key_hash) REFERENCES fact_candidates (id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT ck_review_case_revision CHECK (logical_key_hash ~ '^[0-9a-f]{64}$' AND revision BETWEEN 0 AND 2147483647),
	CONSTRAINT ck_review_case_pointer CHECK ((revision = 0 AND chosen_fact_id IS NULL AND current_decision_id IS NULL) OR (revision > 0 AND current_decision_id IS NOT NULL)),
	CONSTRAINT ck_review_case_times CHECK (updated_at >= created_at)
)""")
    op.execute("""CREATE TABLE review_decisions (
	id UUID NOT NULL,
	case_id UUID NOT NULL,
	case_revision INTEGER NOT NULL,
	logical_key_hash VARCHAR(64) NOT NULL,
	fact_id UUID NOT NULL,
	action VARCHAR(7) NOT NULL,
	checks JSONB NOT NULL,
	return_reason VARCHAR(24),
	fact_sha256 VARCHAR(64) NOT NULL,
	conflicts_sha256 VARCHAR(64) NOT NULL,
	reviewer_user_id UUID NOT NULL,
	audit_event_id UUID NOT NULL,
	is_synthetic BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_review_decision_case FOREIGN KEY(case_id, logical_key_hash) REFERENCES review_cases (id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT fk_review_decision_fact FOREIGN KEY(fact_id, logical_key_hash) REFERENCES fact_candidates (id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT uq_review_decision_revision UNIQUE (case_id, case_revision),
	CONSTRAINT uq_review_decision_pointer UNIQUE (id, case_id),
	CONSTRAINT uq_review_resolution_parent UNIQUE (id, fact_id, logical_key_hash),
	CONSTRAINT ck_review_decision_action CHECK (case_revision BETWEEN 1 AND 2147483647 AND action IN ('approve','return')),
	CONSTRAINT ck_review_return_reason CHECK ((action = 'approve' AND return_reason IS NULL) OR (action = 'return' AND return_reason IS NOT NULL AND return_reason IN ('INVALID_VALUE','MISSING_EVIDENCE','SCOPE_MISMATCH','UNIT_MISMATCH','PERIOD_UNCLEAR','MISSING_CONTEXT','FOOTNOTE_UNRESOLVED','SOURCE_UNAVAILABLE','CONFLICT_UNRESOLVED','UNSUPPORTED_LITERAL'))),
	CONSTRAINT ck_review_checks CHECK (jsonb_typeof(checks) = 'array' AND jsonb_array_length(checks) = 10 AND octet_length(checks::text) <= 4096),
	CONSTRAINT ck_review_decision_hashes CHECK (logical_key_hash ~ '^[0-9a-f]{64}$' AND fact_sha256 ~ '^[0-9a-f]{64}$' AND conflicts_sha256 ~ '^[0-9a-f]{64}$')
)""")
    op.execute("""CREATE TABLE review_conflict_resolutions (
	id UUID NOT NULL,
	decision_id UUID NOT NULL,
	selected_fact_id UUID NOT NULL,
	other_fact_id UUID NOT NULL,
	logical_key_hash VARCHAR(64) NOT NULL,
	reason_code VARCHAR(24) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_review_resolution_decision FOREIGN KEY(decision_id, selected_fact_id, logical_key_hash) REFERENCES review_decisions (id, fact_id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT fk_review_resolution_other FOREIGN KEY(other_fact_id, logical_key_hash) REFERENCES fact_candidates (id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT uq_review_resolution_other UNIQUE (decision_id, other_fact_id),
	CONSTRAINT ck_review_resolution_scope CHECK (selected_fact_id <> other_fact_id AND logical_key_hash ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_review_resolution_reason CHECK (reason_code IN ('SELECTED_SUPPORTED','INCORRECT_VALUE','WRONG_CONTEXT','DUPLICATE_OR_EQUIVALENT'))
)""")
    op.execute('ALTER TABLE review_cases ADD CONSTRAINT fk_review_case_current_decision FOREIGN KEY(current_decision_id, id) REFERENCES review_decisions (id, case_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED')
    op.execute('CREATE INDEX ix_review_decision_fact ON review_decisions (fact_id, case_revision)')
    op.execute("""CREATE FUNCTION reviews_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable review history cannot be changed' USING ERRCODE='23514'; END $$""")
    op.execute('CREATE TRIGGER reviews_decisions_immutable BEFORE UPDATE OR DELETE ON review_decisions FOR EACH ROW EXECUTE FUNCTION reviews_reject_mutation()')
    op.execute('CREATE TRIGGER reviews_resolutions_immutable BEFORE UPDATE OR DELETE ON review_conflict_resolutions FOR EACH ROW EXECUTE FUNCTION reviews_reject_mutation()')


def downgrade():
    op.execute("DROP TRIGGER reviews_resolutions_immutable ON review_conflict_resolutions")
    op.execute("DROP TRIGGER reviews_decisions_immutable ON review_decisions")
    op.execute("DROP FUNCTION reviews_reject_mutation()")
    op.execute("ALTER TABLE review_cases DROP CONSTRAINT fk_review_case_current_decision")
    op.drop_table("review_conflict_resolutions")
    op.drop_table("review_decisions")
    op.drop_table("review_cases")
