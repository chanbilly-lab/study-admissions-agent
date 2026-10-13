import type { AppendInput, CreateInput, ProfileContextData, ProfilePage, ProfileRef, ProfileSnapshot, ProfileVersionData, ProfileWriteData } from '../../../../../packages/contracts/v2/profiles/generated'
import { createSessionApi, SessionError } from '../auth/client'
import { adaptationOf, exact, validSnapshot } from './form'
export type { AppendInput, CreateInput, ProfileContextData, ProfilePage, ProfileRef, ProfileSnapshot, ProfileVersionData, ProfileWriteData }
export class ProfileError extends Error {
  constructor(public readonly status: number, message?: string) {
    super(message ?? ({ 401: '当前会话已失效，请重新登录。', 403: '当前用途或对象权限已失效，私人资料已清空。',
      404: '指定画像不存在或不可读取。', 409: '确认版本已变化。请明确重新读取当前版并核对草稿，不会自动覆盖。',
      422: '画像输入未通过校验，本次保存未确认。', 503: '画像服务未开放或暂不可用，不会回退为演示数据。' }[status] ?? '请求结果未确认，请重新读取当前版本。'))
    this.name = 'ProfileError'
  }
}
export interface ProfileApi {
  context(signal?: AbortSignal): Promise<ProfileContextData>
  list(cursor?: string, signal?: AbortSignal): Promise<ProfilePage>
  current(id: string, signal?: AbortSignal): Promise<ProfileVersionData>
  history(id: string, versionId: string, signal?: AbortSignal): Promise<ProfileVersionData>
  create(input: CreateInput, key: string, signal?: AbortSignal): Promise<ProfileWriteData>
  append(id: string, input: AppendInput, signal?: AbortSignal): Promise<ProfileWriteData>
}
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value)
const positive = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 1 && value <= 2_147_483_647
const utc = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value))
function reference(value: unknown): value is ProfileRef { return exact(value, ['profile_id', 'version_id', 'version', 'confirmed_at', 'expires_at', 'is_synthetic']) && uuid(value.profile_id) && uuid(value.version_id) && positive(value.version)
  && utc(value.confirmed_at) && utc(value.expires_at) && Date.parse(value.expires_at) > Date.parse(value.confirmed_at) && typeof value.is_synthetic === 'boolean' }
