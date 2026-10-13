import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPrivacyApi, PrivacyError } from '../src/features/privacy/client'
import { admission, notice, noticeId, consentId } from './privacyFixtures'

const response = (data: unknown) => new Response(JSON.stringify({ data, meta: {} }), { status: 200 })
afterEach(() => vi.unstubAllGlobals())

describe('same-origin privacy client', () => {
  it('fetches anonymous policy and admission only from fixed paths without cache', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(notice())).mockResolvedValueOnce(response(admission()))
    const api = createPrivacyApi('/api', fetcher)
    await api.notice()
    await api.admission()
    expect(fetcher.mock.calls.map(([path]) => path)).toEqual(['/api/v2/privacy/notices/current', '/api/v2/me/admission'])
    for (const [, options] of fetcher.mock.calls) expect(options).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error' })
  })
  it('obtains memory-only CSRF and sends explicit age fields in JSON', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ csrf_token: 'T'.repeat(43), expires_at: '2030-10-02T12:00:00Z' })).mockResolvedValueOnce(response(admission()))
    const local = vi.spyOn(Storage.prototype, 'setItem')
    const api = createPrivacyApi('/api', fetcher)
    const input = { age_band: '18_plus' as const, confirmed: true as const, notice_id: noticeId, expected_revision: 0 }
    await api.declareAge(input)
    expect(fetcher.mock.calls[0][0]).toBe('/api/v2/auth/csrf')
    expect(fetcher.mock.calls[1][0]).toBe('/api/v2/me/age-declarations')
    expect(fetcher.mock.calls[1][1]).toMatchObject({ method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'X-CSRF-Token': 'T'.repeat(43) } })
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual(input)
    expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty('Origin')
    expect(local).not.toHaveBeenCalled()
  })
  it('uses separate purpose confirmation and bodyless DELETE without revision or URL proof', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response({ csrf_token: 'T'.repeat(43), expires_at: '2030-10-02T12:00:00Z' })).mockResolvedValueOnce(response(admission()))
      .mockResolvedValueOnce(response({ csrf_token: 'T'.repeat(43), expires_at: '2030-10-02T12:00:00Z' })).mockResolvedValueOnce(response(admission()))
    const api = createPrivacyApi('', fetcher)
    await api.confirmCore({ purpose: 'core_consultation', confirmed: true, notice_id: noticeId, expected_revision: 4 })
    await api.withdraw(consentId)
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ purpose: 'core_consultation', confirmed: true, notice_id: noticeId, expected_revision: 4 })
    expect(fetcher.mock.calls[3][0]).toBe(`/v2/me/consents/${consentId}`)
    expect(fetcher.mock.calls[3][1]).toMatchObject({ method: 'DELETE', headers: { 'X-CSRF-Token': 'T'.repeat(43) } })
    expect(fetcher.mock.calls[3][1]).not.toHaveProperty('body')
  })
  it.each(['https://evil.example', '//evil.example', '/api?token=x', '/api/../evil'])('rejects unsafe prefix %s before any fetch', (prefix) => {
    const fetcher = vi.fn()
    expect(() => createPrivacyApi(prefix, fetcher)).toThrow()
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('rejects malformed consent ID before obtaining CSRF', async () => {
    const fetcher = vi.fn()
    await expect(createPrivacyApi('/api', fetcher).withdraw('../someone')).rejects.toBeInstanceOf(PrivacyError)
    expect(fetcher).not.toHaveBeenCalled()
  })
  it.each([401, 403, 404, 409, 422, 503])('returns safe status %s without leaking an arbitrary server message', async (status) => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { message: 'sensitive server detail' } }), { status }))
    const error = await createPrivacyApi('/api', fetcher).admission().catch((value) => value)
    expect(error).toBeInstanceOf(PrivacyError)
    expect(error.status).toBe(status)
    expect(error.message).not.toContain('sensitive server detail')
  })
  it.each([
    { ...admission(), age_assurance: 'verified' }, { ...admission(), age_assurance: ['declared'] },
    { ...admission(), revision: '1' }, { ...admission(), private_business_available: true },
    { ...admission(), owner: 'someone' }, { ...admission(), consent_id: undefined },
  ])('rejects invalid admission %j without fabricating an allowed state', async (data) => {
    await expect(createPrivacyApi('/api', vi.fn().mockResolvedValue(response(data))).admission()).rejects.toMatchObject({ status: 200 })
  })
  it('rejects altered guardian/retention policy instead of presenting it as supported', async () => {
    const bad = notice()
    const fetcher = vi.fn().mockResolvedValue(response({ ...bad, age_policy: { ...bad.age_policy, guardian_verification_available: true } }))
    await expect(createPrivacyApi('/api', fetcher).notice()).rejects.toBeInstanceOf(PrivacyError)
  })
  it('does not submit after the CSRF fetch is aborted', async () => {
    const controller = new AbortController()
    const fetcher = vi.fn(async () => { controller.abort(); return response({ csrf_token: 'T'.repeat(43), expires_at: '2030-10-02T12:00:00Z' }) })
    await expect(createPrivacyApi('/api', fetcher).declareAge({ age_band: 'unknown', confirmed: true, notice_id: noticeId, expected_revision: 0 }, controller.signal)).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('reports network failure without a synthetic fallback', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('failed to fetch'))
    await expect(createPrivacyApi('/api', fetcher).notice()).rejects.toMatchObject({ status: 0 })
  })
})
