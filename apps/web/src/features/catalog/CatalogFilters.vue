<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ListV2PublicOfferingsQuery } from '../../../../../packages/contracts/v2/public_catalog/generated'
export type CatalogFilterQuery = Omit<ListV2PublicOfferingsQuery,'entry_year'> & { entry_year: number | null }
const props = defineProps<{ query: CatalogFilterQuery; busy: boolean; synthetic: boolean }>()
const emit = defineEmits<{ changed: [patch: Partial<CatalogFilterQuery>]; search: [] }>()
const year = ref(props.query.entry_year === null ? '' : String(props.query.entry_year))
watch(() => props.query.entry_year, value => { if (value !== null) year.value = String(value) })
const provinces = [['Beijing','北京'],['Tianjin','天津'],['Hebei','河北'],['Shanxi','山西'],['InnerMongolia','内蒙古'],['Liaoning','辽宁'],['Jilin','吉林'],['Heilongjiang','黑龙江'],['Shanghai','上海'],['Jiangsu','江苏'],['Zhejiang','浙江'],['Anhui','安徽'],['Fujian','福建'],['Jiangxi','江西'],['Shandong','山东'],['Henan','河南'],['Hubei','湖北'],['Hunan','湖南'],['Guangdong','广东'],['Guangxi','广西'],['Hainan','海南'],['Chongqing','重庆'],['Sichuan','四川'],['Guizhou','贵州'],['Yunnan','云南'],['Tibet','西藏'],['Shaanxi','陕西'],['Gansu','甘肃'],['Qinghai','青海'],['Ningxia','宁夏'],['Xinjiang','新疆']]
function update(key: keyof CatalogFilterQuery, event: Event) {
  const value = (event.target as HTMLInputElement).value
  if (key === 'entry_year') { year.value = value; emit('changed', { entry_year: /^[1-9][0-9]{0,3}$/.test(value) ? Number(value) : null }) }
  else if (key === 'limit') emit('changed', { limit: Number(value) })
  else emit('changed', { [key]: value || null })
}
</script>
<template>
  <form class="catalog-filters" aria-label="公开项目筛选" @submit.prevent="emit('search')">
    <label>明确入学年度<input :value="year" data-testid="catalog-year" type="text" inputmode="numeric" autocomplete="off" placeholder="请填写年度" maxlength="4" @input="update('entry_year', $event)"></label>
    <label>机构国家 / 地区<select :value="query.country" data-testid="catalog-country" @change="update('country', $event)"><option value="">不限定</option><option value="CN">中国大陆（CN）</option><option value="GB">英国（GB）</option><option value="HK">香港（HK）</option><option value="MO">澳门（MO）</option><option value="TW">台湾（TW）</option></select></label>
    <label>生源省份<select :value="query.province" data-testid="catalog-province" @change="update('province', $event)"><option value="">不限定</option><option value="not_applicable">明确不适用</option><option v-if="synthetic" value="known:DEMO_PROVINCE">DEMO · 合成省份</option><option v-for="[code,label] in provinces" :key="code" :value="`known:${code}`">{{ label }}</option></select></label>
    <label>申请路径<select :value="query.pathway" data-testid="catalog-pathway" @change="update('pathway', $event)"><option value="">不限定</option><option value="known:gaokao">普通高考</option><option value="known:uk_undergraduate">英国本科</option><option value="not_applicable">明确不适用</option></select></label>
    <label>课程体系<select :value="query.course_system" data-testid="catalog-course-system" @change="update('course_system', $event)"><option value="">不限定</option><option value="known:gaokao">普通高考</option><option value="known:A_levels">A levels（仅资料查询）</option><option value="known:HKDSE">HKDSE（未适配）</option><option value="not_applicable">明确不适用</option></select></label>
    <label>申请身份<select :value="query.applicant_category" data-testid="catalog-applicant-category" @change="update('applicant_category', $event)"><option value="">不限定</option><option value="known:cn_mainland">大陆普通高考身份</option><option value="known:hmt_joint">港澳台联招（未适配）</option><option value="not_applicable">明确不适用</option></select></label>
    <label>每页数量<select :value="query.limit" data-testid="catalog-limit" @change="update('limit', $event)"><option value="1">1</option><option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="100">100</option></select></label>
    <button type="submit" class="primary" data-testid="catalog-search" :disabled="busy">{{ busy ? '正在读取…' : '查询公开项目' }}</button>
    <p class="filter-note">省份与身份是资料范围，不根据所在地推断。空筛选表示不限定；2026 参考资料不自动成为 2027 资格依据。</p>
  </form>
</template>
<style scoped>
.catalog-filters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:25px 0}.catalog-filters label{display:flex;flex-direction:column;gap:8px;font-size:12px;color:#4d6757;min-width:0}.catalog-filters :is(input,select){width:100%;min-width:0;padding:11px 12px;border:1px solid #c5d5c4;background:#fff;border-radius:7px;font-size:12px;color:#294b3b}.catalog-filters button{align-self:end;padding:12px 15px;border:1px solid #1b6453;border-radius:7px;background:#1b6453;color:white;font-size:12px}.filter-note{grid-column:1/-1;font-size:11px;color:#7b8872;line-height:1.9;margin:0}.catalog-filters :focus-visible{outline:3px solid #8cb6a4;outline-offset:3px}@media(max-width:850px){.catalog-filters{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.catalog-filters{grid-template-columns:1fr}}
</style>
