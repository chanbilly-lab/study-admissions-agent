import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ProfileError } from '../src/features/profiles/client'
import { snapshotToDraft } from '../src/features/profiles/form'
import { useProfiles } from '../src/features/profiles/useProfiles'
import { actor, context, deferred, otherActor, profileApi, rootId, snapshot, version, versionId } from './profilesFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => vi.unstubAllGlobals())
async function loaded(api = profileApi()) { const model = useProfiles(api); await model.setAccess(actor, true); await model.load(rootId); return model }
function newDraft(model: ReturnType<typeof useProfiles>) { model.newProfile(); model.state.draft = snapshotToDraft(snapshot()); model.state.draft.confirmed = true }

describe('current-use and owner scoped profile state', () => {
  it('requires current core signal and fresh server capability, never session flags or client roles', async () => {
    const api = profileApi(), model = useProfiles(api); await model.setAccess(actor, false); expect(api.context).not.toHaveBeenCalled()
    await model.setAccess(null, true); expect(api.context).not.toHaveBeenCalled()
    await model.setAccess(actor, true); expect(api.context).toHaveBeenCalledOnce(); expect(model.state.current).toBeNull(); expect(model.state.editing).toBe(false)
  })
  it('respects independent can_create/read/append flags', async () => {
    const api = profileApi({ context: vi.fn(async () => context({ can_create: false, can_append: false })) }), model = await loaded(api)
    model.newProfile(); model.editCurrent(); expect(model.state.editing).toBe(false); expect(model.canRead()).toBe(true)
  })
  it('initially reads a version as readonly and never uses a history version as current CAS', async () => {
    const api = profileApi(), model = await loaded(api); expect(model.state.editing).toBe(false)
    model.editCurrent(); expect(model.state.editing).toBe(true); model.state.historyVersionId = versionId; await model.history()
    expect(model.state.current?.version).toBe(1); expect(model.state.history?.version_id).toBe(versionId); expect(model.state.draft.confirmed).toBe(false)
  })
  it('requires new confirmation after each edit and does not produce client authority fields', async () => {
    const api = profileApi(), invalidated = vi.fn(), model = useProfiles(api, vi.fn(), invalidated); await model.setAccess(actor, true); newDraft(model)
    model.changed(); await model.save(); expect(api.create).not.toHaveBeenCalled(); model.state.draft.confirmed = true; await model.save()
    expect(api.create).toHaveBeenCalledOnce(); expect(vi.mocked(api.create).mock.calls[0][0]).not.toHaveProperty('owner_id'); expect(model.state.draft.confirmed).toBe(false)
    expect(model.state.current?.profile.assessments.math!.achieved.value).toBe('0'); expect(invalidated).toHaveBeenCalled()
  })
  it('same explicit create retry keeps exact key; editing clears it and prevents duplicate pending saves', async () => {
    const wait = deferred<{ version: ReturnType<typeof version>; replayed: boolean }>()
    const api = profileApi({ create: vi.fn().mockRejectedValueOnce(new ProfileError(0)).mockReturnValueOnce(wait.promise).mockResolvedValue({ version: version({ profile: snapshot({ weekly_hours: '1' }) }), replayed: false }) })
    const model = useProfiles(api); await model.setAccess(actor, true); newDraft(model); await model.save()
    model.state.draft.confirmed = true; const pending = model.save(); await model.save(); expect(api.create).toHaveBeenCalledTimes(2)
    expect(vi.mocked(api.create).mock.calls[0][1]).toBe(vi.mocked(api.create).mock.calls[1][1]); wait.reject(new ProfileError(0)); await pending
    model.state.draft.weeklyHours = '1'; model.changed(); model.state.draft.confirmed = true; await model.save()
    expect(vi.mocked(api.create).mock.calls[2][1]).not.toBe(vi.mocked(api.create).mock.calls[1][1])
  })
  it('CAS409 preserves only the local draft, clears confirmation and requires an explicit fresh current read', async () => {
    const api = profileApi({ append: vi.fn().mockRejectedValue(new ProfileError(409)), current: vi.fn().mockResolvedValueOnce(version()).mockResolvedValue(version({ version: 3 })) }), model = await loaded(api)
    model.editCurrent(); model.state.draft.weeklyHours = '2'; model.changed(); model.state.draft.confirmed = true; await model.save()
    expect(model.state.conflict).toBe(true); expect(model.state.draft.weeklyHours).toBe('2'); expect(model.state.draft.confirmed).toBe(false)
    model.state.draft.confirmed = true; await model.save(); expect(api.append).toHaveBeenCalledOnce()
    await model.load(rootId, true); expect(model.state.current?.version).toBe(3); expect(model.state.draft.weeklyHours).toBe('2'); expect(model.state.draft.confirmed).toBe(false)
  })
  it('network-uncertain append blocks repeat writes until current is explicitly reloaded', async () => {
    const api = profileApi({ append: vi.fn().mockRejectedValue(new ProfileError(0)) }), model = await loaded(api); model.editCurrent(); model.state.draft.confirmed = true
    await model.save(); expect(model.state.appendUnconfirmed).toBe(true); model.state.draft.confirmed = true; await model.save(); expect(api.append).toHaveBeenCalledOnce()
  })
  it.each([401, 403, 404, 503])('write status %s clears all private values/receipts and does not retain permission', async status => {
    const expired = vi.fn(), api = profileApi({ append: vi.fn().mockRejectedValue(new ProfileError(status)) }), model = useProfiles(api, expired)
    await model.setAccess(actor, true); await model.load(rootId); model.editCurrent(); model.state.draft.confirmed = true; await model.save()
    expect(model.state.current).toBeNull(); expect(model.state.history).toBeNull(); expect(model.state.context).toBeNull(); expect(model.state.draft.grades).toEqual({}); expect(model.canSave()).toBe(false)
    expect(expired).toHaveBeenCalledTimes(status === 401 ? 1 : 0)
  })
  it.each(['core', 'actor', 'edit', 'dispose'] as const)('invalidates pending current reads on %s and refuses late private responses', async action => {
    const wait = deferred<ReturnType<typeof version>>(), api = profileApi({ current: vi.fn(() => wait.promise) }), model = useProfiles(api)
    await model.setAccess(actor, true); const pending = model.load(rootId)
    if (action === 'core') await model.setAccess(actor, false)
    else if (action === 'actor') await model.setAccess(otherActor, true)
    else if (action === 'edit') model.changed()
    else model.dispose()
    expect(vi.mocked(api.current).mock.calls[0][1]?.aborted).toBe(true); wait.resolve(version()); await pending
    expect(model.state.current).toBeNull(); expect(model.state.history).toBeNull()
  })
  it('mode mismatch and a self-consistent but different saved payload are never accepted', async () => {
    const api = profileApi({ create: vi.fn(async () => ({ version: version({ profile: snapshot({ weekly_hours: '40' }) }), replayed: false })) }), model = useProfiles(api)
    await model.setAccess(actor, true); newDraft(model); await model.save(); expect(model.state.current).toBeNull(); expect(model.state.context).toBeNull()
    await model.setAccess({ ...actor, is_synthetic: false }, true); expect(model.state.context).toBeNull()
  })
})
