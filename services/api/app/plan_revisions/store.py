"""Same-session append-only persistence with exact immutable proposal replay."""

from contextlib import contextmanager
from datetime import date, datetime, time
import json
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..api.v2.idempotency_canonical import canonical_request_hash
from ..changes.store import HEADS as CHANGES_HEADS, MAPPERS as CHANGES_MAPPERS
from ..profiles.store import database_time
from .models import RevisionsBase, RevisionProposal, RevisionDecision, PlanReplacement
from .schemas import (REVISIONS_HEAD, MAX_SNAPSHOT_BYTES, RevisionError, RevisionData,
    RevisionDecisionData, ReplacementData)

HEADS={**CHANGES_HEADS,"changes_alembic_version":"0001_changes_t34"}
MAPPERS=(*CHANGES_MAPPERS,RevisionProposal,RevisionDecision,PlanReplacement)


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2]/"revisions_alembic.ini"))


def migrate_revisions(engine,target="head"):
    if getattr(getattr(engine,"dialect",None),"name",None)!="postgresql" or target not in {"head",REVISIONS_HEAD}:
        raise RevisionError()
    try:
        with engine.begin() as connection:
            config=migration_config()
            config.attributes["connection"]=connection
            command.upgrade(config,target)
    except Exception:
        raise RevisionError() from None


def bounded_payload(value):
    try:
        if type(value) is not dict or len(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(", ",": ")).encode())>MAX_SNAPSHOT_BYTES:
            raise ValueError()
        return value
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise RevisionError(422) from None


def _native(value):
    if type(value) is list:
        return [_native(v) for v in value]
    if type(value) is not dict:
        return value
    result={}
    instants={"created_at","expires_at","generated_at","assessment_at","completed_at","decided_at","accepted_at","valid_from","valid_until","calculated_utc_instant","utc_instant",
              "horizon_start","horizon_end","start_at","end_at","internal_goal"}
    for key,item in value.items():
        if type(item) is str and key in instants:
            item=datetime.fromisoformat(item)
        elif type(item) is str and key in {"local_date","week_start"}:
            item=date.fromisoformat(item)
        elif type(item) is str and key=="local_time":
            item=time.fromisoformat(item)
        else:
            item=_native(item)
        result[key]=item
    return result


