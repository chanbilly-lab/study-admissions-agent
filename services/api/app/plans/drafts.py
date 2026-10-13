"""Deterministic unconfirmed actions over exact server assessment snapshots."""

from decimal import Decimal
from types import SimpleNamespace

from ..api.v2.idempotency_canonical import canonical_request_hash
from ..rules.deferral import _deadline_status
from ..rules.expression import DecimalValue
from .schemas import (DraftBuildInput, DraftTask, PlanAssessmentRef, PlanDeadlineRef,
    PlanDraft, PlanError, SCHEMA_VERSION, GENERATOR_VERSION, plan_draft_fingerprint,
    task_fingerprint)

_TEMPLATES = {
    "VERIFY_UNKNOWN": ("核验未知资料与适用规则", "补齐或人工核验未知输入、规则和证据后重新评估；不默认允许后补。"),
    "REVIEW_INELIGIBLE": ("复核不满足条件与替代目标", "对照原评估复核不满足项，并明确选择替代目标或确认新资料后重新评估；不宣称已满足资格。"),
    "PREPARE_MATERIALS": ("审阅一般材料准备事项", "再次核对适用年度、阶段和当前依据，自行审阅一般准备事项；此任务不提交申请或保证录取。"),
    "OBTAIN_ACHIEVED": ("准备并取得对应实得记录", "取得对应实得记录，由本人明确确认新画像版本，并按各目标独立条件重新评估；不以预测或完成任务替代达标。"),
    "RECHECK_CONDITIONS": ("重新核验必要后补条件", "核对本目标的完整条件、申请与补交独立期限；更新本人确认资料后重新评估，不因任务完成声称条件已满足。"),
    "VERIFY_HISTORY": ("复核历史结果与当前依据", "重新核验画像及当前发布、规则和证据；历史资格状态仅供追溯，不作为当前准备或后补许可。"),
    "SELF_DIRECTED_STUDY": ("审阅自主学习目标", "由本人审阅自主目标并记录通用练习或测评过程；无知识诊断、提分、学习效果或录取保证。"),
}
_PERIOD_SCOPES = ("application_cycle", "intake", "channel", "course_system", "pathway",
                  "applicant_category", "province", "exam_system", "subject_scope", "batch_group")
_ACTION_PRIORITY = {"VERIFY_UNKNOWN": 0, "VERIFY_HISTORY": 0, "REVIEW_INELIGIBLE": 1,
    "OBTAIN_ACHIEVED": 2, "RECHECK_CONDITIONS": 3, "PREPARE_MATERIALS": 4, "SELF_DIRECTED_STUDY": 5}


def _rule_matches(assessment, bundle):
    target = assessment.target
    return (bundle.release_version == 1 and len(assessment.rule_refs) == 1
        and (bundle.bundle_id, bundle.expression_sha256, bundle.fact_ids, bundle.evidence_ids) == (
            assessment.rule_refs[0].bundle_id, assessment.rule_refs[0].expression_sha256,
            assessment.rule_refs[0].fact_ids, assessment.rule_refs[0].evidence_ids)
        and (bundle.release_id, bundle.requirements_version, bundle.ruleset_version, bundle.stage,
             bundle.offering_id, bundle.offering_version, bundle.scope_sha256,
             bundle.scope.dataset_id, bundle.scope.institution_id, bundle.scope.program_id, bundle.scope.country,
             bundle.is_synthetic) == (
             assessment.release_id, assessment.requirements_version, assessment.ruleset_version, assessment.stage,
             target.offering_id, target.offering_version, target.scope_sha256,
             target.dataset_id, target.institution_id, target.program_id, target.country,
             assessment.catalogue_is_synthetic))


