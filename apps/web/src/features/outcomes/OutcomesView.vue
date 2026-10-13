<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from 'vue'
import type { DirectorySelection, DirectorySelectionEvent } from '../../../../../packages/contracts/referenceDirectory'
import { useReferenceQuery } from '../reference/query'
import SchoolProgramPicker from '../reference/directory/SchoolProgramPicker.vue'
import { validInstitution, validProgram } from '../reference/directory/client'
const form = reactive({ cohort: '', level: 'program', metric: '' })
const selection = shallowRef<DirectorySelection>({ institution: null, program: null })
const supportedLevel = computed(() => form.level === 'institution' || form.level === 'program')
const selectionContext = computed(() => JSON.stringify([form.cohort, form.level, form.metric]))
const levels = [{ key: 'program', name: '专业' }, { key: 'discipline', name: '学科汇总' }, { key: 'college', name: '学院' }, { key: 'institution', name: '学校' }]
const metrics = [{ key: 'working', name: '工作' }, { key: 'further_study', name: '升学' }, { key: 'destination_confirmed', name: '去向落实' }, { key: 'salary', name: '报告薪资' }]
const { result, loading, error, clear, run } = useReferenceQuery()
const target = computed(() => form.level === 'institution' ? selection.value.institution : form.level === 'program' ? selection.value.program : null)
const canQuery = computed(() => !loading.value && supportedLevel.value && /^[1-9][0-9]{0,3}$/.test(form.cohort) && selection.value.institution !== null && target.value !== null)
watch(form, () => { selection.value = { institution: null, program: null }; clear() }, { flush: 'sync' })
function updateSelection(value: DirectorySelectionEvent) {
  if (value.purpose !== 'outcomes' || value.context_key !== selectionContext.value) return
  clear()
  if (!supportedLevel.value || value.institution === null || !validInstitution(value.institution)) { selection.value = { institution: null, program: null }; return }
  const program = form.level === 'program' && value.program !== null && validProgram(value.program) && value.program.institution_id === value.institution.id && value.program.country === value.institution.country ? value.program : null
  selection.value = JSON.parse(JSON.stringify({ institution: value.institution, program })) as DirectorySelection
}
function submit() {
  clear()
  const institution = selection.value.institution, chosen = target.value
  if (!canQuery.value || !institution || !validInstitution(institution) || !chosen
    || (form.level === 'institution' ? !validInstitution(chosen) : !validProgram(chosen) || chosen.institution_id !== institution.id || chosen.country !== institution.country)) {
    error.value = '请填写明确毕业届，并按学校或专业层级从可信目录选择对象；学院及学科目录尚未适配。'; return
  }
  void run({ resource: 'outcomes', filters: { graduation_cohort: Number(form.cohort), requested_level: form.level, subject_ref: chosen.outcome_subject_ref, metric_kind: form.metric || null, region_key: null } })
}
</script>
<template>
  <section class="panel" aria-labelledby="outcomes-title">
    <div class="query-heading"><div><p class="section-label">人群与统计口径</p><h2 id="outcomes-title">实际毕业结果与数据局限</h2></div><span class="query-badge">资料尚未接入</span></div>
    <p class="intro">每个指标分别核对实际统计人群、毕业届、调查时间、方法、样本和分母；上级汇总不代替某专业结果。</p>
    <div class="availability-note"><strong>按学校或专业层级选择实际对象</strong><p>目录只提供已发布对象身份，不代表该毕业届结果存在。学院与学科暂无可信目录，不能用学校或专业对象代替。</p></div>
    <div class="outcomes-query">
      <p id="outcomes-query-help" class="field-help">毕业届按报告中实际毕业人群填写，不能用资料发布年或身份来源的招生年替代。当前不默认毕业届。</p>
      <form @submit.prevent="submit" aria-describedby="outcomes-query-help">
        <div class="query-fields">
          <label>毕业届<input v-model="form.cohort" maxlength="4" inputmode="numeric" required /></label>
          <label>请求层级<select v-model="form.level"><option v-for="level in levels" :key="level.key" :value="level.key" :disabled="level.key === 'college' || level.key === 'discipline'">{{ level.name }}{{ level.key === 'college' || level.key === 'discipline' ? '（对象目录未适配）' : '' }}</option></select></label>
          <label>指标<select v-model="form.metric"><option value="">全部指标</option><option v-for="metric in metrics" :key="metric.key" :value="metric.key">{{ metric.name }}</option></select></label>
        </div>
        <p class="field-help">学校级只需选学校；专业级需选学校及其专业。学院与学科查询保持不可用，不回到其他层级。</p>
        <SchoolProgramPicker purpose="outcomes" :context-key="selectionContext" :requires-program="form.level === 'program'" :disabled="!supportedLevel" @changed="updateSelection" />
        <div class="query-actions"><p>{{ target ? '已选择目录对象；毕业统计缺失仍按原范围显示。' : '请选择对应层级的目录对象。没有可信选项时查询保持禁用。' }}</p><button class="button primary" type="submit" :disabled="!canQuery">{{ loading ? '查询中…' : '查询此人群' }}</button></div>
      </form>
    </div>
    <div class="notice compact measurement-note"><strong>不同指标不能混用</strong><p>去向落实和工作或升学不是纯就业率；学校或学科薪资不是专业薪资。周期、税基或币种未知时不换算月薪/年薪，不预测个人收益。</p></div>
    <p class="screen-reader-status" role="status" aria-live="polite" aria-atomic="true">{{ loading ? '正在查询毕业结果。' : error ? '查询未完成，请查看错误说明。' : result ? '查询完成，所选人群资料存在缺口。' : '尚未查询毕业结果。' }}</p>
    <section class="query-results" aria-labelledby="outcomes-results-title" :aria-busy="loading">
      <h3 id="outcomes-results-title">查询结果</h3>
      <p v-if="error" class="notice error">{{ error }}</p>
      <p v-else-if="loading" class="empty-state">正在查询所选人群与指标，请稍候。</p>
      <div v-else-if="result" class="empty-state"><strong>此人群范围的资料未启用</strong><p>没有可核验指标或实际上级汇总；样本、回应率、分母和统计周期未知，小样本抑制数值也不会展示。不将缺失填0，不计算排名。</p></div>
      <div v-else class="empty-state"><strong>尚未查询</strong><p>填写真实毕业届并从学校或专业目录明确选择对象后查询。没有可信选项时不能提交，不提供手填对象标识。</p></div>
    </section>
  </section>
