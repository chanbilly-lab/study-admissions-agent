<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import type { SessionData } from '../features/auth/client'
import type { ProfileVersionData } from '../../../../packages/contracts/v2/profiles/generated'
import type { CatalogApi } from '../features/catalog/client'
import type { EligibilityApi } from '../features/eligibility/client'
import type { AssessmentData } from '../../../../packages/contracts/v2/assessments/generated'
import { offeringKey } from '../features/catalog/client'
import { scopeFingerprint } from '../features/catalog/validation'
import { useAdmissionsWorkspace } from '../features/catalog/useAdmissionsWorkspace'
import CatalogFilters from '../features/catalog/CatalogFilters.vue'
import OfferingCard from '../features/catalog/OfferingCard.vue'
import AssessmentResult from '../features/eligibility/AssessmentResult.vue'
import PublicEvidenceDialog from '../features/evidence/PublicEvidenceDialog.vue'
import { scopeLabels, scopeText } from '../features/catalog/presentation'
import { bindProfile } from '../features/eligibility/validation'
import QAPanel from '../features/qa/QAPanel.vue'
import type { QAApi } from '../features/qa/client'
const props = defineProps<{ actor: SessionData | null; coreAllowed: boolean; profile: ProfileVersionData | null; profileEpoch: number; catalogApi?: CatalogApi; eligibilityApi?: EligibilityApi; qaApi?: QAApi }>()
const emit = defineEmits<{ sessionExpired: []; planAssessment: [result: AssessmentData] }>()
const workspace = useAdmissionsWorkspace({ catalogApi: props.catalogApi, eligibilityApi: props.eligibilityApi }, () => emit('sessionExpired'))
const { state } = workspace
const selected = computed(workspace.selectedOffering), compared = computed(workspace.compareItems)
const scopeFields = ['intake','application_cycle','channel','exam_system','subject_scope','batch_group'] as const
watch(() => [props.actor, props.coreAllowed] as const, ([actor, allowed]) => { void workspace.setAccess(actor, allowed) }, { immediate: true, flush: 'sync' })
watch(() => [props.profile, props.profileEpoch] as const, ([profile, epoch]) => workspace.setProfile(profile, epoch), { immediate: true, flush: 'sync' })
onMounted(() => { void workspace.loadConfig() })
onUnmounted(workspace.dispose)
function checked(event: Event) { return (event.target as HTMLInputElement).checked }
function scopeChanged(field: typeof scopeFields[number], event: Event) { workspace.setScope(field, (event.target as HTMLSelectElement).value === 'target' && selected.value ? selected.value.scope[field] : null) }
function historyChanged(event: Event) { workspace.setAssessmentId((event.target as HTMLInputElement).value) }
function canAddToPlan(result: AssessmentData) { return !!props.actor && props.coreAllowed && !!props.profile && !state.privateBusy && bindProfile(result, props.profile) }
function openEvidence(item: NonNullable<typeof selected.value>, id: string) { if (state.selectedKey !== offeringKey(item)) workspace.selectOffering(offeringKey(item)); void workspace.openEvidence(id) }
async function openResultEvidence(result: AssessmentData, id: string) {
  workspace.closeEvidence()
  const item = selected.value
  const displayed = () => state.result === result || state.history === result
  if (!displayed()) return
  if (!item || result.current_validity !== 'current' || result.release_id !== item.release_id || result.requirements_version !== item.requirements_version || result.target.offering_id !== item.id || result.target.offering_version !== item.version || result.target.dataset_id !== item.scope.dataset_id || result.target.institution_id !== item.institution_id || result.target.program_id !== item.program_id || result.target.country !== item.scope.country) {
    state.evidenceMessage = '原评估与当前所选发布或项目范围不一致，不能借用新发布读取历史证据。'; return
  }
  try {
    const fingerprint = await scopeFingerprint(item.scope)
    if (!displayed() || selected.value !== item || !props.actor || !props.coreAllowed) return
    if (fingerprint !== result.target.scope_sha256) { state.evidenceMessage = '原评估的完整适用范围指纹不一致，证据不可读取。'; return }
    await workspace.openEvidence(id)
  } catch { if (displayed()) state.evidenceMessage = '原评估的证据绑定未通过核验。' }
}
</script>
<template>
  <section class="catalog-workspace" data-testid="catalog-workspace" aria-labelledby="catalog-title">
    <header class="workspace-heading"><div><p class="kicker">PROGRAMMES · QUALIFICATION · EVIDENCE</p><h2 id="catalog-title">先看项目，再核对适用依据。</h2><p>公开资料查询与本人资格评估分别验证。比较不会计算录取概率、学校排名或自动形成申请。</p></div><span class="public-tag">匿名公共读取</span></header>
    <div class="boundary"><strong>真实规则覆盖与资料处理仍未开放</strong><p>只有当前已发布资料可展示。缺少适用规则、当前审核证明或后补期限时，资格保持未知；不以历史数字或合成资料填补。</p></div>
    <p v-if="state.config?.demo_banner" class="demo" data-testid="catalog-demo-banner"><strong>{{ state.config.demo_banner }}</strong></p>
    <p v-if="state.config && !state.config.business_available" class="message" role="status">公共目录未开放或未配置读取服务。可以核对查询范围，服务不可用时不会回退到 M0。</p>
    <CatalogFilters :query="state.query" :busy="state.publicStatus === 'loading'" :synthetic="!!state.config?.allow_test_fixture_read" @changed="workspace.setFilters" @search="workspace.search" />
    <p v-if="state.publicMessage" class="message" :class="{error:state.publicError !== null}" :role="state.publicError !== null ? 'alert' : 'status'" data-testid="catalog-message">{{ state.publicMessage }}</p>
    <button v-if="state.publicError === 409" type="button" class="secondary" data-testid="catalog-restart" @click="workspace.search">明确重新读取第一页</button>
    <section v-if="state.page" class="catalog-results" aria-labelledby="catalog-results-title">
      <div class="results-heading"><h3 id="catalog-results-title">已发布项目</h3><p data-testid="catalog-coverage">{{ state.page.coverage.status === 'no_published_records' ? '当前查询范围没有可公开记录' : '部分公开资料，完整范围仍未知' }} · 本页 {{ state.page.coverage.returned_count }} 条 · 总量与覆盖率未知</p></div>
      <p v-if="!state.page.items.length && state.page.coverage.status === 'partial'" class="note">此页已结束；不代表整个查询范围没有资料。</p>
      <div class="offering-grid"><OfferingCard v-for="item in state.page.items" :key="offeringKey(item)" :offering="item" :selected="state.selectedKey === offeringKey(item)" :compared="state.compareKeys.includes(offeringKey(item))" :compare-disabled="state.compareKeys.length >= 4" @select="workspace.selectOffering(offeringKey(item))" @compare="workspace.toggleCompare(offeringKey(item))" @evidence="openEvidence(item,$event)" /></div>
      <button v-if="state.page.page.has_more" type="button" class="secondary next" data-testid="catalog-next" :disabled="state.publicStatus === 'loading'" @click="workspace.nextPage">读取下一页</button>
    </section>
    <section v-if="compared.length" class="comparison" aria-labelledby="comparison-title" data-testid="catalog-comparison"><div class="results-heading"><h3 id="comparison-title">逐项比较 · {{ compared.length }} / 4</h3><p>每张卡片保留准确年度、发布和项目版本；不合并门槛、典型条件与历史统计。</p></div><div class="comparison-grid"><div v-for="item in compared" :key="offeringKey(item)" class="compare-item"><OfferingCard :offering="item" compact @evidence="openEvidence(item,$event)" /><button type="button" class="secondary" :data-testid="`catalog-uncompare-${item.id}-${item.version}`" @click="workspace.toggleCompare(offeringKey(item))">移除此比较项目</button></div></div></section>
    <QAPanel :target="selected" :api="qaApi" />
    <section class="private-check" aria-labelledby="private-check-title" :aria-busy="!!state.privateBusy">
      <div class="results-heading"><h3 id="private-check-title">本人资格检查</h3><button type="button" class="secondary" data-testid="catalog-context-refresh" :disabled="!actor || !coreAllowed || !!state.privateBusy" @click="workspace.refreshContext">重新检查评估入口</button></div>
      <p v-if="!actor" class="note">尚未登录。公开项目可浏览；不读取画像、历史评估或学生成绩。</p><p v-else-if="!coreAllowed" class="note">核心用途尚未有效确认或正在变化；私人评估、历史与确认状态已清空。</p><p v-else-if="!state.context" class="note">评估入口尚未取得当前服务端授权，不能通过客户端角色打开。</p>
      <p v-if="state.privateMessage" class="message" :class="{error:state.privateError !== null}" :role="state.privateError !== null ? 'alert' : 'status'" data-testid="assessment-message">{{ state.privateMessage }}</p>
      <template v-if="actor && coreAllowed && state.context">
        <p v-if="state.context.is_synthetic" class="demo"><strong>DEMO · 当前本人合成评估入口</strong>，正式招生规则缺失时仍为 unknown。</p>
        <p class="note">服务端能力：检查 {{ state.context.can_evaluate ? '可操作' : '关闭' }} / 历史读取 {{ state.context.can_read ? '可操作' : '关闭' }} / 重放 {{ state.context.can_replay ? '可操作' : '关闭' }}；每次请求仍即时核验。</p>
        <p v-if="!profile" class="message">请在上方明确读取本人当前确认版。编辑、未确认草稿或版本冲突时，不使用旧确认版检查。</p>
        <p v-if="!selected" class="note">请选择一个准确项目版本作为目标。</p>
        <div v-if="profile && selected" class="binding" data-testid="assessment-binding"><h4>本次明确核对的对象</h4><dl><div><dt>本人确认版</dt><dd>第 {{ profile.version }} 版 · {{ profile.version_id }} · 入学 {{ profile.profile.entry_year }} 年</dd></div><div><dt>准确目标</dt><dd>{{ selected.institution_name }} / {{ selected.program_name }} · {{ selected.entry_year }} 年 · 项目 v{{ selected.version }}</dd></div><div><dt>发布版本</dt><dd>{{ selected.release_id }} / {{ selected.release_version }}</dd></div></dl><p v-if="profile.profile.entry_year !== selected.entry_year" role="alert" class="message error">画像入学年与目标不一致；请核对当前画像与查询年度。</p><p v-if="!['CN','GB'].includes(selected.scope.country)" class="message">此地域可查询资料，个性化适配尚未开放，不套用普通高考规则。</p>
          <label class="stage">本次阶段<select :value="state.stage" data-testid="catalog-stage" :disabled="!!state.privateBusy" @change="workspace.setStage(($event.target as HTMLSelectElement).value as 'application' | 'enrollment')"><option value="application">申请阶段</option><option value="enrollment">入学阶段</option></select></label>
          <fieldset class="scope-confirmation"><legend>明确附加适用范围</legend><p>原目标未知保持未知；选择“不提供”发送 null，不推断省份、身份、周期或期限。</p><label v-for="field in scopeFields" :key="field">{{ scopeLabels[field] }}<select :value="state.scope[field] === null ? 'none' : 'target'" :data-testid="`catalog-scope-${field}`" :disabled="!!state.privateBusy" @change="scopeChanged(field,$event)"><option value="target">使用目标声明：{{ scopeText(selected.scope[field]) }}</option><option value="none">不提供（null）</option></select></label></fieldset>
          <label class="confirmation"><input type="checkbox" :checked="state.confirmed" data-testid="catalog-confirm" :disabled="!!state.privateBusy || !state.context.can_evaluate" @change="workspace.setConfirmed(checked($event))"><span>我已核对当前本人确认版、项目、发布、阶段及上列范围，明确请求本次资格检查。</span></label><button type="button" class="primary" data-testid="catalog-evaluate" :disabled="!workspace.canEvaluate() || !state.confirmed || profile.profile.entry_year !== selected.entry_year" @click="workspace.evaluateSelected">{{ state.privateBusy ? '正在核查…' : '检查此项目资格' }}</button>
        </div>
        <div v-if="state.result" data-testid="assessment-current-result"><AssessmentResult :result="state.result" @evidence="openResultEvidence(state.result,$event)" /><button type="button" class="secondary" data-testid="plan-assessment-add" :disabled="!canAddToPlan(state.result)" @click="emit('planAssessment',state.result)">加入准备目标{{ state.result.current_validity !== 'current' || state.result.eligibility.status === 'unknown' ? '（仅核验来源）' : '' }}</button></div>
        <section v-if="state.context.can_read" class="history"><h4>明确读取已有评估</h4><p class="note">使用服务端已返回的评估 ID；历史结论保持原画像、阶段和时刻，不自动确认新检查。</p><div class="history-query"><label>评估 UUID<input :value="state.assessmentId" data-testid="assessment-history-id" autocomplete="off" :disabled="!!state.privateBusy" @input="historyChanged"></label><button type="button" class="secondary" data-testid="assessment-history-read" :disabled="!!state.privateBusy || !state.assessmentId" @click="workspace.readAssessment()">读取历史评估</button></div><div v-if="state.history" data-testid="assessment-history-result"><AssessmentResult :result="state.history" historical @evidence="openResultEvidence(state.history,$event)" /><button type="button" class="secondary" data-testid="plan-history-assessment-add" :disabled="!canAddToPlan(state.history)" @click="emit('planAssessment',state.history)">加入准备目标（历史或未知来源仅核验）</button><label v-if="state.context.can_replay" class="confirmation"><input type="checkbox" data-testid="assessment-replay-confirm" :checked="state.replayConfirmed" :disabled="!!state.privateBusy" @change="workspace.setReplayConfirmed(checked($event))"><span>我明确要求重放此评估，并核对其原版本与当前证明状态；不创建新的确认。</span></label><button v-if="state.context.can_replay" type="button" class="secondary" data-testid="assessment-replay" :disabled="!!state.privateBusy || !state.replayConfirmed" @click="workspace.replayAssessment()">明确重放此历史评估</button></div></section>
      </template>
    </section>
    <PublicEvidenceDialog :evidence="state.evidence" :loading="state.evidenceBusy" :message="state.evidenceMessage" @close="workspace.closeEvidence" />
  </section>
