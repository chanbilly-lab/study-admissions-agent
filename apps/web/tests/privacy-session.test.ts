import { describe, expect, it, vi } from 'vitest'
import type { SessionData } from '../src/features/auth/client'
import { useSession } from '../src/features/auth/useSession'

const actor: SessionData = { authenticated: true, user_id: '0e3ef957-3cdd-4f44-8147-b0fe1d46b8f8',
  expires_at: '2030-10-03T12:00:00Z', is_synthetic: true, private_business_available: false }

describe('privacy authentication invalidation', () => {
  it('clears actor and prevents a pending session read from restoring it after privacy 401', async () => {
    let finish!: (value: SessionData) => void
    const api = { loginPath: '/api/v2/auth/login',
      session: vi.fn().mockResolvedValueOnce(actor).mockImplementationOnce(
        () => new Promise<SessionData>((resolve) => { finish = resolve })),
      csrf: vi.fn(async () => ({ csrf_token: 'T'.repeat(43), expires_at: actor.expires_at })),
      logout: vi.fn(async () => ({ logged_out: true as const })) }
    const session = useSession(api)
    await session.refresh()
    const reading = session.refresh()
    session.invalidate()
    expect(session.state.actor).toBeNull()
    expect(session.state.status).toBe('unauthenticated')
    expect(session.state.canLogout).toBe(false)
    expect(api.session.mock.calls[1]?.[0].aborted).toBe(true)
    finish(actor)
    await reading
    expect(session.state.actor).toBeNull()
    expect(session.state.message).toContain('已失效')
  })
})
