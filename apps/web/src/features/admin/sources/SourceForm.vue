<script setup lang="ts">
import type { SourceDraft } from '../useAdmin'
defineProps<{ draft: SourceDraft; mode: 'create' | 'revise'; busy: boolean; canSave: boolean }>()
const emit = defineEmits<{ changed: []; save: [] }>()
const permissions = [{ value: 'pending', label: '待确认' }, { value: 'denied', label: '未获许可' }, { value: 'granted', label: '已登记许可' }]
</script>

<template>
  <form class="source-form" @submit.prevent="emit('save')">
    <fieldset :disabled="busy" @input="emit('changed')" @change="emit('changed')">
      <legend>{{ mode === 'create' ? '登记新来源' : '追加来源声明版本' }}</legend>
      <div class="source-grid">
        <label>候选数据集 UUID<input v-model="draft.datasetId" data-testid="source-dataset" :readonly="mode === 'revise'" autocomplete="off" required></label>
        <label>数据集预期版本<input v-model="draft.datasetRevision" data-testid="source-dataset-revision" type="number" min="1" step="1" :readonly="mode === 'revise'" required><small>与服务端当前 revision 比较，不覆盖并发变更。</small></label>
        <label v-if="mode === 'create'">来源引用代码<input v-model="draft.reference" data-testid="source-reference" maxlength="100" autocomplete="off" required><small>合成来源须用 DEMO_ 前缀。</small></label>
        <label>出版者 / 来源名称<input v-model="draft.publisher" data-testid="source-publisher" maxlength="200" autocomplete="off" required></label>
        <label class="source-wide">来源 URL · 只登记，不访问<input v-model="draft.url" data-testid="source-url" type="text" maxlength="2048" autocomplete="off" required><small>不跳转、不抓取；地址不能代替使用许可。</small></label>
        <label>资料用途<select v-model="draft.dataType" data-testid="source-data-type" required><option disabled value="">明确选择资料类型</option><option value="entry_requirements">入学要求</option><option value="application_dates">申请日期</option><option value="regional_cutoffs">地区分数线</option><option value="admission_observations">历史录取统计</option><option value="curriculum">培养与课程</option><option value="outcomes">毕业去向</option><option value="institution_directory">机构目录</option></select></label>
        <label>官方性声明<select v-model="draft.authority" data-testid="source-authority"><option value="unclassified">尚未分类</option><option value="claimed_official">登记者声明官方</option><option value="not_official">非官方</option></select><small>声明不代表系统已核验真实官方依据。</small></label>
        <label class="source-wide">适用范围说明<textarea v-model="draft.scope" data-testid="source-scope" maxlength="1000" rows="3" required></textarea></label>
        <label>人工导入许可<select v-model="draft.manual" data-testid="source-manual-permission"><option v-for="permission in permissions" :key="permission.value" :value="permission.value">{{ permission.label }}</option></select></label>
        <label>公开使用许可<select v-model="draft.publication" data-testid="source-publication-permission"><option v-for="permission in permissions" :key="permission.value" :value="permission.value">{{ permission.label }}</option></select></label>
        <label>自动获取许可声明<select v-model="draft.automated" data-testid="source-auto-permission"><option v-for="permission in permissions" :key="permission.value" :value="permission.value">{{ permission.label }}</option></select><small>自动获取始终关闭；这里只登记声明。</small></label>
        <label>复查间隔（天）<input v-model="draft.recheckDays" data-testid="source-recheck" type="number" min="1" max="730" step="1" required></label>
        <label class="source-wide">许可依据<textarea v-model="draft.basis" data-testid="source-basis" maxlength="2000" rows="2"></textarea><small>任一许可不是“待确认”时，依据和记录代码都必须填写；全部待确认时都留空。</small></label>
        <label class="source-wide">许可记录代码<input v-model="draft.permissionReference" data-testid="source-permission-reference" maxlength="100" autocomplete="off"><small>合成许可记录须用 DEMO_ 前缀。</small></label>
      </div>
      <label class="source-check"><input v-model="draft.manualEnabled" data-testid="source-manual-enabled" type="checkbox"><span>请求启用人工导入（须已登记对应许可；服务端仍逐次验证）</span></label>
    </fieldset>
    <label class="source-check"><input v-model="draft.confirmed" data-testid="source-confirm" type="checkbox" :disabled="busy"><span>我明确确认本次来源声明。保存不代表事实审核或公开发布。</span></label>
    <button class="admin-button" type="submit" data-testid="source-save" :disabled="!canSave">{{ mode === 'create' ? '确认登记来源' : '确认追加版本' }}</button>
  </form>
</template>

<style scoped>
.source-form{margin-top:20px}.source-form fieldset{margin:0;padding:0;border:0;min-width:0}.source-form legend{font-size:15px;font-weight:600;margin-bottom:18px}.source-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px}.source-grid label{display:flex;flex-direction:column;gap:7px;font-size:12px;min-width:0;color:#486456}.source-grid input,.source-grid select,.source-grid textarea{font-size:12px;width:100%;min-width:0}.source-grid textarea{resize:vertical;border:1px solid #cfdad2;border-radius:6px;padding:10px 12px;font:inherit;line-height:1.6}.source-grid small{font-size:10px}.source-wide{grid-column:1/-1}.source-check{display:flex;align-items:flex-start;gap:9px;font-size:11px;line-height:1.8;margin:19px 0;color:#526e5a}.source-check input{width:16px;height:16px;min-height:16px;flex:0 0 16px;margin-top:2px}.admin-button{background:#1b6453;border:0;color:white;border-radius:7px;font-size:12px;padding:12px 18px}.admin-button:disabled{opacity:.45}@media(max-width:650px){.source-grid{grid-template-columns:1fr}.source-wide{grid-column:auto}.admin-button{width:100%}}
</style>
