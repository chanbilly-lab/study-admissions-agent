<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import type { SessionData } from '../../features/auth/client'
import { createReviewWorkspaceApi, ReviewWorkspaceError, type ReviewContextData, type ReviewWorkspaceApi } from '../../features/admin/reviews/client'
import type { PublicPreviewApi } from '../../features/admin/releases/publicClient'
import PreparationPanel from '../../features/admin/preparation/PreparationPanel.vue'
import ReviewPanel from '../../features/admin/reviews/ReviewPanel.vue'
import ReleasePanel from '../../features/admin/releases/ReleasePanel.vue'
import PublicReleasePreview from '../../features/admin/releases/PublicReleasePreview.vue'
const props = defineProps<{ actor: SessionData | null; api?: ReviewWorkspaceApi; publicApi?: PublicPreviewApi }>()
const emit = defineEmits<{ sessionExpired: [] }>()
const api = props.api ?? createReviewWorkspaceApi(), context = ref<ReviewContextData | null>(null), message = ref(''), busy = ref(false)
let generation = 0, pending: AbortController | undefined
async function refresh() {
  const current = ++generation; pending?.abort(); context.value = null; message.value = ''; busy.value = false
  if (!props.actor) { message.value = '尚未登录，未读取私有审核权限。'; return }
  pending = new AbortController(); busy.value = true
  try {
    const result = await api.context(pending.signal)
    if (current !== generation) return
    if (result.is_synthetic !== props.actor?.is_synthetic) throw new ReviewWorkspaceError(200)
    context.value = result; message.value = '服务器已返回独立操作能力；每次执行仍需即时权限与证明。'
  } catch (error) {
    if (current === generation) { message.value = error instanceof ReviewWorkspaceError ? error.message : '管理能力读取未确认。'; if (error instanceof ReviewWorkspaceError && error.status === 401) emit('sessionExpired') }
  } finally { if (current === generation) busy.value = false }
}
watch(() => props.actor, () => { void refresh() }, { immediate: true })
onUnmounted(() => { generation++; pending?.abort(); context.value = null })
</script>
<template>
  <section class="review-workspace" data-testid="review-release-workspace" aria-labelledby="review-workspace-title">
    <header class="rw-heading"><div><p class="rw-kicker">EVIDENCE / REVIEW / RELEASE</p><h2 id="review-workspace-title">逐项核验，明确发布。</h2><p>原文准备、独立审核、公开许可分开确认。真实资料处理与公众上线门槛继续保留。</p></div><button type="button" :disabled="busy || !actor" @click="refresh">重新检查审核与发布能力</button></header>
    <p v-if="context?.is_synthetic" class="rw-boundary" data-testid="review-demo">DEMO · 合成隔离验收。不是真实官方招生依据，不代表已完成真实人工审核或正式发布。</p>
    <p data-testid="review-context-status" :role="context ? 'status' : 'alert'">{{ busy ? '正在由服务器检查…' : message }}</p>
    <template v-if="actor && context">
      <PreparationPanel v-if="context.can_prepare" :actor="actor" :api="api" @session-expired="emit('sessionExpired')" /><p v-else class="rw-closed">服务器未开放原批准备能力。</p>
      <ReviewPanel v-if="context.can_review" :actor="actor" :api="api" @session-expired="emit('sessionExpired')" /><p v-else class="rw-closed">服务器未开放独立审核能力。</p>
      <ReleasePanel v-if="context.can_publish || context.can_withdraw" :actor="actor" :api="api" :can-publish="context.can_publish" :can-withdraw="context.can_withdraw" @session-expired="emit('sessionExpired')" /><p v-else class="rw-closed">服务器未开放发布或撤回能力。</p>
    </template>
    <PublicReleasePreview :api="publicApi" />
  </section>