</template>
<style scoped>
.catalog-workspace{grid-column:1/-1;min-width:0;padding:30px;background:#fff;border:1px solid #dce5d6;border-radius:12px;color:#294b3a}.workspace-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;margin-bottom:22px}.kicker{font-size:10px;letter-spacing:1.6px;color:#8a987d;margin:0 0 10px}.workspace-heading h2{font-size:25px;margin:0;line-height:1.5}.workspace-heading p:last-child{font-size:11px;color:#7f8c72;line-height:1.9;margin-top:10px}.public-tag{font-size:10px;border:1px solid #d6e2cc;border-radius:20px;padding:7px 11px;white-space:nowrap;color:#758a68}.boundary{padding:16px 18px;border:1px solid #dbe2c8;background:#f4f6e9;border-radius:8px}.boundary strong{font-size:13px}.boundary p,.demo,.message,.note{font-size:11px;line-height:1.9;color:#76856a}.boundary p{margin:8px 0 0}.demo{padding:12px 15px;border:1px solid #e2d9bd;border-radius:6px;background:#f9f3e5;color:#817146;margin:18px 0}.message{background:#f5f8ef;border:1px solid #dce6d2;padding:13px 16px;border-radius:7px;overflow-wrap:anywhere;margin:18px 0}.message.error{background:#fcf2e7;border-color:#e7d5b8;color:#8c6741}.results-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:25px 0 18px}.results-heading h3{font-size:17px;margin:0}.results-heading p{font-size:10px;line-height:1.9;color:#87937b;margin:0;max-width:440px}.offering-grid,.comparison-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.comparison,.private-check{border-top:1px solid #e0e8d9;margin-top:32px;padding-top:8px}.compare-item{min-width:0}.compare-item>button{margin-top:11px;width:100%}.secondary,.primary{border:1px solid #b9cfb7;border-radius:6px;background:white;color:#4b7049;font-size:11px;padding:11px 14px;line-height:1.7}.primary{background:#1b6453;border-color:#1b6453;color:white}.next{margin-top:18px}.binding{padding:22px;border:1px solid #d9e4ce;border-radius:8px;background:#f8faf5;margin:22px 0}.binding h4,.history h4{font-size:14px;margin:0 0 17px}.binding dl{font-size:11px;display:grid;gap:10px}.binding dl>div{display:grid;grid-template-columns:94px minmax(0,1fr);gap:12px}.binding dt{color:#8a957c}.binding dd{margin:0;line-height:1.8;overflow-wrap:anywhere}.stage{display:flex;flex-direction:column;gap:8px;font-size:12px;margin:21px 0;max-width:300px}.stage select,.scope-confirmation select,.history input{width:100%;min-width:0;border:1px solid #c8d8bd;border-radius:6px;padding:10px 12px;font-size:11px;background:white;color:#476640}.scope-confirmation{border:1px solid #d8e2ce;border-radius:6px;padding:16px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px;min-width:0}.scope-confirmation legend{font-size:12px;padding:0 7px}.scope-confirmation p{grid-column:1/-1;font-size:10px;line-height:1.8;margin:0;color:#879479}.scope-confirmation label{display:flex;flex-direction:column;gap:7px;font-size:11px;min-width:0}.confirmation{display:flex;align-items:flex-start;gap:10px;font-size:11px;line-height:1.9;margin:22px 0;color:#57734c}.confirmation input{width:17px;height:17px;flex:0 0 17px;margin:3px 0 0}.confirmation span{min-width:0}.history{border-top:1px solid #e1e8d9;margin-top:27px;padding-top:23px}.history-query{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:13px;margin:20px 0}.history-query label{display:flex;flex-direction:column;gap:8px;font-size:11px;min-width:0}.catalog-workspace :focus-visible{outline:3px solid #8cb6a4;outline-offset:3px}.catalog-workspace button:disabled{background:#f0f3e9;color:#919d85;border-color:#e0e7d8;cursor:default}@media(max-width:850px){.workspace-heading{flex-wrap:wrap}.results-heading{flex-wrap:wrap}}@media(max-width:650px){.catalog-workspace{padding:24px 17px}.workspace-heading h2{font-size:22px}.offering-grid,.comparison-grid,.scope-confirmation,.history-query{grid-template-columns:1fr}.binding{padding:19px 15px}.binding dl>div{grid-template-columns:1fr;gap:3px}.private-check .results-heading{align-items:stretch}.private-check .results-heading button{width:100%}}
</style>
