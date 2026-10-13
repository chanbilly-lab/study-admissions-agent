import { mount, flushPromises } from '@vue/test-utils'
import { beforeAll, describe, it, expect, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import NotificationsPanel from '../src/features/plans/notifications/NotificationsPanel.vue'
import PlanView from '../src/views/PlanView.vue'
import type { useNotifications } from '../src/features/plans/notifications/useNotifications'
import { NotificationError } from '../src/features/plans/notifications/client'
import { PlanError } from '../src/features/plans/client'
import { planApi } from './plansFixtures'
import { actor, version, preference, notification, page, notificationApi, deferred } from './notificationsFixtures'
beforeAll(() => Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true }))
const props = () => ({ actor, coreAllowed: true, profile: version(), profileEpoch: 1, api: notificationApi() })
type Wrapper = ReturnType<typeof mount>
const idle = (wrapper: Wrapper) => expect(wrapper.get('[data-testid="notifications-workspace"]').attributes('aria-busy')).toBe('false')
async function ready(wrapper: Wrapper) { await vi.waitFor(() => { expect(wrapper.find('[data-testid="notifications-preferences-read"]').exists()).toBe(true); idle(wrapper) }) }
async function visible(wrapper: Wrapper, selector: string) { await vi.waitFor(() => { expect(wrapper.find(selector).exists()).toBe(true); idle(wrapper) }) }

