"""Owner-authorized suggestions, with historical and current proofs separated."""

from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.context import audited
from ..auth.config import AuthFlowError
from ..api.v2.idempotency_canonical import canonical_request_hash
from ..assessments.models import EligibilityAssessment
from ..assessments.store import result_fingerprint
from ..changes.service import ChangesService
from ..changes.models import AssessmentChangeImpact,PlanChangeImpact
from ..changes.store import impact_data
from ..evidence.schemas import _uuid
from ..plan_execution.models import ExecutionHead, TaskCompletion
from ..plan_execution.service import ExecutionService
from ..plans.models import PlanSourceAssessment
from ..plans.schedule_schemas import ScheduleInput
from ..plans.scheduler import schedule_plan
from ..plans.store import assessment_reference
from ..profiles.store import database_time
from ..releases.models import CatalogReleaseState
from ..rules.schemas import AssessmentData
from .diff import compare_plans
from .models import PlanReplacement
from .schemas import (RevisionError, RevisionPolicy, ProposeInput, DecisionInput, RevisionContextData,
    RevisionHistoryData, PlanPin, CompletionReference, RevisionSourceRef, DeadlineReference,
    HistoricalSchedule, RevisionData, RevisionResult, proposal_fingerprint)
from .store import RevisionsStore, _native


