"""Finite PostgreSQL worker operations and persisted, separately scoped authority."""

from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID,uuid4
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from ..audit.models import AuditEvent
from ..auth.authorization import AuthorizationError
from ..auth.config import AuthFlowError
from ..auth.models import AuthOwnedResource,AuthUser
from ..auth.service import ExecutionReference
from ..assessments.models import EligibilityAssessment
from ..changes.models import AssessmentChangeImpact
from ..changes.service import ChangesService
from ..changes.store import impact_data
from ..notifications.service import NotificationService,PROOF_FIELDS
from ..notifications.schemas import NotificationData,NotificationError
from ..profiles.store import database_time
from ..releases.models import ChangeEvent,OutboxEvent
from ..rules.adapters.schemas import TargetReference
from .models import DurableJob,CleanupPermit,NotificationPreference
from .schemas import JobsPolicy,JobClaim,CleanupScope,CleanupResource,scope_hash
from .store import JobsStore,fingerprint


class JobsService:
    def __init__(self,changes_service,notification_service,store,policy=JobsPolicy()):
        try:
            if (not isinstance(changes_service,ChangesService) or not isinstance(notification_service,NotificationService)
                or not isinstance(store,JobsStore)):
                raise ValueError()
            self.changes_service,self.notification_service,self.store=changes_service,notification_service,store
            self.profile_service=notification_service.profile_service
            self.auth_service=self.profile_service.auth_service
            self.policy=JobsPolicy.model_validate(policy)
            self._initial=(changes_service,notification_service,store,self.profile_service,self.auth_service,
                self.auth_service.clock,self.auth_service.runtime_settings,self.policy)
            self._validate()
        except Exception:
            raise NotificationError() from None

    def _validate(self):
        try:
            changes,notifications,store,profiles,auth,clock,runtime,policy=self._initial
            current=JobsPolicy.model_validate(self.policy)
            if (self.changes_service is not changes or self.notification_service is not notifications or self.store is not store
                or self.profile_service is not profiles or self.auth_service is not auth or auth.clock is not clock
                or auth.runtime_settings!=runtime or current!=policy or changes.auth_service is not auth
                or changes.profile_service is not profiles or notifications.store.engine is not store.engine
                or changes.store.engine is not store.engine):
                raise ValueError()
            changes._validate();notifications._validate()
            return current
        except Exception:
            raise NotificationError() from None

    def _ready(self):
        policy=self._validate()
        if not policy.enabled or not policy.allow_test_jobs or self.auth_service.runtime_settings.app_environment!="test":
            raise NotificationError()

    def _guard_session(self,session):
        self.changes_service._guard_session(session)
        self.notification_service._guard_session(session)
        with self.store._work(session):
            pass

    @contextmanager
    def _transaction(self,supplied=None):
        try:
            self._ready()
            if supplied is None:
                self.store.assert_schema_ready()
                with Session(self.store.engine) as same,same.begin():
                    self._guard_session(same)
                    yield same
            else:
                self._guard_session(supplied)
                yield supplied
        except Exception as error:
            self.profile_service._abort(supplied)
            if isinstance(error,(NotificationError,AuthFlowError,AuthorizationError)):
                raise
            raise NotificationError() from None

    @staticmethod
    def _uuid(value):
        if type(value) is not UUID or value.version!=4:
            raise NotificationError(422)
        return value

    def _audit(self,session,row=None,current=None,*,action="authorization.owned.execute",object_id=None,version=None,now=None):
        return self.auth_service.store.audit.success(session,action,actor=current,actor_kind="system" if current is None else None,
            object_type="deletion_job" if action=="deletion.accept" else "job",
            object_id=object_id if object_id else row.id if row else None,
            object_version=version if version else row.generation if row and row.generation else None,
            now=now if now else self.auth_service._now())

    def enqueue_outbox(self,*,limit=100,session=None):
        with self._transaction(session) as same:
            if type(limit) is not int or not 1<=limit<=100:
                raise NotificationError(422)
            rows=same.execute(select(OutboxEvent,ChangeEvent).join(ChangeEvent,ChangeEvent.id==OutboxEvent.event_id)
                .where(~select(DurableJob.id).where(DurableJob.kind=="release_impact",DurableJob.outbox_id==OutboxEvent.id).exists())
                .order_by(OutboxEvent.created_at,OutboxEvent.id).limit(limit).with_for_update(of=OutboxEvent,skip_locked=True)).all()
            result=[]
            for outbox,event in rows:
                if outbox.status!="pending" or not event.is_synthetic or database_time(outbox.created_at)!=database_time(event.created_at):
                    raise NotificationError(409)
                now=self.auth_service._now()
                if database_time(event.created_at)>now:
                    raise NotificationError(409)
                row=self.store.put_job(same,kind="release_impact",natural={"kind":"release_impact","event":str(event.id),"outbox":str(outbox.id)},
                    payload={"last_assessment_id":None},now=now,expires_at=now+timedelta(seconds=self.policy.job_ttl_seconds),
                    is_synthetic=event.is_synthetic,event_id=event.id,outbox_id=outbox.id)
                result.append(row.id)
            if result:
                self._audit(same)
            now=self.auth_service._now()
            self._ready()
            if any(not database_time(row.created_at)<=now<database_time(row.expires_at) for row in same.identity_map.values() if isinstance(row,DurableJob)):
                raise NotificationError(409)
        return tuple(result)

    def claim(self,worker_id,*,session=None):
        with self._transaction(session) as same:
            self._uuid(worker_id)
            # A bounded terminal sweep prevents an expired head being mistaken
            # for an empty queue while still respecting SKIP LOCKED workers.
            claim=None
            for _ in range(100):
                claim=self.store.claim(same,worker_id,now=self.auth_service._now(),policy=self.policy)
                if claim is not None:
                    break
                remaining=same.scalar(select(DurableJob.id).where(
                    ((DurableJob.status=="queued") & (DurableJob.available_at<=self.auth_service._now()))
                    | ((DurableJob.status=="running") & ((DurableJob.lease_until<=self.auth_service._now())
                        | (DurableJob.expires_at<=self.auth_service._now()))))
                    .limit(1).with_for_update(skip_locked=True))
                if remaining is None:
                    break
            if claim is not None:
                row=self.store.get_job(same,claim.job_id)
                self._audit(same,row)
            now=self.auth_service._now()
            self._ready()
            if claim is not None and now>=claim.lease_until:
                raise NotificationError(409)
        return claim

    @staticmethod
    def _preference_payload(preference):
        return {name:str(value) if type(value) is UUID else value for name in
            ("session_id","profile_id","profile_version_id","profile_sha256",*PROOF_FIELDS)
            for value in (getattr(preference,name),)}

    def _fanout(self,session,row):
        if set(row.payload)!={"last_assessment_id"}:
            raise NotificationError(409)
        last=row.payload["last_assessment_id"]
        if last is not None:
            try:
                parsed=UUID(last)
                if str(parsed)!=last or parsed.version!=4:
                    raise ValueError()
            except Exception:
                raise NotificationError(409) from None
        self.changes_service.process_event(row.event_id,session=session)
        self.notification_service._validate()
        if not self.notification_service.policy.enabled:
            return False
        statement=select(AssessmentChangeImpact,NotificationPreference,
            EligibilityAssessment.profile_id,EligibilityAssessment.profile_version_id,
            EligibilityAssessment.profile_is_synthetic).join(EligibilityAssessment,EligibilityAssessment.id==AssessmentChangeImpact.assessment_id)
        statement=statement.join(NotificationPreference,NotificationPreference.owner_user_id==AssessmentChangeImpact.owner_user_id).where(
            AssessmentChangeImpact.event_id==row.event_id,NotificationPreference.enabled.is_(True),
            NotificationPreference.profile_id==EligibilityAssessment.profile_id,
            NotificationPreference.profile_version_id==EligibilityAssessment.profile_version_id,
            NotificationPreference.is_synthetic==EligibilityAssessment.profile_is_synthetic)
        if last is not None:
            statement=statement.where(AssessmentChangeImpact.assessment_id>UUID(last))
        rows=session.execute(statement.order_by(AssessmentChangeImpact.assessment_id).limit(101)).all()
        now=self.auth_service._now()
        for impact,pref,profile_id,version_id,mode in rows[:100]:
            if not mode or impact.is_synthetic!=mode or pref.is_synthetic!=mode:
                raise NotificationError(409)
            payload=self._preference_payload(pref)
            self.store.put_job(session,kind="notification",natural={"kind":"notification","event":str(row.event_id),
                "owner":str(pref.owner_user_id),"assessment":str(impact.assessment_id),"preference":pref.version,
                "profile_version":str(version_id),"consent":str(pref.consent_id)},payload=payload,now=now,
                expires_at=now+timedelta(seconds=self.policy.job_ttl_seconds),is_synthetic=mode,
                owner=pref.owner_user_id,event_id=row.event_id,assessment_id=impact.assessment_id,preference_version=pref.version)
        if len(rows)>100:
            row.payload={"last_assessment_id":str(rows[99][0].assessment_id)}
            row.payload_sha256=fingerprint(row.payload)
            return True
        return False

    def _user(self,session,hint):
        try:
            reference=ExecutionReference(user_id=hint.owner_user_id,session_id=UUID(hint.payload["session_id"]))
        except Exception:
            raise NotificationError(409) from None
        current,_=self.auth_service.store.locked_principal(session,reference,clock=self.auth_service._now,production=False)
        current,proof=self.notification_service._base(session,current)
        preference=self.notification_service.store.preference(session,current.user_id)
        if (preference is None or not preference.enabled or preference.version!=hint.preference_version
            or self._preference_payload(preference)!=hint.payload):
            raise AuthorizationError(403)
        current,root,version,proof,data=self.profile_service._read(session,current,preference.profile_id,version_id=preference.profile_version_id)
        if root.current_version_id!=version.id:
            raise AuthorizationError(403)
        self.notification_service._preference_binding(preference,current,root,version,data)
        return current,proof,root,version,preference

    def _emit(self,session,row,current,profile):
        impact=session.scalar(select(AssessmentChangeImpact).where(AssessmentChangeImpact.event_id==row.event_id,
            AssessmentChangeImpact.assessment_id==row.assessment_id,AssessmentChangeImpact.owner_user_id==current.user_id))
        if impact is None or impact.is_synthetic!=current.is_synthetic:
            raise NotificationError(409)
        change=impact_data(impact)
        metadata=session.execute(select(EligibilityAssessment.profile_id,EligibilityAssessment.profile_version_id,
            EligibilityAssessment.profile_is_synthetic,EligibilityAssessment.dataset_id,EligibilityAssessment.entry_year,
            EligibilityAssessment.assessment_at,EligibilityAssessment.expires_at,
            EligibilityAssessment.payload["target"].label("target")).where(EligibilityAssessment.id==row.assessment_id,
                EligibilityAssessment.owner_user_id==current.user_id).with_for_update()).one_or_none()
        if metadata is None:
            raise NotificationError(409)
        target=TargetReference.model_validate(metadata.target)
        if (metadata.profile_id,metadata.profile_version_id,metadata.profile_is_synthetic,metadata.entry_year,target.offering_id)!= (
            profile.profile_id,profile.id,current.is_synthetic,change.entry_year,change.offering_id):
            raise NotificationError(409)
        now=self.auth_service._now()
        if not database_time(metadata.assessment_at)<=now<database_time(metadata.expires_at):
            raise AuthorizationError(403)
        reason=next((reason for reason in change.reasons if reason!="REFERENCE_REPLACED"),"REFERENCE_REPLACED")
        data=NotificationData(id=uuid4(),version=1,event_id=row.event_id,assessment_id=row.assessment_id,
            profile_id=profile.profile_id,profile_version_id=profile.id,profile_sha256=profile.payload_sha256,
            is_synthetic=current.is_synthetic,reason=reason,needs_review=change.needs_review,dataset_id=metadata.dataset_id,
            entry_year=change.entry_year,offering_id=target.offering_id,offering_version=target.offering_version,
            before_release_id=change.before_release_id,after_release_id=change.after_release_id,
            created_at=now,expires_at=min(database_time(profile.expires_at),database_time(metadata.expires_at)),read_at=None)
        saved=self.notification_service.store.put(session,current,data,row)
        return saved,metadata

    def _final(self,session,row,claim,*,authority=None,notifications=(),metadata=None,permit=None):
        # Every INSERT/UPDATE/audit/ack has already flushed before this boundary.
        if authority is not None:
            current,proof,root,version,preference=authority
            now=self.notification_service._final(session,current,proof,versions=(version,),roots=(root,),
                notifications=notifications,preference=preference)
        else:
            now=self.auth_service._now()
        self._ready()
        if (row.generation!=claim.generation or not database_time(row.created_at)<=now<database_time(row.expires_at)
            or now>=claim.lease_until or database_time(row.updated_at)>now):
            raise NotificationError(409)
        if metadata is not None and not database_time(metadata.assessment_at)<=now<database_time(metadata.expires_at):
            raise NotificationError(409)
        if permit is not None and not database_time(permit.accepted_at)<=now<database_time(permit.expires_at):
            raise NotificationError(409)
        return now

    def run_claim(self,claim,*,session=None):
        try:
            with self._transaction(session) as same:
                try:
                    claim=JobClaim.model_validate(claim)
                except Exception:
                    raise NotificationError(422) from None
                hint=self.store.get_job(same,claim.job_id,lock=False)
                authority=None
                if hint.kind in {"notification","export","model"}:
                    authority=self._user(same,hint)
                elif hint.kind=="cleanup_probe":
                    owner=same.scalar(select(AuthUser).where(AuthUser.id==hint.owner_user_id).with_for_update().execution_options(populate_existing=True))
                    if owner is None or owner.is_synthetic!=hint.is_synthetic:
                        raise NotificationError(409)
                row=self.store.get_job(same,claim.job_id)
                self.store.fence(row,claim,self.auth_service._now())
                metadata=permit=None
                notifications=()
                status,reason="completed","OK"
                if row.kind=="release_impact":
                    if self._fanout(same,row):
                        status="queued"
                elif row.kind=="notification":
                    saved,metadata=self._emit(same,row,authority[0],authority[3])
                    notifications=(saved,)
                elif row.kind=="cleanup_probe":
                    permit=self._cleanup(same,row)
                else:
                    status,reason="failed","HANDLER_UNAVAILABLE"
                audit=self._audit(same,row,current=authority[0] if authority else None)
                result=self.store.finish(same,row,claim,status=status,reason=reason,now=self.auth_service._now(),audit_event_id=audit.id,retry_seconds=1)
                self._final(same,row,claim,authority=authority,notifications=notifications,metadata=metadata,permit=permit)
            return result
        except (AuthFlowError,AuthorizationError) as error:
            if session is not None:
                raise
            return self._terminal(claim,"cancelled","AUTHORITY_REVOKED")

    def _terminal(self,claim,status,reason):
        with self._transaction() as same:
            row=self.store.get_job(same,claim.job_id)
            self.store.fence(row,claim,self.auth_service._now())
            audit=self._audit(same,row)
            result=self.store.finish(same,row,claim,status=status,reason=reason,now=self.auth_service._now(),audit_event_id=audit.id)
            self._final(same,row,claim)
        return result

    def retry_claim(self,claim,*,session=None):
        with self._transaction(session) as same:
            try:
                claim=JobClaim.model_validate(claim)
            except Exception:
                raise NotificationError(422) from None
            row=self.store.get_job(same,claim.job_id)
            self.store.fence(row,claim,self.auth_service._now())
            status,reason=("failed","ATTEMPTS_EXHAUSTED") if row.attempts>=self.policy.max_attempts else ("queued","RETRYABLE_FAILURE")
            audit=self._audit(same,row)
            result=self.store.finish(same,row,claim,status=status,reason=reason,now=self.auth_service._now(),audit_event_id=audit.id,
                retry_seconds=min(60,self.policy.retry_seconds*(2**(row.attempts-1))))
            self._final(same,row,claim)
        return result

    def accept_cleanup_probe(self,principal,resource_ids,*,watermark,purpose="deletion_cleanup",session=None):
        """Trusted internal acceptance only; no deletion API or physical cleanup."""
        with self._transaction(session) as same:
            if not self.policy.allow_cleanup_probe:
                raise NotificationError()
            if type(resource_ids) not in {tuple,list} or not 1<=len(resource_ids)<=100 or type(watermark) is not int or not 1<=watermark<=2147483647:
                raise NotificationError(422)
            ids=tuple(sorted((self._uuid(value) for value in resource_ids),key=str))
            if len(set(ids))!=len(ids):
                raise NotificationError(422)
            current,proof=self.notification_service._base(same,principal)
            records=same.scalars(select(AuthOwnedResource).where(AuthOwnedResource.id.in_(ids),AuthOwnedResource.owner_user_id==current.user_id)
                .order_by(AuthOwnedResource.id).with_for_update().execution_options(populate_existing=True)).all()
            if len(records)!=len(ids) or any(row.is_synthetic!=current.is_synthetic for row in records):
                raise AuthorizationError(403)
            scope=CleanupScope(owner_user_id=current.user_id,is_synthetic=current.is_synthetic,
                resources=tuple(CleanupResource(resource_id=row.id,resource_type=row.resource_type,version=row.version,status=row.status,is_synthetic=row.is_synthetic) for row in records),
                watermark=watermark,purpose=purpose)
            latest=same.scalar(select(func.max(CleanupPermit.watermark)).where(CleanupPermit.owner_user_id==current.user_id))
            if latest is not None and watermark<latest:
                raise NotificationError(409)
            sha=scope_hash(scope)
            permit=same.scalar(select(CleanupPermit).where(CleanupPermit.owner_user_id==current.user_id,CleanupPermit.watermark==watermark,CleanupPermit.scope_sha256==sha).with_for_update())
            if permit is None:
                now=self.auth_service._now();permit_id=uuid4()
                audit=self._audit(same,current=current,action="deletion.accept",object_id=permit_id,version=watermark,now=now)
                permit=CleanupPermit(id=permit_id,owner_user_id=current.user_id,is_synthetic=current.is_synthetic,purpose=purpose,watermark=watermark,
                    scope=scope.model_dump(mode="json"),scope_sha256=sha,accepted_at=now,expires_at=now+timedelta(days=30),audit_event_id=audit.id)
                same.add(permit);same.flush()
            now=self.auth_service._now()
            job=self.store.put_job(same,kind="cleanup_probe",natural={"kind":"cleanup_probe","permit":str(permit.id),"scope":sha},
                payload={"scope_sha256":sha,"watermark":watermark},now=now,expires_at=now+timedelta(seconds=self.policy.job_ttl_seconds),
                is_synthetic=current.is_synthetic,owner=current.user_id,permit_id=permit.id)
            now=self.profile_service._final(same,current,proof)
            self._ready()
            if not database_time(permit.accepted_at)<=now<database_time(permit.expires_at) or not database_time(job.created_at)<=now<database_time(job.expires_at):
                raise NotificationError(409)
            result=job.id
        return result

    def _cleanup(self,session,row):
        if not self.policy.allow_cleanup_probe:
            raise NotificationError()
        permit,scope=self.store.get_permit(session,row.permit_id)
        if (permit.owner_user_id,permit.is_synthetic)!=(row.owner_user_id,row.is_synthetic) or not permit.is_synthetic:
            raise NotificationError(409)
        if row.payload!={"scope_sha256":permit.scope_sha256,"watermark":permit.watermark}:
            raise NotificationError(409)
        accepted=session.scalar(select(AuditEvent).where(AuditEvent.id==permit.audit_event_id).with_for_update())
        if (accepted is None or accepted.action!="deletion.accept" or accepted.outcome!="succeeded" or accepted.reason_code!="OK"
            or accepted.actor_kind!="user" or accepted.actor_user_id!=permit.owner_user_id or accepted.object_type!="deletion_job"
            or accepted.object_id!=permit.id or accepted.object_version!=permit.watermark or accepted.is_synthetic!=permit.is_synthetic
            or database_time(accepted.occurred_at)!=database_time(permit.accepted_at)):
            raise NotificationError(409)
        latest=session.scalar(select(func.max(CleanupPermit.watermark)).where(CleanupPermit.owner_user_id==permit.owner_user_id))
        if latest!=permit.watermark:
            raise NotificationError(409)
        resources=session.scalars(select(AuthOwnedResource).where(AuthOwnedResource.id.in_([item.resource_id for item in scope.resources]))
            .order_by(AuthOwnedResource.id).with_for_update().execution_options(populate_existing=True)).all()
        if len(resources)!=len(scope.resources):
            raise NotificationError(409)
        for resource,expected in zip(resources,scope.resources):
            if (resource.id,resource.owner_user_id,resource.resource_type,resource.version,resource.status,resource.is_synthetic)!=(
                expected.resource_id,permit.owner_user_id,expected.resource_type,expected.version,expected.status,expected.is_synthetic):
                raise NotificationError(409)
        return permit
