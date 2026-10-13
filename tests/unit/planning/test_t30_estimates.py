"""Explicit adjustable estimates and bounded pure-input checks."""

from datetime import timedelta
from uuid import UUID

import pytest

from services.api.app.plans.drafts import build_plan_draft
from services.api.app.plans.schemas import DraftBuildInput, PlanError, PlanPolicy
from test_t30_drafts import NOW, build, fixture_case


@pytest.mark.parametrize("hours", ["0", "0.125", "1000", None])
def test_hours_are_editable_parameters_with_stable_task_identity(hours):
    case = fixture_case("eligible")
    original = build(case)
    changed = build(case, estimate_overrides=({"task_key": original.tasks[0].task_key, "estimated_hours": hours},))
    assert changed.tasks[0].task_key == original.tasks[0].task_key
    assert changed.tasks[0].estimated_hours == hours
    assert changed.tasks[0].estimate_source == ("unknown" if hours is None else "user_adjusted")
    assert changed.scheduled is False and changed.confirmed is False


@pytest.mark.parametrize("hours", [1.25, True, -1, "-1", "1e3", " 1", "1000.000001", "1\n"])
def test_invalid_estimates_fail_with_fixed_safe_error(hours):
    case = fixture_case("eligible")
    original = build(case)
    with pytest.raises(PlanError) as error:
        build_plan_draft({"assessments": (case[0],), "confirmed": True, "generated_at": NOW,
            "estimate_overrides": ({"task_key": original.tasks[0].task_key, "estimated_hours": hours},)})
    assert error.value.code == "INVALID_PLAN_INPUT" and error.value.status_code == 422


def test_unknown_task_override_cannot_mutate_or_add_work():
    with pytest.raises(PlanError):
        build_plan_draft({"assessments": (fixture_case("eligible")[0],), "confirmed": True,
            "generated_at": NOW, "estimate_overrides": ({"task_key": "f" * 64, "estimated_hours": "2"},)})


def test_self_directed_study_requires_an_explicit_bounded_student_goal():
    case = fixture_case("unknown")
    assert all(task.kind != "study" for task in build(case).tasks)
    draft = build(case, study_goals=({"goal_key": "DEMO_MY_GOAL", "goal_text": "记录自主阅读练习", "estimated_hours": "1.5"},))
    study = next(task for task in draft.tasks if task.kind == "study")
    assert study.title == "记录自主阅读练习" and study.assessment_ids == () and study.dependency_keys == ()
    assert study.action_code == "SELF_DIRECTED_STUDY" and study.estimated_hours == "1.5"
    assert "NO_EDUCATIONAL_DIAGNOSIS" in draft.warnings


@pytest.mark.parametrize("change", ["hash", "profile", "mode", "expiry", "future", "confirm", "duplicate", "constructed"])
def test_copied_or_constructed_source_inputs_are_fully_revalidated(change):
    case = fixture_case()
    source = case[0]
    options = {"assessments": (source,), "confirmed": True, "generated_at": NOW}
    if change == "hash":
        options["assessments"] = (source.model_copy(update={"result_sha256": "f" * 64}),)
    elif change == "profile":
        second = fixture_case(token=1)[0].model_copy(update={"profile_id": UUID(int=12345)})
        options["assessments"] = (source, second)
    elif change == "mode":
        options["assessments"] = (source.model_copy(update={"catalogue_is_synthetic": False}),)
    elif change == "expiry":
        options["generated_at"] = source.expires_at
    elif change == "future":
        options["generated_at"] = NOW - timedelta(microseconds=1)
    elif change == "confirm":
        options["confirmed"] = 1
    elif change == "duplicate":
        options["assessments"] = (source, source)
    else:
        bad = DraftBuildInput.model_construct(**{**options, "confirmed": False})
        options = bad
    with pytest.raises(PlanError):
        build_plan_draft(options)


def test_plan_policy_has_no_real_processing_switch():
    assert PlanPolicy().enabled is False and PlanPolicy().real_plans_ready is False
    for value in (True, 0, 1):
        with pytest.raises(ValueError):
            PlanPolicy(real_plans_ready=value)
