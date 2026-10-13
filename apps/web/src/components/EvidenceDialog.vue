<script setup lang="ts">
import { nextTick, onUnmounted, ref, watch } from 'vue'
import type { Evidence } from '../../../../packages/contracts/index'
const props = defineProps<{ evidence: Evidence | null; loading: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
let previousFocus: HTMLElement | null = null
let generation = 0
function restoreFocus() {
  if (previousFocus?.isConnected) previousFocus.focus()
  previousFocus = null
}
const reviewLabels: Record<string, string> = { demo_reviewed: '演示审核通过', review_required: '待审核', conflicted: '有冲突', expired: '已过期' }
watch(() => props.loading || !!props.evidence, async (open) => {
  const current = ++generation
  if (open && !dialog.value?.open) previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  await nextTick()
  if (current !== generation || !dialog.value?.isConnected) return
  if (open && !dialog.value.open) dialog.value.showModal()
  else if (!open) { if (dialog.value.open) dialog.value.close(); restoreFocus() }
}, { immediate: true })
onUnmounted(() => { generation++; dialog.value?.close(); restoreFocus() })
</script>

<template>
  <dialog ref="dialog" class="evidence-dialog" aria-labelledby="evidence-title" @cancel.prevent="emit('close')">
    <div class="dialog-heading"><div><span class="eyebrow">SYNTHETIC EVIDENCE</span><h2 id="evidence-title">合成规则证据</h2></div><button type="button" class="icon-button" aria-label="关闭证据" autofocus @click="emit('close')">×</button></div>
    <div class="notice warning">DEMO · 这份证据是合成夹具，不是真实官方招生依据。</div>
    <p v-if="loading" role="status">正在读取证据原文与版本信息…</p>
    <template v-else-if="evidence">
      <h3>{{ evidence.title }}</h3>
      <span class="tiny-label">合成原文片段</span><blockquote class="evidence-excerpt">{{ evidence.excerpt }}</blockquote>
      <dl class="evidence-metadata"><div><dt>适用年度 / 路径</dt><dd>{{ evidence.entry_year }} · {{ evidence.country }} · {{ evidence.pathway }} · {{ evidence.province ?? '生源范围未提供' }}</dd></div><div><dt>适用项目</dt><dd>{{ evidence.offering_ids.join(' · ') }}</dd></div><div><dt>申请身份</dt><dd>{{ evidence.applicant_category }}</dd></div><div><dt>审核状态</dt><dd>{{ reviewLabels[evidence.review_status] }}（{{ evidence.review_status }}）</dd></div><div><dt>合成来源</dt><dd>{{ evidence.source_url }}</dd></div><div><dt>原文定位</dt><dd>{{ evidence.locator }}</dd></div><div><dt>数据截至</dt><dd>{{ evidence.data_as_of }}</dd></div><div><dt>不可变版本</dt><dd>{{ evidence.document_version_id }}</dd></div><div><dt>SHA256</dt><dd class="hash">{{ evidence.document_sha256 }}</dd></div></dl>
      <p class="muted">证据 ID：{{ evidence.id }} · is_synthetic = true</p>
    </template>
  </dialog>
</template>
