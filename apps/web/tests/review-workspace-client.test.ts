import { afterEach, describe, expect, it, vi } from 'vitest'
import { createReviewWorkspaceApi, strictInteger } from '../src/features/admin/reviews/client'
import { datasetId, importId, factId, releaseId, rows, detail, document, release, prechecked, reviewContext, current, sourceId } from './reviewReleaseFixtures'

const response = (data: unknown) => new Response(JSON.stringify({ data, meta: { api_version: 'v2', request_id: 'a'.repeat(32) } }), { status: 200 })
const csrf = () => response({ csrf_token: 'T'.repeat(43), expires_at: '2030-10-02T12:00:00Z' })
afterEach(() => vi.restoreAllMocks())
describe('review workspace HTTP boundary', () => {
  it('uses fixed no-store private paths, bounded discovery and encoded cursor without loading source URLs', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(reviewContext())).mockResolvedValueOnce(response(rows())).mockResolvedValueOnce(response(detail())).mockResolvedValueOnce(response(current()))
    const api = createReviewWorkspaceApi('/api', fetcher); await api.context(); await api.rows(importId, 'cursor:+'); await api.detail(factId); await api.current(datasetId, 2027)
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['/api/v2/admin/review-context', `/api/v2/admin/imports/${importId}/rows?limit=20&cursor=cursor%3A%2B`, `/api/v2/admin/review-candidates/${factId}`, `/api/v2/admin/releases/current?dataset_id=${datasetId}&entry_year=2027`])
    for (const [, value] of fetcher.mock.calls) expect(value).toMatchObject({ credentials: 'same-origin', cache: 'no-store', redirect: 'error', method: 'GET' })
  })
  it('obtains fresh in-memory CSRF for each write and uses an idempotency key only for publishing', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response(document())).mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response(prechecked())).mockResolvedValueOnce(csrf()).mockResolvedValueOnce(response(release()))
    const api = createReviewWorkspaceApi('/api', fetcher), storage = vi.spyOn(Storage.prototype, 'setItem')
    await api.document({ dataset_id: datasetId, source_id: sourceId, source_version: 1, document_reference: 'DEMO_document', language: 'en', confirmed: true })
    const input = { dataset_id: datasetId, expected_dataset_revision: 4, entry_year: 2027, kind: 'test_fixture' as const, valid_from: '2026-10-02T08:00:00+08:00', valid_until: '2026-10-04T08:00:00+08:00', members: release().members.map(item => ({ fact_id: item.fact_id, expected_case_revision: item.case_revision, expected_decision_id: item.decision_id, public_evidence: false })), replaces_release_id: null, expected_replaced_state_revision: null, confirmed: true as const }
    await api.precheck(input); await api.publish(input, releaseId)
    expect(fetcher.mock.calls[3][1].headers).not.toHaveProperty('Idempotency-Key'); expect(fetcher.mock.calls[5][1].headers).toMatchObject({ 'X-CSRF-Token': 'T'.repeat(43), 'Idempotency-Key': releaseId })
    expect(JSON.parse(fetcher.mock.calls[5][1].body)).toEqual(input); expect(fetcher.mock.calls[5][1].headers).not.toHaveProperty('Origin'); expect(storage).not.toHaveBeenCalled()
  })
  it.each([401, 403, 409, 422, 503])('surfaces safe status %s without secret text or a successful fallback', async status => {
    const fetcher = vi.fn().mockResolvedValue(new Response('RAW_SENTINEL', { status })), error = await createReviewWorkspaceApi('/api', fetcher).context().catch(error => error)
    expect(error.status).toBe(status); expect(error.message).not.toContain('RAW_SENTINEL'); expect(fetcher).toHaveBeenCalledOnce()
  })
  it('rejects injected identifiers and unconfirmed writes before sending CSRF', async () => {
    const fetcher = vi.fn(), api = createReviewWorkspaceApi('/api', fetcher)
    expect(() => api.detail('../secret')).toThrow(); expect(() => api.current(datasetId, 2027.5)).toThrow()
    await expect(api.document({ dataset_id: datasetId, source_id: sourceId, source_version: 1, document_reference: 'DEMO_document', language: 'en', confirmed: false } as never)).rejects.toMatchObject({ status: 422 })
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('rejects missing synthetic marker and oversized row discovery responses', async () => {
    const missing = { ...rows() } as Record<string, unknown>; delete missing.is_synthetic
    const oversized = rows({ rows: Array.from({ length: 21 }, () => rows().rows[0]) })
    for (const value of [missing, oversized]) await expect(createReviewWorkspaceApi('/api', vi.fn().mockResolvedValue(response(value))).rows(importId)).rejects.toMatchObject({ status: 200 })
  })
  it('rejects a candidate response that claims to be a hard rule or includes private original file metadata', async () => {
    const invalidFact = detail(); invalidFact.fact.hard_rule = true as never
    const privateSnippet = { ...detail(), evidence: { ...detail().evidence, file_id: importId } }
    for (const value of [invalidFact, privateSnippet]) await expect(createReviewWorkspaceApi('/api', vi.fn().mockResolvedValue(response(value))).detail(factId)).rejects.toMatchObject({ status: 200 })
  })
  it('accepts native Vue numeric values but rejects missing, fractional and unsafe integer input', () => {
    expect(strictInteger(2027)).toBe(2027); expect(strictInteger('', 0)).toBeNull(); expect(strictInteger('1.0')).toBeNull(); expect(strictInteger(1.5)).toBeNull(); expect(strictInteger('9007199254740992')).toBeNull()
  })
})
