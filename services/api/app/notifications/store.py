"""Owner-filtered notification metadata, with immutable content and read CAS."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from ..jobs.store import JobsStore, bounded, fingerprint
from ..jobs.models import NotificationPreference, InboxNotification
from ..profiles.store import database_time
from .schemas import NotificationError, NotificationData, NotificationPreferenceData


class NotificationsStore(JobsStore):
    def preference(self,session,owner):
        with self._work(session):
            return session.scalar(select(NotificationPreference).where(NotificationPreference.owner_user_id==owner)
                .with_for_update().execution_options(populate_existing=True))

    @staticmethod
    def preference_data(row,current):
        return NotificationPreferenceData(version=row.version if row else 0,enabled=row.enabled if row else False,
            profile_id=row.profile_id if row else None,profile_version_id=row.profile_version_id if row else None,
            profile_sha256=row.profile_sha256 if row else None,is_synthetic=current.is_synthetic,
            updated_at=database_time(row.updated_at) if row else None)

    def put(self,session,current,data,job):
        with self._work(session):
            data=NotificationData.model_validate(data)
            payload=bounded(data.model_dump(mode="json"))
            session.execute(insert(InboxNotification).values(id=data.id,job_id=job.id,owner_user_id=current.user_id,
                is_synthetic=current.is_synthetic,event_id=data.event_id,assessment_id=data.assessment_id,
                profile_id=data.profile_id,profile_version_id=data.profile_version_id,profile_sha256=data.profile_sha256,
                payload=payload,payload_sha256=fingerprint(payload),created_at=data.created_at,expires_at=data.expires_at,
                read_version=1,read_at=None,read_request_sha256=None).on_conflict_do_nothing(index_elements=[InboxNotification.event_id,InboxNotification.owner_user_id,InboxNotification.assessment_id]))
            row=session.scalar(select(InboxNotification).where(InboxNotification.event_id==data.event_id,
                InboxNotification.owner_user_id==current.user_id,InboxNotification.assessment_id==data.assessment_id)
                .with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise NotificationError()
            return self.data(row)

    def get(self,session,notification_id,owner):
        with self._work(session):
            row=session.scalar(select(InboxNotification).where(InboxNotification.id==notification_id,InboxNotification.owner_user_id==owner)
                .with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise NotificationError(404)
            return row

    @staticmethod
    def data(row):
        if fingerprint(bounded(row.payload))!=row.payload_sha256:
            raise NotificationError(409)
        raw=dict(row.payload)
        for field in ("created_at","expires_at"):
            raw[field]=datetime.fromisoformat(raw[field])
        if raw["read_at"] is not None or raw["version"]!=1:
            raise NotificationError(409)
        raw.update(read_at=database_time(row.read_at) if row.read_at else None,version=row.read_version)
        data=NotificationData.model_validate(raw)
        if (data.id,data.event_id,data.assessment_id,data.profile_id,data.profile_version_id,data.profile_sha256,data.is_synthetic,data.created_at,data.expires_at)!=(
            row.id,row.event_id,row.assessment_id,row.profile_id,row.profile_version_id,row.profile_sha256,row.is_synthetic,database_time(row.created_at),database_time(row.expires_at)):
            raise NotificationError(409)
        return data
