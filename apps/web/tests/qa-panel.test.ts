import { webcrypto } from 'node:crypto'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import QAPanel from '../src/features/qa/QAPanel.vue'
import { publicFact } from './catalogUiFixtures'
import { answer, api, closedContext, deferred, target, unknown } from './qaFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = '' })
const id = (name: string) => `[data-testid="${name}"]`
async function activate(wrapper: ReturnType<typeof mount>, intent = 'requirements') {
  await wrapper.get(id('qa-toggle')).trigger('click'); await wrapper.get(id('qa-intent')).setValue(intent)
  await wrapper.get(id('qa-context-refresh')).trigger('click')
  await vi.waitFor(() => expect(wrapper.get(id('qa-ask')).attributes('disabled')).toBeUndefined())
}
describe('T39 QA panel actual DOM', () => {
  it('starts folded without inputs or extra IO, expands explicitly and still requires capability plus intent', async () => {
    const port = api(), wrapper = mount(QAPanel, { props: { target: target(), api: port } })
    expect(wrapper.find('input,select,textarea').exists()).toBe(false); expect(port.context).not.toHaveBeenCalled()
    await wrapper.get(id('qa-toggle')).trigger('click'); expect(wrapper.get(id('qa-intent')).element).toHaveProperty('value', '')
    expect(port.context).not.toHaveBeenCalled(); expect(wrapper.get(id('qa-ask')).attributes('disabled')).toBeDefined()
    await wrapper.get(id('qa-context-refresh')).trigger('click'); await vi.waitFor(() => expect(wrapper.find(id('qa-demo')).exists()).toBe(true))
    expect(wrapper.get(id('qa-ask')).attributes('disabled')).toBeDefined(); await wrapper.get(id('qa-intent')).setValue('requirements')
    expect(wrapper.get(id('qa-ask')).attributes('disabled')).toBeUndefined(); wrapper.unmount()
  })
  it('renders original string numbers and unit/footnote distinctions, with escaped source injection and no URL actions', async () => {
    const fact = publicFact({ value_text: '600.000001', normalized_value: '600.000001', footnote_text: 'DEMO_<script>window.__qa=1</script>' }), item = target(fact), port = api({}, item)
    const wrapper = mount(QAPanel, { props: { target: item, api: port }, attachTo: document.body }); await activate(wrapper)
    await wrapper.get(id('qa-ask')).trigger('click'); await vi.waitFor(() => expect(wrapper.find(id('qa-result')).exists()).toBe(true))
    expect(wrapper.get(id('qa-fact-value')).text()).toBe('600.000001'); expect(wrapper.text()).toContain('points'); expect(wrapper.text()).toContain('<script>window.__qa=1</script>')
    expect(wrapper.find('img,script,a').exists()).toBe(false)
    const citation = answer(item).citations[0]!
    await wrapper.get(id(`qa-original-${citation.id}`)).get('summary').trigger('click')
    expect(wrapper.find('pre').text()).toContain('<img'); expect(wrapper.text()).toContain('来源自报官方'); expect(wrapper.text()).toContain('固定一般建议')
    expect(wrapper.text()).not.toContain('"normalized_value"'); expect(wrapper.text()).not.toContain('本人 eligible'); wrapper.unmount()
  })
  it('shows date-only precision and candidate UTC as unknown rather than manufacturing 23:59 or a final deadline', async () => {
    const fact = publicFact({ fact_type: 'date', field_key: 'DEMO_deadline', value_kind: 'text', value_text: 'DEMO_2027年1月15日', normalized_value: '2027-01-15', unit: null, unit_code: 'ISO_DATE', claim_kind: 'information', footnote_state: 'unknown', footnote_text: null,
      date_resolution: { event_type: 'application_deadline', original_text: 'DEMO_2027年1月15日', precision: 'date', local_date: '2027-01-15', local_time: null, timezone: 'Europe/London', source_alignment: 'pending', conversion_status: 'date_only', calculated_utc_instant: null, utc_instant: null, tzdata_version: '2026.4' } })
    const item = target(fact), port = api({ answer: vi.fn(async input => { const data = answer(item, input); data.unknown_reasons = ['DATE_UNRESOLVED']; return data }) }, item)
    const wrapper = mount(QAPanel, { props: { target: item, api: port } }); await activate(wrapper, 'dates'); await wrapper.get(id('qa-ask')).trigger('click')
    await vi.waitFor(() => expect(wrapper.find(id('qa-date')).exists()).toBe(true))
    expect(wrapper.get(id('qa-date')).text()).toContain('date'); expect(wrapper.get(id('qa-date')).text()).toContain('未知；不补23:59'); expect(wrapper.get(id('qa-unknown')).text()).toContain('精确时刻'); expect(wrapper.text()).toContain('脚注情况未知')
    expect(wrapper.get(id('qa-date')).text()).not.toContain('T23:59'); wrapper.unmount()
  })
  it('keeps a disabled service visibly closed and cannot ask through controls', async () => {
    const port = api({ context: vi.fn(async () => closedContext()) }), wrapper = mount(QAPanel, { props: { target: target(), api: port } })
    await wrapper.get(id('qa-toggle')).trigger('click'); await wrapper.get(id('qa-intent')).setValue('requirements'); await wrapper.get(id('qa-context-refresh')).trigger('click')
    await vi.waitFor(() => expect(wrapper.get(id('qa-status')).text()).toContain('未启用'))
    expect(wrapper.get(id('qa-ask')).attributes('disabled')).toBeDefined(); expect(port.answer).not.toHaveBeenCalled(); wrapper.unmount()
  })
  it('shows explicit unknown without a fabricated fact, source or missing-evidence label', async () => {
    const port = api({ answer: vi.fn(async () => unknown()) }), wrapper = mount(QAPanel, { props: { target: target(), api: port } }); await activate(wrapper); await wrapper.get(id('qa-ask')).trigger('click')
    await vi.waitFor(() => expect(wrapper.get(id('qa-result')).text()).toContain('未知'))
    expect(wrapper.find('[data-testid^="qa-citation-"]').exists()).toBe(false); expect(wrapper.find(id('qa-unknown')).exists()).toBe(false); expect(wrapper.text()).not.toContain('没有可公开的证据原文'); wrapper.unmount()
  })
  it('clears DOM synchronously on target changes and cannot revive a late successful answer', async () => {
    const hold = deferred<ReturnType<typeof answer>>(), consumed = deferred<void>(), port = api({ answer: vi.fn(async () => { const data = await hold.promise; consumed.resolve(); return data }) }), wrapper = mount(QAPanel, { props: { target: target(), api: port } }); await activate(wrapper); await wrapper.get(id('qa-ask')).trigger('click')
    await wrapper.setProps({ target: null }); expect(wrapper.find(id('qa-result')).exists()).toBe(false)
    hold.resolve(answer()); await consumed.promise; await flushPromises()
    expect(wrapper.find(id('qa-result')).exists()).toBe(false); expect(wrapper.find(id('qa-no-target')).exists()).toBe(true); expect(wrapper.get(id('qa-intent')).element).toHaveProperty('value', '')
    wrapper.unmount()
  })
})
