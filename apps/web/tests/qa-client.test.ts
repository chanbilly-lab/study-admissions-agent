import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createQAApi } from '../src/features/qa/client'
import { bindsOffering, validAnswer, validContext, validRequest } from '../src/features/qa/validation'
import { answer, closedContext, clone, context, deferred, failure, meta, rehash, request, response, target, uid, unknown } from './qaFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => vi.unstubAllGlobals())

describe('T39 anonymous bounded QA client', () => {
  it('accepts the actual finite projection and sends only closed public fields anonymously', async () => {
    const fetcher = vi.fn(async (url: RequestInfo | URL, _options?: RequestInit) => response(String(url).endsWith('/context') ? context() : answer()))
    const client = createQAApi('/qa', fetcher)
    expect((await client.context()).can_ask).toBe(true)
    const result = await client.answer(request()); expect(result.citations).toHaveLength(1)
    expect(fetcher.mock.calls.map(c => c[0])).toEqual(['/qa/v2/qa/context', '/qa/v2/qa/answers'])
    for (const call of fetcher.mock.calls) expect(call[1]).toMatchObject({ credentials: 'omit', redirect: 'error', cache: 'no-store' })
    const options = fetcher.mock.calls[1]![1]!
    expect(Object.keys(JSON.parse(options.body as string))).toEqual(Object.keys(request()))
    expect(options.headers).not.toHaveProperty('X-CSRF-Token'); expect(options.headers).not.toHaveProperty('Idempotency-Key')
    expect(JSON.parse(options.body as string).scope).not.toHaveProperty('dataset_id')
  })
  it('accepts default disabled configuration with no keys and no answer fallback', async () => {
    const fetcher = vi.fn(async () => response(closedContext(), meta('disabled', 'verified')))
    expect((await createQAApi('/qa', fetcher).context()).can_ask).toBe(false); expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('normalizes optional absent or undefined keywords, while rejecting null, extra fields and nonplain inputs', async () => {
    const { keywords: _keywords, ...withoutKeywords } = request()
    const fetcher = vi.fn(async (_url: RequestInfo | URL, _options?: RequestInit) => response(answer()))
    const client = createQAApi('/qa', fetcher)
    for (const input of [withoutKeywords, { ...withoutKeywords, keywords: undefined }]) {
      expect((await client.answer(input)).status).toBe('answered')
      expect(JSON.parse(fetcher.mock.calls.at(-1)![1]!.body as string).keywords).toEqual([])
    }
    const calls = fetcher.mock.calls.length
    for (const bad of [{ ...withoutKeywords, keywords: null }, { ...withoutKeywords, owner_id: uid(20) }, Object.assign(Object.create(null), withoutKeywords)]) {
      await expect(client.answer(bad as ReturnType<typeof request>)).rejects.toMatchObject({ status: 422 })
    }
    expect(fetcher).toHaveBeenCalledTimes(calls)
  })
  it.each(['https://remote.invalid', '//remote.invalid', '/qa?key=secret', '/qa/../api', '/qa#key'])('rejects an uncontrolled prefix %s', prefix => expect(() => createQAApi(prefix)).toThrow())
  it.each(['profile_id', 'owner_id', 'assessments', 'tools', 'prompt', 'student_confirmed'])('rejects injected private/action field %s before any network request', async field => {
    const fetcher = vi.fn(), input = { ...request(), [field]: uid(20) }
    await expect(createQAApi('/qa', fetcher).answer(input)).rejects.toMatchObject({ status: 422 }); expect(fetcher).not.toHaveBeenCalled()
  })
  it('rejects a client dataset scope injection, scope year mismatch and spoofed enums', async () => {
    const input = request(), fetcher = vi.fn()
    for (const bad of [{ ...input, scope: { ...input.scope, dataset_id: uid(1) } }, { ...input, scope: { ...input.scope, entry_year: 2026 } }, { ...input, intent: ['requirements'] }, { ...input, keywords: ['a', 'a'] }, { ...input, keywords: ['\ud800'] }]) {
      expect(validRequest(bad)).toBe(false)
      await expect(createQAApi('/qa', fetcher).answer(bad as typeof input)).rejects.toMatchObject({ status: 422 })
    }
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('freezes the exact caller body before awaiting transport and rejects a different returned intent', async () => {
    const hold = deferred<Response>(), input = request(), fetcher = vi.fn(async (_url: RequestInfo | URL, _options?: RequestInit) => hold.promise)
    const work = createQAApi('/qa', fetcher).answer(input); input.intent = 'fees'
    expect(JSON.parse(fetcher.mock.calls[0]![1]!.body as string).intent).toBe('requirements')
    hold.resolve(response(answer(target(), input)))
    await expect(work).rejects.toMatchObject({ status: 200 })
  })
  it('preserves a provider abstention without inventing a missing-evidence reason', async () => {
    const data = unknown(); expect(data.unknown_reasons).toEqual([])
    expect(await validAnswer(data, request())).toBe(true)
    expect((await createQAApi('/qa', vi.fn(async () => response(data))).answer(request())).status).toBe('unknown')
    expect(await validAnswer(unknown(target(), request(), true), request())).toBe(true)
    const noReason = unknown(target(), request(), true); noReason.unknown_reasons = []
    expect(await validAnswer(noReason, request())).toBe(false)
  })
  it.each(['id', 'content_sha256', 'requirements_version', 'offering_id', 'entry_year', 'is_synthetic', 'extra'])('rejects altered citation %s rather than accepting hash-shaped data', async key => {
    const data = answer(), citation = data.citations[0]!
    const raw = citation as unknown as Record<string, unknown>
    raw[key] = key === 'extra' ? 'private' : key === 'is_synthetic' ? false : key === 'entry_year' ? 2026 : key === 'id' || key === 'offering_id' ? uid(90) : '0'.repeat(64)
    await expect(createQAApi('/qa', vi.fn(async () => response(data))).answer(request())).rejects.toMatchObject({ status: 200 })
  })
  it('rejects cross-scope evidence even when its public projection hash is recomputed', async () => {
    const data = answer(); data.citations[0]!.scope.province = { status: 'known', value: 'OTHER_PROVINCE' }; data.citations[0]!.evidence.scope = clone(data.citations[0]!.scope); rehash(data.citations[0]!)
    expect(await validAnswer(data, request())).toBe(false)
  })
  it('binds facts and release fingerprint to the explicitly selected public record', async () => {
    const item = target(), data = answer(item); data.citations[0]!.fact.unit = 'GBP'; rehash(data.citations[0]!)
    expect(await validAnswer(data, request(item))).toBe(true)
    expect(bindsOffering(data, item)).toBe(false)
    const replaced = answer(); replaced.content_sha256 = '9'.repeat(64); expect(bindsOffering(replaced, item)).toBe(false)
  })
  it.each(['profile_version_id', 'release_id', 'request_id', 'data_mode', 'model_mode'])('rejects unsafe or mismatched public envelope %s', async key => {
    const metadata = meta() as Record<string, unknown>; metadata[key] = key.endsWith('_id') ? uid(99) : key === 'data_mode' ? 'verified' : 'live'
    await expect(createQAApi('/qa', vi.fn(async () => response(answer(), metadata as ReturnType<typeof meta>))).answer(request())).rejects.toMatchObject({ status: 200 })
  })
  it.each([[503, 'MODEL_DISABLED'], [503, 'MODEL_TIMEOUT'], [429, 'BUDGET_EXHAUSTED'], [409, 'CITATION_CONFLICT']] as const)('uses a fixed safe message for %s %s without retries', async (status, code) => {
    const fetcher = vi.fn(async () => failure(status, code)); const error = await createQAApi('/qa', fetcher).answer(request()).catch(e => e)
    expect(error).toMatchObject({ status, code }); expect(error.message).not.toContain('RAW_SECRET'); expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('distinguishes bad successful JSON from unconfirmed transport and enforces bounded UTF-8', async () => {
    for (const bytes of ['{broken', 'x'.repeat(524289), new Uint8Array([0xff])]) {
      const fetcher = vi.fn(async () => new Response(bytes, { status: 200, headers: { 'Content-Type': 'application/json' } }))
      await expect(createQAApi('/qa', fetcher).answer(request())).rejects.toMatchObject({ status: 200 })
    }
    await expect(createQAApi('/qa', vi.fn(async () => { throw new Error('RAW_SECRET') })).answer(request())).rejects.toMatchObject({ status: 0 })
  })
  it('rejects forged capability booleans and externally enabled modes', () => {
    for (const data of [{ ...context(), can_ask: 1 }, { ...context(), live_available: true }, { ...context(), model_mode: ['mock'] }, { ...closedContext(), can_ask: true }]) expect(validContext(data)).toBe(false)
  })
})
