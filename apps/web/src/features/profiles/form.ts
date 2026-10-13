import type { AdaptationData, GradeAssessments, GradeSlot, Preferences, ProfileSnapshot, ScopeKey } from '../../../../../packages/contracts/v2/profiles/generated'

export const scopeFields = [
  { key: 'residence_region', label: '所在地', hint: '所在地不推断考试省份或申请身份；如 CN / HK / MO / TW。' },
  { key: 'course_system', label: '课程体系', hint: '普通高考填 gaokao；HKDSE 等其他体系单独记录，未适配。' },
  { key: 'applicant_category', label: '申请身份', hint: '须本人明确；如 cn_mainland，不由所在地推断。' },
  { key: 'exam_province', label: '高考生源省份', hint: '填写本人考试省份代码；DEMO_PROVINCE 仅隔离测试。省份意向不代表规则已覆盖。' },
  { key: 'pathway', label: '目标路线', hint: '普通高考填 gaokao；英国本科填 uk_undergraduate。' },
] as const
export type ScopeField = typeof scopeFields[number]['key']
export type AssessmentKey = keyof GradeAssessments
export const assessmentLabels: Record<AssessmentKey, string> = {
  gaokao_total: '高考总分', chinese: '语文', math: '数学', gaokao_english: '高考英语', physics: '物理', chemistry: '化学', biology: '生物',
  politics: '思想政治', history: '历史', geography: '地理', ielts_overall: 'IELTS 总分', ielts_listening: 'IELTS 听力',
  ielts_reading: 'IELTS 阅读', ielts_writing: 'IELTS 写作', ielts_speaking: 'IELTS 口语',
}
export const assessmentKeys = Object.keys(assessmentLabels) as AssessmentKey[]
export interface SlotDraft { status: GradeSlot['status']; value: string; scale: string; unit: '' | 'points' | 'band' }
export interface ProfileDraft {
  entryYear: string; scopes: Record<ScopeField, { status: ScopeKey['status']; value: string }>; subjects: string;
  grades: Partial<Record<AssessmentKey, { achieved: SlotDraft; predicted: SlotDraft }>>; weeklyHours: string;
  preferencesEnabled: boolean; preferredFields: string; preferredCountries: ('CN' | 'GB')[];
  budgetEnabled: boolean; budgetAmount: string; budgetCurrency: '' | 'CNY' | 'GBP'; confirmed: boolean;
}
export const blankSlot = (): SlotDraft => ({ status: 'missing', value: '', scale: '', unit: '' })
export function blankDraft(): ProfileDraft {
  return { entryYear: '', scopes: Object.fromEntries(scopeFields.map(({ key }) => [key, { status: 'unknown', value: '' }])) as ProfileDraft['scopes'],
    subjects: '', grades: {}, weeklyHours: '', preferencesEnabled: false, preferredFields: '', preferredCountries: [],
    budgetEnabled: false, budgetAmount: '', budgetCurrency: '', confirmed: false }
}
export const identifier = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$/.test(value)
export const decimal = (value: unknown): value is string => typeof value === 'string' && /^(0|[1-9][0-9]{0,6})(\.[0-9]{1,6})?$/.test(value)
// Compare a bounded decimal exactly using integer micro-units. Never turn grades into floats.
export function decimalUnits(value: string): bigint { const [whole, fraction = ''] = value.split('.'); return BigInt(whole) * 1_000_000n + BigInt(fraction.padEnd(6, '0')) }
export function asksGaokao(draft: ProfileDraft) {
  return draft.scopes.course_system.status === 'known' && draft.scopes.course_system.value === 'gaokao'
    && draft.scopes.applicant_category.status === 'known' && draft.scopes.applicant_category.value === 'cn_mainland'
    && draft.scopes.pathway.status === 'known' && ['gaokao', 'uk_undergraduate'].includes(draft.scopes.pathway.value)
}
export function asksLanguage(draft: ProfileDraft) { return asksGaokao(draft) && draft.scopes.pathway.value === 'uk_undergraduate' }
export function allowedAssessments(draft: ProfileDraft) { return assessmentKeys.filter(key => key.startsWith('ielts_') ? asksLanguage(draft) : asksGaokao(draft)) }
export function clearUnsupportedDraftFields(draft: ProfileDraft): boolean {
  const allowed = allowedAssessments(draft); let removed = false
  for (const key of assessmentKeys) if (draft.grades[key] && !allowed.includes(key)) { delete draft.grades[key]; removed = true }
  if (!asksGaokao(draft) && draft.subjects !== '') { draft.subjects = ''; removed = true }
  return removed
}
function slotInput(slot: SlotDraft, key: AssessmentKey): GradeSlot {
  if (slot.status !== 'provided') return { status: slot.status, value: null, scale: null, unit: null }
  if (!decimal(slot.value) || !decimal(slot.scale) || decimalUnits(slot.scale) <= 0n || decimalUnits(slot.value) > decimalUnits(slot.scale)
    || slot.unit !== (key.startsWith('ielts_') ? 'band' : 'points')) throw new Error(`${assessmentLabels[key]}须填写明确成绩、正满分和相符单位。`)
  return { status: 'provided', value: slot.value, scale: slot.scale, unit: slot.unit }
}
export function draftToSnapshot(draft: ProfileDraft): ProfileSnapshot {
  if (!/^[1-9][0-9]{0,3}$/.test(draft.entryYear)) throw new Error('请明确填写 1–9999 的入学年。2027 只是英国目标提示，不会自动填写。')
  const scopes = Object.fromEntries(scopeFields.map(({ key }) => {
    const scope = draft.scopes[key]
    if (scope.status === 'known' && !identifier(scope.value)) throw new Error('已知范围须填写明确的有界代码，不从其他字段推断。')
    return [key, { status: scope.status, value: scope.status === 'known' ? scope.value : null }]
  })) as Record<ScopeField, ScopeKey>
  const assessments: GradeAssessments = {}
  for (const key of assessmentKeys) {
    const pair = draft.grades[key]
    if (pair) assessments[key] = { achieved: slotInput(pair.achieved, key), predicted: slotInput(pair.predicted, key) }
  }
  const subjects = draft.subjects !== '' ? draft.subjects.split(/[,，]/).map(value => value.trim()) : []
  if (subjects.length > 8 || new Set(subjects).size !== subjects.length || subjects.some(value => !identifier(value))) throw new Error('选科须为至多 8 个唯一代码，以逗号分隔。')
  if (draft.weeklyHours !== '' && (!decimal(draft.weeklyHours) || decimalUnits(draft.weeklyHours) > 40_000_000n)) throw new Error('每周时数须为 0–40 的明确十进制字符串；空白表示未提供。')
  let preferences: Preferences | null = null
  if (draft.preferencesEnabled) {
    const fields = draft.preferredFields === '' ? [] : draft.preferredFields.split('\n')
    if (fields.length > 10 || new Set(fields).size !== fields.length || fields.some(value => !validPreference(value))) throw new Error('专业兴趣每行一项，至多 10 项，不能空白或重复。')
    if (draft.budgetEnabled && (!decimal(draft.budgetAmount) || !['CNY', 'GBP'].includes(draft.budgetCurrency))) throw new Error('预算须明确数额和币种；不根据家庭信息推断。')
    preferences = { preferred_fields: fields, preferred_countries: [...draft.preferredCountries],
      budget: draft.budgetEnabled ? { amount: draft.budgetAmount, currency: draft.budgetCurrency as 'CNY' | 'GBP' } : null }
  }
  return { study_level: 'bachelor', entry_year: Number(draft.entryYear), ...scopes, subjects, assessments,
    weekly_hours: draft.weeklyHours === '' ? null : draft.weeklyHours, preferences }
}
export function snapshotToDraft(profile: ProfileSnapshot): ProfileDraft {
  const draft = blankDraft(); draft.entryYear = String(profile.entry_year)
  for (const { key } of scopeFields) draft.scopes[key] = { status: profile[key].status, value: profile[key].value ?? '' }
  draft.subjects = profile.subjects.join(','); draft.weeklyHours = profile.weekly_hours ?? ''
  for (const key of assessmentKeys) {
    const pair = profile.assessments[key]
    const slot = (value: GradeSlot): SlotDraft => ({ status: value.status, value: value.value ?? '', scale: value.scale ?? '', unit: value.unit ?? '' })
    if (pair) draft.grades[key] = { achieved: slot(pair.achieved), predicted: slot(pair.predicted) }
  }
  if (profile.preferences) {
    draft.preferencesEnabled = true; draft.preferredFields = profile.preferences.preferred_fields.join('\n'); draft.preferredCountries = [...profile.preferences.preferred_countries]
    if (profile.preferences.budget) { draft.budgetEnabled = true; draft.budgetAmount = profile.preferences.budget.amount; draft.budgetCurrency = profile.preferences.budget.currency }
  }
  return draft
}
export function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
export function exact(value: unknown, keys: readonly string[]): value is Record<string, unknown> { return record(value) && Object.keys(value).length === keys.length && keys.every(key => key in value) }
function validPreference(value: unknown): value is string {
  if (typeof value !== 'string' || Array.from(value).length < 1 || Array.from(value).length > 100 || !value.trim() || /[\x00-\x1f\x7f]/.test(value)) return false
  for (const char of value) { const code = char.codePointAt(0)!; if (code >= 0xd800 && code <= 0xdfff) return false }
  return new TextEncoder().encode(value).length <= 400
}
export function adaptationOf(profile: ProfileSnapshot): AdaptationData {
  if (profile.course_system.status === 'known' && profile.course_system.value !== 'gaokao') return { status: 'unsupported', reason: 'COURSE_NOT_SUPPORTED' }
  if (profile.pathway.status === 'known' && !['gaokao', 'uk_undergraduate'].includes(profile.pathway.value!)) return { status: 'unsupported', reason: 'PATHWAY_NOT_SUPPORTED' }
  if (profile.applicant_category.status === 'known' && profile.applicant_category.value !== 'cn_mainland') return { status: 'unsupported', reason: 'APPLICANT_NOT_SUPPORTED' }
  if (['course_system', 'pathway', 'applicant_category', 'exam_province'].some(key => profile[key as ScopeField].status !== 'known')) return { status: 'unknown', reason: 'MISSING_SCOPE' }
  return { status: 'unknown', reason: 'ADAPTER_NOT_IMPLEMENTED' }
}
function validScope(value: unknown): value is ScopeKey { return exact(value, ['status', 'value']) && (value.status === 'known' ? identifier(value.value) : (value.status === 'unknown' || value.status === 'not_applicable') && value.value === null) }
function validSlot(value: unknown, key: string): value is GradeSlot {
  if (!exact(value, ['status', 'value', 'scale', 'unit'])) return false
  if (value.status === 'provided') return decimal(value.value) && decimal(value.scale) && decimalUnits(value.scale) > 0n && decimalUnits(value.value) <= decimalUnits(value.scale) && value.unit === (key.startsWith('ielts_') ? 'band' : 'points')
  return typeof value.status === 'string' && ['missing', 'pending', 'not_applicable'].includes(value.status) && value.value === null && value.scale === null && value.unit === null
}
export function validSnapshot(value: unknown): value is ProfileSnapshot {
  if (!exact(value, ['study_level', 'entry_year', ...scopeFields.map(item => item.key), 'subjects', 'assessments', 'weekly_hours', 'preferences']) || value.study_level !== 'bachelor'
    || typeof value.entry_year !== 'number' || !Number.isSafeInteger(value.entry_year) || value.entry_year < 1 || value.entry_year > 9999 || scopeFields.some(({ key }) => !validScope(value[key]))
    || !Array.isArray(value.subjects) || value.subjects.length > 8 || value.subjects.some(item => !identifier(item)) || new Set(value.subjects).size !== value.subjects.length || !record(value.assessments)
    || Object.entries(value.assessments).some(([key, pair]) => !assessmentKeys.includes(key as AssessmentKey) || !exact(pair, ['achieved', 'predicted']) || !validSlot(pair.achieved, key) || !validSlot(pair.predicted, key))
    || !(value.weekly_hours === null || decimal(value.weekly_hours) && decimalUnits(value.weekly_hours) <= 40_000_000n)) return false
  const preference = value.preferences
  return preference === null || exact(preference, ['preferred_fields', 'preferred_countries', 'budget']) && Array.isArray(preference.preferred_fields) && preference.preferred_fields.length <= 10
    && preference.preferred_fields.every(validPreference) && new Set(preference.preferred_fields).size === preference.preferred_fields.length && Array.isArray(preference.preferred_countries)
    && preference.preferred_countries.length <= 2 && preference.preferred_countries.every(item => item === 'CN' || item === 'GB') && new Set(preference.preferred_countries).size === preference.preferred_countries.length
    && (preference.budget === null || exact(preference.budget, ['amount', 'currency']) && decimal(preference.budget.amount) && (preference.budget.currency === 'CNY' || preference.budget.currency === 'GBP'))
}
