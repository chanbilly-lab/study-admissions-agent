<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from 'vue'
import type { DirectorySelection, DirectorySelectionEvent } from '../../../../../packages/contracts/referenceDirectory'
import { useReferenceQuery } from '../reference/query'
import SchoolProgramPicker from '../reference/directory/SchoolProgramPicker.vue'
import { validInstitution, validProgram } from '../reference/directory/client'
const form = reactive({ cohort: '2026', teaching: '' })
const selection = shallowRef<DirectorySelection>({ institution: null, program: null })
const selectionContext = computed(() => JSON.stringify([form.cohort, form.teaching]))
const { result, loading, error, clear, run } = useReferenceQuery()
const canQuery = computed(() => !loading.value && /^[1-9][0-9]{0,3}$/.test(form.cohort)
  && (form.teaching === '' || /^[1-9][0-9]{0,3}$/.test(form.teaching)) && selection.value.institution !== null && selection.value.program !== null)
watch(form, () => { selection.value = { institution: null, program: null }; clear() }, { flush: 'sync' })
function updateSelection(value: DirectorySelectionEvent) {
  if (value.purpose !== 'curricula' || value.context_key !== selectionContext.value) return
  clear()
  if (value.institution === null || !validInstitution(value.institution)) { selection.value = { institution: null, program: null }; return }
  const program = value.program !== null && validProgram(value.program) && value.program.institution_id === value.institution.id && value.program.country === value.institution.country ? value.program : null
  selection.value = JSON.parse(JSON.stringify({ institution: value.institution, program })) as DirectorySelection
}
function submit() {
  clear()
  const { institution, program } = selection.value
  if (!canQuery.value || !institution || !program || !validInstitution(institution) || !validProgram(program) || program.institution_id !== institution.id || program.country !== institution.country) {
    error.value = '请填写明确入学届，并从可信目录选择学校及其专业；目录缺失时不能提交查询。'; return
  }
  void run({ resource: 'curricula', filters: { program_id: program.id, entry_cohort: Number(form.cohort), teaching_year: form.teaching ? Number(form.teaching) : null, region_key: null } })
}
</script>
<template>
  <section class="panel" aria-labelledby="curricula-title">
    <div class="query-heading"><div><p class="section-label">课程与版本</p><h2 id="curricula-title">按入学届查询培养方案</h2></div><span class="query-badge">资料尚未接入</span></div>
    <p class="intro">入学届、教学年和版本独立。没有当届方案时，不自动套用旧届；未来课程需标暂定，歧义学分保持未知。</p>
    <div class="availability-note"><strong>先选择资料届，再搜索学校与专业</strong><p>选项只能来自可信的已发布身份目录。目录未启用或没有匹配时不能查询；选择身份也不代表当届培养方案存在。</p></div>
    <div class="curricula-query">
      <p id="curricula-query-help" class="field-help">入学届与教学年分别填写；身份来源的招生年仅供核对，不会替换这里的资料届。</p>
      <form @submit.prevent="submit" aria-describedby="curricula-query-help">
        <div class="query-fields"><label>入学届<input v-model="form.cohort" maxlength="4" inputmode="numeric" required /></label><label>教学年（可选）<input v-model="form.teaching" maxlength="4" inputmode="numeric" /></label></div>
        <SchoolProgramPicker purpose="curricula" :context-key="selectionContext" @changed="updateSelection" />
        <div class="query-actions"><p>{{ selection.program ? '已选择目录专业；当届资料是否存在以查询结果为准。' : '请先完成学校与专业选择。没有目录选项时查询保持禁用。' }}</p><button class="button primary" type="submit" :disabled="!canQuery">{{ loading ? '查询中…' : '查询当届方案' }}</button></div>
      </form>
    </div>
    <p class="screen-reader-status" role="status" aria-live="polite" aria-atomic="true">{{ loading ? '正在查询培养资料。' : error ? '查询未完成，请查看错误说明。' : result ? '查询完成，当届培养资料存在缺口。' : '尚未查询培养资料。' }}</p>
    <section class="query-results" aria-labelledby="curricula-results-title" :aria-busy="loading">
      <h3 id="curricula-results-title">查询结果</h3>
      <p v-if="error" class="notice error">{{ error }}</p>
      <p v-else-if="loading" class="empty-state">正在查询所选项目与入学届，请稍候。</p>
      <div v-else-if="result" class="empty-state"><strong>当届培养资料未启用</strong><p>没有可显示的培养版本、学位、课程、学分或证据。未知不填0，也不回旧届；培养方向不能当就业统计。</p></div>
      <div v-else class="empty-state"><strong>尚未查询</strong><p>请明确搜索并选择学校及专业后查询。当目录没有可选项时，不提供手填标识或虚构的学校专业选项。</p></div>
    </section>
  </section>
</template>
<style scoped>
.query-heading{display:flex;justify-content:space-between;align-items:center;gap:16px}.section-label{font-size:12px;font-weight:650;color:var(--primary);margin-bottom:8px}.query-badge{border:1px solid var(--border);border-radius:999px;padding:7px 12px;font-size:12px;color:var(--muted);white-space:nowrap}.intro{margin:14px 0 22px;color:var(--muted);font-size:15px}.availability-note{padding:20px;border:1px solid var(--border);border-left:3px solid var(--primary);border-radius:10px;background:var(--surface,#f4f8f5)}.availability-note strong{font-size:15px;color:var(--ink)}.availability-note p{margin-top:8px;font-size:14px;color:var(--muted)}.advanced-query{margin-top:22px;padding:18px 20px;border:1px solid var(--border);border-radius:10px}.advanced-query summary{cursor:pointer;min-height:44px;line-height:1.8;color:var(--ink);font-size:14px;font-weight:600}.advanced-query summary span{font-size:12px;font-weight:400;color:var(--muted);margin-left:12px}.field-help{margin-top:12px;font-size:12px;color:var(--muted);line-height:1.8}.query-fields{display:grid;gap:18px;margin-top:18px;grid-template-columns:minmax(240px,1.5fr) repeat(2,minmax(120px,1fr))}label{display:flex;flex-direction:column;gap:9px;font-size:14px;font-weight:600;color:var(--ink)}.identifier-field input{font-family:ui-monospace,monospace;font-size:14px}.query-actions{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-top:22px}.query-actions p{font-size:12px;color:var(--muted)}button{min-height:44px;min-width:160px}.query-results{border-top:1px solid var(--border);padding-top:24px;margin-top:24px}.query-results>h3{margin-bottom:16px}.empty-state{text-align:left}.empty-state strong{color:var(--ink);font-size:15px}.empty-state p{margin-top:10px}.screen-reader-status{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:800px){.query-fields{grid-template-columns:repeat(2,minmax(0,1fr))}.identifier-field{grid-column:1/-1}}@media(max-width:560px){.query-heading{align-items:flex-start;flex-direction:column;gap:12px}.query-fields{grid-template-columns:1fr}.advanced-query{padding:16px}.query-actions{align-items:stretch;flex-direction:column;gap:12px}.query-actions button{width:100%}.availability-note{padding:17px}}
.curricula-query{margin-top:22px}.curricula-query .query-fields{grid-template-columns:repeat(2,minmax(0,1fr))}@media(max-width:560px){.curricula-query .query-fields{grid-template-columns:1fr}}
</style>
