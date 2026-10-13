import { describe, expect, it, vi } from 'vitest'
import { checkFields, useReview } from '../src/features/admin/reviews/useReview'
import { ReviewWorkspaceError } from '../src/features/admin/reviews/client'
import { actor, otherActor, deferred, workspaceApi, factId, detail, fact, classification, decision, caseId, decisionId } from './reviewReleaseFixtures'

async function loaded(api = workspaceApi()) { const model = useReview(api); model.setActor(otherActor); model.state.factId = factId; await model.load(); return { api, model } }
function approve(model: ReturnType<typeof useReview>) { for (const field of checkFields) model.state.checks[field] = 'accepted'; model.state.action = 'approve'; model.state.confirmed = true }

describe('independent human review state', () => {
  it('starts with ten empty checks and requires an independent confirmation', async () => {
    const { api, model } = await loaded(); expect(Object.values(model.state.checks)).toEqual(Array(10).fill('')); expect(model.canDecide()).toBe(false)
    approve(model); model.state.confirmed = false; await model.decide(); expect(api.review).not.toHaveBeenCalled()
    model.state.confirmed = true; await model.decide(); expect(model.state.decision?.current_approved).toBe(true); expect(model.state.message).toContain('不代表已公开发布')
    const body = vi.mocked(api.review).mock.calls[0][0]; expect(body.expected_case_revision).toBe(0); expect(body.expected_fact_version).toBe(1); expect(body.checks).toHaveLength(10)
    expect(body.conflict_resolutions).toEqual([]); expect(body.return_reason).toBeNull(); expect(model.state.detail).toBeNull()
  })
  it.each(['MISSING_EVIDENCE', 'INCOMPLETE_SCOPE', 'UNRESOLVED_DATE', 'BASE_DRAFT', 'SELF_REVIEW_FORBIDDEN'] as const)('does not approve diagnostic gap %s', async gap => {
    const { api, model } = await loaded(workspaceApi({ detail: vi.fn(async () => detail({ gaps: [gap] })) })); approve(model)
    await model.decide(); expect(model.canDecide()).toBe(false); expect(api.review).not.toHaveBeenCalled()
  })
  it('requires every exact adjacent conflict reason without automatically choosing a value', async () => {
    const conflict = '1df55d96-280f-4496-be21-86b477b054fb'
    const conflictDetail = detail({ fact: fact({ state: 'conflicted', conflicting_ids: [conflict] }), gaps: ['CURRENT_CONFLICTS'], conflicts: [{ fact_id: conflict, version: 1, value_kind: 'decimal', value_text: '650', normalized_value: '650', unit_text: 'points', footnote_state: 'none', footnote_text: null, classification: classification(), evidence_id: null, state: 'review_required' }] })
    const { api, model } = await loaded(workspaceApi({ detail: vi.fn(async () => conflictDetail) })); approve(model)
    expect(model.state.resolutions[conflict]).toBe(''); expect(model.canDecide()).toBe(false)
    model.state.resolutions[conflict] = 'WRONG_CONTEXT'; await model.decide()
    expect(vi.mocked(api.review).mock.calls[0][0].conflict_resolutions).toEqual([{ fact_id: conflict, reason_code: 'WRONG_CONTEXT' }])
  })
  it('can explicitly return an incomplete candidate with a finite reason and no conflict resolution', async () => {
    const api = workspaceApi({ detail: vi.fn(async () => detail({ evidence: null, gaps: ['MISSING_EVIDENCE'] })), review: vi.fn(async () => decision({ action: 'return', return_reason: 'MISSING_EVIDENCE', current_approved: false })) })
    const { model } = await loaded(api); approve(model); model.state.action = 'return'; expect(model.canDecide()).toBe(false)
    model.state.returnReason = 'MISSING_EVIDENCE'; await model.decide()
    expect(vi.mocked(api.review).mock.calls[0][0]).toMatchObject({ action: 'return', return_reason: 'MISSING_EVIDENCE', conflict_resolutions: [] })
    expect(model.state.decision?.current_approved).toBe(false); expect(model.state.message).toContain('当前批准已失效')
  })
  it('does not treat retained historical selection as a current approval', async () => {
    const value = detail({ case: { case_id: caseId, logical_key_hash: 'd'.repeat(64), case_revision: 3, chosen_fact_id: factId, current_decision_id: decisionId, current_approved: false, is_synthetic: true } })
    const { model } = await loaded(workspaceApi({ detail: vi.fn(async () => value) })); expect(model.state.detail?.case.current_approved).toBe(false)
    expect(model.state.action).toBe(''); expect(model.state.confirmed).toBe(false)
  })
  it('clears stale CAS details and all confirmations after 409', async () => {
    const { model } = await loaded(workspaceApi({ review: vi.fn(async () => { throw new ReviewWorkspaceError(409) }) })); approve(model); await model.decide()
    expect(model.state.detail).toBeNull(); expect(model.state.decision).toBeNull(); expect(model.state.confirmed).toBe(false)
    expect(Object.values(model.state.checks)).toEqual(Array(10).fill('')); expect(model.state.message).toContain('重新读取')
  })
  it('discards a late detail from a previous actor', async () => {
    const pending = deferred<ReturnType<typeof detail>>(), model = useReview(workspaceApi({ detail: vi.fn(() => pending.promise) }))
    model.setActor(actor); model.state.factId = factId; const call = model.load(); model.setActor(otherActor); pending.resolve(detail()); await call
    expect(model.state.detail).toBeNull(); expect(model.state.factId).toBe('')
  })
  it('requires accepted statistics/date contexts when applicable', async () => {
    const { model } = await loaded(workspaceApi({ detail: vi.fn(async () => detail({ fact: fact({ fact_type: 'statistic', classification: classification({ claim_kind: 'historical_statistic' }) }) })) }))
    approve(model); model.state.checks.statistics_context = 'not_applicable'; expect(model.canDecide()).toBe(false)
    model.state.checks.statistics_context = 'accepted'; expect(model.canDecide()).toBe(true)
  })
})
