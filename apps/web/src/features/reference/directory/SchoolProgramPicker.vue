<script setup lang="ts">
import { watch } from 'vue'
import type { DirectorySelectionEvent } from '../../../../../../packages/contracts/referenceDirectory'
import { useDirectorySelection } from './useDirectorySelection'
import type { DirectoryPurpose } from './useDirectorySelection'

const props = withDefaults(defineProps<{ purpose: DirectoryPurpose; contextKey: string; requiresProgram?: boolean; disabled?: boolean }>(), { requiresProgram: true, disabled: false })
const emit = defineEmits<{ changed: [selection: DirectorySelectionEvent] }>()
const directory = useDirectorySelection(selection => emit('changed', selection))
const { state, institutionBusy, programBusy } = directory
watch(() => [props.purpose, props.contextKey, props.requiresProgram, props.disabled] as const,
  ([purpose, contextKey, requiresProgram, disabled]) => directory.setContext(purpose, contextKey, requiresProgram, disabled), { flush: 'sync', immediate: true })
function searchKey(event: KeyboardEvent, resource: 'institutions' | 'programs') {
  if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  if (resource === 'institutions') void directory.searchInstitutions()
  else void directory.searchPrograms()
}
</script>

<template>
  <section class="directory-picker" :aria-labelledby="purpose + '-directory-title'">
    <div class="picker-heading"><div><p class="picker-label">从可信目录选择</p><h3 :id="purpose + '-directory-title'">{{ requiresProgram ? '学校 → 专业' : '选择学校' }}</h3></div><span class="picker-mode">不会自动搜索或选择</span></div>
    <p class="picker-help">搜索已发布的身份记录，可留空关键词浏览。目录缺失时没有可选项，不能根据名称猜标识。</p>
    <fieldset :disabled="disabled">
      <legend>学校搜索与选择</legend>
      <div class="institution-search">
        <label>机构国家<select :value="state.country" @change="directory.setCountry(($event.target as HTMLSelectElement).value)"><option value="">不限定</option><option value="CN">中国大陆（CN）</option><option value="GB">英国（GB）</option></select></label>
        <label>学校关键词<input :value="state.institutionQuery" maxlength="100" autocomplete="off" @input="directory.setInstitutionQuery(($event.target as HTMLInputElement).value)" @keydown="searchKey($event, 'institutions')" /></label>
        <button class="button secondary" type="button" :disabled="institutionBusy" @click="directory.searchInstitutions()">{{ institutionBusy ? '搜索中…' : '搜索学校' }}</button>
      </div>
      <p class="directory-status" :class="{ error: state.institutionStatus === 'error' }" role="status" aria-live="polite" aria-atomic="true">{{ institutionBusy ? '正在搜索学校目录。' : state.institutionMessage || '尚未搜索学校。请点击“搜索学校”，不会用演示或研究候选填充目录。' }}</p>
      <label>选择学校<select :value="state.institution?.id ?? ''" :disabled="institutionBusy || !state.institutions?.directory_available || !state.institutions.items.length" @change="directory.selectInstitution(($event.target as HTMLSelectElement).value)">
        <option value="">请选择本页搜索结果中的学校</option><option v-for="item in state.institutions?.items ?? []" :key="item.id" :value="item.id">{{ item.name }} · {{ item.country }} · 身份依据{{ item.proof.identity_evidence_entry_year }} · 标识尾部{{ item.id.slice(-8) }}</option>
      </select></label>
      <button v-if="state.institutions?.page.has_more" class="button secondary next-page" type="button" :disabled="institutionBusy" @click="directory.nextInstitutions()">下一页学校</button>
    </fieldset>
    <fieldset v-if="requiresProgram" :disabled="disabled || !state.institution">
      <legend>所选学校的专业</legend>
      <p v-if="!state.institution" class="picker-help">先明确选择一所学校，再搜索该校专业。</p>
      <div class="program-search"><label>专业关键词<input :value="state.programQuery" maxlength="100" autocomplete="off" @input="directory.setProgramQuery(($event.target as HTMLInputElement).value)" @keydown="searchKey($event, 'programs')" /></label><button class="button secondary" type="button" :disabled="programBusy" @click="directory.searchPrograms()">{{ programBusy ? '搜索中…' : '搜索该校专业' }}</button></div>
      <p class="directory-status" :class="{ error: state.programStatus === 'error' }" role="status" aria-live="polite" aria-atomic="true">{{ programBusy ? '正在搜索所选学校的专业。' : state.programMessage || '尚未搜索专业。没有自动选择首项或根据学校名称推定专业。' }}</p>
      <label>选择专业<select :value="state.program?.id ?? ''" :disabled="programBusy || !state.programs?.directory_available || !state.programs.items.length" @change="directory.selectProgram(($event.target as HTMLSelectElement).value)">
        <option value="">请选择本页搜索结果中的专业</option><option v-for="item in state.programs?.items ?? []" :key="item.id" :value="item.id">{{ item.name }} · 身份依据{{ item.proof.identity_evidence_entry_year }} · 标识尾部{{ item.id.slice(-8) }}</option>
      </select></label>
      <button v-if="state.programs?.page.has_more" class="button secondary next-page" type="button" :disabled="programBusy" @click="directory.nextPrograms()">下一页专业</button>
    </fieldset>
    <div v-if="state.institution" class="selected-identity">
      <strong>已选择：{{ state.institution.name }}<template v-if="state.program"> → {{ state.program.name }}</template></strong>
      <p>学校身份来源招生年：{{ state.institution.proof.identity_evidence_entry_year }}<template v-if="state.program">；专业身份来源招生年：{{ state.program.proof.identity_evidence_entry_year }}</template>。仅证明对象身份，不代表本次入学届、毕业届资料或资格已齐全。</p>
      <details class="identity-proof"><summary>查看所选对象的身份来源标识</summary><dl>
        <div><dt>学校目录标识</dt><dd>{{ state.institution.id }}</dd></div><div><dt>学校来源发布/项目版本</dt><dd>{{ state.institution.proof.release_id }}<br />{{ state.institution.proof.offering_id }} · {{ state.institution.proof.offering_version }}</dd></div><div><dt>学校来源要求摘要</dt><dd>{{ state.institution.proof.requirements_version }}</dd></div>
        <template v-if="state.program"><div><dt>专业目录标识</dt><dd>{{ state.program.id }}</dd></div><div><dt>专业来源发布/项目版本</dt><dd>{{ state.program.proof.release_id }}<br />{{ state.program.proof.offering_id }} · {{ state.program.proof.offering_version }}</dd></div><div><dt>专业来源要求摘要</dt><dd>{{ state.program.proof.requirements_version }}</dd></div></template>
      </dl></details>
    </div>
    <p class="picker-help">更改关键词、国家、学校或上方资料条件会清除相关选择及旧资料结果。下一页显示新的选项页，需要明确重新选择；同名记录不自动合并，请核对所选课程身份。</p>
  </section>
