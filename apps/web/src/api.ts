import type { Eligibility, Envelope, Evidence, Offering, PlanDraft, Profile, ProfileInput, RuntimeConfig } from '../../../packages/contracts/index'

export type DemoUser = 'alice' | 'bob'
export const demoTokens: Record<DemoUser, string> = { alice: 'demo-alice-token', bob: 'demo-bob-token' }
export interface SelectionInput { profile_version_id: string; offering_ids: string[] }
export interface CatalogFilter { entry_year: number; province: string; country?: 'CN' | 'GB' }
export interface M0Api {
  config(user: DemoUser): Promise<Envelope<RuntimeConfig>>
  profiles(user: DemoUser): Promise<Envelope<Profile[]>>
  createProfile(user: DemoUser, input: ProfileInput): Promise<Envelope<Profile>>
  offerings(user: DemoUser, filter: CatalogFilter): Promise<Envelope<Offering[]>>
  check(user: DemoUser, input: SelectionInput): Promise<Envelope<Eligibility[]>>
  draft(user: DemoUser, input: SelectionInput): Promise<Envelope<PlanDraft>>
  evidence(user: DemoUser, id: string): Promise<Envelope<Evidence>>
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public requestId: string | null = null) { super(message); this.name = 'ApiError' }
}

function errorText(body: unknown): string {
  if (typeof body !== 'object' || body === null) return '服务未返回可读的错误说明'
  const detail = 'detail' in body ? body.detail : 'error' in body ? body.error : null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item: unknown) => typeof item === 'object' && item !== null && 'msg' in item ? String(item.msg) : '输入校验失败').join('；')
  if (typeof detail === 'object' && detail !== null && 'message' in detail) return String(detail.message)
  return '请求失败，请检查 API 服务与演示配置'
}

export function createApi(baseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): M0Api {
  async function request<T>(user: DemoUser, path: string, input?: unknown): Promise<Envelope<T>> {
    let response: Response
    try {
      response = await fetcher(`${baseUrl.replace(/\/$/, '')}${path}`, {
        method: input === undefined ? 'GET' : 'POST',
        headers: { Authorization: `Bearer ${demoTokens[user]}`, ...(input === undefined ? {} : { 'Content-Type': 'application/json' }) },
        ...(input === undefined ? {} : { body: JSON.stringify(input) }),
      })
    } catch { throw new ApiError('无法连接 API 服务。请按运行说明启动后端；页面不会生成替代数据。', 0) }
    let body: unknown
    try { body = await response.json() } catch { throw new ApiError('API 返回了无法读取的响应，请检查后端服务。', response.status) }
    const requestId = response.headers.get('x-request-id')
    if (!response.ok) throw new ApiError(errorText(body), response.status, requestId)
    if (typeof body !== 'object' || body === null || !('data' in body) || !('meta' in body)) throw new ApiError('API 响应缺少 data / meta 契约。', response.status, requestId)
    return body as Envelope<T>
  }
  return {
    config: (user) => request(user, '/v1/config'),
    profiles: (user) => request(user, '/v1/profiles'),
    createProfile: (user, input) => request(user, '/v1/profiles', input),
    offerings: (user, filter) => {
      const query = new URLSearchParams({ entry_year: String(filter.entry_year), province: filter.province })
      if (filter.country) query.set('country', filter.country)
      return request(user, `/v1/offerings?${query}`)
    },
    check: (user, input) => request(user, '/v1/eligibility/check', input),
    draft: (user, input) => request(user, '/v1/plans/drafts', input),
    evidence: (user, id) => request(user, `/v1/evidence/${encodeURIComponent(id)}`),
  }
}
