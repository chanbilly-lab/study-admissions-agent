"""Frozen T34 additive relation and immutable impact history."""

from alembic import op

revision = "0001_changes_t34"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TABLE change_event_receipts (\n\tevent_id UUID NOT NULL,\n\tdataset_id UUID NOT NULL,\n\tentry_year INTEGER NOT NULL,\n\tis_synthetic BOOLEAN NOT NULL,\n\tevent_type VARCHAR(12) NOT NULL,\n\tbefore_release_id UUID,\n\tafter_release_id UUID,\n\tevent_sha256 VARCHAR(64) NOT NULL,\n\tpayload_sha256 VARCHAR(64) NOT NULL,\n\tpayload JSONB NOT NULL,\n\tassessment_count INTEGER NOT NULL,\n\tplan_count INTEGER NOT NULL,\n\tprocessed_at TIMESTAMP WITH TIME ZONE NOT NULL,\n\taudit_event_id UUID NOT NULL,\n\tPRIMARY KEY (event_id),\n\tCONSTRAINT fk_change_receipt_event FOREIGN KEY(event_id) REFERENCES catalog_change_events (id) ON DELETE RESTRICT,\n\tCONSTRAINT fk_change_receipt_before FOREIGN KEY(before_release_id, dataset_id, entry_year, is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT,\n\tCONSTRAINT fk_change_receipt_after FOREIGN KEY(after_release_id, dataset_id, entry_year, is_synthetic) REFERENCES catalog_releases (id, dataset_id, entry_year, is_synthetic) ON DELETE RESTRICT,\n\tCONSTRAINT ck_change_receipt_counts CHECK (entry_year BETWEEN 1 AND 9999 AND assessment_count>=0 AND plan_count>=0),\n\tCONSTRAINT ck_change_receipt_type CHECK ((event_type='published' AND before_release_id IS NULL AND after_release_id IS NOT NULL) OR (event_type='replaced' AND before_release_id IS NOT NULL AND after_release_id IS NOT NULL AND before_release_id<>after_release_id) OR (event_type='withdrawn' AND before_release_id IS NOT NULL AND after_release_id IS NULL)),\n\tCONSTRAINT ck_change_receipt_hashes CHECK (length(event_sha256)=64 AND event_sha256 ~ '^[0-9a-f]{64}$' AND length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$'),\n\tCONSTRAINT ck_change_receipt_payload CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=262144)\n)")
    op.execute('CREATE INDEX ix_change_receipt_dataset ON change_event_receipts (dataset_id, entry_year, event_id)')
    op.execute("CREATE TABLE assessment_change_impacts (\n\tevent_id UUID NOT NULL,\n\tassessment_id UUID NOT NULL,\n\towner_user_id UUID NOT NULL,\n\tis_synthetic BOOLEAN NOT NULL,\n\tneeds_review BOOLEAN NOT NULL,\n\tpayload JSONB NOT NULL,\n\tpayload_sha256 VARCHAR(64) NOT NULL,\n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL,\n\tPRIMARY KEY (event_id, assessment_id),\n\tCONSTRAINT uq_assessment_change_scope UNIQUE (event_id, assessment_id, owner_user_id, is_synthetic),\n\tCONSTRAINT fk_assessment_change_receipt FOREIGN KEY(event_id) REFERENCES change_event_receipts (event_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,\n\tCONSTRAINT fk_assessment_change_assessment FOREIGN KEY(assessment_id) REFERENCES eligibility_assessments (id) ON DELETE RESTRICT,\n\tCONSTRAINT ck_assessment_change_hash CHECK (length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$'),\n\tCONSTRAINT ck_assessment_change_payload CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=65536)\n)")
    op.execute('CREATE INDEX ix_assessment_change_owner ON assessment_change_impacts (owner_user_id, assessment_id, event_id)')
    op.execute("CREATE TABLE plan_change_impacts (\n\tevent_id UUID NOT NULL,\n\tplan_version_id UUID NOT NULL,\n\tassessment_id UUID NOT NULL,\n\tplan_id UUID NOT NULL,\n\towner_user_id UUID NOT NULL,\n\tis_synthetic BOOLEAN NOT NULL,\n\tneeds_review BOOLEAN NOT NULL,\n\tpayload JSONB NOT NULL,\n\tpayload_sha256 VARCHAR(64) NOT NULL,\n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL,\n\tPRIMARY KEY (event_id, plan_version_id, assessment_id),\n\tCONSTRAINT fk_plan_change_assessment_scope FOREIGN KEY(event_id, assessment_id, owner_user_id, is_synthetic) REFERENCES assessment_change_impacts (event_id, assessment_id, owner_user_id, is_synthetic) ON DELETE RESTRICT,\n\tCONSTRAINT fk_plan_change_source FOREIGN KEY(plan_version_id, assessment_id) REFERENCES plan_draft_assessments (version_id, assessment_id) ON DELETE RESTRICT,\n\tCONSTRAINT fk_plan_change_version FOREIGN KEY(plan_version_id, plan_id) REFERENCES plan_draft_versions (id, plan_id) ON DELETE RESTRICT,\n\tCONSTRAINT fk_plan_change_owner FOREIGN KEY(plan_id, owner_user_id, is_synthetic) REFERENCES plan_draft_roots (id, owner_user_id, is_synthetic) ON DELETE RESTRICT,\n\tCONSTRAINT ck_plan_change_hash CHECK (length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$'),\n\tCONSTRAINT ck_plan_change_payload CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=65536)\n)")
    op.execute('CREATE INDEX ix_plan_change_owner ON plan_change_impacts (owner_user_id, plan_id, event_id)')
    op.execute("CREATE INDEX ix_assessment_release_target ON eligibility_assessments (release_id, dataset_id, entry_year)")
    op.execute("CREATE INDEX ix_plan_source_assessment ON plan_draft_assessments (assessment_id, version_id, plan_id)")
    op.execute("CREATE FUNCTION changes_reject_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Change history cannot be changed' USING ERRCODE='23514'; END $$")
    op.execute('CREATE TRIGGER change_event_receipts_no_update BEFORE UPDATE ON change_event_receipts FOR EACH ROW EXECUTE FUNCTION changes_reject_update()')
    op.execute('CREATE TRIGGER assessment_change_impacts_no_update BEFORE UPDATE ON assessment_change_impacts FOR EACH ROW EXECUTE FUNCTION changes_reject_update()')
    op.execute('CREATE TRIGGER plan_change_impacts_no_update BEFORE UPDATE ON plan_change_impacts FOR EACH ROW EXECUTE FUNCTION changes_reject_update()')


def downgrade():
    op.execute('DROP TRIGGER plan_change_impacts_no_update ON plan_change_impacts')
    op.execute('DROP TRIGGER assessment_change_impacts_no_update ON assessment_change_impacts')
    op.execute('DROP TRIGGER change_event_receipts_no_update ON change_event_receipts')
    op.execute("DROP FUNCTION changes_reject_update()")
    op.execute("DROP INDEX ix_plan_source_assessment")
    op.execute("DROP INDEX ix_assessment_release_target")
    op.drop_table('plan_change_impacts')
    op.drop_table('assessment_change_impacts')
    op.drop_table('change_event_receipts')
