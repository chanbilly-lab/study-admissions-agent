import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminView from '../src/views/admin/AdminView.vue'
import { AdminError } from '../src/features/admin/client'
import { actor, adminApi, sourceId, datasetId, source, definition, rejected } from './adminFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto))
afterEach(() => vi.unstubAllGlobals())
const selector = (name: string) => `[data-testid="${name}"]`

describe('management workspace interactions', () => {
  it.each([403, 503])('shows server denial %s without source or import controls', async status => {
    const wrapper = mount(AdminView, { props: { actor, api: adminApi({ context: vi.fn().mockRejectedValue(new AdminError(status)) }) } })
    await flushPromises()
    expect(wrapper.find(selector('source-save')).exists()).toBe(false)
    expect(wrapper.find(selector('original-upload')).exists()).toBe(false)
    expect(wrapper.get(selector('admin-message')).attributes('role')).toBe('alert')
    wrapper.unmount()
  })
  it('numeric form inputs and separate unchecked confirmation create the exact source request', async () => {
    const api = adminApi(), wrapper = mount(AdminView, { props: { actor, api } }); await flushPromises()
    expect((wrapper.get(selector('source-confirm')).element as HTMLInputElement).checked).toBe(false)
    const fields = { 'source-dataset': datasetId, 'source-dataset-revision': '1', 'source-reference': 'DEMO_source',
      'source-publisher': definition().publisher, 'source-url': definition().entry_url, 'source-data-type': 'entry_requirements',
      'source-scope': definition().scope_note, 'source-manual-permission': 'granted', 'source-recheck': '30',
      'source-basis': definition().license_basis!, 'source-permission-reference': definition().permission_record_reference! }
    for (const [name, value] of Object.entries(fields)) await wrapper.get(selector(name)).setValue(value)
    await wrapper.get(selector('source-manual-enabled')).setValue(true)
    expect(wrapper.get(selector('source-save')).attributes('disabled')).toBeDefined()
    await wrapper.get(selector('source-confirm')).setValue(true)
    expect(wrapper.get(selector('source-save')).attributes('disabled')).toBeUndefined()
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(api.register).toHaveBeenCalledWith(expect.objectContaining({ confirmed: true, expected_dataset_revision: 1,
      source: expect.objectContaining({ dataset_id: datasetId, is_synthetic: true, definition: definition() }) }), expect.any(AbortSignal))
    expect(wrapper.get(selector('source-result')).text()).toContain('读取版本 1')
    expect((wrapper.get(selector('source-confirm')).element as HTMLInputElement).checked).toBe(false)
    wrapper.unmount()
  })
  it('renders an HTML-looking publisher and stored URL as escaped text, with no URL navigation', async () => {
    const publisher = 'DEMO_<img src=x onerror=alert(1)>', url = 'https://source-sentinel.invalid/?secret=notvisited'
    const api = adminApi({ source: vi.fn(async () => source({ publisher, entry_url: url })) })
    const wrapper = mount(AdminView, { props: { actor, api } }); await flushPromises()
    await wrapper.get(selector('source-query-id')).setValue(sourceId)
    await wrapper.get(selector('source-query-button')).trigger('click'); await flushPromises()
    expect(wrapper.get(selector('source-result')).text()).toContain(publisher)
    expect(wrapper.get(selector('source-result')).text()).toContain(url)
    expect(wrapper.find('img').exists()).toBe(false); expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.get(selector('admin-demo')).text()).toContain('不是真实官方')
    wrapper.unmount()
  })
  it('shows unknown rejected totals and only fixed error positions, with no published success', async () => {
    const wrapper = mount(AdminView, { props: { actor, api: adminApi({ result: vi.fn(async () => rejected()) }) } }); await flushPromises()
    await wrapper.get(selector('import-query-id')).setValue(rejected().id)
    await wrapper.get(selector('import-query-button')).trigger('click'); await flushPromises()
    const output = wrapper.get(selector('import-result'))
    expect(output.text()).toContain('rejected'); expect(output.text()).toContain('候选写入为 0'); expect(output.text()).toContain('结构未知（不是 0 行）')
    expect(wrapper.get(selector('import-errors')).text()).toContain('INVALID_STRUCTURE')
    expect(output.text()).not.toContain('发布成功'); expect(wrapper.find(selector('original-confirm')).exists()).toBe(false)
    wrapper.unmount()
  })
  it('changing the actor to null clears visible source metadata and original inputs', async () => {
    const wrapper = mount(AdminView, { props: { actor, api: adminApi() } }); await flushPromises()
    await wrapper.get(selector('source-query-id')).setValue(sourceId); await wrapper.get(selector('source-query-button')).trigger('click'); await flushPromises()
    await wrapper.get(selector('original-content')).setValue('DEMO secret original')
    await wrapper.setProps({ actor: null }); await flushPromises()
    expect(wrapper.find(selector('source-result')).exists()).toBe(false); expect(wrapper.find(selector('original-content')).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('DEMO secret original'); expect(wrapper.get(selector('context-status')).text()).toContain('尚未登录')
    wrapper.unmount()
  })
})
