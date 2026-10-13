import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import App from '../src/App.vue'
import { makeApi, offering, profile } from './fixtures'

let wrapper: VueWrapper | undefined
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.open = true } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.open = false } })
})
afterEach(() => wrapper?.unmount())
describe('M0 confirmed profile to evidence to draft interaction', () => {
  it('saves after editing real numeric inputs, including capacity and score scales', async () => {
    const api = makeApi(); wrapper = mount(App, { props: { api } }); await flushPromises()
    await wrapper.find('#weekly-hours').setValue('12')
    await wrapper.find('#score-gaokao_total').setValue('640')
    await wrapper.find('input[aria-label="高考总分满分"]').setValue('750')
    await wrapper.find('#score-math').setValue('125')
    await wrapper.find('input[aria-label="数学满分"]').setValue('150')
    await wrapper.find('#score-english_language').setValue('')
    await wrapper.find('#confirm-profile').setValue(true)
    await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(api.createProfile).toHaveBeenCalledWith('alice', expect.objectContaining({ weekly_hours: 12, assessments: {
      gaokao_total: { value: 640, scale: 750, unit: 'points', kind: 'achieved' },
      math: { value: 125, scale: 150, unit: 'points', kind: 'achieved' },
    } }))
  })
  it('requires explicit confirmation before a synthetic profile is written', async () => {
    const api = makeApi(); wrapper = mount(App, { props: { api } }); await flushPromises()
    await wrapper.find('form').trigger('submit')
    expect(api.createProfile).not.toHaveBeenCalled()
    expect(wrapper.find('[role="alert"]').text()).toContain('确认')
    await wrapper.find('#display-name').setValue('DEMO_已确认的新画像')
    await wrapper.find('#confirm-profile').setValue(true)
    await wrapper.find('form').trigger('submit'); await flushPromises()
    expect(api.createProfile).toHaveBeenCalledWith('alice', expect.objectContaining({ display_name: 'DEMO_已确认的新画像', is_synthetic: true, confirmed: true, assessments: profile().assessments }))
    const saved = api.createProfile.mock.calls[0]?.[1]
    expect(saved).not.toHaveProperty('owner_id')
    expect(saved?.assessments).not.toHaveProperty('english_language')
    expect((wrapper.find('#confirm-profile').element as HTMLInputElement).checked).toBe(false)
  })
  it('renders unknown separately from conditional, shows evidence as escaped text, and keeps missing dates unknown', async () => {
    const api = makeApi(); wrapper = mount(App, { props: { api }, attachTo: document.body }); await flushPromises()
    expect(wrapper.text()).toContain('所有学生、机构、项目与招生证据均为合成数据')
    expect(wrapper.text()).toContain('mock 模式')
    expect(wrapper.text()).toContain('未知 · 未公布')
    await wrapper.find(`input[aria-label="选择 ${offering.title}"]`).setValue(true)
    await wrapper.findAll('button').find((item) => item.text().includes('运行确定性资格检查'))!.trigger('click'); await flushPromises()
    expect(wrapper.find('.result-card .status-chip').text()).toContain('unknown')
    expect(wrapper.find('.result-card').text()).toContain('历史竞争背景')
    expect(wrapper.find('.result-card').text()).toContain('偏好匹配')
    await wrapper.find('.reason-list .text-button').trigger('click'); await flushPromises()
    expect(api.evidence).toHaveBeenCalledWith('alice', 'DEMO_evidence')
    expect(wrapper.find('.evidence-excerpt').text()).toContain('<script>bad()</script>')
    expect(wrapper.find('.evidence-excerpt script').exists()).toBe(false)
    expect(wrapper.find('.evidence-dialog').text()).toContain('不是真实官方招生依据')
    expect(wrapper.find('.evidence-dialog').text()).toContain('DEMO_CN_course')
    await wrapper.find('button[aria-label="关闭证据"]').trigger('click'); await flushPromises()
    await wrapper.findAll('button').find((item) => item.text().includes('生成未确认计划草案'))!.trigger('click'); await flushPromises()
    expect(wrapper.find('.task-list').text()).toContain('未知 · 未安排日期')
    expect(wrapper.find('.task-list').text()).toContain('待用户审阅 · 未确认')
    expect(wrapper.text()).not.toContain('23:59')
  })
})
