<script setup lang="ts">
import type { ProfileVersionData } from './client'
import { assessmentLabels, assessmentKeys, scopeFields } from './form'
defineProps<{ version: ProfileVersionData; history?: boolean }>()
const statusLabels = { provided: '明确提供', missing: '未提供', pending: '待出成绩（不是后补许可）', not_applicable: '不适用' }
</script>
<template>
  <article class="profile-summary" :data-testid="history ? 'profile-history-result' : 'profile-current'">
    <div class="summary-heading"><h3>{{ history ? '指定历史版本 · 只读' : '当前确认版本 · 只读' }}</h3><span>{{ version.is_synthetic ? 'DEMO · 合成声明' : '本人声明 · 未核验成绩' }}</span></div>
    <dl class="profile-metadata">
      <div><dt>画像根 UUID</dt><dd :data-testid="history ? undefined : 'profile-current-root-id'">{{ version.profile_id }}</dd></div>
      <div><dt>确认版号</dt><dd :data-testid="history ? undefined : 'profile-current-version'">{{ version.version }}</dd></div>
      <div><dt>版本 UUID</dt><dd :data-testid="history ? undefined : 'profile-current-version-id'">{{ version.version_id }}</dd></div>
      <div><dt>完整快照 SHA</dt><dd :data-testid="history ? undefined : 'profile-current-hash'">{{ version.profile_sha256 }}</dd></div>
      <div><dt>确认时间</dt><dd><time :datetime="version.confirmed_at">{{ version.confirmed_at }}</time></dd></div>
      <div><dt>资料期限</dt><dd><time :datetime="version.expires_at">{{ version.expires_at }}</time></dd></div>
      <div><dt>入学年</dt><dd>{{ version.profile.entry_year }}</dd></div>
      <div v-for="field in scopeFields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ version.profile[field.key].status === 'known' ? version.profile[field.key].value : version.profile[field.key].status === 'unknown' ? '未知 / 未提供' : '明确不适用' }}</dd></div>
      <div><dt>选科声明</dt><dd>{{ version.profile.subjects.join('、') || '未提供' }}</dd></div>
      <div><dt>每周时数</dt><dd>{{ version.profile.weekly_hours === null ? '未知 / 未提供' : version.profile.weekly_hours + ' 小时' }}</dd></div>
    </dl>
    <p class="profile-adaptation" data-testid="profile-adaptation">{{ version.adaptation.status === 'unsupported' ? '该课程、身份或路线尚未适配' : '适配结果未知，尚未实现规则适配' }} · {{ version.adaptation.reason }}。此声明不能作为资格或录取判断。</p>
    <div class="summary-grades" v-if="Object.keys(version.profile.assessments).length">
      <div v-for="key in assessmentKeys.filter(key => version.profile.assessments[key])" :key="key"><strong>{{ assessmentLabels[key] }}</strong><p v-for="slot in ['achieved', 'predicted'] as const" :key="slot">{{ slot === 'achieved' ? '实得' : '预测' }}：{{ statusLabels[version.profile.assessments[key]![slot].status] }}<template v-if="version.profile.assessments[key]![slot].status === 'provided'"> · {{ version.profile.assessments[key]![slot].value }} / {{ version.profile.assessments[key]![slot].scale }} {{ version.profile.assessments[key]![slot].unit }}</template></p></div>
    </div><p v-else class="summary-note">没有已提供的成绩项，不自动判断为零或可后补。</p>
    <p v-if="version.profile.preferences" class="summary-note">本人偏好：{{ version.profile.preferences.preferred_fields.join('、') || '未提供专业兴趣' }}；国家 {{ version.profile.preferences.preferred_countries.join(' / ') || '未提供' }}；预算 {{ version.profile.preferences.budget ? version.profile.preferences.budget.amount + ' ' + version.profile.preferences.budget.currency : '未知 / 未提供' }}。偏好不等于学校资格。</p>
    <p v-if="history" class="summary-note">历史版不能成为当前追加的 CAS；读取历史不会复制到编辑草稿。</p>
  </article>
</template>
<style scoped>
.profile-summary{margin-top:22px;padding:24px;background:#f7f9f3;border:1px solid #d6e2cb;border-radius:10px;min-width:0}.summary-heading{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}.summary-heading h3{font-size:15px}.summary-heading span{font-size:10px;color:#6d7d5f}.profile-metadata{display:grid;gap:11px;margin:22px 0;font-size:11px}.profile-metadata>div{display:grid;grid-template-columns:100px minmax(0,1fr);gap:12px}.profile-metadata dt{color:#83917b}.profile-metadata dd{margin:0;overflow-wrap:anywhere;line-height:1.8}.profile-adaptation,.summary-note{font-size:11px;line-height:1.9;color:#7a795d}.profile-adaptation{padding:12px;background:#f5efdf;border-radius:7px}.summary-grades{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px;margin-top:18px;font-size:11px}.summary-grades>div{padding:12px;background:#fff;border-radius:7px;min-width:0;overflow-wrap:anywhere}.summary-grades p{margin-top:7px;line-height:1.9}.summary-note{margin-top:16px}@media(max-width:650px){.profile-summary{padding:19px 15px}.summary-grades{grid-template-columns:1fr}.profile-metadata>div{grid-template-columns:85px minmax(0,1fr)}}
</style>
