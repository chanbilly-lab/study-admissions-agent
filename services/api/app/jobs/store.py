"""Same-engine lease persistence; claims and effects have explicit transactions."""

from contextlib import contextmanager
from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from ..api.v2.idempotency_canonical import canonical_request_hash
from ..plan_revisions.store import HEADS as REVISION_HEADS, MAPPERS as REVISION_MAPPERS
from ..profiles.store import database_time
from ..notifications.schemas import JOBS_HEAD, NotificationError
from .models import JobsBase, DurableJob, JobAttempt, CleanupPermit, NotificationPreference, InboxNotification
from .schemas import JobClaim, JobResult, JobsPolicy, CleanupScope, scope_hash

HEADS = {**REVISION_HEADS,"revisions_alembic_version":"0001_revisions_t35"}
MAPPERS = (*REVISION_MAPPERS,DurableJob,JobAttempt,CleanupPermit,NotificationPreference,InboxNotification)


def migrate_jobs(engine, target="head"):
    if getattr(getattr(engine,"dialect",None),"name",None)!="postgresql" or target not in {"head",JOBS_HEAD}:
        raise NotificationError()
    try:
        with engine.begin() as connection:
            config=Config(str(Path(__file__).resolve().parents[2]/"jobs_alembic.ini"))
            config.attributes["connection"]=connection
            command.upgrade(config,target)
    except Exception:
        raise NotificationError() from None


def fingerprint(value):
    return canonical_request_hash(value)


def bounded(value, maximum=8192):
    try:
        if type(value) is not dict or len(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(", ",": ")).encode())>maximum:
            raise ValueError()
        return value
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise NotificationError(422) from None


