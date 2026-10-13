<script setup lang="ts">
import type { ExecutionData } from '../../../../../packages/contracts/v2/plans/generated'
import { conflictLabels,statusLabels } from './presentation'
import { localTime,microHours } from './form'
defineProps<{execution:ExecutionData}>()
</script>
<template>
 <section class="schedule" aria-label="服务端安排方案" data-testid="plan-schedule-result"><template v-if="execution.proposal.schedule"><h4>{{ statusLabels[execution.proposal.schedule.status] }}</h4><p class="boundary">官方截止仍未核验 · constraints_complete=false。容量可安排不等于资格或官方期限已经确认。</p>
  <ul class="conflicts"><li v-for="(c,i) in execution.proposal.schedule.conflicts" :key="i">{{ conflictLabels[c.code] }}<small v-if="c.task_key"> · 任务 {{ c.task_key }}</small></li></ul>
  <div class="weeks"><p v-for="week in execution.proposal.schedule.weeks" :key="week.week_start">当地 ISO 周 {{ week.week_start }}：{{ microHours(week.assigned_microseconds) }} 小时 / {{ week.capacity_microseconds===null?'未知容量':microHours(week.capacity_microseconds)+' 小时容量' }}</p></div>
  <ol><li v-for="allocation in execution.proposal.schedule.allocations" :key="`${allocation.task_key}:${allocation.start_at}`"><strong>{{ execution.proposal.effective_draft.tasks.find(t=>t.task_key===allocation.task_key)?.title }}</strong><p>{{ allocation.start_at }} → {{ allocation.end_at }} · {{ microHours(allocation.duration_microseconds) }} 小时</p><p>{{ localTime(allocation.start_at,execution.proposal.schedule.display_timezone) }}</p></li></ol>
  <p>可选调整：{{ execution.proposal.schedule.options.map(v=>({EDIT_AVAILABILITY:'核对可用时间',EDIT_ESTIMATES:'核对估时',EDIT_HORIZON:'核对区间',REDUCE_GOALS:'减少目标',VERIFY_DEADLINES:'核验期限'}[v])).join('、')||'无' }}</p>
 </template><p v-else>尚未生成容量方案。未知工时不会自动补为 0。</p>
 <details class="sources" open><summary>原评估来源快照 · 不代替当前资格</summary><dl v-for="r in execution.proposal.effective_draft.assessment_refs" :key="r.assessment_id"><div><dt>项目 / 版本</dt><dd>{{ r.target.offering_id }} / {{ r.target.offering_version }}</dd></div><div><dt>机构 / 专业</dt><dd>{{ r.target.institution_id }} / {{ r.target.program_id }}</dd></div><div><dt>原结论 / 有效性</dt><dd>{{ r.eligibility_status }} / {{ r.current_validity }} · {{ r.stage }}</dd></div><div><dt>原发布</dt><dd>{{ r.release_id }}</dd></div><div><dt>要求 / 规则版本</dt><dd>{{ r.requirements_version }} / {{ r.ruleset_version??'规则未知' }}</dd></div><div><dt>完整范围 SHA</dt><dd>{{ r.target.scope_sha256 }}</dd></div><div><dt>入学年度</dt><dd>此来源引用未提供年度；须核对其绑定的本人确认画像与项目资料。</dd></div></dl></details>
 <details v-if="execution.proposal.effective_draft.deadline_refs.length"><summary>原申请与补交期限引用（分别保留）</summary><div v-for="r in execution.proposal.effective_draft.deadline_refs" :key="r.deadline_key"><p>{{ r.purpose==='application'?'主申请':'补交' }} · {{ r.assessment_key }} · 状态 {{ r.status }}</p><template v-if="r.date_event"><p>原文：{{ r.date_event.original_text }}</p><p>精度 {{ r.date_event.precision }} · 原日期 {{ r.date_event.local_date??'未知' }} · 原时间 {{ r.date_event.local_time??'未知' }} · 时区 {{ r.date_event.timezone??'未知' }}</p><p>计算候选 UTC {{ r.date_event.calculated_utc_instant??'未知' }} · 官方 UTC 未知</p></template><p v-else>没有可展示的日期快照；不造截止时间。</p></div></details>
 </section>
</template>
<style scoped>
.schedule{padding:19px;background:#f6f8f1;border:1px solid #dce6d3;border-radius:8px;margin:20px 0;min-width:0}h4{font-size:14px;margin:0 0 12px}p,li,summary{font-size:11px;line-height:1.9;color:#718269;overflow-wrap:anywhere}.boundary{color:#8b733e}.conflicts{padding-left:17px}.weeks{border-top:1px solid #dce5d3}.schedule ol{padding-left:18px}.schedule small{font-size:9px}details{border-top:1px solid #dce5d3;margin-top:17px;padding-top:15px}summary{cursor:pointer}.sources dl{font-size:10px;line-height:1.9;border-bottom:1px solid #e2e7da;padding-bottom:13px}.sources dl>div{display:grid;grid-template-columns:105px minmax(0,1fr);gap:10px}.sources dt{color:#8c987d}.sources dd{margin:0;overflow-wrap:anywhere}@media(max-width:650px){.sources dl>div{grid-template-columns:1fr;gap:2px}}
</style>
