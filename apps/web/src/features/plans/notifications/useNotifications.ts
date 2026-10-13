import { reactive } from 'vue'
import type { SessionData } from '../../auth/client'
import type { ProfileVersionData } from '../../profiles/client'
import { createNotificationApi, NotificationError, type NotificationApi, type NotificationContextData, type NotificationPage, type NotificationPreferenceData } from './client'
import { copy, sameContent, validContext, validNotification, validPage, validPreference, validSelectedProfile } from './validation'

export function useNotifications(options: { api?: NotificationApi } = {}, onPrivateInvalidated = () => {}, onSessionExpired = () => {}) {
  const api = options.api ?? createNotificationApi()
  const state = reactive({ context: null as NotificationContextData | null, preferences: null as NotificationPreferenceData | null, page: null as NotificationPage | null,
    profile: null as ProfileVersionData | null, enabled: false, confirmed: false, busy: false, conflict: false, error: null as number | null, message: '' })
  let actor: SessionData | null = null, core = false, epoch = -1, source: ProfileVersionData | null = null, disposed = false
  let scope = 0, operation = 0, profileGeneration = 0, controller: AbortController | null = null
  const access = () => !disposed && actor !== null && core
  function cancel() { operation++; controller?.abort(); controller = null; state.busy = false }
  function clear() { scope++; profileGeneration++; cancel(); state.context = null; state.preferences = null; state.page = null; state.profile = null; state.enabled = false; state.confirmed = false; state.conflict = false; state.error = null; state.message = '' }
  function fail(error: unknown) {
    const failure = error instanceof NotificationError ? error : new NotificationError(0)
    state.confirmed = false
    if ([401, 403, 404, 503, 200].includes(failure.status)) { clear(); onPrivateInvalidated(); if (failure.status === 401) onSessionExpired() }
    else if ([409, 0].includes(failure.status)) { state.conflict = true; state.preferences = null; state.page = null }
    state.error = failure.status; state.message = failure.message
  }
  async function run(action: (signal: AbortSignal) => Promise<void>) {
    if (!access() || state.busy) return
    cancel(); const generation = scope, order = operation, pending = new AbortController(); controller = pending; state.busy = true; state.error = null; state.message = ''
    try { await action(pending.signal) } catch (error) { if (generation === scope && order === operation && !pending.signal.aborted) fail(error) }
    finally { if (generation === scope && order === operation) { controller = null; state.busy = false } }
  }
  function setAccess(next: SessionData | null, allowed: boolean, nextEpoch: number) {
    if (next !== actor || allowed !== core || nextEpoch !== epoch) { actor = next; core = allowed; epoch = nextEpoch; source = null; clear() }
  }
  async function setProfile(value: ProfileVersionData | null) {
    if (source === value) return
    source = value; clear(); const generation = scope, order = ++profileGeneration
    if (!value || !access()) return
    try { const profile = copy(value); if (!await validSelectedProfile(profile) || profile.is_synthetic !== actor!.is_synthetic) throw new NotificationError(200)
      if (generation === scope && order === profileGeneration && access()) state.profile = profile
    } catch (error) { if (generation === scope && order === profileGeneration) fail(error) }
  }
  const canRead = () => access() && state.context?.can_read === true && !state.busy
  const canSave = () => access() && !state.busy && !state.conflict && state.context?.can_manage_preferences === true && state.preferences !== null && (!state.enabled || state.profile !== null)
  function setEnabled(value: boolean) { if (state.enabled !== value) { cancel(); state.enabled = value === true; state.confirmed = false } }
  function setConfirmed(value: boolean) { state.confirmed = value === true }
  async function refreshContext() { state.confirmed = false; await run(async signal => { const context = await api.context(signal); if (!validContext(context) || context.is_synthetic !== actor!.is_synthetic) throw new NotificationError(200)
    if (!signal.aborted) { if (!context.can_read) { state.preferences = null; state.page = null; state.enabled = false } state.context = copy(context); state.message = context.can_read || context.can_manage_preferences ? '已检查当前站内提醒能力；每次操作仍由服务端核验。' : '站内提醒服务尚未开放，不会模拟消息或偏好保存。' } }) }
  async function readPreferences() { if (!canRead()) return; state.confirmed = false; await run(async signal => { const preference = await api.preferences(signal)
    if (!validPreference(preference) || preference.is_synthetic !== actor!.is_synthetic) throw new NotificationError(200)
    if (!signal.aborted) { state.preferences = copy(preference); state.enabled = preference.enabled; state.conflict = false; state.message = '已读取服务端偏好；修改后仍需独立本人确认。' } }) }
  async function savePreferences() {
    if (!canSave() || !state.confirmed) return
    const previous = copy(state.preferences!), profile = state.profile ? copy(state.profile) : null
    const input = { expected_version: previous.version, enabled: state.enabled, profile_id: state.enabled ? profile!.profile_id : null, student_confirmed: true as const }
    state.confirmed = false
    await run(async signal => { const preference = await api.savePreferences(input, signal)
      if (!validPreference(preference) || preference.is_synthetic !== actor!.is_synthetic || preference.version !== previous.version + 1 || preference.enabled !== input.enabled || preference.profile_id !== input.profile_id
        || input.enabled && (preference.profile_version_id !== profile!.version_id || preference.profile_sha256 !== profile!.profile_sha256)) throw new NotificationError(200)
      if (!signal.aborted) { state.preferences = copy(preference); state.enabled = preference.enabled; state.page = null; state.conflict = false; state.message = preference.enabled ? '站内提醒偏好已开启，绑定此本人确认画像。不会发送邮件或短信。' : '站内提醒偏好已关闭。' }
    })
  }
  async function readNotifications(after?: string) {
    if (!canRead()) return
    await run(async signal => { const page = await api.list(after, signal)
      if (!validPage(page) || page.items.some(item => item.is_synthetic !== actor!.is_synthetic) || after !== undefined && page.next_cursor === after) throw new NotificationError(200)
      if (!signal.aborted) { state.page = copy(page); state.conflict = false; state.message = page.items.length ? '提醒只记录原依据的变化，不代表资格或录取结论。' : '本页没有可读站内提醒；不推断资料或规则已完整。' }
    })
  }
  async function nextPage() { if (state.page?.next_cursor) await readNotifications(state.page.next_cursor) }
  function canMarkRead(id: string) { return canRead() && !state.conflict && state.context?.can_mark_read === true && state.page?.items.some(item => item.id === id && item.read_at === null) === true }
  async function markRead(id: string) {
    if (!canMarkRead(id)) return
    const previous = copy(state.page!.items.find(item => item.id === id)!)
    await run(async signal => { const result = await api.markRead(id, { expected_version: previous.version, student_confirmed: true }, signal)
      if (!validNotification(result) || !sameContent(previous, result) || result.version !== 2 || result.read_at === null || result.is_synthetic !== actor!.is_synthetic) throw new NotificationError(200)
      if (!signal.aborted && state.page) { state.page.items = state.page.items.map(item => item.id === id ? copy(result) : item); state.message = '服务端已确认此提醒为已读；计划和资格没有改变。' }
    })
  }
  function dispose() { disposed = true; clear(); actor = null; source = null }
  return { state, setAccess, setProfile, setEnabled, setConfirmed, refreshContext, readPreferences, savePreferences, readNotifications, nextPage, canRead, canSave, canMarkRead, markRead, dispose }
}
