<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { ReferenceFilters, StatisticsResource } from '../reference/client'
import { useReferenceQuery } from '../reference/query'
import CutoffResults from './CutoffResults.vue'

const mainland = ['北京','天津','河北','山西','内蒙古','辽宁','吉林','黑龙江','上海','江苏','浙江','安徽','福建','江西','山东','河南','湖北','湖南','广东','广西','海南','重庆','四川','贵州','云南','西藏','陕西','甘肃','青海','宁夏','新疆']
const regions = [...mainland.map((name, index) => ({ key: `cn_region_${String(index + 1).padStart(2, '0')}`, name })), { key: 'hk', name: '香港' }, { key: 'mo', name: '澳门' }, { key: 'tw', name: '台湾' }]
const kinds: { key: StatisticsResource; name: string }[] = [{ key: 'coverage', name: '来源与覆盖' }, { key: 'province_cutoffs', name: '省级分段线与控制线' }, { key: 'score_distributions', name: '分数分布' }, { key: 'admissions', name: '历史投档与录取观测' }]
const form = reactive({ kind: 'province_cutoffs' as StatisticsResource, year: '2026', region: 'cn_region_11', subject: '', batch: '', round: '' })
const optional = [{ key: 'subject', label: '考试科类原称' }, { key: 'batch', label: '批次原称' }, { key: 'round', label: '轮次原称' }] as const
const { result, loading, error, clear, run } = useReferenceQuery()
const localCutoffs = computed(() => result.value?.schema_version === 'reference.cutoffs.local.1' ? result.value : null)
const emptyResult = computed(() => result.value?.schema_version === 'reference.minimal.1' ? result.value : null)
watch(form, clear, { flush: 'sync' })
const reasons = { source_not_enabled: '来源尚未启用，未取得已发布资料。这不代表官方尚未公布。', not_applicable: '普通高考统计不适用于所选港澳台路径，需按其独立招生体系查询。', scope_incomplete: '考试科类、批次或轮次范围不完整，当前不能形成同口径统计。真实来源也未启用。' }
function submit() {
  clear()
  if (!/^[1-9][0-9]{0,3}$/.test(form.year) || optional.some(field => form[field.key].length > 256)) { error.value = '请填写1–9999的完整资料年度；可选原称最多256字。'; return }
  const filters: ReferenceFilters = { year: Number(form.year), region_key: form.region }
  if (form.kind !== 'coverage') Object.assign(filters, { pathway: 'ordinary_gaokao', subject_category: form.subject.trim() || null, batch: form.batch.trim() || null, round: form.round.trim() || null })
  if (form.kind === 'admissions') Object.assign(filters, { institution_code: null, group_code: null, program_code: null })
  void run({ resource: form.kind, filters })
}
</script>

