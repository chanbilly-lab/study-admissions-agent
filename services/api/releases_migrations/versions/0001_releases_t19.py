"""Frozen immutable releases, CAS state and transactional change/outbox records."""

from alembic import op

revision = "0001_releases_t19"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
IF (SELECT count(*) FROM auth_alembic_version) <> 1 OR (SELECT min(version_num) FROM auth_alembic_version) <> '0006_audit_t10' THEN RAISE EXCEPTION 'Required releases prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM catalog_alembic_version) <> 1 OR (SELECT min(version_num) FROM catalog_alembic_version) <> '0003_catalog_sources_t13' THEN RAISE EXCEPTION 'Required releases prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM storage_alembic_version) <> 1 OR (SELECT min(version_num) FROM storage_alembic_version) <> '0001_storage_t14' THEN RAISE EXCEPTION 'Required releases prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM imports_alembic_version) <> 1 OR (SELECT min(version_num) FROM imports_alembic_version) <> '0001_imports_t15' THEN RAISE EXCEPTION 'Required releases prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM evidence_alembic_version) <> 1 OR (SELECT min(version_num) FROM evidence_alembic_version) <> '0001_evidence_t16' THEN RAISE EXCEPTION 'Required releases prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM facts_alembic_version) <> 1 OR (SELECT min(version_num) FROM facts_alembic_version) <> '0001_facts_t17' THEN RAISE EXCEPTION 'Required releases prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM reviews_alembic_version) <> 1 OR (SELECT min(version_num) FROM reviews_alembic_version) <> '0001_reviews_t18' THEN RAISE EXCEPTION 'Required releases prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM idempotency_alembic_version) <> 1 OR (SELECT min(version_num) FROM idempotency_alembic_version) <> '0001_idempotency_t49' THEN RAISE EXCEPTION 'Required releases prerequisite is unavailable'; END IF;
END $$""")
    op.execute("""CREATE TABLE catalog_releases (
	id UUID NOT NULL,
	version INTEGER NOT NULL,
	dataset_id UUID NOT NULL,
	entry_year INTEGER NOT NULL,
	kind VARCHAR(12) NOT NULL,
	is_synthetic BOOLEAN NOT NULL,
	valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
	valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
	content_sha256 VARCHAR(64) NOT NULL,
	requirements_version VARCHAR(64) NOT NULL,
	ruleset_version VARCHAR(64),
	replaces_release_id UUID,
	publisher_user_id UUID NOT NULL,
	audit_event_id UUID NOT NULL,
	published_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_release_dataset_mode FOREIGN KEY(dataset_id, is_synthetic) REFERENCES catalog_datasets (id, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT uq_release_scope UNIQUE (id, dataset_id, entry_year, is_synthetic),
	CONSTRAINT uq_release_content UNIQUE (content_sha256),
	CONSTRAINT ck_release_version CHECK (version = 1 AND entry_year BETWEEN 1 AND 9999),
	CONSTRAINT ck_release_kind CHECK ((kind = 'formal' AND is_synthetic = false) OR (kind = 'test_fixture' AND is_synthetic = true)),
	CONSTRAINT ck_release_interval_rules CHECK (valid_from < valid_until AND ruleset_version IS NULL),
	CONSTRAINT ck_release_hashes CHECK (content_sha256 ~ '^[0-9a-f]{64}$' AND requirements_version ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_release_no_self_replace CHECK (replaces_release_id IS NULL OR replaces_release_id <> id),
	CONSTRAINT fk_release_replaces_scope FOREIGN KEY(replaces_release_id, dataset_id, entry_year, is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT
)""")
    op.execute("""CREATE TABLE catalog_change_events (
	id UUID NOT NULL,
	release_id UUID NOT NULL,
	dataset_id UUID NOT NULL,
	entry_year INTEGER NOT NULL,
	is_synthetic BOOLEAN NOT NULL,
	event_type VARCHAR(9) NOT NULL,
	state_revision INTEGER NOT NULL,
	related_release_id UUID,
	reason_code VARCHAR(18),
	actor_user_id UUID NOT NULL,
	audit_event_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_release_event_scope FOREIGN KEY(release_id, dataset_id, entry_year, is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT fk_release_event_related FOREIGN KEY(related_release_id, dataset_id, entry_year, is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT uq_release_event_revision UNIQUE (release_id, state_revision),
	CONSTRAINT ck_release_event_shape CHECK ((event_type = 'published' AND state_revision = 1 AND related_release_id IS NULL AND reason_code IS NULL) OR (event_type = 'replaced' AND state_revision BETWEEN 2 AND 2147483647 AND related_release_id IS NOT NULL AND related_release_id <> release_id AND reason_code IS NULL) OR (event_type = 'withdrawn' AND state_revision BETWEEN 2 AND 2147483647 AND related_release_id IS NULL AND reason_code IS NOT NULL AND reason_code IN ('INCORRECT_FACT','RIGHTS_REVOKED','SOURCE_UNAVAILABLE','ADMIN_REQUEST')))
)""")
    op.execute("""CREATE TABLE catalog_release_members (
	id UUID NOT NULL,
	release_id UUID NOT NULL,
	dataset_id UUID NOT NULL,
	entry_year INTEGER NOT NULL,
	is_synthetic BOOLEAN NOT NULL,
	fact_id UUID NOT NULL,
	logical_key_hash VARCHAR(64) NOT NULL,
	decision_id UUID NOT NULL,
	case_revision INTEGER NOT NULL,
	offering_id UUID NOT NULL,
	offering_version INTEGER NOT NULL,
	source_id UUID NOT NULL,
	source_version INTEGER NOT NULL,
	evidence_id UUID NOT NULL,
	file_id UUID NOT NULL,
	fact_sha256 VARCHAR(64) NOT NULL,
	scope_sha256 VARCHAR(64) NOT NULL,
	evidence_sha256 VARCHAR(64) NOT NULL,
	source_sha256 VARCHAR(64) NOT NULL,
	file_sha256 VARCHAR(64) NOT NULL,
	file_metadata_sha256 VARCHAR(64) NOT NULL,
	public_evidence BOOLEAN NOT NULL,
	snapshot JSONB NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_release_member_scope FOREIGN KEY(release_id, dataset_id, entry_year, is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT fk_release_member_fact FOREIGN KEY(fact_id, logical_key_hash) REFERENCES fact_candidates (id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT fk_release_member_decision FOREIGN KEY(decision_id, fact_id, logical_key_hash) REFERENCES review_decisions (id, fact_id, logical_key_hash) ON DELETE RESTRICT,
	CONSTRAINT fk_release_member_offering FOREIGN KEY(dataset_id, offering_id, offering_version) REFERENCES catalog_offering_versions (dataset_id, offering_id, version) ON DELETE RESTRICT,
	CONSTRAINT fk_release_member_source FOREIGN KEY(dataset_id, source_id, source_version) REFERENCES catalog_source_versions (dataset_id, source_id, version) ON DELETE RESTRICT,
	CONSTRAINT fk_release_member_evidence FOREIGN KEY(evidence_id) REFERENCES evidence_snippets (id) ON DELETE RESTRICT,
	CONSTRAINT fk_release_member_file FOREIGN KEY(file_id) REFERENCES storage_objects (id) ON DELETE RESTRICT,
	CONSTRAINT uq_release_member_fact UNIQUE (release_id, fact_id),
	CONSTRAINT uq_release_member_logical UNIQUE (release_id, logical_key_hash),
	CONSTRAINT ck_release_member_versions CHECK (entry_year BETWEEN 1 AND 9999 AND case_revision BETWEEN 1 AND 2147483647 AND offering_version BETWEEN 1 AND 2147483647 AND source_version BETWEEN 1 AND 2147483647),
	CONSTRAINT ck_release_member_hashes CHECK (logical_key_hash ~ '^[0-9a-f]{64}$' AND fact_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$' AND evidence_sha256 ~ '^[0-9a-f]{64}$' AND source_sha256 ~ '^[0-9a-f]{64}$' AND file_sha256 ~ '^[0-9a-f]{64}$' AND file_metadata_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_release_member_snapshot CHECK (jsonb_typeof(snapshot) = 'object' AND octet_length(snapshot::text) <= 524288)
)""")
    op.execute("""CREATE TABLE catalog_release_states (
	release_id UUID NOT NULL,
	dataset_id UUID NOT NULL,
	entry_year INTEGER NOT NULL,
	is_synthetic BOOLEAN NOT NULL,
	status VARCHAR(9) NOT NULL,
	revision INTEGER NOT NULL,
	replaced_by_release_id UUID,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (release_id),
	CONSTRAINT fk_release_state_scope FOREIGN KEY(release_id, dataset_id, entry_year, is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT fk_release_state_successor FOREIGN KEY(replaced_by_release_id, dataset_id, entry_year, is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT ck_release_state_revision CHECK (status IN ('published','withdrawn','replaced') AND revision BETWEEN 1 AND 2147483647),
	CONSTRAINT ck_release_state_successor CHECK ((status = 'replaced' AND replaced_by_release_id IS NOT NULL AND replaced_by_release_id <> release_id) OR (status IN ('published','withdrawn') AND replaced_by_release_id IS NULL))
)""")
    op.execute("""CREATE TABLE catalog_outbox (
	id UUID NOT NULL,
	event_id UUID NOT NULL,
	status VARCHAR(7) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_release_outbox_event FOREIGN KEY(event_id) REFERENCES catalog_change_events (id) ON DELETE RESTRICT,
	CONSTRAINT uq_release_outbox_event UNIQUE (event_id),
	CONSTRAINT ck_release_outbox_pending CHECK (status = 'pending')
)""")
    op.execute("CREATE UNIQUE INDEX uq_release_current_published ON catalog_release_states (dataset_id, entry_year) WHERE status = 'published'")
    op.execute("""CREATE FUNCTION releases_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable release history cannot be changed' USING ERRCODE='23514'; END $$""")
    op.execute('CREATE TRIGGER releases_root_immutable BEFORE UPDATE OR DELETE ON catalog_releases FOR EACH ROW EXECUTE FUNCTION releases_reject_mutation()')
    op.execute('CREATE TRIGGER releases_members_immutable BEFORE UPDATE OR DELETE ON catalog_release_members FOR EACH ROW EXECUTE FUNCTION releases_reject_mutation()')
    op.execute('CREATE TRIGGER releases_events_immutable BEFORE UPDATE OR DELETE ON catalog_change_events FOR EACH ROW EXECUTE FUNCTION releases_reject_mutation()')


def downgrade():
    op.execute('DROP TRIGGER releases_events_immutable ON catalog_change_events')
    op.execute('DROP TRIGGER releases_members_immutable ON catalog_release_members')
    op.execute('DROP TRIGGER releases_root_immutable ON catalog_releases')
    op.execute("DROP FUNCTION releases_reject_mutation()")
    op.drop_table('catalog_outbox')
    op.drop_table('catalog_release_states')
    op.drop_table('catalog_release_members')
    op.drop_table('catalog_change_events')
    op.drop_table('catalog_releases')
