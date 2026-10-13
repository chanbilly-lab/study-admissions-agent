<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import type { SessionData } from '../auth/client'
import type { PrivacyApi } from './client'
import { useAdmission } from './useAdmission'

const props = defineProps<{ actor: SessionData | null; api?: PrivacyApi }>()
const emit = defineEmits<{ sessionExpired: []; admissionChanged: [allowed: boolean] }>()
const admission = useAdmission(props.api, () => emit('sessionExpired'))
const { state } = admission
const reasons = {
  allowed: '核心用途门槛已满足；私有业务仍未开放。',
  processing_disabled: '资料处理未就绪，当前不接受年龄声明或用途确认。',
  age_missing: '尚无有效的成年本人声明；未知或未成年保持私有处理关闭。',
  age_expired: '本人声明已到期，需要重新声明并确认。',
  notice_changed: '当前告知已变更，需要重新声明并确认。',
  policy_changed: '当前政策已变更，需要重新声明并确认。',
  consent_missing: '尚未确认核心咨询用途。',
  consent_withdrawn: '核心用途已撤回，后续相应用途处理关闭。',
  consent_invalidated: '旧用途确认已失效，需要重新明确确认。',
  role_missing: '当前账号缺少所需权限；用途确认不会授予角色。',
}
const current = computed(() => state.admission)
const busy = computed(() => state.status === 'loading' || state.action !== null)
const canDeclare = computed(() => admission.canSubmit() && Boolean(state.ageBand) && state.ageConfirmed)
const canConfirm = computed(admission.canConfirm)
watch(() => props.actor, (actor) => { void admission.setActor(actor) }, { immediate: true })
// This signal only invalidates private UI. A positive value still requires its
// own current server capability check; a write in flight never keeps old data.
watch(() => [props.actor, state.status, state.action, state.admission] as const, () => {
  emit('admissionChanged', Boolean(props.actor && state.status === 'ready' && state.action === null
    && state.admission?.user_id === props.actor.user_id && state.admission.is_synthetic === props.actor.is_synthetic
    && state.admission.core_consultation_allowed))
}, { immediate: true, flush: 'sync' })
onUnmounted(admission.dispose)
</script>

