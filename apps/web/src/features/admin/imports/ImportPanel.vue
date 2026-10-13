<script setup lang="ts">
import type { useAdmin } from '../useAdmin'
const props = defineProps<{ admin: ReturnType<typeof useAdmin> }>()
const state = props.admin.state
function fileChanged(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) void props.admin.chooseFile(file)
}
</script>

<template>
  <section class="import-panel" aria-labelledby="import-title">
    <h3 id="import-title">02 / 隔离原文与候选导入</h3>
    <p>仅 UTF-8 JSON / CSV，净原文 ≤1 MiB、同步导入 ≤200 行。原文不改写；没有 PDF、自动抽取或发布入口。</p>
    <p v-if="!state.source" class="import-note">先登记或读取已许可的来源版本，再保存原文。</p>
    <template v-else>
      <p class="import-note">绑定来源 <code>{{ state.source.source_id }}</code> · 版本 {{ state.source.version }}。许可、原文件与期限由服务端再次核对。</p>
      <fieldset :disabled="!admin.canImport()" class="import-fields">
        <label>选择 UTF-8 原文文件<input data-testid="original-file-input" type="file" accept=".json,.csv,application/json,text/csv" @change="fileChanged"></label>
        <label>显示文件名<input v-model="state.filename" data-testid="original-filename" maxlength="255" autocomplete="off" @input="admin.originalChanged"></label>
        <label>原文格式<select v-model="state.contentType" data-testid="original-content-type" @change="admin.originalChanged"><option value="application/json">JSON</option><option value="text/csv">CSV</option></select></label>
        <label class="import-wide">原文内容 · 可粘贴或由文件读取<textarea v-model="state.content" data-testid="original-content" rows="8" maxlength="1048576" spellcheck="false" @input="admin.originalChanged"></textarea></label>
      </fieldset>
      <label class="import-check"><input v-model="state.fileConfirmed" data-testid="original-confirm" type="checkbox" :disabled="!admin.canImport()"><span>我确认保存上述原文字节到来源隔离区，不代表安全扫描或审核通过。</span></label>
      <button type="button" class="admin-button" data-testid="original-upload" :disabled="!admin.canUpload()" @click="admin.upload">确认隔离保存原文</button>
      <div v-if="state.file" data-testid="file-receipt" class="receipt">
        <strong>quarantined · 原文已隔离</strong>
        <dl><div><dt>文件标识</dt><dd>{{ state.file.id }}</dd></div><div><dt>净字节 / 格式</dt><dd>{{ state.file.size_bytes }} / {{ state.file.media_type }}</dd></div><div><dt>SHA-256</dt><dd>{{ state.file.sha256 }}</dd></div><div><dt>保存到期</dt><dd>{{ state.file.expires_at }}</dd></div></dl>
      </div>
      <label class="import-check"><input v-model="state.importConfirmed" data-testid="import-confirm" type="checkbox" :disabled="!admin.canImport() || !state.file"><span>我确认按当前来源版本和上述原文哈希进行整批候选导入。任何坏行都会拒绝整批。</span></label>
      <button type="button" class="admin-button" data-testid="import-submit" :disabled="!admin.canSubmitImport()" @click="admin.submitImport">确认导入候选</button>
    </template>
    <div class="import-query"><label>已有导入回执 UUID<input v-model="state.importQueryId" data-testid="import-query-id" autocomplete="off" :disabled="!!state.busy" @input="state.result = null"></label><button type="button" class="admin-secondary" data-testid="import-query-button" :disabled="!admin.canImport()" @click="admin.loadImport">重新读取回执</button></div>
    <div v-if="state.result" data-testid="import-result" class="receipt" :class="{ rejected: state.result.status === 'rejected' }">
      <strong>{{ state.result.status === 'staged' ? 'staged · 候选已暂存，尚未审核或发布' : 'rejected · 整批被拒绝，候选写入为 0' }}</strong>
      <dl><div><dt>回执 UUID</dt><dd>{{ state.result.id }}</dd></div><div><dt>总行数</dt><dd>{{ state.result.total_rows === null ? '结构未知（不是 0 行）' : state.result.total_rows }}</dd></div><div><dt>暂存 / 错误</dt><dd>{{ state.result.staged_rows }} / {{ state.result.error_count }}</dd></div><div><dt>幂等回放</dt><dd>{{ state.result.replayed ? '是 · 已按当前权限重新读取' : '否' }}</dd></div></dl>
      <div v-if="state.result.errors.length" data-testid="import-errors" class="error-table"><table><caption>固定错误位置与代码，不显示原始坏值</caption><thead><tr><th>行号</th><th>字段</th><th>代码</th></tr></thead><tbody><tr v-for="(error, index) in state.result.errors" :key="index"><td>{{ error.row_number === 0 ? '文档结构' : error.row_number }}</td><td>{{ error.field }}</td><td>{{ error.code }}</td></tr></tbody></table></div>
    </div>
  </section>
</template>

<style scoped>
.import-panel{min-width:0}.import-panel h3{font-size:16px}.import-panel>p{font-size:11px;color:#788776;margin-top:11px;line-height:1.9}.import-note{background:#f2f5eb;padding:13px;border-radius:6px;overflow-wrap:anywhere}.import-fields{padding:0;border:0;margin:19px 0;display:grid;grid-template-columns:1fr 1fr;gap:15px;min-width:0}.import-fields label,.import-query label{display:flex;flex-direction:column;gap:7px;font-size:12px;color:#486456;min-width:0}.import-fields input,.import-fields select,.import-query input{font-size:12px}.import-wide{grid-column:1/-1}.import-fields textarea{width:100%;min-width:0;resize:vertical;border:1px solid #cfdad2;border-radius:6px;padding:11px;font:12px/1.7 ui-monospace,monospace;color:#355249;background:#fafcf8}.import-check{display:flex;gap:9px;font-size:11px;line-height:1.8;margin:18px 0;color:#526e5a;align-items:flex-start}.import-check input{width:16px;height:16px;min-height:16px;flex:0 0 16px;margin-top:2px}.admin-button,.admin-secondary{border-radius:7px;padding:12px 17px;font-size:12px}.admin-button{border:0;background:#1b6453;color:white}.admin-secondary{border:1px solid #b9cebd;color:#426b4c;background:white}.import-query{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:11px;margin-top:28px}.receipt{margin-top:20px;border:1px solid #cedecb;border-radius:7px;padding:16px;background:#f7faf3;min-width:0}.receipt strong{font-size:12px;line-height:1.8}.receipt.rejected{border-color:#e2c6b0;background:#fdf4eb;color:#855b3c}.receipt dl{font-size:10px;display:grid;gap:9px;margin:15px 0 0}.receipt dl>div{display:grid;grid-template-columns:88px minmax(0,1fr);gap:9px}.receipt dt{color:#8a927b}.receipt dd{margin:0;overflow-wrap:anywhere;line-height:1.8}.error-table{overflow:auto;margin-top:17px}.error-table table{width:100%;text-align:left;border-collapse:collapse;font-size:10px}.error-table caption{text-align:left;margin-bottom:10px}.error-table th,.error-table td{padding:8px;border-bottom:1px solid #ecdccd;overflow-wrap:anywhere}@media(max-width:650px){.import-fields,.import-query{grid-template-columns:1fr}.import-wide{grid-column:auto}.admin-button,.admin-secondary{width:100%}.error-table table{min-width:320px}}
</style>