</template>
<style scoped>
.review-workspace{grid-column:1/-1;min-width:0;color:#284b3b;display:grid;gap:24px}.rw-heading{display:flex;align-items:center;justify-content:space-between;gap:22px}.rw-heading h2{font-size:25px}.rw-heading p{font-size:11px;color:#75876c;line-height:1.9;margin-top:10px}.rw-heading .rw-kicker{font-size:10px;letter-spacing:2px;margin-bottom:8px;color:#8a967c}.review-workspace>p{font-size:12px;line-height:1.9}.review-workspace :deep(button){font-size:12px;border:1px solid #b7cdbb;border-radius:7px;background:#fff;color:#3c674b;padding:11px 16px;white-space:normal;overflow-wrap:anywhere}.review-workspace :deep(button:disabled){opacity:.45}.review-workspace :deep(button:focus-visible),.review-workspace :deep(input:focus-visible),.review-workspace :deep(select:focus-visible){outline:3px solid #8cb6a4;outline-offset:3px}.review-workspace :deep(.rw-card){padding:26px;border:1px solid #dae5d6;border-radius:11px;background:#fff;min-width:0}.review-workspace :deep(h3){font-size:17px;margin-bottom:14px}.review-workspace :deep(h4){font-size:12px;margin-bottom:12px}.review-workspace :deep(p){font-size:11px;line-height:1.95;margin:12px 0;color:#718067;overflow-wrap:anywhere}.review-workspace :deep(fieldset){border:0;padding:0;margin:22px 0;min-width:0}.review-workspace :deep(legend){font-size:13px;font-weight:600;margin-bottom:14px}.review-workspace :deep(label){font-size:12px;display:flex;flex-direction:column;gap:8px;min-width:0;color:#476652}.review-workspace :deep(input),.review-workspace :deep(select),.review-workspace :deep(textarea){font-size:12px;min-width:0;width:100%}.review-workspace :deep(textarea){border:1px solid #d0dcd0;border-radius:7px;padding:11px;resize:vertical;font:12px/1.7 ui-monospace,monospace}.review-workspace :deep(.rw-grid){display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:20px 0;align-items:end}.review-workspace :deep(.rw-wide){grid-column:1/-1}.review-workspace :deep(.rw-check){display:flex;flex-direction:row;gap:9px;align-items:flex-start;font-size:11px;line-height:1.9;margin:18px 0}.review-workspace :deep(.rw-check input){width:16px;height:16px;min-height:16px;flex:0 0 16px;margin-top:3px}.review-workspace :deep(small){display:block;font-size:10px;color:#87937a;overflow-wrap:anywhere}.review-workspace :deep(.rw-output){padding:17px;border:1px solid #d8e5d1;border-radius:7px;background:#f7faf3;margin:20px 0;overflow-wrap:anywhere;min-width:0;font-size:11px}.review-workspace :deep(.rw-output>button){margin:5px}.review-workspace :deep(.rw-message){border-left:3px solid #8eb795;padding:12px 15px;background:#f3f7ee}.review-workspace :deep(.rw-message.error){border-color:#cda781;background:#fdf3e5;color:#875d3a}.review-workspace :deep(pre){white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.9 ui-monospace,monospace;max-height:380px;overflow:auto}.review-workspace :deep(code){white-space:pre-wrap;overflow-wrap:anywhere;font-size:10px}.review-workspace :deep(.rw-side-by-side){display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-items:start}.review-workspace :deep(dl){display:grid;gap:10px;font-size:10px}.review-workspace :deep(dl>div){display:grid;grid-template-columns:100px minmax(0,1fr);gap:10px}.review-workspace :deep(dd){margin:0;line-height:1.8;overflow-wrap:anywhere}.review-workspace :deep(.rw-gaps){font-size:11px;color:#8b643b;line-height:1.9;padding-left:18px}.review-workspace :deep(summary){font-size:12px;cursor:pointer;margin:20px 0}.review-workspace :deep(.rw-boundary){background:#eff3e5;border:1px solid #d3ddc3;padding:14px;border-radius:7px}.rw-closed{padding:20px;background:#f5f7ef;border-radius:8px}@media(max-width:800px){.review-workspace :deep(.rw-side-by-side){grid-template-columns:1fr}}@media(max-width:650px){.rw-heading{flex-direction:column;align-items:flex-start}.rw-heading h2{font-size:23px}.rw-heading button{width:100%}.review-workspace :deep(.rw-card){padding:22px 16px}.review-workspace :deep(.rw-grid){grid-template-columns:1fr}.review-workspace :deep(.rw-wide){grid-column:auto}.review-workspace :deep(dl>div){grid-template-columns:85px minmax(0,1fr)}}
</style>
