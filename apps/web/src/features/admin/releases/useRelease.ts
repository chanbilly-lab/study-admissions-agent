import { reactive } from 'vue'
import { uuid } from '../client'
import { ReviewWorkspaceError, strictInteger, type ReviewWorkspaceApi, type SessionData, type AdminPublishInput,
  type CurrentReleaseData, type PublishPrecheckData, type ReleaseData, type AdminWithdrawalInput } from '../reviews/client'
const member = () => ({ factId: '', caseRevision: '' as string | number, decisionId: '', publicEvidence: false })
export const withdrawalReasons = ['INCORRECT_FACT', 'RIGHTS_REVOKED', 'SOURCE_UNAVAILABLE', 'ADMIN_REQUEST'] as const
function instant(value: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$/.exec(value)
  if (!match || Number(match[1]) < 1) return null
  const date = new Date(`${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}Z`)
  if (!Number.isFinite(date.getTime()) || date.getUTCFullYear() !== Number(match[1]) || date.getUTCMonth() + 1 !== Number(match[2])
    || date.getUTCDate() !== Number(match[3]) || date.getUTCHours() !== Number(match[4]) || date.getUTCMinutes() !== Number(match[5]) || date.getUTCSeconds() !== Number(match[6])) return null
  const time = Date.parse(value); return Number.isFinite(time) ? time : null
}
export function useRelease(api: ReviewWorkspaceApi, expired: () => void = () => {}) {
  const state = reactive({ datasetId: '', year: '' as string | number, head: null as CurrentReleaseData | null,
    kind: '' as AdminPublishInput['kind'] | '', validFrom: '', validUntil: '', members: [member()], replace: false,
    precheckConfirmed: false, publishConfirmed: false, precheck: null as PublishPrecheckData | null, result: null as ReleaseData | null,
    withdrawalReason: '' as typeof withdrawalReasons[number] | '', withdrawConfirmed: false, busy: '', message: '', error: false })
  let actor: SessionData | null = null, canPublish = false, canWithdraw = false, generation = 0, pending: AbortController | undefined
  let checkedPayload: string | undefined, requestKey: string | undefined, requestPayload: string | undefined
  function invalidate() { generation++; pending?.abort(); state.busy = ''; state.message = ''; state.error = false }
  function clearPositive() { state.precheck = null; state.precheckConfirmed = false; state.publishConfirmed = false; checkedPayload = undefined; requestKey = undefined; requestPayload = undefined }
  function changed() { invalidate(); clearPositive(); state.result = null }
  function scopeChanged() { changed(); state.head = null; state.withdrawConfirmed = false; state.withdrawalReason = '' }
  function reset() { scopeChanged(); state.datasetId = ''; state.year = ''; state.kind = ''; state.validFrom = ''; state.validUntil = ''; state.members = [member()]; state.replace = false }
  function setAccess(value: SessionData | null, publish: boolean, withdraw: boolean) { reset(); actor = value; canPublish = publish; canWithdraw = withdraw }
  function withdrawalChanged() { invalidate(); state.withdrawConfirmed = false; state.result = null }
  async function run<T>(name: string, call: (signal: AbortSignal) => Promise<T>, apply: (result: T) => void) {
    if (!actor || state.busy) return
    const current = ++generation; pending?.abort(); pending = new AbortController(); state.busy = name; state.message = ''; state.error = false
    try { const result = await call(pending.signal); if (current === generation) apply(result) }
    catch (error) { if (current === generation) {
      state.result = null; state.publishConfirmed = false; state.precheckConfirmed = false; state.withdrawConfirmed = false
      const message = error instanceof ReviewWorkspaceError ? error.message : '发布或撤回结果未确认。'
      // Failed positive proof must not hide an independently available withdrawal.
      if (!(error instanceof ReviewWorkspaceError) || error.status !== 0) { state.precheck = null; checkedPayload = undefined }
      if (error instanceof ReviewWorkspaceError && [401, 403].includes(error.status)) { reset(); if (error.status === 401) expired() }
      state.message = message; state.error = true
    } }
    finally { if (current === generation) state.busy = '' }
  }
  async function loadCurrent() {
    const dataset = state.datasetId, year = strictInteger(state.year, 1, 9999)
    if (!uuid(dataset) || year === null || !(canPublish || canWithdraw)) return
    clearPositive(); state.head = null; state.withdrawConfirmed = false
    await run('current', signal => api.current(dataset, year, signal), result => {
      if (result.dataset_id !== dataset || result.entry_year !== year || result.release && result.release.is_synthetic !== actor?.is_synthetic) throw new ReviewWorkspaceError(200)
      state.head = result; state.message = '当前发布头与数据集 revision 已读取。metadata 状态不代替匿名公共读取。'
    })
  }
  function addMember() { if (!state.busy && state.members.length < 50) { changed(); state.members.push(member()) } }
  function removeMember(index: number) { if (!state.busy && state.members.length > 1) { changed(); state.members.splice(index, 1) } }
  function input(): AdminPublishInput | null {
    const year = strictInteger(state.year, 1, 9999), start = instant(state.validFrom), end = instant(state.validUntil)
    if (!actor || !canPublish || !state.head || state.head.dataset_id !== state.datasetId || state.head.entry_year !== year
      || !state.kind || (actor.is_synthetic ? state.kind !== 'test_fixture' : state.kind !== 'formal') || start === null || end === null || start >= end
      || state.members.length < 1 || state.members.length > 50 || new Set(state.members.map(item => item.factId)).size !== state.members.length) return null
    const members: AdminPublishInput['members'] = []
    for (const item of state.members) {
      const revision = strictInteger(item.caseRevision)
      if (!uuid(item.factId) || !uuid(item.decisionId) || revision === null) return null
      members.push({ fact_id: item.factId, expected_case_revision: revision, expected_decision_id: item.decisionId, public_evidence: item.publicEvidence })
    }
    if (state.replace && (!state.head.release || state.head.release.state !== 'published')) return null
    return { dataset_id: state.datasetId, expected_dataset_revision: state.head.dataset_revision, entry_year: year!, kind: state.kind,
      valid_from: state.validFrom, valid_until: state.validUntil, members, replaces_release_id: state.replace ? state.head.release!.release_id : null,
      expected_replaced_state_revision: state.replace ? state.head.release!.state_revision : null, confirmed: true }
  }
  function canPrecheck() { return !!actor && !state.busy && state.precheckConfirmed && !!input() }
  async function precheck() {
    if (!canPrecheck()) return
    const value = input()!, fingerprint = JSON.stringify(value); state.precheck = null; state.precheckConfirmed = false; state.publishConfirmed = false
    await run('precheck', signal => api.precheck(value, signal), result => {
      if (result.dataset_revision !== value.expected_dataset_revision || result.member_count !== value.members.length || result.is_synthetic !== actor?.is_synthetic) throw new ReviewWorkspaceError(200)
      state.precheck = result; checkedPayload = fingerprint; state.message = '当前发布预检通过，不是永久许可；提交时服务端会重新核验所有证据与期限。'
    })
  }
  function canPublishNow() { const value = input(); return !!actor && canPublish && !state.busy && state.publishConfirmed && !!state.precheck && !!value && JSON.stringify(value) === checkedPayload }
  async function publish() {
    if (!canPublishNow()) return
    const value = input()!, fingerprint = JSON.stringify(value)
    if (requestPayload !== fingerprint || !requestKey) { requestPayload = fingerprint; requestKey = crypto.randomUUID() }
    const key = requestKey; state.publishConfirmed = false; state.result = null
    await run('publish', signal => api.publish(value, key, signal), result => {
      if (result.dataset_id !== value.dataset_id || result.entry_year !== value.entry_year || result.kind !== value.kind || result.state !== 'published'
        || result.is_synthetic !== actor?.is_synthetic || result.replaces_release_id !== value.replaces_release_id
        || result.members.map(item => `${item.fact_id}:${item.decision_id}:${item.case_revision}:${item.public_evidence}`).sort().join()
          !== value.members.map(item => `${item.fact_id}:${item.expected_decision_id}:${item.expected_case_revision}:${item.public_evidence}`).sort().join()) throw new ReviewWorkspaceError(200)
      state.result = result; clearPositive(); state.head = null; state.message = '服务端已确认原子发布。请重新读取当前发布头及匿名公共目录，不能把此管理回执当公共投影。'
    })
  }
  function canWithdrawNow() { return !!actor && canWithdraw && !state.busy && !!state.head?.release && state.head.release.state === 'published' && !!state.withdrawalReason && state.withdrawConfirmed }
  async function withdraw() {
    if (!canWithdrawNow()) return
    const head = state.head!.release!, input: AdminWithdrawalInput = { expected_state_revision: head.state_revision, reason_code: state.withdrawalReason as typeof withdrawalReasons[number], confirmed: true }
    state.withdrawConfirmed = false; state.result = null
    await run('withdraw', signal => api.withdraw(head.release_id, input, signal), result => {
      if (result.release_id !== head.release_id || result.state !== 'withdrawn' || result.state_revision !== head.state_revision + 1) throw new ReviewWorkspaceError(200)
      state.result = result; clearPositive(); state.head = null; state.message = '服务端已确认撤回，旧历史保留。请重新读取当前头和匿名公共目录，确认当前可见状态。'
    })
  }
  function dispose() { reset(); actor = null; canPublish = false; canWithdraw = false }
  return { state, setAccess, dispose, changed, scopeChanged, withdrawalChanged, loadCurrent, addMember, removeMember, input,
    canPrecheck, precheck, canPublishNow, publish, canWithdrawNow, withdraw }
}