describe('T36 lazy in-app notifications panel', () => {
  it('keeps the old PlanView entry folded with no reminder inputs or probes', async () => {
    const api = notificationApi(), wrapper = mount(PlanView, { props: { actor, coreAllowed: true, profile: null, profileEpoch: 1, targets: [], api: planApi(), notificationApi: api } })
    await flushPromises()
    expect(wrapper.get('[data-testid="notifications-toggle"]').attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[data-testid="notifications-workspace"]').exists()).toBe(false); expect(api.context).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="notifications-toggle"]').trigger('click'); await ready(wrapper)
    expect(api.context).toHaveBeenCalledOnce(); expect(api.preferences).not.toHaveBeenCalled(); expect(api.list).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('reads legitimate reminders independently of an old plan source conflict and without selected profile', async () => {
    const api = notificationApi(), old = planApi({ list: async () => { throw new PlanError(409) } })
    const wrapper = mount(PlanView, { props: { actor, coreAllowed: true, profile: null, profileEpoch: 1, targets: [], api: old, notificationApi: api } })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="plan-list"]').exists()).toBe(true))
    await wrapper.get('[data-testid="plan-list"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="plan-conflict"]').exists()).toBe(true))
    await wrapper.get('[data-testid="notifications-toggle"]').trigger('click'); await ready(wrapper)
    await wrapper.get('[data-testid="notifications-read"]').trigger('click'); await visible(wrapper, '[data-testid="notifications-page"]')
    expect(wrapper.find('[data-testid="notification-' + notification().id + '"]').exists()).toBe(true); expect(api.list).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
  it('keeps a real asynchronous selected profile through initial context loading and requires explicit opt-in confirmation', async () => {
    const p = props(), wrapper = mount(NotificationsPanel, { props: p }); await ready(wrapper)
    await wrapper.get('[data-testid="notifications-preferences-read"]').trigger('click'); await visible(wrapper, '[data-testid="notifications-selected-profile"]')
    expect(wrapper.get('[data-testid="notifications-enabled"]').element).toHaveProperty('checked', false)
    expect(wrapper.text()).toContain('重新登录或修改画像后须重新确认')
    await wrapper.get('[data-testid="notifications-enabled"]').setValue(true)
    expect(wrapper.get('[data-testid="notifications-preferences-save"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="notifications-preference-confirm"]').setValue(true); await wrapper.get('[data-testid="notifications-preferences-save"]').trigger('click')
    await vi.waitFor(() => { expect(wrapper.text()).toContain('服务端版本 1'); idle(wrapper) })
    expect(p.api.savePreferences).toHaveBeenCalledOnce(); expect(wrapper.get('[data-testid="notifications-preference-confirm"]').element).toHaveProperty('checked', false)
    wrapper.unmount()
  })
  it('shows only finite review messages and marks read only after the server confirms', async () => {
    const pending = deferred<ReturnType<typeof notification>>(), p = props(); p.api = notificationApi({ markRead: () => pending.promise })
    const wrapper = mount(NotificationsPanel, { props: p }); await ready(wrapper)
    await wrapper.get('[data-testid="notifications-read"]').trigger('click'); await visible(wrapper, '[data-testid="notifications-page"]')
    expect(wrapper.text()).toContain('原依据待复核'); expect(wrapper.text()).toContain('没有资格或录取结论'); expect(wrapper.find('a').exists()).toBe(false)
    await wrapper.get('[data-testid="notification-mark-read-' + notification().id + '"]').trigger('click')
    expect(wrapper.find('[data-testid="notification-read-at-' + notification().id + '"]').exists()).toBe(false)
    pending.resolve(notification(true)); await visible(wrapper, '[data-testid="notification-read-at-' + notification().id + '"]')
    expect(wrapper.text()).toContain(notification(true).read_at!); expect(wrapper.text()).toContain('读取版本 2')
    wrapper.unmount()
  })
  it('shows a version conflict with no optimistic read or automatic rewrite, then permits explicit current read', async () => {
    const p = props(); p.api = notificationApi({ savePreferences: vi.fn(async () => { throw new NotificationError(409) }) })
    const wrapper = mount(NotificationsPanel, { props: p }); await ready(wrapper)
    await wrapper.get('[data-testid="notifications-preferences-read"]').trigger('click'); await visible(wrapper, '[data-testid="notifications-preferences"]')
    await wrapper.get('[data-testid="notifications-enabled"]').setValue(true); await wrapper.get('[data-testid="notifications-preference-confirm"]').setValue(true)
    await wrapper.get('[data-testid="notifications-preferences-save"]').trigger('click'); await visible(wrapper, '[data-testid="notifications-conflict"]')
    expect(wrapper.find('[data-testid="notifications-preferences-save"]').exists()).toBe(false); expect(p.api.savePreferences).toHaveBeenCalledOnce()
    await wrapper.get('[data-testid="notifications-preferences-read"]').trigger('click'); await visible(wrapper, '[data-testid="notifications-preferences"]')
    expect(wrapper.find('[data-testid="notifications-conflict"]').exists()).toBe(false); expect(wrapper.get('[data-testid="notifications-preference-confirm"]').element).toHaveProperty('checked', false)
    wrapper.unmount()
  })
  it('clears a private pending inbox synchronously on withdrawal and ignores its successful late response', async () => {
    const pending = deferred<ReturnType<typeof page>>(), p = props(); p.api = notificationApi({ list: () => pending.promise })
    const wrapper = mount(NotificationsPanel, { props: p }); await ready(wrapper)
    const workspace = (wrapper.vm as unknown as { workspace: ReturnType<typeof useNotifications> }).workspace, read = vi.spyOn(workspace, 'readNotifications')
    await wrapper.get('[data-testid="notifications-read"]').trigger('click'); const settled = read.mock.results[0]!.value
    await wrapper.setProps({ coreAllowed: false }); expect(wrapper.find('input').exists()).toBe(false)
    pending.resolve(page()); await settled; await flushPromises()
    expect(wrapper.find('[data-testid="notifications-page"]').exists()).toBe(false); expect(wrapper.text()).not.toContain(notification().id)
    wrapper.unmount()
  })
  it('clears existing messages and preference confirmation on a profile epoch change', async () => {
    const p = props(), wrapper = mount(NotificationsPanel, { props: p }); await ready(wrapper)
    await wrapper.get('[data-testid="notifications-read"]').trigger('click'); await visible(wrapper, '[data-testid="notifications-page"]')
    await wrapper.get('[data-testid="notifications-preferences-read"]').trigger('click'); await visible(wrapper, '[data-testid="notifications-preferences"]')
    await wrapper.get('[data-testid="notifications-preference-confirm"]').setValue(true)
    await wrapper.setProps({ profileEpoch: 2 }); expect(wrapper.find('[data-testid="notifications-page"]').exists()).toBe(false); expect(wrapper.find('[data-testid="notifications-preferences"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain(notification().id); wrapper.unmount()
  })
})