<template>
  <section class="privacy-panel" aria-labelledby="privacy-title">
    <header class="privacy-heading">
      <div><p class="privacy-step">02 / 资料用途与年龄准入</p><h2 id="privacy-title">先了解，再明确确认。</h2></div>
    <span class="privacy-pill">{{ state.notice?.readiness ? '仅合成离线流程' : '真实资料处理尚未开放' }}</span>
    </header>
    <p class="privacy-intro">本人声明成年不等于独立年龄核验。完成隐私步骤不会自动开放画像、申请或管理权限。</p>
  <p v-if="state.status === 'loading'" class="privacy-message" role="status">正在读取当前告知与本人设置…</p>
  <p v-if="state.message" class="privacy-message" :role="state.status === 'error' ? 'alert' : 'status'">{{ state.message }}</p>
  <p v-if="state.notice?.is_synthetic" class="privacy-demo" data-testid="privacy-demo"><strong>DEMO · 合成告知与准入验收</strong><br>此告知仅用于隔离测试，不能用于真实学生资料处理。</p>
  <div v-if="state.notice && !state.notice.readiness" class="privacy-unready" role="status">
      <strong>正式告知尚未就绪</strong>
      <p>当前不接受年龄声明或用途确认。资料处理责任主体及权利请求渠道尚待完善。</p>
  </div>
  <details v-if="state.notice" class="privacy-notice" open>
    <summary>当前告知与保存上限</summary>
    <dl class="privacy-meta">
      <div><dt>政策版本</dt><dd>{{ state.notice.policy_version }}</dd></div>
      <div><dt>告知版本</dt><dd>{{ state.notice.notice_version ?? '未配置正式版本' }}</dd></div>
      <div><dt>文本 hash</dt><dd data-testid="notice-hash">{{ state.notice.notice_hash }}</dd></div>
    </dl>
    <p class="privacy-text" data-testid="notice-text">{{ state.notice.text }}</p>
    <p class="privacy-retention">附件类型 {{ state.notice.retention_policy.file_types.join(' / ') }}，单文件上限 {{ state.notice.retention_policy.max_file_bytes / 1048576 }} MiB；私有资料最长 {{ state.notice.retention_policy.private_data_max_months }} 个月；删除受理后在线清理上限 {{ state.notice.retention_policy.online_deletion_max_days }} 天；脱敏日志 {{ state.notice.retention_policy.sanitized_logs_max_days }} 天；审计/授权记录最长 {{ state.notice.retention_policy.audit_authorization_max_months }} 个月；备份 {{ state.notice.retention_policy.backup_max_days }} 天。</p>
    <p class="privacy-retention">以上是产品上限，更短必要期限优先。清理作业、删除传播和备份恢复重施删除尚未实现；本页面不接收附件。</p>
  </details>
    <div class="privacy-policy" aria-label="当前年龄产品政策">
      <div><span>18 岁及以上</span><p>需要本人明确声明并确认具体用途。</p></div>
      <div><span>14–17 岁</span><p>需要独立监护核验与本人确认；本版未提供核验，私有处理关闭。</p></div>
      <div><span>不满 14 岁 / 年龄未知</span><p>仅公开浏览。无需提交出生日期、证件或成绩。</p></div>
  </div>
  <div v-if="current" class="privacy-current" aria-labelledby="admission-title">
    <h3 id="admission-title">本人当前设置</h3>
    <dl class="privacy-meta">
      <div><dt>年龄状态</dt><dd data-testid="age-assurance">{{ current.age_assurance === 'declared' ? '18 岁及以上 · 本人声明，未独立核验' : '未知 / 无有效成年声明' }}</dd></div>
      <div><dt>用途确认</dt><dd>{{ { not_confirmed: '尚未确认', active: '已记录确认', withdrawn: '已撤回', invalidated: '已失效' }[current.consent_status] }}</dd></div>
    </dl>
    <p class="privacy-decision" :class="{ allowed: current.core_consultation_allowed }" data-testid="admission-decision">{{ reasons[current.reason] }}</p>
    <p class="privacy-retention">最终准入以服务端当前会话、声明、告知和权限校验为准。本页面不开放画像、计划或管理功能。</p>
  </div>
  <p v-else-if="!actor && state.notice" class="privacy-retention">登录后可读取本人隐私设置。公开浏览无需提交年龄或成绩。</p>
  <template v-if="actor && current && state.notice?.readiness">
    <form class="privacy-form" @submit.prevent="admission.declareAge">
      <fieldset :disabled="busy || !admission.canSubmit()">
        <legend>本人年龄区间声明</legend>
        <label class="privacy-choice"><input v-model="state.ageBand" type="radio" name="age-band" value="18_plus">18 岁及以上</label>
        <label class="privacy-choice"><input v-model="state.ageBand" type="radio" name="age-band" value="14_17">14–17 岁</label>
        <label class="privacy-choice"><input v-model="state.ageBand" type="radio" name="age-band" value="under_14">不满 14 岁</label>
        <label class="privacy-choice"><input v-model="state.ageBand" type="radio" name="age-band" value="unknown">年龄未知 / 不作成年声明</label>
        <p class="privacy-retention">选择未成年或未知会清除原成年声明并使旧用途确认失效；不会保存新的儿童年龄声明。此步骤不核验年龄。</p>
        <label class="privacy-confirm"><input v-model="state.ageConfirmed" type="checkbox" data-testid="age-confirmation">我已阅读当前告知，并明确提交上述本人声明。</label>
      </fieldset>
      <button type="submit" class="privacy-primary" :disabled="!canDeclare" data-testid="declare-age">{{ state.action === 'age' ? '正在提交…' : '明确提交年龄声明' }}</button>
    </form>
    <form v-if="current.age_band === '18_plus' && current.age_assurance === 'declared' && current.consent_status !== 'active'" class="privacy-form" @submit.prevent="admission.confirmCore">
      <h3>单独确认核心咨询用途</h3>
      <p class="privacy-retention">仅用于本人确认的本科咨询、确定性资格和准备计划。不包含外部模型、营销或第三方共享；不代替画像和计划的后续明确确认。</p>
      <label class="privacy-confirm"><input v-model="state.coreConfirmed" type="checkbox" :disabled="busy || !admission.canSubmit()" data-testid="core-confirmation">我已阅读当前版本告知，明确确认核心咨询用途。</label>
      <button type="submit" class="privacy-primary" :disabled="!canConfirm" data-testid="confirm-core">{{ state.action === 'confirm' ? '正在确认…' : '明确确认核心用途' }}</button>
    </form>
  </template>
  <button v-if="current?.consent_id && current.consent_status === 'active'" type="button" class="privacy-withdraw" :disabled="busy" data-testid="withdraw-core" @click="admission.withdraw">撤回核心用途确认</button>
  <p v-if="state.action" role="status" class="privacy-message">正在等待服务端确认，本次操作尚未完成…</p>
  <button type="button" class="privacy-refresh" :disabled="busy" @click="admission.refresh">重新读取隐私设置</button>
  </section>
