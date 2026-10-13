"""Independent synthetic T30 gold cases; a pure draft is not an approval port."""

from datetime import datetime, timedelta, timezone, tzinfo
from hashlib import sha256
import json
from pathlib import Path
import socket
import subprocess
import sys
from uuid import UUID

import pytest

from app.admissions_catalog.date_schemas import DateEventData, DateEventInput
from app.admissions_catalog.dates import normalize_date_event
from app.evidence.schemas import EvidenceScope
from app.plans.drafts import build_plan_draft
from app.plans.schemas import DraftBuildInput, EstimateOverride, PlanDraft, PlanError, StudyGoalInput
from app.rules.adapters.schemas import RuleBundle, TargetReference, expression_fingerprint, scope_fingerprint
from app.rules.assessment_engine import EligibilityEngineResult, evaluate_eligibility
from app.rules.deferral import DeadlineBinding, DeferralBundle, DeferralResult
from app.rules.expression import EvaluationContext, parse_expression
from app.rules.schemas import AssessmentData


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
SENTINEL = "DEMO_T30_PRIVATE_SENTINEL"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("T30 pure drafts may not perform network IO")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def known(value):
    return {"status": "known", "value": value}


def scope(index):
    names = ("degree", "course", "campus", "teaching_language", "progression_pathway", "intake",
        "application_cycle", "channel", "course_system", "pathway", "applicant_category", "province",
        "exam_system", "subject_scope", "batch_group")
    values = dict(dataset_id=UUID(int=100+index), institution_id=UUID(int=200+index),
        program_id=UUID(int=300+index), country="CN", study_level="undergraduate", entry_year=2027)
    values.update({name: known("DEMO_"+name) for name in names})
    values.update(course_system=known("gaokao"), pathway=known("gaokao"),
        applicant_category=known("cn_mainland"), province=known("Zhejiang"))
    return EvidenceScope.model_validate(values)


def allowed(index, key="math"):
    return DeferralResult(deferral_status="allowed", reason="ALLOWED", application_deadline_status="before",
        supplement_deadline_status="before", bundle_id=UUID(int=2000+index), policy_id=UUID(int=2100+index),
        policy_version="d"*64, application_deadline_event_id=UUID(int=2200+index),
        supplement_deadline_event_id=UUID(int=2300+index), evidence_ids=(UUID(int=2400+index),))


def assessment(status="conditional", *, index=1, key="math", scale="150", threshold="90", validity="current"):
    reference = {"name": "assessment", "key": key, "basis": "achieved"}
    expr = {"op": "gte", "field": reference,
        "value": {"kind": "decimal", "value": threshold, "unit": "points", "scale": scale}}
    datum = {"status": "missing", "value": None}
    if status in {"eligible", "ineligible"}:
        expr = {"op": "eq", "field": {"name": "entry_year"},
            "value": {"kind": "integer", "value": 2027 if status == "eligible" else 2028}}
        fields = [{"field": {"name": "entry_year"}, "datum": {"status": "known",
            "value": {"kind": "integer", "value": 2027}}}]
    else:
        fields = [{"field": reference, "datum": datum}]
    context = EvaluationContext.model_validate({"fields": fields, "assessment_date": None, "assessment_at": None})
    expression = parse_expression(expr)
    rule_scope = scope(index)
    bundle = RuleBundle(bundle_id=UUID(int=1000+index), reference_key="DEMO_T30_RULE_"+str(index),
        release_id=UUID(int=1100+index), release_version=1, requirements_version="a"*64,
        ruleset_version=expression_fingerprint(expression), is_synthetic=True, scope=rule_scope,
        scope_sha256=scope_fingerprint(rule_scope), offering_id=UUID(int=400+index), offering_version=1,
        stage="application", valid_from=NOW-timedelta(days=1), valid_until=NOW+timedelta(days=1),
        expression=expression, expression_sha256=expression_fingerprint(expression),
        fact_ids=(UUID(int=1200+index),), evidence_ids=(UUID(int=1300+index),))
    result = evaluate_eligibility(expression, context,
        deferrals={key: allowed(index, key)} if status == "conditional" else None)
    assert result.status == status
    raw = dict(assessment_id=UUID(int=500+index), version=1, profile_id=UUID(int=10),
        profile_version_id=UUID(int=11), profile_version=1, profile_sha256="b"*64,
        target=TargetReference(dataset_id=rule_scope.dataset_id, institution_id=rule_scope.institution_id,
            program_id=rule_scope.program_id, offering_id=bundle.offering_id, offering_version=1,
            country="CN", scope_sha256=bundle.scope_sha256), release_id=bundle.release_id,
        requirements_version=bundle.requirements_version, ruleset_version=bundle.ruleset_version,
        stage="application", assessment_at=NOW-timedelta(minutes=1), expires_at=NOW+timedelta(hours=1),
        engine_version="T28_v1", binding_mode="test_fixture", profile_is_synthetic=True,
        catalogue_is_synthetic=True, eligibility=result, competition_context={"status":"unknown","reason":"DATA_UNAVAILABLE"},
        preference_fit={"status":"unknown","reason":"DATA_UNAVAILABLE"}, data_quality={"status":"unknown","reason":"DATA_UNAVAILABLE"},
        rule_refs=({"bundle_id":bundle.bundle_id,"expression_sha256":bundle.expression_sha256,
            "fact_ids":bundle.fact_ids,"evidence_ids":bundle.evidence_ids},),
        result_sha256="0"*64, current_validity=validity, replayed=False)
    current = AssessmentData.model_validate(raw)
    raw["result_sha256"] = fingerprint({name: value for name, value in current.model_dump(mode="json").items()
        if name not in {"result_sha256", "current_validity", "replayed"}})
    return AssessmentData.model_validate(raw), bundle


