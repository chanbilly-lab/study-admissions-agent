"""Frozen independent candidate imports; all prior profiles stay unchanged."""

from alembic import op

revision = "0001_imports_t15"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
IF (SELECT count(*) FROM auth_alembic_version) <> 1 OR (SELECT min(version_num) FROM auth_alembic_version) <> '0006_audit_t10' THEN RAISE EXCEPTION 'Required import prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM catalog_alembic_version) <> 1 OR (SELECT min(version_num) FROM catalog_alembic_version) <> '0003_catalog_sources_t13' THEN RAISE EXCEPTION 'Required import prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM storage_alembic_version) <> 1 OR (SELECT min(version_num) FROM storage_alembic_version) <> '0001_storage_t14' THEN RAISE EXCEPTION 'Required import prerequisite is unavailable'; END IF;
IF (SELECT count(*) FROM idempotency_alembic_version) <> 1 OR (SELECT min(version_num) FROM idempotency_alembic_version) <> '0001_idempotency_t49' THEN RAISE EXCEPTION 'Required import prerequisite is unavailable'; END IF;
END $$""")
    op.execute("""CREATE TABLE import_batches (
    id UUID NOT NULL,
    dataset_id UUID NOT NULL,
    source_id UUID NOT NULL,
    source_version INTEGER NOT NULL,
    file_id UUID NOT NULL,
    file_sha256 VARCHAR(64) NOT NULL,
    file_size INTEGER NOT NULL,
    format VARCHAR(4) NOT NULL,
    parser_schema_version VARCHAR(6) NOT NULL,
    status VARCHAR(8) NOT NULL,
    version INTEGER NOT NULL,
    total_rows INTEGER,
    staged_rows INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    actor_user_id UUID NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_import_source_version FOREIGN KEY(dataset_id, source_id, source_version) REFERENCES catalog_source_versions (dataset_id, source_id, version) ON DELETE RESTRICT,
    CONSTRAINT fk_import_source_mode FOREIGN KEY(dataset_id, source_id, is_synthetic) REFERENCES catalog_sources (dataset_id, id, is_synthetic) ON DELETE RESTRICT,
    CONSTRAINT fk_import_file FOREIGN KEY(file_id) REFERENCES storage_objects (id) ON DELETE RESTRICT,
    CONSTRAINT uq_import_natural_content UNIQUE (dataset_id, source_id, source_version, file_sha256, format, parser_schema_version),
    CONSTRAINT uq_import_candidate_parent UNIQUE (id, dataset_id, is_synthetic),
    CONSTRAINT ck_import_versions CHECK (source_version BETWEEN 1 AND 2147483647 AND version = 1),
    CONSTRAINT ck_import_file CHECK (file_sha256 ~ '^[0-9a-f]{64}$' AND file_size BETWEEN 1 AND 1048576),
    CONSTRAINT ck_import_format CHECK (format IN ('json','csv') AND parser_schema_version = 'T15_v1'),
    CONSTRAINT ck_import_status CHECK (status IN ('staged','rejected','deleted')),
    CONSTRAINT ck_import_counts CHECK ((total_rows IS NULL OR total_rows BETWEEN 0 AND 200) AND staged_rows BETWEEN 0 AND 200 AND error_count BETWEEN 0 AND 2800),
    CONSTRAINT ck_import_result CHECK (status = 'deleted' OR (status = 'staged' AND total_rows IS NOT NULL AND total_rows > 0 AND staged_rows = total_rows AND error_count = 0) OR (status = 'rejected' AND staged_rows = 0 AND error_count > 0))
)""")
    op.execute("""CREATE INDEX ix_import_actor_created ON import_batches (actor_user_id, created_at, id)""")
    op.execute("""CREATE TABLE import_candidate_rows (
    id UUID NOT NULL,
    import_id UUID NOT NULL,
    dataset_id UUID NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    row_number INTEGER NOT NULL,
    offering_id UUID NOT NULL,
    offering_version INTEGER NOT NULL,
    entry_year INTEGER NOT NULL,
    source_record_reference VARCHAR(100) NOT NULL,
    fact_type VARCHAR(11) NOT NULL,
    field_key VARCHAR(100) NOT NULL,
    value_kind VARCHAR(7) NOT NULL,
    value_text TEXT,
    unit TEXT,
    missing_reason VARCHAR(32),
    footnote_state VARCHAR(7) NOT NULL,
    footnote_text TEXT,
    locator TEXT,
    review_state VARCHAR(5) NOT NULL,
    evidence_state VARCHAR(10) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_import_row_batch_mode FOREIGN KEY(import_id, dataset_id, is_synthetic) REFERENCES import_batches (id, dataset_id, is_synthetic) ON DELETE RESTRICT,
    CONSTRAINT fk_import_row_offering_version FOREIGN KEY(dataset_id, offering_id, offering_version) REFERENCES catalog_offering_versions (dataset_id, offering_id, version) ON DELETE RESTRICT,
    CONSTRAINT fk_import_row_offering_mode FOREIGN KEY(dataset_id, offering_id, is_synthetic) REFERENCES catalog_offerings (dataset_id, id, is_synthetic) ON DELETE RESTRICT,
    CONSTRAINT uq_import_row_number UNIQUE (import_id, row_number),
    CONSTRAINT ck_import_row_scope CHECK (row_number BETWEEN 1 AND 201 AND entry_year BETWEEN 1 AND 9999 AND offering_version BETWEEN 1 AND 2147483647),
    CONSTRAINT ck_import_row_type CHECK (fact_type IN ('requirement','score','fee','material','date','statistic') AND value_kind IN ('text','decimal')),
    CONSTRAINT ck_import_row_identifiers CHECK (source_record_reference ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$' AND field_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'),
    CONSTRAINT ck_import_row_namespace CHECK ((is_synthetic AND left(source_record_reference,5) = 'DEMO_') OR (NOT is_synthetic AND upper(left(source_record_reference,5)) <> 'DEMO_')),
    CONSTRAINT ck_import_row_missing CHECK ((value_text IS NULL AND missing_reason IS NOT NULL) OR (value_text IS NOT NULL AND missing_reason IS NULL)),
    CONSTRAINT ck_import_row_missing_reason CHECK (missing_reason IS NULL OR missing_reason IN ('not_provided','not_applicable','not_published','unavailable','ambiguous')),
    CONSTRAINT ck_import_row_value CHECK (value_text IS NULL OR (octet_length(value_text) BETWEEN 1 AND 4096 AND (value_kind <> 'decimal' OR (length(value_text) <= 64 AND value_text ~ '^-?(0|[1-9][0-9]*)([.][0-9]+)?$')))),
    CONSTRAINT ck_import_row_text CHECK ((unit IS NULL OR octet_length(unit) BETWEEN 1 AND 4096) AND (footnote_text IS NULL OR octet_length(footnote_text) BETWEEN 1 AND 4096) AND (locator IS NULL OR octet_length(locator) BETWEEN 1 AND 4096)),
    CONSTRAINT ck_import_row_footnote CHECK ((footnote_state = 'present' AND footnote_text IS NOT NULL) OR (footnote_state IN ('none','unknown') AND footnote_text IS NULL)),
    CONSTRAINT ck_import_row_unreviewed CHECK (review_state = 'draft' AND evidence_state = 'unresolved')
)""")
    op.execute("""CREATE TABLE import_row_errors (
    import_id UUID NOT NULL,
    row_number INTEGER NOT NULL,
    field VARCHAR(23) NOT NULL,
    code VARCHAR(24) NOT NULL,
    PRIMARY KEY (import_id, row_number, field, code),
    CONSTRAINT fk_import_error_batch FOREIGN KEY(import_id) REFERENCES import_batches (id) ON DELETE RESTRICT,
    CONSTRAINT ck_import_error_row CHECK (row_number BETWEEN 0 AND 201),
    CONSTRAINT ck_import_error_field CHECK (field IN ('document','offering_id','offering_version','entry_year','source_record_reference','fact_type','field_key','value_kind','value_text','unit','missing_reason','footnote_state','footnote_text','locator')),
    CONSTRAINT ck_import_error_code CHECK (code IN ('INVALID_ENCODING','INPUT_TOO_LARGE','INVALID_STRUCTURE','EMPTY_IMPORT','TOO_MANY_ROWS','INVALID_HEADER','DUPLICATE_KEY','MISSING_FIELD','UNEXPECTED_FIELD','INVALID_FIELD','FIELD_TOO_LARGE','INVALID_INTEGER','INVALID_UUID','INVALID_DECIMAL','MISSING_VALUE_REASON','INVALID_FOOTNOTE','SCOPE_MISMATCH','NAMESPACE_MISMATCH'))
)""")


def downgrade():
    op.drop_table("import_row_errors")
    op.drop_table("import_candidate_rows")
    op.drop_index("ix_import_actor_created", table_name="import_batches")
    op.drop_table("import_batches")