</template>

<style scoped>
.privacy-choice input[type=radio],.privacy-confirm input[type=checkbox]{width:16px;height:16px;min-height:16px;padding:0;flex:0 0 16px}
.privacy-message{font-size:12px;line-height:1.9;color:#796348;margin:18px 0}.privacy-demo{border:1px solid #d6e0c8;border-radius:7px;background:#eef3e5;padding:12px 15px;font-size:11px;line-height:1.9;color:#617245}.privacy-notice{margin:24px 0;border-block:1px solid #e5ebe1;padding:18px 0}.privacy-notice summary{cursor:pointer;font-size:13px;font-weight:600}.privacy-meta{display:grid;gap:11px;margin:18px 0;font-size:11px}.privacy-meta>div{display:grid;grid-template-columns:76px minmax(0,1fr);gap:12px}.privacy-meta dt{color:#83917b}.privacy-meta dd{margin:0;overflow-wrap:anywhere;line-height:1.8}.privacy-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9;font-size:12px;color:#637562}.privacy-retention{font-size:11px;line-height:1.9;color:#7b8973;margin-top:12px}.privacy-current{margin-top:25px;padding:20px;background:#f6f8f3;border-radius:8px}.privacy-current h3,.privacy-form h3{font-size:14px;font-weight:600}.privacy-decision{font-size:12px;line-height:1.9;color:#78623f;padding-top:10px}.privacy-decision.allowed{color:#286a4c}.privacy-form{margin-top:25px;padding-top:22px;border-top:1px solid #e6ece2}.privacy-form fieldset{border:0;padding:0;min-width:0}.privacy-form legend{font-size:14px;font-weight:600;margin-bottom:16px}.privacy-choice,.privacy-confirm{display:flex;align-items:flex-start;gap:10px;font-size:12px;line-height:1.9;margin:12px 0;color:#526d58}.privacy-choice input,.privacy-confirm input{margin-top:5px;flex-shrink:0;accent-color:#266a54}.privacy-confirm{padding:15px;background:#f4f7ef;border-radius:7px;margin-top:18px}.privacy-primary,.privacy-withdraw,.privacy-refresh{border-radius:7px;padding:12px 18px;font-size:12px;margin-top:16px;border:1px solid #bdcebe;background:#fff;color:#426b4c}.privacy-primary{background:#1b6453;color:#fff;border-color:#1b6453}.privacy-primary:disabled{background:#eef2eb;color:#94a18b;border-color:#e1e7dd}.privacy-withdraw{border-color:#d5c2b1;color:#865d42;margin-right:14px}.privacy-refresh{display:block}.privacy-primary:focus-visible,.privacy-withdraw:focus-visible,.privacy-refresh:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #8cb6a4;outline-offset:4px}
.privacy-panel{min-width:0;background:#fff;border:1px solid #dfe7dd;border-radius:14px;padding:30px 34px;color:#193e35;box-shadow:0 14px 50px #1d453008}.privacy-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}.privacy-step{font-size:10px;color:#80927c;margin:0 0 12px}.privacy-heading h2{font-size:23px;font-weight:600;line-height:1.5;margin:0}.privacy-pill{flex-shrink:0;max-width:190px;border-radius:5px;padding:7px 10px;background:#eff2ed;color:#65745f;font-size:10px;line-height:1.6}.privacy-intro{font-size:12px;color:#6a7d70;line-height:1.9;margin:18px 0 22px;max-width:760px}.privacy-unready{background:#faf4e8;border:1px solid #eadfc6;border-radius:8px;padding:17px 19px;color:#826934;font-size:12px;line-height:1.9}.privacy-unready strong{font-weight:600}.privacy-unready p{margin:5px 0 0}.privacy-policy{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:21px;margin-top:27px}.privacy-policy>div{border-top:1px solid #e5ece2;padding-top:16px}.privacy-policy span{font-size:11px;font-weight:600;line-height:1.7}.privacy-policy p{font-size:11px;color:#7a8b76;line-height:1.9;margin:6px 0 0}@media(max-width:850px){.privacy-panel{padding:25px}.privacy-heading{flex-wrap:wrap}.privacy-policy{gap:16px}}@media(max-width:650px){.privacy-panel{padding:24px 20px}.privacy-policy{grid-template-columns:1fr;gap:13px}.privacy-heading h2{font-size:21px}.privacy-pill{max-width:none}.privacy-intro{font-size:11px}}
</style>