class RevisionService:
    def __init__(self,execution_service,changes_service,store,policy=RevisionPolicy()):
        self.execution_service,self.changes_service,self.store=execution_service,changes_service,store
        self.plans_service=execution_service.plans_service
        self.profile_service=self.plans_service.eligibility_service.profile_service
        self.auth_service=self.profile_service.auth_service
        try:
            self.policy=RevisionPolicy.model_validate(policy)
            self._initial=(execution_service,changes_service,store,self.auth_service,self.auth_service.clock,
                self.auth_service.runtime_settings,self.policy)
            self._validate()
        except Exception:
            raise RevisionError() from None

    def _validate(self):
        try:
            execution,changes,store,auth,clock,runtime,policy=self._initial
            if (not isinstance(execution,ExecutionService) or not isinstance(changes,ChangesService)
                or not isinstance(store,RevisionsStore) or self.execution_service is not execution
                or self.changes_service is not changes or self.store is not store or self.auth_service is not auth
                or auth.clock is not clock or auth.runtime_settings!=runtime or RevisionPolicy.model_validate(self.policy)!=policy
                or execution.plans_service is not self.plans_service or self.profile_service is not self.plans_service.eligibility_service.profile_service
                or changes.execution_service is not execution or changes.eligibility_service is not self.plans_service.eligibility_service
                or store.engine is not execution.store.engine or store.engine is not changes.store.engine or store.engine is not auth.store.engine):
                raise ValueError()
            execution._validate()
            changes._validate()
            return policy
        except Exception:
            raise RevisionError() from None

    def _ready(self):
        policy=self._validate()
        if not policy.enabled or not policy.allow_test_revisions or self.auth_service.runtime_settings.app_environment!="test":
            raise RevisionError()

    def _guard_session(self,session):
        self.execution_service._guard_session(session)
        self.changes_service._guard_session(session)
        with self.store._work(session):
            pass

    def _preflight(self,session=None):
        try:
            self._ready()
            if session is not None:
                self._guard_session(session)
        except Exception as error:
            self.profile_service._abort(session)
            if isinstance(error,RevisionError):
                raise
            raise RevisionError() from None

    @contextmanager
    def _transaction(self,supplied=None):
        try:
            self._preflight(supplied)
            if supplied is None:
                self.store.assert_schema_ready()
                with Session(self.store.engine) as same,same.begin():
                    self._guard_session(same)
                    yield same
            else:
                yield supplied
        except Exception as error:
            self.profile_service._abort(supplied)
            if isinstance(error,(RevisionError,AuthFlowError)):
                raise
            status=getattr(error,"status_code",503)
            raise RevisionError(status if status in {404,409,422} else 503) from None

    def _authorize(self,session,principal):
        current=self.profile_service._authorize(session,principal)
        if not current.is_synthetic:
            raise RevisionError()
        return current

    @staticmethod
    def _input(model,value):
        try:
            return model.model_validate(value)
        except (ValueError,TypeError):
            raise RevisionError(422) from None

    def _lock_pair(self,session,current,ids):
        # All methods take the same immutable plan ordering before proposal locks.
        for plan_id in sorted(set(ids),key=str):
            self.plans_service.store.get(session,plan_id,current.user_id)
            self.execution_service.store.get(session,plan_id,current.user_id)

    def _history(self,session,current,plan_id,*,state_version=None):
        plan_id=_uuid(plan_id)
        current,owned=self.profile_service.authorizer.check_owned_in_transaction(session,current,"plan",plan_id,"read")
        root=self.plans_service.store.get(session,plan_id,current.user_id)
        if root.current_version!=1 or owned.version!=1 or owned.parent_id is not None or owned.is_synthetic!=current.is_synthetic or root.is_synthetic!=current.is_synthetic:
            raise RevisionError(409)
        source=self.plans_service.store.result(session,root)
        head=self.execution_service.store.get(session,plan_id,current.user_id)
        value=self.execution_service.store.result(session,head,source,state_version=state_version)
        current,profile_root,profile_row,privacy,profile=self.profile_service._read(session,current,
            root.profile_id,version_id=root.profile_version_id)
        if (profile.profile_sha256!=root.profile_sha256 or profile.version!=root.profile_version
            or (source.draft.profile_id,source.draft.profile_version_id,source.draft.profile_sha256)!=(root.profile_id,root.profile_version_id,root.profile_sha256)):
            raise RevisionError(409)
        associations=session.scalars(select(PlanSourceAssessment).where(PlanSourceAssessment.version_id==source.version_id)
            .order_by(PlanSourceAssessment.assessment_id).limit(5).with_for_update().execution_options(populate_existing=True)).all()
        refs={r.assessment_id:r for r in source.draft.assessment_refs}
        if len(associations)!=len(refs) or {(a.assessment_id,a.result_sha256,a.plan_id) for a in associations}!={(r.assessment_id,r.result_sha256,root.id) for r in refs.values()}:
            raise RevisionError(409)
        summaries,assessments,lifetimes=[],[],[]
        for association in associations:
            # Read the immutable result only; replay_snapshot (including original
            # expression/context) is deliberately absent from this SELECT.
            columns=[c for c in EligibilityAssessment.__table__.columns if c.name not in {"replay_snapshot","snapshot_sha256"}]
            row=session.execute(select(*columns).where(EligibilityAssessment.id==association.assessment_id,
                EligibilityAssessment.owner_user_id==current.user_id).with_for_update()).mappings().one_or_none()
            if row is None:
                raise RevisionError(409)
            ref=refs[row["id"]]
            if result_fingerprint(row["payload"])!=row["result_sha256"] or row["result_sha256"]!=ref.result_sha256:
                raise RevisionError(409)
            raw=dict(row["payload"])
            raw["current_validity"]=ref.current_validity
            raw["replayed"]=False
            data=AssessmentData.model_validate(_native(raw))
            if (assessment_reference(data)!=ref or (data.profile_id,data.profile_version_id,data.profile_version,data.profile_sha256,data.profile_is_synthetic,
                data.catalogue_is_synthetic,data.target.dataset_id,data.release_id,data.assessment_id,data.version,data.engine_version,data.binding_mode)
                !=(root.profile_id,root.profile_version_id,root.profile_version,root.profile_sha256,current.is_synthetic,
                   row["catalogue_is_synthetic"],row["dataset_id"],row["release_id"],row["id"],row["version"],row["engine_version"],row["binding_mode"])
                or row["profile_id"]!=root.profile_id or row["profile_version_id"]!=root.profile_version_id
                or row["profile_version"]!=root.profile_version or row["profile_is_synthetic"]!=current.is_synthetic
                or data.assessment_at!=database_time(row["assessment_at"]) or data.expires_at!=database_time(row["expires_at"])
                or profile.profile.entry_year!=row["entry_year"]):
                raise RevisionError(409)
            state=session.scalar(select(CatalogReleaseState).where(CatalogReleaseState.release_id==row["release_id"])
                .with_for_update().execution_options(populate_existing=True))
            validity="needs_review" if profile_root.current_version_id!=profile_row.id else "unavailable"
            if state is not None and state.status in {"withdrawn","replaced"}:
                validity=state.status
            summaries.append(RevisionSourceRef(assessment_id=data.assessment_id,result_sha256=data.result_sha256,target=data.target,
                entry_year=row["entry_year"],release_id=data.release_id,requirements_version=data.requirements_version,ruleset_version=data.ruleset_version,
                stage=data.stage,original_eligibility_status=data.eligibility.status,original_validity=ref.current_validity,current_validity=validity))
            assessments.append(data)
            lifetimes.append((data.assessment_at,data.expires_at))
        if value.proposal.schedule is not None:
            recomputed=schedule_plan(ScheduleInput(draft=value.proposal.effective_draft,assessments=tuple(assessments),
                generated_at=value.proposal.created_at,**value.proposal.schedule_configuration.model_dump()))
            if recomputed!=value.proposal.schedule:
                raise RevisionError(409)
        completions=session.scalars(select(TaskCompletion).where(TaskCompletion.plan_id==root.id,
            TaskCompletion.state_version<=value.state_version)
            .order_by(TaskCompletion.state_version).limit(101).with_for_update().execution_options(populate_existing=True)).all()
        if len(completions)!=len(value.completed_tasks) or any(c.owner_user_id!=current.user_id or c.is_synthetic!=current.is_synthetic for c in completions):
            raise RevisionError(409)
        completion_refs=tuple(CompletionReference(completion_id=c.id,confirmation_id=c.confirmation_id,task_key=c.task_key,
            completed_state_version=c.state_version,completed_at=database_time(c.completed_at),source=c.source) for c in completions)
        deadlines=[]
        for ref in value.proposal.effective_draft.deadline_refs:
            event=ref.date_event
            deadlines.append(DeadlineReference(deadline_key=ref.deadline_key,assessment_id=ref.assessment_id,assessment_key=ref.assessment_key,
                purpose=ref.purpose,status=ref.status,event_id=ref.event_id,precision=event.precision if event else None,
                local_date=event.local_date if event else None,local_time=event.local_time if event else None,
                timezone=event.timezone if event else None,reference_calendar=ref.reference_calendar,official_utc_instant=None))
        schedule=None
        if value.proposal.schedule is not None:
            s=value.proposal.schedule
            schedule=HistoricalSchedule(status=s.status,generated_at=s.generated_at,horizon_start=s.horizon_start,horizon_end=s.horizon_end,
                display_timezone=s.display_timezone,weekly_hours=s.weekly_hours,constraints_complete=False,tasks=s.tasks,allocations=s.allocations)
        pin=PlanPin(plan_id=root.id,source_plan_version_id=source.version_id,state_version=value.state_version,state=value.state,
            proposal_id=value.proposal.id,proposal_state_version=value.proposal.state_version,source_draft_sha256=value.source_draft_sha256,
            draft_sha256=value.proposal.effective_draft.draft_sha256,schedule_sha256=value.proposal.schedule.schedule_sha256 if value.proposal.schedule else None,
            profile_id=root.profile_id,profile_version_id=root.profile_version_id,profile_version=root.profile_version,profile_sha256=root.profile_sha256,
            confirmation_id=value.confirmation.id if value.confirmation else None,is_synthetic=current.is_synthetic)
        history=RevisionHistoryData(schema_version="v2.t35",pin=pin,tasks=value.proposal.effective_draft.tasks,sources=tuple(summaries),deadlines=tuple(deadlines),
            schedule=schedule,completion_refs=completion_refs,created_at=value.created_at,expires_at=value.expires_at,current_actions=False)
        times=[value.created_at,value.proposal.created_at]
        if value.confirmation is not None:
            times.append(value.confirmation.confirmed_at)
        times.extend(c.completed_at for c in completion_refs)
        return SimpleNamespace(source=source,value=value,history=history,root=root,head=head,profile_root=profile_root,profile_row=profile_row,
            privacy=privacy,lifetimes=tuple(lifetimes),times=tuple(times))

    def _proposal_proof(self,session,current,value):
        # Reconstruct the pinned immutable proposals, not the current execution
        # heads. Later workspace edits or old completions remain legitimate,
        # while a rehashed fabricated revision snapshot is never authority.
        old=self._history(session,current,value.old.pin.plan_id,state_version=value.old.pin.state_version)
        new=self._history(session,current,value.new.pin.plan_id,state_version=value.new.pin.state_version)
        def retained(history):
            raw=history.model_dump(mode="json")
            for source in raw["sources"]:
                source.pop("current_validity")
            return raw
        if retained(value.old)!=retained(old.history) or retained(value.new)!=retained(new.history):
            raise RevisionError(409)
        for record in (old,new):
            if (any(t>value.created_at for t in record.times)
                or any(not start<=value.created_at<end for start,end in record.lifetimes)
                or not database_time(record.profile_row.confirmed_at)<=value.created_at<database_time(record.profile_row.expires_at)
                or not record.source.created_at<=value.created_at<record.source.expires_at):
                raise RevisionError(409)
        changed=self._creation_impacts(session,current,old,value.created_at)
        if compare_plans(old.history,new.history,source_business_changed=changed)!=value.diff:
            raise RevisionError(409)
        return old,new

    def _creation_impacts(self,session,current,record,created_at):
        # The original proposal's bounded evidence set excludes later events.
        # Reject/get must not become unavailable merely because new events have
        # accumulated after this immutable suggestion was created.
        rows=session.scalars(select(AssessmentChangeImpact).join(PlanSourceAssessment,
            PlanSourceAssessment.assessment_id==AssessmentChangeImpact.assessment_id)
            .where(PlanSourceAssessment.plan_id==record.root.id,
                PlanSourceAssessment.version_id==record.source.version_id,
                AssessmentChangeImpact.owner_user_id==current.user_id,
                AssessmentChangeImpact.created_at<=created_at)
            .order_by(AssessmentChangeImpact.created_at,AssessmentChangeImpact.event_id,
                AssessmentChangeImpact.assessment_id).limit(101).with_for_update()).all()
        if len(rows)>100 or any(row.is_synthetic!=current.is_synthetic for row in rows):
            raise RevisionError(409)
        values=tuple(impact_data(row,plan_id=record.root.id) for row in rows)
        sources={source.assessment_id:source for source in record.history.sources}
        for impact in values:
            source=sources.get(impact.assessment_id)
            if source is None or (impact.offering_id,impact.entry_year,impact.before_release_id)!=(
                source.target.offering_id,source.entry_year,source.release_id):
                raise RevisionError(409)
        self.changes_service._impact_receipts(session,values)
        durable=session.scalars(select(PlanChangeImpact).where(PlanChangeImpact.plan_id==record.root.id,
            PlanChangeImpact.owner_user_id==current.user_id,PlanChangeImpact.created_at<=created_at)
            .order_by(PlanChangeImpact.event_id,PlanChangeImpact.assessment_id).limit(101).with_for_update()).all()
        if len(durable)>100:
            raise RevisionError(409)
        actual={(value.event_id,value.assessment_id):value for value in values}
        if any(row.plan_version_id!=record.source.version_id or row.is_synthetic!=current.is_synthetic
            or actual.get((row.event_id,row.assessment_id))!=impact_data(row) for row in durable):
            raise RevisionError(409)
        return any(value.needs_review for value in values)

    def _final(self,session,current,records,*,new_current=None,revision=None):
        if new_current is not None:
            # This helper ends with Profile._final's LAST SQL and returns exactly
            # that fresh time; every following check remains local.
            now=self.execution_service._final(session,current,((new_current.source,new_current.value),))
        else:
            privacy=records[-1].privacy if records else self.profile_service._proof(session,current)
            now=self.profile_service._final(session,current,privacy,
                tuple(r.profile_row for r in records),tuple(r.profile_root for r in records))
        self._ready()
        for record in records:
            self.profile_service._binding(record.profile_row,record.privacy)
            if (not database_time(record.profile_row.confirmed_at)<=now<database_time(record.profile_row.expires_at)
                or not record.source.created_at<=now<record.source.expires_at
                or any(t>now for t in record.times) or any(not start<=now<end for start,end in record.lifetimes)):
                raise RevisionError(409)
        if revision is not None:
            if not revision.created_at<=now<revision.expires_at or (revision.decision is not None and revision.decision.decided_at>now):
                raise RevisionError(409)
        return now

    def _audit(self,session,current,plan_id,version):
        return self.auth_service.store.audit.success(session,"authorization.owned.execute",actor=current,
            object_type="plan",object_id=plan_id,object_version=version,now=self.auth_service._now())

    def preflight(self,principal):
        self._preflight()
        with self._transaction() as same:
            current=self._authorize(same,principal)
            self._final(same,current,())

    def context(self,principal,*,session=None):
        if not self._validate().enabled:
            return RevisionContextData(schema_version="v2.t35",can_read_history=False,can_propose=False,can_decide=False,
                reason="processing_disabled",is_synthetic=principal.is_synthetic)
        with self._transaction(session) as same:
            current=self._authorize(same,principal)
            result=RevisionContextData(schema_version="v2.t35",can_read_history=True,can_propose=True,can_decide=True,reason="ready",is_synthetic=current.is_synthetic)
            self._final(same,current,())
        return result

    def get_history(self,principal,plan_id,*,session=None):
        self._preflight(session)
        return self._get_history(principal,plan_id,session=session)

    @audited("authorization.owned.execute")
    def _get_history(self,principal,plan_id,*,session=None):
        with self._transaction(session) as same:
            current=self._authorize(same,principal)
            record=self._history(same,current,plan_id)
            self._audit(same,current,record.history.pin.plan_id,record.history.pin.state_version)
            self._final(same,current,(record,))
            result=record.history
        return result

    def propose(self,principal,request,*,session=None):
        self._preflight(session)
        return self._propose(principal,request,session=session)

    @audited("authorization.owned.execute")
    def _propose(self,principal,request,*,session=None):
        with self._transaction(session) as same:
            request=self._input(ProposeInput,request)
            current=self._authorize(same,principal)
            self._lock_pair(same,current,(request.old_plan_id,request.new_plan_id))
            old=self._history(same,current,request.old_plan_id)
            new=self._history(same,current,request.new_plan_id)
            if (old.value.state!="confirmed" or new.value.state!="draft" or old.value.state_version!=request.expected_old_state_version
                or new.value.state_version!=request.expected_new_state_version or old.root.profile_id!=new.root.profile_id):
                raise RevisionError(409)
            # A complete current read is required for the new explicitly chosen draft.
            self.execution_service._read(same,current,new.root.id)
            impacts=self.changes_service.get_plan_impacts(current,old.root.id,session=same)
            diff=compare_plans(old.history,new.history,source_business_changed=any(v.needs_review for v in impacts.items))
            request_sha=canonical_request_hash(request.model_dump(mode="json"))
            row=self.store.find_request(same,current.user_id,request_sha)
            replayed=row is not None
            if row is None:
                now=self.auth_service._now()
                raw={"schema_version":"v2.t35","revision_id":uuid4(),"revision_version":1,"status":"proposed","old":old.history,"new":new.history,
                    "diff":diff,"decision":None,"replacement":None,"created_at":now,"expires_at":min(old.history.expires_at,new.history.expires_at),
                    "is_synthetic":current.is_synthetic,"proposal_sha256":"0"*64}
                # Hash the actual canonical wire rather than a different UTC spelling.
                skeleton=RevisionData.model_construct(**raw).model_dump(mode="json")
                raw["proposal_sha256"]=proposal_fingerprint(skeleton)
                value=RevisionData.model_validate(raw)
                audit=self._audit(same,current,new.root.id,new.value.state_version)
                row=self.store.create(same,current,value,request_sha,audit_event_id=audit.id)
            value=self.store.result(same,row)
            self._proposal_proof(same,current,value)
            if value.old.pin!=old.history.pin or value.new.pin!=new.history.pin or value.old.completion_refs!=old.history.completion_refs:
                raise RevisionError(409)
            result=RevisionResult(revision=value,replayed=replayed)
            self._audit(same,current,new.root.id,new.value.state_version)
            self._final(same,current,(old,new),new_current=new,revision=value)
        return result

    def get_revision(self,principal,revision_id,*,session=None):
        self._preflight(session)
        return self._get_revision(principal,revision_id,session=session)

    @audited("authorization.owned.execute")
    def _get_revision(self,principal,revision_id,*,session=None):
        with self._transaction(session) as same:
            current=self._authorize(same,principal)
            revision_id=_uuid(revision_id)
            hint=self.store.hint(same,revision_id,current.user_id)
            self._lock_pair(same,current,hint)
            row=self.store.get(same,revision_id,current.user_id)
            old=self._history(same,current,row.old_plan_id)
            new=self._history(same,current,row.new_plan_id)
            value=self.store.result(same,row)
            self._proposal_proof(same,current,value)
            self._audit(same,current,new.root.id,new.value.state_version)
            self._final(same,current,(old,new),revision=value)
        return value

    def decide(self,principal,revision_id,request,*,session=None):
        self._preflight(session)
        return self._decide(principal,revision_id,request,session=session)

    @audited("authorization.owned.execute")
    def _decide(self,principal,revision_id,request,*,session=None):
        with self._transaction(session) as same:
            request=self._input(DecisionInput,request)
            current=self._authorize(same,principal)
            revision_id=_uuid(revision_id)
            hint=self.store.hint(same,revision_id,current.user_id)
            self._lock_pair(same,current,hint)
            row=self.store.get(same,revision_id,current.user_id)
            old=self._history(same,current,row.old_plan_id)
            new=self._history(same,current,row.new_plan_id)
            value=self.store.result(same,row)
            self._proposal_proof(same,current,value)
            if request.action=="accept":
                if (old.history.pin!=value.old.pin or new.history.pin!=value.new.pin
                    or old.history.completion_refs!=value.old.completion_refs or new.value.state!="draft"):
                    raise RevisionError(409)
                self.execution_service._read(same,current,new.root.id)
                # Globally unique predecessor/successor plus increasing creation
                # order prevents cycles without an unbounded graph traversal.
                if old.value.created_at>new.value.created_at:
                    raise RevisionError(409)
                occupied=same.scalars(select(PlanReplacement).where((PlanReplacement.old_plan_id==old.root.id)
                    |(PlanReplacement.new_plan_id==new.root.id)).with_for_update()).all()
                if any(r.revision_id!=row.id for r in occupied):
                    raise RevisionError(409)
            request_sha=canonical_request_hash({"revision_id":str(row.id),"request":request.model_dump(mode="json")})
            audit=self._audit(same,current,new.root.id,new.value.state_version)
            replayed=self.store.decide(same,row,request,request_sha=request_sha,now=self.auth_service._now(),audit_event_id=audit.id)
            value=self.store.result(same,row)
            result=RevisionResult(revision=value,replayed=replayed)
            self._audit(same,current,new.root.id,new.value.state_version)
            self._final(same,current,(old,new),new_current=new if request.action=="accept" else None,revision=value)
        return result
