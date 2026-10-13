import type {
  ReviewContextData, ImportRowsData, DocumentData, VersionData, SnippetData, TypedCandidate, Classification,
  ReviewCandidatesData, ReviewDetailData, ReviewDecisionData, CurrentReleaseData, PublishPrecheckData, ReleaseData,
  AdminDocumentInput, AdminVersionInput, AdminSnippetInput, AdminFactInput, AdminReviewInput, AdminPublishInput, AdminWithdrawalInput,
} from '../../../../../../packages/contracts/v2/admin_review/generated'
import { createSessionApi, SessionError, type SessionData } from '../../auth/client'
import { uuid } from '../client'
export type { ReviewContextData, ImportRowsData, DocumentData, VersionData, SnippetData, TypedCandidate, Classification,
  ReviewCandidatesData, ReviewDetailData, ReviewDecisionData, CurrentReleaseData, PublishPrecheckData, ReleaseData,
  AdminDocumentInput, AdminVersionInput, AdminSnippetInput, AdminFactInput, AdminReviewInput, AdminPublishInput, AdminWithdrawalInput, SessionData }
export class ReviewWorkspaceError extends Error {
  constructor(public readonly status: number) {
    super(({ 401: '当前会话已失效，请重新登录。', 403: '服务端拒绝当前操作，请检查独立审核职责与强认证。',
      404: '指定对象不存在或不可读取。', 409: '版本、冲突集合或资料期限已变化。请重新读取并逐项确认，未覆盖已有记录。',
      422: '本次输入、定位或逐项检查不完整，服务端未确认成功。', 503: '审核或发布服务未开放或暂不可用，不会使用演示回退。' }[status]
      ?? '本次结果未确认，请重新读取状态。'))
  }
}
export interface ReviewWorkspaceApi {
  context(signal?: AbortSignal): Promise<ReviewContextData>
  rows(id: string, cursor?: string, signal?: AbortSignal): Promise<ImportRowsData>
  document(input: AdminDocumentInput, signal?: AbortSignal): Promise<DocumentData>
  version(input: AdminVersionInput, signal?: AbortSignal): Promise<VersionData>
  snippet(input: AdminSnippetInput, signal?: AbortSignal): Promise<SnippetData>
  fact(input: AdminFactInput, signal?: AbortSignal): Promise<TypedCandidate>
  candidates(dataset: string, year: number, cursor?: string, signal?: AbortSignal): Promise<ReviewCandidatesData>
  detail(id: string, signal?: AbortSignal): Promise<ReviewDetailData>
  review(input: AdminReviewInput, signal?: AbortSignal): Promise<ReviewDecisionData>
  precheck(input: AdminPublishInput, signal?: AbortSignal): Promise<PublishPrecheckData>
  publish(input: AdminPublishInput, key: string, signal?: AbortSignal): Promise<ReleaseData>
  current(dataset: string, year: number, signal?: AbortSignal): Promise<CurrentReleaseData>
  release(id: string, signal?: AbortSignal): Promise<ReleaseData>
  withdraw(id: string, input: AdminWithdrawalInput, signal?: AbortSignal): Promise<ReleaseData>
}
export function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function exact(value: unknown, keys: readonly string[]): value is Record<string, unknown> { return record(value) && Object.keys(value).length === keys.length && keys.every(key => key in value) }
const positive = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value >= 1 && value <= 2147483647
const hash = (value: unknown) => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
const cursor = (value: unknown) => value === null || typeof value === 'string' && value.length > 0 && value.length <= 512
const marker = (value: Record<string, unknown>) => typeof value.is_synthetic === 'boolean'
function context(value: unknown): value is ReviewContextData { return exact(value, ['schema_version', 'can_prepare', 'can_review', 'can_publish', 'can_withdraw', 'is_synthetic'])
  && value.schema_version === 'v2.t22' && ['can_prepare', 'can_review', 'can_publish', 'can_withdraw', 'is_synthetic'].every(key => typeof value[key] === 'boolean') }
function rows(value: unknown): value is ImportRowsData { return exact(value, ['import_id', 'dataset_id', 'source_id', 'source_version', 'file_id', 'file_sha256', 'format', 'total_rows', 'rows', 'next_cursor', 'is_synthetic'])
  && ['import_id', 'dataset_id', 'source_id', 'file_id'].every(key => uuid(value[key])) && positive(value.source_version) && hash(value.file_sha256)
  && ['json', 'csv'].includes(String(value.format)) && positive(value.total_rows) && Number(value.total_rows) <= 200 && cursor(value.next_cursor) && marker(value)
  && Array.isArray(value.rows) && value.rows.length <= 20 && value.rows.every(item => exact(item, ['row_id', 'row']) && uuid(item.row_id)
    && record(item.row) && uuid(item.row.offering_id) && positive(item.row.offering_version) && positive(item.row.entry_year) && positive(item.row.row_number)) }
