import { mount, flushPromises } from '@vue/test-utils'
import { beforeAll, describe, it, expect, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import RevisionPanel from '../src/features/plans/revisions/RevisionPanel.vue'
import PlanView from '../src/views/PlanView.vue'
import { RevisionError } from '../src/features/plans/revisions/client'
import type { useRevisions } from '../src/features/plans/revisions/useRevisions'
import { actor, profile, newPlan, history, revisionApi, planApi, deferred } from './revisionsFixtures'

beforeAll(() => Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true }))
const props = () => ({ actor, coreAllowed: true, profile: profile(), profileEpoch: 1, current: null, api: revisionApi(), planApi: planApi({ get: async () => newPlan() }) })
type Wrapper = ReturnType<typeof mount>
const idle = (wrapper: Wrapper) => expect(wrapper.get('[data-testid="revision-workspace"]').attributes('aria-busy')).toBe('false')
async function ready(wrapper: Wrapper) {
  await vi.waitFor(() => {
    expect(wrapper.find('[data-testid="revision-propose-confirm"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('写操作须先明确选择当前确认画像。')
    idle(wrapper)
  })
}
async function visible(wrapper: Wrapper, selector: string) {
  await vi.waitFor(() => { expect(wrapper.find(selector).exists()).toBe(true); idle(wrapper) })
}
async function selectPair(wrapper: Wrapper) {
  await wrapper.get('[data-testid="revision-new-id"]').setValue(newPlan().plan_id)
  await wrapper.get('[data-testid="revision-new-read"]').trigger('submit')
  await visible(wrapper, '[data-testid="revision-new-candidate"]')
  await wrapper.get('[data-testid="revision-old-id"]').setValue(history().pin.plan_id)
  await wrapper.get('[data-testid="revision-old-read"]').trigger('submit')
  await visible(wrapper, '[data-testid="revision-history-old"]')
}

describe('T35 bounded revision panel', () => {
  it('keeps the old PlanView entry lazy with no new probes or inputs', async () => {
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)
    const wrapper = mount(PlanView, { props: { actor, coreAllowed: true, profile: profile(), profileEpoch: 1, targets: [], api: planApi() } })
    await flushPromises()
    expect(wrapper.find('[data-testid="revision-toggle"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="revision-workspace"]').exists()).toBe(false)
    expect(fetcher).not.toHaveBeenCalled()
    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('mounts a real async current profile and current new draft without losing context', async () => {
    const p = props(), wrapper = mount(RevisionPanel, { props: { ...p, current: newPlan() } })
    await ready(wrapper)
    await visible(wrapper, '[data-testid="revision-new-candidate"]')
    expect(p.api.context).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-testid="revision-new-id"]').element).toHaveProperty('value', newPlan().plan_id)
    wrapper.unmount()
  })

  it('requires separate proposal and decision checkboxes, shows history, and keeps the new plan unconfirmed', async () => {
    const p = props(), wrapper = mount(RevisionPanel, { props: p })
    await ready(wrapper)
    await selectPair(wrapper)
    expect(wrapper.get('[data-testid="revision-propose"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="revision-completions-old"]').text()).toContain('student_declared')
    await wrapper.get('[data-testid="revision-propose-confirm"]').setValue(true)
    await wrapper.get('[data-testid="revision-propose"]').trigger('click')
    await visible(wrapper, '[data-testid="revision-diff"]')
    expect(wrapper.get('[data-testid="revision-diff"]').text()).toContain('本人确认画像版本')
    expect(wrapper.get('[data-testid="revision-accept"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="revision-decision-confirm"]').setValue(true)
    await wrapper.get('[data-testid="revision-accept"]').trigger('click')
    await visible(wrapper, '[data-testid="revision-accepted"]')
    expect(wrapper.get('[data-testid="revision-accepted"]').text()).toContain('新草案未被最终确认')
    expect(wrapper.get('[data-testid="revision-completions-new"]').text()).toContain('无原完成记录')
    expect(p.planApi.confirm).not.toHaveBeenCalled()
    expect(p.planApi.complete).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows a rejected revision with its original completion references', async () => {
    const p = props(), wrapper = mount(RevisionPanel, { props: p })
    await ready(wrapper)
    await selectPair(wrapper)
    await wrapper.get('[data-testid="revision-propose-confirm"]').setValue(true)
    await wrapper.get('[data-testid="revision-propose"]').trigger('click')
    await visible(wrapper, '[data-testid="revision-diff"]')
    await wrapper.get('[data-testid="revision-decision-confirm"]').setValue(true)
    await wrapper.get('[data-testid="revision-reject"]').trigger('click')
    await visible(wrapper, '[data-testid="revision-rejected"]')
    expect(wrapper.get('[data-testid="revision-completions-old"]').text()).toContain('student_declared')
    wrapper.unmount()
  })

  it('renders original task labels as text and never turns source fields into links', async () => {
    const h = history()
    h.tasks[0]!.title = 'DEMO_<img src="https://sentinel.invalid/x" onerror="window.fail=1">'
    const { hash } = await import('./revisionsFixtures')
    h.tasks[0]!.task_key = hash(Object.fromEntries(['kind', 'action_code', 'title', 'acceptance_criteria', 'assessment_key', 'basis', 'unit', 'scale', 'work_scope_sha256'].map(k => [k, h.tasks[0]![k as keyof typeof h.tasks[0]]])))
    h.completion_refs[0]!.task_key = h.tasks[0]!.task_key
    h.schedule = null
    h.pin.schedule_sha256 = null
    const p = props()
    p.api = revisionApi({ history: async () => h })
    const wrapper = mount(RevisionPanel, { props: p })
    await ready(wrapper)
    await wrapper.get('[data-testid="revision-old-id"]').setValue(h.pin.plan_id)
    await wrapper.get('[data-testid="revision-old-read"]').trigger('submit')
    await visible(wrapper, '[data-testid="revision-history-old"]')
    expect(wrapper.text()).toContain('<img')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('a').exists()).toBe(false)
    wrapper.unmount()
  })

  it('immediately erases history on withdrawal and ignores a successful late 200', async () => {
    const pending = deferred<ReturnType<typeof history>>(), p = props()
    p.api = revisionApi({ history: () => pending.promise })
    const wrapper = mount(RevisionPanel, { props: p })
    await ready(wrapper)
    const workspace = (wrapper.vm as unknown as { workspace: ReturnType<typeof useRevisions> }).workspace
    const read = vi.spyOn(workspace, 'readOldPlan')
    await wrapper.get('[data-testid="revision-old-id"]').setValue(history().pin.plan_id)
    await wrapper.get('[data-testid="revision-old-read"]').trigger('submit')
    expect(read).toHaveBeenCalledOnce()
    const settled = read.mock.results[0]!.value
    await wrapper.setProps({ coreAllowed: false })
    expect(wrapper.find('input').exists()).toBe(false)
    pending.resolve(history())
    await settled
    await flushPromises()
    expect(wrapper.find('[data-testid="revision-history-old"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('keeps the fixed permission error visible when invalidation also clears the parent current plan', async () => {
    const p = props()
    p.api = revisionApi({ history: async () => { throw new RevisionError(403) } })
    const wrapper = mount(RevisionPanel, { props: { ...p, current: newPlan() } })
    await ready(wrapper)
    await visible(wrapper, '[data-testid="revision-new-candidate"]')
    await wrapper.get('[data-testid="revision-old-id"]').setValue(history().pin.plan_id)
    await wrapper.get('[data-testid="revision-old-read"]').trigger('submit')
    await vi.waitFor(() => expect(wrapper.emitted('privateInvalidated')).toHaveLength(1))
    await wrapper.setProps({ current: null })
    expect(wrapper.get('[data-testid="revision-message"]').text()).toContain('权限已失效')
    expect(wrapper.find('[data-testid="revision-new-candidate"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
