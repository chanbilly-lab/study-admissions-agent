<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import type { SessionData } from '../auth/client'
import type { SharingApi } from './client'
import { useSharing } from './useSharing'

const props = defineProps<{ actor: SessionData | null; api?: SharingApi }>()
const emit = defineEmits<{ sessionExpired: [] }>()
const sharing = useSharing(props.api, () => emit('sessionExpired'))
const { state } = sharing
const names = { profile: '画像元数据', plan: '计划元数据', attachment: '附件元数据', export: '导出元数据', job: '作业元数据' }
const fields = { status: '对象状态 status', version: '对象版本 version' }
const actions = { read: '读取 read', list: '列出 list' }
const scope = computed(() => state.policy?.scope_matrix.find(item => item.resource_type === state.resourceType))
const states = { pending: '待受权人接受', accepted: '已接受', revoked: '已撤销' }
const date = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC' }).format(new Date(value))
watch(() => props.actor, actor => { void sharing.setActor(actor) }, { immediate: true })
function changed() { state.confirmed = false }
function changeKind() { state.fields = []; state.actions = []; changed() }
onUnmounted(sharing.dispose)
</script>

<template>
  <section class="sharing-panel" aria-labelledby="sharing-title" :aria-busy="state.status === 'loading' || state.action !== null">
    <header class="sharing-heading"><div><p class="sharing-kicker">03 / 明确范围的共享</p><h2 id="sharing-title">共享授权</h2></div><span class="sharing-pill">真实共享未开放</span></header>
    <p class="sharing-intro">核心咨询确认不包含共享。每项授权由本人明确选择，指定受权人在自己的会话中独立接受；监护关系与角色不会自动赋权。</p>
    <p v-if="state.policy?.is_synthetic" class="sharing-demo" data-testid="sharing-demo"><strong>DEMO · 合成共享策略</strong> · 当前仅验收元数据权限，没有真实学生内容或整文件权限。</p>
    <p v-if="state.status === 'loading'" role="status">正在读取共享设置…</p>
    <p v-if="state.message" :role="state.status === 'error' ? 'alert' : 'status'" class="sharing-message">{{ state.message }}</p>
    <p v-if="state.policyError" role="alert" class="sharing-closed" data-testid="sharing-policy-unavailable">{{ state.policyError }}</p>
    <template v-if="state.policy">
      <p v-if="!state.policy.sharing_available" class="sharing-closed" data-testid="sharing-closed">共享配置未开放。不会收集对象或受权人输入；已有本人授权仍可请求撤销。</p>
      <details class="sharing-policy"><summary>查看独立共享告知与范围</summary><p class="sharing-text">{{ state.policy.text }}</p><dl><div><dt>政策版本</dt><dd>{{ state.policy.policy_version }}</dd></div><div><dt>原文 SHA256</dt><dd>{{ state.policy.text_sha256 }}</dd></div></dl><p>合成策略上限：30 天；精确绑定对象版本，变更版本需重新授权。正式部署期限尚未决定。</p></details>
      <p v-if="!actor" class="sharing-help">公开查看策略无需提交个人资料。请先登录，再读取本人授权。</p>
    </template>
    <template v-if="actor && state.list">
      <div class="sharing-list-header"><div class="sharing-tabs" aria-label="授权方向"><button type="button" :aria-pressed="state.direction === 'issued'" :disabled="!!state.action" @click="sharing.chooseDirection('issued')">本人授出</button><button type="button" :aria-pressed="state.direction === 'received'" :disabled="!!state.action" @click="sharing.chooseDirection('received')">本人收到</button></div><span>{{ state.list.total }} 项 · 当前页 {{ state.list.items.length }} 项</span></div>
      <p class="sharing-help">修改年龄声明或核心用途后，请重新读取共享设置。成年声明不等于独立年龄核验。</p>
      <form v-if="sharing.canCreate()" class="sharing-form" @submit.prevent="sharing.create">
        <h3>创建一项具体授权</h3>
        <p class="sharing-help">输入预登记受权人和本人对象的准确 UUID；服务端校验登记与归属。此处没有真实对象选择器，不接受姓名、证件或成绩。</p>
        <div class="sharing-input-grid">
          <label>对象类型<select v-model="state.resourceType" data-testid="grant-kind" required @change="changeKind"><option value="" disabled>请选择</option><option v-for="item in state.policy?.scope_matrix" :key="item.resource_type" :value="item.resource_type">{{ names[item.resource_type] }}</option></select></label>
          <label>具体对象 UUID<input v-model="state.resourceId" data-testid="grant-resource" required autocomplete="off" spellcheck="false" @input="changed"></label>
          <label>当前对象版本<input v-model="state.resourceVersion" data-testid="grant-resource-version" type="number" min="1" step="1" required @input="changed"></label>
          <label>指定受权人 UUID<input v-model="state.granteeId" data-testid="grant-grantee" required autocomplete="off" spellcheck="false" @input="changed"></label>
          <label class="sharing-expiry">到期时间（UTC）<input v-model="state.expiryUtc" data-testid="grant-expiry" type="datetime-local" step="1" required @input="changed"><small>按 UTC 输入，提交时明确带 Z。上限 30 天；实际期限以服务端校验为准。</small></label>
        </div>
        <div v-if="scope" class="sharing-scope-grid"><fieldset><legend>具体字段（至少一项）</legend><label v-for="field in scope.fields" :key="field" class="sharing-choice"><input v-model="state.fields" type="checkbox" :value="field" :data-testid="`grant-field-${field}`" @change="changed"><span>{{ fields[field] }}</span></label></fieldset><fieldset><legend>具体动作（至少一项）</legend><label v-for="action in scope.actions" :key="action" class="sharing-choice"><input v-model="state.actions" type="checkbox" :value="action" :data-testid="`grant-action-${action}`" @change="changed"><span>{{ actions[action] }}</span></label></fieldset></div>
        <label class="sharing-choice sharing-confirm"><input v-model="state.confirmed" type="checkbox" data-testid="grant-confirmation"><span>我已阅读独立共享告知，确认将上述对象版本、字段、动作和期限授权给指定受权人。这不允许下载、写入、转授权或代我确认。</span></label>
        <button type="submit" class="sharing-primary" data-testid="create-grant" :disabled="!sharing.inputReady()">创建待接受授权</button>
      </form>
      <p v-else-if="state.direction === 'issued' && state.policy?.sharing_available" class="sharing-closed">创建授权需当前本人学生权限、有效成年声明及核心用途确认。当前尚不满足；撤销已有本人授权仍允许。</p>
      <p v-if="state.direction === 'received' && !state.list.actor_declaration_id" class="sharing-closed">接受授权需要自己的当前有效成年声明。未知或未成年私有访问关闭；接受不会授予角色。</p>
      <div class="sharing-grants">
        <p v-if="state.list.items.length === 0" class="sharing-empty">当前页没有授权。</p>
        <article v-for="grant in state.list.items" :key="grant.id" class="sharing-grant" :data-testid="`grant-${grant.id}`">
          <div class="sharing-grant-head"><h3>{{ names[grant.resource_type] }} · 版本 {{ grant.resource_version }}</h3><span>{{ states[grant.state] }}</span></div>
          <p class="sharing-effective" :class="{ active: grant.access_active }" data-testid="grant-effective">{{ grant.access_active ? '当前有效（服务端本次检查）' : '当前无有效访问许可' }}</p>
          <dl><div><dt>授权标识</dt><dd>{{ grant.id }}</dd></div><div><dt>具体对象</dt><dd>{{ grant.resource_id }}</dd></div><div><dt>{{ state.direction === 'issued' ? '指定受权人' : '授权人' }}</dt><dd>{{ state.direction === 'issued' ? grant.grantee_user_id : grant.owner_user_id }}</dd></div><div><dt>字段 / 动作</dt><dd>{{ grant.fields.join('、') }} / {{ grant.actions.join('、') }}</dd></div><div><dt>明确到期</dt><dd><time :datetime="grant.expires_at">{{ date(grant.expires_at) }} UTC</time></dd></div></dl>
          <p class="sharing-help">“已接受”是历史状态；到期、撤回、声明、用途、政策或对象版本变化后，旧授权不会自动恢复。</p>
          <template v-if="sharing.canAccept(grant)"><label class="sharing-choice sharing-confirm"><input v-model="state.acceptConfirmed[grant.id]" type="checkbox" :data-testid="`accept-confirm-${grant.id}`"><span>我已阅读共享告知，明确接受这项对象、字段、动作和期限的授权；不接受其他资料或权限。</span></label><button type="button" class="sharing-primary" :data-testid="`accept-grant-${grant.id}`" :disabled="!state.acceptConfirmed[grant.id] || !!state.action" @click="sharing.accept(grant)">独立接受此项授权</button></template>
          <button v-if="sharing.canRevoke(grant)" type="button" class="sharing-revoke" :data-testid="`revoke-grant-${grant.id}`" :disabled="!!state.action" @click="sharing.revoke(grant)">{{ state.direction === 'issued' ? '撤销此项授权' : grant.state === 'pending' ? '拒绝此项共享' : '退出此项共享' }}</button>
        </article>
      </div>
      <button v-if="state.list.page.has_more" type="button" class="sharing-secondary" :disabled="!!state.action" @click="sharing.refresh(state.list.page.next_cursor ?? undefined)">读取下一页</button>
    </template>
    <button type="button" class="sharing-secondary sharing-refresh" :disabled="state.status === 'loading' || !!state.action" @click="sharing.refresh()">重新读取共享设置</button>
    <p class="sharing-footnote">撤销影响后续服务端访问，不能收回已送达副本。真实资料、公众共享、监护核验和业务功能仍未开放。</p>
  </section>
