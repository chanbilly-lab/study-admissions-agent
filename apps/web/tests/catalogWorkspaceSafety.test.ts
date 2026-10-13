// T29 independent boundary tests: asynchronous replies deliberately ignore
// cancellation, so success requires generations/bindings rather than a mock abort.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAdmissionsWorkspace } from '../src/features/catalog/useAdmissionsWorkspace'
import { CatalogError } from '../src/features/catalog/client'
import { createEligibilityApi, EligibilityError } from '../src/features/eligibility/client'
import { scopeFingerprint } from '../src/features/catalog/validation'
import { actor, otherActor, deferred, nextVersionId } from './profilesFixtures'
import { assessment, catalogApi, clone, context, eligibilityApi, evidence, hash, id, offering, page, response, version } from './catalogFixtures'
import type { AssessmentData } from '../src/features/eligibility/client'

const owned: ReturnType<typeof useAdmissionsWorkspace>[] = []
afterEach(() => { for (const w of owned.splice(0)) w.dispose() })
function workspace(options: Parameters<typeof useAdmissionsWorkspace>[0] = {}, expired = vi.fn()) {
  const w = useAdmissionsWorkspace({ catalogApi: catalogApi(), eligibilityApi: eligibilityApi(), ...options }, expired); owned.push(w); return w
}
async function ready(options: Parameters<typeof useAdmissionsWorkspace>[0] = {}) {
  const w = workspace(options)
  w.setAccess(actor, true)
  await w.setProfile(version(), 1)
  w.setFilters({ entry_year: 2027 })
  await w.search()
  expect(w.state.publicStatus).toBe('ready')
  w.selectOffering(offering()); await w.refreshContext()
  expect(w.selectedOffering()).not.toBeNull(); expect(w.canEvaluate()).toBe(true)
  return w
}
function fixtureOutcome(status: 'eligible' | 'ineligible' | 'conditional' | 'unknown'): AssessmentData {
  if (status === 'unknown') return assessment()
  const truth = status === 'eligible' ? 'true' : status === 'ineligible' ? 'false' : 'unknown'
  const reason = truth === 'true' ? 'MATCH' : truth === 'false' ? 'NO_MATCH' : 'MISSING'
  return assessment({ binding_mode: 'test_fixture', ruleset_version: 'c'.repeat(64),
    rule_refs: [{ bundle_id: id(230), expression_sha256: 'd'.repeat(64), fact_ids: [id(231)], evidence_ids: [id(104)] }],
    eligibility: { status, reason: status === 'conditional' ? 'DEFERRAL_SATISFIABLE' : status === 'eligible' ? 'RULE_TRUE' : 'RULE_FALSE',
      evaluation: { truth, reason, trace: [{ op: 'gte', field: { name: 'assessment', key: 'math', basis: 'achieved' }, outcome: truth, reason, children: [] }] },
      obligations: status === 'conditional' ? [{ assessment_key: 'math', basis: 'achieved', deferral: {
        deferral_status: 'allowed', reason: 'ALLOWED', application_deadline_status: 'before', supplement_deadline_status: 'before',
        bundle_id: id(232), policy_id: id(233), policy_version: 'f'.repeat(64), application_deadline_event_id: id(234),
        supplement_deadline_event_id: id(235), evidence_ids: [id(104)] } }] : [] } })
}