def _policy_matches(assessment, obligation, bundle):
    target, permission = assessment.target, obligation.deferral
    if (bundle.release_version != 1 or (bundle.bundle_id, bundle.policy_id, bundle.policy_version, bundle.release_id,
         bundle.requirements_version, bundle.ruleset_version, bundle.stage, bundle.offering_id,
         bundle.offering_version, bundle.scope_sha256, bundle.scope.dataset_id,
         bundle.scope.institution_id, bundle.scope.program_id, bundle.scope.country,
         bundle.is_synthetic) != (
         permission.bundle_id, permission.policy_id, permission.policy_version, assessment.release_id,
         assessment.requirements_version, assessment.ruleset_version, assessment.stage, target.offering_id,
         target.offering_version, target.scope_sha256, target.dataset_id,
         target.institution_id, target.program_id, target.country, assessment.catalogue_is_synthetic)
        or obligation.assessment_key not in bundle.assessment_keys):
        return False
    application, supplement = bundle.application_deadline, bundle.supplement_deadline
    if (supplement is None or supplement.date_event.id != permission.supplement_deadline_event_id
        or (application.date_event.id if application else None) != permission.application_deadline_event_id
        or bundle.application_deadline_required != (permission.application_deadline_status != "not_applicable")
        or assessment.stage == "application" and not bundle.application_deadline_required):
        return False
    evidence = set(bundle.policy_evidence_ids)
    for purpose, binding in (("application", application), ("supplement", supplement)):
        if binding is None:
            continue
        event = binding.date_event
        expected_type = "application_deadline" if purpose == "application" else (
            "language_supplement" if obligation.assessment_key.startswith("ielts_") else "score_supplement")
        if ((event.dataset_id, event.offering_id, event.offering_version, event.entry_year, event.is_synthetic) != (
            target.dataset_id, target.offering_id, target.offering_version, bundle.scope.entry_year,
            assessment.catalogue_is_synthetic) or event.event_type != expected_type):
            return False
        evidence.update(binding.evidence_ids)
    return evidence == set(permission.evidence_ids)


def _bindings(current):
    rules, policies = {}, {}
    for bundle in current.rule_bundles:
        matches = [item for item in current.assessments if _rule_matches(item, bundle)]
        if not matches:
            raise PlanError(422)
        for item in matches:
            if item.current_validity == "current" and not bundle.valid_from <= current.generated_at < bundle.valid_until:
                raise PlanError(422)
            rules[item.assessment_id] = bundle
    for bundle in current.deadline_bundles:
        matches = [(item, obligation) for item in current.assessments for obligation in item.eligibility.obligations
                   if _policy_matches(item, obligation, bundle)]
        if not matches:
            raise PlanError(422)
        for item, obligation in matches:
            if item.current_validity == "current" and not bundle.valid_from <= current.generated_at < bundle.valid_until:
                raise PlanError(422)
            if item.current_validity == "current":
                for purpose, binding in (("application", bundle.application_deadline), ("supplement", bundle.supplement_deadline)):
                    if binding is None and purpose == "application" and not bundle.application_deadline_required:
                        continue
                    event_type = "application_deadline" if purpose == "application" else (
                        "language_supplement" if obligation.assessment_key.startswith("ielts_") else "score_supplement")
                    status, problem = _deadline_status(SimpleNamespace(assessment_at=current.generated_at), bundle, binding, event_type)
                    if status != "before" or problem is not None:
                        raise PlanError(422)
            policies[item.assessment_id, obligation.assessment_key] = bundle
    return rules, policies


def _canonical_decimal(value):
    whole, separator, fraction = value.partition(".")
    fraction = fraction.rstrip("0")
    return whole + ("." + fraction if separator and fraction else "")


def _completion_scope(assessment, key, rule):
    unit, scale = None, None
    known = rule is not None
    values = []
    if rule is not None:
        stack = [rule.expression]
        while stack:
            node = stack.pop()
            if node.field is not None and (node.field.name, node.field.key, node.field.basis) == ("assessment", key, "achieved"):
                literals = (node.value,) if node.value is not None else node.values
                for value in literals:
                    if type(value) is DecimalValue:
                        values.append((value.unit, _canonical_decimal(value.scale)))
                    else:
                        known = False
            stack.extend(node.children)
            if node.child is not None:
                stack.append(node.child)
        pairs = set(values)
        if len(pairs) == 1:
            unit, scale = next(iter(pairs))
            if Decimal(scale) <= 0 or len(scale) > 14:
                known = False
                unit, scale = None, None
        else:
            known = False
        if any(getattr(rule.scope, name).status == "unknown" for name in _PERIOD_SCOPES):
            known = False
    scope = {"profile_id": str(assessment.profile_id), "profile_version_id": str(assessment.profile_version_id),
             "country": assessment.target.country, "stage": assessment.stage,
             "generator_version": GENERATOR_VERSION}
    if known:
        scope.update(entry_year=rule.scope.entry_year,
            period={name: getattr(rule.scope, name).model_dump(mode="json") for name in _PERIOD_SCOPES})
    else:
        # An unresolved unit/scale/period cannot establish shared work across targets.
        scope["assessment_id"] = str(assessment.assessment_id)
    return unit, scale, canonical_request_hash(scope)