function version(value: unknown): value is ProfileVersionData {
  return exact(value, ['profile_id', 'version_id', 'version', 'profile', 'profile_sha256', 'confirmed_at', 'source', 'expires_at', 'is_synthetic', 'adaptation']) && uuid(value.profile_id) && uuid(value.version_id) && positive(value.version)
    && validSnapshot(value.profile) && typeof value.profile_sha256 === 'string' && /^[0-9a-f]{64}$/.test(value.profile_sha256) && utc(value.confirmed_at) && utc(value.expires_at) && Date.parse(value.expires_at) > Date.parse(value.confirmed_at)
    && value.source === 'student_declared' && typeof value.is_synthetic === 'boolean' && exact(value.adaptation, ['status', 'reason'])
    && value.adaptation.status === adaptationOf(value.profile).status && value.adaptation.reason === adaptationOf(value.profile).reason
}
export async function snapshotHash(profile: ProfileSnapshot): Promise<string> {
  // All object keys in this closed DTO are ASCII. Lexical sorting matches T49;
  // strings keep their original Unicode and arrays retain their declared order.
  const ordered = (value: unknown): unknown => Array.isArray(value) ? value.map(ordered) : value !== null && typeof value === 'object'
    ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, item]) => [key, ordered(item)])) : value
  const bytes = new TextEncoder().encode(JSON.stringify(ordered(profile)))
  if (bytes.length > 65_536 || !crypto.subtle) throw new ProfileError(200, '无法校验完整画像快照，结果未确认。')
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), value => value.toString(16).padStart(2, '0')).join('')
}
export function createProfileApi(prefix = import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): ProfileApi {
  const session = createSessionApi(prefix, fetcher), base = `${prefix.replace(/\/$/, '')}/v2/profiles`
  const ref = (id: string) => { if (!uuid(id)) throw new ProfileError(422) }
  async function request<T>(path: string, validate: (value: unknown) => value is T, signal?: AbortSignal, input?: CreateInput | AppendInput, key?: string): Promise<T> {
    let token: string | undefined
    let bodyText: string | undefined, submittedProfile: ProfileSnapshot | undefined
    try {
      if (input) {
        const keys = 'expected_current_version' in input ? ['profile', 'confirmed', 'expected_current_version'] : ['profile', 'confirmed']
        if (!exact(input, keys) || input.confirmed !== true || !validSnapshot(input.profile) || ('expected_current_version' in input && !positive(input.expected_current_version))) throw new ProfileError(422)
        if (key !== undefined && !/^[A-Za-z0-9._:-]{1,128}$/.test(key)) throw new ProfileError(422)
        bodyText = JSON.stringify(input)
        submittedProfile = (JSON.parse(bodyText) as CreateInput).profile
        token = (await session.csrf(signal)).csrf_token
      }
      const headers: Record<string, string> = { Accept: 'application/json' }
      if (input) { headers['Content-Type'] = 'application/json'; headers['X-CSRF-Token'] = token! }
      if (key !== undefined) headers['Idempotency-Key'] = key
      const response = await fetcher(base + path, { method: input ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers, signal,
        ...(input ? { body: bodyText } : {}) })
      if (response.status !== 200) throw new ProfileError(response.status)
      const body: unknown = await response.json()
      if (!exact(body, ['data', 'meta']) || !validate(body.data) || !exact(body.meta, ['api_version', 'request_id', 'data_as_of', 'profile_version_id', 'release_id', 'ruleset_version', 'profile_mode', 'data_mode', 'model_mode'])
        || body.meta.api_version !== 'v2' || typeof body.meta.request_id !== 'string' || !/^[0-9a-f]{32}$/.test(body.meta.request_id) || body.meta.data_as_of !== null || body.meta.release_id !== null || body.meta.ruleset_version !== null
        || !(body.meta.data_mode === 'demo' || body.meta.data_mode === 'verified') || !(body.meta.model_mode === 'disabled' || body.meta.model_mode === 'mock') || (body.meta.data_mode === 'verified' && body.meta.model_mode === 'mock')) throw new ProfileError(200, '画像响应与契约不一致，结果未确认。')
      const data = body.data
      const boundVersion = version(data) ? data : exact(data, ['version', 'replayed']) && version(data.version) ? data.version : null
      if (boundVersion ? body.meta.profile_version_id !== boundVersion.version_id || body.meta.profile_mode !== (boundVersion.is_synthetic ? 'synthetic' : 'real') : body.meta.profile_version_id !== null || body.meta.profile_mode !== null) throw new ProfileError(200, '画像响应版本引用不一致，结果未确认。')
      if (boundVersion && boundVersion.profile_sha256 !== await snapshotHash(boundVersion.profile)) throw new ProfileError(200, '画像内容与版本 hash 不一致，结果未确认。')
      if (submittedProfile && boundVersion && boundVersion.profile_sha256 !== await snapshotHash(submittedProfile)) throw new ProfileError(200, '返回的画像并非本次明确确认的完整草稿，保存结果未确认。')
      return data
    } catch (error) {
      if (error instanceof ProfileError || signal?.aborted) throw error
      if (error instanceof SessionError) throw new ProfileError(error.status)
      throw new ProfileError(0)
    } finally { token = undefined }
  }
  const written = (value: unknown): value is ProfileWriteData => exact(value, ['version', 'replayed']) && version(value.version) && typeof value.replayed === 'boolean'
  return {
    context: signal => request('/context', (value): value is ProfileContextData => exact(value, ['schema_version', 'can_create', 'can_read', 'can_append', 'reason', 'is_synthetic']) && value.schema_version === 'v2.t23'
      && ['can_create', 'can_read', 'can_append', 'is_synthetic'].every(key => typeof value[key] === 'boolean') && (value.reason === 'allowed' || value.reason === 'processing_disabled')
      && (value.reason !== 'processing_disabled' || !value.can_create && !value.can_read && !value.can_append), signal),
    list(cursor, signal) { if (cursor !== undefined && (cursor.length < 1 || cursor.length > 2048)) throw new ProfileError(422)
      return request(`?limit=20${cursor === undefined ? '' : '&cursor=' + encodeURIComponent(cursor)}`, (value): value is ProfilePage => exact(value, ['items', 'next_cursor']) && Array.isArray(value.items) && value.items.length <= 20 && value.items.every(reference)
        && new Set(value.items.map(item => item.profile_id)).size === value.items.length && (value.next_cursor === null || typeof value.next_cursor === 'string' && value.next_cursor.length >= 1 && value.next_cursor.length <= 2048), signal) },
    current(id, signal) { ref(id); return request('/' + id, version, signal).then(data => { if (data.profile_id !== id) throw new ProfileError(200); return data }) },
    history(id, versionId, signal) { ref(id); ref(versionId); return request(`/${id}/versions/${versionId}`, version, signal).then(data => { if (data.profile_id !== id || data.version_id !== versionId) throw new ProfileError(200); return data }) },
    create(input, key, signal) { if (!exact(input, ['profile', 'confirmed']) || !/^[A-Za-z0-9._:-]{1,128}$/.test(key)) throw new ProfileError(422); return request('', written, signal, input, key) },
    append(id, input, signal) { ref(id); if (!exact(input, ['profile', 'confirmed', 'expected_current_version'])) throw new ProfileError(422)
      const expected = input.expected_current_version
      return request(`/${id}/versions`, written, signal, input).then(data => { if (data.version.profile_id !== id || data.version.version !== expected + 1 || data.replayed) throw new ProfileError(200); return data }) },
  }
}
