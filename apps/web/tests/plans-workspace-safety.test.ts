// T33 independent tests. Deferred transports deliberately ignore cancellation;
// generation and exact bindings must protect private state after successful I/O.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPlanApi, PlanError, type PlanApi, type ExecutionData } from '../src/features/plans/client'
import { usePlansWorkspace } from '../src/features/plans/usePlans'
import { validExecution } from '../src/features/plans/validation'
import { emptyLocal, fromExecution, workspaceInput } from '../src/features/plans/form'
import { csrf, id } from './catalogFixtures'
import { actor, otherActor, version, clone, hash, deferred, assessment, plan, proposal, confirmed, completed,
  planApi, response, rehash, workspaceRequest } from './plansFixtures'
import { nextVersionId } from './profilesFixtures'

const owned: ReturnType<typeof usePlansWorkspace>[] = []
afterEach(() => { for (const w of owned.splice(0)) w.dispose(); vi.restoreAllMocks() })
function workspace(api = planApi(), expired = vi.fn()) {
  const w = usePlansWorkspace({ api }, expired); owned.push(w); return w
}
async function ready(current = plan(), api = planApi({ get: vi.fn(async () => clone(current)) })) {
  vi.mocked(api.get).mockResolvedValueOnce(clone(current))
  const w = workspace(api)
  w.setAccess(actor, true); await w.setProfile(version(), 1); await w.refreshContext(); await w.loadPlan(current.plan_id)
  expect(w.state.current).toEqual(current); expect(w.canWrite()).toBe(true)
  return { w, api }
}
function cleared(w: ReturnType<typeof workspace>) {
  expect(w.state.current).toBeNull(); expect(w.state.history).toBeNull(); expect(w.state.context).toBeNull()
  expect(w.state.page).toBeNull(); expect(w.state.targets).toEqual([]); expect(w.state.selectedIds).toEqual([])
  expect(w.state.local).toEqual(emptyLocal()); expect(w.state.profile).toBeNull(); expect(w.state.retryKind).toBeNull()
  expect(w.state.createConfirmed).toBe(false); expect(w.state.confirmChecked).toBe(false)
  expect(w.state.deadlineAcknowledged).toBe(false); expect(w.state.taskConfirmations).toEqual({}); expect(w.canWrite()).toBe(false)
}