def _deadline(assessment, obligation, purpose, bundle):
    permission = obligation.deferral
    binding = getattr(bundle, purpose + "_deadline") if bundle is not None else None
    values = dict(assessment_id=str(assessment.assessment_id), assessment_key=obligation.assessment_key,
        purpose=purpose, status=getattr(permission, purpose + "_deadline_status"),
        bundle_id=str(permission.bundle_id), policy_id=str(permission.policy_id), policy_version=permission.policy_version,
        event_id=str(getattr(permission, purpose + "_deadline_event_id")) if getattr(permission, purpose + "_deadline_event_id") else None,
        evidence_ids=[str(value) for value in permission.evidence_ids],
        date_event=binding.date_event.model_dump(mode="json") if binding else None,
        reference_calendar=binding.reference_calendar if binding else None)
    values["deadline_key"] = canonical_request_hash(values)
    # Native dates are retained for strict T12 validation, not promoted to official UTC.
    if binding:
        values["date_event"] = binding.date_event
    return PlanDeadlineRef.model_validate(values)


def _task(action, *, assessment=None, work_scope=None, key=None, unit=None, scale=None,
          dependencies=(), deadlines=(), study=None):
    title, acceptance = _TEMPLATES[action]
    if study is not None:
        title = study.goal_text
    if work_scope is None:
        work_scope = canonical_request_hash({"assessment_id": str(assessment.assessment_id),
            "result_sha256": assessment.result_sha256, "target": assessment.target.model_dump(mode="json")})
    hours = study.estimated_hours if study is not None else None
    values = dict(kind="study" if study is not None else "prepare" if action in {"PREPARE_MATERIALS", "OBTAIN_ACHIEVED"} else "verify",
        action_code=action, title=title, acceptance_criteria=acceptance, assessment_key=key,
        basis="achieved" if key is not None else None, unit=unit, scale=scale, work_scope_sha256=work_scope,
        estimated_hours=hours, estimate_source="user_adjusted" if hours is not None else "unknown", estimate_editable=True,
        assessment_ids=[str(assessment.assessment_id)] if assessment is not None else [],
        dependency_keys=list(dependencies), deadline_keys=list(deadlines), confirmed=False)
    values["task_key"] = task_fingerprint(values)
    return DraftTask.model_validate(values)


