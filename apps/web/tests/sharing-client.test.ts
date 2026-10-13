import { afterEach, describe, expect, it, vi } from 'vitest'
import { createSharingApi, SharingError, isGrantData } from '../src/features/sharing/client'
import { grant, grants, mutation, policy, grantId, otherActor, resourceId } from './sharingFixtures'
import { consentId } from './privacyFixtures'
const response = (data: unknown) => new Response(JSON.stringify({ data, meta: {} }), { status: 200 })
const proof = () => response({ csrf_token: 'T'.repeat(43), expires_at: '2030-10-02T12:00:00Z' })
const input = () => ({ resource_type: 'profile' as const, resource_id: resourceId, expected_resource_version: 1, grantee_user_id: otherActor.user_id,
  fields: ['status' as const], actions: ['read' as const], expires_at: '2026-10-04T00:00:00Z', confirmed: true as const, expected_revision: 0,
  owner_consent_id: consentId, sharing_policy_version: policy().policy_version, sharing_policy_hash: policy().text_sha256 })
afterEach(() => vi.unstubAllGlobals())
describe('same-origin sharing client', () => {
  it('uses fixed public policy and directional pagination with no owner or proof query', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(policy())).mockResolvedValueOnce(response(grants()))
    const api = createSharingApi('/api', fetcher)
    await api.policy(); await api.list('received', grantId)
    expect(fetcher.mock.calls[0][0]).toBe('/api/v2/sharing/policy')
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v2/access-grants?direction=received&limit=20&after_id=${grantId}`)
    for (const [, options] of fetcher.mock.calls) expect(options).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error' })
  })
  it('sends exactly explicit creation fields with memory-only CSRF', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(proof()).mockResolvedValueOnce(response(mutation()))
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    await createSharingApi('/api', fetcher).create(input())
    expect(fetcher.mock.calls[0][0]).toBe('/api/v2/auth/csrf')
    const options = fetcher.mock.calls[1][1]
    expect(JSON.parse(options.body)).toEqual(input())
    expect(options.headers).toEqual({ Accept: 'application/json', 'X-CSRF-Token': 'T'.repeat(43), 'Content-Type': 'application/json' })
    expect(storage).not.toHaveBeenCalled()
    expect(options).toMatchObject({ credentials: 'same-origin', cache: 'no-store', redirect: 'error' })
  })
  it('accepts only current grant and policy inputs, and revokes with empty body/query', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(proof()).mockResolvedValueOnce(response(mutation()))
      .mockResolvedValueOnce(proof()).mockResolvedValueOnce(response(mutation()))
    const api = createSharingApi('', fetcher)
    const accept = { confirmed: true as const, expected_version: 1, sharing_policy_version: policy().policy_version, sharing_policy_hash: policy().text_sha256 }
    await api.accept(grantId, accept); await api.revoke(grantId)
    expect(fetcher.mock.calls[1][0]).toBe(`/v2/access-grants/${grantId}/accept`)
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual(accept)
    expect(fetcher.mock.calls[3][0]).toBe(`/v2/access-grants/${grantId}`)
    expect(fetcher.mock.calls[3][1]).toMatchObject({ method: 'DELETE', headers: { Accept: 'application/json', 'X-CSRF-Token': 'T'.repeat(43) } })
    expect(fetcher.mock.calls[3][1]).not.toHaveProperty('body')
  })
  it.each(['https://evil.example', '//evil.example', '/api?secret=x', '/api/../evil'])('rejects unsafe prefix %s before fetch', prefix => {
    const fetcher = vi.fn(); expect(() => createSharingApi(prefix, fetcher)).toThrow(); expect(fetcher).not.toHaveBeenCalled()
  })
  it('rejects malformed pagination and grant IDs before retrieving CSRF', async () => {
    const fetcher = vi.fn(), api = createSharingApi('/api', fetcher)
    await expect(api.list('issued', '../bad')).rejects.toBeInstanceOf(SharingError)
    await expect(api.revoke('../bad')).rejects.toBeInstanceOf(SharingError)
    await expect(api.accept('../bad', { confirmed: true, expected_version: 1, sharing_policy_version: 'v', sharing_policy_hash: 'b'.repeat(64) })).rejects.toBeInstanceOf(SharingError)
    expect(fetcher).not.toHaveBeenCalled()
  })
  it.each([401, 403, 404, 409, 422, 503])('uses a safe message for status %s', async status => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{"message":"secret value"}', { status }))
    const error = await createSharingApi('/api', fetcher).policy().catch(error => error)
    expect(error.status).toBe(status); expect(error.message).not.toContain('secret value')
  })
  it.each([
    { ...policy(), private_business_available: true }, { ...policy(), text_sha256: 'bad' },
    { ...policy(), scope_matrix: [{ resource_type: 'profile', fields: ['conversation'], actions: ['read'] }] },
    { ...policy(), scope_matrix: [{ resource_type: 'profile', fields: ['status'], actions: ['download'] }] },
    { ...policy(), owner: 'client injected' },
  ])('rejects policy contract drift and unsupported scope', async value => {
    await expect(createSharingApi('/api', vi.fn(async () => response(value))).policy()).rejects.toBeInstanceOf(SharingError)
  })
  it('rejects extra cross-subject proof and inconsistent active status', () => {
    expect(isGrantData({ ...grant(), owner_consent_id: consentId })).toBe(false)
    expect(isGrantData(grant({ access_active: true }))).toBe(false)
    expect(isGrantData(grant({ state: 'accepted', accepted_at: '2026-10-03T00:00:01Z', access_active: true }))).toBe(true)
  })
  it('fails closed on network errors and does not automatically retry a write', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(proof()).mockRejectedValueOnce(new TypeError('connection lost'))
    await expect(createSharingApi('/api', fetcher).create(input())).rejects.toBeInstanceOf(SharingError)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
