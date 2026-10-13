import type { MarkReadInput, NotificationContextData, NotificationData, NotificationPage, NotificationPreferenceData, PreferenceInput } from '../../../../../../packages/contracts/v2/notifications/generated'
import { createSessionApi, SessionError } from '../../auth/client'
import { exact, prefixBase, uuid, validMeta } from '../../catalog/validation'
import { cursor, validContext, validNotification, validPage, validPreference, validPreferenceInput, validReadInput } from './validation'
export type { MarkReadInput, NotificationContextData, NotificationData, NotificationPage, NotificationPreferenceData, PreferenceInput }

export class NotificationError extends Error {
  constructor(public readonly status: number) {
    super(({ 401: '当前会话已失效，请重新登录。',
      403: '当前用途或提醒权限已失效，私人提醒已清空。',
      404: '提醒不存在或不可读取，私人内容已清空。',
      409: '提醒或偏好版本已变化，请明确重读后重新核对。',
      422: '提醒输入未通过校验，本次操作未确认。',
      503: '站内提醒服务未开放或暂不可用，私人内容已清空。',
      200: '提醒响应未通过验证，私人内容已清空。',
    }[status] ?? '网络结果未确认。请明确读取服务端状态，不会自动再次写入。'))
    this.name = 'NotificationError'
  }
}

export interface NotificationApi {
  context(signal?: AbortSignal): Promise<NotificationContextData>
  preferences(signal?: AbortSignal): Promise<NotificationPreferenceData>
  savePreferences(input: PreferenceInput, signal?: AbortSignal): Promise<NotificationPreferenceData>
  list(cursor?: string, signal?: AbortSignal): Promise<NotificationPage>
  markRead(id: string, input: MarkReadInput, signal?: AbortSignal): Promise<NotificationData>
}
export function createNotificationApi(prefix = import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): NotificationApi {
  let base: string
  try { base = prefixBase(prefix) + '/notifications' } catch { throw new NotificationError(422) }
  const session = createSessionApi(prefix, fetcher)
  async function request<T>(path: string, kind: 'context' | 'preference' | 'page' | 'notification', signal?: AbortSignal, input?: PreferenceInput | MarkReadInput): Promise<T> {
    let token: string | undefined, successful = false
    try {
      if (input && !('enabled' in input ? validPreferenceInput(input) : validReadInput(input))) throw new NotificationError(422)
      // Capture the entire request before awaiting the in-memory CSRF proof.
      const body = input === undefined ? undefined : JSON.stringify(input)
      if (body && new TextEncoder().encode(body).length > 65536) throw new NotificationError(422)
      const frozen = body ? JSON.parse(body) as PreferenceInput | MarkReadInput : undefined
      if (input) token = (await session.csrf(signal)).csrf_token
      const response = await fetcher(base + path, { method: input ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal,
        headers: { Accept: 'application/json', ...(input ? { 'Content-Type': 'application/json', 'X-CSRF-Token': token! } : {}) }, ...(body ? { body } : {}) })
      if (response.status !== 200) throw new NotificationError(response.status)
      successful = true
      const raw = await response.text()
      if (new TextEncoder().encode(raw).length > 262144) throw new NotificationError(200)
      const envelope: unknown = JSON.parse(raw)
      if (!exact(envelope, ['data', 'meta']) || !exact(envelope.meta, ['api_version', 'request_id', 'data_as_of', 'profile_version_id', 'release_id', 'ruleset_version', 'profile_mode', 'data_mode', 'model_mode'])
        || envelope.meta.data_mode !== 'verified' || envelope.meta.model_mode !== 'disabled') throw new NotificationError(200)
      const data = envelope.data
      const valid = kind === 'context' ? validContext(data) : kind === 'preference' ? validPreference(data) : kind === 'page' ? validPage(data) : validNotification(data)
      if (!valid) throw new NotificationError(200)
      const profile = kind === 'preference' ? data as NotificationPreferenceData : kind === 'notification' ? data as NotificationData : null
      if (!validMeta(envelope.meta, response, profile?.profile_version_id ?? null, profile?.profile_version_id ? profile.is_synthetic : null)) throw new NotificationError(200)
      if (kind === 'notification' && (data as NotificationData).id !== path.split('/')[1]) throw new NotificationError(200)
      if (frozen && validPreferenceInput(frozen)) {
        const preference = data as NotificationPreferenceData
        if (preference.enabled !== frozen.enabled || preference.profile_id !== frozen.profile_id || preference.version !== frozen.expected_version + 1) throw new NotificationError(200)
      } else if (frozen && ((data as NotificationData).version !== 2 || (data as NotificationData).read_at === null)) throw new NotificationError(200)
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      return data as T
    } catch (error) {
      if (error instanceof NotificationError || signal?.aborted) throw error
      if (error instanceof SessionError) throw new NotificationError(error.status)
      throw new NotificationError(successful ? 200 : 0)
    } finally { token = undefined }
  }
  return {
    context: signal => request('/context', 'context', signal),
    preferences: signal => request('/preferences', 'preference', signal),
    savePreferences: (input, signal) => request('/preferences', 'preference', signal, input),
    list: (after, signal) => { if (after !== undefined && !cursor(after)) throw new NotificationError(422); const query = new URLSearchParams({ limit: '20', ...(after === undefined ? {} : { cursor: after }) }); return request('?' + query, 'page', signal) },
    markRead: (id, input, signal) => { if (!uuid(id)) throw new NotificationError(422); return request('/' + id + '/read', 'notification', signal, input) },
  }
}
