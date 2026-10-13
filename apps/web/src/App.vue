<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue'
import type { EligibilityStatus, Offering, Rule } from '../../../packages/contracts/index'
import type { DemoUser, M0Api } from './api'
import { assessmentFields, blankProfileForm, formToInput, profileToForm } from './profileForm'
import { useWorkspace } from './workspace'
import EvidenceDialog from './components/EvidenceDialog.vue'

const props = defineProps<{ api?: M0Api }>()
const workspace = useWorkspace(props.api)
const { state, profile, canCheck, canDraft } = workspace
const form = reactive(blankProfileForm())
const country = reactive({ selected: 'all' })
const visibleOfferings = computed(() => state.offerings.filter((item) => country.selected === 'all' || item.country === country.selected))
const hiddenSelectedCount = computed(() => state.selectedOfferingIds.filter(id => !visibleOfferings.value.some(item => item.id === id)).length)
const workflowSteps = [
  { id: 'profile', number: '01', label: '确认画像' },
  { id: 'catalog', number: '02', label: '选择项目' },
  { id: 'eligibility', number: '03', label: '检查资格' },
  { id: 'plan', number: '04', label: '审阅草案' },
] as const
const currentStep = computed(() => {
  if (!state.config || !profile.value || state.profileDirty) return 'profile'
  if (!state.selectedOfferingIds.length) return 'catalog'
  if (!state.results.length) return 'eligibility'
  return 'plan'
})
const workflowState = computed(() => ({
  profile: state.profileDirty ? '修改待确认保存' : profile.value ? `已保存 · v${profile.value.version}` : '待确认保存',
  catalog: state.selectedOfferingIds.length ? `${state.selectedOfferingIds.length} 个项目已选` : '待选择项目',
  eligibility: state.results.length ? `${state.results.length} 项结果可查看` : '待运行检查',
  plan: state.plan ? '草案待人工审阅' : '尚未生成草案',
}))
const nextStepHint = computed(() => {
  if (state.busy.load) return '正在读取演示资料，请等待连接结果。'
  if (state.busy.save) return '正在保存合成画像，请等待保存结果。'
  if (state.busy.check) return '正在检查所选项目，结果返回后可查看逐条依据。'
  if (state.busy.draft) return '正在生成计划草案，完成后仍需人工审阅。'
  if (!state.config) return '连接演示服务后，从合成画像开始。'
  if (currentStep.value === 'profile') return '先审阅资料并确认保存；留空表示成绩未提供，不推断数值。'
  if (currentStep.value === 'catalog') return '选择你想比较的演示项目，再查看适用条件。'
  if (currentStep.value === 'eligibility') return '运行资格检查，查看每项条件与证据。'
  return state.plan ? '查看草案任务、缺项与依据；草案仍未确认。' : '资格结果已可查看，下一步可明确生成计划草案。'
})
const statuses: Record<EligibilityStatus, { label: string; explanation: string }> = {
  eligible: { label: '满足已核查条件', explanation: '在这份合成画像与演示规则范围内满足硬条件，不代表录取。' },
  ineligible: { label: '明确不满足', explanation: '存在不满足的适用硬条件，请查看原子规则原因。' },
  conditional: { label: '有条件可后补', explanation: '仅有适用、已审核、带期限的演示后补政策支持时出现。' },
  unknown: { label: '待补充 / 待核验', explanation: '成绩或规则依据不足，当前不能确认资格。' },
}
const reviewLabels: Record<string, string> = { demo_reviewed: '演示审核通过', review_required: '待审核', conflicted: '有冲突', expired: '已过期' }
const subjectLabels: Record<string, string> = { physics: '物理', chemistry: '化学', biology: '生物', history: '历史', geography: '地理', politics: '政治' }
const subjectOptions = Object.entries(subjectLabels)
watch(profile, (value) => {
  Object.assign(form, value ? profileToForm(value) : blankProfileForm(state.config?.supported_province, state.config?.entry_year))
}, { immediate: true })
watch(() => state.config, (value) => {
  if (value && !profile.value) Object.assign(form, blankProfileForm(value.supported_province, value.entry_year))
})
onMounted(() => workspace.load())
function onFormEdit() { form.confirmed = false; workspace.markProfileEdited() }
function changeUser(event: Event) { country.selected = 'all'; void workspace.switchUser((event.target as HTMLSelectElement).value as DemoUser) }
function changeProfile(event: Event) { workspace.selectProfile((event.target as HTMLSelectElement).value) }
function toggleSubject(code: string, event: Event) {
  const current = form.subjects.split(',').filter(Boolean)
  form.subjects = ((event.target as HTMLInputElement).checked ? [...current, code] : current.filter((item) => item !== code)).join(',')
  onFormEdit()
}
function toggleOffering(id: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  workspace.selectOfferings(checked ? [...state.selectedOfferingIds, id] : state.selectedOfferingIds.filter((item) => item !== id))
}
async function save() {
  try { await workspace.saveProfile(formToInput(form)) }
  catch (error) { state.error = error instanceof Error ? error.message : '画像校验失败。' }
}
function offering(id: string): Offering | undefined { return state.offerings.find((item) => item.id === id) }
function ruleSummary(rule: Rule) {
  const key = rule.field.split('.').at(-1) ?? rule.field
  const field = assessmentFields.find((item) => item.key === key)?.label ?? (key === 'subjects' ? '选科' : key)
  const op = { gte: '至少', eq: '等于', in: '包含于', exists: '需要提供' }[rule.op]
  const value = Array.isArray(rule.value) ? rule.value.map((item) => subjectLabels[item] ?? item).join(' / ') : rule.value
  return `${field} ${op}${value === null ? '' : ` ${value}`}${rule.scale ? `（满分 ${rule.scale}，${rule.unit === 'band' ? 'band' : 'points'}）` : ''}`
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" aria-label="工作台导航">
      <a class="brand" href="#workspace"><span class="brand-mark" aria-hidden="true">路</span><span>升学路线<span class="brand-sub">ADMISSION WORKSPACE</span></span></a>
      <div class="sidebar-divider"></div>
      <p class="nav-caption">合成演示 · 本科咨询流程</p>
      <nav>
        <a href="#profile" class="nav-link" :class="{ active: currentStep === 'profile' }" :aria-current="currentStep === 'profile' ? 'step' : undefined"><span>01</span>合成学生画像</a>
        <a href="#catalog" class="nav-link" :class="{ active: currentStep === 'catalog' }" :aria-current="currentStep === 'catalog' ? 'step' : undefined"><span>02</span>项目与规则</a>
        <a href="#eligibility" class="nav-link" :class="{ active: currentStep === 'eligibility' }" :aria-current="currentStep === 'eligibility' ? 'step' : undefined"><span>03</span>资格与证据</a>
        <a href="#plan" class="nav-link" :class="{ active: currentStep === 'plan' }" :aria-current="currentStep === 'plan' ? 'step' : undefined"><span>04</span>计划草案</a>
      </nav>
      <div class="scope-note"><span class="tiny-label">当前支持范围</span><strong>普通高考本科<br />＋ 英国本科</strong><p>生源省份由服务端配置。其他省份与路径尚未支持。</p></div>
      <div class="sidebar-footer"><span class="status-dot"></span>仅用于合成数据演示<br /><span>计划草案需人工审阅</span></div>
    </aside>

    <main id="workspace" class="main-content">
      <header class="topbar">
        <div><span class="eyebrow">升学决策支持</span><h1>路线工作台</h1><p class="workspace-subtitle">把资料、项目、证据与下一步计划放在一起。</p></div>
        <div class="identity"><label for="demo-user">演示身份</label><select id="demo-user" :value="state.user" @change="changeUser"><option value="alice">DEMO Alice</option><option value="bob">DEMO Bob</option></select></div>
      </header>

      <div class="demo-banner" role="note">
        <span class="demo-badge">DEMO</span>
        <div><strong>所有学生、机构、项目与招生证据均为合成数据</strong><p>演示证据不是真实官方依据。资格结果不表示录取；计划保持未确认草案。</p></div>
        <span class="mode-badge" :class="{ live: state.config?.model_mode === 'live' }">{{ state.config ? `${state.config.model_mode} 模式` : '模式待连接' }}</span>
      </div>
      <div v-if="state.config?.model_mode === 'live'" class="notice warning" role="status">M0 live 接口已预留，但当前不可用。计划请求失败会明确显示，不会回退为 mock 内容。</div>
      <div v-if="state.error" class="notice error" role="alert"><strong>请求未完成</strong><p>{{ state.error }}</p><button v-if="!state.config" class="button secondary" :disabled="state.busy.load" @click="workspace.load">重新连接 API</button></div>
      <div v-if="state.busy.load" class="notice" role="status">正在读取演示配置、当前身份的画像与项目…</div>

      <section class="workflow-guide" aria-label="咨询流程与下一步">
        <div class="workflow-intro"><strong>从资料到计划，分四步查看</strong><p>{{ nextStepHint }}</p></div>
        <ol class="workflow-steps">
          <li v-for="step in workflowSteps" :key="step.id" :class="{ current: currentStep === step.id }">
            <a :href="`#${step.id}`" :aria-current="currentStep === step.id ? 'step' : undefined"><span class="workflow-number" aria-hidden="true">{{ step.number }}</span><span><strong>{{ step.label }}</strong><small>{{ workflowState[step.id] }}</small></span></a>
          </li>
        </ol>
      </section>

      <section class="overview-grid" aria-label="当前工作范围">
        <div class="metric-card"><span class="tiny-label">生源省份 · 配置</span><strong>{{ state.config?.supported_province ?? '待连接' }}</strong><small>仅此省份普通高考路径</small></div>
        <div class="metric-card"><span class="tiny-label">入学年度 · 项目</span><strong>{{ state.config?.entry_year ?? '—' }}</strong><small>规则按年度核验</small></div>
        <div class="metric-card"><span class="tiny-label">已选 / 可查看项目</span><strong v-if="state.config">{{ state.selectedOfferingIds.length }}<em> / {{ state.offerings.length }}</em></strong><strong v-else>待连接</strong><small>按招生机会逐个检查</small></div>
        <div class="metric-card"><span class="tiny-label">当前画像</span><strong class="profile-metric">{{ profile?.display_name ?? '尚未保存' }}</strong><small>{{ state.profileDirty ? '有未保存修改 · 需确认' : profile ? `不可变版本 ${profile.version}` : '请确认后创建' }}</small></div>
      </section>

      <section id="profile" class="panel">
        <div class="section-heading"><div><span class="eyebrow">01 · PROFILE</span><h2>先确认一份合成画像</h2><p>编辑成绩后须重新确认保存，再进行资格检查。空白成绩保持缺失。</p></div><span class="soft-badge">is_synthetic = true</span></div>
        <div class="profile-select-row"><label for="profile-select">选择已保存画像</label><select id="profile-select" :value="state.selectedProfileId" :disabled="state.busy.load || state.busy.save" @change="changeProfile"><option value="">＋ 创建合成画像</option><option v-for="item in state.profiles" :key="item.id" :value="item.id">{{ item.display_name }} · v{{ item.version }}</option></select><span class="muted">当前演示身份的数据由后端隔离</span></div>
        <form @submit.prevent="save">
          <fieldset class="profile-fieldset" :disabled="state.busy.load || state.busy.save || !state.config">
            <div class="form-grid">
              <label for="display-name">合成画像名称<input id="display-name" v-model="form.display_name" required maxlength="100" @input="onFormEdit" /></label>
              <label for="entry-year">预计入学年<input id="entry-year" v-model.number="form.entry_year" type="number" min="2026" max="2100" required @input="onFormEdit" /></label>
              <label for="province">生源省份<input id="province" :value="form.province" readonly /><small>由配置确定，不推断所在地</small></label>
              <label for="weekly-hours">每周可用时数<input id="weekly-hours" v-model="form.weekly_hours" type="number" min="0.5" max="40" step="0.5" required @input="onFormEdit" /></label>
              <fieldset class="subject-field wide-field"><legend>高考选科</legend><div class="subject-options"><label v-for="[code, label] in subjectOptions" :key="code" class="checkbox-label"><input type="checkbox" :checked="form.subjects.split(',').includes(code)" @change="toggleSubject(code, $event)" />{{ label }}</label></div></fieldset>
              <div class="profile-context"><span>本科 · 普通高考</span><span>申请身份：cn_mainland</span><span>成绩不作学历或 GPA 换算</span></div>
            </div>
            <p id="score-help" class="table-help">成绩、满分与成绩类型分别填写。窄屏可在成绩表内左右滑动，或聚焦表格后使用方向键。</p>
            <div class="score-table-wrapper" role="region" aria-label="成绩与成绩来源表格" aria-describedby="score-help" tabindex="0"><table class="score-table"><caption>成绩与来源类型 · 留空表示尚未取得或未填写</caption><thead><tr><th scope="col">评估项</th><th scope="col">成绩</th><th scope="col">满分</th><th scope="col">实得 / 预测</th></tr></thead><tbody><tr v-for="field in assessmentFields" :key="field.key"><th scope="row">{{ field.label }}<span class="score-unit">{{ field.unit }}</span></th><td><input :id="`score-${field.key}`" v-model="form.scores[field.key]!.value" :aria-label="`${field.label}成绩`" type="number" min="0" step="any" placeholder="缺失" @input="onFormEdit" /></td><td><input v-model="form.scores[field.key]!.scale" :aria-label="`${field.label}满分`" type="number" min="0.01" step="any" @input="onFormEdit" /></td><td><select v-model="form.scores[field.key]!.kind" :aria-label="`${field.label}类型`" @change="onFormEdit"><option value="achieved">实得 achieved</option><option value="predicted">预测 predicted</option></select></td></tr></tbody></table></div>
            <div class="confirmation-row"><label class="checkbox-label" for="confirm-profile"><input id="confirm-profile" v-model="form.confirmed" type="checkbox" /><span>我确认这是合成学生资料，并确认保存这份画像。</span></label><button class="button primary" type="submit" :disabled="!form.confirmed || state.busy.save">{{ state.busy.save ? '正在保存…' : '确认并保存合成画像' }}</button></div>
          </fieldset>
        </form>
        <div class="inline-note">预测成绩不会冒充实得资格。缺少成绩且没有适用、已审核、带期限的后补政策时，结果应为 unknown。</div>
      </section>

      <section id="catalog" class="panel">
        <div class="section-heading"><div><span class="eyebrow">02 · CATALOG</span><h2>选择演示招生项目</h2><p>每个项目对应具体年度与路径；门槛、期限、规则版本均读取后端。</p></div><label for="country-filter" class="compact-label">国家 / 路径<select id="country-filter" v-model="country.selected"><option value="all">全部演示路径</option><option value="CN">国内 · 普通高考</option><option value="GB">英国 · 本科</option></select></label></div>
        <div v-if="hiddenSelectedCount" class="notice compact selected-context"><strong>另有 {{ hiddenSelectedCount }} 个已选项目在当前筛选之外</strong><p>资格检查仍包含这些项目。筛选只改变显示，不会取消选择。</p><button type="button" class="button secondary" @click="country.selected = 'all'">显示全部项目</button></div>
        <div v-if="!visibleOfferings.length && !state.busy.load" class="empty-state"><strong>{{ !state.config ? '演示服务尚未连接' : state.offerings.length ? '此筛选下没有项目' : '尚未载入演示项目' }}</strong><p>{{ !state.config ? '连接演示服务后可查看当前范围的合成项目。' : state.offerings.length ? '切换国家 / 路径筛选后继续选择。' : '当前服务没有可展示的合成项目，请核对演示数据配置。' }}</p></div>
        <div class="offering-grid">
          <article v-for="item in visibleOfferings" :key="item.id" class="offering-card" :class="{ selected: state.selectedOfferingIds.includes(item.id) }">
            <div class="offering-topline"><span class="country-pill">{{ item.country === 'CN' ? '国内 · 普通高考' : '英国 · 本科' }}</span><label class="selection-label"><input type="checkbox" :checked="state.selectedOfferingIds.includes(item.id)" :aria-label="`选择 ${item.title}`" @change="toggleOffering(item.id, $event)" />选择</label></div>
            <span class="tiny-label institution">{{ item.institution_name }}</span><h3>{{ item.title }}</h3>
            <div class="offering-meta"><span>{{ item.entry_year }} 入学</span><span>{{ item.province ?? '生源范围未指定' }}</span><span>合成项目</span></div>
            <p class="deadline"><span>申请期限</span><strong>{{ item.deadline ?? '未知 · 缺少期限依据' }}</strong><button v-if="item.deadline_evidence_id" class="text-button" @click="workspace.showEvidence(item.deadline_evidence_id)">期限证据 ↗</button></p>
            <ul class="rule-list"><li v-for="rule in item.rules" :key="rule.id"><span class="rule-line">{{ ruleSummary(rule) }}</span><div class="rule-details"><span>{{ rule.stage === 'application' ? '申请阶段' : '入学阶段' }} · {{ reviewLabels[rule.review_status] }} · {{ rule.version }}</span><button class="text-button" @click="workspace.showEvidence(rule.evidence_id)">合成证据 ↗</button></div><div v-if="rule.deferral" class="deferral-note">演示后补政策期限：{{ rule.deferral.deadline }}<button class="text-button" @click="workspace.showEvidence(rule.deferral.evidence_id)">查看后补依据 ↗</button><button class="text-button" @click="workspace.showEvidence(rule.deferral.deadline_evidence_id)">查看期限依据 ↗</button></div></li></ul>
          </article>
        </div>
        <div class="action-row"><p>{{ state.profileDirty ? '画像有未保存修改，请先确认保存。' : profile ? `使用 ${profile.display_name} · v${profile.version} 检查 ${state.selectedOfferingIds.length} 个项目` : '请先确认并保存合成画像。' }}</p><button class="button primary" :disabled="!canCheck" @click="workspace.check">{{ state.busy.check ? '正在检查…' : '运行确定性资格检查 →' }}</button></div>
      </section>

      <section id="eligibility" class="panel">
        <div class="section-heading"><div><span class="eyebrow">03 · ELIGIBILITY & EVIDENCE</span><h2>资格结论与逐条依据</h2><p>四态结果由确定性规则计算。历史竞争、偏好与数据质量独立展示。</p></div><span class="soft-badge">不调用模型</span></div>
        <div class="status-legend"><span v-for="(item, key) in statuses" :key="key" class="status-chip" :class="key">{{ key }} · {{ item.label }}</span></div>
        <div v-if="!state.results.length" class="empty-state">选择已确认画像与项目后运行检查。结果不会依据缺失成绩自动推断可以后补。</div>
        <article v-for="result in state.results" :key="result.id" class="result-card">
          <div class="result-heading"><div><span class="tiny-label">{{ offering(result.offering_id)?.institution_name ?? result.offering_id }}</span><h3>{{ offering(result.offering_id)?.title ?? result.offering_id }}</h3></div><span class="status-chip" :class="result.status">{{ result.status }} · {{ statuses[result.status].label }}</span></div>
          <p class="result-explanation">{{ statuses[result.status].explanation }}</p>
          <div class="result-dimensions"><div><span class="tiny-label">已核查资格</span><strong>{{ statuses[result.status].label }}</strong><small>规则集 {{ result.ruleset_version }}</small></div><div><span class="tiny-label">历史竞争背景</span><p>{{ result.competition_context }}</p><small>M0 未实现历史竞争分析</small></div><div><span class="tiny-label">偏好匹配</span><p>{{ result.preference_fit }}</p><small>M0 未实现偏好排名</small></div><div><span class="tiny-label">数据质量</span><p v-for="quality in result.data_quality" :key="quality">{{ quality }}</p><p v-if="!result.data_quality.length">无额外质量提示 · 仅合成演示</p></div></div>
          <ul class="reason-list"><li v-for="reason in result.reasons" :key="reason.rule_id"><span class="outcome" :class="reason.outcome">{{ reason.outcome }}</span><div><p>{{ reason.message }}</p><small>规则 {{ reason.rule_id }}</small><div class="evidence-links"><button v-for="id in reason.evidence_ids" :key="id" class="text-button" @click="workspace.showEvidence(id)">{{ id }} ↗</button></div></div></li></ul>
          <div v-if="result.missing_fields.length" class="notice compact"><strong>缺失项</strong><p>{{ result.missing_fields.join(' · ') }}</p></div>
          <div v-if="result.conditions.length" class="notice warning compact"><strong>演示后补条件</strong><p v-for="condition in result.conditions" :key="condition">{{ condition }}</p></div>
          <div class="result-evidence"><span class="tiny-label">全部引用 · 合成证据</span><button v-for="id in result.evidence_ids" :key="id" class="text-button" @click="workspace.showEvidence(id)">{{ id }} ↗</button></div>
        </article>
        <div class="action-row"><p>草案生成时，服务端重新核验当前画像与选择的项目。</p><button class="button primary" :disabled="!canDraft" @click="workspace.draft">{{ state.busy.draft ? '正在生成…' : '生成未确认计划草案 →' }}</button></div>
      </section>

      <section id="plan" class="panel">
        <div class="section-heading"><div><span class="eyebrow">04 · PLAN DRAFT</span><h2>可审阅的下一步草案</h2><p>仅列准备与核验任务；估时是演示计划参数。本轮不确认、执行或排程任务。</p></div><span class="soft-badge">未确认 · draft</span></div>
        <div v-if="!state.plan" class="empty-state">完成资格检查后生成计划草案。没有依据的期限将保持未知。</div>
        <template v-else>
          <p class="plan-narrative">{{ state.plan.narrative }}</p>
          <div v-if="state.plan.warnings.length" class="notice warning"><strong>草案中的待解决项</strong><p v-for="warning in state.plan.warnings" :key="warning">{{ warning }}</p></div>
          <div class="task-list"><article v-for="(task, index) in state.plan.tasks" :key="task.id" class="task-card"><span class="task-index">{{ String(index + 1).padStart(2, '0') }}</span><div class="task-body"><div class="task-heading"><h3>{{ task.title }}</h3><span class="soft-badge">估时 {{ task.estimated_hours }} 小时</span></div><p class="muted">{{ offering(task.offering_id)?.title ?? task.offering_id }}</p><dl class="task-details"><div><dt>验收条件</dt><dd>{{ task.acceptance_criteria }}</dd></div><div><dt>前置依赖</dt><dd>{{ task.dependencies.length ? task.dependencies.join(' · ') : '无' }}</dd></div><div><dt>目标日期</dt><dd>{{ task.target_date ?? '未知 · 未安排日期' }}<span v-if="!task.hard_deadline_id"> · 无已核验固定期限</span></dd></div><div><dt>确认状态</dt><dd>待用户审阅 · 未确认</dd></div></dl><div class="evidence-links"><button v-for="id in task.evidence_ids" :key="id" class="text-button" @click="workspace.showEvidence(id)">合成证据 {{ id }} ↗</button></div></div></article></div>
          <p v-if="!state.plan.tasks.length" class="empty-state">此草案没有可列出的任务，请先处理资格结果中的缺失或不满足项。</p>
          <p class="plan-id">草案 {{ state.plan.id }} · 画像 {{ state.plan.profile_version_id }} · {{ state.plan.model_mode }} 模式 · is_synthetic = true</p>
        </template>
      </section>
      <footer class="page-footer"><span>M0 · 只展示合成数据的离线样例</span><span v-if="state.meta">数据截至 {{ state.meta.data_as_of }} · 规则集 {{ state.meta.ruleset_version }} · 请求 {{ state.meta.request_id }}</span></footer>
    </main>
    <EvidenceDialog :evidence="state.evidence" :loading="state.busy.evidence" @close="workspace.closeEvidence" />
  </div>
</template>
