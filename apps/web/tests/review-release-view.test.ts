import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ReviewReleaseView from '../src/views/admin/ReviewReleaseView.vue'
import ReviewPanel from '../src/features/admin/reviews/ReviewPanel.vue'
import { ReviewWorkspaceError } from '../src/features/admin/reviews/client'
import { actor, otherActor, deferred, workspaceApi, publicApi, reviewContext, detail, snippet, factId, datasetId, scope } from './reviewReleaseFixtures'
const selector = (name: string) => `[data-testid="${name}"]`
afterEach(() => vi.restoreAllMocks())

describe('review and release workspace interactions', () => {
  it.each([403, 503])('shows server denial %s with no private controls while keeping an independent anonymous preview', async status => {
    const api = workspaceApi({ context: vi.fn(async () => { throw new ReviewWorkspaceError(status) }) }), anonymous = publicApi()
    const wrapper = mount(ReviewReleaseView, { props: { actor, api, publicApi: anonymous } }); await flushPromises()
    expect(wrapper.find(selector('prep-load')).exists()).toBe(false); expect(wrapper.find(selector('review-decide')).exists()).toBe(false)
    expect(wrapper.find(selector('release-publish')).exists()).toBe(false); expect(wrapper.find(selector('public-toggle')).exists()).toBe(true)
    expect(anonymous.offerings).not.toHaveBeenCalled(); expect(wrapper.get(selector('review-context-status')).attributes('role')).toBe('alert'); wrapper.unmount()
  })
  it('renders bounded original and unknown scope as text and starts all ten checks unselected', async () => {
    const text = 'DEMO_<img src=https://source-sentinel.invalid/x onerror=alert(1)>', api = workspaceApi({ detail: vi.fn(async () => detail({ evidence: snippet({ text }), scope: { ...scope, province: { status: 'unknown', value: null } }, gaps: ['INCOMPLETE_SCOPE'] })) })
    const wrapper = mount(ReviewPanel, { props: { actor: otherActor, api } })
    await wrapper.get(selector('review-fact-id')).setValue(factId); await wrapper.get(selector('review-load')).trigger('click'); await flushPromises()
    expect(wrapper.get(selector('review-original')).text()).toBe(text); expect(wrapper.find('img').exists()).toBe(false); expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.text()).toContain('unknown / null'); expect(wrapper.get(selector('review-gaps')).text()).toContain('INCOMPLETE_SCOPE')
    expect(wrapper.findAll('select[data-testid^="review-check-"]').map(item => (item.element as HTMLSelectElement).value)).toEqual(Array(10).fill(''))
    expect((wrapper.get(selector('review-confirm')).element as HTMLInputElement).checked).toBe(false); expect(wrapper.get(selector('review-decide')).attributes('disabled')).toBeDefined(); wrapper.unmount()
  })
  it('submits ten explicit judgments with separate confirmation and displays only the returned review decision', async () => {
    const api = workspaceApi(), wrapper = mount(ReviewPanel, { props: { actor: otherActor, api } })
    await wrapper.get(selector('review-fact-id')).setValue(factId); await wrapper.get(selector('review-load')).trigger('click'); await flushPromises()
    for (const field of ['original_value','claim_kind','unit','period','scope','evidence_location','missingness','footnote','statistics_context','date_context']) await wrapper.get(selector(`review-check-${field}`)).setValue('accepted')
    await wrapper.get(selector('review-action')).setValue('approve'); expect(wrapper.get(selector('review-decide')).attributes('disabled')).toBeDefined()
    await wrapper.get(selector('review-confirm')).setValue(true); await wrapper.get(selector('review-decide')).trigger('click'); await flushPromises()
    expect(api.review).toHaveBeenCalledOnce(); expect(wrapper.get(selector('review-decision-result')).text()).toContain('尚未发布'); expect(wrapper.find(selector('review-detail')).exists()).toBe(false); wrapper.unmount()
  })
  it('clears private panels and original inputs on actor loss and ignores a late capability response', async () => {
    const pending = deferred<ReturnType<typeof reviewContext>>(), api = workspaceApi({ context: vi.fn().mockResolvedValueOnce(reviewContext()).mockImplementationOnce(() => pending.promise) })
    const wrapper = mount(ReviewReleaseView, { props: { actor, api, publicApi: publicApi() } }); await flushPromises()
    await wrapper.get(selector('review-dataset')).setValue(datasetId); await wrapper.get(selector('prep-import-id')).setValue('private reference')
    await wrapper.setProps({ actor: otherActor }); await wrapper.setProps({ actor: null }); pending.resolve(reviewContext()); await flushPromises()
    expect(wrapper.find(selector('review-panel')).exists()).toBe(false); expect(wrapper.find(selector('prep-import-id')).exists()).toBe(false)
    expect(wrapper.find(selector('public-toggle')).exists()).toBe(true); expect(wrapper.text()).not.toContain('private reference'); wrapper.unmount()
  })
  it('uses server capability flags rather than presenting student-side preparation or publishing', async () => {
    const wrapper = mount(ReviewReleaseView, { props: { actor, api: workspaceApi({ context: vi.fn(async () => reviewContext({ can_prepare: false, can_review: false, can_publish: false, can_withdraw: false })) }), publicApi: publicApi() } })
    await flushPromises(); expect(wrapper.find(selector('prep-load')).exists()).toBe(false); expect(wrapper.find(selector('release-precheck')).exists()).toBe(false)
    expect(wrapper.text()).toContain('服务器未开放独立审核能力'); wrapper.unmount()
  })
})
