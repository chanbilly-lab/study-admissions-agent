"""Deterministic, conservative atomic rules. This module has no provider dependency."""
from datetime import date
from hashlib import sha256
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from .models import EvidenceRecord
from .schemas import Eligibility, Evidence, Offering, Profile, Rule, RuleResult, Score
from .settings import Settings

RULESET_VERSION = "DEMO_M0_v1"
DATA_AS_OF = "2026-09-30"
SCORE_FIELDS = {"assessments.gaokao_total", "assessments.math", "assessments.english_language"}
PROFILE_FIELDS = {"subjects", "province", "entry_year", "study_level", "course_system", "applicant_category"}


def rule_shape_problem(rule: Rule, offering: Offering):
    if rule.offering_id != offering.id:
        return "规则不属于当前具体招生项目"
    if rule.field not in SCORE_FIELDS | PROFILE_FIELDS:
        return "字段不在 M0 原子白名单内"
    if rule.field in SCORE_FIELDS:
        if rule.op != "gte" or not isinstance(rule.value, (int, float)) or isinstance(rule.value, bool):
            return "M0 成绩规则需要数值 gte 门槛"
        if rule.unit not in ("points", "band") or rule.scale is None or rule.scale <= 0 or rule.value < 0 or rule.value > rule.scale:
            return "成绩规则的单位、满分或门槛无效"
    else:
        if rule.unit is not None or rule.scale is not None:
            return "非成绩规则不可附带成绩单位或满分"
        if rule.op == "exists" and rule.value is not None:
            return "exists 规则值必须为空"
        if rule.op != "exists":
            if rule.field == "entry_year":
                if rule.op not in ("eq", "gte") or not isinstance(rule.value, (int, float)) or isinstance(rule.value, bool) or not float(rule.value).is_integer():
                    return "入学年度需要整数 eq 或 gte 规则"
            elif rule.field == "subjects":
                if rule.op != "in" or not isinstance(rule.value, list) or not rule.value:
                    return "选科规则需要非空字符串数组 in 或 exists"
            elif rule.op == "eq":
                if not isinstance(rule.value, str):
                    return "文本画像字段 eq 规则需要字符串值"
            elif rule.op == "in":
                if not isinstance(rule.value, list) or not rule.value:
                    return "文本画像字段 in 规则需要非空字符串数组"
            else:
                return "文本画像字段仅支持 eq、in 或 exists"
    return None


def valid_evidence(session: Session, evidence_id: str, offering: Offering) -> tuple[Evidence | None, str | None]:
    record = session.get(EvidenceRecord, evidence_id)
    if record is None:
        return None, "证据缺失"
    try:
        evidence = Evidence.model_validate(record.payload)
    except ValidationError:
        return None, "证据格式无效"
    if evidence.review_status != "demo_reviewed":
        return None, f"证据尚不可用：{evidence.review_status}"
    if offering.id not in evidence.offering_ids:
        return None, "证据不适用于当前具体招生项目"
    actual_hash = sha256(record.raw_document.encode("utf-8")).hexdigest()
    if actual_hash != evidence.document_sha256 or actual_hash != record.document_sha256:
        return None, "合成原文哈希不一致，需重新审核"
    if evidence.excerpt not in record.raw_document:
        return None, "证据片段无法定位到合成原文"
    for field in ("entry_year", "country", "province", "applicant_category", "pathway"):
        if getattr(evidence, field) != getattr(offering, field):
            return None, f"证据适用范围不一致：{field}"
    if evidence.document_version_id != record.document_version_id:
        return None, "文档版本不一致"
    return evidence, None


def scope_problem(profile: Profile, offering: Offering, settings: Settings):
    if profile.province != settings.supported_province:
        return "画像生源省份不属于配置支持范围"
    if offering.entry_year != profile.entry_year:
        return "项目与画像入学年度不一致"
    if offering.entry_year != settings.entry_year:
        return "项目入学年度不属于当前配置周期"
    for field in ("study_level", "course_system", "applicant_category"):
        if getattr(profile, field) != getattr(offering, field):
            return f"申请范围不一致：{field}"
    if offering.country == "CN":
        if offering.province != profile.province or offering.pathway != "gaokao":
            return "国内省份或普通高考申请路径不一致"
    elif offering.country == "GB":
        if offering.province is not None or offering.pathway != "uk_undergraduate":
            return "英国本科申请路径范围不一致"
    else:
        return "M0 未支持的国家"
    return None


def deferral_condition(session, rule, offering, assessment_date):
    policy = rule.deferral
    if policy is None or rule.stage != "enrollment":
        return None, "缺少适用且带期限的已审核入学阶段后补政策"
    try:
        deadline = date.fromisoformat(policy.deadline)
    except (ValueError, TypeError):
        return None, "后补期限无效"
    if deadline < assessment_date:
        return None, "已审核后补期限已经过去，需核验现行政策"
    for identifier in (policy.evidence_id, policy.deadline_evidence_id):
        evidence, problem = valid_evidence(session, identifier, offering)
        if problem:
            return None, f"后补政策不可核验：{problem}"
        # Deadline is a reviewed structured value and must occur in the supporting raw excerpt.
        if identifier == policy.deadline_evidence_id and policy.deadline not in evidence.excerpt:
            return None, "后补期限与证据原文不一致"
    return f"须于 {policy.deadline} 后补 {rule.field} 并达到 {rule.value}/{rule.scale} {rule.unit}（合成演示政策，仅日期）", None


