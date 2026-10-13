"""Additive local-only three-fact reference schema, independent of old heads."""

from alembic import op

revision = "0001_ref_cutoffs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE reference_cutoff_sources (
      id UUID PRIMARY KEY, original_sha256 VARCHAR(64) NOT NULL UNIQUE,
      body_bytes INTEGER NOT NULL, raw_body BYTEA NOT NULL, payload JSONB NOT NULL,
      CONSTRAINT ck_ref_source_hash CHECK (original_sha256 ~ '^[0-9a-f]{64}$'),
      CONSTRAINT ck_ref_source_bytes CHECK (body_bytes BETWEEN 1 AND 2097152 AND octet_length(raw_body)=body_bytes),
      CONSTRAINT ck_ref_source_payload CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=16384)
    )""")
    op.execute("""
    CREATE TABLE reference_cutoff_batches (
      id UUID PRIMARY KEY, source_id UUID NOT NULL REFERENCES reference_cutoff_sources(id) ON DELETE RESTRICT,
      batch_key VARCHAR(100) NOT NULL UNIQUE, manifest_sha256 VARCHAR(64) NOT NULL UNIQUE,
      manifest JSONB NOT NULL, state VARCHAR(16) NOT NULL, state_version INTEGER NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      CONSTRAINT ck_ref_batch_scope CHECK (batch_key='ZJ2026_ORDINARY_CUTOFF_3'),
      CONSTRAINT ck_ref_batch_hash CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
      CONSTRAINT ck_ref_batch_manifest CHECK (jsonb_typeof(manifest)='object' AND octet_length(manifest::text)<=65536),
      CONSTRAINT ck_ref_batch_state CHECK ((state='candidate' AND state_version=0) OR
        (state='approved_local' AND state_version=1) OR (state='withdrawn' AND state_version=2))
    )""")
    op.execute("""
    CREATE TABLE reference_cutoff_records (
      batch_id UUID NOT NULL REFERENCES reference_cutoff_batches(id) ON DELETE RESTRICT,
      record_key VARCHAR(100) NOT NULL, line_kind VARCHAR(24) NOT NULL, value INTEGER NOT NULL,
      payload JSONB NOT NULL, PRIMARY KEY (batch_id,record_key),
      CONSTRAINT uq_ref_record_line_kind UNIQUE (batch_id,line_kind),
      CONSTRAINT ck_ref_record_key CHECK (record_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$' AND
        upper(substr(record_key,1,5)) <> 'DEMO_'),
      CONSTRAINT ck_ref_record_reviewed_fact CHECK ((line_kind='segment_first' AND value=494) OR
        (line_kind='segment_second' AND value=266) OR (line_kind='special_category' AND value=594)),
      CONSTRAINT ck_ref_record_payload CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=8192)
    )""")
    op.execute("""
    CREATE TABLE reference_cutoff_reviews (
      id UUID PRIMARY KEY, batch_id UUID NOT NULL REFERENCES reference_cutoff_batches(id) ON DELETE RESTRICT,
      sequence INTEGER NOT NULL, decision VARCHAR(16) NOT NULL, manifest_sha256 VARCHAR(64) NOT NULL,
      original_sha256 VARCHAR(64) NOT NULL, review_ref VARCHAR(100) NOT NULL, recorded_at TIMESTAMPTZ NOT NULL,
      proof_sha256 VARCHAR(64) NOT NULL, proof JSONB NOT NULL,
      CONSTRAINT uq_ref_review_sequence UNIQUE (batch_id,sequence),
      CONSTRAINT ck_ref_review_decision CHECK ((sequence=1 AND decision='approve_local') OR (sequence=2 AND decision='withdraw')),
      CONSTRAINT ck_ref_review_hashes CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$' AND
        original_sha256 ~ '^[0-9a-f]{64}$' AND proof_sha256 ~ '^[0-9a-f]{64}$'),
      CONSTRAINT ck_ref_review_human CHECK (review_ref='USER_ZJ2026_ORDINARY_3'),
      CONSTRAINT ck_ref_review_proof CHECK (jsonb_typeof(proof)='object' AND octet_length(proof::text)<=16384)
    )""")
    op.execute("""
    CREATE FUNCTION ref_cutoff_no_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'immutable local reference evidence' USING ERRCODE='23514'; END $$""")
    for table in ("reference_cutoff_sources", "reference_cutoff_records", "reference_cutoff_reviews"):
        op.execute(f"CREATE TRIGGER {table}_no_mutation BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION ref_cutoff_no_mutation()")
        op.execute(f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
                   "FOR EACH STATEMENT EXECUTE FUNCTION ref_cutoff_no_mutation()")
    op.execute("""
    CREATE FUNCTION ref_cutoff_batch_transition() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE expected_decision TEXT;
    BEGIN
      IF TG_OP='DELETE' OR TG_OP='TRUNCATE' THEN
        RAISE EXCEPTION 'local reference batch cannot be removed' USING ERRCODE='23514';
      END IF;
      IF (to_jsonb(NEW)-'state'-'state_version') IS DISTINCT FROM (to_jsonb(OLD)-'state'-'state_version') THEN
        RAISE EXCEPTION 'immutable local reference manifest' USING ERRCODE='23514';
      END IF;
      IF OLD.state='candidate' AND NEW.state='approved_local' AND NEW.state_version=OLD.state_version+1 THEN
        expected_decision := 'approve_local';
      ELSIF OLD.state='approved_local' AND NEW.state='withdrawn' AND NEW.state_version=OLD.state_version+1 THEN
        expected_decision := 'withdraw';
      ELSE RAISE EXCEPTION 'invalid local reference transition' USING ERRCODE='23514'; END IF;
      IF NOT EXISTS (SELECT 1 FROM reference_cutoff_reviews r JOIN reference_cutoff_sources s ON s.id=NEW.source_id
         WHERE r.batch_id=NEW.id AND r.sequence=NEW.state_version AND r.decision=expected_decision
         AND r.manifest_sha256=NEW.manifest_sha256 AND r.original_sha256=s.original_sha256) THEN
        RAISE EXCEPTION 'local reference transition needs matching review' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("CREATE TRIGGER reference_cutoff_batches_transition BEFORE UPDATE OR DELETE ON reference_cutoff_batches "
               "FOR EACH ROW EXECUTE FUNCTION ref_cutoff_batch_transition()")
    op.execute("CREATE TRIGGER reference_cutoff_batches_no_truncate BEFORE TRUNCATE ON reference_cutoff_batches "
               "FOR EACH STATEMENT EXECUTE FUNCTION ref_cutoff_batch_transition()")
    op.execute("""
    CREATE FUNCTION ref_cutoff_complete_batch() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target_id UUID; b reference_cutoff_batches; r reference_cutoff_reviews;
    BEGIN
      IF TG_TABLE_NAME='reference_cutoff_batches' THEN target_id:=NEW.id; ELSE target_id:=NEW.batch_id; END IF;
      SELECT * INTO b FROM reference_cutoff_batches WHERE id=target_id;
      IF NOT FOUND OR (SELECT count(*) FROM reference_cutoff_records WHERE batch_id=target_id) <> 3 THEN
        RAISE EXCEPTION 'local reference batch must contain its complete three records' USING ERRCODE='23514';
      END IF;
      IF b.state_version=0 THEN
        IF EXISTS (SELECT 1 FROM reference_cutoff_reviews WHERE batch_id=target_id) THEN
          RAISE EXCEPTION 'candidate cannot have an unmatched review' USING ERRCODE='23514';
        END IF;
      ELSE
        SELECT * INTO r FROM reference_cutoff_reviews WHERE batch_id=target_id AND sequence=b.state_version;
        IF NOT FOUND OR r.manifest_sha256<>b.manifest_sha256 OR
          r.original_sha256<>(SELECT original_sha256 FROM reference_cutoff_sources WHERE id=b.source_id) OR
          (b.state='approved_local' AND r.decision<>'approve_local') OR
          (b.state='withdrawn' AND r.decision<>'withdraw') OR
          (SELECT count(*) FROM reference_cutoff_reviews WHERE batch_id=target_id)<>b.state_version THEN
          RAISE EXCEPTION 'local reference state and append-only reviews differ' USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NULL;
    END $$""")
    for table, operations in (("reference_cutoff_batches", "INSERT OR UPDATE"),
                              ("reference_cutoff_records", "INSERT"), ("reference_cutoff_reviews", "INSERT")):
        op.execute(f"CREATE CONSTRAINT TRIGGER {table}_complete AFTER {operations} ON {table} "
                   "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ref_cutoff_complete_batch()")


def downgrade():
    # Only the isolated new profile; never an application startup action.
    for table in ("reference_cutoff_batches", "reference_cutoff_records", "reference_cutoff_reviews"):
        op.execute(f"DROP TRIGGER {table}_complete ON {table}")
    op.execute("DROP FUNCTION ref_cutoff_complete_batch()")
    op.execute("DROP TRIGGER reference_cutoff_batches_no_truncate ON reference_cutoff_batches")
    op.execute("DROP TRIGGER reference_cutoff_batches_transition ON reference_cutoff_batches")
    op.execute("DROP FUNCTION ref_cutoff_batch_transition()")
    for table in ("reference_cutoff_sources", "reference_cutoff_records", "reference_cutoff_reviews"):
        op.execute(f"DROP TRIGGER {table}_no_mutation ON {table}")
        op.execute(f"DROP TRIGGER {table}_no_truncate ON {table}")
    op.execute("DROP FUNCTION ref_cutoff_no_mutation()")
    for table in ("reference_cutoff_reviews", "reference_cutoff_records", "reference_cutoff_batches", "reference_cutoff_sources"):
        op.drop_table(table)