def build(*items, rules=(), deadlines=(), **updates):
    raw = dict(assessments=items, confirmed=True, generated_at=NOW, rule_bundles=rules,
        deadline_bundles=deadlines, study_goals=(), estimate_overrides=())
    raw.update(updates)
    return build_plan_draft(DraftBuildInput.model_construct(**raw))


def rehash(source, **changes):
    raw = source.model_dump()
    raw.update(changes)
    validated = AssessmentData.model_validate(raw)
    raw["result_sha256"] = fingerprint({name: value for name, value in validated.model_dump(mode="json").items()
        if name not in {"result_sha256", "current_validity", "replayed"}})
    return AssessmentData.model_validate(raw)


def date_binding(item, index, *, purpose, precision="second"):
    permission = item.eligibility.obligations[0].deferral
    instant = NOW+timedelta(days=1 if purpose == "application" else 2) if precision == "date" else (
        NOW+timedelta(hours=2 if purpose == "application" else 3))
    raw = DateEventInput(id=getattr(permission, purpose+"_deadline_event_id"), dataset_id=item.target.dataset_id,
        offering_id=item.target.offering_id, offering_version=1, reference_key="DEMO_T30_"+purpose+str(index),
        is_synthetic=True, entry_year=2027, event_type="application_deadline" if purpose == "application" else "score_supplement",
        original_text="DEMO 原文日期，不能据此补23:59", precision=precision, local_date=instant.date(),
        local_time=instant.time().replace(tzinfo=None) if precision == "second" else None,
        timezone="UTC", source_alignment="pending", evidence_reference=None)
    resolution = normalize_date_event(raw)
    event = DateEventData(**raw.model_dump(), **resolution.model_dump(), utc_instant=None,
        review_state="draft", evidence_state="unresolved")
    return DeadlineBinding(date_event=event, evidence_ids=permission.evidence_ids, reference_calendar="UTC")


def deadline_bundle(item, rule, index, *, precision="second"):
    permission = item.eligibility.obligations[0].deferral
    return DeferralBundle(bundle_id=permission.bundle_id, reference_key="DEMO_T30_POLICY_"+str(index),
        policy_id=permission.policy_id, policy_version=permission.policy_version, release_id=item.release_id,
        release_version=1, requirements_version=item.requirements_version, ruleset_version=item.ruleset_version,
        is_synthetic=True, scope=rule.scope, scope_sha256=rule.scope_sha256, offering_id=item.target.offering_id,
        offering_version=1, stage=item.stage, assessment_keys=("math",), allowed_missing_states=("missing", "pending"),
        valid_from=NOW-timedelta(days=1), valid_until=NOW+timedelta(days=1), policy_evidence_ids=permission.evidence_ids,
        application_deadline_required=True, application_deadline=date_binding(item,index,purpose="application",precision=precision),
        supplement_deadline=date_binding(item,index,purpose="supplement",precision=precision))


def safe_failure(operation):
    with pytest.raises(PlanError) as failure:
        operation()
    assert failure.value.status_code == 422
    assert SENTINEL not in str(failure.value)+repr(failure.value)


@pytest.mark.parametrize("status,actions", [("eligible", {"PREPARE_MATERIALS"}),
    ("ineligible", {"REVIEW_INELIGIBLE"}), ("unknown", {"VERIFY_UNKNOWN"}),
    ("conditional", {"OBTAIN_ACHIEVED", "RECHECK_CONDITIONS"})])
