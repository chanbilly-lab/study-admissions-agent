import { describe, expect, it, vi } from 'vitest'
import { ApiError, createApi } from '../src/api'
import { envelope, profile } from './fixtures'

describe('API client: authenticated requests and explicit failures', () => {
  it('sends a server-resolved demo credential, and never adds client owner identity', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(envelope([profile('bob')]))))
    const api = createApi('/api', fetcher)
    await api.profiles('bob')
    expect(fetcher).toHaveBeenCalledWith('/api/v1/profiles', { method: 'GET', headers: { Authorization: 'Bearer demo-bob-token' } })
  })
  it('keeps live unavailability as an error, without fallback request or fabricated draft', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ detail: 'M0 live provider is unavailable' }), { status: 503 }))
    const api = createApi('/api', fetcher)
    await expect(api.draft('alice', { profile_version_id: 'DEMO_profile_alice', offering_ids: ['DEMO_CN_course'] })).rejects.toThrow('M0 live provider is unavailable')
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('does not replace a network failure with fixture data', async () => {
    const api = createApi('/api', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')))
    await expect(api.profiles('alice')).rejects.toBeInstanceOf(ApiError)
  })
  it('rejects successful responses missing the shared envelope', async () => {
    const api = createApi('/api', vi.fn<typeof fetch>().mockResolvedValue(new Response('{}')))
    await expect(api.config('alice')).rejects.toThrow('data / meta')
  })
})
