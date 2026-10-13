import { reactive } from 'vue'
import type { SessionData } from '../auth/client'
import { createPrivacyApi, PrivacyError, type AdmissionData, type AgeBand, type PrivacyApi, type PrivacyNoticeData } from './client'

export function useAdmission(api: PrivacyApi = createPrivacyApi(), onSessionExpired: () => void = () => {}) {
  const state = reactive<{ status: 'loading' | 'ready' | 'error'; notice: PrivacyNoticeData | null; admission: AdmissionData | null;
    message: string; action: 'age' | 'confirm' | 'withdraw' | null; ageBand: AgeBand | ''; ageConfirmed: boolean; coreConfirmed: boolean }>({
    status: 'loading', notice: null, admission: null, message: '', action: null, ageBand: '', ageConfirmed: false, coreConfirmed: false,
  })
  let actor: SessionData | null = null
  let generation = 0
  let pending: AbortController | undefined

  function clearConfirmation() {
    state.ageBand = ''
    state.ageConfirmed = false
    state.coreConfirmed = false
  }
  function begin() {
    const current = ++generation
    pending?.abort()
    pending = new AbortController()
    state.admission = null
    clearConfirmation()
    state.message = ''
    return { current, signal: pending.signal }
  }
  function accept(value: AdmissionData) {
    if (!actor || value.user_id !== actor.user_id || value.is_synthetic !== actor.is_synthetic) {
      throw new PrivacyError(200, '本人设置与当前会话不匹配，资料处理保持关闭。')
    }
    state.admission = value
  }
  function failure(error: unknown) {
    state.admission = null
    state.status = 'error'
    state.message = error instanceof PrivacyError ? error.message : '无法读取隐私设置，本次操作未确认。'
    if (error instanceof PrivacyError && error.status === 401) onSessionExpired()
  }
  async function refresh() {
    const { current, signal } = begin()
    state.status = 'loading'
    state.notice = null
    state.action = null
    try {
      const [notice, admission] = await Promise.all([api.notice(signal), actor ? api.admission(signal) : Promise.resolve(null)])
      if (generation !== current) return
      state.notice = notice
      if (admission) accept(admission)
      state.status = 'ready'
    } catch (error) { if (generation === current) failure(error) }
  }
  function setActor(value: SessionData | null) {
    actor = value
    return refresh()
  }
  function canSubmit() {
    return state.status === 'ready' && !state.action && actor !== null && state.notice?.readiness === true
      && state.notice.notice_id !== null && state.admission?.readiness === true
      && state.admission.notice_id === state.notice.notice_id
      && state.admission.policy_version === state.notice.policy_version
  }
  function canConfirm() {
    return canSubmit() && state.coreConfirmed && state.admission?.age_assurance === 'declared'
      && state.admission.age_band === '18_plus' && state.notice?.purposes.includes('core_consultation') === true
      && ['consent_missing', 'consent_withdrawn', 'consent_invalidated', 'role_missing'].includes(state.admission.reason)
  }
  async function mutate(action: 'age' | 'confirm' | 'withdraw') {
    if (state.action || !actor || state.status !== 'ready') return
    const previous = state.admission
    const notice = state.notice
    const ageBand = state.ageBand
    if (!previous || !notice) return
    if (action === 'withdraw') {
      if (!previous.consent_id || previous.consent_status !== 'active') return
    } else if (!canSubmit() || !notice.notice_id
      || (action === 'age' && (!ageBand || !state.ageConfirmed))
      || (action === 'confirm' && !canConfirm())) return
    const { current, signal } = begin()
    state.action = action
    try {
      const result = action === 'age' ? await api.declareAge({ age_band: ageBand as AgeBand, confirmed: true, notice_id: notice.notice_id!, expected_revision: previous.revision }, signal)
        : action === 'confirm' ? await api.confirmCore({ purpose: 'core_consultation', confirmed: true, notice_id: notice.notice_id!, expected_revision: previous.revision }, signal)
        : await api.withdraw(previous.consent_id!, signal)
      if (generation !== current) return
      accept(result)
      state.status = 'ready'
      state.message = action === 'withdraw' ? '服务端已返回撤回后的当前状态。' : '服务端已返回当前准入状态；私有业务仍未开放。'
    } catch (error) {
      if (generation !== current) return
      if (error instanceof PrivacyError && error.status === 409) {
        await refresh()
        if (state.status === 'ready') state.message = error.message
      } else failure(error)
    } finally { if (generation === current) state.action = null }
  }
  function dispose() {
    ++generation
    pending?.abort()
    actor = null
    state.admission = null
    state.notice = null
    state.action = null
    clearConfirmation()
  }
  return { state, setActor, refresh, canSubmit, canConfirm, declareAge: () => mutate('age'), confirmCore: () => mutate('confirm'), withdraw: () => mutate('withdraw'), dispose }
}
