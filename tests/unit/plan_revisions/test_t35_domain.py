"""Local T35 projections preserve unknown dates and exact profile metadata."""

from datetime import date,time
from uuid import uuid4

import pytest

from services.api.app.admissions_catalog.date_schemas import DateEventData, DateEventInput
from services.api.app.admissions_catalog.dates import normalize_date_event
from services.api.app.plan_revisions.schemas import DeadlineReference, RevisionEnvelope
from services.api.app.profiles.schemas import ProfileMeta
from tests.unit.plan_revisions.test_t35_safety import history


def test_actual_unknown_date_precision_is_retained_without_a_fabricated_instant():
    value=DateEventInput(id=uuid4(),dataset_id=uuid4(),offering_id=uuid4(),offering_version=1,
        entry_year=2027,event_type="application_deadline",original_text="DEMO: deadline not specified",
        local_date=None,local_time=None,timezone=None,precision="unknown",source_alignment="pending",
        evidence_reference=None,reference_key="DEMO_T35_UNKNOWN_DEADLINE",is_synthetic=True)
    event=DateEventData(**value.model_dump(),**normalize_date_event(value).model_dump(),
        utc_instant=None,review_state="draft",evidence_state="unresolved")
    reference=DeadlineReference(deadline_key="1"*64,assessment_id=uuid4(),assessment_key="math",
        purpose="application",status="unknown",event_id=event.id,precision=event.precision,
        local_date=event.local_date,local_time=event.local_time,timezone=event.timezone,
        reference_calendar=None,official_utc_instant=None)
    assert reference.precision=="unknown"
    assert reference.model_dump(mode="json")["precision"]=="unknown"
    assert reference.local_date is reference.local_time is reference.official_utc_instant is None
    for field,bad in (("local_date",date(2027,1,1)),("local_time",time(12)),("timezone","UTC")):
        with pytest.raises(ValueError):
            DeadlineReference.model_validate(reference.model_copy(update={field:bad}))


def test_history_envelope_binds_the_original_profile_version_even_after_selection_changes():
    retained=history()
    meta=ProfileMeta(api_version="v2",request_id="a"*32,data_as_of=None,
        profile_version_id=retained.pin.profile_version_id,release_id=None,ruleset_version=None,
        profile_mode="synthetic",data_mode="verified",model_mode="disabled")
    assert RevisionEnvelope(data=retained,meta=meta).meta.profile_version_id==retained.pin.profile_version_id
    with pytest.raises(ValueError):
        RevisionEnvelope(data=retained,meta=meta.model_copy(update={"profile_version_id":uuid4()}))
