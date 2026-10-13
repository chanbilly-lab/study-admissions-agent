import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import SharingPanel from '../src/features/sharing/SharingPanel.vue'
import { SharingError } from '../src/features/sharing/client'
import { actor, otherActor, grant, grants, policy, sharingApi, now, resourceId, grantId } from './sharingFixtures'
let wrapper: VueWrapper | undefined
beforeEach(() => vi.spyOn(Date, 'now').mockReturnValue(now))
afterEach(() => wrapper?.unmount())
describe('explicit sharing panel', () => {
  it('closed deployment shows the boundary without collecting inputs', async () => {
    wrapper = mount(SharingPanel, { props: { actor, api: sharingApi({ policy: vi.fn(async () => policy({ sharing_available: false, readiness_reason: 'disabled' })) }) } })
    await flushPromises()
    expect(wrapper.text()).toContain('共享配置未开放'); expect(wrapper.text()).toContain('真实共享未开放')
    expect(wrapper.find('form').exists()).toBe(false); expect(wrapper.find('input').exists()).toBe(false)
  })
  it('anonymous policy is escaped and has no private requests or form', async () => {
    const api = sharingApi({ policy: vi.fn(async () => policy({ text: '<img src=x onerror=alert(1)>' })) })
    wrapper = mount(SharingPanel, { props: { actor: null, api } }); await flushPromises()
    expect(wrapper.find('img').exists()).toBe(false); expect(wrapper.text()).toContain('<img src=x')
    expect(api.list).not.toHaveBeenCalled(); expect(wrapper.find('form').exists()).toBe(false)
  })
  it.each(['issued', 'received'] as const)('policy 503 exposes only %s revocation/refusal controls', async direction => {
    const current = direction === 'issued' ? actor : otherActor
    const api = sharingApi({ policy: vi.fn().mockRejectedValue(new SharingError(503)),
      list: vi.fn(async queried => grants({ user_id: current.user_id, items: queried === direction ? [grant()] : [], total: queried === direction ? 1 : 0 })) })
    wrapper = mount(SharingPanel, { props: { actor: current, api } }); await flushPromises()
    if (direction === 'received') { await wrapper.get('button[aria-pressed="false"]').trigger('click'); await flushPromises() }
    expect(wrapper.get('[data-testid="sharing-policy-unavailable"]').text()).toContain('创建和接受保持关闭')
    expect(wrapper.find('form').exists()).toBe(false); expect(wrapper.find(`[data-testid="accept-grant-${grantId}"]`).exists()).toBe(false)
    expect(wrapper.get(`[data-testid="revoke-grant-${grantId}"]`).text()).toBe(direction === 'issued' ? '撤销此项授权' : '拒绝此项共享')
  })
  it('has no default selections, uses concrete metadata scope and resets confirmation after input changes', async () => {
    const api = sharingApi(); wrapper = mount(SharingPanel, { props: { actor, api } }); await flushPromises()
    expect((wrapper.get('[data-testid="grant-confirmation"]').element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.get('[data-testid="create-grant"]').attributes()).toHaveProperty('disabled')
    await wrapper.get('[data-testid="grant-kind"]').setValue('profile')
    expect((wrapper.get('[data-testid="grant-field-status"]').element as HTMLInputElement).checked).toBe(false)
    await wrapper.get('[data-testid="grant-resource"]').setValue(resourceId)
    await wrapper.get('[data-testid="grant-resource-version"]').setValue('1')
    await wrapper.get('[data-testid="grant-grantee"]').setValue(otherActor.user_id)
    await wrapper.get('[data-testid="grant-expiry"]').setValue('2026-10-04T00:00')
    await wrapper.get('[data-testid="grant-field-status"]').setValue(true)
    await wrapper.get('[data-testid="grant-action-read"]').setValue(true)
    await wrapper.get('[data-testid="grant-confirmation"]').setValue(true)
    expect(wrapper.get('[data-testid="create-grant"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="grant-resource-version"]').setValue('2')
    expect((wrapper.get('[data-testid="grant-confirmation"]').element as HTMLInputElement).checked).toBe(false)
    await wrapper.get('[data-testid="grant-confirmation"]').setValue(true)
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(api.create).toHaveBeenCalledOnce()
    expect(vi.mocked(api.create).mock.calls[0][0].expected_resource_version).toBe(2)
    expect(wrapper.text()).not.toContain('年龄已核验')
    expect(wrapper.find('input[name="owner"],input[name="roles"],input[name="guardian"],input[type="file"]').exists()).toBe(false)
  })
  it('labels an accepted but no longer effective grant accurately', async () => {
    wrapper = mount(SharingPanel, { props: { actor, api: sharingApi({ list: vi.fn(async () => grants({ items: [grant({ state: 'accepted', accepted_at: '2026-10-03T00:00:01Z' })], total: 1 })) }) } })
    await flushPromises(); expect(wrapper.text()).toContain('已接受'); expect(wrapper.get('[data-testid="grant-effective"]').text()).toContain('无有效访问许可')
  })
  it('recipient receives independent acceptance and refusal without requiring a role', async () => {
    const api = sharingApi({ list: vi.fn(async direction => grants({ user_id: otherActor.user_id, owner_consent_id: null, items: direction === 'received' ? [grant()] : [], total: direction === 'received' ? 1 : 0 })) })
    wrapper = mount(SharingPanel, { props: { actor: otherActor, api } }); await flushPromises()
    await wrapper.get('button[aria-pressed="false"]').trigger('click'); await flushPromises()
    expect(wrapper.get(`[data-testid="accept-grant-${grantId}"]`).attributes()).toHaveProperty('disabled')
    expect(wrapper.text()).toContain('拒绝此项共享')
    await wrapper.get(`[data-testid="accept-confirm-${grantId}"]`).setValue(true)
    await wrapper.get(`[data-testid="accept-grant-${grantId}"]`).trigger('click'); await flushPromises()
    expect(api.accept).toHaveBeenCalledOnce()
  })
  it('allows rejection or withdrawal under reduced admission', async () => {
    const api = sharingApi({ list: vi.fn(async direction => grants({ user_id: otherActor.user_id, actor_declaration_id: null, owner_consent_id: null, items: direction === 'received' ? [grant({ state: 'accepted', accepted_at: '2026-10-03T00:00:01Z' })] : [], total: direction === 'received' ? 1 : 0 })) })
    wrapper = mount(SharingPanel, { props: { actor: otherActor, api } }); await flushPromises()
    await wrapper.get('button[aria-pressed="false"]').trigger('click'); await flushPromises()
    expect(wrapper.find(`[data-testid="accept-grant-${grantId}"]`).exists()).toBe(false)
    expect(wrapper.get(`[data-testid="revoke-grant-${grantId}"]`).text()).toBe('退出此项共享')
  })
})
