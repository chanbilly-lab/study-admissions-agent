<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { SessionApi } from './client'
import { useSession } from './useSession'
import SettingsView from '../../views/SettingsView.vue'
import type { RightsApi } from '../privacy/rights/client'
import type { PrivacyApi } from '../privacy/client'
import type { SharingApi } from '../sharing/client'
import AdminView from '../../views/admin/AdminView.vue'
import type { AdminApi } from '../admin/client'
import ReviewReleaseView from '../../views/admin/ReviewReleaseView.vue'
import type { ReviewWorkspaceApi } from '../admin/reviews/client'
import type { PublicPreviewApi } from '../admin/releases/publicClient'
import ProfileView from '../../views/ProfileView.vue'
import type { ProfileApi } from '../profiles/client'
import type { ProfileVersionData } from '../../../../../packages/contracts/v2/profiles/generated'
import CatalogView from '../../views/CatalogView.vue'
import type { CatalogApi } from '../catalog/client'
import type { EligibilityApi } from '../eligibility/client'
import type { AssessmentData } from '../eligibility/client'
import { bindProfile } from '../eligibility/validation'
import PlanView from '../../views/PlanView.vue'
import type { PlanApi } from '../plans/client'
import type { QAApi } from '../qa/client'

const props = defineProps<{ api?: SessionApi; privacyApi?: PrivacyApi; sharingApi?: SharingApi; rightsApi?: RightsApi; adminApi?: AdminApi; reviewApi?: ReviewWorkspaceApi; publicApi?: PublicPreviewApi; profileApi?: ProfileApi; catalogApi?: CatalogApi; eligibilityApi?: EligibilityApi; planApi?: PlanApi; qaApi?: QAApi }>()
const coreAllowed = ref(false)
const catalogExpanded = ref(false), selectedProfile = ref<ProfileVersionData | null>(null), profileEpoch = ref(0)
const plansExpanded = ref(false), planTargets = ref<AssessmentData[]>([]), planSelectionMessage = ref('')
function invalidateProfile() { selectedProfile.value = null; profileEpoch.value++; planTargets.value = []; planSelectionMessage.value = '' }
function selectProfile(version: ProfileVersionData | null) { if (selectedProfile.value?.version_id !== version?.version_id) { planTargets.value = []; planSelectionMessage.value = '' }; selectedProfile.value = version }
function addPlanAssessment(result: AssessmentData) {
  if (!state.actor || !coreAllowed.value || !selectedProfile.value || !bindProfile(result, selectedProfile.value)) return
  if (planTargets.value.some(item => item.assessment_id === result.assessment_id)) { planSelectionMessage.value = '此本人评估已加入准备目标。'; return }
  if (planTargets.value.length >= 4) { planSelectionMessage.value = '最多加入四个评估目标，请在新一组选择前重新核对画像。'; return }
  planTargets.value = [...planTargets.value, JSON.parse(JSON.stringify(result)) as AssessmentData]
  planSelectionMessage.value = '已加入准备目标。请展开计划工作台，明确选择后创建草案。'
}
const session = useSession(props.api)
const { state, loginPath } = session
watch(() => [state.actor, coreAllowed.value] as const, invalidateProfile, { flush: 'sync' })
const labels = {
  loading: '正在检查会话', logging_out: '正在退出', authenticated: '会话已建立', unauthenticated: '尚未登录',
  forbidden: '账号未获准访问', unavailable: '身份服务未启用或不可用', error: '会话检查失败',
}
const expiry = computed(() => state.actor ? new Intl.DateTimeFormat('zh-CN', {
  dateStyle: 'medium', timeStyle: 'medium', timeZone: 'Asia/Shanghai',
}).format(new Date(state.actor.expires_at)) : '')
onMounted(() => { void session.refresh() })
onUnmounted(session.dispose)
</script>