function document(value: unknown): value is DocumentData { return exact(value, ['id', 'dataset_id', 'source_id', 'source_version', 'document_reference', 'language', 'is_synthetic', 'current_version', 'created_at'])
  && uuid(value.id) && uuid(value.dataset_id) && uuid(value.source_id) && positive(value.source_version) && marker(value)
  && Number.isInteger(value.current_version) && Number(value.current_version) >= 0 && typeof value.document_reference === 'string' && typeof value.language === 'string' }
function version(value: unknown): value is VersionData { return exact(value, ['id', 'document_id', 'version', 'document_sha256', 'size_bytes', 'media_type', 'is_synthetic', 'created_at'])
  && uuid(value.id) && uuid(value.document_id) && positive(value.version) && positive(value.size_bytes) && Number(value.size_bytes) <= 1048576
  && hash(value.document_sha256) && marker(value) && ['application/json', 'text/csv'].includes(String(value.media_type)) }
function snippet(value: unknown): value is SnippetData { return record(value) && uuid(value.id) && uuid(value.document_id) && uuid(value.offering_id)
  && positive(value.document_version) && positive(value.offering_version) && positive(value.entry_year) && marker(value)
  && typeof value.text === 'string' && new TextEncoder().encode(value.text).length <= 4096 && hash(value.document_sha256) && hash(value.snippet_sha256)
  && record(value.locator) && value.locator.page === null && value.locator.section === null && value.locator.location_kind === 'utf8_byte_lines'
  && record(value.scope) && !('file_id' in value) && !('path' in value) }
function fact(value: unknown): value is TypedCandidate { return record(value) && uuid(value.id) && value.version === 1 && uuid(value.import_id)
  && uuid(value.import_row_id) && uuid(value.dataset_id) && uuid(value.offering_id) && positive(value.offering_version) && positive(value.entry_year)
  && marker(value) && value.hard_rule === false && value.publication_eligible === false && ['draft', 'review_required', 'conflicted'].includes(String(value.state))
  && record(value.classification) && Array.isArray(value.conflicting_ids) && value.conflicting_ids.length <= 200 && value.conflicting_ids.every(uuid) }
function candidates(value: unknown): value is ReviewCandidatesData { return exact(value, ['dataset_id', 'entry_year', 'dataset_revision', 'items', 'next_cursor'])
  && uuid(value.dataset_id) && positive(value.entry_year) && positive(value.dataset_revision) && cursor(value.next_cursor) && Array.isArray(value.items)
  && value.items.length <= 100 && value.items.every(item => record(item) && uuid(item.fact_id) && item.version === 1 && uuid(item.dataset_id) && positive(item.entry_year) && marker(item)) }
function detail(value: unknown): value is ReviewDetailData { return exact(value, ['fact', 'case', 'evidence', 'scope', 'gaps', 'conflicts']) && fact(value.fact)
  && record(value.case) && Number.isInteger(value.case.case_revision) && Number(value.case.case_revision) >= 0 && typeof value.case.current_approved === 'boolean'
  && record(value.scope) && (value.evidence === null || snippet(value.evidence)) && Array.isArray(value.gaps) && value.gaps.every(item => typeof item === 'string')
  && Array.isArray(value.conflicts) && value.conflicts.length <= 200 && value.conflicts.every(item => record(item) && uuid(item.fact_id) && item.version === 1) }
function decision(value: unknown): value is ReviewDecisionData { return record(value) && uuid(value.decision_id) && uuid(value.case_id) && uuid(value.fact_id)
  && positive(value.case_revision) && ['approve', 'return'].includes(String(value.action)) && Array.isArray(value.checks) && value.checks.length === 10
  && typeof value.current_approved === 'boolean' && marker(value) }
function head(value: unknown): value is CurrentReleaseData { return exact(value, ['dataset_id', 'entry_year', 'dataset_revision', 'release'])
  && uuid(value.dataset_id) && positive(value.entry_year) && positive(value.dataset_revision) && (value.release === null || record(value.release)
    && uuid(value.release.release_id) && value.release.version === 1 && positive(value.release.state_revision) && hash(value.release.requirements_version) && marker(value.release)) }