def test_independent_four_state_gold_uses_real_evaluation_and_preserves_original_hash(status, actions):
    source, rule = assessment(status)
    before = source.model_dump(mode="json")
    draft = build(source, rules=(rule,))
    assert {task.action_code for task in draft.tasks} == actions
    assert draft.status == "draft" and draft.confirmed is False and draft.scheduled is False
    assert draft.assessment_refs[0].result_sha256 == source.result_sha256
    assert all(task.confirmed is False and task.estimate_editable is True for task in draft.tasks)
    assert source.model_dump(mode="json") == before


@pytest.mark.parametrize("historical", ["needs_review", "replaced", "withdrawn"])
@pytest.mark.parametrize("status", ["eligible", "conditional"])
def test_invalid_historical_success_is_only_verification_even_if_original_hash_is_valid(status, historical):
    source, rule = assessment(status, validity=historical)
    draft = build(source, rules=(rule,))
    assert {task.action_code for task in draft.tasks} == {"VERIFY_HISTORY"}
    assert draft.assessment_refs[0].eligibility_status == status
    assert draft.assessment_refs[0].current_validity == historical
    assert not draft.deadline_refs and "HISTORICAL_RESULT_REQUIRES_REVIEW" in draft.warnings


def test_unknown_without_any_ruleset_still_builds_only_verification():
    source, _ = assessment("unknown")
    raw = source.model_dump()
    raw.update(binding_mode="unavailable", ruleset_version=None, rule_refs=(), current_validity="unavailable",
        eligibility=EligibilityEngineResult(status="unknown", reason="RULESET_UNAVAILABLE", evaluation=None, obligations=()))
    changed = AssessmentData.model_validate(raw)
    raw["result_sha256"] = fingerprint({name:value for name,value in changed.model_dump(mode="json").items()
        if name not in {"result_sha256","current_validity","replayed"}})
    draft = build(AssessmentData.model_validate(raw))
    assert {task.action_code for task in draft.tasks} == {"VERIFY_UNKNOWN"} and not draft.deadline_refs


@pytest.mark.parametrize("second_scale,shared", [("150", True), ("100", False)])
def test_shared_work_keeps_each_target_policy_and_two_deadline_references(second_scale, shared):
    first, first_rule = assessment(index=1, threshold="90")
    second, second_rule = assessment(index=2, threshold="95", scale=second_scale)
    draft = build(first, second, rules=(first_rule, second_rule))
    work = [task for task in draft.tasks if task.action_code == "OBTAIN_ACHIEVED"]
    rechecks = [task for task in draft.tasks if task.action_code == "RECHECK_CONDITIONS"]
    assert len(work) == (1 if shared else 2) and len(rechecks) == 2
    assert len(draft.deadline_refs) == 4
    assert {(ref.assessment_id,ref.purpose,ref.policy_id) for ref in draft.deadline_refs} == {
        (item.assessment_id,purpose,item.eligibility.obligations[0].deferral.policy_id)
        for item in (first,second) for purpose in ("application","supplement")}
    assert all(ref.date_event is None and ref.reference_calendar is None for ref in draft.deadline_refs)
    for check in rechecks:
        assert check.dependency_keys and all(key in {task.task_key for task in work} for key in check.dependency_keys)
    if shared:
        assert set(work[0].assessment_ids) == {first.assessment_id,second.assessment_id}
        assert set(work[0].deadline_keys) == {ref.deadline_key for ref in draft.deadline_refs}


def test_missing_rule_snapshot_does_not_merge_identical_assessment_keys_across_targets():
    first, _ = assessment(index=1)
    second, _ = assessment(index=2)
    draft = build(first,second)
    assert len([task for task in draft.tasks if task.action_code == "OBTAIN_ACHIEVED"]) == 2


def test_an_unused_any_branch_is_not_a_second_required_completion_task():
    source, rule = assessment()
    original = rule.expression
    other = parse_expression({"op":"gte","field":{"name":"assessment","key":"physics","basis":"achieved"},
        "value":{"kind":"decimal","value":"80","unit":"points","scale":"100"}})
    expression = parse_expression({"op":"any","children":[original,other]})
    context = EvaluationContext.model_validate({"fields":[{"field":{"name":"assessment","key":key,"basis":"achieved"},
        "datum":{"status":"missing","value":None}} for key in ("math","physics")],
        "assessment_date":None,"assessment_at":None})
    result = evaluate_eligibility(expression,context,deferrals={"math":allowed(1),"physics":allowed(2)})
    rule = rule.model_copy(update={"expression":expression,"expression_sha256":expression_fingerprint(expression),
        "ruleset_version":expression_fingerprint(expression)})
    reference = source.rule_refs[0].model_copy(update={"expression_sha256":rule.expression_sha256})
    source = rehash(source,eligibility=result,ruleset_version=rule.ruleset_version,rule_refs=(reference,))
    draft = build(source,rules=(rule,))
    chosen = {item.assessment_key for item in result.obligations}
    assert len(chosen)==1
    assert {task.assessment_key for task in draft.tasks if task.action_code=="OBTAIN_ACHIEVED"}==chosen
    assert {ref.assessment_key for ref in draft.deadline_refs}==chosen


