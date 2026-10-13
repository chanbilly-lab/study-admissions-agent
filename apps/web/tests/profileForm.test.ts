import { describe, expect, it } from 'vitest'
import { blankProfileForm, formToInput, profileToForm } from '../src/profileForm'
import { profile } from './fixtures'

describe('confirmed synthetic profile contract', () => {
  it('refuses to produce a write request without explicit user confirmation', () => {
    expect(() => formToInput(blankProfileForm('浙江'))).toThrow('确认')
  })
  it('omits blank assessments instead of making them achieved zero or implicitly deferred', () => {
    const form = blankProfileForm('浙江'); form.confirmed = true
    form.scores.math = { value: '0', scale: '150', kind: 'predicted' }
    const input = formToInput(form)
    expect(input.assessments).toEqual({ math: { value: 0, scale: 150, unit: 'points', kind: 'predicted' } })
    expect(input).not.toHaveProperty('owner_id')
    expect(input).toMatchObject({ is_synthetic: true, confirmed: true, province: '浙江' })
  })
  it('preserves backend assessment keys and achieved versus predicted types', () => {
    const form = profileToForm(profile()); form.confirmed = true
    form.scores.english_language = { value: '6.5', scale: '9', kind: 'predicted' }
    const input = formToInput(form)
    expect(input.assessments).toHaveProperty('gaokao_total.value', 610)
    expect(input.assessments).toHaveProperty('english_language.kind', 'predicted')
    expect(input.assessments).not.toHaveProperty('total')
    expect(input.assessments).not.toHaveProperty('ielts')
  })
  it('does not silently coerce an invalid score or weekly capacity', () => {
    const form = blankProfileForm('浙江'); form.confirmed = true
    form.scores.math = { value: '151', scale: '150', kind: 'achieved' }
    expect(() => formToInput(form)).toThrow('数学')
    form.scores.math.value = ''; form.weekly_hours = '41'
    expect(() => formToInput(form)).toThrow('40')
    form.weekly_hours = '0'
    expect(() => formToInput(form)).toThrow('大于 0')
  })
  it('accepts runtime numeric v-model values and preserves a cleared field as missing', () => {
    const form = blankProfileForm('浙江'); form.confirmed = true; form.weekly_hours = 12
    form.scores.gaokao_total = { value: 640, scale: 750, kind: 'achieved' }
    form.scores.math = { value: 0, scale: 150, kind: 'predicted' }
    form.scores.english_language = { value: '', scale: 9, kind: 'achieved' }
    const input = formToInput(form)
    expect(input.weekly_hours).toBe(12)
    expect(input.assessments.gaokao_total).toMatchObject({ value: 640, scale: 750 })
    expect(input.assessments.math).toMatchObject({ value: 0, kind: 'predicted' })
    expect(input.assessments).not.toHaveProperty('english_language')
  })
})
