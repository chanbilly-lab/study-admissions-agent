<script setup lang="ts">
import { onUnmounted, watch } from 'vue'
import type { ReviewWorkspaceApi, SessionData } from '../reviews/client'
import { usePreparation } from './usePreparation'
const props = defineProps<{ api: ReviewWorkspaceApi; actor: SessionData }>()
const emit = defineEmits<{ sessionExpired: [] }>()
const model = usePreparation(props.api, () => emit('sessionExpired')), state = model.state
watch(() => props.actor, model.setActor, { immediate: true }); onUnmounted(model.dispose)
function file(event: Event) { const value = (event.target as HTMLInputElement).files?.[0]; if (value) void model.chooseOriginal(value) }
</script>
<template>
  <section class="rw-card" data-testid="preparation-panel" aria-labelledby="prep-title" :aria-busy="!!state.busy">
    <h3 id="prep-title">01 / 从有效导入行准备事实</h3><p>仅原批负责人可读取有效行。每个步骤单独确认和提交；任一步完成都不代表整链审核或发布完成。</p>
    <div class="rw-grid"><label>导入回执 UUID<input v-model="state.importId" data-testid="prep-import-id" :disabled="!!state.busy" @input="model.scopeChanged"></label><button type="button" data-testid="prep-load" :disabled="!!state.busy" @click="model.loadRows(false)">读取当前有效行</button></div>
    <p v-if="state.message" :role="state.error ? 'alert' : 'status'" class="rw-message" :class="{ error: state.error }">{{ state.message }}</p>
    <template v-if="state.page">
      <p>原批 {{ state.page.import_id }} · {{ state.page.total_rows }} 行 · 每页最多 20 行 · 来源版本 {{ state.page.source_version }}</p>
      <fieldset :disabled="!!state.busy" class="rw-rows"><legend>明确选择一行，不按数值或新旧自动选择</legend><label v-for="item in state.page.rows" :key="item.row_id" class="rw-check"><input type="radio" name="prepared-row" :checked="state.rowId === item.row_id" :data-testid="`prep-row-${item.row_id}`" @change="model.selectRow(item.row_id)"><span>行 {{ item.row.row_number }} · {{ item.row.field_key }} · {{ item.row.value_text ?? `缺失/${item.row.missing_reason}` }} {{ item.row.unit ?? '' }}<small>{{ item.row_id }}</small></span></label></fieldset>
      <button type="button" data-testid="prep-next-page" :disabled="!!state.busy || !state.page.next_cursor" @click="model.loadRows(true)">下一页有效行</button>
      <template v-if="model.selected()">
        <p>项目 {{ model.selected()!.row.offering_id }} / 版本 {{ model.selected()!.row.offering_version }} / 入学年 {{ model.selected()!.row.entry_year }}，均来自服务器原行，不能在本页修改。</p>
        <details><summary>重新选择自己的原文并核对哈希</summary><label>本机原文文件<input type="file" accept=".json,.csv" data-testid="prep-original-file" :disabled="!!state.busy" @change="file"></label><label>或粘贴自己持有的原文<textarea v-model="state.original" data-testid="prep-original-text" rows="5" maxlength="1048576" :disabled="!!state.busy" @input="model.originalChanged"></textarea></label><button type="button" data-testid="prep-verify-original" :disabled="!!state.busy" @click="model.verifyOriginal">核对本机原文字节 SHA-256</button><p data-testid="prep-original-status">{{ state.originalMessage }}</p><p>没有全文下载。原文不做 trim、补值或换行修复；本机哈希匹配不是权限或审核证明。</p></details>
        <div class="rw-grid"><label>文档引用代码<input v-model="state.reference" data-testid="prep-document-reference" maxlength="100" :disabled="!!state.busy" @input="model.definitionChanged"></label><label>原文语言<select v-model="state.language" data-testid="prep-language" :disabled="!!state.busy" @change="model.definitionChanged"><option disabled value="">明确选择</option><option value="zh-Hans">简体中文</option><option value="zh-Hant">繁体中文</option><option value="en">英语</option><option value="und">未确定</option></select></label></div>
        <label class="rw-check"><input v-model="state.confirmed.document" type="checkbox" data-testid="prep-document-confirm" :disabled="!!state.busy"><span>确认登记这份文档身份，合成引用使用 DEMO_。</span></label><button type="button" data-testid="prep-create-document" :disabled="!model.canDocument()" @click="model.createDocument">确认登记文档</button>
        <div v-if="state.document" class="rw-output" data-testid="prep-document-result">文档 {{ state.document.id }} · 当前版本 {{ state.document.current_version }}</div>
        <label class="rw-check"><input v-model="state.confirmed.version" type="checkbox" data-testid="prep-version-confirm" :disabled="!!state.busy || !state.document"><span>确认以服务器原批确切 file/hash 创建文档版本，使用当前版本 CAS。</span></label><button type="button" data-testid="prep-create-version" :disabled="!model.canVersion()" @click="model.createVersion">确认绑定原文件版本</button>
        <div v-if="state.version" class="rw-output" data-testid="prep-version-result">版本 {{ state.version.version }} · 原文字节 SHA-256 {{ state.version.document_sha256 }}</div>
        <div class="rw-grid"><label>UTF-8 起始字节（含）<input v-model="state.byteStart" data-testid="prep-byte-start" type="number" min="0" step="1" :disabled="!!state.busy" @input="model.spanChanged"></label><label>UTF-8 结束字节（不含）<input v-model="state.byteEnd" data-testid="prep-byte-end" type="number" min="1" step="1" :disabled="!!state.busy" @input="model.spanChanged"></label></div>
        <p>半开字节范围，不能填写字符位置；片段最多 4096 字节，不支持 PDF 页码。</p>
        <label class="rw-check"><input v-model="state.confirmed.snippet" type="checkbox" data-testid="prep-snippet-confirm" :disabled="!!state.busy || !state.version"><span>确认这个确切字节范围与原行项目、年份和版本关联。</span></label><button type="button" data-testid="prep-create-snippet" :disabled="!model.canSnippet()" @click="model.createSnippet">确认生成有界证据片段</button>
        <div v-if="state.snippet" class="rw-output" data-testid="prep-snippet-result"><strong>服务器原文片段 / 尚未人工审核</strong><pre>{{ state.snippet.text }}</pre><p>byte [{{ state.snippet.locator.byte_start }}, {{ state.snippet.locator.byte_end }}) · 物理行 {{ state.snippet.locator.line_start }}–{{ state.snippet.locator.line_end }}</p><code>{{ state.snippet.snippet_sha256 }}</code></div>
        <fieldset :disabled="!!state.busy" @input="model.classificationChanged" @change="model.classificationChanged"><legend>显式分类 · 不修改原值或自动补日期</legend><div class="rw-grid">
          <label>声明类别<select v-model="state.classification.claim" data-testid="prep-claim"><option disabled value="">明确选择</option><option v-for="value in ['unknown','minimum_requirement','typical_offer','historical_statistic','information']" :key="value" :value="value">{{ value }}</option></select></label>
          <label>规范单位<select v-model="state.classification.unit" data-testid="prep-unit"><option disabled value="">明确选择</option><option v-for="value in ['unknown','points','percent','fraction','CNY','GBP','item','people','text','ISO_DATE']" :key="value" :value="value">{{ value }}</option></select></label>
          <label>时间口径<select v-model="state.classification.period" data-testid="prep-period"><option disabled value="">明确选择</option><option v-for="value in ['unknown','not_applicable','academic_year','program','one_time','survey_period']" :key="value" :value="value">{{ value }}</option></select></label>
          <label>统计口径<select v-model="state.classification.basis" data-testid="prep-statistics-basis"><option disabled value="">明确选择</option><option v-for="value in ['unknown','not_applicable','admission','employment','other']" :key="value" :value="value">{{ value }}</option></select></label>
          <label>统计人群（空为 null）<input v-model="state.classification.population" data-testid="prep-population" maxlength="512"></label><label>分母定义（空为 null）<input v-model="state.classification.denominator" data-testid="prep-denominator" maxlength="512"></label>
          <label>毕业/统计届年（空为 null）<input v-model="state.classification.cohort" data-testid="prep-cohort" type="number" min="1" max="9999" step="1"></label><label>调查期（空为 null）<input v-model="state.classification.survey" data-testid="prep-survey" maxlength="100"></label><label class="rw-wide">已有明确日期事件 UUID（空为 null）<input v-model="state.classification.dateId" data-testid="prep-date-id" autocomplete="off"><small>此页不创建日期；缺 snapshot 仍为 draft / UNRESOLVED_DATE，不推断 UTC 或截止时刻。</small></label>
        </div></fieldset>
        <label class="rw-check"><input v-model="state.confirmed.fact" data-testid="prep-fact-confirm" type="checkbox" :disabled="!!state.busy || !state.snippet"><span>确认按上述显式分类创建类型化候选，未批准、未发布。</span></label><button type="button" data-testid="prep-create-fact" :disabled="!model.canFact()" @click="model.createFact">确认暂存类型化事实</button>
        <div v-if="state.fact" data-testid="prep-fact-result" class="rw-output"><strong>候选 {{ state.fact.id }}</strong><p>状态 {{ state.fact.state }} · 原值 {{ state.fact.value_text ?? '缺失' }} · 规范值 {{ state.fact.normalized_value ?? '未知' }}</p><p>hard_rule=false / publication_eligible=false。由另一账号从审核队列发现并独立审核。</p></div>
      </template>
    </template>
  </section>
</template>
