"""Original-purpose owner reads and explicit preference/read confirmations."""

import base64
from contextlib import contextmanager
import json
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..api.v2.idempotency_canonical import canonical_request_hash
from ..auth.authorization import AuthorizationError
from ..auth.config import AuthFlowError
from ..jobs.models import NotificationPreference, InboxNotification
from ..profiles.service import ProfileService
from ..profiles.models import ProfileRoot,ProfileVersion
from ..auth.models import AuthOwnedResource
from ..profiles.store import database_time
from .schemas import (NotificationPolicy,NotificationError,NotificationContextData,PreferenceInput,MarkReadInput,
    NotificationPage)
from .store import NotificationsStore

PROOF_FIELDS=("admission_id","consent_id","declaration_id","notice_id","policy_version","notice_sha256")


class NotificationService:
    def __init__(self,profile_service,store,policy=NotificationPolicy()):
        try:
            if not isinstance(profile_service,ProfileService) or not isinstance(store,NotificationsStore):
                raise ValueError()
            self.profile_service,self.store=profile_service,store
            self.auth_service=profile_service.auth_service
            self.policy=NotificationPolicy.model_validate(policy)
            self._initial=(profile_service,store,self.auth_service,self.auth_service.clock,self.auth_service.runtime_settings,self.policy)
            self._validate()
        except Exception:
            raise NotificationError() from None

    def _validate(self):
        try:
            profile,store,auth,clock,runtime,policy=self._initial
            current=NotificationPolicy.model_validate(self.policy)
            if (self.profile_service is not profile or self.store is not store or self.auth_service is not auth
                or auth.clock is not clock or auth.runtime_settings!=runtime or current!=policy or profile.store.engine is not store.engine):
                raise ValueError()
            profile._validate()
            return current
        except Exception:
            raise NotificationError() from None

    def _ready(self):
        policy=self._validate()
        if not policy.enabled or not policy.allow_test_notifications or self.auth_service.runtime_settings.app_environment!="test":
            raise NotificationError()

    def _guard_session(self,session):
        self.profile_service._guard_session(session)
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
            status=getattr(error,"status_code",None)
            raise NotificationError(status if status in {404,409,422} else 503) from None

    @staticmethod
    def _input(model,value):
        try:
            return model.model_validate(value)
        except Exception:
            raise NotificationError(422) from None

    def _base(self,session,principal):
        current=self.profile_service._authorize(session,principal)
        if not current.is_synthetic:
            raise NotificationError()
        return current,self.profile_service._proof(session,current)

    def _final(self,session,current,proof,*,versions=(),roots=(),notifications=(),preference=None):
        now=self.profile_service._final(session,current,proof,versions,roots)
        self._ready()
        if preference is not None and database_time(preference.updated_at)>now:
            raise NotificationError(409)
        for item in notifications:
            if not item.created_at<=now<item.expires_at or item.read_at is not None and item.read_at>now:
                raise NotificationError(409)
        return now

    def _audit(self,session,current,object_id=None,version=None):
        return self.auth_service.store.audit.success(session,"authorization.owned.check",actor=current,
            object_type="job" if object_id else None,object_id=object_id,object_version=version,now=self.auth_service._now())

    def preflight(self,principal):
        with self._transaction() as same:
            current,proof=self._base(same,principal)
            self._final(same,current,proof)

    def context(self,principal,*,session=None):
        policy=self._validate()
        if not policy.enabled:
            return NotificationContextData(schema_version="v2.t36",can_read=False,can_manage_preferences=False,
                can_mark_read=False,is_synthetic=principal.is_synthetic,delivery_channel="in_app",external_delivery_enabled=False)
        with self._transaction(session) as same:
            current,proof=self._base(same,principal)
            value=NotificationContextData(schema_version="v2.t36",can_read=True,can_manage_preferences=True,
                can_mark_read=True,is_synthetic=current.is_synthetic,delivery_channel="in_app",external_delivery_enabled=False)
            self._final(same,current,proof)
        return value

    def get_preferences(self,principal,*,session=None):
        with self._transaction(session) as same:
            current,proof=self._base(same,principal)
            row=self.store.preference(same,current.user_id)
            versions,roots=(),()
            if row is not None and row.enabled:
                fields=(ProfileVersion.id,ProfileVersion.profile_id,ProfileVersion.owner_user_id,ProfileVersion.is_synthetic,
                    ProfileVersion.payload_sha256,ProfileVersion.confirmed_at,ProfileVersion.expires_at,
                    *(getattr(ProfileVersion,name) for name in PROOF_FIELDS))
                metadata=same.execute(select(*fields).where(ProfileVersion.id==row.profile_version_id).with_for_update()).one_or_none()
                if (metadata is None or (metadata.profile_id,metadata.owner_user_id,metadata.is_synthetic,metadata.payload_sha256)
                    !=(row.profile_id,current.user_id,current.is_synthetic,row.profile_sha256)
                    or any(getattr(row,name)!=getattr(metadata,name) for name in PROOF_FIELDS)
                    or database_time(metadata.confirmed_at)>self.auth_service._now()):
                    raise NotificationError(409)
                root=same.scalar(select(ProfileRoot).where(ProfileRoot.id==row.profile_id,ProfileRoot.owner_user_id==current.user_id).with_for_update())
                registry=same.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id==row.profile_id,AuthOwnedResource.owner_user_id==current.user_id).with_for_update())
                original=(row.admission_id,row.consent_id,row.declaration_id,row.notice_id,row.policy_version,row.notice_sha256)
                present=(proof.admission.id,proof.admission.consent_id,proof.declaration.id,proof.notice.id,proof.notice.policy_version,proof.notice.text_sha256)
                stale=(original!=present or row.session_id!=current.session_id or root is None or registry is None
                    or registry.status!="active" or root.current_version_id!=row.profile_version_id
                    or self.auth_service._now()>=database_time(metadata.expires_at))
                if stale:
                    result=self.store.preference_data(row,current).model_copy(update={"enabled":False,"profile_id":None,"profile_version_id":None,"profile_sha256":None})
                    result=type(result).model_validate(result)
                else:
                    current,root,version,proof,data=self.profile_service._read(same,current,row.profile_id,version_id=row.profile_version_id)
                    self._preference_binding(row,current,root,version,data)
                    versions,roots=(version,),(root,)
                    result=self.store.preference_data(row,current)
            else:
                result=self.store.preference_data(row,current)
            self._audit(same,current)
            self._final(same,current,proof,versions=versions,roots=roots,preference=row)
        return result

    @staticmethod
    def _preference_binding(row,current,root,version,data,*,require_current=True):
        if (not row.enabled or row.owner_user_id!=current.user_id or row.is_synthetic!=current.is_synthetic
            or row.profile_id!=root.id or row.profile_version_id!=version.id or row.profile_sha256!=data.profile_sha256
            or any(getattr(row,name)!=getattr(version,name) for name in PROOF_FIELDS)
            or require_current and (root.current_version_id!=version.id or row.session_id!=current.session_id)):
            raise NotificationError(409)

    def update_preferences(self,principal,request,*,session=None):
        with self._transaction(session) as same:
            request=self._input(PreferenceInput,request)
            current,proof=self._base(same,principal)
            row=self.store.preference(same,current.user_id)
            if request.expected_version!=(row.version if row else 0):
                raise NotificationError(409)
            if row is None:
                row=NotificationPreference(owner_user_id=current.user_id,version=0,is_synthetic=current.is_synthetic)
            versions,roots=(),()
            if request.enabled:
                current,root,version,proof,data=self.profile_service._read(same,current,request.profile_id)
                row.session_id=current.session_id
                row.profile_id,row.profile_version_id,row.profile_sha256=root.id,version.id,data.profile_sha256
                for name in PROOF_FIELDS:
                    setattr(row,name,getattr(version,name))
                versions,roots=(version,),(root,)
            else:
                for name in ("session_id","profile_id","profile_version_id","profile_sha256",*PROOF_FIELDS):
                    setattr(row,name,None)
            row.enabled=request.enabled
            row.version+=1
            row.updated_at=self.auth_service._now()
            same.add(row)
            same.flush()
            result=self.store.preference_data(row,current)
            self._audit(same,current)
            self._final(same,current,proof,versions=versions,roots=roots,preference=row)
        return result

    def _notification(self,session,current,row):
        data=self.store.data(row)
        current,root,version,proof,profile=self.profile_service._read(session,current,data.profile_id,version_id=data.profile_version_id)
        if row.is_synthetic!=current.is_synthetic or data.profile_sha256!=profile.profile_sha256:
            raise NotificationError(409)
        return current,root,version,proof,data

    def list_notifications(self,principal,*,limit=20,cursor=None,session=None):
        with self._transaction(session) as same:
            if type(limit) is not int or not 1<=limit<=20:
                raise NotificationError(422)
            current,proof=self._base(same,principal)
            last=None
            if cursor is not None:
                try:
                    if type(cursor) is not str or not 1<=len(cursor)<=1024:
                        raise ValueError()
                    raw=json.loads(base64.urlsafe_b64decode(cursor+"="*((-len(cursor))%4)))
                    if type(raw) is not dict or set(raw)!={"owner","limit","last"} or raw["owner"]!=str(current.user_id) or type(raw["limit"]) is not int or raw["limit"]!=limit:
                        raise ValueError()
                    last=UUID(raw["last"])
                    if str(last)!=raw["last"] or last.version!=4:
                        raise ValueError()
                except Exception:
                    raise NotificationError(409) from None
            statement=select(InboxNotification).join(ProfileVersion,ProfileVersion.id==InboxNotification.profile_version_id)
            statement=statement.join(AuthOwnedResource,AuthOwnedResource.id==InboxNotification.profile_id).where(
                InboxNotification.owner_user_id==current.user_id,InboxNotification.expires_at>self.auth_service._now(),
                ProfileVersion.owner_user_id==current.user_id,ProfileVersion.profile_id==InboxNotification.profile_id,
                ProfileVersion.admission_id==proof.admission.id,ProfileVersion.consent_id==proof.admission.consent_id,
                ProfileVersion.declaration_id==proof.declaration.id,ProfileVersion.notice_id==proof.notice.id,
                ProfileVersion.policy_version==proof.notice.policy_version,ProfileVersion.notice_sha256==proof.notice.text_sha256,
                ProfileVersion.expires_at>self.auth_service._now(),AuthOwnedResource.owner_user_id==current.user_id,AuthOwnedResource.status=="active")
            if last:
                statement=statement.where(InboxNotification.id>last)
            rows=same.scalars(statement.order_by(InboxNotification.id).limit(limit+1).with_for_update(of=InboxNotification).execution_options(populate_existing=True)).all()
            items,versions,roots=[],[],[]
            for row in rows[:limit]:
                current,root,version,proof,data=self._notification(same,current,row)
                items.append(data);versions.append(version);roots.append(root)
            next_cursor=base64.urlsafe_b64encode(json.dumps({"owner":str(current.user_id),"limit":limit,"last":str(rows[limit-1].id)},separators=(",",":")).encode()).decode().rstrip("=") if len(rows)>limit else None
            result=NotificationPage(items=tuple(items),next_cursor=next_cursor)
            self._audit(same,current)
            self._final(same,current,proof,versions=versions,roots=roots,notifications=items)
        return result

    def mark_read(self,principal,notification_id,request,*,session=None):
        with self._transaction(session) as same:
            request=self._input(MarkReadInput,request)
            if type(notification_id) is not UUID or notification_id.version!=4:
                raise NotificationError(422)
            current,proof=self._base(same,principal)
            row=self.store.get(same,notification_id,current.user_id)
            current,root,version,proof,data=self._notification(same,current,row)
            request_sha=canonical_request_hash(request.model_dump(mode="json"))
            if row.read_version==2:
                if request.expected_version!=2 and row.read_request_sha256!=request_sha:
                    raise NotificationError(409)
            elif request.expected_version!=row.read_version:
                raise NotificationError(409)
            else:
                row.read_version,row.read_at,row.read_request_sha256=2,self.auth_service._now(),request_sha
                same.flush()
                data=self.store.data(row)
            self._audit(same,current,row.id,row.read_version)
            self._final(same,current,proof,versions=(version,),roots=(root,),notifications=(data,))
        return data