def evaluate_rule(session, profile, offering, rule, assessment_date):
    references = [rule.evidence_id]
    shape_problem = rule_shape_problem(rule, offering)
    if shape_problem:
        return RuleResult(rule_id=rule.id, outcome="unknown", message=shape_problem, evidence_ids=references), None
    if rule.review_status != "demo_reviewed":
        return RuleResult(rule_id=rule.id, outcome="unknown", message=f"规则尚不可用：{rule.review_status}", evidence_ids=references), None
    _, problem = valid_evidence(session, rule.evidence_id, offering)
    if problem:
        return RuleResult(rule_id=rule.id, outcome="unknown", message=problem, evidence_ids=references), None
    if rule.field in SCORE_FIELDS:
        actual = profile.assessments.get(rule.field.split(".", 1)[1])
    else:
        actual = getattr(profile, rule.field)
    if actual is None or actual == []:
        condition, problem = deferral_condition(session, rule, offering, assessment_date)
        if condition:
            references += [rule.deferral.evidence_id, rule.deferral.deadline_evidence_id]
            return RuleResult(rule_id=rule.id, outcome="deferred", message=condition, evidence_ids=references), condition
        return RuleResult(rule_id=rule.id, outcome="unknown", message=f"缺少 {rule.field}；{problem}", evidence_ids=references), None
    if isinstance(actual, Score):
        if actual.kind != "achieved":
            return RuleResult(rule_id=rule.id, outcome="unknown", message="预测成绩不能作为实得资格成绩", evidence_ids=references), None
        if rule.unit != actual.unit or rule.scale != actual.scale:
            return RuleResult(rule_id=rule.id, outcome="unknown", message="成绩单位或满分不一致，禁止自动换算", evidence_ids=references), None
        actual = actual.value
    elif rule.unit is not None or rule.scale is not None:
        return RuleResult(rule_id=rule.id, outcome="unknown", message="非成绩字段不可使用成绩单位或满分", evidence_ids=references), None

    result = None
    if rule.op == "gte":
        if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(rule.value, (int, float)):
            result = actual >= rule.value
    elif rule.op == "eq":
        if isinstance(rule.value, (str, int, float)) and not isinstance(actual, list):
            result = actual == rule.value
    elif rule.op == "in":
        if isinstance(rule.value, list) and all(isinstance(item, str) for item in rule.value):
            result = any(item in rule.value for item in actual) if isinstance(actual, list) else actual in rule.value
    elif rule.op == "exists":
        if rule.value is None:
            result = actual is not None
    if result is None:
        return RuleResult(rule_id=rule.id, outcome="unknown", message="原子操作与字段类型不匹配", evidence_ids=references), None
    return RuleResult(rule_id=rule.id, outcome="true" if result else "false",
                      message=f"{rule.field} {rule.op} {rule.value}：{'满足' if result else '实得条件不满足'}（合成规则）",
                      evidence_ids=references), None


def evaluate(session: Session, profile: Profile, offering: Offering, settings: Settings) -> Eligibility:
    problem = scope_problem(profile, offering, settings)
    reasons = []
    conditions = []
    missing = []
    quality = ["仅使用合成 DEMO 规则和证据，不能作为真实招生依据"]
    if problem:
        reasons.append(RuleResult(rule_id="DEMO_SCOPE", outcome="unknown", message=problem, evidence_ids=[]))
        quality.append(problem)
    elif not offering.rules:
        reasons.append(RuleResult(rule_id="DEMO_RULESET", outcome="unknown", message="没有可核验的硬资格规则", evidence_ids=[]))
    else:
        for rule in offering.rules:
            result, condition = evaluate_rule(session, profile, offering, rule, settings.assessment_date)
            reasons.append(result)
            if condition:
                conditions.append(condition)
            if rule.field in SCORE_FIELDS and rule.field.split(".", 1)[1] not in profile.assessments:
                missing.append(rule.field)
            if result.outcome == "unknown":
                quality.append(result.message)
    outcomes = {item.outcome for item in reasons}
    # A supported, reviewed hard failure remains ineligible even if another atom is unknown.
    status = "ineligible" if "false" in outcomes else "unknown" if "unknown" in outcomes else "conditional" if "deferred" in outcomes else "eligible"
    return Eligibility(
        id=f"DEMO_ELIGIBILITY_{uuid4().hex}", profile_version_id=profile.id, offering_id=offering.id,
        status=status, reasons=reasons, evidence_ids=sorted({eid for item in reasons for eid in item.evidence_ids}),
        missing_fields=sorted(set(missing)), conditions=conditions,
        competition_context="M0 未接入历史竞争数据，不提供录取概率",
        preference_fit="M0 未进行个人偏好排序", data_quality=quality, ruleset_version=RULESET_VERSION,
    )
