import { describe, expect, it, vi } from 'vitest'
import { createSessionApi, SessionError, type SessionData } from '../src/features/auth/client'

const actor: SessionData = { authenticated: true, user_id: '0e3ef957-3cdd-4f44-8147-b0fe1d46b8f8', expires_at: '2030-10-02T12:00:00Z', is_synthetic: true, private_business_available: false }

describe('same-origin identity client', () => {
  it('reads a cookie session without sending credentials or storing tokens', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ data: actor, meta: {} }), { status: 200 }))
    const api = createSessionApi('/api', fetcher)
    expect(api.loginPath).toBe('/api/v2/auth/login')
    expect(await api.session()).toEqual(actor)
    expect(fetcher).toHaveBeenCalledWith('/api/v2/auth/session', expect.objectContaining({ method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: { Accept: 'application/json' } }))
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it.each(['https://external.invalid', '//external.invalid', '/api?issuer=evil', '/api/%2e%2e', '/api/../other'])(
    'rejects a nonfixed API path %s before any request', (prefix) => {
      const fetcher = vi.fn()
      expect(() => createSessionApi(prefix, fetcher)).toThrow('同源相对路径')
      expect(fetcher).not.toHaveBeenCalled()
    },
  )

  it.each([401, 403, 404, 503])('uses safe local text for %s, without echoing provider input', async (status) => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ error: { message: 'SECRET_IDP_CODE' } }), { status }))
    await expect(createSessionApi('/api', fetcher).session()).rejects.toMatchObject({ status })
    try { await createSessionApi('/api', fetcher).session() }
    catch (error) { expect(String(error)).not.toContain('SECRET_IDP_CODE') }
  })

  it.each([
    { ...actor, token: 'SHOULD_NOT_REACH_UI' }, { ...actor, private_business_available: true },
    { ...actor, authenticated: false }, { ...actor, expires_at: 'not-a-date' }, { ...actor, user_id: 'not-a-uuid' },
  ])('refuses invalid or expanded actor data', async (data) => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ data, meta: {} }), { status: 200 }))
    await expect(createSessionApi('/api', fetcher).session()).rejects.toThrow('不符合契约')
  })

  it('does not turn connection failure into a demo account', async () => {
    const fetcher = vi.fn(async () => { throw new Error('SECRET_TRANSPORT_DETAILS') })
    await expect(createSessionApi('/api', fetcher).session()).rejects.toEqual(new SessionError(0, '无法连接身份服务。页面不会切换为演示账号。'))
  })
})
