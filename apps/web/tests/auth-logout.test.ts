import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import AuthView from '../src/features/auth/AuthView.vue'
import { createSessionApi, SessionError, type CsrfData, type SessionData } from '../src/features/auth/client'
import { useSession } from '../src/features/auth/useSession'

const actor: SessionData = { authenticated: true, user_id: '0e3ef957-3cdd-4f44-8147-b0fe1d46b8f8', expires_at: '2030-10-02T12:00:00Z', is_synthetic: true, private_business_available: false }
const proof: CsrfData = { csrf_token: 'T'.repeat(43), expires_at: actor.expires_at }
const api = () => ({ loginPath: '/api/v2/auth/login', session: vi.fn(async () => actor),
  csrf: vi.fn(async () => proof), logout: vi.fn(async (_token: string, _signal?: AbortSignal) => ({ logged_out: true as const })) })
let wrapper: VueWrapper | undefined
afterEach(() => wrapper?.unmount())

describe('CSRF and logout wire', () => {
  it('gets a session-bound proof and sends it only in the fixed POST header', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ data: proof, meta: {} }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { logged_out: true }, meta: {} }), { status: 200 }))
    const client = createSessionApi('/api', fetcher)
    const token = await client.csrf()
    expect(token).toEqual(proof)
    await client.logout(token.csrf_token)
    expect(fetcher).toHaveBeenNthCalledWith(1, '/api/v2/auth/csrf', expect.objectContaining({ method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error' }))
    expect(fetcher).toHaveBeenNthCalledWith(2, '/api/v2/auth/logout', expect.objectContaining({ method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: { Accept: 'application/json', 'X-CSRF-Token': proof.csrf_token } }))
    expect(fetcher.mock.calls[1]?.[1]).not.toHaveProperty('body')
    expect(fetcher.mock.calls[1]?.[1].headers).not.toHaveProperty('Origin')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it.each([{ ...proof, csrf_token: '' }, { ...proof, csrf_token: 'short' },
    { ...proof, csrf_token: 'T'.repeat(43) + '\r\nInjected: yes' }, { ...proof, expires_at: 'not-a-date' },
    { ...proof, secret: 'UNEXPECTED' }])('rejects malformed CSRF envelopes', async (data) => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ data, meta: {} }), { status: 200 }))
    await expect(createSessionApi('/api', fetcher).csrf()).rejects.toThrow('不符合契约')
  })

  it('rejects an invalid token before a request or URL proof is sent', async () => {
    const fetcher = vi.fn()
    await expect(createSessionApi('/api', fetcher).logout('invalid')).rejects.toThrow('凭据无效')
    expect(fetcher).not.toHaveBeenCalled()
  })

  it.each([{ logged_out: false }, { logged_out: true, token: 'UNEXPECTED' }, null])('rejects unconfirmed logout data', async (data) => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ data, meta: {} }), { status: 200 }))
    await expect(createSessionApi('/api', fetcher).logout(proof.csrf_token)).rejects.toThrow('无法确认')
  })
})

describe('logout memory and concurrent requests', () => {
  it('clears actor immediately, performs one logout for repeated clicks, and keeps proofs outside reactive state', async () => {
    const client = api()
    let finish!: () => void
    client.logout.mockImplementationOnce(() => new Promise(resolve => { finish = () => resolve({ logged_out: true }) }))
    const session = useSession(client)
    await session.refresh()
    const first = session.logout()
    expect(session.state.actor).toBeNull()
    expect(session.state.status).toBe('logging_out')
    expect(session.logout()).toBe(first)
    await flushPromises()
    expect(client.csrf).toHaveBeenCalledTimes(1)
    expect(client.logout).toHaveBeenCalledTimes(1)
    expect(JSON.stringify(session.state)).not.toContain(proof.csrf_token)
    await session.refresh()
    expect(client.session).toHaveBeenCalledTimes(1)
    finish()
    await first
    expect(session.state.status).toBe('unauthenticated')
    expect(session.state.message).toContain('已退出当前应用')
    expect(session.state.logoutUnconfirmed).toBe(false)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('does not let an in-flight successful read restore identity after logout', async () => {
    const client = api()
    let finishRead!: (data: SessionData) => void
    client.session.mockImplementationOnce(() => new Promise(resolve => { finishRead = resolve }))
    const session = useSession(client)
    const read = session.refresh()
    await session.logout()
    finishRead(actor)
    await read
    expect(session.state.actor).toBeNull()
    expect(session.state.status).toBe('unauthenticated')
  })

  it.each(['csrf', 'logout'] as const)('treats %s 401 as an invalid current application session', async (stage) => {
    const client = api()
    client[stage].mockRejectedValueOnce(new SessionError(401))
    const session = useSession(client)
    await session.refresh()
    await session.logout()
    expect(session.state.actor).toBeNull()
    expect(session.state.status).toBe('unauthenticated')
    expect(session.state.message).toContain('已失效')
    expect(session.state.logoutUnconfirmed).toBe(false)
    if (stage === 'csrf') expect(client.logout).not.toHaveBeenCalled()
  })

  it.each([403, 503, 0])('does not report server revocation after logout failure %s', async (status) => {
    const client = api()
    client.logout.mockRejectedValueOnce(new SessionError(status))
    const session = useSession(client)
    await session.refresh()
    await session.logout()
    expect(session.state.actor).toBeNull()
    expect(session.state.status).toBe('error')
    expect(session.state.message).toContain('退出未确认')
    expect(session.state.message).not.toContain('已退出')
    expect(session.state.logoutUnconfirmed).toBe(true)
    await session.logout()
    expect(client.csrf).toHaveBeenCalledTimes(2)
    expect(session.state.status).toBe('unauthenticated')
  })

  it('does not submit logout after disposal while awaiting CSRF', async () => {
    const client = api()
    let finish!: (data: CsrfData) => void
    client.csrf.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const session = useSession(client)
    const exit = session.logout()
    session.dispose()
    finish(proof)
    await exit
    expect(client.logout).not.toHaveBeenCalled()
    expect(session.state.actor).toBeNull()
  })
})

describe('visible application logout', () => {
  it('shows the scoped logout action and returns to login after confirmed revocation', async () => {
    const client = api()
    wrapper = mount(AuthView, { props: { api: client } })
    await flushPromises()
    expect(wrapper.get('button.auth-logout').text()).toBe('退出当前应用')
    expect(wrapper.text()).toContain('单点登录会话由供应商管理')
    await wrapper.get('button.auth-logout').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="actor-id"]').exists()).toBe(false)
    expect(wrapper.find('a.auth-login').exists()).toBe(true)
    expect(wrapper.text()).not.toContain(proof.csrf_token)
  })

  it('offers a retry without claiming logout succeeded after server failure', async () => {
    const client = api()
    client.logout.mockRejectedValueOnce(new SessionError(503))
    wrapper = mount(AuthView, { props: { api: client } })
    await flushPromises()
    await wrapper.get('button.auth-logout').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('退出未确认')
    expect(wrapper.get('button.auth-logout').text()).toBe('重试退出当前应用')
    expect(wrapper.find('a.auth-login').exists()).toBe(false)
    expect(wrapper.find('[data-testid="actor-id"]').exists()).toBe(false)
  })
})