class RevisionsStore:
    def __init__(self,engine):
        if getattr(getattr(engine,"dialect",None),"name",None)!="postgresql":
            raise RevisionError()
        self.engine=engine

    @contextmanager
    def _work(self,session):
        if not isinstance(session,Session) or not session.is_active or not session.in_transaction() or not session.get_transaction().is_active:
            raise RevisionError()
        try:
            for mapper in (None,*MAPPERS):
                bind=session.get_bind(mapper=mapper)
                if getattr(bind,"engine",bind) is not self.engine:
                    raise RevisionError()
            yield
        except IntegrityError as error:
            name=getattr(getattr(error.orig,"diag",None),"constraint_name",None)
            if getattr(error.orig,"sqlstate",None)=="23505" and name in {
                "uq_revision_natural_request","uq_revision_single_decision","uq_revision_old_successor","uq_revision_new_predecessor","uq_revision_single_relationship"}:
                raise RevisionError(409) from None
            raise RevisionError() from None
        except SQLAlchemyError:
            raise RevisionError() from None

    def assert_schema_ready(self):
        try:
            inspector=inspect(self.engine)
            if not {*RevisionsBase.metadata.tables,"revisions_alembic_version"}.issubset(inspector.get_table_names()):
                raise RevisionError()
            for table in RevisionsBase.metadata.tables.values():
                if set(table.columns.keys())!={c["name"] for c in inspector.get_columns(table.name)}:
                    raise RevisionError()
            with self.engine.connect() as connection:
                for table,head in {**HEADS,"revisions_alembic_version":REVISIONS_HEAD}.items():
                    if connection.execute(text("SELECT version_num FROM "+table)).scalars().all()!=[head]:
                        raise RevisionError()
                for table in RevisionsBase.metadata.tables:
                    enabled=connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid=CAST(:name AS regclass) AND tgname=:trigger AND NOT tgisinternal"),
                        {"name":table,"trigger":table+"_no_update"}).scalar_one_or_none()
                    if enabled not in {"O","A"}:
                        raise RevisionError()
        except SQLAlchemyError:
            raise RevisionError() from None

    def find_request(self,session,owner,request_sha):
        with self._work(session):
            return session.scalar(select(RevisionProposal).where(RevisionProposal.owner_user_id==owner,
                RevisionProposal.request_sha256==request_sha).with_for_update().execution_options(populate_existing=True))

    def get(self,session,revision_id,owner):
        with self._work(session):
            row=session.scalar(select(RevisionProposal).where(RevisionProposal.id==revision_id,RevisionProposal.owner_user_id==owner)
                .with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise RevisionError(404)
            return row

    def hint(self,session,revision_id,owner):
        with self._work(session):
            value=session.execute(select(RevisionProposal.old_plan_id,RevisionProposal.new_plan_id)
                .where(RevisionProposal.id==revision_id,RevisionProposal.owner_user_id==owner)).one_or_none()
            if value is None:
                raise RevisionError(404)
            return value

    def create(self,session,current,value,request_sha,*,audit_event_id):
        with self._work(session):
            value=RevisionData.model_validate(value)
            a,b=value.old.pin,value.new.pin
            row=RevisionProposal(id=value.revision_id,owner_user_id=current.user_id,is_synthetic=value.is_synthetic,
                old_plan_id=a.plan_id,new_plan_id=b.plan_id,old_source_version_id=a.source_plan_version_id,new_source_version_id=b.source_plan_version_id,
                old_proposal_id=a.proposal_id,new_proposal_id=b.proposal_id,expected_old_state_version=a.state_version,expected_new_state_version=b.state_version,
                request_sha256=request_sha,payload_sha256=value.proposal_sha256,payload=bounded_payload(value.model_dump(mode="json")),
                created_at=value.created_at,expires_at=value.expires_at,audit_event_id=audit_event_id)
            session.add(row)
            session.flush()
            return row

    def decide(self,session,row,request,*,request_sha,now,audit_event_id):
        with self._work(session):
            prior=session.scalar(select(RevisionDecision).where(RevisionDecision.revision_id==row.id)
                .with_for_update().execution_options(populate_existing=True))
            if prior is not None:
                if prior.request_sha256!=request_sha or prior.action!=request.action:
                    raise RevisionError(409)
                return True
            if request.expected_revision_version!=1:
                raise RevisionError(409)
            decision=RevisionDecision(id=uuid4(),revision_id=row.id,old_plan_id=row.old_plan_id,new_plan_id=row.new_plan_id,
                owner_user_id=row.owner_user_id,is_synthetic=row.is_synthetic,action=request.action,revision_version=2,
                request_sha256=request_sha,decided_at=now,expires_at=row.expires_at,audit_event_id=audit_event_id)
            session.add(decision)
            session.flush()
            if request.action=="accept":
                session.add(PlanReplacement(id=uuid4(),revision_id=row.id,decision_id=decision.id,old_plan_id=row.old_plan_id,new_plan_id=row.new_plan_id,
                    owner_user_id=row.owner_user_id,is_synthetic=row.is_synthetic,action="accept",accepted_at=now,expires_at=row.expires_at,audit_event_id=audit_event_id))
                session.flush()
            return False

    def result(self,session,row):
        with self._work(session):
            try:
                raw=bounded_payload(row.payload)
                value=RevisionData.model_validate(_native(raw))
                a,b=value.old.pin,value.new.pin
                if (value.model_dump(mode="json")!=raw or value.status!="proposed" or value.revision_version!=1
                    or value.proposal_sha256!=row.payload_sha256 or value.revision_id!=row.id
                    or value.created_at!=database_time(row.created_at) or value.expires_at!=database_time(row.expires_at)
                    or (a.plan_id,b.plan_id,a.source_plan_version_id,b.source_plan_version_id,a.proposal_id,b.proposal_id,a.state_version,b.state_version,a.is_synthetic)
                    !=(row.old_plan_id,row.new_plan_id,row.old_source_version_id,row.new_source_version_id,row.old_proposal_id,row.new_proposal_id,
                       row.expected_old_state_version,row.expected_new_state_version,row.is_synthetic)):
                    raise ValueError()
                decision=session.scalar(select(RevisionDecision).where(RevisionDecision.revision_id==row.id)
                    .with_for_update().execution_options(populate_existing=True))
                relationship=session.scalar(select(PlanReplacement).where(PlanReplacement.revision_id==row.id)
                    .with_for_update().execution_options(populate_existing=True))
                values=value.model_dump()
                if decision is not None:
                    if (decision.old_plan_id,decision.new_plan_id,decision.owner_user_id,decision.is_synthetic,decision.expires_at)!=(row.old_plan_id,row.new_plan_id,row.owner_user_id,row.is_synthetic,row.expires_at):
                        raise ValueError()
                    values.update(status={"accept":"accepted","reject":"rejected"}[decision.action],revision_version=2,
                        decision=RevisionDecisionData(decision_id=decision.id,action=decision.action,revision_version=decision.revision_version,decided_at=database_time(decision.decided_at)))
                if relationship is not None:
                    if decision is None or decision.action!="accept" or relationship.action!="accept" or (relationship.decision_id,relationship.old_plan_id,relationship.new_plan_id,
                        relationship.owner_user_id,relationship.is_synthetic,relationship.expires_at)!=(decision.id,row.old_plan_id,row.new_plan_id,row.owner_user_id,row.is_synthetic,row.expires_at):
                        raise ValueError()
                    values["replacement"]=ReplacementData(relationship_id=relationship.id,old_plan_id=relationship.old_plan_id,new_plan_id=relationship.new_plan_id,
                        accepted_at=database_time(relationship.accepted_at),new_plan_confirmed=False,completion_credit_transferred=False)
                if decision is not None and (decision.action=="accept")!=(relationship is not None):
                    raise ValueError()
                return RevisionData.model_validate(values)
            except (ValueError,TypeError,KeyError,OverflowError):
                raise RevisionError() from None
