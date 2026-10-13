import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPublicPreviewApi, type PublicPreviewApi } from '../src/features/admin/releases/publicClient'
import PublicReleasePreview from '../src/features/admin/releases/PublicReleasePreview.vue'
import { deferred, publicApi, publicOffering, publicRecords, releaseId } from './reviewReleaseFixtures'
const response = (data: unknown) => new Response(JSON.stringify({ data, meta: { api_version: 'v2', request_id: 'c'.repeat(32) } }), { status: 200 })
describe('actual anonymous release projection', () => {
  it('uses explicit year and omits credentials, with no private endpoint or CSRF', async () => {
    const fetcher = vi.fn().mockResolvedValue(response(publicRecords())), api = createPublicPreviewApi(fetcher)
    await api.offerings(2027)
    expect(fetcher).toHaveBeenCalledWith('/public/v2/offerings?entry_year=2027&limit=20', expect.objectContaining({ method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error' }))
    expect(fetcher).toHaveBeenCalledOnce(); expect(fetcher.mock.calls[0][1].headers).not.toHaveProperty('X-CSRF-Token')
  })
  it('does not accept internal release DTO or fabricated coverage', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ release_id: releaseId, members: [] }))
      .mockResolvedValueOnce(response({ ...publicRecords(), coverage: { ...publicRecords().coverage, coverage_ratio: 1 } }))
    await expect(createPublicPreviewApi(fetcher).offerings(2027)).rejects.toMatchObject({ status: 200 })
    await expect(createPublicPreviewApi(fetcher).offerings(2027)).rejects.toMatchObject({ status: 200 })
  })
  it('closed API remains unavailable without fallback records', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('RAW_SECRET', { status: 503 }))
    const error = await createPublicPreviewApi(fetcher).offerings(2027).catch(error => error)
    expect(error.status).toBe(503); expect(error.message).not.toContain('RAW_SECRET'); expect(fetcher).toHaveBeenCalledOnce()
  })
  it.each([
    { ...publicRecords(), coverage: { ...publicRecords().coverage, status: 'no_published_records' } },
    { ...publicRecords(), page: { limit: 20, has_more: true, next_cursor: null } },
  ])('rejects contradictory empty coverage or next-page state', async data => {
    await expect(createPublicPreviewApi(vi.fn().mockResolvedValue(response(data))).offerings(2027)).rejects.toMatchObject({ status: 200 })
  })
  it('requires a year, then shows the public release ID and a withdrawal empty state', async () => {
    const api = publicApi(), wrapper = mount(PublicReleasePreview, { props: { api } })
    expect(wrapper.find('input').exists()).toBe(false); expect(wrapper.get('[data-testid="public-toggle"]').attributes('aria-expanded')).toBe('false')
    await wrapper.get('[data-testid="public-toggle"]').trigger('click')
    await wrapper.get('[data-testid="public-refresh"]').trigger('click'); expect(api.offerings).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="public-year"]').setValue('2027'); await wrapper.get('[data-testid="public-refresh"]').trigger('click'); await flushPromises()
    expect(wrapper.get('[data-testid="public-result"]').text()).toContain(releaseId)
    expect(wrapper.text()).toContain('DEMO 合成'); expect(wrapper.text()).toContain('覆盖总量和比例未知')
    api.offerings.mockResolvedValue(publicRecords([])); await wrapper.get('[data-testid="public-refresh"]').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('没有可公开记录'); expect(wrapper.text()).not.toContain(releaseId); wrapper.unmount()
  })
  it('changing year invalidates a late page and never executes imported HTML', async () => {
    const wait = deferred<ReturnType<typeof publicRecords>>(), api = { offerings: vi.fn(() => wait.promise) }
    const wrapper = mount(PublicReleasePreview, { props: { api } })
    await wrapper.get('[data-testid="public-toggle"]').trigger('click')
    await wrapper.get('[data-testid="public-year"]').setValue('2027'); await wrapper.get('[data-testid="public-refresh"]').trigger('click')
    await wrapper.get('[data-testid="public-year"]').setValue('2026')
    wait.resolve(publicRecords([publicOffering({ institution_name: 'DEMO_<img src=x onerror=alert(1)>' })])); await flushPromises()
    expect(wrapper.find('[data-testid="public-result"]').exists()).toBe(false); expect(wrapper.find('img').exists()).toBe(false); wrapper.unmount()
  })
  it('collapsing the anonymous form removes inputs, aborts its pending page and ignores a late response', async () => {
    const pending = deferred<ReturnType<typeof publicRecords>>(), api = { offerings: vi.fn((..._args: Parameters<PublicPreviewApi['offerings']>) => pending.promise) }
    const wrapper = mount(PublicReleasePreview, { props: { api } })
    await wrapper.get('[data-testid="public-toggle"]').trigger('click'); await wrapper.get('[data-testid="public-year"]').setValue('2027')
    await wrapper.get('[data-testid="public-refresh"]').trigger('click'); await wrapper.get('[data-testid="public-toggle"]').trigger('click')
    expect(api.offerings.mock.calls[0][1]?.aborted).toBe(true)
    pending.resolve(publicRecords()); await flushPromises(); expect(wrapper.find('input').exists()).toBe(false); expect(wrapper.find('[data-testid="public-result"]').exists()).toBe(false)
    await wrapper.get('[data-testid="public-toggle"]').trigger('click'); expect((wrapper.get('[data-testid="public-year"]').element as HTMLInputElement).value).toBe(''); wrapper.unmount()
  })
})
