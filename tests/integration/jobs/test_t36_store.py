"""Actual durable processing, scoped CAS, failures and additive migration."""
from datetime import timedelta
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select,text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from services.api.app.jobs.models import DurableJob,InboxNotification,CleanupPermit,NotificationPreference
from services.api.app.jobs.store import HEADS,migrate_jobs
from services.api.app.notifications.schemas import NotificationError,PreferenceInput,MarkReadInput
from tests.integration.changes.test_t34_store import immutable_rows

pytestmark=pytest.mark.postgres


def drain(case,*,steps=20):
    worker=uuid4()
    case.jobs.enqueue_outbox()
    result=[]
    for _ in range(steps):
        claim=case.jobs.claim(worker)
        if claim is None:
            break
        value=case.jobs.run_claim(claim)
        result.append(value)
        if value.status=="queued":
            case.clock.advance(1)
    return result


def notification_claim(case):
    case.jobs.enqueue_outbox()
    for _ in range(20):
        claim=case.jobs.claim(uuid4())
        if claim is None:
            raise AssertionError("a real queued notification was expected")
        with Session(case.jobs.store.engine) as session:
            kind=session.get(DurableJob,claim.job_id).kind
        if kind=="notification":
            return claim
        case.jobs.run_claim(claim)
    raise AssertionError("bounded preparation did not reach the notification")


def test_notification_durable_dedup_read_cas_and_original_rows(job_case_factory,pg_engine):
    case=job_case_factory(withdraw=True)
    frozen=immutable_rows(pg_engine)
    results=drain(case)
    assert any(value.kind=="notification" and value.status=="completed" for value in results)
    page=case.notifications.list_notifications(case.principal,limit=1)
    assert len(page.items)==1 and page.items[0].reason=="RELEASE_WITHDRAWN"
    first=page.items[0]
    read=case.notifications.mark_read(case.principal,first.id,MarkReadInput(expected_version=1,student_confirmed=True))
    assert read.version==2 and read.read_at is not None
    assert case.notifications.mark_read(case.principal,first.id,MarkReadInput(expected_version=1,student_confirmed=True))==read
    assert case.notifications.mark_read(case.principal,first.id,MarkReadInput(expected_version=2,student_confirmed=True))==read
    assert case.jobs.enqueue_outbox()==()
    assert drain(case)==[]
    assert immutable_rows(pg_engine)==frozen
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM inbox_notifications")).scalar_one()==1
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE inbox_notifications SET payload_sha256=:sha"),{"sha":"a"*64})


def test_preference_default_cas_disable_stops_queued_and_reoptin(job_case_factory,pg_engine):
    case=job_case_factory(opt_in=False,withdraw=True)
    assert case.notifications.get_preferences(case.principal).version==0
    assert not case.notifications.get_preferences(case.principal).enabled
    enabled=case.notifications.update_preferences(case.principal,PreferenceInput(expected_version=0,enabled=True,
        profile_id=case.profile.profile_id,student_confirmed=True))
    with pytest.raises(NotificationError) as error:
        case.notifications.update_preferences(case.principal,PreferenceInput(expected_version=0,enabled=False,profile_id=None,student_confirmed=True))
    assert error.value.status_code==409
    claim=notification_claim(case)
    frozen=immutable_rows(pg_engine)
    with Session(pg_engine) as session:
        template=session.get(DurableJob,claim.job_id)
        event_id,assessment_id=template.event_id,template.assessment_id

    def closed_user_claim(kind):
        # Only the trusted internal closed seam queues these types. It reuses
        # the actual opt-in proof; no export/model handler or artifact exists.
        with Session(pg_engine) as session,session.begin():
            preference=session.get(NotificationPreference,case.principal.user_id)
            now=case.clock()
            row=case.jobs.store.put_job(session,kind=kind,
                natural={"kind":kind,"probe":str(uuid4())},
                payload=case.jobs._preference_payload(preference),now=now,
                expires_at=now+timedelta(seconds=case.jobs.policy.job_ttl_seconds),
                is_synthetic=True,owner=case.principal.user_id,event_id=event_id,
                assessment_id=assessment_id,preference_version=preference.version)
            job_id=row.id
        for _ in range(20):
            selected=case.jobs.claim(uuid4())
            assert selected is not None
            if selected.job_id==job_id:
                return selected
            with Session(pg_engine) as session:
                assert session.get(DurableJob,selected.job_id).kind=="release_impact"
            case.jobs.run_claim(selected)
        raise AssertionError("bounded closed seam preparation did not reach the job")

    export_claim=closed_user_claim("export")
    disabled=case.notifications.update_preferences(case.principal,PreferenceInput(expected_version=enabled.version,enabled=False,profile_id=None,student_confirmed=True))
    assert disabled.version==2 and disabled.profile_id is None
    assert case.jobs.run_claim(claim).status=="cancelled"
    exported=case.jobs.run_claim(export_claim)
    assert (exported.kind,exported.status,exported.reason)==("export","cancelled","AUTHORITY_REVOKED")
    assert case.notifications.list_notifications(case.principal).items==()
    reenabled=case.notifications.update_preferences(case.principal,PreferenceInput(expected_version=2,enabled=True,
        profile_id=case.profile.profile_id,student_confirmed=True))
    assert reenabled.version==3
    model_claim=closed_user_claim("model")
    case.auth.logout(case.owner.cookie,case.auth.get_csrf_token(case.owner.cookie).token)
    modelled=case.jobs.run_claim(model_claim)
    assert (modelled.kind,modelled.status,modelled.reason)==("model","cancelled","AUTHORITY_REVOKED")
    assert immutable_rows(pg_engine)==frozen
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM inbox_notifications")).scalar_one()==0
        assert connection.execute(text("SELECT outcome,reason FROM job_attempts WHERE job_id IN (:export,:model) ORDER BY job_id"),
            {"export":export_claim.job_id,"model":model_claim.job_id}).all()==[("cancelled","AUTHORITY_REVOKED")]*2