describe('T29 independent current authority and request boundaries', () => {
  it.each(['context', 'assessment'] as const)('accepts a synthetic %s only with the actual enabled private verified/disabled mode', async operation => {
    const data = operation === 'context' ? context() : assessment()
    const fetcher = vi.fn(async () => response(data, { privateData: operation === 'assessment', overrides: { data_mode: 'verified', model_mode: 'disabled' } }))
    const api = createEligibilityApi('/api', fetcher)
    const read = operation === 'context' ? await api.context() : await api.get(id(200))
    expect(read).toEqual(data)
    expect(fetcher.mock.calls).toHaveLength(1)
  })

  it.each([
    ['context', 'disabled'], ['context', 'mock'], ['assessment', 'disabled'], ['assessment', 'mock'],
  ] as const)('rejects successful private %s metadata claiming demo/%s although the generic foundation permits it', async (operation, modelMode) => {
    const data = operation === 'context' ? context() : assessment()
    const fetcher = vi.fn(async () => response(data, { privateData: operation === 'assessment', overrides: { data_mode: 'demo', model_mode: modelMode } }))
    const api = createEligibilityApi('/api', fetcher)
    await expect(operation === 'context' ? api.context() : api.get(id(200))).rejects.toMatchObject({ status: 200 })
  })

  it('does not guess a year, read private data, or submit an unconfirmed request', async () => {
    const pub = catalogApi(), priv = eligibilityApi(), w = workspace({ catalogApi: pub, eligibilityApi: priv })
    expect(w.state.query.entry_year).toBeNull()
    await w.search(); await w.evaluateSelected(); await w.readAssessment(id(200))
    expect(pub.offerings).not.toHaveBeenCalled(); expect(priv.context).not.toHaveBeenCalled()
    expect(priv.evaluate).not.toHaveBeenCalled(); expect(priv.get).not.toHaveBeenCalled()
  })

  it('sends the full 21-field raw scope hash and only explicit profile/target references', async () => {
    const priv = eligibilityApi(), w = await ready({ eligibilityApi: priv })
    await w.evaluateSelected(); expect(priv.evaluate).not.toHaveBeenCalled()
    w.setConfirmed(true); await w.evaluateSelected()
    const input = vi.mocked(priv.evaluate).mock.calls[0]![0]
    expect(Object.keys(input).sort()).toEqual(['profile_id', 'profile_version_id', 'release_id', 'target', 'stage', 'confirmed',
      'intake', 'application_cycle', 'channel', 'exam_system', 'subject_scope', 'batch_group'].sort())
    expect(Object.keys(offering().scope)).toHaveLength(21)
    expect(input.target.scope_sha256).toBe(await scopeFingerprint(offering().scope))
    expect(input).not.toHaveProperty('owner_user_id'); expect(input).not.toHaveProperty('assessment_at')
    expect(input).not.toHaveProperty('residence_region'); expect(input).not.toHaveProperty('expression')
    expect(w.state.confirmed).toBe(false)
  })

  it.each(['eligible', 'ineligible', 'conditional', 'unknown'] as const)('preserves server %s without using the public null ruleset as authority', async status => {
    const raw = fixtureOutcome(status), w = await ready({ eligibilityApi: eligibilityApi({ evaluate: vi.fn(async () => clone(raw)) }) })
    expect(w.selectedOffering()!.ruleset_version).toBeNull()
    w.setConfirmed(true); await w.evaluateSelected()
    expect(w.state.result?.eligibility.status).toBe(status)
    expect(w.state.result?.competition_context.status).toBe('unknown')
    expect(w.state.result?.preference_fit.status).toBe('unknown')
    expect(w.state.result?.data_quality.status).toBe('unknown')
  })

  it.each(['profile_version_id', 'profile_sha256', 'release_id', 'requirements_version', 'stage', 'target'] as const)('rejects a validly hashed success bound to a different %s', async field => {
    const raw = assessment()
    if (field === 'target') raw.target.scope_sha256 = '2'.repeat(64)
    else if (field === 'stage') raw.stage = 'enrollment'
    else if (field === 'profile_sha256' || field === 'requirements_version') raw[field] = '2'.repeat(64)
    else raw[field] = id(299)
    raw.result_sha256 = hash(Object.fromEntries(Object.entries(raw).filter(([key]) => !['result_sha256', 'current_validity', 'replayed'].includes(key))))
    const w = await ready({ eligibilityApi: eligibilityApi({ evaluate: vi.fn(async () => raw) }) })
    w.setConfirmed(true); await w.evaluateSelected()
    expect(w.state.result).toBeNull(); expect(w.state.confirmed).toBe(false); expect(w.state.privateError).toBe(200)
  })

  it.each([401, 403, 404, 409, 422, 503])('does not retain a private success or confirmation after HTTP %s', async status => {
    const expired = vi.fn(), priv = eligibilityApi({ get: vi.fn(async () => { throw new EligibilityError(status) }) })
    const w = workspace({ eligibilityApi: priv }, expired)
    w.setAccess(actor, true); await w.setProfile(version(), 1); await w.refreshContext()
    w.setReplayConfirmed(true); await w.readAssessment(id(200))
    expect(w.state.history).toBeNull(); expect(w.state.replayConfirmed).toBe(false)
    expect(w.state.privateError).toBe(status); expect(expired).toHaveBeenCalledTimes(status === 401 ? 1 : 0)
  })
})

