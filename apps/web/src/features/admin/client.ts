import type {
  AdminContextData, AdminSourceData, AdminSourceRegisterInput, AdminSourceRevisionInput,
  AdminSourceFileInput, AdminImportInput, SourceDefinition, FileData, ImportResult,
} from '../../../../../packages/contracts/v2/admin/generated'
import { createSessionApi, SessionError } from '../auth/client'

export type { AdminContextData, AdminSourceData, AdminSourceRegisterInput, AdminSourceRevisionInput,
  AdminSourceFileInput, AdminImportInput, SourceDefinition, FileData, ImportResult }
export const MAX_CONTENT_BYTES = 1_048_576
export const sourceDefinitionKeys = ['publisher', 'entry_url', 'purpose', 'data_type', 'scope_note', 'authority_claim',
  'manual_import_permission', 'publication_permission', 'automated_fetch_permission', 'license_basis',
  'permission_record_reference', 'recheck_days', 'manual_import_enabled'] as const
export function uuid(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value)
}
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function exact(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return record(value) && Object.keys(value).length === keys.length && keys.every(key => key in value)
}
function integer(value: unknown, min = 1, max = 2_147_483_647): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= min && value <= max
}
function utc(value: unknown): value is string {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value))
}
function hash(value: unknown): value is string { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value) }
function text(value: unknown, max: number): value is string { return typeof value === 'string' && value.length > 0 && value.length <= max }
function nullableText(value: unknown, max: number) { return value === null || text(value, max) }

export class AdminError extends Error {
  constructor(public readonly status: number, message?: string) {
    super(message ?? ({ 401: '当前会话已失效，请重新登录。', 403: '服务器拒绝管理操作。仅当前受权数据管理员且认证强度有效时可操作。',
      404: '管理入口或指定记录不存在。', 409: '版本、来源或权限已变化。请重新读取并再次确认，不会覆盖旧版本。',
      413: '原文超出 1 MiB 上限，未确认保存。', 422: '输入未通过服务端校验，本次操作未确认成功。',
      503: '管理服务未开放或暂不可用，不会回退到演示数据。' }[status] ?? '请求结果无法确认，请重新读取状态。'))
    this.name = 'AdminError'
  }
}

export interface AdminApi {
  context(signal?: AbortSignal): Promise<AdminContextData>
  register(input: AdminSourceRegisterInput, signal?: AbortSignal): Promise<AdminSourceData>
  source(id: string, version?: number, signal?: AbortSignal): Promise<AdminSourceData>
  revise(id: string, input: AdminSourceRevisionInput, signal?: AbortSignal): Promise<AdminSourceData>
  upload(input: AdminSourceFileInput, signal?: AbortSignal): Promise<FileData>
  import(input: AdminImportInput, key: string, signal?: AbortSignal): Promise<ImportResult>
  result(id: string, signal?: AbortSignal): Promise<ImportResult>
}

function contextData(value: unknown): value is AdminContextData {
  return exact(value, ['schema_version', 'can_manage_sources', 'can_import', 'is_synthetic']) && value.schema_version === 'v2.t21'
    && ['can_manage_sources', 'can_import', 'is_synthetic'].every(key => typeof value[key] === 'boolean')
}
function sourceData(value: unknown): value is AdminSourceData {
  const keys = [...sourceDefinitionKeys, 'id', 'dataset_id', 'source_id', 'version', 'is_synthetic', 'created_at',
    'permission_reviewed_at', 'recheck_due_at', 'auto_fetch_enabled', 'dataset_revision']
  if (!exact(value, keys) || !['id', 'dataset_id', 'source_id'].every(key => uuid(value[key]))
    || !integer(value.version) || !integer(value.dataset_revision) || typeof value.is_synthetic !== 'boolean'
    || !utc(value.created_at) || !utc(value.recheck_due_at) || !(value.permission_reviewed_at === null || utc(value.permission_reviewed_at))
    || value.auto_fetch_enabled !== false || value.purpose !== 'admissions_reference'
    || !text(value.publisher, 200) || !text(value.entry_url, 2048) || !text(value.scope_note, 1000)
    || !['entry_requirements', 'application_dates', 'regional_cutoffs', 'admission_observations', 'curriculum', 'outcomes', 'institution_directory'].includes(String(value.data_type))
    || !['unclassified', 'claimed_official', 'not_official'].includes(String(value.authority_claim))
    || !['manual_import_permission', 'publication_permission', 'automated_fetch_permission'].every(key => ['pending', 'denied', 'granted'].includes(String(value[key])))
    || !nullableText(value.license_basis, 2000) || !nullableText(value.permission_record_reference, 100)
    || !integer(value.recheck_days, 1, 730) || typeof value.manual_import_enabled !== 'boolean') return false
  return true
}
function fileData(value: unknown): value is FileData {
  return exact(value, ['id', 'namespace', 'is_synthetic', 'status', 'media_type', 'size_bytes', 'sha256', 'created_at', 'expires_at'])
    && uuid(value.id) && value.namespace === 'source_quarantine' && typeof value.is_synthetic === 'boolean'
    && value.status === 'quarantined' && ['application/json', 'text/csv'].includes(String(value.media_type))
    && integer(value.size_bytes, 1, MAX_CONTENT_BYTES) && hash(value.sha256) && utc(value.created_at) && utc(value.expires_at)
}
const errorFields = ['document', 'offering_id', 'offering_version', 'entry_year', 'source_record_reference', 'fact_type',
  'field_key', 'value_kind', 'value_text', 'unit', 'missing_reason', 'footnote_state', 'footnote_text', 'locator']