<template>
  <section class="panel" aria-labelledby="statistics-title">
    <div class="query-heading"><div><p class="section-label">资料范围</p><h2 id="statistics-title">全国历史统计查询</h2></div><span class="query-badge">只读查询</span></div>
    <p class="intro">请选择资料范围后查询。页面不会自动查询、填补缺年资料或生成排名。</p>
    <form @submit.prevent="submit" class="reference-form">
      <div class="primary-filters">
        <label>资料类型<select v-model="form.kind"><option v-for="kind in kinds" :key="kind.key" :value="kind.key">{{ kind.name }}</option></select></label>
        <label>资料年度<input v-model="form.year" inputmode="numeric" maxlength="4" required aria-describedby="year-help" /></label>
        <label>地区<select v-model="form.region"><option v-for="region in regions" :key="region.key" :value="region.key">{{ region.name }}</option></select></label>
      </div>
      <p id="year-help" class="field-help">按实际考试或招生年度查询。港澳台普通高考统计不适用，需使用独立招生体系；兵团仍属新疆子范围。</p>
      <details v-if="form.kind !== 'coverage'" class="scope-details">
        <summary>细分口径（可选）<span v-if="form.subject || form.batch || form.round">已填写筛选</span></summary>
        <p class="field-help">按来源的原始名称填写；不确定时可留空。展开或收起不会清除已填写的条件。</p>
        <div class="secondary-filters"><label v-for="field in optional" :key="field.key">{{ field.label }}（可选）<input v-model="form[field.key]" maxlength="256" /></label></div>
      </details>
      <div class="query-actions"><p>修改筛选会清除旧结果，需要重新查询。</p><button class="button primary" type="submit" :disabled="loading">{{ loading ? '查询中…' : '查询当前范围' }}</button></div>
    </form>
    <p class="notice compact"><strong>当前本地范围：浙江2026普通类三条省线</strong><br />一段线与本科控制线分别定义；投档与最终录取不同，学校、院校专业组与专业粒度不得折为一个学校分数。其他资料缺口按结果展示。</p>
    <p class="screen-reader-status" role="status" aria-live="polite" aria-atomic="true">{{ loading ? '正在查询所选范围。' : error ? '查询未完成，请查看错误说明。' : localCutoffs?.reference_available ? '查询完成，已返回本地复核省线与来源。' : result ? '查询完成，当前范围存在资料缺口。' : '尚未查询。' }}</p>
    <section class="query-results" aria-labelledby="statistics-results-title" :aria-busy="loading">
      <h3 id="statistics-results-title">查询结果</h3>
      <p v-if="loading" class="empty-state">正在查询所选范围，请稍候。</p>
      <p v-else-if="error" class="notice error">{{ error }}</p>
      <CutoffResults v-else-if="localCutoffs" :data="localCutoffs" />
      <div v-else-if="emptyResult" class="empty-state"><strong>{{ reasons[emptyResult.missing_reason] }}</strong><p>此查询没有已发布记录；来源、证据和数据更新时间均未知。覆盖分母未知，不计算覆盖率，也不显示为0%。</p><p>没有进行资格判断、学校排名、就业收益预测或录取概率计算。</p></div>
      <div v-else class="empty-state"><strong>尚未查询</strong><p>核对上方资料类型、年度与地区后，点击“查询当前范围”。更改筛选后不会沿用旧结果。</p></div>
    </section>
  </section>
</template>

<style scoped>
.query-heading{display:flex;justify-content:space-between;align-items:center;gap:16px}.section-label{font-size:12px;font-weight:650;color:var(--primary);margin-bottom:8px}.query-badge{border:1px solid var(--border);border-radius:999px;padding:7px 12px;font-size:12px;color:var(--muted);white-space:nowrap}.intro{margin:14px 0 22px;color:var(--muted);font-size:15px}.reference-form{padding:22px;border:1px solid var(--border);border-radius:12px;background:var(--surface,#f4f8f5);margin-bottom:20px}.primary-filters,.secondary-filters{display:grid;grid-template-columns:minmax(210px,1.4fr) repeat(2,minmax(140px,1fr));gap:18px}.secondary-filters{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:16px}.reference-form label{display:flex;flex-direction:column;gap:9px;font-size:14px;font-weight:600;color:var(--ink)}.field-help{margin:12px 0 0;font-size:12px;font-weight:400;color:var(--muted);line-height:1.8}.scope-details{border-top:1px solid var(--border);margin-top:20px;padding-top:16px}.scope-details summary{min-height:44px;cursor:pointer;font-size:14px;font-weight:600;color:var(--ink);line-height:1.8}.scope-details summary span{margin-left:12px;font-size:12px;font-weight:400;color:var(--primary)}.query-actions{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:22px}.query-actions p{font-size:12px;color:var(--muted)}.query-actions button{min-height:44px;min-width:160px}.query-results{border-top:1px solid var(--border);margin-top:24px;padding-top:24px}.query-results>h3{margin-bottom:16px}.query-results .empty-state{text-align:left}.empty-state strong{font-size:15px;color:var(--ink)}.empty-state p{margin-top:10px}.screen-reader-status{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:760px){.primary-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.primary-filters label:first-child{grid-column:1/-1}.secondary-filters{grid-template-columns:1fr}.reference-form{padding:18px}.query-actions{align-items:stretch;flex-direction:column;gap:12px}.query-actions button{width:100%}}@media(max-width:430px){.primary-filters{grid-template-columns:1fr}.query-heading{align-items:flex-start}.query-badge{font-size:11px;padding:6px 9px}.reference-form{padding:16px}}
</style>
