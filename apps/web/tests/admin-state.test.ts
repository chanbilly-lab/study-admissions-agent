import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminError } from '../src/features/admin/client'
import { useAdmin } from '../src/features/admin/useAdmin'
import { actor, otherActor, deferred, adminApi, context, definition, source, file, rejected, result, datasetId, sourceId, content } from './adminFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto))
afterEach(() => vi.unstubAllGlobals())
function fill(model: ReturnType<typeof useAdmin>) {
  Object.assign(model.state.draft, { datasetId, datasetRevision: 1, reference: 'DEMO_source', publisher: 'DEMO_合成发布者',
    url: definition().entry_url, dataType: 'entry_requirements', scope: 'DEMO 本科要求', manual: 'granted',
    basis: 'DEMO_仅合成测试授权', permissionReference: 'DEMO_permission', recheckDays: 30, manualEnabled: true, confirmed: true })
}
async function loaded(api = adminApi()) {
  const model = useAdmin(api); await model.setActor(actor)
  model.state.sourceQueryId = sourceId; await model.loadSource()
  model.state.filename = 'DEMO.json'; model.state.content = content; model.state.fileConfirmed = true
  return model
}

describe('explicit current management state', () => {
  it('does not query anonymous management or infer privilege from login', async () => {
    const api = adminApi(), model = useAdmin(api); await model.setActor(null)
    expect(api.context).not.toHaveBeenCalled(); expect(model.canManage()).toBe(false)
    await model.setActor(actor); expect(api.context).toHaveBeenCalledOnce()
  })
  it.each([403, 503])('server status %s closes all forms without synthetic fallback', async status => {
    const api = adminApi({ context: vi.fn().mockRejectedValue(new AdminError(status)) }), model = useAdmin(api)
    await model.setActor(actor); fill(model); await model.saveSource()
    expect(model.state.context).toBeNull(); expect(model.canSave()).toBe(false); expect(api.register).not.toHaveBeenCalled()
  })
  it('requires independent source confirmation and handles actual numeric v-model values', async () => {
    const api = adminApi(), model = useAdmin(api); await model.setActor(actor); fill(model)
    model.state.draft.confirmed = false; await model.saveSource(); expect(api.register).not.toHaveBeenCalled()
    model.state.draft.confirmed = true; await model.saveSource()
    expect(api.register).toHaveBeenCalledWith({ expected_dataset_revision: 1, confirmed: true, source: {
      id: expect.any(String), dataset_id: datasetId, reference_key: 'DEMO_source', is_synthetic: true, definition: definition(),
    } }, expect.any(AbortSignal))
    expect(model.state.source?.version).toBe(1); expect(model.state.draft.confirmed).toBe(false)
    expect(model.state.message).toContain('不是事实审核')
  })
  it('does not treat official declaration as manual or publication permission', async () => {
    const model = useAdmin(adminApi()); await model.setActor(actor); fill(model)
    Object.assign(model.state.draft, { authority: 'claimed_official', manual: 'pending', basis: '', permissionReference: '', manualEnabled: true })
    expect(model.canSave()).toBe(false)
    model.state.draft.manualEnabled = false; expect(model.canSave()).toBe(true)
  })
  it('rejects fractional numeric versions and pending permissions with an invented basis', async () => {
    const model = useAdmin(adminApi()); await model.setActor(actor); fill(model)
    model.state.draft.datasetRevision = 1.2; expect(model.canSave()).toBe(false)
    model.state.draft.datasetRevision = 1; model.state.draft.manual = 'pending'; model.state.draft.manualEnabled = false
    expect(model.canSave()).toBe(false)
  })
  it('CAS409 clears old success and requires a fresh source read and confirmation', async () => {
    const api = adminApi({ revise: vi.fn().mockRejectedValue(new AdminError(409)) }), model = await loaded(api)
    model.state.file = file(); model.state.draft.confirmed = true; await model.saveSource()
    expect(model.state.source).toBeNull(); expect(model.state.file).toBeNull(); expect(model.state.draft.confirmed).toBe(false)
    expect(model.state.notice).toBe('error'); expect(model.state.message).toContain('重新读取')
  })
  it('binds an upload to the exact stored source and byte hash before accepting a receipt', async () => {
    const api = adminApi(), model = await loaded(api); await model.upload()
    expect(api.upload).toHaveBeenCalledWith({ source_id: sourceId, source_version: 1, filename: 'DEMO.json', content_type: 'application/json', content_utf8: content, confirmed: true }, expect.any(AbortSignal))
    expect(model.state.file).toEqual(file()); expect(model.state.fileConfirmed).toBe(false); expect(model.state.importConfirmed).toBe(false)
    expect(model.state.message).toContain('不代表安全扫描')
  })
  it('rejects a mismatched byte receipt and cannot import it', async () => {
    const model = await loaded(adminApi({ upload: vi.fn(async () => file({ sha256: 'f'.repeat(64) })) })); await model.upload()
    expect(model.state.file).toBeNull(); expect(model.canSubmitImport()).toBe(false); expect(model.state.notice).toBe('error')
  })
  it.each(['sourceChanged', 'queryChanged', 'originalChanged'] as const)('scope/content edit %s aborts a pending upload and blocks its old receipt', async method => {
    const wait = deferred<ReturnType<typeof file>>(), api = adminApi({ upload: vi.fn(() => wait.promise) }), model = await loaded(api)
    const operation = model.upload(); await vi.waitFor(() => expect(api.upload).toHaveBeenCalledOnce())
    model[method](); expect(vi.mocked(api.upload).mock.calls[0][1]?.aborted).toBe(true)
    wait.resolve(file()); await operation
    expect(model.state.file).toBeNull(); expect(model.state.message).toBe(''); expect(model.state.busy).toBeNull()
  })
  it('file content edits clear the old receipt, confirmations and successful import result', async () => {
    const model = await loaded(); model.state.file = file(); model.state.result = result(); model.state.importConfirmed = true
    model.state.content = '[]'; model.originalChanged()
    expect(model.state.file).toBeNull(); expect(model.state.result).toBeNull(); expect(model.state.importConfirmed).toBe(false)
  })
  it('same explicit retry keeps its idempotency key; changed file content gets a new key', async () => {
    const api = adminApi({ import: vi.fn().mockRejectedValueOnce(new AdminError(0)).mockResolvedValue(result()) }), model = await loaded(api)
    await model.upload(); model.state.importConfirmed = true; await model.submitImport()
    expect(model.state.result).toBeNull(); model.state.importConfirmed = true; await model.submitImport()
    expect(vi.mocked(api.import).mock.calls[1][1]).toBe(vi.mocked(api.import).mock.calls[0][1])
    model.state.content = '[ ]'; model.originalChanged(); model.state.fileConfirmed = true; await model.upload()
    model.state.importConfirmed = true; await model.submitImport()
    expect(vi.mocked(api.import).mock.calls[2][1]).not.toBe(vi.mocked(api.import).mock.calls[0][1])
  })
  it('a rejected response is zero candidates, never an optimistic publish state', async () => {
    const model = await loaded(adminApi({ import: vi.fn(async () => rejected()) })); await model.upload()
    await model.submitImport(); expect(model.state.result).toBeNull()
    model.state.importConfirmed = true; await model.submitImport()
    expect(model.state.result).toEqual(rejected()); expect(model.state.message).toContain('拒绝整批'); expect(model.state.result?.total_rows).toBeNull()
  })
  it('401 clears management and signals the parent session', async () => {
    const expired = vi.fn(), api = adminApi({ source: vi.fn().mockRejectedValue(new AdminError(401)) }), model = useAdmin(api, expired)
    await model.setActor(actor); model.state.sourceQueryId = sourceId; await model.loadSource()
    expect(expired).toHaveBeenCalledOnce(); expect(model.state.context).toBeNull(); expect(model.state.source).toBeNull()
  })
  it('actor switch prevents a prior read from restoring another account metadata', async () => {
    const wait = deferred<ReturnType<typeof source>>(), api = adminApi({ source: vi.fn(() => wait.promise) }), model = useAdmin(api)
    await model.setActor(actor); model.state.sourceQueryId = sourceId; const operation = model.loadSource()
    await model.setActor(otherActor); wait.resolve(source()); await operation
    expect(model.state.source).toBeNull(); expect(model.state.sourceQueryId).toBe(''); expect(model.state.draft.datasetId).toBe('')
  })
  it('logout clears a late context result and all original text', async () => {
    const wait = deferred<ReturnType<typeof context>>(), model = useAdmin(adminApi({ context: vi.fn(() => wait.promise) }))
    const operation = model.setActor(actor); model.state.content = content; await model.setActor(null)
    wait.resolve(context()); await operation
    expect(model.state.context).toBeNull(); expect(model.state.content).toBe(''); expect(model.state.status).toBe('idle')
  })
})