def test_different_application_cycle_is_not_shared_even_with_identical_grade_and_scale():
    first,first_rule=assessment(index=1)
    second,second_rule=assessment(index=2)
    changed_scope=second_rule.scope.model_copy(update={"application_cycle":{"status":"known","value":"DEMO_other_cycle"}})
    changed_scope=EvidenceScope.model_validate(changed_scope)
    changed_hash=scope_fingerprint(changed_scope)
    second_rule=second_rule.model_copy(update={"scope":changed_scope,"scope_sha256":changed_hash})
    second=rehash(second,target=second.target.model_copy(update={"scope_sha256":changed_hash}))
    draft=build(first,second,rules=(first_rule,second_rule))
    assert len([task for task in draft.tasks if task.action_code=="OBTAIN_ACHIEVED"])==2


def test_explicit_self_directed_learning_does_not_infer_weakness_or_confirm_a_plan():
    source,rule=assessment("unknown")
    goal=StudyGoalInput(goal_key="DEMO_autonomous_goal",goal_text="记录自己的数学练习过程",estimated_hours="0")
    draft=build(source,rules=(rule,),study_goals=(goal,))
    studies=[task for task in draft.tasks if task.kind=="study"]
    assert len(studies)==1 and studies[0].title==goal.goal_text and studies[0].estimated_hours=="0"
    assert studies[0].assessment_key is None and studies[0].basis is None and not studies[0].deadline_keys
    assert "NO_EDUCATIONAL_DIAGNOSIS" in draft.warnings and not draft.confirmed


@pytest.mark.parametrize("precision", ["second", "date"])
def test_actual_bound_dates_preserve_raw_precision_and_do_not_become_official_utc(precision):
    source, rule = assessment()
    policy = deadline_bundle(source,rule,1,precision=precision)
    draft = build(source,rules=(rule,),deadlines=(policy,))
    assert len(draft.deadline_refs) == 2
    for ref in draft.deadline_refs:
        assert ref.date_event.precision == precision and ref.date_event.utc_instant is None
        assert ref.date_event.original_text == "DEMO 原文日期，不能据此补23:59"
        if precision == "date":
            assert ref.date_event.local_time is None and ref.date_event.calculated_utc_instant is None


def test_date_only_today_cannot_keep_a_stale_before_permission_status():
    source,rule=assessment()
    policy=deadline_bundle(source,rule,1,precision="date")
    event=policy.application_deadline.date_event.model_copy(update={"local_date":NOW.date()})
    binding=policy.application_deadline.model_copy(update={"date_event":event})
    policy=policy.model_copy(update={"application_deadline":binding})
    safe_failure(lambda: build(source,rules=(rule,),deadlines=(policy,)))


@pytest.mark.parametrize("tamper", ["event_type","offering","year","policy","evidence"])
def test_deadline_snapshots_must_match_actual_obligation_scope_policy_and_evidence(tamper):
    source, rule = assessment()
    policy = deadline_bundle(source,rule,1)
    changes = {}
    if tamper in {"event_type","offering","year"}:
        event = policy.supplement_deadline.date_event.model_copy(update={
            "event_type":"application_deadline"} if tamper=="event_type" else {
            "offering_id":UUID(int=9999)} if tamper=="offering" else {"entry_year":2028})
        changes["supplement_deadline"] = policy.supplement_deadline.model_copy(update={"date_event":event})
    elif tamper=="policy":
        changes["policy_version"] = "e"*64
    else:
        changes["policy_evidence_ids"] = (UUID(int=9999),)
    safe_failure(lambda: build(source,rules=(rule,),deadlines=(policy.model_copy(update=changes),)))