def test_expired_original_file_does_not_block_committed_impact(job_case_factory,pg_engine):
    case=job_case_factory(withdraw=True,file_lifetime_seconds=40)
    case.clock.advance(41)
    assert any(result.kind=="notification" and result.status=="completed" for result in drain(case))
    assert len(case.notifications.list_notifications(case.principal).items)==1


def test_required_audit_failure_and_retry_backoff_are_atomic(job_case_factory,pg_engine):
    case=job_case_factory(withdraw=True,max_attempts=2,retry_seconds=2)
    claim=notification_claim(case)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION deny_t36_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.action='authorization.owned.execute' AND NEW.object_id='"+str(claim.job_id)+"'::uuid THEN RAISE EXCEPTION 'fixture audit failure'; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER deny_t36_audit BEFORE INSERT ON auth_audit_events FOR EACH ROW EXECUTE FUNCTION deny_t36_audit()"))
    with pytest.raises(Exception) as error:
        case.jobs.run_claim(claim)
    assert getattr(error.value,"status_code",None)==503
    with pg_engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM inbox_notifications")).scalar_one()==0
        assert connection.execute(text("SELECT status FROM durable_jobs WHERE id=:id"),{"id":claim.job_id}).scalar_one()=="running"
        connection.execute(text("DROP TRIGGER deny_t36_audit ON auth_audit_events"))
        connection.execute(text("DROP FUNCTION deny_t36_audit()"))
    retry=case.jobs.retry_claim(claim)
    assert retry.status=="queued" and retry.reason=="RETRYABLE_FAILURE"
    for _ in range(10):
        other=case.jobs.claim(uuid4())
        if other is None:
            break
        assert other.job_id!=claim.job_id
        case.jobs.run_claim(other)
    case.clock.advance(2)
    second=case.jobs.claim(uuid4())
    assert second.job_id==claim.job_id and second.generation==2
    final=case.jobs.retry_claim(second)
    assert final.status=="failed" and final.reason=="ATTEMPTS_EXHAUSTED"


def test_deferred_commit_effect_rollback_and_exact_claim_retry(job_case_factory,pg_engine):
    case=job_case_factory(withdraw=True)
    claim=notification_claim(case)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION deny_t36_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'fixture deferred failure'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER deny_t36_commit AFTER INSERT ON inbox_notifications DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION deny_t36_commit()"))
    with pytest.raises(NotificationError) as error:
        case.jobs.run_claim(claim)
    assert error.value.status_code==503
    with pg_engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM inbox_notifications")).scalar_one()==0
        assert connection.execute(text("SELECT count(*) FROM job_attempts WHERE job_id=:id"),{"id":claim.job_id}).scalar_one()==0
        assert connection.execute(text("SELECT status FROM durable_jobs WHERE id=:id"),{"id":claim.job_id}).scalar_one()=="running"
        connection.execute(text("DROP TRIGGER deny_t36_commit ON inbox_notifications"))
        connection.execute(text("DROP FUNCTION deny_t36_commit()"))
    assert case.jobs.run_claim(claim).status=="completed"


def test_caller_error_aborts_all_writes(job_case_factory,pg_engine):
    case=job_case_factory(withdraw=True)
    claim=notification_claim(case)
    with Session(pg_engine) as session:
        session.begin()
        session.execute(text("CREATE TABLE t36_caller_probe (id integer)"))
        with pytest.raises(NotificationError):
            case.jobs.run_claim(claim.model_copy(update={"generation":claim.generation+1}),session=session)
        assert not session.in_transaction()
        session.commit()
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT to_regclass('t36_caller_probe')")).scalar_one() is None


def test_additive_migration_down_up_constraints(jobs_store,pg_engine):
    from pathlib import Path
    path=Path("services/api/jobs_alembic.ini").resolve()
    with pg_engine.begin() as connection:
        parents={table:connection.execute(text("SELECT version_num FROM "+table)).scalar_one() for table in HEADS}
        config=Config(str(path));config.attributes["connection"]=connection
        command.downgrade(config,"base")
        assert connection.execute(text("SELECT to_regclass('durable_jobs')")).scalar_one() is None
        assert {table:connection.execute(text("SELECT version_num FROM "+table)).scalar_one() for table in HEADS}==parents
    migrate_jobs(pg_engine);migrate_jobs(pg_engine)
    jobs_store.assert_schema_ready()
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM pg_trigger WHERE tgname IN ('cleanup_permits_no_update','job_attempts_no_update','inbox_notifications_content_guard')")).scalar_one()==3