</template>

<style scoped>
.sharing-panel{background:#fff;border:1px solid #dfe7dd;border-radius:14px;padding:32px;color:#193e35;min-width:0}.sharing-heading,.sharing-list-header,.sharing-grant-head{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}.sharing-kicker{font-size:10px;color:#80927c;margin-bottom:10px}.sharing-heading h2{font-size:24px}.sharing-pill{font-size:10px;padding:7px 10px;border-radius:5px;background:#f6efde;color:#826932}.sharing-intro,.sharing-text{font-size:13px;line-height:1.9;margin:20px 0;color:#637568}.sharing-demo,.sharing-closed{font-size:12px;line-height:1.9;padding:13px 15px;background:#f1f4e8;border:1px solid #dce3cd;border-radius:7px;margin:18px 0;color:#647343}.sharing-closed{background:#f7f3e9;color:#7c6b45;border-color:#e6dcc5}.sharing-policy{border-block:1px solid #e8ede5;padding:17px 0;margin:22px 0;font-size:11px;line-height:1.9;color:#78846d}.sharing-policy summary{cursor:pointer;font-size:12px;color:#426b4c}.sharing-text{white-space:pre-wrap}.sharing-panel dl{display:grid;gap:10px;margin:18px 0;font-size:11px}.sharing-panel dl>div{display:grid;grid-template-columns:95px minmax(0,1fr);gap:13px}.sharing-panel dt{color:#899580}.sharing-panel dd{margin:0;overflow-wrap:anywhere;line-height:1.8}.sharing-list-header{margin-top:25px;font-size:11px;color:#809078}.sharing-tabs{display:flex;gap:8px}.sharing-tabs button{font-size:12px;border:1px solid #ccd7c7;padding:10px 15px;border-radius:7px;background:#fff;color:#5a795e}.sharing-tabs button[aria-pressed=true]{background:#eaf1e7;color:#32573a;border-color:#9db598}.sharing-help,.sharing-footnote{font-size:11px;line-height:1.9;color:#849079;margin:13px 0}.sharing-form{margin:23px 0 30px;border:1px solid #e0e8db;background:#fbfcf9;border-radius:9px;padding:23px}.sharing-form h3,.sharing-grant h3{font-size:14px;font-weight:600}.sharing-input-grid{display:grid;grid-template-columns:1fr 1fr;gap:19px;margin:22px 0}.sharing-input-grid label{display:flex;flex-direction:column;gap:9px;font-size:11px;min-width:0;color:#62765d}.sharing-input-grid input,.sharing-input-grid select{width:100%;min-width:0;background:#fff;border:1px solid #ccd7c7;border-radius:6px;padding:11px;font-size:12px;color:#365942;box-sizing:border-box}.sharing-input-grid small{font-size:10px;line-height:1.8;color:#86927a}.sharing-expiry{grid-column:1/-1}.sharing-scope-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.sharing-scope-grid fieldset{border:1px solid #dce4d5;border-radius:7px;padding:13px;min-width:0}.sharing-scope-grid legend{font-size:11px;padding:0 6px;color:#6d8267}.sharing-panel .sharing-choice{display:flex;align-items:flex-start;gap:10px;margin:12px 0;font-size:11px;line-height:1.8;color:#697d61}.sharing-panel .sharing-choice input[type=checkbox]{width:18px;height:18px;min-width:18px;flex:0 0 18px;appearance:auto;padding:0;margin:1px 0 0;accent-color:#3f6e50}.sharing-choice span{flex:1;min-width:0}.sharing-confirm{margin:21px 0!important}.sharing-primary,.sharing-secondary,.sharing-revoke{font-size:12px;border:1px solid #afc1a7;padding:12px 17px;border-radius:7px;background:#fff;color:#4c7149}.sharing-primary{background:#315f48;color:#fff;border-color:#315f48}.sharing-panel button:disabled{opacity:.48;cursor:not-allowed}.sharing-revoke{border-color:#cab99a;color:#897044;margin-top:10px}.sharing-grants{display:grid;gap:17px;margin-top:24px}.sharing-grant{border:1px solid #dfe6d8;border-radius:9px;padding:22px}.sharing-grant-head>span{font-size:10px;background:#f1f3e9;color:#7c866d;padding:6px 9px;border-radius:5px}.sharing-effective{font-size:11px;margin-top:14px;color:#997e47}.sharing-effective.active{color:#3d7d53}.sharing-empty{font-size:12px;padding:25px;text-align:center;background:#f8faf5;color:#8b9780;border-radius:7px}.sharing-message{font-size:12px;line-height:1.9;color:#846832;padding:12px 0}.sharing-refresh{margin-top:21px}.sharing-panel button:focus-visible,.sharing-panel input:focus-visible,.sharing-panel select:focus-visible,.sharing-panel summary:focus-visible{outline:3px solid #93bba0;outline-offset:3px}@media(max-width:650px){.sharing-panel{padding:24px 19px}.sharing-input-grid,.sharing-scope-grid{grid-template-columns:1fr}.sharing-form,.sharing-grant{padding:19px 15px}.sharing-panel dl>div{grid-template-columns:72px minmax(0,1fr);gap:10px}.sharing-primary,.sharing-revoke{width:100%}.sharing-list-header{align-items:flex-start}.sharing-heading h2{font-size:22px}}
</style>
