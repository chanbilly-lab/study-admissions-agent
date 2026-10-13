<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { createPublicPreviewApi, PublicPreviewError, type PublicOfferingsData, type PublicPreviewApi } from './publicClient'
const props = defineProps<{ api?: PublicPreviewApi }>()
const api = props.api ?? createPublicPreviewApi()
const year = ref<string | number>(''), data = ref<PublicOfferingsData | null>(null), busy = ref(false), message = ref('')
const expanded = ref(false)
let generation = 0, pending: AbortController | undefined
function changed() { generation++; pending?.abort(); data.value = null; busy.value = false; message.value = '' }
function toggle() { changed(); expanded.value = !expanded.value; if (!expanded.value) year.value = '' }
async function refresh() {
  if (!expanded.value) return
  const value = String(year.value)
  if (!/^[0-9]{1,4}$/.test(value) || Number(value) < 1) { message.value = '请明确填写入学年度。'; return }
  const current = ++generation; pending?.abort(); pending = new AbortController(); busy.value = true; data.value = null; message.value = ''
  try { const result = await api.offerings(Number(value), pending.signal); if (current === generation) data.value = result }
  catch (error) { if (current === generation) message.value = error instanceof PublicPreviewError ? error.message : '公共读取未确认。' }
  finally { if (current === generation) busy.value = false }
}
onUnmounted(changed)
</script>
<template>
  <section class="public-preview" aria-labelledby="public-preview-title">
    <h3 id="public-preview-title">匿名公共目录预览</h3>
    <p>不携带会话 Cookie；仅展示 T20 当前公共投影。管理审核或发布回执不能代替公共读取，范围总量未知。</p>
    <button type="button" data-testid="public-toggle" :aria-expanded="expanded" aria-controls="public-query-panel" @click="toggle">{{ expanded ? '收起匿名公共预览' : '展开匿名公共预览' }}</button>
    <div v-if="expanded" id="public-query-panel">
    <div class="public-query"><label>明确入学年度<input v-model="year" type="number" min="1" max="9999" step="1" data-testid="public-year" @input="changed"></label><button type="button" data-testid="public-refresh" :disabled="busy" @click="refresh">重新读取公共目录</button></div>
    <p v-if="message" role="alert">{{ message }}</p>
    <div v-if="data" data-testid="public-result">
      <p>{{ data.coverage.status === 'no_published_records' ? '当前范围没有可公开记录。' : '部分公开资料；不是全国完整覆盖。' }} 本页 {{ data.coverage.returned_count }} 条 · 覆盖总量和比例未知。</p>
      <article v-for="item in data.items" :key="`${item.release_id}:${item.id}:${item.version}`" class="public-item">
        <strong>{{ item.institution_name }} / {{ item.program_name }}</strong>
        <p v-if="item.is_synthetic" class="demo">DEMO 合成测试资料，不是真实招生依据。</p>
        <dl><div><dt>当前 release</dt><dd>{{ item.release_id }} / {{ item.release_version }}</dd></div><div><dt>入学年 / 项目版本</dt><dd>{{ item.entry_year }} / {{ item.version }}</dd></div><div><dt>要求快照</dt><dd>{{ item.requirements_version }}</dd></div><div><dt>规则版本</dt><dd>未编译（null）</dd></div></dl>
        <ul><li v-for="(fact, index) in item.facts" :key="index">{{ fact.field_key }}：{{ fact.value_text ?? `缺失（${fact.missing_reason ?? 'unknown'}）` }} {{ fact.unit ?? '' }} · {{ fact.claim_kind }}</li></ul>
      </article>
      <p v-if="data.page.has_more">尚有后续记录；此预览只读取当前一页，不推断全量。</p>
    </div>
    </div>
  </section>
</template>
<style scoped>
.public-preview{padding:24px;border:1px solid #d9e3d5;border-radius:10px;background:#f8faf4;min-width:0}.public-preview h3{font-size:16px}.public-preview p{font-size:11px;line-height:1.9;color:#6e7d66;margin:12px 0}.public-query{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:14px;margin:20px 0}.public-query label{display:flex;flex-direction:column;gap:8px;font-size:12px}.public-query input{font-size:12px}.public-query button{padding:12px 18px;background:white;border:1px solid #b6cbb9;border-radius:7px;color:#426b4c;font-size:12px}.public-item{border-top:1px solid #dae5d1;padding:20px 0;overflow-wrap:anywhere;font-size:12px}.public-item dl{font-size:10px;display:grid;gap:8px;margin:14px 0}.public-item dl>div{display:grid;grid-template-columns:96px minmax(0,1fr);gap:10px}.public-item dd{margin:0}.public-item ul{padding-left:18px;line-height:1.9}.public-item .demo{color:#735f33}@media(max-width:650px){.public-preview{padding:20px 16px}.public-query{grid-template-columns:1fr}}
</style>
