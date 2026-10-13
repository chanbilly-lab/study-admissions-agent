<script setup lang="ts">
import { onUnmounted, watch } from 'vue'
import type { SessionData } from '../../features/auth/client'
import type { AdminApi } from '../../features/admin/client'
import { useAdmin } from '../../features/admin/useAdmin'
import SourceForm from '../../features/admin/sources/SourceForm.vue'
import ImportPanel from '../../features/admin/imports/ImportPanel.vue'
const props = defineProps<{ actor: SessionData | null; api?: AdminApi }>()
const emit = defineEmits<{ sessionExpired: [] }>()
const admin = useAdmin(props.api, () => emit('sessionExpired'))
const state = admin.state
watch(() => props.actor, actor => { void admin.setActor(actor) }, { immediate: true })
onUnmounted(admin.dispose)
</script>

<template>
  <section class="admin-workspace" data-testid="admin-workspace" aria-labelledby="admin-title" :aria-busy="!!state.busy">
    <header class="admin-heading"><div><p class="admin-kicker">DATA WORKSPACE</p><h2 id="admin-title">来源与导入管理</h2><p>服务器检查当前数据管理员与认证强度。身份登录不会自动获得管理权限。</p></div><button type="button" class="admin-secondary" :disabled="!!state.busy || !actor" @click="admin.refresh">重新检查管理入口</button></header>
    <div class="admin-boundary"><strong>资料声明 → 隔离原文 → 候选暂存</strong><p>本页不提供审核或发布。来源 URL 仅文本登记，自动获取始终关闭，真实资料与公众发布仍有独立门槛。</p></div>
    <p v-if="state.context?.is_synthetic" class="admin-demo" data-testid="admin-demo"><strong>DEMO · 合成管理验收</strong> · 使用合成数据集、DEMO_ 来源及许可记录，不是真实官方招生依据。</p>
    <p data-testid="context-status" class="admin-status">{{ state.status === 'loading' ? '正在由服务器检查管理权限…' : !actor ? '尚未登录，未读取管理权限。' : state.context ? '管理状态已由服务器返回；每次操作仍会重验。' : '管理入口未开放、不可用或当前主体未获授权。' }}</p>
    <p v-if="state.message" data-testid="admin-message" class="admin-message" :class="{ error: state.notice === 'error' }" :role="state.notice === 'error' ? 'alert' : 'status'">{{ state.message }}</p>
    <div v-if="state.context" class="admin-columns">
      <section v-if="state.context.can_manage_sources" class="admin-card" aria-labelledby="source-title">
        <h3 id="source-title">01 / 来源声明</h3>
        <div class="source-query"><label>来源 UUID<input v-model="state.sourceQueryId" data-testid="source-query-id" autocomplete="off" :disabled="!!state.busy" @input="admin.queryChanged"></label><label>指定历史版本（可空）<input v-model="state.sourceQueryVersion" data-testid="source-query-version" type="number" min="1" step="1" :disabled="!!state.busy" @input="admin.queryChanged"></label><button type="button" class="admin-secondary" data-testid="source-query-button" :disabled="!admin.canManage()" @click="admin.loadSource">读取来源</button></div>
        <div v-if="state.source" data-testid="source-result" class="source-result"><strong>{{ state.source.publisher }}</strong><p>来源 {{ state.source.source_id }} · 读取版本 {{ state.source.version }} · 数据集 revision {{ state.source.dataset_revision }}</p><code>{{ state.source.entry_url }}</code><p>复查到期 {{ state.source.recheck_due_at }} · 官方性仅声明：{{ state.source.authority_claim }}</p></div>
        <div class="source-modes"><button type="button" class="admin-secondary" :disabled="!!state.busy" @click="admin.switchMode('create')">登记新来源</button><button type="button" class="admin-secondary" data-testid="source-revise" :disabled="!!state.busy || !state.source" @click="admin.switchMode('revise')">修改已读取来源</button></div>
        <SourceForm :draft="state.draft" :mode="state.mode" :busy="!!state.busy" :can-save="admin.canSave()" @changed="admin.sourceChanged" @save="admin.saveSource" />
      </section>
      <div v-else class="admin-card">服务器未开放来源管理。</div>
      <div v-if="state.context.can_import" class="admin-card"><ImportPanel :admin="admin" /></div>
      <div v-else class="admin-card">服务器未开放候选导入。</div>
    </div>
  </section>
</template>

<style scoped>
.admin-workspace{grid-column:1/-1;min-width:0;color:#254538}.admin-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:22px}.admin-kicker{font-size:10px;letter-spacing:2px;color:#819178;margin-bottom:8px}.admin-heading h2{font-size:24px}.admin-heading p:last-child{font-size:11px;color:#7a8974;margin-top:9px}.admin-boundary{background:#e9efe2;border:1px solid #cedbc4;border-radius:9px;padding:17px 20px}.admin-boundary strong{font-size:13px}.admin-boundary p{font-size:11px;color:#6f7f66;margin-top:6px;line-height:1.9}.admin-demo{padding:13px 16px;background:#f1f4e7;border:1px solid #d8dfc7;border-radius:7px;margin-top:15px;font-size:11px;line-height:1.9}.admin-status{font-size:12px;color:#7a8973;margin:18px 0}.admin-message{padding:14px 17px;border:1px solid #d4e1ce;background:#f6f9f0;border-radius:7px;font-size:12px;margin-bottom:20px;line-height:1.9;overflow-wrap:anywhere}.admin-message.error{background:#fcf2e5;border-color:#e8d3b3;color:#875f36}.admin-columns{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px;align-items:start}.admin-card{min-width:0;background:white;border:1px solid #dce6d7;border-radius:11px;padding:26px}.admin-card h3{font-size:16px}.admin-secondary{background:white;border:1px solid #b9cebd;color:#426b4c;border-radius:7px;padding:11px 14px;font-size:11px}.source-query{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;margin-top:19px}.source-query label{font-size:11px;color:#687e65;display:flex;flex-direction:column;gap:7px;min-width:0}.source-query input{font-size:11px}.source-query button{grid-column:1/-1}.source-result{padding:15px;border:1px solid #dbe5d1;background:#f6f9f0;border-radius:7px;margin-top:19px;overflow-wrap:anywhere}.source-result strong{font-size:12px}.source-result p{font-size:10px;color:#75846a;margin-top:7px;line-height:1.8}.source-result code{display:block;font:10px/1.9 ui-monospace,monospace;margin-top:8px;color:#576f49;white-space:pre-wrap;overflow-wrap:anywhere}.source-modes{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}@media(max-width:1050px){.admin-columns{grid-template-columns:1fr}.admin-card{padding:23px}}@media(max-width:650px){.admin-heading{align-items:flex-start;flex-direction:column}.admin-heading h2{font-size:22px}.admin-heading button{width:100%}.admin-card{padding:22px 16px}.source-query{grid-template-columns:1fr}.source-query button{grid-column:auto}.source-modes>*{flex:1}}
</style>
