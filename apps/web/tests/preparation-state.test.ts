import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePreparation } from '../src/features/admin/preparation/usePreparation'
import { ReviewWorkspaceError } from '../src/features/admin/reviews/client'
import { actor, otherActor, deferred, workspaceApi, rows, document, original, rowId, importId, datasetId, sourceId, fileId, documentId, evidenceId, originalHash } from './reviewReleaseFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto))
afterEach(() => vi.unstubAllGlobals())

async function prepared(api = workspaceApi()) {
  const model = usePreparation(api); model.setActor(actor); model.state.importId = importId; await model.loadRows(); model.selectRow(rowId)
  model.state.original = original; await model.verifyOriginal(); model.state.reference = 'DEMO_document'; model.state.language = 'en'
  return { api, model }
}
async function snippetReady() {
  const value = await prepared(), { model } = value
  model.state.confirmed.document = true; await model.createDocument(); model.state.confirmed.version = true; await model.createVersion()
  model.state.byteStart = 0; model.state.byteEnd = new TextEncoder().encode(original).length; model.state.confirmed.snippet = true; await model.createSnippet()
  return value
}

describe('manual evidence preparation state', () => {
  it('binds four separately confirmed writes to discovered server IDs and exact original hash', async () => {
    const { api, model } = await prepared()
    await model.createDocument(); expect(api.document).not.toHaveBeenCalled()
    model.state.confirmed.document = true; await model.createDocument()
    expect(api.document).toHaveBeenCalledWith({ dataset_id: datasetId, source_id: sourceId, source_version: 1, document_reference: 'DEMO_document', language: 'en', confirmed: true }, expect.any(AbortSignal))
    expect(model.state.confirmed.version).toBe(false); await model.createVersion(); expect(api.version).not.toHaveBeenCalled()
    model.state.confirmed.version = true; await model.createVersion()
    expect(api.version).toHaveBeenCalledWith({ document_id: documentId, expected_current_version: 0, file_id: fileId, file_sha256: originalHash, confirmed: true }, expect.any(AbortSignal))
    model.state.byteStart = 0; model.state.byteEnd = new TextEncoder().encode(original).length; model.state.confirmed.snippet = true; await model.createSnippet()
    expect(model.state.snippet?.id).toBe(evidenceId); expect(model.state.confirmed.fact).toBe(false); expect(model.state.fact).toBeNull()
    Object.assign(model.state.classification, { claim: 'minimum_requirement', unit: 'points', period: 'not_applicable', basis: 'not_applicable' })
    model.state.confirmed.fact = true; await model.createFact()
    expect(api.fact).toHaveBeenCalledWith({ import_id: importId, import_row_id: rowId, evidence_id: evidenceId, classification: { claim_kind: 'minimum_requirement', unit_code: 'points', period: 'not_applicable', statistics_basis: 'not_applicable', statistic_population: null, statistic_denominator: null, cohort_year: null, survey_period: null, date_event_id: null }, confirmed: true }, expect.any(AbortSignal))
    expect(model.state.fact?.publication_eligible).toBe(false); expect(model.state.message).toContain('仍不可作为硬规则')
  })
  it('keeps preparation closed when local original bytes differ and does not fetch the original', async () => {
    const { api, model } = await prepared(); model.state.original += '\r\n'; model.originalChanged(); await model.verifyOriginal()
    model.state.confirmed.document = true; await model.createDocument()
    expect(model.state.originalMatched).toBe(false); expect(api.document).not.toHaveBeenCalled(); expect(api.rows).toHaveBeenCalledOnce()
  })
  it('retains byte precision and rejects spans through a multibyte character or over 4 KiB', async () => {
    const { model } = await snippetReady(); model.state.original = '中'; model.state.originalMatched = true
    model.state.byteStart = 1; model.state.byteEnd = 3; model.state.confirmed.snippet = true; expect(model.canSnippet()).toBe(false)
    model.state.byteStart = 0; model.state.byteEnd = 3; expect(model.canSnippet()).toBe(true)
    model.state.original = 'a'.repeat(4097); model.state.byteEnd = 4097; expect(model.canSnippet()).toBe(false)
    model.state.byteEnd = 1.5; expect(model.canSnippet()).toBe(false)
  })
  it('requires four explicit classification choices and never creates a date snapshot in the browser', async () => {
    const { api, model } = await snippetReady(); model.state.confirmed.fact = true; expect(model.canFact()).toBe(false)
    Object.assign(model.state.classification, { claim: 'informational', unit: 'unknown', period: 'unknown', basis: 'unknown', dateId: '' })
    await model.createFact(); expect(vi.mocked(api.fact).mock.calls[0][0].classification.date_event_id).toBeNull()
    expect(vi.mocked(api.fact).mock.calls[0][0]).not.toHaveProperty('date_resolution')
  })
  it('invalidates committed receipts and confirmations when selecting another row', async () => {
    const { model } = await snippetReady(); model.state.confirmed.fact = true; model.selectRow(rowId)
    expect(model.state.document).toBeNull(); expect(model.state.version).toBeNull(); expect(model.state.snippet).toBeNull()
    expect(Object.values(model.state.confirmed)).toEqual([false, false, false, false]); expect(model.state.classification.claim).toBe('')
  })
  it('does not refill an old document after original content changes during a request', async () => {
    const pending = deferred<ReturnType<typeof document>>(), { api, model } = await prepared(workspaceApi({ document: vi.fn(() => pending.promise) }))
    model.state.confirmed.document = true; const call = model.createDocument(); model.state.original = 'changed'; model.originalChanged()
    pending.resolve(document()); await call; expect(model.state.document).toBeNull(); expect(model.state.originalMatched).toBe(false)
    expect(vi.mocked(api.document).mock.calls[0][1]?.aborted).toBe(true)
  })
  it('does not restore another actor batch after a late read', async () => {
    const pending = deferred<ReturnType<typeof rows>>(), api = workspaceApi({ rows: vi.fn(() => pending.promise) }), model = usePreparation(api)
    model.setActor(actor); model.state.importId = importId; const call = model.loadRows(); model.setActor(otherActor)
    pending.resolve(rows()); await call; expect(model.state.page).toBeNull(); expect(model.state.importId).toBe('')
  })
  it('clears private data and notifies session expiry on a 401 without claiming later steps committed', async () => {
    const expired = vi.fn(), api = workspaceApi({ rows: vi.fn(async () => { throw new ReviewWorkspaceError(401) }) }), model = usePreparation(api, expired)
    model.setActor(actor); model.state.importId = importId; await model.loadRows()
    expect(model.state.page).toBeNull(); expect(model.state.importId).toBe(''); expect(expired).toHaveBeenCalledOnce(); expect(model.state.error).toBe(true)
  })
})
