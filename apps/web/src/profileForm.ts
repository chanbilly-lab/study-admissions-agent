import type { Profile, ProfileInput, Score } from '../../../packages/contracts/index'

export const assessmentFields = [
  { key: 'gaokao_total', label: '高考总分', scale: 750, unit: 'points' },
  { key: 'math', label: '数学', scale: 150, unit: 'points' },
  { key: 'english_language', label: 'IELTS 总分', scale: 9, unit: 'band' },
] as const
// Vue's v-model on type="number" yields a number after editing and '' when cleared.
export interface ScoreForm { value: string | number; scale: string | number; kind: Score['kind'] }
export interface ProfileForm {
  display_name: string; entry_year: number; province: string; subjects: string; weekly_hours: string | number;
  scores: Record<string, ScoreForm>; confirmed: boolean;
}
export function blankProfileForm(province = '', entryYear = 2027): ProfileForm {
  return {
    display_name: 'DEMO_合成学生', entry_year: entryYear, province, subjects: 'physics,chemistry', weekly_hours: '8', confirmed: false,
    scores: Object.fromEntries(assessmentFields.map(({ key, scale }) => [key, { value: '', scale: String(scale), kind: 'achieved' as const }])),
  }
}
export function profileToForm(profile: Profile): ProfileForm {
  const form = blankProfileForm(profile.province, profile.entry_year)
  form.display_name = profile.display_name; form.subjects = profile.subjects.join(','); form.weekly_hours = String(profile.weekly_hours)
  for (const { key } of assessmentFields) {
    const assessment = profile.assessments[key]
    if (assessment) form.scores[key] = { value: String(assessment.value), scale: String(assessment.scale), kind: assessment.kind }
  }
  return form
}
export function formToInput(form: ProfileForm): ProfileInput {
  if (!form.confirmed) throw new Error('请先确认这是合成画像，并确认本次保存。')
  if (!form.display_name.trim()) throw new Error('请填写合成画像名称。')
  if (!Number.isInteger(Number(form.entry_year)) || Number(form.entry_year) < 2026 || Number(form.entry_year) > 2100) throw new Error('请填写有效入学年。')
  const hoursText = String(form.weekly_hours).trim()
  const hours = Number(hoursText)
  if (hoursText === '' || !Number.isFinite(hours) || hours <= 0 || hours > 40) throw new Error('每周可用时数必须大于 0 且不超过 40。')
  const assessments: Record<string, Score> = {}
  for (const { key, label, unit } of assessmentFields) {
    const score = form.scores[key]
    if (!score) continue
    const valueText = String(score.value).trim(), scaleText = String(score.scale).trim()
    if (valueText === '') continue
    const value = Number(valueText), scale = Number(scaleText)
    if (scaleText === '' || !Number.isFinite(value) || !Number.isFinite(scale) || scale <= 0 || value < 0 || value > scale) throw new Error(`${label}必须为 0 到所填满分之间的数值。`)
    assessments[key] = { value, scale, unit, kind: score.kind }
  }
  return {
    display_name: form.display_name.trim(), is_synthetic: true, confirmed: true, study_level: 'bachelor', course_system: 'gaokao',
    entry_year: Number(form.entry_year), province: form.province, applicant_category: 'cn_mainland',
    subjects: form.subjects.split(/[,，]/).map((item) => item.trim()).filter(Boolean), assessments, weekly_hours: hours,
  }
}
