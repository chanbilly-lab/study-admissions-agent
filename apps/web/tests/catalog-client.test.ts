import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createCatalogApi } from '../src/features/catalog/client'
import { createEligibilityApi } from '../src/features/eligibility/client'
import { canonicalHash, scopeFingerprint, validScope } from '../src/features/catalog/validation'
import { config, page, offering, evidence, request, response, csrf, assessment, clone, hash } from './catalogFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => vi.unstubAllGlobals())
describe('T29 closed clients', () => {
  it('uses anonymous no-store transport and preserves all unknown raw scope fields in the hash', async () => {
    const item = offering(); item.scope.campus = { status: 'unknown', value: null }
    expect(validScope(item.scope)).toBe(true); expect(await scopeFingerprint(item.scope)).toBe(hash(item.scope))
    const fetcher = vi.fn(async (_url: RequestInfo | URL, _options?: RequestInit) => response(page([item])))
    await createCatalogApi('/public', fetcher).offerings({ entry_year: 2027 })
    expect(fetcher.mock.calls[0]![0]).toBe('/public/v2/offerings?entry_year=2027')
    expect(fetcher.mock.calls[0]![1]).toMatchObject({ credentials: 'omit', cache: 'no-store', redirect: 'error' })
  })
  it.each(['https://evil.test', '//evil.test', '/api?next=x', '/api/../evil', '/api#hash'])('rejects nonrelative controlled prefixes %s', prefix => {
    expect(() => createCatalogApi(prefix)).toThrow(); expect(() => createEligibilityApi(prefix)).toThrow()
  })
  it.each([401, 403, 409, 422, 503])('never reads error bodies or returns raw status %s text', async status => {
    const json = vi.fn(async () => { throw new Error('secret'); }), result = { status, json } as unknown as Response, fetcher = vi.fn(async () => result)
    await expect(createCatalogApi('/public', fetcher).config()).rejects.toMatchObject({ status })
    await expect(createEligibilityApi('/api', fetcher).context()).rejects.toMatchObject({ status })
    expect(json).not.toHaveBeenCalled()
  })
  it.each([true, 2027.5, 0, 10000, '2027'])('rejects invalid explicit query year %s before network', value => {
    const fetcher = vi.fn(); expect(() => createCatalogApi('/public', fetcher).offerings({ entry_year: value } as never)).toThrow(); expect(fetcher).not.toHaveBeenCalled()
  })
  it('binds config metadata and refuses invented private public fields', async () => {
    await expect(createCatalogApi('/public', vi.fn(async () => response(config(), { overrides: { data_mode: 'verified' } }))).config()).rejects.toMatchObject({ status: 200 })
    const item = { ...offering(), source_url: 'http://private/?secret' }
    await expect(createCatalogApi('/public', vi.fn(async () => response(page([item])))).offerings({ entry_year: 2027 })).rejects.toMatchObject({ status: 200 })
  })
  it.each(['  \t\r\n', '\u0085', 'prefix\u009fsuffix'])('rejects invalid bounded fact context without changing raw quote semantics', async value => {
    const item = offering(); item.facts[0]!.unit = value
    await expect(createCatalogApi('/public', vi.fn(async () => response(page([item])))).offerings({ entry_year: 2027 })).rejects.toMatchObject({ status: 200 })
    const quote = evidence(offering(), '   ')
    expect((await createCatalogApi('/public', vi.fn(async () => response(quote))).evidence(quote.evidence_id, quote.release_id)).quote).toBe('   ')
  })
  it.each([{ data_mode: 'demo', model_mode: 'disabled' }, { data_mode: 'demo', model_mode: 'mock' }, { data_mode: 'verified', model_mode: 'mock' }])('refuses private transport mode %s', async mode => {
    const data = assessment()
    await expect(createEligibilityApi('/api', vi.fn(async () => response(data, { privateData: true, overrides: mode }))).get(data.assessment_id)).rejects.toMatchObject({ status: 200 })
  })
  it.each(['request_id', 'profile_version_id'])('rejects wrong metadata %s', async field => {
    await expect(createCatalogApi('/public', vi.fn(async () => response(page(), { overrides: { [field]: field === 'request_id' ? 'f'.repeat(32) : offering().id } }))).offerings({ entry_year: 2027 })).rejects.toMatchObject({ status: 200 })
  })
  it('checks evidence quote UTF8 bytes, hash and exact release while keeping HTML inert as text', async () => {
    const good = evidence(), fetcher = vi.fn(async () => response(good))
    expect((await createCatalogApi('/public', fetcher).evidence(good.evidence_id, good.release_id)).quote).toContain('<img')
    for (const bad of [{ ...good, snippet_sha256: '0'.repeat(64) }, { ...good, release_id: offering(9).id }, { ...good, locator: { ...good.locator, byte_end: good.locator.byte_end + 1 } }]) {
      await expect(createCatalogApi('/public', vi.fn(async () => response(bad))).evidence(good.evidence_id, good.release_id)).rejects.toMatchObject({ status: 200 })
    }
  })
  it('requires fresh CSRF on each confirmed write with no idem header, freezes caller input before awaiting', async () => {
    const input = request(), fetcher = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).endsWith('/csrf')) { input.stage = 'enrollment'; return csrf() }
      return response(assessment(), { privateData: true })
    })
    const api = createEligibilityApi('/api', fetcher); await api.evaluate(input)
    input.stage = 'application'; await api.evaluate(input)
    const calls = fetcher.mock.calls as unknown as [string, RequestInit][]
    expect(calls.filter(([url]) => url.endsWith('/csrf'))).toHaveLength(2)
    expect(JSON.parse(calls[1]![1].body as string).stage).toBe('application')
    expect(calls[1]![1]).toMatchObject({ method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'X-CSRF-Token': 'T'.repeat(43) } })
    expect(calls[1]![1].headers).not.toHaveProperty('Idempotency-Key')
  })
  it('accepts server unknown ruleset response instead of denying a facts-only check', async () => {
    const api = createEligibilityApi('/api', vi.fn(async (url: RequestInfo | URL) => String(url).endsWith('/csrf') ? csrf() : response(assessment(), { privateData: true })))
    expect((await api.evaluate(request())).eligibility.status).toBe('unknown')
  })
  it.each(['profile_version_id', 'scope_sha256', 'result_sha256', 'requirements_version'])('rejects forged bound assessment %s', async key => {
    const data = assessment()
    if (key === 'scope_sha256') data.target.scope_sha256 = '1'.repeat(64)
    else (data as unknown as Record<string, unknown>)[key] = key === 'profile_version_id' ? offering(9).id : '1'.repeat(64)
    const fetcher = vi.fn(async (url: RequestInfo | URL) => String(url).endsWith('/csrf') ? csrf() : response(data, { privateData: true }))
    await expect(createEligibilityApi('/api', fetcher).evaluate(request())).rejects.toMatchObject({ status: 200 })
  })
  it('allows dynamic historical validity while checking frozen canonical result hash', async () => {
    const data = assessment({ current_validity: 'withdrawn', replayed: true })
    expect(await canonicalHash(Object.fromEntries(Object.entries(data).filter(([k]) => !['result_sha256', 'replayed', 'current_validity'].includes(k))))).toBe(data.result_sha256)
    const api = createEligibilityApi('/api', vi.fn(async (url: RequestInfo | URL) => String(url).endsWith('/csrf') ? csrf() : response(data, { privateData: true })))
    expect((await api.replay(data.assessment_id, { confirmed: true })).current_validity).toBe('withdrawn')
  })
  it('does not expose extra actual-grade or raw quote properties in an assessment', async () => {
    const data = { ...clone(assessment()), raw_quote: '<script>secret</script>' }
    await expect(createEligibilityApi('/api', vi.fn(async () => response(data, { privateData: true }))).get(data.assessment_id)).rejects.toMatchObject({ status: 200 })
  })
})
