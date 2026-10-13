"""Append-only annual request metadata; no fetching or fact publication tables."""

from alembic import op

revision = "0001_annual_updates"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE public.annual_source_cycles (
        id UUID PRIMARY KEY, schedule_id VARCHAR(100) NOT NULL, cycle_year INTEGER NOT NULL,
        config_revision INTEGER NOT NULL, config_sha256 VARCHAR(64) NOT NULL,
        config_snapshot JSONB NOT NULL, plan_payload JSONB NOT NULL,
        scheduled_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL, request_count INTEGER NOT NULL,
        CONSTRAINT uq_annual_source_cycle UNIQUE (schedule_id,cycle_year),
        CONSTRAINT ck_annual_schedule_id CHECK (schedule_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'),
        CONSTRAINT ck_annual_cycle_bounds CHECK (cycle_year BETWEEN 2000 AND 9998 AND config_revision BETWEEN 1 AND 2147483647
          AND request_count BETWEEN 1 AND 10 AND created_at>=scheduled_at),
        CONSTRAINT ck_annual_config_snapshot CHECK ((config_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(config_snapshot)='object'
          AND octet_length(config_snapshot::text)<=65536 AND config_snapshot->>'schema_version'='annual.source.schedule.1'
          AND config_snapshot->>'schedule_id'=schedule_id AND config_snapshot->'revision'=to_jsonb(config_revision)
          AND config_snapshot->'enabled'='true'::jsonb) IS TRUE),
        CONSTRAINT ck_annual_plan_payload CHECK ((jsonb_typeof(plan_payload)='object' AND octet_length(plan_payload::text)<=131072
          AND plan_payload->>'schema_version'='annual.source.plan.1' AND plan_payload->>'cycle_id'=id::text
          AND plan_payload->>'schedule_id'=schedule_id AND plan_payload->'cycle_year'=to_jsonb(cycle_year)
          AND plan_payload->'config_revision'=to_jsonb(config_revision) AND plan_payload->>'config_sha256'=config_sha256
          AND jsonb_typeof(plan_payload->'requests')='array' AND jsonb_array_length(plan_payload->'requests')=request_count) IS TRUE)
      )""")
    op.execute("""
      CREATE TABLE public.annual_source_update_requests (
        id UUID PRIMARY KEY, cycle_id UUID NOT NULL REFERENCES public.annual_source_cycles(id) ON DELETE RESTRICT,
        target_ref VARCHAR(100) NOT NULL, kind VARCHAR(24) NOT NULL,
        exam_year INTEGER NULL, entry_year INTEGER NULL, payload JSONB NOT NULL, payload_sha256 VARCHAR(64) NOT NULL,
        CONSTRAINT uq_annual_source_target UNIQUE (cycle_id,target_ref),
        CONSTRAINT ck_annual_target_ref CHECK (target_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'),
        CONSTRAINT ck_annual_target_year CHECK ((kind IN ('province_cutoffs','admission_observations')
          AND exam_year BETWEEN 1 AND 9999 AND exam_year IS NOT NULL AND entry_year IS NULL)
          OR (kind='entry_requirements' AND exam_year IS NULL AND entry_year BETWEEN 1 AND 9999 AND entry_year IS NOT NULL)),
        CONSTRAINT ck_annual_request_payload CHECK ((payload_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(payload)='object'
          AND octet_length(payload::text)<=16384 AND payload->>'id'=id::text AND payload->>'target_ref'=target_ref
          AND payload->>'dataset_type'=kind AND payload->'exam_year'=COALESCE(to_jsonb(exam_year),'null'::jsonb)
          AND payload->'entry_year'=COALESCE(to_jsonb(entry_year),'null'::jsonb) AND payload->>'status'='awaiting_collection'
          AND payload->'source_evidence_year'='null'::jsonb AND payload->'network_requested'='false'::jsonb
          AND payload->'facts_updated'='false'::jsonb AND payload->'published'='false'::jsonb) IS TRUE)
      )""")
    op.execute("""
      CREATE FUNCTION public.annual_source_no_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'immutable annual request metadata' USING ERRCODE='23514'; END $$""")
    for table in ("annual_source_cycles", "annual_source_update_requests"):
        op.execute(f"CREATE TRIGGER {table}_no_mutation BEFORE UPDATE OR DELETE ON public.{table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.annual_source_no_mutation()")
        op.execute(f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON public.{table} "
                   "FOR EACH STATEMENT EXECUTE FUNCTION public.annual_source_no_mutation()")
    op.execute("""
      CREATE FUNCTION public.annual_source_complete_cycle() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE parent_id UUID; expected_count INTEGER;
      BEGIN
        IF TG_TABLE_NAME='annual_source_cycles' THEN parent_id:=NEW.id; ELSE parent_id:=NEW.cycle_id; END IF;
        SELECT request_count INTO expected_count FROM public.annual_source_cycles WHERE id=parent_id;
        IF NOT FOUND OR (SELECT count(*) FROM public.annual_source_update_requests WHERE cycle_id=parent_id) <> expected_count THEN
          RAISE EXCEPTION 'annual request cycle must contain its complete target batch' USING ERRCODE='23514';
        END IF;
        RETURN NULL;
      END $$""")
    for table in ("annual_source_cycles", "annual_source_update_requests"):
        op.execute(f"CREATE CONSTRAINT TRIGGER {table}_complete AFTER INSERT ON public.{table} "
                   "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.annual_source_complete_cycle()")


def downgrade():
    # Removing immutable request history needs a separately authorized recovery plan.
    raise RuntimeError("ANNUAL_UPDATE_DOWNGRADE_DISABLED")