@pytest.mark.parametrize("value", ["0", "1.250000", None])
def test_estimates_are_editable_without_changing_task_semantics_or_confirming(value):
    source, rule = assessment("eligible")
    first = build(source,rules=(rule,))
    override = EstimateOverride(task_key=first.tasks[0].task_key,estimated_hours=value)
    changed = build(source,rules=(rule,),estimate_overrides=(override,))
    assert changed.tasks[0].task_key == first.tasks[0].task_key
    assert changed.tasks[0].estimated_hours == value and changed.tasks[0].estimate_editable is True
    assert changed.tasks[0].estimate_source == ("unknown" if value is None else "user_adjusted")
    assert changed.confirmed is False


def test_unknown_override_and_forged_nested_copy_do_not_silently_pass():
    source, _ = assessment("eligible")
    safe_failure(lambda: build(source,estimate_overrides=(EstimateOverride(task_key="f"*64,estimated_hours="1"),)))
    forged = source.model_copy(update={"result_sha256":"0"*64})
    safe_failure(lambda: build_plan_draft(DraftBuildInput.model_construct(assessments=(forged,),confirmed=True,
        generated_at=NOW,study_goals=(),estimate_overrides=(),rule_bundles=(),deadline_bundles=())))


def test_invalid_private_goal_nested_construct_is_revalidated_and_not_echoed():
    source,_=assessment("unknown")
    goal=StudyGoalInput.model_construct(goal_key="DEMO_private_goal",goal_text=SENTINEL+"\x80",estimated_hours=None)
    safe_failure(lambda: build(source,study_goals=(goal,)))


@pytest.mark.parametrize("field,value", [("confirmed",1),("generated_at",NOW.replace(tzinfo=None)),
    ("assessments",()),("profile_sha256","c"*64),("profile_version_id",UUID(int=8888)),
    ("catalogue_is_synthetic",False),("assessment_at",NOW+timedelta(seconds=1)),("expires_at",NOW)])
def test_exact_confirmation_profile_mode_and_retention_reject_forged_constructs(field,value):
    source, _ = assessment()
    other, _ = assessment(index=2)
    raw = dict(assessments=(source,other),confirmed=True,generated_at=NOW,study_goals=(),
        estimate_overrides=(),rule_bundles=(),deadline_bundles=())
    if field in {"confirmed","generated_at","assessments"}:
        raw[field]=value
    else:
        raw["assessments"]=(source,other.model_copy(update={field:value}))
    safe_failure(lambda: build_plan_draft(DraftBuildInput.model_construct(**raw)))


def test_custom_timezone_is_rejected_without_executing_attacker_callbacks():
    calls=[]
    class EvilTimezone(tzinfo):
        def utcoffset(self, value):
            calls.append(SENTINEL)
            raise AssertionError(SENTINEL)
    source,_=assessment("eligible")
    raw=DraftBuildInput.model_construct(assessments=(source,),confirmed=True,
        generated_at=datetime(2026,10,4,tzinfo=EvilTimezone()),study_goals=(),estimate_overrides=(),
        rule_bundles=(),deadline_bundles=())
    safe_failure(lambda: build_plan_draft(raw))
    assert calls==[]


def test_pure_import_does_not_load_m0_database_provider_or_read_environment():
    code = r'''
import builtins, os, socket, sys
from importlib.util import find_spec
from pathlib import Path
sys.path.insert(0, sys.argv[1])
original=builtins.__import__
def guarded(name,*args,**kwargs):
    package=(args[0] or {}).get('__package__','') if args else ''
    if name.split('.')[0] in {'sqlalchemy','psycopg'} or name in {'app.database','app.models','app.planning','app.seed'} or name.startswith('app.providers') or (name.startswith('providers') and package.startswith('app')):
        raise AssertionError('Unexpected business IO import: '+name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
def forbidden(*args,**kwargs): raise AssertionError('Unexpected network')
socket.socket.connect=forbidden
socket.getaddrinfo=forbidden
os.environ.update(PLANS_DATABASE_URL='DEMO_PRIVATE_SENTINEL',V2_DATA_MODE='verified',DEMO_MODE='false',LLM_API_KEY='DEMO_PRIVATE_SENTINEL')
from app.plans.drafts import build_plan_draft
assert callable(build_plan_draft)
assert Path(find_spec('app.planning').origin)==Path(sys.argv[1])/'app'/'planning.py'
assert not any(name.startswith(('sqlalchemy','psycopg','app.providers','app.database','app.planning','app.seed')) for name in sys.modules)
print('pure import isolated')
'''
    directory=Path(__file__).resolve().parents[3]/"services"/"api"
    result=subprocess.run([sys.executable,"-I","-B","-c",code,str(directory)],capture_output=True,
        text=True,timeout=30)
    assert result.returncode==0, result.stderr
    assert result.stdout.strip()=="pure import isolated"
