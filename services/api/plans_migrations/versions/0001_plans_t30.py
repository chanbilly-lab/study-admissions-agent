"""Frozen T30 private draft snapshots and same-version references."""

from alembic import op

revision = "0001_plans_t30"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TABLE plan_draft_roots (\n\tid UUID NOT NULL, \n\towner_user_id UUID NOT NULL, \n\tis_synthetic BOOLEAN NOT NULL, \n\tprofile_id UUID NOT NULL, \n\tprofile_version_id UUID NOT NULL, \n\tprofile_version INTEGER NOT NULL, \n\tprofile_sha256 VARCHAR(64) NOT NULL, \n\tcurrent_version INTEGER NOT NULL, \n\tcurrent_version_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_plan_root_owner_mode UNIQUE (id, owner_user_id, is_synthetic), \n\tCONSTRAINT fk_plan_root_registry FOREIGN KEY(id, owner_user_id) REFERENCES auth_owned_resources (id, owner_user_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_plan_root_profile_owner FOREIGN KEY(profile_id, owner_user_id, is_synthetic) REFERENCES student_profiles (id, owner_user_id, is_synthetic) ON DELETE RESTRICT, \n\tCONSTRAINT fk_plan_root_profile_version FOREIGN KEY(profile_version_id, profile_id, profile_version) REFERENCES student_profile_versions (id, profile_id, version) ON DELETE RESTRICT, \n\tCONSTRAINT ck_plan_root_versions CHECK (profile_version BETWEEN 1 AND 2147483647 AND current_version BETWEEN 1 AND 2147483647), \n\tCONSTRAINT ck_plan_root_hash CHECK (length(profile_sha256)=64 AND profile_sha256 ~ '^[0-9a-f]{64}$')\n)")
    op.execute('CREATE INDEX ix_plan_root_owner_id ON plan_draft_roots (owner_user_id, id)')
    op.execute('CREATE TABLE plan_draft_versions (\n\tid UUID NOT NULL, \n\tplan_id UUID NOT NULL, \n\towner_user_id UUID NOT NULL, \n\tis_synthetic BOOLEAN NOT NULL, \n\tversion INTEGER NOT NULL, \n\tpayload JSONB NOT NULL, \n\tdraft_sha256 VARCHAR(64) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\taudit_event_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_plan_version_number UNIQUE (plan_id, version), \n\tCONSTRAINT uq_plan_version_pointer UNIQUE (id, plan_id, version), \n\tCONSTRAINT uq_plan_version_scope UNIQUE (id, plan_id), \n\tCONSTRAINT fk_plan_version_owner FOREIGN KEY(plan_id, owner_user_id, is_synthetic) REFERENCES plan_draft_roots (id, owner_user_id, is_synthetic) ON DELETE RESTRICT, \n\tCONSTRAINT ck_plan_version_positive CHECK (version BETWEEN 1 AND 2147483647), \n\tCONSTRAINT ck_plan_version_hash CHECK (length(draft_sha256)=64 AND draft_sha256 ~ \'^[0-9a-f]{64}$\'), \n\tCONSTRAINT ck_plan_version_payload CHECK (jsonb_typeof(payload)=\'object\' AND octet_length(payload::text)<=524288), \n\tCONSTRAINT ck_plan_version_markers CHECK (payload @> jsonb_build_object(\'status\',\'draft\',\'confirmed\',false,\'scheduled\',false,\'schema_version\',\'T30_v1\',\'generator_version\',\'T30_v1\')), \n\tCONSTRAINT ck_plan_version_retention CHECK (expires_at>created_at AND expires_at<=(((created_at AT TIME ZONE \'UTC\')+interval \'24 months\') AT TIME ZONE \'UTC\'))\n)')
    op.execute('CREATE INDEX ix_plan_version_expiry ON plan_draft_versions (expires_at, id)')
    op.execute('CREATE TABLE plan_draft_tasks (\n\tversion_id UUID NOT NULL, \n\ttask_key VARCHAR(64) NOT NULL, \n\tplan_id UUID NOT NULL, \n\tordinal INTEGER NOT NULL, \n\tpayload JSONB NOT NULL, \n\tpayload_sha256 VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (version_id, task_key), \n\tCONSTRAINT uq_plan_task_scope UNIQUE (version_id, plan_id, task_key), \n\tCONSTRAINT uq_plan_task_ordinal UNIQUE (version_id, ordinal), \n\tCONSTRAINT fk_plan_task_version FOREIGN KEY(version_id, plan_id) REFERENCES plan_draft_versions (id, plan_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_plan_task_ordinal CHECK (ordinal BETWEEN 1 AND 100), \n\tCONSTRAINT ck_plan_task_hashes CHECK (length(task_key)=64 AND task_key ~ \'^[0-9a-f]{64}$\' AND length(payload_sha256)=64 AND payload_sha256 ~ \'^[0-9a-f]{64}$\'), \n\tCONSTRAINT ck_plan_task_payload CHECK (jsonb_typeof(payload)=\'object\' AND octet_length(payload::text)<=131072 AND payload @> jsonb_build_object(\'confirmed\',false,\'estimate_editable\',true))\n)')
    op.execute("CREATE TABLE plan_draft_assessments (\n\tversion_id UUID NOT NULL, \n\tassessment_id UUID NOT NULL, \n\tplan_id UUID NOT NULL, \n\tresult_sha256 VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (version_id, assessment_id), \n\tCONSTRAINT fk_plan_assessment_version FOREIGN KEY(version_id, plan_id) REFERENCES plan_draft_versions (id, plan_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_plan_assessment_exact FOREIGN KEY(assessment_id) REFERENCES eligibility_assessments (id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_plan_assessment_hash CHECK (length(result_sha256)=64 AND result_sha256 ~ '^[0-9a-f]{64}$')\n)")
    op.execute('CREATE TABLE plan_draft_dependencies (\n\tversion_id UUID NOT NULL, \n\ttask_key VARCHAR(64) NOT NULL, \n\tdependency_key VARCHAR(64) NOT NULL, \n\tplan_id UUID NOT NULL, \n\tPRIMARY KEY (version_id, task_key, dependency_key), \n\tCONSTRAINT fk_plan_dependency_task FOREIGN KEY(version_id, plan_id, task_key) REFERENCES plan_draft_tasks (version_id, plan_id, task_key) ON DELETE RESTRICT, \n\tCONSTRAINT fk_plan_dependency_same_version FOREIGN KEY(version_id, plan_id, dependency_key) REFERENCES plan_draft_tasks (version_id, plan_id, task_key) ON DELETE RESTRICT, \n\tCONSTRAINT ck_plan_dependency_not_self CHECK (task_key<>dependency_key)\n)')
    op.execute('ALTER TABLE plan_draft_roots ADD CONSTRAINT fk_plan_root_current_version FOREIGN KEY(current_version_id, id, current_version) REFERENCES plan_draft_versions (id, plan_id, version) DEFERRABLE INITIALLY DEFERRED')
    op.execute("CREATE FUNCTION plans_reject_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Plan draft history cannot be changed' USING ERRCODE='23514'; END $$")
    op.execute('CREATE TRIGGER plan_draft_roots_no_update BEFORE UPDATE ON plan_draft_roots FOR EACH ROW EXECUTE FUNCTION plans_reject_update()')
    op.execute('CREATE TRIGGER plan_draft_versions_no_update BEFORE UPDATE ON plan_draft_versions FOR EACH ROW EXECUTE FUNCTION plans_reject_update()')
    op.execute('CREATE TRIGGER plan_draft_tasks_no_update BEFORE UPDATE ON plan_draft_tasks FOR EACH ROW EXECUTE FUNCTION plans_reject_update()')
    op.execute('CREATE TRIGGER plan_draft_assessments_no_update BEFORE UPDATE ON plan_draft_assessments FOR EACH ROW EXECUTE FUNCTION plans_reject_update()')
    op.execute('CREATE TRIGGER plan_draft_dependencies_no_update BEFORE UPDATE ON plan_draft_dependencies FOR EACH ROW EXECUTE FUNCTION plans_reject_update()')


def downgrade():
    op.execute('DROP TRIGGER plan_draft_roots_no_update ON plan_draft_roots')
    op.execute('DROP TRIGGER plan_draft_versions_no_update ON plan_draft_versions')
    op.execute('DROP TRIGGER plan_draft_tasks_no_update ON plan_draft_tasks')
    op.execute('DROP TRIGGER plan_draft_assessments_no_update ON plan_draft_assessments')
    op.execute('DROP TRIGGER plan_draft_dependencies_no_update ON plan_draft_dependencies')
    op.execute("DROP FUNCTION plans_reject_update()")
    op.execute("ALTER TABLE plan_draft_roots DROP CONSTRAINT fk_plan_root_current_version")
    op.drop_table('plan_draft_dependencies')
    op.drop_table('plan_draft_assessments')
    op.drop_table('plan_draft_tasks')
    op.drop_table('plan_draft_versions')
    op.drop_table('plan_draft_roots')
