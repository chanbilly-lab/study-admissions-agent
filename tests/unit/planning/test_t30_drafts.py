"""T30 draft action goldens over actual T28 four-state evaluations."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest

from services.api.app.admissions_catalog.date_schemas import DateEventData, DateEventInput
from services.api.app.admissions_catalog.dates import normalize_date_event
from services.api.app.evidence.schemas import EvidenceScope
from services.api.app.plans.drafts import build_plan_draft
from services.api.app.plans.schemas import (DraftBuildInput, PlanError, assessment_fingerprint,
    plan_draft_fingerprint)
from services.api.app.rules.adapters.schemas import (RuleBundle, expression_fingerprint, scope_fingerprint)
from services.api.app.rules.assessment_engine import evaluate_eligibility
from services.api.app.rules.deferral import DeferralBundle, DeferralResult
from services.api.app.rules.expression import EvaluationContext
from services.api.app.rules.schemas import AssessmentData

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
PERIOD = ("intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")


def fixture_case(status="conditional", *, token=0, scale="750", stage="application", cycle="DEMO_2027", predicted=False):
    uid = lambda n: UUID(int=n + token * 100)
    known = lambda text: {"status": "known", "value": text}
    scope = EvidenceScope(dataset_id=UUID(int=1), institution_id=UUID(int=2), program_id=uid(3),
        country="CN", study_level="undergraduate", entry_year=2027,
        **{key: known("DEMO_" + key) for key in ("degree", "course", "campus", "teaching_language", "progression_pathway", *PERIOD)},
        course_system=known("gaokao"), pathway=known("gaokao"), applicant_category=known("cn_mainland"),
        province=known("Zhejiang"))
    scope = scope.model_copy(update={"application_cycle": type(scope.application_cycle).model_validate(known(cycle))})
    expression = {"op": "gte", "field": {"name": "assessment", "key": "math", "basis": "predicted" if predicted else "achieved"},
        "value": {"kind": "decimal", "value": "600", "unit": "points", "scale": scale}}
    rule = RuleBundle(bundle_id=uid(4), reference_key="DEMO_RULE", release_id=uid(5), release_version=1,
        requirements_version="a" * 64, ruleset_version="b" * 64, is_synthetic=True, scope=scope,
        scope_sha256=scope_fingerprint(scope), offering_id=uid(6), offering_version=1, stage=stage,
        valid_from=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=30), expression=expression,
        expression_sha256=expression_fingerprint(expression), fact_ids=(uid(7),), evidence_ids=(uid(8),))
    def event(identifier, kind):
        item = DateEventInput(id=identifier, dataset_id=scope.dataset_id, offering_id=rule.offering_id,
            offering_version=1, reference_key="DEMO_DEADLINE", is_synthetic=True, entry_year=2027,
            event_type=kind, original_text="DEMO_2027 date-only", precision="date", local_date=date(2027, 5, 1),
            local_time=None, timezone="Asia/Shanghai", source_alignment="pending", evidence_reference="DEMO_EVIDENCE")
        return DateEventData(**item.model_dump(), **normalize_date_event(item).model_dump(),
            utc_instant=None, review_state="draft", evidence_state="unresolved")
    application = event(uid(9), "application_deadline") if stage == "application" else None
    supplement = event(uid(10), "score_supplement")
    evidence = (uid(11), uid(12), uid(13)) if application else (uid(11), uid(13))
    permission = DeferralResult(deferral_status="allowed", reason="ALLOWED",
        application_deadline_status="before" if application else "not_applicable", supplement_deadline_status="before",
        bundle_id=uid(14), policy_id=uid(15), policy_version="c" * 64,
        application_deadline_event_id=application.id if application else None,
        supplement_deadline_event_id=supplement.id, evidence_ids=evidence)
    policy = DeferralBundle(bundle_id=permission.bundle_id, reference_key="DEMO_POLICY", policy_id=permission.policy_id,
        policy_version=permission.policy_version, release_id=rule.release_id, release_version=1,
        requirements_version=rule.requirements_version, ruleset_version=rule.ruleset_version,
        is_synthetic=True, scope=scope, scope_sha256=rule.scope_sha256, offering_id=rule.offering_id,
        offering_version=1, stage=stage, assessment_keys=("math",), allowed_missing_states=("missing", "pending"),
        valid_from=rule.valid_from, valid_until=rule.valid_until, policy_evidence_ids=(uid(11),),
        application_deadline_required=bool(application),
        application_deadline={"date_event": application, "evidence_ids": (uid(12),), "reference_calendar": "Asia/Shanghai"} if application else None,
        supplement_deadline={"date_event": supplement, "evidence_ids": (uid(13),), "reference_calendar": "Asia/Shanghai"})
    datum = {"status": "missing", "value": None}
    if status in {"eligible", "ineligible"}:
        datum = {"status": "known", "value": {"kind": "decimal", "value": "650" if status == "eligible" else "550", "unit": "points", "scale": scale}}
    context = EvaluationContext(fields=({"field": expression["field"], "datum": datum},))
    eligibility = evaluate_eligibility(expression, context, deferrals={"math": permission} if status == "conditional" else None)
    assert eligibility.status == status if not predicted else eligibility.status == "unknown"
    values = dict(assessment_id=uid(16), version=1, profile_id=UUID(int=17), profile_version_id=UUID(int=18),
        profile_version=1, profile_sha256="d" * 64,
        target=dict(dataset_id=scope.dataset_id, institution_id=scope.institution_id, program_id=scope.program_id,
            offering_id=rule.offering_id, offering_version=1, country="CN", scope_sha256=rule.scope_sha256),
        release_id=rule.release_id, requirements_version=rule.requirements_version, ruleset_version=rule.ruleset_version,
        stage=stage, assessment_at=NOW, expires_at=NOW + timedelta(days=10), engine_version="T28_v1",
        binding_mode="test_fixture", profile_is_synthetic=True, catalogue_is_synthetic=True, eligibility=eligibility,
        competition_context={"status": "unknown", "reason": "DATA_UNAVAILABLE"},
        preference_fit={"status": "unknown", "reason": "DATA_UNAVAILABLE"}, data_quality={"status": "unknown", "reason": "DATA_UNAVAILABLE"},
        rule_refs=({"bundle_id": rule.bundle_id, "expression_sha256": rule.expression_sha256,
            "fact_ids": rule.fact_ids, "evidence_ids": rule.evidence_ids},), result_sha256="0" * 64,
        current_validity="current", replayed=False)
    initial = AssessmentData.model_validate(values)
    values["result_sha256"] = assessment_fingerprint(initial.model_dump(mode="json"))
    return AssessmentData.model_validate(values), rule, policy


def build(*cases, **options):
    return build_plan_draft(DraftBuildInput(assessments=tuple(item[0] for item in cases), confirmed=True,
        generated_at=NOW, **options))


@pytest.mark.parametrize("status,actions", [
    ("eligible", {"PREPARE_MATERIALS"}), ("ineligible", {"REVIEW_INELIGIBLE"}),
    ("unknown", {"VERIFY_UNKNOWN"}), ("conditional", {"OBTAIN_ACHIEVED", "RECHECK_CONDITIONS"}),
])
def test_four_state_actions_use_actual_engine_outcomes(status, actions):
    case = fixture_case(status)
    draft = build(case)
    assert {item.action_code for item in draft.tasks} == actions
    assert draft.status == "draft" and draft.confirmed is False and draft.scheduled is False
    assert all(item.confirmed is False and item.estimate_editable is True and item.estimated_hours is None for item in draft.tasks)
    assert draft.assessment_refs[0].eligibility_status == status
    assert plan_draft_fingerprint(draft.model_dump(mode="json")) == draft.draft_sha256


def test_compatible_shared_achieved_work_retains_each_targets_policy_and_dependency():
    a, b = fixture_case(token=1), fixture_case(token=2)
    draft = build(a, b, rule_bundles=(a[1], b[1]), deadline_bundles=(a[2], b[2]))
    work = [task for task in draft.tasks if task.action_code == "OBTAIN_ACHIEVED"]
    checks = [task for task in draft.tasks if task.action_code == "RECHECK_CONDITIONS"]
    assert len(work) == 1 and set(work[0].assessment_ids) == {a[0].assessment_id, b[0].assessment_id}
    assert work[0].unit == "points" and work[0].scale == "750"
    assert len(checks) == 2 and all(task.dependency_keys == (work[0].task_key,) for task in checks)
    assert len(draft.deadline_refs) == 4 and len(work[0].deadline_keys) == 4
    assert {item.policy_id for item in draft.deadline_refs} == {a[2].policy_id, b[2].policy_id}
    assert all(item.date_event.precision == "date" and item.date_event.local_time is None
        and item.date_event.calculated_utc_instant is None and item.date_event.utc_instant is None for item in draft.deadline_refs)


@pytest.mark.parametrize("change", ["scale", "cycle", "no_rule"])
def test_incompatible_or_unproved_work_is_not_merged(change):
    a = fixture_case(token=1)
    b = fixture_case(token=2, scale="800" if change == "scale" else "750", cycle="DEMO_2028" if change == "cycle" else "DEMO_2027")
    draft = build(a, b, rule_bundles=() if change == "no_rule" else (a[1], b[1]))
    assert len([item for item in draft.tasks if item.action_code == "OBTAIN_ACHIEVED"]) == 2


@pytest.mark.parametrize("validity", ["needs_review", "withdrawn", "replaced"])
def test_invalid_historical_conditional_has_only_verification_actions(validity):
    original, rule, policy = fixture_case()
    historical = original.model_copy(update={"current_validity": validity, "replayed": True})
    draft = build((historical, rule, policy))
    assert [item.action_code for item in draft.tasks] == ["VERIFY_HISTORY"]
    assert draft.assessment_refs[0].eligibility_status == "conditional"
    assert draft.assessment_refs[0].current_validity == validity and draft.deadline_refs == ()


def test_no_date_snapshot_preserves_two_event_refs_without_inventing_a_time():
    case = fixture_case()
    draft = build(case)
    assert {item.purpose for item in draft.deadline_refs} == {"application", "supplement"}
    assert all(item.date_event is None and item.reference_calendar is None for item in draft.deadline_refs)
    assert {item.event_id for item in draft.deadline_refs} == {case[2].application_deadline.date_event.id, case[2].supplement_deadline.date_event.id}
    assert "DEADLINE_SNAPSHOT_UNAVAILABLE" in draft.warnings


def test_enrollment_explicit_application_not_applicable_is_separate_from_supplement():
    case = fixture_case(stage="enrollment")
    draft = build(case, deadline_bundles=(case[2],))
    application = next(item for item in draft.deadline_refs if item.purpose == "application")
    supplement = next(item for item in draft.deadline_refs if item.purpose == "supplement")
    assert application.status == "not_applicable" and application.event_id is None and application.date_event is None
    assert supplement.status == "before" and supplement.date_event.id == case[2].supplement_deadline.date_event.id


def test_predicted_value_does_not_create_achieved_preparation():
    case = fixture_case("unknown", predicted=True)
    assert [item.action_code for item in build(case).tasks] == ["VERIFY_UNKNOWN"]


def test_unknown_verification_precedes_preparation_and_optional_study_in_stable_order():
    unknown = fixture_case("unknown", token=1)
    eligible = fixture_case("eligible", token=2)
    goal = {"goal_key": "DEMO_ORDER", "goal_text": "审阅自主阅读记录", "estimated_hours": None}
    draft = build(eligible, unknown, study_goals=(goal,))
    reversed_draft = build(unknown, eligible, study_goals=(goal,))
    assert [task.action_code for task in draft.tasks] == ["VERIFY_UNKNOWN", "PREPARE_MATERIALS", "SELF_DIRECTED_STUDY"]
    assert draft == reversed_draft


def test_unavailable_current_proof_cannot_reuse_a_historical_completion_permission():
    source, rule, policy = fixture_case()
    unavailable = source.model_copy(update={"current_validity": "unavailable"})
    draft = build((unavailable, rule, policy))
    assert [task.action_code for task in draft.tasks] == ["VERIFY_UNKNOWN"]
    assert draft.deadline_refs == () and draft.assessment_refs[0].eligibility_status == "conditional"


@pytest.mark.parametrize("kind", ["rule", "policy"])
def test_a_bundle_cannot_claim_an_unpublished_release_version(kind):
    case = fixture_case()
    with pytest.raises(PlanError):
        build(case, **({"rule_bundles": (case[1].model_copy(update={"release_version": 2}),)}
            if kind == "rule" else {"deadline_bundles": (case[2].model_copy(update={"release_version": 2}),)}))