def build_plan_draft(value: DraftBuildInput) -> PlanDraft:
    """Build bounded draft actions; caller independently proves identity and current authority."""
    try:
        if type(value) not in (dict, DraftBuildInput):
            raise PlanError(422)
        current = DraftBuildInput.model_validate(value)
        rules, policies = _bindings(current)
        tasks, deadlines = {}, {}
        warnings = {"UNCONFIRMED_DRAFT", "NOT_SCHEDULED", "ESTIMATES_ARE_EDITABLE"}
        def add(task):
            old = tasks.get(task.task_key)
            if old is None:
                tasks[task.task_key] = task
            else:
                values = old.model_dump(mode="python")
                for name in ("assessment_ids", "dependency_keys", "deadline_keys"):
                    values[name] = tuple(sorted(set(getattr(old, name)) | set(getattr(task, name)), key=str))
                tasks[task.task_key] = DraftTask.model_validate(values)
        for assessment in sorted(current.assessments, key=lambda item: str(item.assessment_id)):
            status = assessment.eligibility.status
            if assessment.current_validity in {"needs_review", "replaced", "withdrawn"}:
                add(_task("VERIFY_HISTORY", assessment=assessment))
                warnings.add("HISTORICAL_RESULT_REQUIRES_REVIEW")
            elif assessment.current_validity == "unavailable":
                add(_task("VERIFY_UNKNOWN", assessment=assessment))
                warnings.add("RULES_UNAVAILABLE")
            elif status == "conditional":
                dependencies, references = [], []
                for obligation in sorted(assessment.eligibility.obligations, key=lambda item: item.assessment_key):
                    bundle = policies.get((assessment.assessment_id, obligation.assessment_key))
                    own_deadlines = []
                    for purpose in ("application", "supplement"):
                        ref = _deadline(assessment, obligation, purpose, bundle)
                        deadlines[ref.deadline_key] = ref
                        own_deadlines.append(ref.deadline_key)
                        if ref.event_id is not None and ref.date_event is None:
                            warnings.add("DEADLINE_SNAPSHOT_UNAVAILABLE")
                    unit, scale, work_scope = _completion_scope(assessment, obligation.assessment_key, rules.get(assessment.assessment_id))
                    work = _task("OBTAIN_ACHIEVED", assessment=assessment, key=obligation.assessment_key,
                        unit=unit, scale=scale, work_scope=work_scope, deadlines=own_deadlines)
                    add(work)
                    dependencies.append(work.task_key)
                    references.extend(own_deadlines)
                add(_task("RECHECK_CONDITIONS", assessment=assessment, dependencies=dependencies, deadlines=references))
            else:
                action = {"eligible": "PREPARE_MATERIALS", "ineligible": "REVIEW_INELIGIBLE", "unknown": "VERIFY_UNKNOWN"}[status]
                add(_task(action, assessment=assessment))
                if assessment.ruleset_version is None:
                    warnings.add("RULES_UNAVAILABLE")
        for goal in current.study_goals:
            work_scope = canonical_request_hash({"profile_id": str(current.assessments[0].profile_id),
                "profile_version_id": str(current.assessments[0].profile_version_id), "goal_key": goal.goal_key})
            add(_task("SELF_DIRECTED_STUDY", study=goal, work_scope=work_scope))
            warnings.add("NO_EDUCATIONAL_DIAGNOSIS")
        for override in current.estimate_overrides:
            if override.task_key not in tasks:
                raise PlanError(422)
            values = tasks[override.task_key].model_dump(mode="python")
            values.update(estimated_hours=override.estimated_hours,
                          estimate_source="user_adjusted" if override.estimated_hours is not None else "unknown")
            tasks[override.task_key] = DraftTask.model_validate(values)
        first = current.assessments[0]
        refs = tuple(PlanAssessmentRef(assessment_id=item.assessment_id, result_sha256=item.result_sha256,
            target=item.target, release_id=item.release_id, requirements_version=item.requirements_version,
            ruleset_version=item.ruleset_version, stage=item.stage, eligibility_status=item.eligibility.status,
            current_validity=item.current_validity, rule_refs=item.rule_refs)
            for item in sorted(current.assessments, key=lambda item: str(item.assessment_id)))
        values = dict(schema_version=SCHEMA_VERSION, generator_version=GENERATOR_VERSION,
            status="draft", confirmed=False, scheduled=False, profile_id=first.profile_id,
            profile_version_id=first.profile_version_id, profile_sha256=first.profile_sha256,
            is_synthetic=first.profile_is_synthetic, generated_at=current.generated_at,
            expires_at=min(item.expires_at for item in current.assessments), assessment_refs=refs,
            tasks=tuple(sorted(tasks.values(), key=lambda task: (_ACTION_PRIORITY[task.action_code], task.task_key))),
            deadline_refs=tuple(deadlines[key] for key in sorted(deadlines)),
            warnings=tuple(sorted(warnings)))
        # Hash actual JSON serialization (including native UTC), then validate the whole result.
        from pydantic import TypeAdapter
        payload = TypeAdapter(dict).dump_python(values, mode="json")
        values["draft_sha256"] = plan_draft_fingerprint(payload)
        return PlanDraft.model_validate(values)
    except PlanError:
        raise
    except (ValueError, TypeError, OverflowError, RecursionError, KeyError, AttributeError):
        raise PlanError(422) from None