<template>
  <div class="auth-shell">
    <header class="auth-header">
      <div class="auth-brand"><span class="auth-mark" aria-hidden="true">↗</span><span>升学咨询<span class="brand-caption">身份与访问</span></span></div>
      <span class="auth-environment">独立身份入口</span>
    </header>
    <main class="auth-main">
      <section class="auth-intro" aria-labelledby="auth-title">
        <p class="auth-kicker">ACCOUNT ACCESS</p>
        <h1 id="auth-title">先确认身份，<br>再开启下一步。</h1>
        <p class="auth-description">使用已登记的身份供应商登录。浏览器通过受保护的 Cookie 读取当前会话，不接收或保存登录 token。</p>
        <div class="auth-scope">
          <strong>公开注册与真实学生资料处理尚未开放</strong>
          <p>当前入口验证登录、会话与隐私准入。合成画像与来源管理分别由服务器检查当前用途和权限；真实画像、申请仍未开放，身份认证不会自动取得这些权限。</p>
        </div>
      </section>
      <section class="auth-card" aria-labelledby="session-title" :aria-busy="state.status === 'loading' || state.status === 'logging_out'">
        <div class="auth-card-heading"><span class="auth-step">01 / 身份验证</span><span class="auth-state-pill" :class="state.status">{{ labels[state.status] }}</span></div>
        <h2 id="session-title">当前会话</h2>
        <p v-if="state.status === 'loading'" role="status" class="auth-status">正在向服务端检查当前身份…</p>
        <p v-else-if="state.status === 'logging_out'" role="status" class="auth-status">{{ state.message }}</p>
        <template v-else-if="state.actor">
          <p role="status" class="auth-status">已通过当前服务端会话验证。</p>
          <p v-if="state.actor.is_synthetic" class="auth-demo" data-testid="synthetic-banner"><strong>DEMO · 合成身份验收</strong><br>这是隔离测试主体，不是真实 Keycloak 账号或真实学生。</p>
          <dl class="auth-details">
            <div><dt>账号标识</dt><dd data-testid="actor-id">{{ state.actor.user_id }}</dd></div>
            <div><dt>会话到期</dt><dd><time :datetime="state.actor.expires_at">{{ expiry }}</time><small>北京时间 · 以服务端有效期为准</small></dd></div>
            <div><dt>私有业务</dt><dd>尚未开放</dd></div>
          </dl>
        </template>
        <template v-else>
          <p :role="state.status === 'unauthenticated' ? 'status' : 'alert'" class="auth-status">{{ state.message }}</p>
          <a v-if="state.status === 'unauthenticated'" class="auth-login" :href="loginPath">通过身份供应商登录 <span aria-hidden="true">→</span></a>
        </template>
        <button v-if="state.canLogout || state.logoutUnconfirmed || state.status === 'logging_out'" type="button" class="auth-logout auth-refresh" :disabled="state.status === 'logging_out'" @click="session.logout">{{ state.logoutUnconfirmed ? '重试退出当前应用' : '退出当前应用' }}</button>
        <button type="button" class="auth-refresh" :disabled="state.status === 'loading' || state.status === 'logging_out'" @click="session.refresh">重新检查会话</button>
        <p v-if="state.actor || state.status === 'logging_out' || state.logoutUnconfirmed" class="auth-logout-note">只退出当前应用会话；身份供应商的单点登录会话由供应商管理。</p>
        <p class="auth-card-note">仅预登记且启用的主体可建立会话。未知账号不会自动注册；供应商失败时不会回退到演示账号。</p>
      </section>
      <SettingsView class="auth-privacy" :actor="state.actor" :privacy-api="privacyApi" :sharing-api="sharingApi" :rights-api="rightsApi" @session-expired="session.invalidate" @admission-changed="coreAllowed = $event" />
      <ProfileView :actor="state.actor" :core-allowed="coreAllowed" :api="profileApi" @session-expired="session.invalidate" @profile-invalidated="invalidateProfile" @profile-selected="selectProfile" />
      <section class="auth-catalog-entry" aria-labelledby="catalog-entry-title"><div><p class="auth-kicker">PROGRAMMES &amp; EVIDENCE</p><h2 id="catalog-entry-title">公开项目、比较与资格证据</h2><p>匿名可查询已发布资料。本人资格检查还需当前用途、服务端权限和明确确认画像；不会根据演示资料填补真实规则。</p></div><button type="button" class="auth-refresh" data-testid="catalog-toggle" :aria-expanded="catalogExpanded" aria-controls="catalog-panel" @click="catalogExpanded = !catalogExpanded">{{ catalogExpanded ? '收起项目与证据工作台' : '展开项目与证据工作台' }}</button></section>
      <CatalogView v-if="catalogExpanded" id="catalog-panel" :actor="state.actor" :core-allowed="coreAllowed" :profile="selectedProfile" :profile-epoch="profileEpoch" :catalog-api="catalogApi" :eligibility-api="eligibilityApi" :qa-api="qaApi" @session-expired="session.invalidate" @plan-assessment="addPlanAssessment" />
      <section class="auth-catalog-entry" aria-labelledby="plans-entry-title"><div><p class="auth-kicker">PREPARATION &amp; PROGRESS</p><h2 id="plans-entry-title">准备计划与本人进度</h2><p>从已返回的本人评估明确选择目标，核对估时与可用时间。官方期限未知仍保留，计划确认不会升级资格。</p><p v-if="planSelectionMessage" role="status" data-testid="plan-selection-message">{{ planSelectionMessage }}</p></div><button type="button" class="auth-refresh" data-testid="plans-toggle" :aria-expanded="plansExpanded" aria-controls="plans-panel" @click="plansExpanded = !plansExpanded">{{ plansExpanded ? '收起计划工作台' : '展开计划工作台' }}</button></section>
      <PlanView v-if="plansExpanded" id="plans-panel" :actor="state.actor" :core-allowed="coreAllowed" :profile="selectedProfile" :profile-epoch="profileEpoch" :targets="planTargets" :api="planApi" @session-expired="session.invalidate" />
      <AdminView :actor="state.actor" :api="adminApi" @session-expired="session.invalidate" />
      <ReviewReleaseView :actor="state.actor" :api="reviewApi" :public-api="publicApi" @session-expired="session.invalidate" />
    </main>
    <footer class="auth-footer"><span>真实身份服务与生产发布仍需独立验收。</span><span>最少资料 · 服务端验证 · 明确权限</span></footer>
  </div>
