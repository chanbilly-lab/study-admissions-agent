import { describe, expect, it } from 'vitest'
import { asksGaokao, blankDraft, clearUnsupportedDraftFields, draftToSnapshot, snapshotToDraft, validSnapshot } from '../src/features/profiles/form'
import { clone, snapshot } from './profilesFixtures'

describe('complete explicit profile declarations', () => {
  it('starts with no year, province, grades, scale or weekly-capacity defaults', () => {
    const draft = blankDraft()
    expect(draft.entryYear).toBe(''); expect(draft.weeklyHours).toBe(''); expect(draft.grades).toEqual({}); expect(draft.confirmed).toBe(false)
    expect(Object.values(draft.scopes).every(scope => scope.status === 'unknown' && scope.value === '')).toBe(true)
    expect(() => draftToSnapshot(draft)).toThrow('入学年')
    draft.entryYear = '2027'; expect(draftToSnapshot(draft)).toMatchObject({ assessments: {}, subjects: [], weekly_hours: null, preferences: null })
  })
  it('keeps exact zero, missing and two independent grade slots rather than predicted achievement', () => {
    const draft = snapshotToDraft(snapshot()); draft.weeklyHours = '0'
    draft.grades.math!.predicted = { status: 'provided', value: '99.000001', scale: '100', unit: 'points' }
    const value = draftToSnapshot(draft)
    expect(value.assessments.math!.achieved.value).toBe('0'); expect(value.assessments.math!.predicted.value).toBe('99.000001'); expect(value.weekly_hours).toBe('0')
    draft.grades.math!.achieved.status = 'missing'; draft.weeklyHours = ''
    expect(draftToSnapshot(draft).assessments.math!.achieved).toEqual({ status: 'missing', value: null, scale: null, unit: null })
    expect(draftToSnapshot(draft).weekly_hours).toBeNull()
  })
  it.each(['', 'NaN', 'Infinity', '1e2', '01', '-1', '1.0000001'])('rejects provided decimal lexical input %s without coercion', value => {
    const draft = snapshotToDraft(snapshot()); draft.grades.math!.achieved.value = value
    expect(() => draftToSnapshot(draft)).toThrow('成绩')
  })
  it('requires positive scale, bounded capacity and the explicitly matching unit', () => {
    const draft = snapshotToDraft(snapshot()); draft.grades.math!.achieved.scale = '0'
    expect(() => draftToSnapshot(draft)).toThrow('满分'); draft.grades.math!.achieved.scale = '100'; draft.grades.math!.achieved.unit = 'band'
    expect(() => draftToSnapshot(draft)).toThrow('单位'); draft.grades.math!.achieved.unit = 'points'; draft.weeklyHours = '40.000001'
    expect(() => draftToSnapshot(draft)).toThrow('时数')
  })
  it('keeps location independent of category/province and never activates gaokao fields for unsupported identity', () => {
    const draft = snapshotToDraft(snapshot()); expect(draftToSnapshot(draft).residence_region.value).toBe('HK')
    expect(draftToSnapshot(draft).applicant_category.value).toBe('cn_mainland'); expect(draftToSnapshot(draft).exam_province.value).toBe('DEMO_PROVINCE')
    draft.scopes.applicant_category.value = 'hmt_joint'; expect(asksGaokao(draft)).toBe(false)
    expect(clearUnsupportedDraftFields(draft)).toBe(true); expect(draft.grades).toEqual({}); expect(draft.subjects).toBe('')
  })
  it('roundtrips an already saved snapshot including hidden fields, then clears only the explicitly switched draft', () => {
    const original = snapshot({ course_system: { status: 'unknown', value: null } }); const draft = snapshotToDraft(original)
    expect(draftToSnapshot(draft)).toEqual(original)
    expect(clearUnsupportedDraftFields(draft)).toBe(true); expect(draftToSnapshot(draft).assessments).toEqual({})
    expect(original.assessments.math!.achieved.value).toBe('0')
  })
  it('preserves valid Unicode preferences and currency/unknown budget semantics', () => {
    const draft = snapshotToDraft(snapshot()); draft.preferencesEnabled = true; draft.preferredFields = '机器人🤖\n𠮷字研究'; draft.preferredCountries = ['GB']
    expect(validSnapshot(draftToSnapshot(draft))).toBe(true); expect(draftToSnapshot(draft).preferences!.budget).toBeNull()
    draft.budgetEnabled = true; draft.budgetAmount = '25000.00'; draft.budgetCurrency = 'GBP'
    expect(draftToSnapshot(draft).preferences!.budget).toEqual({ amount: '25000.00', currency: 'GBP' })
    draft.preferredFields = '\ud800'; expect(() => draftToSnapshot(draft)).toThrow('兴趣')
  })
  it.each([
    (value: ReturnType<typeof snapshot>) => { value.course_system.status = ['unknown'] as never; value.course_system.value = null },
    (value: ReturnType<typeof snapshot>) => { value.assessments.math!.predicted.status = ['missing'] as never },
    (value: ReturnType<typeof snapshot>) => { value.preferences = { preferred_fields: [], preferred_countries: [['CN']] as never, budget: null } },
    (value: ReturnType<typeof snapshot>) => { value.preferences = { preferred_fields: [], preferred_countries: [], budget: { amount: '1', currency: ['CNY'] as never } } },
  ])('rejects array-shaped enum impostors in actual JSON snapshots', change => { const value = clone(snapshot()); change(value); expect(validSnapshot(value)).toBe(false) })
})
