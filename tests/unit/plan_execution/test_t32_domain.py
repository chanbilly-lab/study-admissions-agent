"""Strict execution inputs, immutable estimate cloning and write budgets."""

from datetime import timedelta, tzinfo
from uuid import uuid4

import pytest

from services.api.app.plan_execution.schemas import (
    CompleteInput, ConfirmInput, ConfirmationData, ExecutionData, ExecutionPolicy, ExecutionError, ProposalData,
    MAX_PROPOSAL_BYTES, MAX_SOURCE_BYTES, ScheduleConfiguration, WorkspaceInput,
)
from services.api.app.plan_execution.store import bounded_payload, effective_draft
from services.api.app.plans.scheduler import schedule_plan
from services.api.app.plans.schemas import EstimateOverride
from tests.unit.scheduling.test_t31_capacity import estimated_draft, schedule_input, slot, source_cases


def test_estimate_edits_rehash_a_clone_without_changing_task_or_source_identities():
    draft = estimated_draft(source_cases("conditional"))
    frozen = draft.model_dump(mode="json")
    task = draft.tasks[0]
    changed = effective_draft(draft, (EstimateOverride(task_key=task.task_key, estimated_hours="0"),))
    assert draft.model_dump(mode="json") == frozen
    assert changed.draft_sha256 != draft.draft_sha256
    assert changed.tasks[0].task_key == task.task_key
    assert changed.tasks[0].estimated_hours == "0" and changed.tasks[0].estimate_source == "user_adjusted"
    assert changed.assessment_refs == draft.assessment_refs and changed.deadline_refs == draft.deadline_refs
    cleared = effective_draft(changed, (EstimateOverride(task_key=task.task_key, estimated_hours=None),))
    assert cleared.tasks[0].estimated_hours is None and cleared.tasks[0].estimate_source == "unknown"
    assert cleared.confirmed is False and cleared.scheduled is False


def test_estimate_edits_reject_unrelated_keys_and_duplicate_keys():
    draft = estimated_draft(source_cases("eligible"))
    unrelated = EstimateOverride(task_key="f" * 64, estimated_hours="1")
    with pytest.raises(ExecutionError) as error:
        effective_draft(draft, (unrelated,))
    assert error.value.status_code == 422
    same = EstimateOverride(task_key=draft.tasks[0].task_key, estimated_hours="1")
    with pytest.raises(ExecutionError):
        effective_draft(draft, (same,same))


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_confirmation_is_explicit_for_plan_and_completion(value):
    with pytest.raises(ValueError):
        ConfirmInput(expected_version=2, expected_draft_sha256="a"*64,
            expected_schedule_sha256="b"*64, confirmed=value, acknowledge_unverified_deadlines=True)
    with pytest.raises(ValueError):
        CompleteInput(expected_version=3, confirmed=value)
    with pytest.raises(ValueError):
        ConfirmInput(expected_version=2, expected_draft_sha256="a"*64,
            expected_schedule_sha256="b"*64, confirmed=True, acknowledge_unverified_deadlines=value)


def test_all_write_input_boundaries_revalidate_constructed_models():
    forged = CompleteInput.model_construct(expected_version=True, confirmed=True)
    with pytest.raises(ValueError):
        CompleteInput.model_validate(forged)
    with pytest.raises(ValueError):
        WorkspaceInput.model_validate(WorkspaceInput.model_construct(expected_version=False,estimate_overrides=(),schedule=None))
    with pytest.raises(ValueError):
        ExecutionPolicy.model_validate(ExecutionPolicy.model_construct(enabled=True,allow_test_execution=True,real_execution_ready=True))


def test_calendar_input_rejects_custom_timezone_before_any_callback():
    cases = source_cases("eligible")
    now = cases[0][0].assessment_at
    class UntrustedTimezone(tzinfo):
        calls = 0
        def utcoffset(self, value):
            self.calls += 1
            raise AssertionError("untrusted callback")
    custom = UntrustedTimezone()
    with pytest.raises(ValueError):
        ScheduleConfiguration(horizon_start=now.replace(tzinfo=custom),horizon_end=now+timedelta(hours=1),
            display_timezone="UTC",weekly_hours="1",slots=(),internal_goals=(),
            availability_confirmed=True,rest_excluded=True)
    assert custom.calls == 0


def test_confirmed_projection_binds_schedule_start_to_original_confirmation_not_read_time():
    cases = source_cases("eligible")
    draft = estimated_draft(cases,hours={"PREPARE_MATERIALS":"0.01"})
    now=draft.generated_at
    source=schedule_input(cases,draft,weekly="1",slots=(slot(now,now+timedelta(hours=1)),))
    schedule=schedule_plan(source)
    config=ScheduleConfiguration(**{key:getattr(source,key) for key in ScheduleConfiguration.model_fields})
    proposal=ProposalData(id=uuid4(),state_version=2,estimate_overrides=(),effective_draft=draft,
        schedule_configuration=config,schedule=schedule,created_at=now)
    confirmation=ConfirmationData(id=uuid4(),proposal_id=proposal.id,confirmed_state_version=3,
        confirmed_at=now,acknowledge_unverified_deadlines=True)
    values=dict(schema_version="v2.t32",plan_id=uuid4(),source_plan_version_id=uuid4(),
        source_draft_sha256=draft.draft_sha256,state_version=3,state="confirmed",proposal=proposal,
        confirmation=confirmation,completed_tasks=(),created_at=now,expires_at=draft.expires_at,is_synthetic=True)
    assert ExecutionData(**values).confirmation.confirmed_at == now
    with pytest.raises(ValueError):
        ExecutionData(**{**values,"confirmation":confirmation.model_copy(update={"confirmed_at":now+timedelta(microseconds=1)})})


@pytest.mark.parametrize("limit", [MAX_SOURCE_BYTES, MAX_PROPOSAL_BYTES])
def test_json_write_budget_counts_utf8_and_json_escapes_before_acceptance(limit):
    payload = {"text":"x" * (limit - 12)}
    assert bounded_payload(payload,limit) is payload
    with pytest.raises(ExecutionError) as error:
        bounded_payload({"text":"x"*(limit-11)},limit)
    assert error.value.status_code == 422
    with pytest.raises(ExecutionError):
        bounded_payload({"text":"汉"*(limit//3)},limit)
    with pytest.raises(ExecutionError):
        bounded_payload({"text":"\n"*(limit//2)},limit)
