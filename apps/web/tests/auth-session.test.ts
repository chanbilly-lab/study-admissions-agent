import { describe, expect, it, vi } from 'vitest'
import { SessionError, type SessionData } from '../src/features/auth/client'
import { useSession } from '../src/features/auth/useSession'

const actor: SessionData = { authenticated: true, user_id: '0e3ef957-3cdd-4f44-8147-b0fe1d46b8f8', expires_at: '2030-10-02T12:00:00Z', is_synthetic: true, private_business_available: false }
const writeApi = () => ({ csrf: vi.fn(async () => ({ csrf_token: 'T'.repeat(43), expires_at: actor.expires_at })), logout: vi.fn(async () => ({ logged_out: true as const })) })

describe('identity memory state', () => {
  it('clears the current actor when the server reports expiration', async () => {
    const api = { ...writeApi(), loginPath: '/api/v2/auth/login', session: vi.fn().mockResolvedValueOnce(actor).mockRejectedValueOnce(new SessionError(401)) }
    const session = useSession(api)
    await session.refresh()
    expect(session.state.actor).toEqual(actor)
    await session.refresh()
    expect(session.state.status).toBe('unauthenticated')
    expect(session.state.actor).toBeNull()
  })

  it('does not allow an older successful request to overwrite a newer 401', async () => {
    let resolveOlder!: (actor: SessionData) => void
    const older = new Promise<SessionData>((resolve) => { resolveOlder = resolve })
    const api = { ...writeApi(), loginPath: '/api/v2/auth/login', session: vi.fn().mockReturnValueOnce(older).mockRejectedValueOnce(new SessionError(401)) }
    const session = useSession(api)
    const first = session.refresh()
    await session.refresh()
    expect(api.session.mock.calls[0]?.[0].aborted).toBe(true)
    resolveOlder(actor)
    await first
    expect(session.state.status).toBe('unauthenticated')
    expect(session.state.actor).toBeNull()
  })

  it('cancels a pending request on disposal and keeps identity cleared', async () => {
    let resolvePending!: (actor: SessionData) => void
    const api = { ...writeApi(), loginPath: '/api/v2/auth/login', session: vi.fn(() => new Promise<SessionData>((resolve) => { resolvePending = resolve })) }
    const session = useSession(api)
    const pending = session.refresh()
    session.dispose()
    resolvePending(actor)
    await pending
    expect(session.state.actor).toBeNull()
  })
})