describe('T29 independent stale success isolation', () => {
  it.each(['actor', 'core', 'profile', 'target', 'stage', 'dispose'] as const)('discards a completed evaluation after %s invalidation even if the API ignores abort', async transition => {
    const reply = deferred<AssessmentData>(), started = deferred<void>()
    let signal: AbortSignal | undefined
    const priv = eligibilityApi({ evaluate: vi.fn(async (_input, pending) => { signal = pending; started.resolve(); return reply.promise }) })
    const w = await ready({ eligibilityApi: priv }); w.setConfirmed(true)
    const waiting = w.evaluateSelected(); await started.promise
    if (transition === 'actor') w.setAccess(otherActor, true)
    else if (transition === 'core') w.setAccess(actor, false)
    else if (transition === 'profile') await w.setProfile(version({ version: 2, version_id: nextVersionId }), 2)
    else if (transition === 'target') w.selectOffering(offering())
    else if (transition === 'stage') w.setStage('enrollment')
    else w.dispose()
    expect(signal?.aborted).toBe(true)
    reply.resolve(assessment()); await waiting
    expect(w.state.result).toBeNull(); expect(w.state.history).toBeNull()
    expect(w.state.confirmed).toBe(false); expect(w.state.privateBusy).toBe(false)
  })

  it.each(['actor', 'core', 'dispose'] as const)('discards a late successful historical GET after %s changes', async transition => {
    const reply = deferred<AssessmentData>(), priv = eligibilityApi({ get: vi.fn(() => reply.promise) })
    const w = await ready({ eligibilityApi: priv }), waiting = w.readAssessment(id(200))
    expect(priv.get).toHaveBeenCalledTimes(1)
    if (transition === 'actor') w.setAccess(otherActor, true)
    else if (transition === 'core') w.setAccess(actor, false)
    else w.dispose()
    reply.resolve(assessment()); await waiting
    expect(w.state.history).toBeNull(); expect(w.state.result).toBeNull(); expect(w.state.assessmentId).toBe('')
  })

  it('freezes the explicitly selected profile before asynchronous hash validation', async () => {
    const profile = version(), w = workspace(); w.setAccess(actor, true)
    const loading = w.setProfile(profile, 1)
    profile.profile.assessments.math!.achieved.value = '100'
    await loading
    expect(w.state.profile?.profile.assessments.math!.achieved.value).toBe('0')
    expect(w.state.profile?.profile_sha256).not.toBe(hash(profile.profile))
  })

  it('discards a late quote when the exact target changes, without creating a private error', async () => {
    const reply = deferred<ReturnType<typeof evidence>>(), pub = catalogApi({ evidence: vi.fn(() => reply.promise) })
    const w = await ready({ catalogApi: pub }), loading = w.openEvidence(id(104))
    expect(pub.evidence).toHaveBeenCalledWith(id(104), offering().release_id, expect.any(AbortSignal))
    w.selectOffering(offering()); reply.resolve(evidence()); await loading
    expect(w.state.evidence).toBeNull(); expect(w.state.privateError).toBeNull()
  })

  it('does not allow a policy or historical evidence ID absent from the selected public members to invoke the transport', async () => {
    const pub = catalogApi(), w = await ready({ catalogApi: pub })
    await w.openEvidence(id(999)); expect(pub.evidence).not.toHaveBeenCalled()
    expect(w.state.evidence).toBeNull()
  })
})

describe('T29 exact public targets and independent history', () => {
  it('compares at most four exact identities across pages, preserving distinct versions of the same offering', async () => {
    const one = offering(), two = { ...clone(one), version: 2 }, three = offering(3), four = offering(4), five = offering(5)
    const pub = catalogApi({ offerings: vi.fn(async query => query.cursor ? page([three, four, five], 3) : page([one, two], 3, 'next-page')) })
    const w = workspace({ catalogApi: pub }); w.setFilters({ entry_year: 2027, limit: 3 }); await w.search()
    w.toggleCompare(one); w.toggleCompare(two); await w.nextPage(); w.toggleCompare(three); w.toggleCompare(four); w.toggleCompare(five)
    expect(w.compareItems()).toHaveLength(4)
    expect(w.compareItems().slice(0, 2).map(item => [item.id, item.version])).toEqual([[one.id, 1], [one.id, 2]])
    expect(w.compareItems().map(item => item.program_name)).toEqual(Array(4).fill('DEMO_Program'))
    expect(w.state.publicMessage).toContain('最多比较 4')
  })

  it('a watermark conflict clears the old page, exact target, comparisons, quote, and positive confirmation', async () => {
    const pub = catalogApi({ offerings: vi.fn(async query => { if (query.cursor) throw new CatalogError(409); return page([offering()], 20, 'next-page') }) })
    const w = await ready({ catalogApi: pub }); w.toggleCompare(offering()); await w.openEvidence(id(104)); w.setConfirmed(true)
    await w.nextPage()
    expect(w.state.publicError).toBe(409); expect(w.state.page).toBeNull(); expect(w.selectedOffering()).toBeNull()
    expect(w.compareItems()).toEqual([]); expect(w.state.evidence).toBeNull(); expect(w.state.confirmed).toBe(false)
  })

  it('keeps current and historical results separate while reporting original conclusion plus current withdrawal', async () => {
    const original = fixtureOutcome('eligible'), historic = assessment({ current_validity: 'withdrawn' })
    const priv = eligibilityApi({ evaluate: vi.fn(async () => original), get: vi.fn(async () => historic) })
    const w = await ready({ eligibilityApi: priv }); w.setConfirmed(true); await w.evaluateSelected(); await w.readAssessment(id(200))
    expect(w.state.result?.eligibility.status).toBe('eligible')
    expect(w.state.history?.eligibility.status).toBe('unknown'); expect(w.state.history?.current_validity).toBe('withdrawn')
    expect(w.state.history?.assessment_at).toBe(historic.assessment_at)
    expect(w.state.confirmed).toBe(false); expect(w.state.replayConfirmed).toBe(false)
  })
})
