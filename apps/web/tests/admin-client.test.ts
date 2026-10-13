import { afterEach, describe, expect, it, vi } from 'vitest'
import { AdminError, contentBytes, createAdminApi, MAX_CONTENT_BYTES, readOriginal } from '../src/features/admin/client'
import { context, definition, source, file, result, rejected, sourceId, fileId, datasetId, importId, content } from './adminFixtures'

const response = (data: unknown) => new Response(JSON.stringify({ data, meta: { api_version: 'v2', request_id: 'a'.repeat(32) } }), { status: 200 })
const csrf = () => response({ csrf_token: 'T'.repeat(43), expires_at: '2030-10-02T12:00:00Z' })
afterEach(() => vi.unstubAllGlobals())

describe('server-authorized management client', () => {
  it('uses fixed same-origin reads and does not visit a stored source URL', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(context())).mockResolvedValueOnce(response(source())).mockResolvedValueOnce(response(result()))
    const api = createAdminApi('/api', fetcher)
    await api.context(); await api.source(sourceId, 2); await api.result(importId)
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['/api/v2/admin/context', `/api/v2/admin/sources/${sourceId}?version=2`, `/api/v2/admin/imports/${importId}`])
    for (const [, options] of fetcher.mock.calls) expect(options).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error' })
  })
  it('uses fresh memory-only CSRF, PUT CAS and one import idempotency header', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response(source({ version: 2 })))
      .mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response(result()))
    const storage = vi.spyOn(Storage.prototype, 'setItem'), api = createAdminApi('/api', fetcher)
    const revise = { definition: definition(), expected_dataset_revision: 2, expected_source_version: 1, confirmed: true as const }
    const input = { dataset_id: datasetId, source_id: sourceId, source_version: 2, file_id: fileId, file_sha256: file().sha256, format: 'json' as const, confirmed: true as const }
    await api.revise(sourceId, revise); await api.import(input, importId)
    expect(fetcher.mock.calls[1][1]).toMatchObject({ method: 'PUT', headers: { 'X-CSRF-Token': 'T'.repeat(43) } })
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual(revise)
    expect(fetcher.mock.calls[3][1]).toMatchObject({ method: 'POST', headers: { 'Idempotency-Key': importId, 'X-CSRF-Token': 'T'.repeat(43) } })
    expect(JSON.parse(fetcher.mock.calls[3][1].body)).toEqual(input)
    expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty('Idempotency-Key')
    expect(fetcher.mock.calls[3][1].headers).not.toHaveProperty('Origin'); expect(storage).not.toHaveBeenCalled()
  })
  it('preserves original upload content without trimming or changing BOM and line endings', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response(file()))
    const input = { source_id: sourceId, source_version: 1, filename: 'DEMO.json', content_type: 'application/json' as const, content_utf8: '\uFEFF  []\r\n', confirmed: true as const }
    await createAdminApi('/api', fetcher).upload(input)
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual(input)
  })
  it.each(['https://evil.invalid', '//evil.invalid', '/api?token=x', '/api/../other'])('rejects credential destination %s before fetch', prefix => {
    const fetcher = vi.fn(); expect(() => createAdminApi(prefix, fetcher)).toThrow(); expect(fetcher).not.toHaveBeenCalled()
  })
  it('refuses path injection and unconfirmed writes before CSRF', () => {
    const fetcher = vi.fn(), api = createAdminApi('/api', fetcher)
    expect(() => api.source('../other')).toThrow(AdminError)
    expect(() => api.upload({ source_id: sourceId, source_version: 1, filename: 'DEMO.json', content_type: 'application/json', content_utf8: content, confirmed: false } as never)).toThrow(AdminError)
    expect(fetcher).not.toHaveBeenCalled()
  })
  it.each([401, 403, 404, 409, 413, 422, 503])('reports safe status %s without a raw error or fallback', async status => {
    const fetcher = vi.fn().mockResolvedValue(new Response('RAW_SECRET_SENTINEL', { status }))
    const error = await createAdminApi('/api', fetcher).context().catch(error => error)
    expect(error).toBeInstanceOf(AdminError); expect(error.status).toBe(status); expect(error.message).not.toContain('RAW_SECRET_SENTINEL')
    expect(fetcher).toHaveBeenCalledOnce()
  })
  it('network failure does not retry a source mutation or fabricate success', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(csrf()).mockRejectedValueOnce(new Error('RAW_SECRET_SENTINEL'))
    const error = await createAdminApi('/api', fetcher).revise(sourceId, { definition: definition(), expected_dataset_revision: 2, expected_source_version: 1, confirmed: true }).catch(error => error)
    expect(error.message).toContain('未确认'); expect(error.message).not.toContain('RAW_SECRET_SENTINEL'); expect(fetcher).toHaveBeenCalledTimes(2)
  })
  it.each([
    { ...source(), responsible_user_id: sourceId }, { ...source(), auto_fetch_enabled: true }, { ...source(), version: '1' },
  ])('rejects an unexpected or permissive source response', async data => {
    await expect(createAdminApi('/api', vi.fn().mockResolvedValue(response(data))).source(sourceId)).rejects.toMatchObject({ status: 200 })
  })
  it('preserves a valid rejected receipt with unknown total and zero staged rows', async () => {
    const api = createAdminApi('/api', vi.fn().mockResolvedValue(response(rejected())))
    expect(await api.result(importId)).toEqual(rejected())
  })
  it.each([
    { ...result(), status: 'published' }, { ...rejected(), staged_rows: 1 }, { ...result(), total_rows: null },
    { ...rejected(), errors: [{ row_number: 0, field: 'document', code: 'RAW_BAD_VALUE' }] },
  ])('rejects invented publication or inconsistent result counts', async data => {
    await expect(createAdminApi('/api', vi.fn().mockResolvedValue(response(data))).result(importId)).rejects.toMatchObject({ status: 200 })
  })
})

describe('bounded original UTF-8', () => {
  it('counts UTF-8 bytes and rejects byte overflow or a lone surrogate without replacement', () => {
    expect(contentBytes('招生')).toHaveLength(6)
    expect(() => contentBytes('中'.repeat(Math.floor(MAX_CONTENT_BYTES / 3) + 1))).toThrow(AdminError)
    expect(() => contentBytes('raw\ud800')).toThrow(AdminError)
  })
  it('retains BOM, CRLF and whitespace when reading a selected file', async () => {
    const text = '\uFEFF  [ ]\r\n'
    expect(await readOriginal(new File([text], 'DEMO.json'))).toBe(text)
  })
  it('rejects invalid UTF-8 rather than making a replacement character', async () => {
    await expect(readOriginal(new File([new Uint8Array([0xff, 0xfe])], 'DEMO.csv'))).rejects.toMatchObject({ status: 422 })
  })
  it('rejects declared oversize before allocating file bytes', async () => {
    const allocate = vi.fn()
    await expect(readOriginal({ size: MAX_CONTENT_BYTES + 1, arrayBuffer: allocate } as unknown as File)).rejects.toMatchObject({ status: 413 })
    expect(allocate).not.toHaveBeenCalled()
  })
})
