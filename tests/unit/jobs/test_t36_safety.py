"""Independent closed-authority and lease input checks; no real student data."""

from datetime import datetime, timedelta, timezone, tzinfo
from hashlib import sha256
import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from services.api.app.jobs.schemas import (
    CleanupResource, CleanupScope, JobClaim, JobsPolicy, scope_hash,
)
from services.api.app.notifications.schemas import (
    MarkReadInput, NotificationContextData, NotificationData, NotificationPage,
    NotificationPolicy, PreferenceInput,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def scope():
    return CleanupScope(owner_user_id=UUID(int=1), is_synthetic=True,
        resources=(CleanupResource(resource_id=UUID(int=2), resource_type="profile",
            version=1, status="active", is_synthetic=True),),
        watermark=1, purpose="deletion_cleanup")


def claim():
    return JobClaim(job_id=UUID(int=3), worker_id=UUID(int=4), generation=1,
        lease_token=UUID(int=5), lease_until=NOW + timedelta(seconds=30))


def notification():
    return NotificationData(id=UUID(int=6), version=1, event_id=UUID(int=7),
        assessment_id=UUID(int=8), profile_id=UUID(int=2), profile_version_id=UUID(int=9),
        profile_sha256="a" * 64, is_synthetic=True, reason="RELEASE_WITHDRAWN",
        needs_review=True, dataset_id=UUID(int=10), entry_year=2027,
        offering_id=UUID(int=11), offering_version=1, before_release_id=UUID(int=12),
        after_release_id=None, created_at=NOW, expires_at=NOW + timedelta(days=1), read_at=None)


def test_cleanup_hash_is_exact_canonical_json_not_a_model_or_repr():
    original = scope()
    expected = sha256(json.dumps(original.model_dump(mode="json"), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    assert scope_hash(original) == expected
    assert scope_hash(original.model_dump(mode="json")) == expected
    assert original.model_dump() == scope().model_dump()


@pytest.mark.parametrize("changed", ["owner", "mode", "resource", "version", "status", "watermark", "purpose"])
def test_cleanup_hash_binds_every_authority_dimension(changed):
    original = scope()
    data = original.model_dump()
    if changed == "owner":
        data["owner_user_id"] = UUID(int=13)
    elif changed == "mode":
        data["is_synthetic"] = False
        data["resources"] = (data["resources"][0] | {"is_synthetic": False},)
    elif changed == "resource":
        data["resources"] = (data["resources"][0] | {"resource_id": UUID(int=14)},)
    elif changed == "version":
        data["resources"] = (data["resources"][0] | {"version": 2},)
    elif changed == "status":
        data["resources"] = (data["resources"][0] | {"status": "deleted"},)
    elif changed == "watermark":
        data["watermark"] = 2
    else:
        data["purpose"] = "retention_cleanup"
    assert scope_hash(data) != scope_hash(original)


def test_cleanup_scope_does_not_accept_duplicate_unsorted_or_mixed_mode_resources():
    first = scope().resources[0]
    second = first.model_copy(update={"resource_id": UUID(int=20)})
    for resources in ((first, first), (second, first),
            (first.model_copy(update={"is_synthetic": False}),)):
        with pytest.raises(ValidationError):
            CleanupScope.model_validate(scope().model_copy(update={"resources": resources}))


def test_cleanup_resource_budget_is_checked_before_visiting_untrusted_children():
    class Trap:
        def __getattribute__(self, name):
            pytest.fail("Oversized cleanup resources must not be inspected")

    with pytest.raises(ValidationError):
        CleanupScope.model_validate(scope().model_copy(update={"resources": [Trap()] * 101}))
    calls = []

    class CustomList(list):
        def __iter__(self):
            calls.append("iterated")
            return super().__iter__()

    with pytest.raises(ValidationError):
        CleanupScope.model_validate(scope().model_copy(update={"resources": CustomList([scope().resources[0]])}))
    assert calls == []


@pytest.mark.parametrize("field,value", [
    ("watermark", 0), ("watermark", True), ("purpose", "delete_all_users"),
    ("is_synthetic", 1), ("owner_user_id", "not-a-server-uuid"),
])
def test_constructed_cleanup_scope_is_revalidated_before_hashing(field, value):
    forged = CleanupScope.model_construct(**(scope().model_dump() | {field: value}))
    with pytest.raises(ValidationError):
        scope_hash(forged)


@pytest.mark.parametrize("field,value", [
    ("generation", 0), ("generation", True), ("worker_id", None),
    ("lease_until", NOW.replace(tzinfo=None)), ("lease_until", 1791115200),
])
def test_claim_copied_or_constructed_fields_cannot_skip_validation(field, value):
    for forged in (claim().model_copy(update={field: value}),
            JobClaim.model_construct(**(claim().model_dump() | {field: value}))):
        with pytest.raises(ValidationError):
            JobClaim.model_validate(forged)


def test_claim_rejects_custom_timezone_before_running_its_code():
    calls = []

    class HostileTimezone(tzinfo):
        def utcoffset(self, value):
            calls.append("offset")
            return timedelta(0)
        def dst(self, value):
            calls.append("dst")
            return timedelta(0)

    raw = datetime(2026, 10, 4, 12, tzinfo=HostileTimezone())
    with pytest.raises(ValidationError):
        JobClaim.model_validate(claim().model_copy(update={"lease_until": raw}))
    assert calls == []


@pytest.mark.parametrize("model,field", [
    (JobsPolicy, "real_jobs_ready"), (NotificationPolicy, "real_notifications_ready"),
])
def test_real_processing_cannot_be_enabled_by_false_equivalents(model, field):
    assert getattr(model(), field) is False
    for value in (0, True, "false", None):
        with pytest.raises(ValidationError):
            model.model_validate(model().model_copy(update={field: value}))


def test_preference_is_explicit_and_has_no_client_authority_fields():
    good = {"expected_version": 0, "enabled": True, "profile_id": UUID(int=2), "student_confirmed": True}
    assert PreferenceInput(**good).enabled is True
    assert PreferenceInput(expected_version=1, enabled=False, profile_id=None, student_confirmed=True).profile_id is None
    for bad in (good | {"profile_id": None}, good | {"enabled": False},
            good | {"student_confirmed": 1}, good | {"owner_user_id": UUID(int=1)},
            good | {"session_id": UUID(int=4)}, good | {"system_authorized": True}):
        with pytest.raises(ValidationError):
            PreferenceInput.model_validate(bad)
    with pytest.raises(ValidationError):
        MarkReadInput(expected_version=1, student_confirmed=1)


def test_inbox_read_does_not_change_content_or_cross_the_original_ttl():
    original = notification()
    read = NotificationData.model_validate(original.model_copy(update={"version": 2, "read_at": NOW}))
    assert read.reason == original.reason and read.event_id == original.event_id
    for update in ({"read_at": original.expires_at, "version": 2},
            {"read_at": NOW - timedelta(microseconds=1), "version": 2},
            {"needs_review": False}, {"reason": "STUDENT_ADMITTED"},
            {"quote": "DEMO_PRIVATE_ORIGINAL_TEXT"}):
        with pytest.raises(ValidationError):
            NotificationData.model_validate(original.model_dump() | update)
    with pytest.raises(ValidationError):
        NotificationPage(items=(original, original), next_cursor=None)


def test_no_external_delivery_can_be_forged_in_public_context():
    raw = dict(schema_version="v2.t36", can_read=True, can_manage_preferences=True,
        can_mark_read=True, is_synthetic=True, delivery_channel="in_app", external_delivery_enabled=False)
    for update in ({"external_delivery_enabled": 0}, {"external_delivery_enabled": True},
            {"delivery_channel": "email"}):
        with pytest.raises(ValidationError):
            NotificationContextData.model_validate(raw | update)
