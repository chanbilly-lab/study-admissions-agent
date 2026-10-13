import { reactive } from 'vue'
import type { SessionData } from '../auth/client'
import { createProfileApi, ProfileError, snapshotHash, type ProfileApi, type ProfileContextData, type ProfilePage, type ProfileVersionData } from './client'
import { blankDraft, blankSlot, clearUnsupportedDraftFields, draftToSnapshot, snapshotToDraft, type AssessmentKey, type ProfileDraft } from './form'

export function useProfiles(api: ProfileApi = createProfileApi(), onSessionExpired: () => void = () => {}, onInvalidated: () => void = () => {}) {
  const state = reactive<{ status: 'idle' | 'loading' | 'ready' | 'error'; context: ProfileContextData | null; busy: string | null;
    message: string; error: boolean; page: ProfilePage | null; current: ProfileVersionData | null; history: ProfileVersionData | null;
    draft: ProfileDraft; editing: boolean; dirty: boolean; conflict: boolean; appendUnconfirmed: boolean; routeCleared: boolean; historyVersionId: string }>(
    { status: 'idle', context: null, busy: null, message: '', error: false, page: null, current: null, history: null,
      draft: blankDraft(), editing: false, dirty: false, conflict: false, appendUnconfirmed: false, routeCleared: false, historyVersionId: '' })
  let actor: SessionData | null = null, coreAllowed = false, generation = 0, pending: AbortController | undefined
  let createKey: string | undefined, createPayload: string | undefined
  function cancel() { generation++; pending?.abort(); state.busy = null }
  function reset() {
    state.context = null; state.page = null; state.current = null; state.history = null; state.draft = blankDraft(); state.editing = false
    state.dirty = false; state.conflict = false; state.appendUnconfirmed = false; state.routeCleared = false; state.historyVersionId = ''
    createKey = undefined; createPayload = undefined
  }
  function begin(action: string) { cancel(); pending = new AbortController(); state.busy = action; state.message = ''; state.error = false; return { current: generation, signal: pending.signal } }
  function fail(error: unknown) {
    state.draft.confirmed = false; state.error = true; state.message = error instanceof ProfileError ? error.message : '本次结果未确认，请重新读取。'
    if (error instanceof ProfileError && [401, 403, 404, 503, 200].includes(error.status)) {
      reset(); state.status = 'error'; onInvalidated()
      if (error.status === 401) onSessionExpired()
    }
  }
  function matches(value: { is_synthetic: boolean }) { if (!actor || value.is_synthetic !== actor.is_synthetic) throw new ProfileError(200, '画像模式与当前主体不一致，私人状态已清空。') }
  function canRead() { return !!actor && coreAllowed && !!state.context?.can_read && state.status === 'ready' && !state.busy }
  function canEdit() { return !!actor && coreAllowed && state.status === 'ready' && !state.busy && (state.current ? !!state.context?.can_append : !!state.context?.can_create) }
  async function refresh() {
    const { current, signal } = begin('context'); reset()
    if (!actor || !coreAllowed) { state.status = 'idle'; state.busy = null; return }
    state.status = 'loading'
    try { const context = await api.context(signal); if (current !== generation) return; matches(context); state.context = context; state.status = 'ready' }
    catch (error) { if (current === generation) { state.status = 'error'; fail(error) } }
    finally { if (current === generation) state.busy = null }
  }
  function setAccess(value: SessionData | null, allowed: boolean) {
    cancel(); actor = value; coreAllowed = allowed; reset(); state.message = ''; state.error = false; onInvalidated()
    return refresh()
  }
  function changed(route = false) {
    cancel(); createKey = undefined; createPayload = undefined; state.draft.confirmed = false; state.dirty = true; state.message = ''; state.error = false
    if (route && clearUnsupportedDraftFields(state.draft)) state.routeCleared = true
    onInvalidated()
  }
  function addGrade(key: AssessmentKey) { if (!canEdit() || !state.editing || state.draft.grades[key]) return; state.draft.grades[key] = { achieved: blankSlot(), predicted: blankSlot() }; changed() }
  function removeGrade(key: AssessmentKey) { delete state.draft.grades[key]; changed() }
  function newProfile() {
    if (!actor || !coreAllowed || !state.context?.can_create || state.busy) return
    cancel(); state.current = null; state.history = null; state.draft = blankDraft(); state.editing = true; state.dirty = true
    state.conflict = false; state.appendUnconfirmed = false; state.routeCleared = false; state.historyVersionId = ''; changed()
  }
  async function list(next = false) {
    if (!canRead()) return
    const cursor = next ? state.page?.next_cursor ?? undefined : undefined
    if (next && !cursor) return
    const { current, signal } = begin('list')
    try { const page = await api.list(cursor, signal); if (current !== generation) return; page.items.forEach(matches); state.page = page }
    catch (error) { if (current === generation) { state.page = null; fail(error) } }
    finally { if (current === generation) state.busy = null }
  }
  function acceptCurrent(value: ProfileVersionData, keepDraft: boolean) {
    matches(value); state.current = value; state.history = null; state.historyVersionId = ''; state.conflict = false; state.appendUnconfirmed = false
    if (!keepDraft) { state.draft = snapshotToDraft(value.profile); state.dirty = false; state.routeCleared = false }
    state.editing = keepDraft && !!state.context?.can_append; state.draft.confirmed = false; createKey = undefined; createPayload = undefined
  }
  function editCurrent() {
    if (!canEdit() || !state.current || state.conflict || state.appendUnconfirmed) return
    state.draft = snapshotToDraft(state.current.profile); state.editing = true; state.dirty = false; state.routeCleared = false
    state.draft.confirmed = false; onInvalidated()
  }
  async function load(id: string, keepDraft = false) {
    if (!canRead()) return
    const { current, signal } = begin('read'); state.history = null; state.draft.confirmed = false; onInvalidated()
    try { const value = await api.current(id, signal); if (current !== generation) return; if (value.profile_id !== id) throw new ProfileError(200); acceptCurrent(value, keepDraft)
      state.message = keepDraft ? '已读取服务端当前版。草稿仍未确认，请核对后重新明确保存。' : '已读取本人确认版本；编辑产生新完整版本，不覆盖历史。' }
    catch (error) { if (current === generation) { state.current = null; state.editing = false; state.draft = blankDraft(); fail(error) } }
    finally { if (current === generation) state.busy = null }
  }
  async function history() {
    if (!canRead() || !state.current || !state.historyVersionId) return
    const rootId = state.current.profile_id, versionId = state.historyVersionId
    const { current, signal } = begin('history'); state.history = null; state.draft.confirmed = false
    try { const value = await api.history(rootId, versionId, signal); if (current !== generation) return; matches(value)
      if (value.profile_id !== rootId || value.version_id !== versionId) throw new ProfileError(200); state.history = value }
    catch (error) { if (current === generation) fail(error) }
    finally { if (current === generation) state.busy = null }
  }
  function canSave() {
    if (!state.editing || !canEdit() || !state.draft.confirmed || state.conflict || state.appendUnconfirmed) return false
    try { draftToSnapshot(state.draft); return true } catch { return false }
  }
  function validationMessage() { try { draftToSnapshot(state.draft); return '' } catch (error) { return error instanceof Error ? error.message : '请核对资料。' } }
  async function save() {
    if (!canSave()) return
    const root = state.current, payload = { profile: draftToSnapshot(state.draft), confirmed: true as const }
    const identity = JSON.stringify(payload)
    if (!root && (createPayload !== identity || !createKey)) { createPayload = identity; createKey = crypto.randomUUID() }
    const key = createKey
    const { current, signal } = begin('save'); state.draft.confirmed = false; onInvalidated()
    try {
      const result = root ? await api.append(root.profile_id, { ...payload, expected_current_version: root.version }, signal) : await api.create(payload, key!, signal)
      if (current !== generation) return
      const submittedHash = await snapshotHash(payload.profile)
      if (current !== generation) return
      if (result.version.profile_sha256 !== submittedHash) throw new ProfileError(200, '返回的画像不是本次明确确认的草稿，保存未确认。')
      if (root && (result.version.profile_id !== root.profile_id || result.version.version !== root.version + 1)) throw new ProfileError(200)
      acceptCurrent(result.version, false); state.page = null
      state.message = `服务端已确认第 ${result.version.version} 版${result.replayed ? '（原首建回执重放）' : ''}。资料仅为本人声明，尚无可用资格结果。`
    } catch (error) {
      if (current !== generation) return
      if (error instanceof ProfileError && error.status === 409) { state.conflict = true; createKey = undefined; createPayload = undefined }
      else if (root && !(error instanceof ProfileError && [401, 403, 503, 200, 422, 404].includes(error.status))) state.appendUnconfirmed = true
      fail(error)
    } finally { if (current === generation) state.busy = null }
  }
  function discardDraft() { if (state.current) { state.draft = snapshotToDraft(state.current.profile); state.draft.confirmed = false; state.dirty = false; state.routeCleared = false; onInvalidated() } }
  function dispose() { cancel(); actor = null; coreAllowed = false; reset(); state.status = 'idle' }
  return { state, setAccess, refresh, canRead, canEdit, canSave, validationMessage, changed, addGrade, removeGrade, newProfile, editCurrent, list, load, history, save, discardDraft, dispose }
}