describe('T33 independent private transport boundaries', () => {
  it('accepts actual synthetic context in private verified/disabled mode without sending authority fields', async () => {
    const data = { schema_version: 'v2.t32', is_synthetic: true, reason: 'ready', can_create: true, can_read: true,
      can_edit: true, can_confirm: true, can_complete: true }
    const fetcher = vi.fn(async (_url: RequestInfo | URL, _request?: RequestInit) => new Response(JSON.stringify({ data, meta: {
      api_version: 'v2', request_id: 'e'.repeat(32), data_as_of: null, profile_version_id: null,
      release_id: null, ruleset_version: null, profile_mode: null, data_mode: 'verified', model_mode: 'disabled',
    } }), { status: 200, headers: { 'X-Request-ID': 'e'.repeat(32), 'Cache-Control': 'no-store' } }))
    expect(await createPlanApi('/api', fetcher).context()).toEqual(data)
    const [url, request] = fetcher.mock.calls[0]!
    expect(url).toBe('/api/v2/plans/context')
    expect(request).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error' })
    expect(request).not.toHaveProperty('body')
    expect(request?.headers).not.toHaveProperty('Idempotency-Key')
  })

  it.each([401, 403, 404, 409, 422, 503])('never consumes a private error body for HTTP %s', async status => {
    const text = vi.fn(async () => 'DEMO_PRIVATE_SENTINEL'), json = vi.fn(async () => ({ owner_user_id: id(999) }))
    const fetcher = vi.fn(async () => ({ status, text, json }) as unknown as Response)
    const error = await createPlanApi('/api', fetcher).get(id(300)).catch(e => e)
    expect(error).toBeInstanceOf(PlanError); expect(error.status).toBe(status)
    expect(String(error)).not.toContain('DEMO_PRIVATE_SENTINEL')
    expect(text).not.toHaveBeenCalled(); expect(json).not.toHaveBeenCalled()
  })

  it.each(['GET', 'POST'] as const)('classifies malformed successful %s as bad200 rather than uncertain transport', async method => {
    const fetcher = vi.fn(async (url: RequestInfo | URL) => String(url).endsWith('/csrf') ? csrf() :
      new Response('{DEMO_PRIVATE_SENTINEL', { status: 200 }))
    const api = createPlanApi('/api', fetcher)
    const pending = method === 'GET' ? api.get(id(300)) : api.create({ assessment_ids: [id(200)], confirmed: true })
    await expect(pending).rejects.toMatchObject({ status: 200 })
  })

  it.each(['https://outside.invalid', '//outside.invalid', '/api/../outside'])('rejects a foreign or traversing prefix %s before I/O', prefix => {
    const fetcher = vi.fn()
    expect(() => createPlanApi(prefix, fetcher)).toThrow(PlanError)
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('rejects forged owner, unconfirmed writes and invalid path/query before obtaining CSRF', async () => {
    const fetcher = vi.fn(), api = createPlanApi('/api', fetcher)
    await expect(api.create({ assessment_ids: [id(200)], confirmed: true, owner_user_id: id(999) } as never)).rejects.toMatchObject({ status: 422 })
    await expect(api.create({ assessment_ids: [id(200)], confirmed: false } as never)).rejects.toMatchObject({ status: 422 })
    expect(() => api.get('../private')).toThrow(PlanError)
    expect(() => api.list({ limit: 0 })).toThrow(PlanError)
    expect(() => api.list({ owner: id(999) } as never)).toThrow(PlanError)
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('freezes confirmation before awaiting CSRF and sends the opaque key only in its header', async () => {
    const current = proposal(), token = deferred<Response>(), started = deferred<void>()
    const fetcher = vi.fn(async (url: RequestInfo | URL, _request?: RequestInit) => {
      if (String(url).endsWith('/csrf')) { started.resolve(); return token.promise }
      return response({ execution: confirmed(current), replayed: false, confirmed_state_version: 3 })
    })
    const input = { expected_version: 2, expected_draft_sha256: current.proposal.effective_draft.draft_sha256,
      expected_schedule_sha256: current.proposal.schedule!.schedule_sha256, confirmed: true as const, acknowledge_unverified_deadlines: true as const }
    const frozen = clone(input), pending = createPlanApi('/api', fetcher).confirm(current.plan_id, input, 'DEMO_CONFIRM_ORIGINAL')
    await started.promise; input.expected_version = 999; input.expected_draft_sha256 = 'f'.repeat(64)
    token.resolve(csrf()); await pending
    const [url, request] = fetcher.mock.calls[1]!
    expect(url).toBe('/api/v2/plans/'+current.plan_id+'/confirm')
    expect(JSON.parse(request!.body as string)).toEqual(frozen)
    expect(request!.headers).toMatchObject({ 'Idempotency-Key': 'DEMO_CONFIRM_ORIGINAL' })
    expect(JSON.parse(request!.body as string)).not.toHaveProperty('key')
    expect(JSON.parse(request!.body as string)).not.toHaveProperty('owner_user_id')
  })
})

describe('T33 independent legal projections and forged successful responses', () => {
  it('first proves all shared synthetic execution fixtures legal before isolated attacks', async () => {
    for (const value of [plan(), proposal(), confirmed(), completed()]) {
      expect(await validExecution(value)).toBe(true)
      expect(await createPlanApi('/api', vi.fn(async () => response(value))).get(value.plan_id)).toEqual(value)
    }
  })

  it.each([
    'missing_allocations', 'wrong_task_total', 'wrong_week_total', 'false_ready', 'outside_horizon', 'outside_slot',
    'wrong_estimate', 'duplicate_overlap', 'wrong_week_capacity', 'wrong_task_bounds', 'bad_display_week',
  ] as const)('rejects self-consistently rehashed false-ready schedule: %s', async attack => {
    const good = proposal(); expect(await validExecution(good)).toBe(true)
    const bad = clone(good), s = bad.proposal.schedule!, task = s.tasks[0]!, allocation = s.allocations[0]!
    if (attack === 'missing_allocations') s.allocations = []
    else if (attack === 'wrong_task_total') { task.assigned_microseconds = 0; task.remaining_microseconds = task.estimated_microseconds! }
    else if (attack === 'wrong_week_total') s.weeks[0]!.assigned_microseconds = 0
    else if (attack === 'false_ready') { task.status = 'blocked'; task.start_at = null; task.end_at = null }
    else if (attack === 'outside_horizon') s.horizon_end = bad.proposal.schedule_configuration!.horizon_end = '2026-10-05T01:00:00.123456Z'
    else if (attack === 'outside_slot') bad.proposal.schedule_configuration!.slots[0]!.end_at = '2026-10-05T01:00:00.123456Z'
    else if (attack === 'wrong_estimate') { task.estimated_hours = '1'; task.estimated_microseconds = 3600000000; task.assigned_microseconds = 3600000000; task.remaining_microseconds = 0; allocation.duration_microseconds = 3600000000; allocation.end_at = task.end_at = '2026-10-05T01:00:00.123456Z'; s.weeks[0]!.assigned_microseconds = 3600000000 }
    else if (attack === 'duplicate_overlap') s.allocations.push(clone(allocation))
    else if (attack === 'wrong_week_capacity') s.weeks[0]!.capacity_microseconds = 144000000000
    else if (attack === 'wrong_task_bounds') task.end_at = '2026-10-05T03:00:00.123456Z'
    else if (attack === 'bad_display_week') { allocation.week_start = '2026-09-28'; s.weeks[0]!.week_start = '2026-09-28' }
    rehash(bad)
    expect(bad.proposal.schedule!.schedule_sha256).toBe(hash(Object.fromEntries(Object.entries(bad.proposal.schedule!).filter(([key]) => key !== 'schedule_sha256'))))
    await expect(createPlanApi('/api', vi.fn(async () => response(bad))).get(bad.plan_id)).rejects.toMatchObject({ status: 200 })
  })

  it.each(['confirmed_at_expiry', 'completed_at_expiry', 'milestone_before_confirmation'] as const)('rejects a valid-looking projection at its expired or preconfirmation boundary: %s', async attack => {
    let bad: ExecutionData
    if (attack === 'milestone_before_confirmation') {
      const input = workspaceRequest(); input.estimate_overrides[0]!.estimated_hours = '0'
      bad = confirmed(proposal(input)); bad.confirmation!.confirmed_at = '2026-10-05T00:00:00.123457Z'
    } else {
      bad = completed()
      if (attack === 'confirmed_at_expiry') bad.confirmation!.confirmed_at = bad.expires_at
      else bad.completed_tasks[0]!.completed_at = bad.expires_at
    }
    await expect(createPlanApi('/api', vi.fn(async () => response(bad))).get(bad.plan_id)).rejects.toMatchObject({ status: 200 })
  })

  it.each(['demo', 'mock', 'wrong_profile', 'wrong_request'] as const)('rejects successful private metadata %s without claiming synthetic means demo', async attack => {
    const current = proposal(), meta = attack === 'demo' ? { data_mode: 'demo' } : attack === 'mock' ? { model_mode: 'mock' } :
      attack === 'wrong_profile' ? { profile_version_id: nextVersionId } : { request_id: 'a'.repeat(32) }
    await expect(createPlanApi('/api', vi.fn(async () => response(current, meta))).get(current.plan_id)).rejects.toMatchObject({ status: 200 })
  })
})

describe('T33 independent source selection, exact CAS and explicit retry', () => {
  it('allows an explicit existing-plan read without a selected profile but blocks every write', async () => {
    const api = planApi(), w = workspace(api); w.setAccess(actor, true); await w.refreshContext(); await w.loadPlan(plan().plan_id)
    expect(w.state.current).toEqual(plan()); expect(w.canRead()).toBe(true); expect(w.canWrite()).toBe(false)
    w.state.createConfirmed = true; w.state.confirmChecked = true; w.state.deadlineAcknowledged = true
    await w.createPlan(); await w.saveWorkspace(); await w.confirmPlan(); await w.completeTask(plan().proposal.effective_draft.tasks[0]!.task_key)
    expect(api.create).not.toHaveBeenCalled(); expect(api.workspace).not.toHaveBeenCalled(); expect(api.confirm).not.toHaveBeenCalled(); expect(api.complete).not.toHaveBeenCalled()
  })

  it.each(['withdrawn', 'replaced', 'needs_review'] as const)('retains explicitly selected %s assessment only as its verification source', async validity => {
    const source = assessment({ current_validity: validity }), value = plan()
    value.proposal.effective_draft.assessment_refs[0]!.current_validity = validity
    value.proposal.effective_draft.tasks[0]!.action_code = 'VERIFY_HISTORY'
    const t = value.proposal.effective_draft.tasks[0]!
    t.task_key = hash(Object.fromEntries(['kind','action_code','title','acceptance_criteria','assessment_key','basis','unit','scale','work_scope_sha256'].map(key => [key, t[key as keyof typeof t]])))
    rehash(value)
    const api = planApi({ create: vi.fn(async () => clone(value)) }), { w } = await ready(plan(), api)
    await w.setTargets([source]); w.selectAssessment(source.assessment_id, true); w.state.createConfirmed = true; await w.createPlan()
    expect(w.state.current?.proposal.effective_draft.assessment_refs[0]!.current_validity).toBe(validity)
    expect(w.state.current?.proposal.effective_draft.tasks[0]!.action_code).toBe('VERIFY_HISTORY')
    expect(api.create).toHaveBeenCalledWith({ assessment_ids: [source.assessment_id], confirmed: true, study_goals: [], estimate_overrides: [] }, expect.any(AbortSignal))
  })

  it('rejects an independently valid creation bound to the wrong profile root even with the same version and hash', async () => {
    const bad = plan(); bad.proposal.effective_draft.profile_id = id(799); rehash(bad)
    expect(await validExecution(bad)).toBe(true)
    const api = planApi({ create: vi.fn(async () => bad) }), { w } = await ready(plan(), api)
    await w.setTargets([assessment()]); w.selectAssessment(assessment().assessment_id, true); w.state.createConfirmed = true; await w.createPlan()
    expect(w.state.error).toBe(200); cleared(w)
  })

  it('keeps historical projections out of current CAS and leaves zero-hour completion explicit', async () => {
    const input = workspaceRequest(); input.estimate_overrides[0]!.estimated_hours = '0'
    const current = confirmed(proposal(input)), api = planApi({ get: vi.fn(async () => clone(current)), history: vi.fn(async () => plan()) })
    const { w } = await ready(current, api); await w.readHistory(1)
    expect(w.state.history?.state_version).toBe(1); expect(w.state.current?.state_version).toBe(3)
    const key = current.proposal.effective_draft.tasks[0]!.task_key
    expect(w.canComplete(key)).toBe(true); await w.completeTask(key); expect(api.complete).not.toHaveBeenCalled()
    w.state.taskConfirmations[key] = true; vi.mocked(api.complete).mockResolvedValueOnce({ execution: completed(current), replayed: false })
    await w.completeTask(key)
    expect(api.complete).toHaveBeenCalledWith(current.plan_id, key, { expected_version: 3, confirmed: true }, expect.any(AbortSignal))
  })

  it('preserves exact local parameters on409, requires explicit GET and a new confirmation without silently shifting UTC', async () => {
    const current = proposal(), newer = clone(current); newer.state_version = newer.proposal.state_version = 3
    const api = planApi({ workspace: vi.fn(async () => { throw new PlanError(409) }), get: vi.fn(async () => clone(current)) }), { w } = await ready(current, api)
    w.state.local.estimates[current.proposal.effective_draft.tasks[0]!.task_key] = '0'
    w.state.local.slots[0]!.start = '2026-10-05T00:00:00.000001Z'
    w.state.local.horizonStart = w.state.local.slots[0]!.start
    w.changeLocal(); w.state.local.availabilityConfirmed = w.state.local.restExcluded = true
    const kept = clone(w.state.local); await w.saveWorkspace()
    expect(w.state.error).toBe(409); expect(w.state.conflict).toBe(true); expect(w.state.current).toBeNull()
    expect(w.state.local.estimates).toEqual(kept.estimates); expect(w.state.local.slots).toEqual(kept.slots)
    expect(w.state.confirmChecked).toBe(false); expect(w.state.deadlineAcknowledged).toBe(false)
    await w.saveWorkspace(); await w.confirmPlan(); expect(api.workspace).toHaveBeenCalledTimes(1); expect(api.confirm).not.toHaveBeenCalled()
    vi.mocked(api.get).mockResolvedValueOnce(newer); await w.reloadCurrent()
    expect(w.state.current?.state_version).toBe(3); expect(w.state.local.slots).toEqual(kept.slots); expect(w.state.dirty).toBe(true)
    expect(w.canConfirm()).toBe(false); expect(w.state.local.availabilityConfirmed).toBe(false)
  })

  it('retries uncertain confirmation with the original immutable payload and key while accepting current progress', async () => {
    const current = proposal(), api = planApi({ confirm: vi.fn(async () => { throw new PlanError(0) }) }), { w } = await ready(current, api)
    w.state.confirmChecked = w.state.deadlineAcknowledged = true; await w.confirmPlan()
    expect(w.state.retryKind).toBe('confirm'); expect(api.confirm).toHaveBeenCalledTimes(1)
    const original = clone(vi.mocked(api.confirm).mock.calls[0]!.slice(0, 3))
    w.state.local.weeklyHours = '40'; w.state.confirmChecked = w.state.deadlineAcknowledged = true; await w.confirmPlan()
    expect(api.confirm).toHaveBeenCalledTimes(1)
    vi.mocked(api.confirm).mockResolvedValueOnce({ execution: completed(confirmed(current)), replayed: true, confirmed_state_version: 3 })
    await w.retryConfirm()
    expect(vi.mocked(api.confirm).mock.calls[1]!.slice(0, 3)).toEqual(original)
    expect(w.state.current?.state_version).toBe(4); expect(w.state.current?.completed_tasks).toHaveLength(1); expect(w.state.retryKind).toBeNull()
  })

  it('retries uncertain completion with original CAS instead of rewriting it from a late newer state', async () => {
    const current = confirmed(), key = current.proposal.effective_draft.tasks[0]!.task_key
    const api = planApi({ complete: vi.fn(async () => { throw new PlanError(0) }) }), { w } = await ready(current, api)
    w.state.taskConfirmations[key] = true; await w.completeTask(key)
    expect(w.state.retryKind).toBe('complete')
    const original = clone(vi.mocked(api.complete).mock.calls[0]!.slice(0, 3))
    vi.mocked(api.complete).mockResolvedValueOnce({ execution: completed(current), replayed: true }); await w.retryComplete()
    expect(vi.mocked(api.complete).mock.calls[1]!.slice(0, 3)).toEqual(original)
    expect(original[2]).toEqual({ expected_version: 3, confirmed: true }); expect(w.state.current?.state_version).toBe(4)
  })

  it.each([401, 403, 404, 503, 200])('erases all private state after %s and only401 invalidates the outer session', async status => {
    const current = proposal(), expired = vi.fn(), api = planApi({ get: vi.fn(async () => clone(current)) }), w = workspace(api, expired)
    w.setAccess(actor, true); await w.setProfile(version(), 1); await w.refreshContext(); await w.loadPlan(current.plan_id)
    await w.readHistory(1); await w.setTargets([assessment()]); w.selectAssessment(assessment().assessment_id, true)
    w.state.confirmChecked = w.state.deadlineAcknowledged = true
    vi.mocked(api.get).mockRejectedValueOnce(new PlanError(status)); await w.loadPlan(current.plan_id)
    cleared(w); expect(w.state.error).toBe(status); expect(expired).toHaveBeenCalledTimes(status === 401 ? 1 : 0)
  })
})

describe('T33 independent late200 isolation across private generation changes', () => {
  const transitions = ['actor', 'same_account_session', 'core', 'logout', 'profile', 'epoch', 'dispose'] as const
  for (const operation of ['get', 'create', 'confirm', 'complete'] as const) {
    it.each(transitions)('discards successful '+operation+' after %s even when transport ignores abort', async transition => {
      const current = operation === 'confirm' ? proposal() : operation === 'complete' ? confirmed() : plan()
      const api = planApi(), { w } = await ready(current, api)
      const reply = deferred<unknown>(), started = deferred<void>(); let signal: AbortSignal | undefined
      const pending = vi.fn(async (...args: unknown[]) => { signal = args[args.length - 1] as AbortSignal; started.resolve(); return reply.promise })
      if (operation === 'get') api.get = pending as PlanApi['get']
      else if (operation === 'create') { api.create = pending as PlanApi['create']; await w.setTargets([assessment()]); w.selectAssessment(assessment().assessment_id, true); w.state.createConfirmed = true }
      else if (operation === 'confirm') { api.confirm = pending as PlanApi['confirm']; w.state.confirmChecked = w.state.deadlineAcknowledged = true }
      else { api.complete = pending as PlanApi['complete']; w.state.taskConfirmations[current.proposal.effective_draft.tasks[0]!.task_key] = true }
      const waiting = operation === 'get' ? w.loadPlan(current.plan_id) : operation === 'create' ? w.createPlan() : operation === 'confirm' ? w.confirmPlan() : w.completeTask(current.proposal.effective_draft.tasks[0]!.task_key)
      await started.promise
      if (transition === 'actor') w.setAccess(otherActor, true)
      else if (transition === 'same_account_session') w.setAccess({ ...actor, expires_at: '2030-10-03T12:00:00Z' }, true)
      else if (transition === 'core') w.setAccess(actor, false)
      else if (transition === 'logout') w.setAccess(null, false)
      else if (transition === 'profile') await w.setProfile(version({ version: 2, version_id: nextVersionId }), 2)
      else if (transition === 'epoch') await w.setProfile(null, 2)
      else w.dispose()
      expect(signal?.aborted).toBe(true)
      if (operation === 'confirm') reply.resolve({ execution: confirmed(current), replayed: false, confirmed_state_version: 3 })
      else if (operation === 'complete') reply.resolve({ execution: completed(current), replayed: false })
      else reply.resolve(plan())
      await waiting
      if (transition === 'profile') { expect(w.state.profile?.version_id).toBe(nextVersionId); expect(w.state.current).toBeNull(); expect(w.state.retryKind).toBeNull(); expect(w.state.local).toEqual(emptyLocal()) }
      else cleared(w)
      await w.retryConfirm(); await w.retryComplete(); expect(pending).toHaveBeenCalledTimes(1)
    })
  }

  it.each(['actor', 'core', 'epoch'] as const)('does not restore historical content after %s during a real successful pending GET', async transition => {
    const reply = deferred<ExecutionData>(), started = deferred<void>(), api = planApi(), { w } = await ready(proposal(), api)
    let signal: AbortSignal | undefined
    api.history = vi.fn(async (_id, _version, pending) => { signal = pending; started.resolve(); return reply.promise })
    const waiting = w.readHistory(1); await started.promise
    if (transition === 'actor') w.setAccess(otherActor, true)
    else if (transition === 'core') w.setAccess(actor, false)
    else await w.setProfile(null, 2)
    expect(signal?.aborted).toBe(true); reply.resolve(plan()); await waiting; cleared(w)
  })
})

describe('T33 independent local precision and unknown capacity', () => {
  it('preserves zero distinct from null and does not discard UTC microseconds on serialization or load', () => {
    const current = proposal(), local = fromExecution(current), key = current.proposal.effective_draft.tasks[0]!.task_key
    local.availabilityConfirmed = local.restExcluded = true; local.estimates[key] = '0'; local.weeklyHours = '0'
    local.slots[0]!.start = '2026-10-05T00:00:00.000001+00:00'
    local.horizonStart = local.slots[0]!.start
    const request = workspaceInput(local, current)
    expect(request.estimate_overrides[0]!.estimated_hours).toBe('0'); expect(request.schedule?.weekly_hours).toBe('0')
    expect(request.schedule?.slots[0]!.start_at).toBe(local.slots[0]!.start)
    local.estimates[key] = ''; local.weeklyHours = ''
    const unknown = workspaceInput(local, current)
    expect(unknown.estimate_overrides[0]!.estimated_hours).toBeNull(); expect(unknown.schedule?.weekly_hours).toBeNull()
    expect(fromExecution(current).slots[0]!.start).toContain('.123456Z')
  })
})
