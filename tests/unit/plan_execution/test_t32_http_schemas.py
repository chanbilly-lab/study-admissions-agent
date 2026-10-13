"""Wire adaptation stays local and preserves exact pure scheduler inputs."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.app.plan_execution.http_schemas import HttpWorkspaceInput, wire_utc
from services.api.app.plan_execution.schemas import WorkspaceInput


def body():
    return {"expected_version": 1, "estimate_overrides": [], "schedule": {
        "horizon_start": "2026-10-04T01:00:00.000001Z",
        "horizon_end": "2026-10-04T03:00:00+00:00", "display_timezone": "Asia/Hong_Kong",
        "weekly_hours": "2.000001", "slots": [{"slot_id": str(uuid4()),
            "start_at": "2026-10-04T01:00:00.000001Z", "end_at": "2026-10-04T02:00:00.000001Z"}],
        "internal_goals": [{"task_key": "a" * 64, "due_at": "2026-10-04T02:30:00Z"}],
        "availability_confirmed": True, "rest_excluded": True}}


def test_explicit_wire_utc_becomes_native_without_relaxing_pure_contract():
    raw = body()
    before = deepcopy(raw)
    http = HttpWorkspaceInput.model_validate(raw)
    domain = http.to_domain()
    assert type(domain) is WorkspaceInput
    assert domain.schedule.horizon_start == datetime(2026, 10, 4, 1, 0, 0, 1, timezone.utc)
    assert domain.schedule.slots[0].start_at.microsecond == 1
    assert domain.schedule.internal_goals[0].due_at.tzinfo is timezone.utc
    assert domain.schedule.weekly_hours == "2.000001"
    assert raw == before
    with pytest.raises(ValidationError):
        WorkspaceInput.model_validate(raw)


@pytest.mark.parametrize("value", ["2026-10-04", "2026-10-04T01:00Z", "2026-10-04T01:00:00",
    "2026-10-04T01:00:00+08:00", "2026-10-04T01:00:00-00:00", "2026-10-04t01:00:00z",
    "2026-10-04T01:00:00.0000001Z", "2026-02-30T01:00:00Z", "2026-10-04T01:00:60Z",
    "2026-10-04T01:00:00Z\n", 1791075600, True, None])
def test_wire_time_rejects_ambiguous_or_coercible_inputs(value):
    with pytest.raises(ValueError):
        wire_utc(value)


@pytest.mark.parametrize("field", ["horizon_start", "slot", "goal"])
def test_every_nested_time_uses_the_same_explicit_wire_guard(field):
    raw = body()
    if field == "slot":
        raw["schedule"]["slots"][0]["start_at"] = "2026-10-04T01:00:00+08:00"
    elif field == "goal":
        raw["schedule"]["internal_goals"][0]["due_at"] = "2026-10-04T02:30:00"
    else:
        raw["schedule"][field] = "2026-10-04T01:00:00+08:00"
    with pytest.raises(ValidationError):
        HttpWorkspaceInput.model_validate(raw)


def test_schedule_null_clears_proposal_without_fabricating_availability():
    raw = {"expected_version": 2, "estimate_overrides": [], "schedule": None}
    assert HttpWorkspaceInput.model_validate(raw).to_domain().schedule is None
    del raw["schedule"]
    with pytest.raises(ValidationError):
        HttpWorkspaceInput.model_validate(raw)


@pytest.mark.parametrize("mutation", ["owner", "float", "bool", "duplicate", "confirmation"])
def test_workspace_closes_sensitive_keys_and_exact_inputs(mutation):
    raw = body()
    if mutation == "owner":
        raw["owner_user_id"] = str(uuid4())
    elif mutation == "float":
        raw["schedule"]["weekly_hours"] = 2.0
    elif mutation == "bool":
        raw["expected_version"] = True
    elif mutation == "duplicate":
        raw["estimate_overrides"] = [{"task_key": "a" * 64, "estimated_hours": "0"}] * 2
    else:
        raw["schedule"]["availability_confirmed"] = 1
    with pytest.raises(ValidationError):
        HttpWorkspaceInput.model_validate(raw)


def test_copy_or_construct_cannot_bypass_domain_confirmation_and_capacity():
    original = HttpWorkspaceInput.model_validate(body())
    for forged in (original.model_copy(update={"expected_version": True}),
                   HttpWorkspaceInput.model_construct(**(original.model_dump() | {"expected_version": 0}))):
        with pytest.raises(ValidationError):
            forged.to_domain()
