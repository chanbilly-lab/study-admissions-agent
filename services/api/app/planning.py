from uuid import uuid4

from .eligibility import valid_evidence
from .providers import NarrativeProvider
from .schemas import DraftTask, Eligibility, Offering, PlanDraft, Profile


def build_draft(session, profile: Profile, offerings: list[Offering], results: list[Eligibility], provider: NarrativeProvider, mode: str):
    narrative = provider.draft_narrative(profile, results)
    tasks = []
    warnings = ["所有机构、规则、日期和画像均为合成演示。草案未确认，不执行申请或提交。",
                "估时是可修改的准备参数；M0 未排周计划，不承诺完成时间或学习效果。"]
    for offering, result in zip(offerings, results, strict=True):
        target_date = None
        deadline_id = None
        if result.status == "conditional":
            title = "核验并准备后补成绩"
            acceptance = "对照引用的 DEMO 后补政策确认成绩要求和日期；取得实得成绩后重新检查"
            for rule in offering.rules:
                if any(item.rule_id == rule.id and item.outcome == "deferred" for item in result.reasons):
                    target_date = rule.deferral.deadline
                    deadline_id = rule.deferral.deadline_evidence_id
                    break
        elif result.status == "ineligible":
            title = "复核不满足项与替代项目"
            acceptance = "逐项复核实得不满足条件；选择替代 DEMO 项目或补充新成绩后重新检查"
        elif result.status == "unknown":
            title = "补充资料并人工核验未知项"
            acceptance = "补齐缺失实得成绩或取得适用的已审核证据；重新检查资格，不默认可后补"
        else:
            title = "审阅材料准备草案"
            acceptance = "核对已满足的合成规则、材料清单和适用年度，用户审核后再自行决定下一步"
            if offering.deadline and offering.deadline_evidence_id:
                evidence, problem = valid_evidence(session, offering.deadline_evidence_id, offering)
                if not problem and offering.deadline in evidence.excerpt:
                    target_date = offering.deadline
                    deadline_id = offering.deadline_evidence_id
        if target_date is None:
            warnings.append(f"{offering.id}：此准备任务没有可核验的固定期限，未生成日期或截止时刻。")
        tasks.append(DraftTask(id=f"DEMO_TASK_{uuid4().hex}", offering_id=offering.id, title=title,
                               estimated_hours=min(2.0, profile.weekly_hours), acceptance_criteria=acceptance,
                               dependencies=[], evidence_ids=sorted(set(result.evidence_ids + ([deadline_id] if deadline_id else []))),
                               hard_deadline_id=deadline_id, target_date=target_date, user_confirmed=False))
    total_hours = sum(item.estimated_hours for item in tasks)
    if total_hours > profile.weekly_hours:
        warnings.append(f"准备草案总估时 {total_hours:g} 小时超过单周可用 {profile.weekly_hours:g} 小时；需要分周或减少目标，尚未安排到周。")
    return PlanDraft(id=f"DEMO_PLAN_{uuid4().hex}", profile_version_id=profile.id, status="draft", is_synthetic=True,
                     model_mode=mode, narrative=narrative, tasks=tasks, warnings=warnings, eligibility_results=results)
