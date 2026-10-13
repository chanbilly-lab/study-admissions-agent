import type { ScopeKey } from '../../../../../packages/contracts/v2/public_catalog/generated'

export const scopeKeys = ['province','pathway','course_system','applicant_category','campus','degree','course','teaching_language','progression_pathway','intake','application_cycle','channel','exam_system','subject_scope','batch_group'] as const
export const scopeLabels: Record<typeof scopeKeys[number], string> = {
  province: '生源省份', pathway: '申请路径', course_system: '课程体系', applicant_category: '申请身份',
  campus: '校区', degree: '学位', course: '专业范围', teaching_language: '授课语言', progression_pathway: '升学路线',
  intake: '入学批次', application_cycle: '申请周期', channel: '招生渠道', exam_system: '考试体系', subject_scope: '选科范围', batch_group: '录取批次',
}
export function scopeText(value: ScopeKey): string {
  return value.status === 'known' ? value.value ?? '未知' : value.status === 'not_applicable' ? '明确不适用' : '未知'
}
export const claimLabels = { minimum_requirement: '最低要求', typical_offer: '典型录取条件', historical_statistic: '历史统计', information: '说明资料', unknown: '口径未知' }
export const missingLabels = { ambiguous: '原文有歧义', not_applicable: '明确不适用', not_provided: '未提供', not_published: '未公布', unavailable: '不可获取' }
export const gradeLabels: Record<string, string> = { gaokao_total: '高考总分', math: '数学', chinese: '语文', gaokao_english: '高考英语', physics: '物理', chemistry: '化学', biology: '生物', politics: '政治', history: '历史', geography: '地理', ielts_overall: '雅思总分', ielts_listening: '雅思听力', ielts_reading: '雅思阅读', ielts_writing: '雅思写作', ielts_speaking: '雅思口语' }