</template>
<style scoped>
.query-heading{display:flex;justify-content:space-between;align-items:center;gap:16px}.section-label{font-size:12px;font-weight:650;color:var(--primary);margin-bottom:8px}.query-badge{border:1px solid var(--border);border-radius:999px;padding:7px 12px;font-size:12px;color:var(--muted);white-space:nowrap}.intro{margin:14px 0 22px;color:var(--muted);font-size:15px}.availability-note{padding:20px;border:1px solid var(--border);border-left:3px solid var(--primary);border-radius:10px;background:var(--surface,#f4f8f5)}.availability-note strong{font-size:15px;color:var(--ink)}.availability-note p{margin-top:8px;font-size:14px;color:var(--muted)}.advanced-query{margin-top:22px;padding:18px 20px;border:1px solid var(--border);border-radius:10px}.advanced-query summary{cursor:pointer;min-height:44px;line-height:1.8;color:var(--ink);font-size:14px;font-weight:600}.advanced-query summary span{font-size:12px;font-weight:400;color:var(--muted);margin-left:12px}.field-help{margin-top:12px;font-size:12px;color:var(--muted);line-height:1.8}.query-fields{display:grid;gap:18px;margin-top:18px;grid-template-columns:repeat(2,minmax(0,1fr))}label{display:flex;flex-direction:column;gap:9px;font-size:14px;font-weight:600;color:var(--ink)}.query-actions{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-top:22px}.query-actions p{font-size:12px;color:var(--muted)}button{min-height:44px;min-width:160px}.measurement-note{margin-top:22px}.measurement-note strong{font-size:13px}.query-results{border-top:1px solid var(--border);padding-top:24px;margin-top:24px}.query-results>h3{margin-bottom:16px}.empty-state{text-align:left}.empty-state strong{color:var(--ink);font-size:15px}.empty-state p{margin-top:10px}.screen-reader-status{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:560px){.query-heading{align-items:flex-start;flex-direction:column;gap:12px}.query-fields{grid-template-columns:1fr}.advanced-query{padding:16px}.query-actions{align-items:stretch;flex-direction:column;gap:12px}.query-actions button{width:100%}.availability-note{padding:17px}}
.outcomes-query{margin-top:22px}.outcomes-query .query-fields{grid-template-columns:repeat(3,minmax(0,1fr))}@media(max-width:720px){.outcomes-query .query-fields{grid-template-columns:1fr}}
</style>
