import { reactive } from 'vue'
import { uuid } from '../client'
import { ReviewWorkspaceError, strictInteger, type ReviewWorkspaceApi, type SessionData, type ReviewCandidatesData,
  type ReviewDetailData, type ReviewDecisionData, type AdminReviewInput } from './client'
export const checkFields = ['original_value', 'claim_kind', 'unit', 'period', 'scope', 'evidence_location', 'missingness', 'footnote', 'statistics_context', 'date_context'] as const
export const returnReasons = ['INVALID_VALUE', 'MISSING_EVIDENCE', 'SCOPE_MISMATCH', 'UNIT_MISMATCH', 'PERIOD_UNCLEAR', 'MISSING_CONTEXT', 'FOOTNOTE_UNRESOLVED', 'SOURCE_UNAVAILABLE', 'CONFLICT_UNRESOLVED', 'UNSUPPORTED_LITERAL'] as const
export const conflictReasons = ['SELECTED_SUPPORTED', 'INCORRECT_VALUE', 'WRONG_CONTEXT', 'DUPLICATE_OR_EQUIVALENT'] as const
type CheckStatus = AdminReviewInput['checks'][number]['status'] | ''
const emptyChecks = () => Object.fromEntries(checkFields.map(field => [field, ''])) as Record<typeof checkFields[number], CheckStatus>
export function useReview(api: ReviewWorkspaceApi, expired: () => void = () => {}) {
  const state = reactive({ datasetId: '', year: '' as string | number, page: null as ReviewCandidatesData | null, factId: '',
    detail: null as ReviewDetailData | null, checks: emptyChecks(), resolutions: {} as Record<string, typeof conflictReasons[number] | ''>,
    action: '' as 'approve' | 'return' | '', returnReason: '' as typeof returnReasons[number] | '', confirmed: false,
    decision: null as ReviewDecisionData | null, busy: '', message: '', error: false })
  let actor: SessionData | null = null, generation = 0, pending: AbortController | undefined
  function invalidate() { generation++; pending?.abort(); state.busy = ''; state.message = ''; state.error = false }
  function clearForm() { state.checks = emptyChecks(); state.resolutions = {}; state.action = ''; state.returnReason = ''; state.confirmed = false; state.decision = null }
  function reset() { invalidate(); state.datasetId = ''; state.year = ''; state.page = null; state.factId = ''; state.detail = null; clearForm() }
  function setActor(value: SessionData | null) { reset(); actor = value }
  function changed() { invalidate(); state.confirmed = false; state.decision = null }
  function scopeChanged() { invalidate(); state.page = null; state.detail = null; state.factId = ''; clearForm() }
  function factChanged() { invalidate(); state.detail = null; clearForm() }
  async function run<T>(name: string, call: (signal: AbortSignal) => Promise<T>, apply: (result: T) => void) {
    if (!actor || state.busy) return
    const current = ++generation; pending?.abort(); pending = new AbortController(); state.busy = name; state.message = ''; state.error = false
    try { const result = await call(pending.signal); if (current === generation) apply(result) }
    catch (error) { if (current === generation) {
      const message = error instanceof ReviewWorkspaceError ? error.message : '审核结果未确认。'
      state.confirmed = false; state.decision = null; state.detail = null; clearForm()
      if (error instanceof ReviewWorkspaceError && [401, 403, 503].includes(error.status)) { reset(); if (error.status === 401) expired() }
      state.message = message; state.error = true
    } }
    finally { if (current === generation) state.busy = '' }
  }
  async function search(next = false) {
    const year = strictInteger(state.year, 1, 9999), dataset = state.datasetId, cursor = next ? state.page?.next_cursor ?? undefined : undefined
    if (!uuid(dataset) || year === null || next && !cursor) return
    state.detail = null; clearForm()
    await run('queue', signal => api.candidates(dataset, year, cursor, signal), result => {
      if (result.dataset_id !== dataset || result.entry_year !== year) throw new ReviewWorkspaceError(200)
      state.page = result; state.message = '当前有权候选已返回，未按最高分或最新记录自动选择。'
    })
  }
  async function load() {
    const id = state.factId; if (!uuid(id)) return
    state.detail = null; clearForm()
    await run('detail', signal => api.detail(id, signal), result => {
      if (result.fact.id !== id || result.fact.is_synthetic !== actor?.is_synthetic
        || result.conflicts.map(item => item.fact_id).sort().join() !== [...result.fact.conflicting_ids].sort().join()) throw new ReviewWorkspaceError(200)
      state.detail = result; state.resolutions = Object.fromEntries(result.conflicts.map(item => [item.fact_id, '']))
      state.message = '有限原文与候选已读取。逐项判断由审核者作出，不能由程序默认通过。'
    })
  }
  function choose(id: string) { factChanged(); state.factId = id; return load() }
  function canDecide() {
    if (!actor || state.busy || !state.detail || !state.confirmed || !state.action || checkFields.some(field => !state.checks[field])) return false
    if (state.detail.gaps.includes('SELF_REVIEW_FORBIDDEN')) return false
    if (state.action === 'return') return !!state.returnReason
    if (!state.detail.evidence || state.detail.gaps.some(gap => gap !== 'CURRENT_CONFLICTS')
      || checkFields.slice(0, 8).some(field => state.checks[field] !== 'accepted') || Object.values(state.checks).includes('rejected')
      || state.detail.conflicts.some(item => !state.resolutions[item.fact_id])) return false
    const fact = state.detail.fact
    return (!(fact.fact_type === 'statistic' || fact.classification.claim_kind === 'historical_statistic') || state.checks.statistics_context === 'accepted')
      && (fact.fact_type !== 'date' || state.checks.date_context === 'accepted')
  }
  async function decide() {
    if (!canDecide()) return
    const detail = state.detail!, action = state.action as 'approve' | 'return'
    const input: AdminReviewInput = { fact_id: detail.fact.id, expected_fact_version: 1, expected_case_revision: detail.case.case_revision,
      action, checks: checkFields.map(field => ({ field, status: state.checks[field] as AdminReviewInput['checks'][number]['status'] })),
      conflict_resolutions: action === 'approve' ? detail.conflicts.map(item => ({ fact_id: item.fact_id, reason_code: state.resolutions[item.fact_id] as typeof conflictReasons[number] })) : [],
      return_reason: action === 'return' ? state.returnReason as typeof returnReasons[number] : null, confirmed: true }
    state.confirmed = false; state.decision = null
    await run('decision', signal => api.review(input, signal), result => {
      if (result.fact_id !== detail.fact.id || result.action !== action || result.case_revision !== detail.case.case_revision + 1 || result.is_synthetic !== actor?.is_synthetic) throw new ReviewWorkspaceError(200)
      state.decision = result; state.detail = null; clearForm(); state.decision = result
      state.message = action === 'approve' ? '服务端已提交审核决定；不代表已公开发布。请重新读取当前 case 后使用确切决定和版本。' : '服务端已提交退回决定，当前批准已失效；旧历史仍保留。'
    })
  }
  function dispose() { reset(); actor = null }
  return { state, setActor, dispose, changed, scopeChanged, factChanged, search, load, choose, canDecide, decide }
}
