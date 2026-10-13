import type { AuthCsrfData, AuthLogoutData, AuthSessionData } from '../../../../../packages/contracts/v2/identity/generated'

export type SessionData = AuthSessionData
export type CsrfData = AuthCsrfData
export type LogoutData = AuthLogoutData

export interface SessionApi {
  readonly loginPath: string
  session(signal?: AbortSignal): Promise<SessionData>
  csrf(signal?: AbortSignal): Promise<CsrfData>
  logout(token: string, signal?: AbortSignal): Promise<LogoutData>
}

const messages: Record<number, string> = {
  401: '尚未登录，或会话已到期。',
  403: '账号未获准访问。当前仅允许预登记且启用的主体，不会自动注册。',
  404: '当前 API 未开放身份入口。演示服务不能用于登录。',
  503: '身份服务未启用或暂不可用。请联系维护人员确认配置。',
}

export class SessionError extends Error {
  constructor(public readonly status: number, message = messages[status] ?? '无法读取当前会话，请稍后重试。') {
    super(message)
    this.name = 'SessionError'
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function utcDate(value: unknown): value is string {
  return typeof value === 'string'
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value)
    && Number.isFinite(Date.parse(value))
}

function csrfToken(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{43}$/.test(value)
}

function isSessionData(value: unknown): value is SessionData {
  if (!record(value)) return false
  const keys = ['authenticated', 'user_id', 'expires_at', 'is_synthetic', 'private_business_available']
  return Object.keys(value).length === keys.length && keys.every((key) => key in value)
    && value.authenticated === true && typeof value.user_id === 'string'
    && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.user_id)
    && utcDate(value.expires_at)
    && typeof value.is_synthetic === 'boolean' && value.private_business_available === false
}

export function createSessionApi(basePrefix = import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): SessionApi {
  // Cookie auth uses the current origin. A build setting cannot turn this into
  // an arbitrary IdP, return URL, or cross-origin credential destination.
  if ((!/^\/[A-Za-z0-9/_-]*$/.test(basePrefix) && basePrefix !== '') || basePrefix.includes('//')) {
    throw new SessionError(0, '身份 API 必须使用同源相对路径。')
  }
  const prefix = basePrefix.replace(/\/$/, '')
  const loginPath = `${prefix}/v2/auth/login`
  async function request(path: 'session' | 'csrf' | 'logout', options: RequestInit): Promise<unknown> {
    let response: Response
    try {
      response = await fetcher(`${prefix}/v2/auth/${path}`, {
        credentials: 'same-origin', cache: 'no-store', redirect: 'error', ...options,
      })
    } catch (error) {
      if (options.signal?.aborted) throw error
      throw new SessionError(0, '无法连接身份服务。页面不会切换为演示账号。')
    }
    if (response.status !== 200) throw new SessionError(response.status)
    let body: unknown
    try { body = await response.json() }
    catch { throw new SessionError(200, '身份服务返回了无法读取的响应。') }
    if (!record(body) || !record(body.meta)) {
      throw new SessionError(200, '身份服务响应不符合契约。')
    }
    return body.data
  }
  return {
    loginPath,
    async session(signal) {
      const data = await request('session', { method: 'GET', headers: { Accept: 'application/json' }, signal })
      if (!isSessionData(data)) {
        throw new SessionError(200, '会话响应不符合契约，当前身份已清空。')
      }
      return data
    },
    async csrf(signal) {
      const data = await request('csrf', { method: 'GET', headers: { Accept: 'application/json' }, signal })
      if (!record(data) || Object.keys(data).length !== 2 || !csrfToken(data.csrf_token) || !utcDate(data.expires_at)) {
        throw new SessionError(200, '安全请求凭据响应不符合契约。')
      }
      return { csrf_token: data.csrf_token, expires_at: data.expires_at }
    },
    async logout(token, signal) {
      if (!csrfToken(token)) throw new SessionError(0, '安全请求凭据无效。')
      // Origin is set by the browser. No request body, URL proof or return path.
      const data = await request('logout', { method: 'POST',
        headers: { Accept: 'application/json', 'X-CSRF-Token': token }, signal })
      if (!record(data) || Object.keys(data).length !== 1 || data.logged_out !== true) {
        throw new SessionError(200, '退出响应不符合契约，无法确认服务端已撤销会话。')
      }
      return { logged_out: true }
    },
  }
}
