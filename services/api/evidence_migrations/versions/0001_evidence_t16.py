"""Frozen independent document versions and scoped immutable evidence."""

from alembic import op

revision = "0001_evidence_t16"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
IF (SELECT count(*) FROM auth_alembic_version) <> 1 OR (SELECT min(version_num) FROM auth_alembic_version) <> '0006_audit_t10' THEN RAISE EXCEPTION 'Required evidence prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM catalog_alembic_version) <> 1 OR (SELECT min(version_num) FROM catalog_alembic_version) <> '0003_catalog_sources_t13' THEN RAISE EXCEPTION 'Required evidence prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM storage_alembic_version) <> 1 OR (SELECT min(version_num) FROM storage_alembic_version) <> '0001_storage_t14' THEN RAISE EXCEPTION 'Required evidence prerequisite is unavailable'; END IF;
END $$""")
    op.execute("""CREATE TABLE evidence_documents (
	id UUID NOT NULL,
	dataset_id UUID NOT NULL,
	source_id UUID NOT NULL,
	source_version INTEGER NOT NULL,
	document_reference VARCHAR(100) NOT NULL,
	language VARCHAR(7) NOT NULL,
	is_synthetic BOOLEAN NOT NULL,
	current_version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_evidence_document_source_version FOREIGN KEY(dataset_id, source_id, source_version) REFERENCES catalog_source_versions (dataset_id, source_id, version) ON DELETE RESTRICT,
	CONSTRAINT fk_evidence_document_source_mode FOREIGN KEY(dataset_id, source_id, is_synthetic) REFERENCES catalog_sources (dataset_id, id, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT uq_evidence_document_parent UNIQUE (id, dataset_id, is_synthetic),
	CONSTRAINT uq_evidence_document_reference UNIQUE (dataset_id, source_id, source_version, document_reference),
	CONSTRAINT ck_evidence_document_versions CHECK (source_version BETWEEN 1 AND 2147483647 AND current_version BETWEEN 0 AND 2147483647),
	CONSTRAINT ck_evidence_document_reference CHECK (document_reference ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'),
	CONSTRAINT ck_evidence_document_namespace CHECK ((is_synthetic AND left(document_reference,5) = 'DEMO_') OR (NOT is_synthetic AND upper(left(document_reference,5)) <> 'DEMO_')),
	CONSTRAINT ck_evidence_document_language CHECK (language IN ('zh-Hans','zh-Hant','en','und'))
)""")
    op.execute("""CREATE TABLE evidence_document_versions (
	id UUID NOT NULL,
	document_id UUID NOT NULL,
	dataset_id UUID NOT NULL,
	version INTEGER NOT NULL,
	file_id UUID NOT NULL,
	document_sha256 VARCHAR(64) NOT NULL,
	size_bytes INTEGER NOT NULL,
	media_type VARCHAR(16) NOT NULL,
	is_synthetic BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_evidence_version_document FOREIGN KEY(document_id, dataset_id, is_synthetic) REFERENCES evidence_documents (id, dataset_id, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT fk_evidence_version_file FOREIGN KEY(file_id) REFERENCES storage_objects (id) ON DELETE RESTRICT,
	CONSTRAINT uq_evidence_document_version UNIQUE (document_id, version),
	CONSTRAINT uq_evidence_document_hash UNIQUE (document_id, document_sha256),
	CONSTRAINT uq_evidence_version_parent UNIQUE (document_id, version, dataset_id, is_synthetic),
	CONSTRAINT ck_evidence_version_number CHECK (version BETWEEN 1 AND 2147483647),
	CONSTRAINT ck_evidence_version_hash CHECK (document_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_evidence_version_file CHECK (size_bytes BETWEEN 1 AND 1048576 AND media_type IN ('application/json','text/csv'))
)""")
    op.execute("""CREATE TABLE evidence_snippets (
	id UUID NOT NULL,
	document_id UUID NOT NULL,
	document_version INTEGER NOT NULL,
	dataset_id UUID NOT NULL,
	offering_id UUID NOT NULL,
	offering_version INTEGER NOT NULL,
	entry_year INTEGER NOT NULL,
	language VARCHAR(7) NOT NULL,
	byte_start INTEGER NOT NULL,
	byte_end INTEGER NOT NULL,
	line_start INTEGER NOT NULL,
	line_end INTEGER NOT NULL,
	snippet_sha256 VARCHAR(64) NOT NULL,
	scope_sha256 VARCHAR(64) NOT NULL,
	text TEXT NOT NULL,
	is_synthetic BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_evidence_snippet_document_version FOREIGN KEY(document_id, document_version, dataset_id, is_synthetic) REFERENCES evidence_document_versions (document_id, version, dataset_id, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT fk_evidence_snippet_offering_version FOREIGN KEY(dataset_id, offering_id, offering_version) REFERENCES catalog_offering_versions (dataset_id, offering_id, version) ON DELETE RESTRICT,
	CONSTRAINT fk_evidence_snippet_offering_mode FOREIGN KEY(dataset_id, offering_id, is_synthetic) REFERENCES catalog_offerings (dataset_id, id, is_synthetic) ON DELETE RESTRICT,
	CONSTRAINT uq_evidence_snippet_span UNIQUE (document_id, document_version, offering_id, offering_version, byte_start, byte_end),
	CONSTRAINT ck_evidence_snippet_scope CHECK (document_version BETWEEN 1 AND 2147483647 AND offering_version BETWEEN 1 AND 2147483647 AND entry_year BETWEEN 1 AND 9999),
	CONSTRAINT ck_evidence_snippet_bytes CHECK (byte_start >= 0 AND byte_end > byte_start AND byte_end <= 1048576 AND byte_end - byte_start <= 4096),
	CONSTRAINT ck_evidence_snippet_lines CHECK (line_start >= 1 AND line_end >= line_start AND line_end <= 1048576),
	CONSTRAINT ck_evidence_snippet_text CHECK (octet_length(text) = byte_end - byte_start AND octet_length(text) BETWEEN 1 AND 4096),
	CONSTRAINT ck_evidence_snippet_hashes CHECK (snippet_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_evidence_snippet_language CHECK (language IN ('zh-Hans','zh-Hant','en','und'))
)""")
    op.execute("""CREATE FUNCTION evidence_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable evidence cannot be changed' USING ERRCODE='23514'; END $$""")
    op.execute("CREATE TRIGGER evidence_versions_immutable BEFORE UPDATE OR DELETE ON evidence_document_versions FOR EACH ROW EXECUTE FUNCTION evidence_reject_mutation()")
    op.execute("CREATE TRIGGER evidence_snippets_immutable BEFORE UPDATE OR DELETE ON evidence_snippets FOR EACH ROW EXECUTE FUNCTION evidence_reject_mutation()")


def downgrade():
    op.execute("DROP TRIGGER evidence_snippets_immutable ON evidence_snippets")
    op.execute("DROP TRIGGER evidence_versions_immutable ON evidence_document_versions")
    op.execute("DROP FUNCTION evidence_reject_mutation()")
    op.drop_table("evidence_snippets")
    op.drop_table("evidence_document_versions")
    op.drop_table("evidence_documents")
