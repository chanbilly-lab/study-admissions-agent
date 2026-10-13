import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createProfileApi, ProfileError, snapshotHash } from '../src/features/profiles/client'
import { context, csrf, deferred, meta, nextVersionId, response, rootId, snapshot, version, versionId } from './profilesFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => vi.unstubAllGlobals())

describe('private profiles use the actual generated wire', () => {
  it('uses same-origin reads, bounded list and two exact history UUIDs', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(context())).mockResolvedValueOnce(response(version())).mockResolvedValueOnce(response(version()))
    const api = createProfileApi('/api', fetcher); await api.context(); await api.current(rootId); await api.history(rootId, versionId)
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['/api/v2/profiles/context', `/api/v2/profiles/${rootId}`, `/api/v2/profiles/${rootId}/versions/${versionId}`])
    fetcher.mock.calls.forEach(([, options]) => expect(options).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error' }))
  })
  it('uses CSRF only in memory and sends one create header, then append CAS without an idempotency header', async () => {
    const profile = snapshot(), fetcher = vi.fn().mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response({ version: version({ profile }), replayed: false }))
      .mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response({ version: version({ profile, version: 2, version_id: nextVersionId }), replayed: false }))
    const storage = vi.spyOn(Storage.prototype, 'setItem'), api = createProfileApi('/api', fetcher)
    await api.create({ profile, confirmed: true }, 'opaque-key'); await api.append(rootId, { profile, confirmed: true, expected_current_version: 1 })
    expect(fetcher.mock.calls[1][1]).toMatchObject({ method: 'POST', headers: { 'X-CSRF-Token': 'T'.repeat(43), 'Idempotency-Key': 'opaque-key' } })
    expect(fetcher.mock.calls[3][1].headers).not.toHaveProperty('Idempotency-Key'); expect(fetcher.mock.calls[3][1].headers).not.toHaveProperty('Origin')
    expect(JSON.parse(fetcher.mock.calls[3][1].body)).toMatchObject({ expected_current_version: 1, profile }); expect(storage).not.toHaveBeenCalled()
  })
  it('freezes the exact body before awaiting CSRF despite a caller mutating its object', async () => {
    const wait = deferred<Response>(), input = { profile: snapshot(), confirmed: true as const }
    const fetcher = vi.fn().mockReturnValueOnce(wait.promise).mockResolvedValueOnce(response({ version: version(), replayed: false })), api = createProfileApi('/api', fetcher)
    const operation = api.create(input, 'stable'); input.profile.weekly_hours = '40'; wait.resolve(csrf()); await operation
    expect(JSON.parse(fetcher.mock.calls[1][1].body).profile.weekly_hours).toBeNull()
  })
  it.each(['https://evil.invalid', '//evil.invalid', '/api?token=x', '/api/../other'])('rejects credential destination %s before fetch', prefix => {
    const fetcher = vi.fn(); expect(() => createProfileApi(prefix, fetcher)).toThrow(); expect(fetcher).not.toHaveBeenCalled()
  })
  it('rejects unconfirmed, extra-owner or wrong operation input before a proof request', async () => {
    const fetcher = vi.fn(), api = createProfileApi('/api', fetcher)
    await expect(api.create({ profile: snapshot(), confirmed: false } as never, 'key')).rejects.toMatchObject({ status: 422 })
    expect(() => api.create({ profile: snapshot(), confirmed: true, owner_id: rootId } as never, 'key')).toThrow(ProfileError)
    expect(() => api.create({ profile: snapshot(), confirmed: true, expected_current_version: 1 } as never, 'key')).toThrow(ProfileError)
    expect(() => api.current('../other')).toThrow(ProfileError); expect(fetcher).not.toHaveBeenCalled()
  })
  it.each([401, 403, 404, 409, 422, 503])('uses fixed safe status %s without rendering raw errors or fallback', async status => {
    const fetcher = vi.fn().mockResolvedValue(new Response('RAW_STUDENT_SENTINEL', { status })), api = createProfileApi('/api', fetcher)
    const error = await api.context().catch(error => error); expect(error.status).toBe(status); expect(error.message).not.toContain('RAW_STUDENT_SENTINEL'); expect(fetcher).toHaveBeenCalledOnce()
  })
  it('matches the actual Python canonical hash without normalizing Unicode or decimal lexical values', async () => {
    const profile = snapshot({ preferences: { preferred_fields: ['机器人🤖'], preferred_countries: [], budget: null } })
    expect(await snapshotHash(profile)).toBe(version({ profile }).profile_sha256)
    expect(await snapshotHash(snapshot({ weekly_hours: '1.00' }))).not.toBe(await snapshotHash(snapshot({ weekly_hours: '1' })))
  })
  it.each([
    version({ profile_sha256: 'f'.repeat(64) }), version({ owner_id: rootId } as never),
    version({ adaptation: { status: 'unsupported', reason: 'ADAPTER_NOT_IMPLEMENTED' } }),
    version({ profile: snapshot({ assessments: { math: { achieved: { status: 'provided', value: 1 as never, scale: '100', unit: 'points' }, predicted: { status: 'missing', value: null, scale: null, unit: null } } } }) }),
  ])('rejects permissive or unbound version snapshots', async data => {
    await expect(createProfileApi('/api', vi.fn().mockResolvedValue(response(data))).current(rootId)).rejects.toMatchObject({ status: 200 })
  })
  it.each([{ profile_version_id: nextVersionId }, { profile_mode: 'real' }, { data_mode: ['verified'] as never }, { model_mode: ['disabled'] as never }])('rejects wrong or array-impostor response metadata', async update => {
    const data = version(); await expect(createProfileApi('/api', vi.fn().mockResolvedValue(response(data, { ...meta(data), ...update }))).current(rootId)).rejects.toMatchObject({ status: 200 })
  })
  it('rejects a different self-consistent snapshot returned as the explicitly saved payload', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response({ version: version({ profile: snapshot({ weekly_hours: '40' }) }), replayed: false }))
    await expect(createProfileApi('/api', fetcher).create({ profile: snapshot(), confirmed: true }, 'key')).rejects.toMatchObject({ status: 200 })
  })
  it('does not retry a network-uncertain append or falsely report success', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(csrf()).mockRejectedValueOnce(new Error('RAW_SECRET'))
    await expect(createProfileApi('/api', fetcher).append(rootId, { profile: snapshot(), confirmed: true, expected_current_version: 1 })).rejects.toMatchObject({ status: 0 })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
