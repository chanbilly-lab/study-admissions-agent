import { beforeAll, describe, it, expect, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import { createNotificationApi } from '../src/features/plans/notifications/client'
import { validContext, validPreference, validNotification, validPage, validSelectedProfile } from '../src/features/plans/notifications/validation'
import { context, preference, notification, page, version, response, csrf, deferred, id, clone } from './notificationsFixtures'
beforeAll(() => Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true }))
const input = () => ({ expected_version: 0, enabled: true, profile_id: version().profile_id, student_confirmed: true as const })

describe('T36 notification wire', () => {
  it('validates the actual closed default and finite notification projections', async () => {
    expect(validContext(context())).toBe(true)
    expect(validPreference(preference())).toBe(true)
    expect(validPreference(preference(true))).toBe(true)
    expect(validNotification(notification())).toBe(true)
    expect(validNotification(notification(true))).toBe(true)
    expect(validPage(page())).toBe(true)
    expect(await validSelectedProfile(version())).toBe(true)
  })
  it('uses all five operations with cookie/no-store and only local CSRF on POST', async () => {
    const replies = [context(), preference(), preference(true), page(), notification(true)], calls: { path: string; init: RequestInit }[] = []
    const api = createNotificationApi('/api', vi.fn(async (url, init) => {
      if (String(url).endsWith('/csrf')) return csrf()
      calls.push({ path: String(url), init: init! }); return response(replies.shift())
    }))
    await api.context(); await api.preferences(); await api.savePreferences(input()); await api.list(); await api.markRead(notification().id, { expected_version: 1, student_confirmed: true })
    expect(calls.map(call => call.path)).toEqual(['/api/v2/notifications/context', '/api/v2/notifications/preferences', '/api/v2/notifications/preferences', '/api/v2/notifications?limit=20', '/api/v2/notifications/' + notification().id + '/read'])
    for (const { init } of calls) {
      expect(init.credentials).toBe('same-origin'); expect(init.cache).toBe('no-store'); expect(init.redirect).toBe('error')
      expect((init.headers as Record<string, string>)['Idempotency-Key']).toBeUndefined()
      expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe(init.method === 'POST' ? 'T'.repeat(43) : undefined)
    }
  })
  it('captures the exact preference before a delayed CSRF proof and encodes opaque cursors', async () => {
    const pending = deferred<Response>(), calls: { path: string; init: RequestInit }[] = []
    const api = createNotificationApi('/api', vi.fn(async (url, init) => String(url).endsWith('/csrf') ? pending.promise : (calls.push({ path: String(url), init: init! }), response(String(url).includes('?') ? page() : preference(true)))))
    const original = input(), saved = api.savePreferences(original); original.profile_id = id(1199); pending.resolve(csrf()); await saved
    expect(JSON.parse(calls[0]!.init.body as string)).toEqual(input())
    await api.list('opaque+/='); expect(calls[1]!.path).toBe('/api/v2/notifications?limit=20&cursor=opaque%2B%2F%3D')
  })
  it('rejects client authority, loose booleans, missing confirmation and unsafe IDs before IO', async () => {
    const fetcher = vi.fn(), api = createNotificationApi('/api', fetcher)
    for (const bad of [{ ...input(), owner: id(1) }, { ...input(), enabled: 1 }, { ...input(), student_confirmed: false }, { ...input(), profile_id: null }]) await expect(api.savePreferences(bad as never)).rejects.toMatchObject({ status: 422 })
    expect(() => api.markRead('../secret', { expected_version: 1, student_confirmed: true })).toThrow()
    expect(() => api.list('bad\n')).toThrow(); expect(() => createNotificationApi('https://outside.invalid', fetcher)).toThrow()
    expect(fetcher).not.toHaveBeenCalled()
  })
  it.each([401, 403, 404, 409, 422, 503])('never claims success or reveals server error detail for HTTP %s', async status => {
    const api = createNotificationApi('/api', vi.fn(async () => new Response('PRIVATE_SENTINEL', { status })))
    await expect(api.preferences()).rejects.toMatchObject({ status }); await expect(api.preferences()).rejects.not.toHaveProperty('message', 'PRIVATE_SENTINEL')
  })
  it.each(['GET', 'POST'])('classifies malformed successful %s JSON as bad200', async method => {
    const api = createNotificationApi('/api', vi.fn(async url => String(url).endsWith('/csrf') ? csrf() : new Response('{invalid', { status: 200 })))
    await expect(method === 'GET' ? api.preferences() : api.savePreferences(input())).rejects.toMatchObject({ status: 200 })
  })
  it('rejects metadata spoofing, missing no-store and nonprivate runtime modes', async () => {
    for (const change of [{ request_id: 'a'.repeat(32) }, { profile_version_id: id(1199) }, { model_mode: 'mock' }, { data_mode: 'demo' }]) {
      const api = createNotificationApi('/api', vi.fn(async () => response(preference(true), change)))
      await expect(api.preferences()).rejects.toMatchObject({ status: 200 })
    }
    const missing = createNotificationApi('/api', vi.fn(async () => new Response(JSON.stringify({ data: context(), meta: (await response(context()).json()).meta }), { status: 200 })))
    await expect(missing.context()).rejects.toMatchObject({ status: 200 })
  })
  it('checks preference CAS and read response target instead of accepting another valid object', async () => {
    const save = createNotificationApi('/api', vi.fn(async url => String(url).endsWith('/csrf') ? csrf() : response(preference(true, 2))))
    await expect(save.savePreferences(input())).rejects.toMatchObject({ status: 200 })
    const read = createNotificationApi('/api', vi.fn(async url => String(url).endsWith('/csrf') ? csrf() : response(notification(true, { id: id(1199) }))))
    await expect(read.markRead(notification().id, { expected_version: 1, student_confirmed: true })).rejects.toMatchObject({ status: 200 })
    const repeat = createNotificationApi('/api', vi.fn(async url => String(url).endsWith('/csrf') ? csrf() : response(notification(true))))
    await expect(repeat.markRead(notification().id, { expected_version: 2, student_confirmed: true })).resolves.toMatchObject({ version: 2, read_at: notification(true).read_at })
  })
  it('rejects extra content, forged needs-review/read markers and finite page overflow', async () => {
    const n = notification()
    for (const bad of [{ ...n, quote: 'PRIVATE_SENTINEL' }, { ...n, reason: ['BUSINESS_CHANGED'] }, { ...n, needs_review: false }, { ...n, read_at: n.created_at }, { ...notification(true), read_at: n.expires_at }, { ...n, before_release_id: null, after_release_id: null }]) expect(validNotification(bad)).toBe(false)
    expect(validNotification(notification(false, { reason: 'REFERENCE_REPLACED', needs_review: false }))).toBe(true)
    expect(validPage(page([n, clone(n)]))).toBe(false); expect(validPage(page(Array.from({ length: 21 }, (_, i) => notification(false, { id: id(1200 + i) }))))).toBe(false)
    expect(validPreference({ ...preference(), enabled: true })).toBe(false)
    const forged = version({ profile_sha256: '0'.repeat(64) }); expect(await validSelectedProfile(forged)).toBe(false)
  })
})
