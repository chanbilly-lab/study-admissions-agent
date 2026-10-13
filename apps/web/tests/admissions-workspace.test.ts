import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAdmissionsWorkspace } from '../src/features/catalog/useAdmissionsWorkspace'
import { offeringKey } from '../src/features/catalog/client'
import { EligibilityError } from '../src/features/eligibility/client'
import { actor, otherActor, deferred } from './profilesFixtures'
import { assessment, catalogApi, clone, config, eligibilityApi, evidence, id, offering, page, version } from './catalogFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => vi.unstubAllGlobals())
async function ready(overrides: Parameters<typeof useAdmissionsWorkspace>[0] = {}) {
  const api = overrides.eligibilityApi ?? eligibilityApi(), publicApi = overrides.catalogApi ?? catalogApi()
  const workspace = useAdmissionsWorkspace({ catalogApi: publicApi, eligibilityApi: api })
  workspace.setAccess(actor, true); await workspace.setProfile(version(), 1); workspace.setFilters({ entry_year: 2027 }); await workspace.search()
  workspace.selectOffering(offeringKey(offering())); await workspace.refreshContext()
  return { workspace, api, publicApi }
}
describe('T29 independent response generations', () => {
  it('starts with an explicit blank year and browses without any student access', async () => {
    const publicApi = catalogApi(), api = eligibilityApi(), w = useAdmissionsWorkspace({ catalogApi: publicApi, eligibilityApi: api })
    expect(w.state.query.entry_year).toBeNull(); await w.search(); expect(publicApi.offerings).not.toHaveBeenCalled()
    w.setFilters({ entry_year: 2027 }); await w.search(); expect(w.state.page?.items).toHaveLength(1); expect(api.context).not.toHaveBeenCalled(); expect(w.canEvaluate()).toBe(false)
  })
  it('does not deny evaluation because facts-only release has no ruleset or context says rules unavailable', async () => {
    const { workspace: w, api } = await ready(); expect(w.canEvaluate()).toBe(true); w.setConfirmed(true); await w.evaluateSelected()
    expect(api.evaluate).toHaveBeenCalledOnce(); expect(w.state.result?.eligibility.status).toBe('unknown')
    expect(w.state.result?.target.scope_sha256).toBe(assessment().target.scope_sha256)
  })
  it('requires explicit confirmation; stage and additional scope changes clear old results and confirmation', async () => {
    const { workspace: w, api } = await ready(); await w.evaluateSelected(); expect(api.evaluate).not.toHaveBeenCalled()
    w.setConfirmed(true); await w.evaluateSelected(); expect(w.state.result).not.toBeNull()
    w.setStage('enrollment'); expect(w.state.result).toBeNull(); expect(w.state.confirmed).toBe(false)
    w.setConfirmed(true); w.setScope('channel', null); expect(w.state.confirmed).toBe(false)
  })
  it.each(['logout', 'core', 'actor', 'same-user-session', 'profile-epoch', 'target', 'scope', 'stage', 'dispose'])('prevents delayed private restoration after %s', async change => {
    const pending = deferred<ReturnType<typeof assessment>>(), api = eligibilityApi({ evaluate: vi.fn(() => pending.promise) }), { workspace: w } = await ready({ eligibilityApi: api })
    w.setConfirmed(true); const task = w.evaluateSelected(); await vi.waitFor(() => expect(api.evaluate).toHaveBeenCalled())
    if (change === 'logout') w.setAccess(null, false)
    else if (change === 'core') w.setAccess(actor, false)
    else if (change === 'actor') w.setAccess(otherActor, true)
    else if (change === 'same-user-session') w.setAccess({ ...actor }, true)
    else if (change === 'profile-epoch') await w.setProfile(version(), 2)
    else if (change === 'target') w.selectOffering(offeringKey(offering()))
    else if (change === 'scope') w.setScope('channel', null)
    else if (change === 'stage') w.setStage('enrollment')
    else w.dispose()
    expect(w.state.result).toBeNull(); pending.resolve(assessment()); await task
    expect(w.state.result).toBeNull(); expect(w.state.confirmed).toBe(false); expect(w.state.privateBusy).toBe(false)
  })
  it('keeps public browsing independent while subject changes close the evidence overlay and cancel its pending response', async () => {
    const pending = deferred<ReturnType<typeof evidence>>(), publicApi = catalogApi({ evidence: vi.fn(() => pending.promise) }), { workspace: w } = await ready({ catalogApi: publicApi })
    const task = w.openEvidence(id(104)); w.setAccess(otherActor, true); pending.resolve(evidence()); await task
    expect(w.state.evidence).toBeNull(); expect(w.state.page?.items).toHaveLength(1)
  })
  it('checks exact selected full scope and release instead of accepting a valid quote from another target', async () => {
    const wrong = evidence(offering(2)), { workspace: w } = await ready({ catalogApi: catalogApi({ evidence: vi.fn(async () => wrong) }) })
    await w.openEvidence(id(104)); expect(w.state.evidence).toBeNull(); expect(w.state.evidenceMessage).not.toBe('')
    await w.openEvidence(id(999)); expect(w.state.evidenceMessage).toContain('公开证据范围')
  })
  it('keeps comparison to four exact current-version identities and retains them across pages', async () => {
    const publicApi = catalogApi({ offerings: vi.fn(async q => q.cursor ? page([offering(5)], 20) : page([offering(1), offering(2), offering(3), offering(4)], 20, 'opaque')) })
    const { workspace: w } = await ready({ catalogApi: publicApi })
    for (let i = 1; i <= 4; i++) w.toggleCompare(offeringKey(offering(i)))
    await w.nextPage(); w.toggleCompare(offeringKey(offering(5))); expect(w.compareItems()).toHaveLength(4); expect(w.state.publicMessage).toContain('最多比较')
    w.setFilters({ country: 'GB' }); expect(w.compareItems()).toHaveLength(0); expect(w.state.selectedKey).toBeNull()
  })
  it.each([401, 403, 503, 200])('clears private records after fixed error %s and emits only 401 upward', async status => {
    const expired = vi.fn(), api = eligibilityApi({ evaluate: vi.fn(async () => { throw new EligibilityError(status) }) }), w = useAdmissionsWorkspace({ catalogApi: catalogApi(), eligibilityApi: api }, expired)
    w.setAccess(actor, true); await w.setProfile(version(), 1); w.setFilters({ entry_year: 2027 }); await w.search(); w.selectOffering(offeringKey(offering())); await w.refreshContext(); w.setConfirmed(true); await w.evaluateSelected()
    expect(w.state.result).toBeNull(); expect(w.state.history).toBeNull(); expect(w.state.profile).toBeNull(); expect(expired).toHaveBeenCalledTimes(status === 401 ? 1 : 0)
  })
  it('historical withdrawn replay preserves the immutable unknown outcome without overwriting the selected target result', async () => {
    const data = assessment({ replayed: true, current_validity: 'withdrawn' }), { workspace: w } = await ready({ eligibilityApi: eligibilityApi({ replay: vi.fn(async () => data) }) })
    w.setConfirmed(true); await w.evaluateSelected(); const original = clone(w.state.result)
    w.setAssessmentId(data.assessment_id); await w.replayAssessment(); expect(w.state.history).toBeNull()
    w.setReplayConfirmed(true); await w.replayAssessment(); expect(w.state.history?.current_validity).toBe('withdrawn'); expect(w.state.result).toEqual(original)
  })
  it('changing historical ID aborts pending old history and clears only its old confirmation and snapshot', async () => {
    const pending = deferred<ReturnType<typeof assessment>>(), api = eligibilityApi({ get: vi.fn(() => pending.promise) }), { workspace: w } = await ready({ eligibilityApi: api })
    w.setAssessmentId(id(200)); const task = w.readAssessment(); expect(api.get).toHaveBeenCalledOnce()
    w.setAssessmentId(id(201)); expect(w.state.replayConfirmed).toBe(false); pending.resolve(assessment()); await task
    expect(w.state.history).toBeNull(); expect(w.state.assessmentId).toBe(id(201))
  })
  it('rejects a fully rehashed assessment from another selected profile and clears its result', async () => {
    const wrong = assessment({ profile_sha256: '0'.repeat(64) }), { workspace: w } = await ready({ eligibilityApi: eligibilityApi({ evaluate: vi.fn(async () => wrong) }) })
    w.setConfirmed(true); await w.evaluateSelected(); expect(w.state.result).toBeNull(); expect(w.state.privateError).toBe(200)
  })
  it('rejects mixed-mode config and records, unknown hashes, and keeps blank public data separate from private failures', async () => {
    const publicApi = catalogApi({ config: vi.fn(async () => ({ ...config(), allow_test_fixture_read: false, demo_banner: null })) }), { workspace: w } = await ready({ catalogApi: publicApi })
    expect(w.state.page).toBeNull(); expect(w.state.publicError).toBe(200)
    const invalid = clone(version()); invalid.profile_sha256 = '1'.repeat(64); await w.setProfile(invalid, 3); expect(w.state.profile).toBeNull()
  })
})
