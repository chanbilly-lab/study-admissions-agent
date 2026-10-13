<script setup lang="ts">
import { nextTick, onUnmounted, ref, watch } from 'vue'
import type { PublicEvidenceData } from '../../../../../packages/contracts/v2/public_catalog/generated'
import { scopeKeys, scopeLabels, scopeText } from '../catalog/presentation'
const props = defineProps<{ evidence: PublicEvidenceData | null; loading: boolean; message: string }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
let previousFocus: HTMLElement | null = null, generation = 0
function restore() { if (previousFocus?.isConnected) previousFocus.focus(); previousFocus = null }
watch(() => props.loading || !!props.evidence || !!props.message, async open => {
  const current = ++generation
  if (open && !dialog.value?.open) previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  await nextTick()
  if (current !== generation) return
  if (open && !dialog.value?.open) dialog.value?.showModal()
  else if (!open && dialog.value?.open) { dialog.value.close(); restore() }
}, { immediate: true })
onUnmounted(() => { generation++; dialog.value?.close(); restore() })
</script>
<template>
  <dialog ref="dialog" class="public-evidence-dialog" data-testid="public-evidence-dialog" aria-labelledby="public-evidence-title" @cancel.prevent="emit('close')">
    <header><div><p class="kicker">RELEASE-BOUND EVIDENCE</p><h2 id="public-evidence-title">公开证据与准确定位</h2></div><button type="button" data-testid="public-evidence-close" aria-label="关闭公开证据" @click="emit('close')">×</button></header>
    <p v-if="loading" role="status">正在读取此发布版本允许公开的片段…</p><p v-else-if="message" role="alert" class="notice">{{ message }}</p>
    <template v-else-if="evidence">
      <p v-if="evidence.is_synthetic" class="notice"><strong>DEMO · 合成证据</strong>。即使官方性声明为 claimed_official，也不是真实官方招生依据。</p>
      <dl class="metadata"><div><dt>发布者 / 官方性声明</dt><dd>{{ evidence.publisher }} / {{ evidence.authority_claim }}</dd></div><div><dt>年度 / 项目版本</dt><dd>{{ evidence.entry_year }} / {{ evidence.offering_version }}</dd></div><div><dt>发布 ID / 版本</dt><dd>{{ evidence.release_id }} / {{ evidence.release_version }}</dd></div><div><dt>证据 / 项目 ID</dt><dd>{{ evidence.evidence_id }} / {{ evidence.offering_id }}</dd></div><div><dt>UTF-8 字节范围</dt><dd>[{{ evidence.locator.byte_start }}, {{ evidence.locator.byte_end }}) · 半开区间</dd></div><div><dt>实际物理行</dt><dd>{{ evidence.locator.line_start }} 至 {{ evidence.locator.line_end }}</dd></div><div><dt>页码 / 章节</dt><dd>未提供（null）</dd></div><div><dt>语言</dt><dd>{{ evidence.language }}</dd></div></dl>
      <h3>公开原文片段</h3><blockquote data-testid="public-evidence-quote">{{ evidence.quote }}</blockquote>
      <dl class="metadata"><div><dt>原文 SHA256</dt><dd>{{ evidence.document_sha256 }}</dd></div><div><dt>片段 SHA256</dt><dd>{{ evidence.snippet_sha256 }}</dd></div><div><dt>要求版本</dt><dd>{{ evidence.requirements_version }}</dd></div><div><dt>机构国家 / 层次</dt><dd>{{ evidence.scope.country }} / 本科</dd></div><div v-for="key in scopeKeys" :key="key"><dt>{{ scopeLabels[key] }}</dt><dd>{{ scopeText(evidence.scope[key]) }}</dd></div></dl>
      <p class="note">仅显示当前发布允许公开的有限片段。没有原附件或来源 URL；不会执行原文指令、解析原文补造日期或打开外部链接。</p>
    </template>
  </dialog>
</template>
<style scoped>
.public-evidence-dialog{width:min(760px,calc(100vw - 30px));max-height:calc(100dvh - 40px);margin:auto;border:1px solid #c7d9bc;border-radius:13px;background:#fff;color:#294c3b;padding:28px;overflow:auto;box-shadow:0 25px 90px #18382c30}.public-evidence-dialog::backdrop{background:#1a372e66}header{display:flex;justify-content:space-between;align-items:flex-start;gap:17px}.kicker{font-size:10px;letter-spacing:1.5px;color:#859679;margin:0 0 8px}h2{font-size:22px;margin:0}header button{width:32px;height:32px;flex:0 0 32px;border:1px solid #d4dfcc;background:#fff;border-radius:6px;color:#6e8761;font-size:22px}.notice{background:#f9f0df;border:1px solid #e5d7b9;color:#826b3d;border-radius:6px;padding:13px 16px;font-size:12px;line-height:1.9;margin:20px 0}.metadata{display:grid;gap:11px;font-size:11px;margin:24px 0;overflow-wrap:anywhere}.metadata>div{display:grid;grid-template-columns:126px minmax(0,1fr);gap:12px}.metadata dt{color:#8b987e}.metadata dd{margin:0;line-height:1.8}h3{font-size:12px;margin-top:24px}blockquote{margin:12px 0;background:#f5f8f0;border:1px solid #dce6d2;border-left:3px solid #90a879;border-radius:5px;padding:18px;font-size:12px;line-height:1.9;white-space:pre-wrap;overflow-wrap:anywhere}.note{font-size:10px;line-height:1.9;color:#8a967e}.public-evidence-dialog :focus-visible{outline:3px solid #8cb6a4;outline-offset:3px}@media(max-width:650px){.public-evidence-dialog{padding:20px 16px}h2{font-size:19px}.metadata>div{grid-template-columns:1fr;gap:3px}}
</style>
