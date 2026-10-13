"""Explicit confirmation and declared progress, with one final authority time."""

import base64
from contextlib import contextmanager
import json
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.context import audited
from ..auth.authorization import AuthorizationError
from ..auth.config import AuthFlowError
from ..idempotency.schemas import IdempotencyError, ResourceReceipt
from ..idempotency.service import IdempotencyService
from ..plans.drafts import build_plan_draft
from ..plans.schemas import DraftBuildInput, PlanCreateInput, PlanError
from ..plans.schedule_schemas import ScheduleInput, ScheduleError
from ..plans.scheduler import schedule_plan
from ..plans.service import PlansService
from ..plans.store import assessment_reference
from ..public_catalog.schemas import PublicCatalogError
from ..rules.assessment_engine import evaluate_eligibility
from ..api.v2.idempotency_canonical import canonical_request_hash
from ..evidence.schemas import _uuid
from .models import ExecutionHead
from .schemas import (ExecutionError, ExecutionPolicy, ExecutionContextData, ExecutionPage, ExecutionSummary,
    WorkspaceInput, ConfirmInput, CompleteInput, ConfirmResult, CompleteResult, MAX_SOURCE_BYTES)
from .store import ExecutionStore, bounded_payload, effective_draft


class ExecutionService:
    def __init__(self, plans_service, idempotency_service, store, policy=ExecutionPolicy()):
        self.plans_service, self.idempotency_service, self.store = plans_service, idempotency_service, store
        try:
            self.policy = ExecutionPolicy.model_validate(policy)
            self._initial_policy = self.policy
        except (ValueError, TypeError):
            raise ExecutionError() from None
        self.auth_service = plans_service.auth_service
        self._initial_clock = self.auth_service.clock
        self._initial_runtime = self.auth_service.runtime_settings
        self._validate()

    def _validate(self):
        try:
            if (not isinstance(self.plans_service, PlansService) or not isinstance(self.idempotency_service, IdempotencyService)
                or not isinstance(self.store, ExecutionStore) or self.plans_service.auth_service is not self.auth_service
                or self.idempotency_service.auth_service is not self.auth_service
                or self.idempotency_service.privacy_service is not self.plans_service.eligibility_service.profile_service.privacy_service
                or self.store.engine is not self.auth_service.store.engine
                or self.plans_service.store.engine is not self.store.engine
                or self.auth_service.clock is not self._initial_clock or self.auth_service.runtime_settings != self._initial_runtime):
                raise ExecutionError()
            self.plans_service._validate()
            self.idempotency_service._validate()
            current = ExecutionPolicy.model_validate(self.policy)
            if current != self._initial_policy:
                raise ExecutionError()
            return current
        except (ValueError, TypeError, AttributeError):
            raise ExecutionError() from None

    def _guard_session(self, session):
        self.plans_service._guard_session(session)
        self.idempotency_service._guard_session(session)
        with self.store._work(session):
            pass

    @contextmanager
    def _transaction(self, supplied=None):
        try:
            self._validate()
            if supplied is None:
                self.store.assert_schema_ready()
                with Session(self.store.engine) as same, same.begin():
                    self._guard_session(same)
                    yield same
            else:
                self._guard_session(supplied)
                yield supplied
        except Exception as error:
            if isinstance(supplied, Session):
                try:
                    supplied.rollback()
                except Exception:
                    pass
            if isinstance(error, (ExecutionError, AuthFlowError)):
                raise
            if isinstance(error, (PlanError, ScheduleError, IdempotencyError, PublicCatalogError)):
                raise ExecutionError(error.status_code if error.status_code in {404,409,422} else 503) from None
            raise ExecutionError() from None

    def _authorize(self, session, principal):
        policy = self._validate()
        self._guard_session(session)
        current = self.plans_service._authorize(session, principal)
        if (not policy.enabled or not policy.allow_test_execution or not current.is_synthetic
            or self.auth_service.runtime_settings.app_environment != "test"):
            raise ExecutionError()
        return current

    @staticmethod
    def _input(model, value):
        try:
            return model.model_validate(value)
        except (ValueError, TypeError):
            raise ExecutionError(422) from None

    def _read(self, session, current, plan_id, *, state_version=None):
        plan_id = _uuid(plan_id)
        source = self.plans_service.get_draft(current, plan_id, session=session)
        head = self.store.get(session, plan_id, current.user_id)
        value = self.store.result(session, head, source, state_version=state_version)
        return source, head, value

    def _final(self, session, current, records, *, receipt_expiry=None, first_confirmation=False):
        # Retain structured proofs until the LAST SQL, then use one fresh time.
        profiles = self.plans_service.eligibility_service.profile_service
        eligibility = self.plans_service.eligibility_service
        proofs, versions, roots, sources = [], [], [], []
        privacy = None
        for source, value in records:
            fresh, rows = self.plans_service._sources(session, current,
                tuple(r.assessment_id for r in source.draft.assessment_refs))
            if tuple(assessment_reference(a) for a in fresh) != source.draft.assessment_refs:
                raise ExecutionError(409)
            if value.proposal.schedule is not None:
                recomputed = schedule_plan(ScheduleInput(draft=value.proposal.effective_draft,assessments=fresh,
                    generated_at=value.proposal.created_at,**value.proposal.schedule_configuration.model_dump()))
                if recomputed != value.proposal.schedule:
                    raise ExecutionError(409)
            current, profile_root, version, privacy, profile = profiles._read(session,current,
                source.draft.profile_id,version_id=source.draft.profile_version_id)
            if profile_root.current_version_id != version.id:
                raise ExecutionError(409)
            versions.append(version)
            roots.append(profile_root)
            sources.extend(fresh)
            for data, row in zip(fresh, rows, strict=True):
                validity, proof = eligibility._historical(session,row,data,profile)
                if validity != data.current_validity:
                    raise ExecutionError(409)
                proofs.append((data,proof,profile))
        if privacy is None:
            # Empty lists still require current original core authority.
            current = profiles._authorize(session,current)
            privacy = profiles._proof(session,current)
        now = profiles._final(session,current,privacy,tuple(versions),tuple(roots))
        policy = self._validate()
        if not policy.enabled or not policy.allow_test_execution or not current.is_synthetic:
            raise ExecutionError()
        if receipt_expiry is not None and now >= receipt_expiry:
            raise ExecutionError(409)
        for source, value in records:
            times = [value.created_at,value.proposal.created_at]
            if value.confirmation is not None:
                times.append(value.confirmation.confirmed_at)
            times.extend(c.completed_at for c in value.completed_tasks)
            if (any(t > now for t in times) or not source.created_at <= now < source.expires_at
                or not value.created_at <= now < value.expires_at):
                raise ExecutionError(409)
            if first_confirmation:
                self._unelapsed_schedule(value.proposal.schedule,now)
        if any(not a.assessment_at <= now < a.expires_at for a in sources):
            raise ExecutionError(409)
        for data, proof, profile in proofs:
            if proof is None:
                continue
            release, state, members, bundle, policies, permissions = proof
            try:
                eligibility.proof.final_deadlines(members,((release,state),),now)
                if bundle is not None and not bundle.valid_from <= now < bundle.valid_until:
                    raise PublicCatalogError(409)
                if any(not p.valid_from <= now < p.valid_until or not eligibility._permission_at(p,k,m,members,now)
                       for p,k,m in policies):
                    raise PublicCatalogError(409)
                if bundle is not None:
                    outcome = evaluate_eligibility(bundle.expression,eligibility._context(profile.profile,bundle.expression,now),deferrals=permissions)
                    if (outcome.status,outcome.obligations) != (data.eligibility.status,data.eligibility.obligations):
                        raise PublicCatalogError(409)
            except PublicCatalogError:
                raise ExecutionError(409) from None
        return now

    @staticmethod
    def _unelapsed_schedule(schedule, now):
        if (schedule is None or now >= schedule.horizon_end
            or any(a.start_at < now for a in schedule.allocations)
            or any(t.start_at < now for t in schedule.tasks if t.status == "milestone")):
            raise ExecutionError(409)

    def _audit(self, session, current, plan_id, state_version):
        return self.auth_service.store.audit.success(session,"authorization.owned.execute",actor=current,
            object_type="plan",object_id=plan_id,object_version=state_version,now=self.auth_service._now())

    def preflight(self, principal):
        with self._transaction() as same:
            current = self._authorize(same,principal)
            self._final(same,current,())

    def context(self, principal, *, session=None):
        with self._transaction(session) as same:
            current, _ = self.plans_service.eligibility_service.profile_service.authorizer._refresh(principal,same)
            policy = self._validate()
            enabled = policy.enabled and policy.allow_test_execution
            if enabled:
                current = self._authorize(same,current)
                self._final(same,current,())
            can_confirm = enabled and self.idempotency_service.policy.enabled
            result = ExecutionContextData(schema_version="v2.t32",can_create=enabled,can_read=enabled,
                can_edit=enabled,can_confirm=can_confirm,can_complete=enabled,
                reason="ready" if enabled else "processing_disabled",is_synthetic=current.is_synthetic)
        return result

    @audited("authorization.owned.execute")
    def create_plan(self, principal, request, *, session=None):
        with self._transaction(session) as same:
            request = self._input(PlanCreateInput,request)
            current = self._authorize(same,principal)
            assessments, rows = self.plans_service._sources(same,current,request.assessment_ids)
            rules, policies = self.plans_service._snapshots(assessments,rows)
            now = self.auth_service._now()
            preview = build_plan_draft(DraftBuildInput(assessments=assessments,confirmed=True,generated_at=now,
                study_goals=request.study_goals,estimate_overrides=request.estimate_overrides,rule_bundles=rules,deadline_bundles=policies))
            bounded_payload(preview.model_dump(mode="json"),MAX_SOURCE_BYTES)
            plan_id = uuid4()
            self.plans_service.eligibility_service.profile_service.authorizer.register_owned(current,"plan",resource_id=plan_id,session=same)
            audit = self._audit(same,current,plan_id,1)
            old_root = self.plans_service.store.create(same,current,preview,plan_id=plan_id,audit_event_id=audit.id,now=now)
            source = self.plans_service.store.result(same,old_root)
            head = self.store.create(same,current,source,audit_event_id=audit.id)
            result = self.store.result(same,head,source)
            self._audit(same,current,plan_id,1)
            self._final(same,current,((source,result),))
        return result

    @audited("authorization.owned.execute")
    def get_plan(self, principal, plan_id, *, session=None):
        with self._transaction(session) as same:
            current = self._authorize(same,principal)
            source,head,result = self._read(same,current,plan_id)
            self._audit(same,current,head.plan_id,head.state_version)
            self._final(same,current,((source,result),))
        return result

    def get_version(self, principal, plan_id, state_version, *, session=None):
        with self._transaction(session) as same:
            if type(state_version) is not int or state_version < 1:
                raise ExecutionError(422)
            current = self._authorize(same,principal)
            source,head,latest = self._read(same,current,plan_id)
            result = self.store.result(same,head,source,state_version=state_version)
            self._audit(same,current,head.plan_id,state_version)
            self._final(same,current,((source,latest),(source,result)))
        return result

    @staticmethod
    def _summary(value):
        return ExecutionSummary(plan_id=value.plan_id,state_version=value.state_version,state=value.state,
            proposal_id=value.proposal.id,draft_sha256=value.proposal.effective_draft.draft_sha256,
            schedule_sha256=value.proposal.schedule.schedule_sha256 if value.proposal.schedule is not None else None,
            confirmation_id=value.confirmation.id if value.confirmation is not None else None,
            completed_count=len(value.completed_tasks),created_at=value.created_at,expires_at=value.expires_at,is_synthetic=value.is_synthetic)

    def list_plans(self, principal, *, limit=20, cursor=None, session=None):
        with self._transaction(session) as same:
            current = self._authorize(same,principal)
            if type(limit) is not int or not 1 <= limit <= 20:
                raise ExecutionError(422)
            last = None
            if cursor is not None:
                try:
                    if type(cursor) is not str or len(cursor)>1024:
                        raise ValueError()
                    raw = json.loads(base64.urlsafe_b64decode(cursor + "="*(-len(cursor)%4)))
                    if set(raw)!={"owner","last"} or raw["owner"]!=str(current.user_id):
                        raise ValueError()
                    last = _uuid(raw["last"])
                except (ValueError,TypeError,KeyError):
                    raise ExecutionError(409) from None
            query = select(ExecutionHead).where(ExecutionHead.owner_user_id==current.user_id)
            if last is not None:
                query=query.where(ExecutionHead.plan_id>last)
            heads = same.scalars(query.order_by(ExecutionHead.plan_id).limit(limit+1).with_for_update()
                .execution_options(populate_existing=True)).all()
            records=[]
            for head in heads[:limit]:
                source,locked,value=self._read(same,current,head.plan_id)
                records.append((source,value))
            items=tuple(self._summary(value) for source,value in records)
            next_cursor=None
            if len(heads)>limit:
                next_cursor=base64.urlsafe_b64encode(json.dumps({"owner":str(current.user_id),"last":str(heads[limit-1].plan_id)},
                    sort_keys=True,separators=(",",":")).encode()).decode().rstrip("=")
            result=ExecutionPage(items=items,next_cursor=next_cursor)
            self._final(same,current,tuple(records))
        return result

    @audited("authorization.owned.execute")
    def update_workspace(self, principal, plan_id, request, *, session=None):
        with self._transaction(session) as same:
            request=self._input(WorkspaceInput,request)
            current=self._authorize(same,principal)
            source,head,old=self._read(same,current,plan_id)
            if head.state!="draft" or head.state_version!=request.expected_version:
                raise ExecutionError(409)
            draft=effective_draft(source.draft,request.estimate_overrides)
            now=self.auth_service._now()
            assessments,_=self.plans_service._sources(same,current,tuple(r.assessment_id for r in source.draft.assessment_refs))
            schedule=None if request.schedule is None else schedule_plan(ScheduleInput(draft=draft,assessments=assessments,
                generated_at=now,**request.schedule.model_dump()))
            audit=self._audit(same,current,head.plan_id,head.state_version+1)
            self.store.append_proposal(same,head,request,draft,schedule,now=now,audit_event_id=audit.id)
            result=self.store.result(same,head,source)
            self._audit(same,current,head.plan_id,head.state_version)
            self._final(same,current,((source,result),))
        return result

    def _confirmation_proof(self, session, current, plan_id, request, receipt):
        source,head,value=self._read(session,current,plan_id)
        confirmation=value.confirmation
        if (receipt.kind!="plan" or receipt.resource_id!=head.plan_id or confirmation is None
            or receipt.version!=confirmation.confirmed_state_version
            or request.expected_version!=value.proposal.state_version
            or request.expected_draft_sha256!=value.proposal.effective_draft.draft_sha256
            or value.proposal.schedule is None or request.expected_schedule_sha256!=value.proposal.schedule.schedule_sha256):
            raise ExecutionError(409)
        assessments,_=self.plans_service._sources(session,current,tuple(r.assessment_id for r in source.draft.assessment_refs))
        schedule=schedule_plan(ScheduleInput(draft=value.proposal.effective_draft,assessments=assessments,
            generated_at=value.proposal.created_at,**value.proposal.schedule_configuration.model_dump()))
        if schedule!=value.proposal.schedule or schedule.status!="ready" or schedule.weekly_hours is None:
            raise ExecutionError(409)
        self._final(session,current,((source,value),))
        return source,value

    @audited("authorization.owned.execute")
    def confirm_plan(self, principal, plan_id, request, key: SecretStr, *, session=None):
        with self._transaction(session) as same:
            request=self._input(ConfirmInput,request)
            plan_id=_uuid(plan_id)
            current=self._authorize(same,principal)
            payload={"plan_id":str(plan_id),"request":request.model_dump(mode="json")}
            request_sha=canonical_request_hash(payload)
            failure=[None]
            def protected(callback):
                def call(*args):
                    try:
                        return callback(*args)
                    except (ExecutionError,PlanError,ScheduleError,AuthFlowError,PublicCatalogError) as error:
                        failure[0]=error
                        raise
                return call
            def perform(active,actor):
                source,head,value=self._read(active,actor,plan_id)
                if (head.state!="draft" or head.state_version!=request.expected_version
                    or value.proposal.effective_draft.draft_sha256!=request.expected_draft_sha256
                    or value.proposal.schedule is None or value.proposal.schedule.schedule_sha256!=request.expected_schedule_sha256
                    or value.proposal.schedule.status!="ready" or value.proposal.schedule.weekly_hours is None):
                    raise ExecutionError(409)
                self._unelapsed_schedule(value.proposal.schedule,self.auth_service._now())
                audit=self._audit(active,actor,plan_id,head.state_version+1)
                self.store.confirm(active,head,request_sha,expected_version=request.expected_version,
                    now=self.auth_service._now(),audit_event_id=audit.id)
                return ResourceReceipt(kind="plan",resource_id=plan_id,version=head.state_version)
            def verify(active,actor,receipt):
                self._confirmation_proof(active,actor,plan_id,request,receipt)
                return True
            try:
                receipt=self.idempotency_service.execute(current,"plan.confirm",key,payload,
                    perform=protected(perform),verify_resource=protected(verify),session=same)
            except Exception:
                if failure[0] is not None:
                    raise failure[0]
                raise
            source,head,value=self._read(same,current,plan_id)
            result=ConfirmResult(execution=value,replayed=receipt.replayed,confirmed_state_version=receipt.resource.version)
            self._final(same,current,((source,value),),receipt_expiry=receipt.expires_at,
                first_confirmation=not receipt.replayed)
        return result

    @audited("authorization.owned.execute")
    def complete_task(self, principal, plan_id, task_key, request, *, session=None):
        with self._transaction(session) as same:
            request=self._input(CompleteInput,request)
            current=self._authorize(same,principal)
            source,head,value=self._read(same,current,plan_id)
            tasks={t.task_key:t for t in value.proposal.effective_draft.tasks}
            if type(task_key) is not str or task_key not in tasks:
                raise ExecutionError(404)
            if value.confirmation is None:
                raise ExecutionError(409)
            completed={c.task_key for c in value.completed_tasks}
            if any(key not in completed for key in tasks[task_key].dependency_keys):
                raise ExecutionError(409)
            payload={"plan_id":str(head.plan_id),"task_key":task_key,"request":request.model_dump(mode="json")}
            audit=self._audit(same,current,head.plan_id,head.state_version)
            replayed=self.store.complete(same,head,task_key,canonical_request_hash(payload),expected_version=request.expected_version,
                now=self.auth_service._now(),audit_event_id=audit.id)
            result=CompleteResult(execution=self.store.result(same,head,source),replayed=replayed)
            self._audit(same,current,head.plan_id,head.state_version)
            self._final(same,current,((source,result.execution),))
        return result