</template>

<style scoped>
.auth-privacy{grid-column:1/-1}
.auth-catalog-entry{grid-column:1/-1;min-width:0;padding:25px;border:1px solid #d9e4d3;border-radius:11px;background:#f8faf5;display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:25px}.auth-catalog-entry h2{font-size:23px;margin:0}.auth-catalog-entry p:last-child{font-size:11px;line-height:1.9;color:#74856b;margin-top:12px}.auth-catalog-entry .auth-kicker{margin-bottom:9px}.auth-catalog-entry button{width:auto;margin:0}@media(max-width:650px){.auth-catalog-entry{grid-template-columns:1fr;padding:21px 17px}.auth-catalog-entry h2{font-size:21px}.auth-catalog-entry button{width:100%}}
.auth-logout{border-color:#b8c5c0;color:#285d4e}.auth-logout-note{font-size:10px;color:#78867c;line-height:1.8;margin-top:14px}
.auth-shell{min-height:100vh;background:#f2f5f1;color:#193e35;padding:30px clamp(20px,6vw,100px);display:flex;flex-direction:column}.auth-header{display:flex;justify-content:space-between;align-items:center;gap:20px}.auth-brand{display:flex;align-items:center;gap:13px;font-weight:650;font-size:19px}.auth-mark{display:grid;place-items:center;border:1px solid #548376;width:42px;height:44px;border-radius:12px;font-size:25px}.brand-caption{display:block;font-weight:400;font-size:10px;letter-spacing:2px;margin-top:5px;color:#6e857b}.auth-environment{font-size:11px;border:1px solid #d1dfd4;border-radius:30px;padding:8px 13px;color:#647d6c}.auth-main{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:clamp(35px,8vw,120px);max-width:1160px;width:100%;margin:80px auto;align-items:center}.auth-kicker{color:#7b907b;font-size:10px;letter-spacing:2.5px;margin-bottom:20px}.auth-intro h1{font-size:clamp(32px,4vw,48px);line-height:1.38;letter-spacing:-1.5px;font-weight:600}.auth-description{margin-top:25px;color:#6a7d70;font-size:14px;line-height:1.9;max-width:415px}.auth-scope{border-left:2px solid #a3b693;padding-left:18px;margin-top:38px}.auth-scope strong{font-size:12px;line-height:1.8}.auth-scope p{font-size:11px;color:#778473;margin-top:7px;line-height:1.9}.auth-card{background:#fff;border:1px solid #dfe7dd;border-radius:14px;padding:34px;box-shadow:0 14px 50px #1d453008;min-width:0}.auth-card-heading{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:26px}.auth-step{font-size:10px;color:#80927c}.auth-state-pill{font-size:10px;border-radius:5px;padding:6px 9px;background:#eff2ed;color:#65745f}.auth-state-pill.authenticated{background:#e5f2e8;color:#316b45}.auth-state-pill.unavailable,.auth-state-pill.forbidden,.auth-state-pill.error{background:#faf0de;color:#906d31}.auth-card h2{font-size:23px}.auth-status{margin:17px 0 22px;color:#68796a;font-size:13px;line-height:1.9}.auth-login{display:flex;justify-content:space-between;gap:15px;background:#1b6453;color:#fff;border-radius:7px;padding:15px 18px;font-size:13px;font-weight:600;margin-top:26px}.auth-login:hover{background:#164f43}.auth-refresh{background:#fff;border:1px solid #bdcebe;color:#426b4c;border-radius:7px;padding:12px 15px;width:100%;font-size:12px;margin-top:16px}.auth-card-note{font-size:10px;color:#87917f;line-height:1.9;border-top:1px solid #e9eee6;padding-top:20px;margin-top:25px}.auth-demo{padding:13px 15px;background:#eef3e5;border:1px solid #d6e0c8;border-radius:7px;font-size:11px;line-height:1.9;color:#617245}.auth-details{margin:24px 0 0;display:grid;gap:17px;font-size:12px}.auth-details>div{display:grid;grid-template-columns:80px minmax(0,1fr);gap:12px}.auth-details dt{color:#8a9581}.auth-details dd{margin:0;overflow-wrap:anywhere;line-height:1.7}.auth-details small{display:block;font-size:10px;color:#94a08c;margin-top:3px}.auth-footer{display:flex;justify-content:space-between;gap:20px;font-size:10px;color:#8b9a84;line-height:1.8}.auth-login:focus-visible,.auth-refresh:focus-visible{outline:3px solid #8cb6a4;outline-offset:4px}@media(max-width:850px){.auth-main{gap:32px;margin:50px auto}.auth-card{padding:25px}.auth-card-heading{flex-wrap:wrap;gap:10px}}@media(max-width:650px){.auth-shell{padding:23px 19px}.auth-environment{font-size:10px;padding:6px 9px}.auth-main{grid-template-columns:1fr;margin:40px auto;gap:32px}.auth-intro h1{font-size:33px}.auth-description{font-size:12px;margin-top:19px}.auth-scope{margin-top:24px}.auth-card{padding:24px 20px}.auth-footer{flex-direction:column;gap:5px}}
</style>