class JobsStore:
    def __init__(self, engine):
        if getattr(getattr(engine,"dialect",None),"name",None)!="postgresql":
            raise NotificationError()
        self.engine=engine

    @contextmanager
    def _work(self, session):
        if (not isinstance(session,Session) or not session.is_active or not session.in_transaction()
            or not session.get_transaction().is_active):
            raise NotificationError()
        try:
            for mapper in (None,*MAPPERS):
                binding=session.get_bind(mapper=mapper)
                if getattr(binding,"engine",binding) is not self.engine:
                    raise NotificationError()
            yield
        except SQLAlchemyError:
            raise NotificationError() from None

    def assert_schema_ready(self):
        try:
            inspector=inspect(self.engine)
            if not {*JobsBase.metadata.tables,"jobs_alembic_version"}.issubset(inspector.get_table_names()):
                raise NotificationError()
            for table in JobsBase.metadata.tables.values():
                if set(table.columns.keys())!={column["name"] for column in inspector.get_columns(table.name)}:
                    raise NotificationError()
            with self.engine.connect() as connection:
                for table, head in {**HEADS,"jobs_alembic_version":JOBS_HEAD}.items():
                    if connection.execute(text("SELECT version_num FROM "+table)).scalars().all()!=[head]:
                        raise NotificationError()
                for table,trigger in (("cleanup_permits","cleanup_permits_no_update"),("job_attempts","job_attempts_no_update"),
                    ("inbox_notifications","inbox_notifications_content_guard")):
                    if connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid=CAST(:table AS regclass) AND tgname=:trigger AND NOT tgisinternal"),
                        {"table":table,"trigger":trigger}).scalar_one_or_none() not in {"O","A"}:
                        raise NotificationError()
        except SQLAlchemyError:
            raise NotificationError() from None

    def put_job(self, session, *, kind, natural, payload, now, expires_at, is_synthetic, owner=None,
                event_id=None,outbox_id=None,assessment_id=None,preference_version=None,permit_id=None):
        with self._work(session):
            payload=bounded(payload)
            key=fingerprint(natural)
            statement=insert(DurableJob).values(id=uuid4(),kind=kind,natural_key=key,owner_user_id=owner,
                is_synthetic=is_synthetic,event_id=event_id,outbox_id=outbox_id,assessment_id=assessment_id,
                preference_version=preference_version,permit_id=permit_id,payload=payload,payload_sha256=fingerprint(payload),
                status="queued",reason="OK",attempts=0,generation=0,worker_id=None,lease_token=None,lease_until=None,
                available_at=now,created_at=now,updated_at=now,expires_at=expires_at).on_conflict_do_nothing(index_elements=[DurableJob.natural_key])
            session.execute(statement)
            row=session.scalar(select(DurableJob).where(DurableJob.natural_key==key).with_for_update().execution_options(populate_existing=True))
            if (row is None or (row.kind,row.owner_user_id,row.is_synthetic,row.event_id,row.outbox_id,row.assessment_id,row.preference_version,row.permit_id)
                !=(kind,owner,is_synthetic,event_id,outbox_id,assessment_id,preference_version,permit_id)):
                raise NotificationError(409)
            self.check_job(row)
            if kind!="release_impact" and row.payload!=payload:
                raise NotificationError(409)
            return row

    @staticmethod
    def check_job(row):
        if fingerprint(bounded(row.payload))!=row.payload_sha256:
            raise NotificationError(409)
        return row

    def get_job(self, session, job_id, *, lock=True):
        with self._work(session):
            statement=select(DurableJob).where(DurableJob.id==job_id)
            if lock:
                statement=statement.with_for_update().execution_options(populate_existing=True)
            row=session.scalar(statement)
            if row is None:
                raise NotificationError(404)
            return self.check_job(row)

    def claim(self, session, worker_id, *, now, policy):
        with self._work(session):
            policy=JobsPolicy.model_validate(policy)
            row=session.scalar(select(DurableJob).where(or_(
                (DurableJob.status=="queued") & (DurableJob.available_at<=now),
                (DurableJob.status=="running") & or_(DurableJob.lease_until<=now,DurableJob.expires_at<=now)))
                .order_by(DurableJob.available_at,DurableJob.id).limit(1).with_for_update(skip_locked=True).execution_options(populate_existing=True))
            if row is None:
                return None
            self.check_job(row)
            if now>=database_time(row.expires_at) or row.attempts>=policy.max_attempts:
                row.status,row.reason=("cancelled","EXPIRED") if now>=database_time(row.expires_at) else ("failed","ATTEMPTS_EXHAUSTED")
                row.worker_id=row.lease_token=row.lease_until=None
                row.updated_at=now
                session.flush()
                return None
            row.generation+=1
            row.attempts+=1
            row.status,row.reason="running","OK"
            row.worker_id,row.lease_token=worker_id,uuid4()
            row.lease_until=min(now+timedelta(seconds=policy.lease_seconds),database_time(row.expires_at))
            row.updated_at=now
            session.flush()
            return JobClaim(job_id=row.id,worker_id=worker_id,generation=row.generation,lease_token=row.lease_token,lease_until=database_time(row.lease_until))

    @staticmethod
    def fence(row, claim, now):
        claim=JobClaim.model_validate(claim)
        if (row.status!="running" or (row.worker_id,row.generation,row.lease_token)!=(claim.worker_id,claim.generation,claim.lease_token)
            or database_time(row.lease_until)!=claim.lease_until or not database_time(row.updated_at)<=now<claim.lease_until):
            raise NotificationError(409)

    def finish(self, session, row, claim, *, status, reason, now, audit_event_id, retry_seconds=1):
        with self._work(session):
            self.fence(row,claim,now)
            session.add(JobAttempt(job_id=row.id,generation=claim.generation,worker_id=claim.worker_id,
                lease_token=claim.lease_token,outcome=status,reason=reason,finished_at=now,audit_event_id=audit_event_id))
            row.status,row.reason,row.updated_at=status,reason,now
            row.worker_id=row.lease_token=row.lease_until=None
            if status=="queued":
                row.available_at=now+timedelta(seconds=retry_seconds)
                if reason=="OK":
                    row.attempts=0
            session.flush()
            return self.result(row)

    @staticmethod
    def result(row):
        return JobResult(job_id=row.id,kind=row.kind,status=row.status,reason=row.reason,attempts=row.attempts,generation=row.generation)

    def get_permit(self, session, permit_id):
        with self._work(session):
            row=session.scalar(select(CleanupPermit).where(CleanupPermit.id==permit_id).with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise NotificationError(409)
            scope=CleanupScope.model_validate(row.scope)
            if (scope_hash(scope)!=row.scope_sha256 or (scope.owner_user_id,scope.is_synthetic,scope.watermark,scope.purpose)
                !=(row.owner_user_id,row.is_synthetic,row.watermark,row.purpose)):
                raise NotificationError(409)
            return row,scope
