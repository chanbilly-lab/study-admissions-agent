import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRelease } from '../src/features/admin/releases/useRelease'
import { ReviewWorkspaceError } from '../src/features/admin/reviews/client'
import { actor, otherActor, deferred, workspaceApi, datasetId, factId, decisionId, releaseId, current, publishedHead, prechecked, release } from './reviewReleaseFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto))
afterEach(() => vi.unstubAllGlobals())

async function configured(api = workspaceApi()) {
  const model = useRelease(api); model.setAccess(actor, true, true); model.state.datasetId = datasetId; model.state.year = 2027; await model.loadCurrent()
  model.state.kind = 'test_fixture'; model.state.validFrom = '2026-10-02T00:00:00Z'; model.state.validUntil = '2026-10-04T00:00:00Z'
  Object.assign(model.state.members[0], { factId, caseRevision: 1, decisionId }); return { api, model }
}
async function checked(api = workspaceApi()) { const value = await configured(api); value.model.state.precheckConfirmed = true; await value.model.precheck(); return value }

describe('atomic release confirmation state', () => {
  it('uses current server dataset CAS and requires precheck and publish confirmations separately', async () => {
    const { api, model } = await configured(); expect(model.state.members[0].publicEvidence).toBe(false); expect(model.canPrecheck()).toBe(false)
    model.state.precheckConfirmed = true; await model.precheck(); expect(model.state.precheck?.status).toBe('precheck_passed'); expect(model.canPublishNow()).toBe(false)
    model.state.publishConfirmed = true; await model.publish(); expect(vi.mocked(api.publish).mock.calls[0][0]).toMatchObject({ expected_dataset_revision: 4, replaces_release_id: null, expected_replaced_state_revision: null, confirmed: true })
    expect(model.state.result?.state).toBe('published'); expect(model.state.head).toBeNull(); expect(model.state.message).toContain('不能把此管理回执当公共投影')
  })
  it.each(['2026-10-02', '2026-10-02T00:00:00', '2026-02-30T00:00:00Z'])('rejects incomplete or invalid UTC window %s without inventing a deadline', async value => {
    const { model } = await configured(); model.state.validFrom = value; expect(model.input()).toBeNull()
  })
  it('does not permit duplicate members, fractional revisions, reversed windows or synthetic formal release', async () => {
    const { model } = await configured(); model.state.members[0].caseRevision = 1.5; expect(model.input()).toBeNull()
    model.state.members[0].caseRevision = 1; model.addMember(); Object.assign(model.state.members[1], model.state.members[0]); expect(model.input()).toBeNull()
    model.removeMember(1); model.state.kind = 'formal'; expect(model.input()).toBeNull()
    model.state.kind = 'test_fixture'; model.state.validUntil = model.state.validFrom; expect(model.input()).toBeNull()
  })
  it('invalidates precheck and both positive confirmations after payload changes', async () => {
    const { model } = await checked(); model.state.publishConfirmed = true; model.state.members[0].publicEvidence = true; model.changed()
    expect(model.state.precheck).toBeNull(); expect(model.state.precheckConfirmed).toBe(false); expect(model.canPublishNow()).toBe(false)
  })
  it('ignores a stale precheck completed after an actor switch', async () => {
    const pending = deferred<ReturnType<typeof prechecked>>(), { model } = await configured(workspaceApi({ precheck: vi.fn(() => pending.promise) }))
    model.state.precheckConfirmed = true; const call = model.precheck(); model.setAccess(otherActor, true, true); pending.resolve(prechecked()); await call
    expect(model.state.precheck).toBeNull(); expect(model.state.head).toBeNull(); expect(model.state.members[0].factId).toBe('')
  })
  it('uses exact current published target and state revision only when replacement is explicit', async () => {
    const { model } = await configured(workspaceApi({ current: vi.fn(async () => publishedHead()) }))
    expect(model.input()?.replaces_release_id).toBeNull(); model.state.replace = true
    expect(model.input()).toMatchObject({ replaces_release_id: releaseId, expected_replaced_state_revision: 1 })
  })
  it('keeps withdrawal reachable when positive precheck fails because a source is unavailable', async () => {
    const api = workspaceApi({ current: vi.fn(async () => publishedHead()), precheck: vi.fn(async () => { throw new ReviewWorkspaceError(503) }) })
    const { model } = await configured(api); model.state.precheckConfirmed = true; await model.precheck()
    expect(model.state.precheck).toBeNull(); expect(model.state.head?.release?.state).toBe('published')
    model.state.withdrawalReason = 'SOURCE_UNAVAILABLE'; model.state.withdrawConfirmed = true; await model.withdraw()
    expect(api.withdraw).toHaveBeenCalledWith(releaseId, { expected_state_revision: 1, reason_code: 'SOURCE_UNAVAILABLE', confirmed: true }, expect.any(AbortSignal))
    expect(model.state.result?.state).toBe('withdrawn'); expect(api.publish).not.toHaveBeenCalled()
  })
  it('does not claim success or retry automatically after an unconfirmed publish, and reuses the key only for an explicit identical retry', async () => {
    const api = workspaceApi({ publish: vi.fn().mockRejectedValueOnce(new ReviewWorkspaceError(0)).mockResolvedValueOnce(release()) }), { model } = await checked(api)
    model.state.publishConfirmed = true; await model.publish(); expect(api.publish).toHaveBeenCalledOnce(); expect(model.state.result).toBeNull(); expect(model.state.publishConfirmed).toBe(false)
    expect(model.canPublishNow()).toBe(false); model.state.publishConfirmed = true; await model.publish()
    expect(vi.mocked(api.publish).mock.calls[0][1]).toBe(vi.mocked(api.publish).mock.calls[1][1]); expect(model.state.result?.state).toBe('published')
  })
  it('clears current metadata and notifies expiry on a 401', async () => {
    const expired = vi.fn(), api = workspaceApi({ current: vi.fn(async () => { throw new ReviewWorkspaceError(401) }) }), model = useRelease(api, expired)
    model.setAccess(actor, true, true); model.state.datasetId = datasetId; model.state.year = 2027; await model.loadCurrent()
    expect(model.state.head).toBeNull(); expect(model.state.datasetId).toBe(''); expect(expired).toHaveBeenCalledOnce()
  })
  it('does not refill old current metadata after a scope edit', async () => {
    const pending = deferred<ReturnType<typeof current>>(), api = workspaceApi({ current: vi.fn(() => pending.promise) }), model = useRelease(api)
    model.setAccess(actor, true, true); model.state.datasetId = datasetId; model.state.year = 2027; const call = model.loadCurrent()
    model.state.year = 2028; model.scopeChanged(); pending.resolve(current()); await call; expect(model.state.head).toBeNull()
  })
})
