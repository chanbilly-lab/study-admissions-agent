import { createSessionApi, SessionError } from '../auth/client'
import type { SharingPolicyData, GrantData, GrantListData, GrantMutationData, CreateGrantInput, AcceptGrantInput,
  ListV2AccessGrantsQuery } from '../../../../../packages/contracts/v2/identity/generated'

export type { SharingPolicyData, GrantData, GrantListData, GrantMutationData, CreateGrantInput, AcceptGrantInput }
export type ResourceType = GrantData['resource_type']
export type SharedField = GrantData['fields'][number]
export type SharedAction = GrantData['actions'][number]
export type Direction = NonNullable<ListV2AccessGrantsQuery['direction']>
export interface SharingApi {
  policy(signal?: AbortSignal): Promise<SharingPolicyData>
  list(direction: Direction, afterId?: string, signal?: AbortSignal): Promise<GrantListData>
  create(input: CreateGrantInput, signal?: AbortSignal): Promise<GrantMutationData>
  accept(id: string, input: AcceptGrantInput, signal?: AbortSignal): Promise<GrantMutationData>
  revoke(id: string, signal?: AbortSignal): Promise<GrantMutationData>
}

const messages: Record<number, string> = {
  401: '当前应用会话已失效，请重新登录。',
  403: '当前共享请求未获准，请重新读取年龄、用途及共享设置。',
  404: '共享设置未开放，或指定授权不可访问。',
  409: '对象、政策或授权版本已变化。请重新读取，再次明确确认。',
  422: '共享输入不符合当前契约，请检查具体对象、字段、动作和期限。',
  503: '共享服务未启用或暂不可用，本次操作无法确认。',
}
export class SharingError extends Error {
  constructor(public readonly status: number, message = messages[status] ?? '无法读取共享设置。本次操作未确认，请重新读取。') {
    super(message); this.name = 'SharingError'
  }
}
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function keys(value: Record<string, unknown>, expected: readonly string[]) { return Object.keys(value).length === expected.length && expected.every(key => key in value) }
export function uuid(value: unknown): value is string { return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) }
function text(value: unknown): value is string { return typeof value === 'string' }
function integer(value: unknown, minimum = 0): value is number { return Number.isSafeInteger(value) && Number(value) >= minimum }
function member(value: unknown, choices: readonly string[]) { return text(value) && choices.includes(value) }
function unique(value: unknown, choices: readonly string[], min = 1) { return Array.isArray(value) && value.length >= min && value.length <= choices.length && value.every(item => member(item, choices)) && new Set(value).size === value.length }
function date(value: unknown): value is string { return text(value) && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value)) }
function nullable(value: unknown, check: (value: unknown) => boolean) { return value === null || check(value) }
const kinds = ['profile', 'plan', 'attachment', 'export', 'job']
export function isSharingPolicyData(value: unknown): value is SharingPolicyData {
  return record(value) && keys(value, ['policy_version', 'text', 'text_sha256', 'sharing_available', 'readiness_reason', 'is_synthetic', 'scope_matrix', 'max_duration_seconds', 'guardian_verification_available', 'private_business_available'])
    && text(value.policy_version) && text(value.text) && text(value.text_sha256) && /^[0-9a-f]{64}$/.test(value.text_sha256)
    && typeof value.sharing_available === 'boolean' && member(value.readiness_reason, ['disabled', 'synthetic_test_ready']) && typeof value.is_synthetic === 'boolean'
    && value.max_duration_seconds === 2592000 && value.guardian_verification_available === false && value.private_business_available === false
    && Array.isArray(value.scope_matrix) && value.scope_matrix.length <= 5
    && new Set(value.scope_matrix.map(item => record(item) ? item.resource_type : null)).size === value.scope_matrix.length
    && value.scope_matrix.every(item => record(item) && keys(item, ['resource_type', 'fields', 'actions']) && member(item.resource_type, kinds) && unique(item.fields, ['status', 'version']) && unique(item.actions, ['read', 'list']))
}
export function isGrantData(value: unknown): value is GrantData {
  return record(value) && keys(value, ['id', 'resource_id', 'resource_type', 'resource_version', 'owner_user_id', 'grantee_user_id', 'fields', 'actions', 'created_at', 'expires_at', 'accepted_at', 'revoked_at', 'state', 'version', 'sharing_policy_version', 'is_synthetic', 'access_active'])
    && uuid(value.id) && uuid(value.resource_id) && member(value.resource_type, kinds) && integer(value.resource_version, 1)
    && uuid(value.owner_user_id) && uuid(value.grantee_user_id) && value.owner_user_id !== value.grantee_user_id
    && unique(value.fields, ['status', 'version']) && unique(value.actions, ['read', 'list'])
    && date(value.created_at) && date(value.expires_at) && nullable(value.accepted_at, date) && nullable(value.revoked_at, date)
    && member(value.state, ['pending', 'accepted', 'revoked']) && integer(value.version, 1) && text(value.sharing_policy_version)
    && typeof value.is_synthetic === 'boolean' && typeof value.access_active === 'boolean'
    && (!value.access_active || (value.state === 'accepted' && value.accepted_at !== null && value.revoked_at === null))
}
export function isGrantListData(value: unknown): value is GrantListData {
  if (!record(value) || !keys(value, ['user_id', 'revision', 'actor_declaration_id', 'owner_consent_id', 'sharing_available', 'total', 'items', 'page'])) return false
  const page = value.page
  return uuid(value.user_id) && integer(value.revision) && nullable(value.actor_declaration_id, uuid) && nullable(value.owner_consent_id, uuid)
    && typeof value.sharing_available === 'boolean' && integer(value.total) && Array.isArray(value.items) && value.items.every(isGrantData)
    && record(page) && keys(page, ['limit', 'has_more', 'next_cursor']) && integer(page.limit, 1) && page.limit <= 100 && typeof page.has_more === 'boolean'
    && nullable(page.next_cursor, uuid) && page.has_more === (page.next_cursor !== null) && value.items.length <= page.limit && value.total >= value.items.length
}
export function isGrantMutationData(value: unknown): value is GrantMutationData { return record(value) && keys(value, ['user_id', 'revision', 'grant']) && uuid(value.user_id) && integer(value.revision) && isGrantData(value.grant) }