</template>

<style scoped>
.directory-picker{padding:22px;border:1px solid var(--border);border-radius:12px;background:var(--surface,#f4f8f5);margin:22px 0}.picker-heading{display:flex;justify-content:space-between;align-items:center;gap:18px}.picker-label{font-size:12px;font-weight:600;color:var(--primary);margin-bottom:6px}.picker-mode{font-size:12px;color:var(--muted);white-space:nowrap}.picker-help{font-size:12px;line-height:1.8;color:var(--muted);margin-top:12px}fieldset{min-width:0;border:0;border-top:1px solid var(--border);margin:20px 0 0;padding:20px 0 0}legend{padding:0 10px 0 0;font-size:14px;font-weight:600;color:var(--ink)}.institution-search{display:grid;grid-template-columns:minmax(130px,.8fr) minmax(200px,1.5fr) auto;gap:16px;align-items:end}.program-search{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:end}label{display:flex;flex-direction:column;gap:9px;font-size:14px;font-weight:600;color:var(--ink);min-width:0}input,select{min-height:44px;min-width:0}button{min-height:44px}.directory-status{font-size:13px;line-height:1.8;margin:14px 0;color:var(--muted)}.directory-status.error{color:#8d5544}.next-page{margin-top:14px}.selected-identity{padding:18px;margin-top:22px;border:1px solid var(--border);border-radius:10px;background:var(--paper)}.selected-identity>strong{font-size:14px;color:var(--ink)}.selected-identity>p{font-size:12px;color:var(--muted);line-height:1.8;margin-top:9px}.identity-proof{margin-top:14px;border-top:1px solid var(--border);padding-top:12px}.identity-proof summary{min-height:44px;cursor:pointer;font-size:13px;color:var(--primary);font-weight:600;line-height:1.8}.identity-proof dl{display:grid;gap:12px;margin:12px 0 0}.identity-proof dl>div{display:grid;grid-template-columns:180px minmax(0,1fr);gap:14px}.identity-proof dt{font-size:12px;color:var(--muted)}.identity-proof dd{font-size:12px;line-height:1.8;margin:0;overflow-wrap:anywhere}@media(max-width:720px){.institution-search{grid-template-columns:repeat(2,minmax(0,1fr))}.institution-search button{grid-column:1/-1}.program-search{grid-template-columns:1fr}.directory-picker{padding:18px}.picker-heading{align-items:flex-start;flex-direction:column;gap:10px}.identity-proof dl>div{grid-template-columns:1fr;gap:5px}}@media(max-width:460px){.institution-search{grid-template-columns:1fr}.directory-picker{padding:16px}}
</style>
