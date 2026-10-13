import { describe, expect, it } from 'vitest'
import type { Envelope, Eligibility, Evidence, PlanDraft, Profile } from '../../../packages/contracts/index'
import { useWorkspace } from '../src/workspace'
import { config, deferred, eligibility, envelope, evidence, makeApi, offering, plan, profile } from './fixtures'

describe('workspace context isolation and result invalidation', () => {
  it('uses the configured province/year for catalog queries', async () => {
    const api = makeApi(), workspace = useWorkspace(api)
    await workspace.load()
    expect(api.offerings).toHaveBeenCalledWith('alice', { province: config.supported_province, entry_year: config.entry_year })
  })
  it('ignores a late Alice profile response after switching to Bob', async () => {
    const api = makeApi(), alice = deferred<Envelope<Profile[]>>()
    api.profiles.mockImplementation((user) => user === 'alice' ? alice.promise : Promise.resolve(envelope([profile('bob')])))
    const workspace = useWorkspace(api), initialLoad = workspace.load()
    await Promise.resolve()
    await workspace.switchUser('bob')
    alice.resolve(envelope([profile('alice')]))
    await initialLoad
    expect(workspace.state.profiles.map((item) => item.owner_id)).toEqual(['demo_bob'])
    expect(workspace.profile.value?.owner_id).toBe('demo_bob')
  })
  it('clears private results immediately and ignores old-user checks', async () => {
    const api = makeApi(), pending = deferred<Envelope<Eligibility[]>>()
    api.check.mockReturnValueOnce(pending.promise)
    const workspace = useWorkspace(api)
    await workspace.load(); workspace.selectOfferings([offering.id])
    const check = workspace.check()
    await workspace.switchUser('bob')
    expect(workspace.state.results).toEqual([])
    expect(workspace.state.selectedOfferingIds).toEqual([])
    pending.resolve(envelope([eligibility('eligible')]))
    await check
    expect(workspace.state.results).toEqual([])
  })
  it('disables checks and discards a pending draft when the profile is edited', async () => {
    const api = makeApi(), pending = deferred<Envelope<PlanDraft>>()
    api.draft.mockReturnValueOnce(pending.promise)
    const workspace = useWorkspace(api)
    await workspace.load(); workspace.selectOfferings([offering.id]); await workspace.check()
    const draft = workspace.draft()
    workspace.markProfileEdited()
    pending.resolve(envelope(plan)); await draft
    expect(workspace.state.results).toEqual([])
    expect(workspace.state.plan).toBeNull()
    expect(workspace.canCheck.value).toBe(false)
  })
  it('discard old evidence responses on profile selection changes', async () => {
    const api = makeApi(), pending = deferred<Envelope<Evidence>>()
    api.evidence.mockReturnValueOnce(pending.promise)
    const workspace = useWorkspace(api)
    await workspace.load()
    const read = workspace.showEvidence(evidence.id)
    workspace.selectProfile('')
    pending.resolve(envelope(evidence)); await read
    expect(workspace.state.evidence).toBeNull()
  })
  it('does not retain a stale plan after a failed live draft', async () => {
    const api = makeApi(), workspace = useWorkspace(api)
    await workspace.load(); workspace.selectOfferings([offering.id]); await workspace.check(); await workspace.draft()
    expect(workspace.state.plan).not.toBeNull()
    api.draft.mockRejectedValueOnce(new Error('live 当前不可用'))
    await workspace.draft()
    expect(workspace.state.plan).toBeNull()
    expect(workspace.state.error).toBe('live 当前不可用')
  })
})
