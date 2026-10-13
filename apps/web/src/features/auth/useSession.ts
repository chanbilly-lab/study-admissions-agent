import { reactive } from 'vue'
import { createSessionApi, SessionError, type SessionApi, type SessionData } from './client'

export type SessionStatus = 'loading' | 'logging_out' | 'authenticated' | 'unauthenticated' | 'forbidden' | 'unavailable' | 'error'

export function useSession(api: SessionApi = createSessionApi()) {
  const state = reactive<{ status: SessionStatus; actor: SessionData | null; message: string; logoutUnconfirmed: boolean; canLogout: boolean }>({
    status: 'loading', actor: null, message: '', logoutUnconfirmed: false, canLogout: false,
  })
  let generation = 0
  let pending: AbortController | undefined
  let csrf: string | undefined
  let logoutPending: Promise<void> | undefined

  async function refresh() {
    if (logoutPending) return
    const current = ++generation
    pending?.abort()
    pending = new AbortController()
    state.actor = null
    csrf = undefined
    state.logoutUnconfirmed = false
    state.status = 'loading'
    state.message = ''
    try {
      const actor = await api.session(pending.signal)
      if (generation !== current) return
      state.actor = actor
      state.canLogout = true
      state.status = 'authenticated'
    } catch (error) {
      if (generation !== current) return
      state.actor = null
      state.canLogout = false
      const status = error instanceof SessionError ? error.status : 0
      state.status = status === 401 ? 'unauthenticated' : status === 403 ? 'forbidden'
        : [0, 404, 503].includes(status) ? 'unavailable' : 'error'
      state.message = error instanceof SessionError ? error.message : '无法读取当前会话，请稍后重试。'
    }
  }

  function logout(): Promise<void> {
    if (logoutPending) return logoutPending
    const current = ++generation
    pending?.abort()
    pending = new AbortController()
    csrf = undefined
    state.actor = null
    state.canLogout = false
    state.status = 'logging_out'
    state.message = '正在退出当前应用会话…'
    state.logoutUnconfirmed = false
    const operation = async () => {
      try {
        const proof = await api.csrf(pending?.signal)
        if (generation !== current) return
        csrf = proof.csrf_token
        await api.logout(csrf, pending?.signal)
        if (generation !== current) return
        state.status = 'unauthenticated'
        state.message = '已退出当前应用会话。'
      } catch (error) {
        if (generation !== current) return
        state.actor = null
        if (error instanceof SessionError && error.status === 401) {
          state.status = 'unauthenticated'
          state.message = '当前应用会话已失效。'
        } else {
          state.status = 'error'
          state.logoutUnconfirmed = true
          state.message = '退出未确认。服务端可能仍有有效会话，请重试退出或重新检查会话。'
        }
      } finally {
        csrf = undefined
      }
    }
    logoutPending = operation().finally(() => { logoutPending = undefined })
    return logoutPending
  }

  function dispose() {
    generation++
    pending?.abort()
    state.actor = null
    state.canLogout = false
    csrf = undefined
  }

  function invalidate() {
    dispose()
    state.logoutUnconfirmed = false
    state.status = 'unauthenticated'
    state.message = '当前应用会话已失效，请重新登录。'
  }

  return { state, refresh, logout, dispose, invalidate, loginPath: api.loginPath }
}