const errorCodes = ['INVALID_ENCODING', 'INPUT_TOO_LARGE', 'INVALID_STRUCTURE', 'EMPTY_IMPORT', 'TOO_MANY_ROWS', 'INVALID_HEADER',
  'DUPLICATE_KEY', 'MISSING_FIELD', 'UNEXPECTED_FIELD', 'INVALID_FIELD', 'FIELD_TOO_LARGE', 'INVALID_INTEGER', 'INVALID_UUID',
  'INVALID_DECIMAL', 'MISSING_VALUE_REASON', 'INVALID_FOOTNOTE', 'SCOPE_MISMATCH', 'NAMESPACE_MISMATCH']
function importData(value: unknown): value is ImportResult {
  if (!exact(value, ['id', 'status', 'total_rows', 'staged_rows', 'error_count', 'errors', 'replayed']) || !uuid(value.id)
    || !['staged', 'rejected'].includes(String(value.status)) || !(value.total_rows === null || integer(value.total_rows, 0, 200))
    || !integer(value.staged_rows, 0, 200) || !integer(value.error_count, 0, 2800) || typeof value.replayed !== 'boolean'
    || !Array.isArray(value.errors) || value.errors.length !== value.error_count || value.errors.some(error =>
      !exact(error, ['row_number', 'field', 'code']) || !integer(error.row_number, 0, 201)
      || !errorFields.includes(String(error.field)) || !errorCodes.includes(String(error.code)))) return false
  return value.status === 'staged' ? value.total_rows !== null && Number(value.total_rows) > 0 && value.staged_rows === value.total_rows && value.error_count === 0
    : value.staged_rows === 0 && Number(value.error_count) > 0
}

export function createAdminApi(prefix = import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): AdminApi {
  const session = createSessionApi(prefix, fetcher) // validates the same-origin prefix, never stores proof
  const base = `${prefix.replace(/\/$/, '')}/v2/admin`
  async function request<T>(path: string, validate: (data: unknown) => data is T, signal?: AbortSignal,
    method = 'GET', input?: unknown, key?: string): Promise<T> {
    let token: string | undefined
    try {
      if (method !== 'GET') token = (await session.csrf(signal)).csrf_token
      const headers: Record<string, string> = { Accept: 'application/json' }
      if (token) headers['X-CSRF-Token'] = token
      if (input !== undefined) headers['Content-Type'] = 'application/json'
      if (key) headers['Idempotency-Key'] = key
      const response = await fetcher(`${base}/${path}`, { method, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
        headers, ...(input !== undefined ? { body: JSON.stringify(input) } : {}), signal })
      if (response.status !== 200) throw new AdminError(response.status)
      let body: unknown
      try { body = await response.json() } catch { throw new AdminError(200, '响应无法读取，本次操作未确认。') }
      if (!exact(body, ['data', 'meta']) || !record(body.meta) || body.meta.api_version !== 'v2'
        || !/^[0-9a-f]{32}$/.test(String(body.meta.request_id)) || !validate(body.data)) {
        throw new AdminError(200, '响应与管理契约不一致，本次操作未确认。')
      }
      return body.data
    } catch (error) {
      if (error instanceof AdminError) throw error
      if (error instanceof SessionError) throw new AdminError(error.status)
      if (signal?.aborted) throw error
      throw new AdminError(0, '无法连接管理服务，本次操作未确认。')
    } finally { token = undefined }
  }
  function confirmed(input: { confirmed: true }) { if (input.confirmed !== true) throw new AdminError(422, '请先明确确认本次操作。') }
  function reference(id: string) { if (!uuid(id)) throw new AdminError(422, '请输入规范 UUID 标识。') }
  return {
    context: signal => request('context', contextData, signal),
    register(input, signal) { confirmed(input); return request('sources', sourceData, signal, 'POST', input) },
    source(id, version, signal) { reference(id); return request(`sources/${id}${version !== undefined ? `?version=${version}` : ''}`, sourceData, signal) },
    revise(id, input, signal) { reference(id); confirmed(input); return request(`sources/${id}`, sourceData, signal, 'PUT', input) },
    upload(input, signal) { confirmed(input); return request('source-files', fileData, signal, 'POST', input) },
    import(input, key, signal) { confirmed(input); if (!uuid(key)) throw new AdminError(422, '幂等请求标识无效。'); return request('imports', importData, signal, 'POST', input, key) },
    result(id, signal) { reference(id); return request(`imports/${id}`, importData, signal) },
  }
}

export function contentBytes(value: string): Uint8Array {
  if (/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?:^|[^\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(value)) throw new AdminError(422, '原文含无效 Unicode，未转换或替换。')
  const bytes = new TextEncoder().encode(value)
  if (!bytes.length || bytes.length > MAX_CONTENT_BYTES) throw new AdminError(413, '原文须为 1 字节至 1 MiB，未截断内容。')
  return bytes
}
export async function readOriginal(file: File): Promise<string> {
  if (!file.size || file.size > MAX_CONTENT_BYTES) throw new AdminError(413)
  const bytes = typeof file.arrayBuffer === 'function' ? await file.arrayBuffer() : await new Promise<ArrayBuffer>((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(reader.result as ArrayBuffer); reader.onerror = () => reject(new AdminError(422)); reader.readAsArrayBuffer(file)
  })
  try { return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes) }
  catch { throw new AdminError(422, '文件不是有效 UTF-8，未替换坏字节。') }
}