function precheck(value: unknown): value is PublishPrecheckData { return exact(value, ['status', 'request_sha256', 'dataset_revision', 'member_count', 'checked_at', 'is_synthetic'])
  && value.status === 'precheck_passed' && hash(value.request_sha256) && positive(value.dataset_revision) && positive(value.member_count) && Number(value.member_count) <= 50 && marker(value) }
function release(value: unknown): value is ReleaseData { return record(value) && uuid(value.release_id) && value.version === 1 && uuid(value.dataset_id)
  && positive(value.entry_year) && positive(value.state_revision) && ['published', 'withdrawn', 'replaced'].includes(String(value.state)) && marker(value)
  && value.ruleset_version === null && hash(value.content_sha256) && hash(value.requirements_version) && Array.isArray(value.members) && value.members.length >= 1 && value.members.length <= 50 }
export function createReviewWorkspaceApi(prefix = import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): ReviewWorkspaceApi {
  const session = createSessionApi(prefix, fetcher), base = `${prefix.replace(/\/$/, '')}/v2/admin`
  const ref = (id: string) => { if (!uuid(id)) throw new ReviewWorkspaceError(422) }
  async function request<T>(path: string, validate: (value: unknown) => value is T, signal?: AbortSignal, input?: { confirmed: true }, key?: string): Promise<T> {
    let proof: string | undefined
    try {
      if (input) { if (input.confirmed !== true) throw new ReviewWorkspaceError(422); proof = (await session.csrf(signal)).csrf_token }
      const headers: Record<string, string> = { Accept: 'application/json' }
      if (proof) { headers['X-CSRF-Token'] = proof; headers['Content-Type'] = 'application/json' }
      if (key) headers['Idempotency-Key'] = key
      const response = await fetcher(`${base}/${path}`, { method: input ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
        headers, ...(input ? { body: JSON.stringify(input) } : {}), signal })
      if (response.status !== 200) throw new ReviewWorkspaceError(response.status)
      const body: unknown = await response.json()
      if (!exact(body, ['data', 'meta']) || !record(body.meta) || body.meta.api_version !== 'v2' || !/^[a-f0-9]{32}$/.test(String(body.meta.request_id))
        || !validate(body.data)) throw new ReviewWorkspaceError(200)
      return body.data
    } catch (error) {
      if (error instanceof ReviewWorkspaceError || signal?.aborted) throw error
      if (error instanceof SessionError) throw new ReviewWorkspaceError(error.status)
      throw new ReviewWorkspaceError(0)
    } finally { proof = undefined }
  }
  const scoped = (dataset: string, year: number, token?: string) => {
    ref(dataset); if (!Number.isInteger(year) || year < 1 || year > 9999) throw new ReviewWorkspaceError(422)
    return `dataset_id=${dataset}&entry_year=${year}${token ? `&cursor=${encodeURIComponent(token)}` : ''}`
  }
  return {
    context: signal => request('review-context', context, signal),
    rows(id, token, signal) { ref(id); return request(`imports/${id}/rows?limit=20${token ? `&cursor=${encodeURIComponent(token)}` : ''}`, rows, signal) },
    document: (input, signal) => request('evidence/documents', document, signal, input),
    version: (input, signal) => request('evidence/versions', version, signal, input),
    snippet: (input, signal) => request('evidence/snippets', snippet, signal, input),
    fact: (input, signal) => request('facts', fact, signal, input),
    candidates: (dataset, year, token, signal) => request(`review-candidates?${scoped(dataset, year, token)}&limit=100`, candidates, signal),
    detail(id, signal) { ref(id); return request(`review-candidates/${id}`, detail, signal) },
    review: (input, signal) => request('review-decisions', decision, signal, input),
    precheck: (input, signal) => request('releases/precheck', precheck, signal, input),
    publish(input, key, signal) { if (!uuid(key)) throw new ReviewWorkspaceError(422); return request('releases', release, signal, input, key) },
    current: (dataset, year, signal) => request(`releases/current?${scoped(dataset, year)}`, head, signal),
    release(id, signal) { ref(id); return request(`releases/${id}`, release, signal) },
    withdraw(id, input, signal) { ref(id); return request(`releases/${id}/withdraw`, release, signal, input) },
  }
}
export function strictInteger(value: string | number, min = 1, max = 2147483647): number | null {
  const raw = String(value); if (!/^[0-9]+$/.test(raw)) return null
  const number = Number(raw); return Number.isSafeInteger(number) && number >= min && number <= max ? number : null
}
