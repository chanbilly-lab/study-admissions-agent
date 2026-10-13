import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import AuthView from '../src/features/auth/AuthView.vue'
import { SessionError, type SessionData } from '../src/features/auth/client'

const actor: SessionData = { authenticated: true, user_id: '0e3ef957-3cdd-4f44-8147-b0fe1d46b8f8', expires_at: '2030-10-02T12:00:00Z', is_synthetic: true, private_business_available: false }
const writeApi = () => ({ csrf: vi.fn(async () => ({ csrf_token: 'T'.repeat(43), expires_at: actor.expires_at })), logout: vi.fn(async () => ({ logged_out: true as const })) })
let wrapper: VueWrapper | undefined
afterEach(() => wrapper?.unmount())

describe('independent identity view', () => {
  it('offers a top-level login link with no role, return URL or proof parameters', async () => {
    const api = { ...writeApi(), loginPath: '/api/v2/auth/login', session: vi.fn().mockRejectedValue(new SessionError(401)) }
    wrapper = mount(AuthView, { props: { api } })
    await flushPromises()
    expect(wrapper.get('a.auth-login').attributes('href')).toBe('/api/v2/auth/login')
    expect(wrapper.text()).toContain('尚未登录')
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('退出登录')
    expect(wrapper.text()).toContain('不会自动注册')
  })

  it('labels a synthetic session and removes its ID after an expired refresh', async () => {
    const api = { ...writeApi(), loginPath: '/api/v2/auth/login', session: vi.fn().mockResolvedValueOnce(actor).mockRejectedValueOnce(new SessionError(401)) }
    wrapper = mount(AuthView, { props: { api } })
    await flushPromises()
    expect(wrapper.get('[data-testid="actor-id"]').text()).toBe(actor.user_id)
    expect(wrapper.get('[data-testid="synthetic-banner"]').text()).toContain('DEMO')
    expect(wrapper.text()).toContain('私有业务')
    expect(wrapper.text()).toContain('尚未开放')
    await wrapper.get('button.auth-refresh').trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain(actor.user_id)
    expect(wrapper.find('a.auth-login').exists()).toBe(true)
  })

  it.each([403, 404, 503])('shows the closed/error state %s without a login or demo fallback', async (status) => {
    const api = { ...writeApi(), loginPath: '/api/v2/auth/login', session: vi.fn().mockRejectedValue(new SessionError(status)) }
    wrapper = mount(AuthView, { props: { api } })
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.find('a.auth-login').exists()).toBe(false)
    expect(wrapper.find('[data-testid="actor-id"]').exists()).toBe(false)
    expect(wrapper.find('#demo-user').exists()).toBe(false)
  })
})
