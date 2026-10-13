"""Frozen additive T40 rights_ledger migration; no startup DDL."""
from alembic import op

revision = '0001_ledger_t40'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE TABLE privacy_ledger_events (\n\tsequence BIGSERIAL NOT NULL, \n\tevent_id UUID NOT NULL, \n\tevent JSONB NOT NULL, \n\tprevious_sha256 VARCHAR(64) NOT NULL, \n\tchain_sha256 VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (sequence), \n\tCONSTRAINT ck_privacy_ledger_event CHECK (sequence BETWEEN 1 AND 10000 AND jsonb_typeof(event)='object' AND octet_length(event::text)<=2048 AND previous_sha256 ~ '^[0-9a-f]{64}$' AND chain_sha256 ~ '^[0-9a-f]{64}$'), \n\tUNIQUE (event_id)\n)")
    op.execute("CREATE TABLE privacy_ledger_head (\n\tid SERIAL NOT NULL, \n\tledger_id UUID NOT NULL, \n\tsequence BIGINT NOT NULL, \n\tchain_sha256 VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_privacy_ledger_head CHECK (id=1 AND sequence BETWEEN 0 AND 10000 AND chain_sha256 ~ '^[0-9a-f]{64}$')\n)")
    op.execute("CREATE FUNCTION t40_ledger_no_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable ledger event' USING ERRCODE='23514'; END $$")
    op.execute('CREATE TRIGGER privacy_ledger_events_no_mutation BEFORE UPDATE OR DELETE ON privacy_ledger_events FOR EACH ROW EXECUTE FUNCTION t40_ledger_no_mutation()')

def downgrade():
    op.execute("DROP TRIGGER privacy_ledger_events_no_mutation ON privacy_ledger_events")
    op.execute("DROP FUNCTION t40_ledger_no_mutation()")
    op.drop_table('privacy_ledger_head')
    op.drop_table('privacy_ledger_events')