export function createSharingApi(basePrefix = import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): SharingApi {
  const session = createSessionApi(basePrefix, fetcher) // Also validates the same-origin prefix.
  const prefix = basePrefix.replace(/\/$/, '')
  async function request<T>(path: string, check: (value: unknown) => value is T, options: RequestInit): Promise<T> {
    let response: Response
    try { response = await fetcher(`${prefix}/v2/${path}`, { credentials: 'same-origin', cache: 'no-store', redirect: 'error', ...options }) }
    catch (error) { if (options.signal?.aborted) throw error; throw new SharingError(0) }
    if (response.status !== 200) throw new SharingError(response.status)
    let body: unknown
    try { body = await response.json() } catch { throw new SharingError(200, '共享响应无法读取，本次状态未确认。') }
    if (!record(body) || !keys(body, ['data', 'meta']) || !record(body.meta) || !check(body.data)) throw new SharingError(200, '共享响应不符合契约，本次状态未确认。')
    return body.data
  }
  async function write(path: string, method: 'POST' | 'DELETE', input: CreateGrantInput | AcceptGrantInput | undefined, signal?: AbortSignal) {
    let token: string
    try { token = (await session.csrf(signal)).csrf_token } catch (error) { if (error instanceof SessionError) throw new SharingError(error.status); throw error }
    if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError')
    return request(path, isGrantMutationData, { method, signal, headers: { Accept: 'application/json', 'X-CSRF-Token': token, ...(input ? { 'Content-Type': 'application/json' } : {}) }, ...(input ? { body: JSON.stringify(input) } : {}) })
  }
  function grantId(id: string) { if (!uuid(id)) throw new SharingError(0, '授权标识无效。') }
  return {
    policy: signal => request('sharing/policy', isSharingPolicyData, { method: 'GET', signal, headers: { Accept: 'application/json' } }),
    list: (direction, afterId, signal) => {
      if (!['issued', 'received'].includes(direction) || (afterId !== undefined && !uuid(afterId))) return Promise.reject(new SharingError(0, '共享分页输入无效。'))
      const query = new URLSearchParams({ direction, limit: '20' }); if (afterId) query.set('after_id', afterId)
      return request(`access-grants?${query}`, isGrantListData, { method: 'GET', signal, headers: { Accept: 'application/json' } })
    },
    create: (input, signal) => write('access-grants', 'POST', input, signal),
    accept: async (id, input, signal) => { grantId(id); return write(`access-grants/${id}/accept`, 'POST', input, signal) },
    revoke: async (id, signal) => { grantId(id); return write(`access-grants/${id}`, 'DELETE', undefined, signal) },
  }
}
