"""Finite wire coherence and lease fencing, without persistence or suppliers."""
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from pydantic import ValidationError
from services.api.app.notifications.schemas import (NotificationData,NotificationPage,NotificationPreferenceData,
    PreferenceInput,MarkReadInput,NotificationContextData,NotificationEnvelope)
from services.api.app.profiles.schemas import ProfileMeta
from services.api.app.jobs.schemas import JobClaim
from services.api.app.jobs.store import JobsStore

NOW=datetime(2026,10,4,tzinfo=timezone.utc)


def message(**changes):
    fields=dict(id=uuid4(),version=1,event_id=uuid4(),assessment_id=uuid4(),profile_id=uuid4(),profile_version_id=uuid4(),
        profile_sha256="a"*64,is_synthetic=True,reason="RELEASE_WITHDRAWN",needs_review=True,dataset_id=uuid4(),
        entry_year=2027,offering_id=uuid4(),offering_version=1,before_release_id=uuid4(),after_release_id=None,
        created_at=NOW,expires_at=NOW+timedelta(days=1),read_at=None)
    return NotificationData.model_validate({**fields,**changes})


def test_absent_preference_and_explicit_disable_are_separate():
    value=NotificationPreferenceData(version=0,enabled=False,profile_id=None,profile_version_id=None,profile_sha256=None,is_synthetic=True,updated_at=None)
    assert value.version==0
    assert PreferenceInput(expected_version=1,enabled=False,profile_id=None,student_confirmed=True).expected_version==1
    with pytest.raises(ValidationError):
        NotificationPreferenceData.model_validate(value.model_copy(update={"updated_at":NOW}))


@pytest.mark.parametrize("patch",[{"version":2},{"read_at":NOW},{"needs_review":False},{"before_release_id":None},{"expires_at":NOW}])
def test_message_coherence_rejects_individually_valid_fields(patch):
    with pytest.raises(ValidationError):
        message(**patch)


def test_read_transition_preserves_frozen_body():
    value=message()
    read=NotificationData.model_validate(value.model_copy(update={"version":2,"read_at":NOW+timedelta(seconds=1)}))
    assert read.event_id==value.event_id and read.reason==value.reason
    assert MarkReadInput(expected_version=1,student_confirmed=True).expected_version==1


def test_page_is_bounded_and_distinct():
    item=message()
    assert NotificationPage(items=(item,),next_cursor=None).items==(item,)
    with pytest.raises(ValidationError):
        NotificationPage(items=(item,item),next_cursor=None)
    with pytest.raises(ValidationError):
        NotificationPage(items=[item]*21,next_cursor=None)


def test_single_message_metadata_binds_actual_profile():
    item=message()
    meta=ProfileMeta(api_version="v2",request_id="a"*32,data_as_of=None,data_mode="verified",model_mode="disabled",
        release_id=None,ruleset_version=None,profile_version_id=item.profile_version_id,profile_mode="synthetic")
    assert NotificationEnvelope(data=item,meta=meta).data.id==item.id
    with pytest.raises(ValidationError):
        NotificationEnvelope(data=item,meta=meta.model_copy(update={"profile_version_id":uuid4()}))


def test_fencing_rejects_old_generation_and_exact_expiry():
    claim=JobClaim(job_id=uuid4(),worker_id=uuid4(),generation=1,lease_token=uuid4(),lease_until=NOW+timedelta(seconds=30))
    row=SimpleNamespace(status="running",worker_id=claim.worker_id,generation=1,lease_token=claim.lease_token,lease_until=claim.lease_until,updated_at=NOW)
    JobsStore.fence(row,claim,NOW)
    from services.api.app.notifications.schemas import NotificationError
    with pytest.raises(NotificationError) as error:
        JobsStore.fence(row,claim,claim.lease_until)
    assert error.value.status_code==409
    row.generation=2
    with pytest.raises(NotificationError):
        JobsStore.fence(row,claim,NOW)
