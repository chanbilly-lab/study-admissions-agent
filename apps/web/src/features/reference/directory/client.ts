import type { DirectoryFilters, DirectoryInstitution, DirectoryProgram, InstitutionsDirectoryData, ProgramsDirectoryData, ReferenceDirectoryData } from '../../../../../../packages/contracts/referenceDirectory'

export interface InstitutionSearch { q: string; country: string | null; cursor?: string | null }
export interface ProgramSearch extends InstitutionSearch { institution_id: string }
export interface DirectoryApi {
  institutions(query: InstitutionSearch, signal: AbortSignal): Promise<InstitutionsDirectoryData>
  programs(query: ProgramSearch, signal: AbortSignal): Promise<ProgramsDirectoryData>
}
export interface DirectoryRequest { resource: 'institutions' | 'programs'; filters: DirectoryFilters; cursor: string | null }
export class DirectoryError extends Error {
  constructor(public readonly status: number) {
    super(status === 409 ? '目录版本已变化，请重新搜索学校和专业。'
      : status === 422 ? '学校或专业的搜索条件不符合目录要求，请重新填写。'
      : status === 503 ? '可信目录暂不可读取，请稍后重新搜索；不会用研究候选或演示资料替代。'
      : '目录响应未通过身份与发布证明核验，请重新搜索。')
    this.name = 'DirectoryError'
  }
}
function exact(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype
    && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key))
}
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(value)
const integer = (value: unknown, min: number, max = Number.MAX_SAFE_INTEGER): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= min && value <= max
const country = (value: unknown): value is string => typeof value === 'string' && /^[A-Z]{2}$/.test(value)
const cursor = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9_-]{1,512}$/.test(value)
function plain(value: unknown, min: number, max: number): value is string {
  return typeof value === 'string' && [...value].length >= min && [...value].length <= max
    && !/[\u0000-\u001f\u007f-\u009f]/.test(value)
    && !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(value)
}
export function validInstitution(value: unknown): value is DirectoryInstitution {
  return validIdentity(value, false)
}
export function validProgram(value: unknown): value is DirectoryProgram {
  return validIdentity(value, true)
}
function validIdentity(value: unknown, program: boolean): boolean {
  if (!exact(value, ['id', 'name', 'country', 'is_synthetic', 'outcome_subject_ref', 'proof', ...(program ? ['institution_id'] : [])])
    || !uuid(value.id) || value.outcome_subject_ref !== value.id || !plain(value.name, 1, 200) || !value.name.trim()
    || value.name.trimStart().toUpperCase().startsWith('DEMO_') || !country(value.country) || value.is_synthetic !== false
    || program && !uuid(value.institution_id)
    || !exact(value.proof, ['release_id', 'offering_id', 'offering_version', 'identity_evidence_entry_year', 'requirements_version'])) return false
  const proof = value.proof
  return uuid(proof.release_id) && uuid(proof.offering_id) && integer(proof.offering_version, 1, 2_147_483_647)
    && integer(proof.identity_evidence_entry_year, 1, 9999) && typeof proof.requirements_version === 'string' && /^[0-9a-f]{64}$/.test(proof.requirements_version)
}
function validRequest(request: DirectoryRequest): boolean {
  return ['institutions', 'programs'].includes(request.resource) && plain(request.filters.q, 0, 100)
    && (request.filters.country === null || country(request.filters.country))
    && (request.resource === 'institutions' ? request.filters.institution_id === null : uuid(request.filters.institution_id))
    && (request.cursor === null || cursor(request.cursor))
}
export function validateDirectoryData(value: unknown, request: DirectoryRequest): ReferenceDirectoryData {
  if (!validRequest(request) || !exact(value, ['schema_version', 'resource', 'filters', 'items', 'page', 'directory_available', 'missing_reason', 'catalog_watermark', 'expected_total'])
    || value.schema_version !== 'reference.directory.1' || value.resource !== request.resource || value.expected_total !== null
    || typeof value.directory_available !== 'boolean' || !Array.isArray(value.items) || value.items.length > 20
    || !exact(value.filters, ['q', 'country', 'institution_id']) || Object.entries(request.filters).some(([key, expected]) => (value.filters as Record<string, unknown>)[key] !== expected)
    || !exact(value.page, ['limit', 'next_cursor', 'has_more']) || value.page.limit !== 20 || typeof value.page.has_more !== 'boolean'
    || !(value.page.next_cursor === null || cursor(value.page.next_cursor)) || value.page.has_more !== (value.page.next_cursor !== null)
    || request.cursor !== null && value.page.next_cursor === request.cursor) throw new DirectoryError(200)
  if (!value.directory_available) {
    if (value.missing_reason !== 'directory_not_enabled' || value.items.length !== 0 || value.catalog_watermark !== null || value.page.has_more) throw new DirectoryError(200)
  } else {
    if (!integer(value.catalog_watermark, 0) || (value.items.length === 0
      ? value.missing_reason !== 'no_published_matches' || value.page.has_more
      : value.missing_reason !== null)) throw new DirectoryError(200)
  }
  const ids = new Set<string>()
  for (const item of value.items) {
    if (!(request.resource === 'institutions' ? validInstitution(item) : validProgram(item))
      || request.resource === 'programs' && (item as DirectoryProgram).institution_id !== request.filters.institution_id
      || request.filters.country !== null && item.country !== request.filters.country || ids.has(item.id)) throw new DirectoryError(200)
    ids.add(item.id)
  }
  return value as unknown as ReferenceDirectoryData
}
function parseResponse(value: unknown, request: DirectoryRequest, response: Response): ReferenceDirectoryData {
  if (!exact(value, ['data', 'meta']) || !exact(value.meta, ['api_version', 'request_id', 'data_as_of', 'profile_version_id', 'release_id', 'ruleset_version', 'profile_mode', 'data_mode', 'model_mode'])) throw new DirectoryError(200)
  const meta = value.meta
  if (meta.api_version !== 'v2' || meta.data_mode !== 'verified' || meta.model_mode !== 'disabled'
    || typeof meta.request_id !== 'string' || !/^[0-9a-f]{32}$/.test(meta.request_id) || meta.request_id !== response.headers.get('X-Request-ID')
    || ['data_as_of', 'profile_version_id', 'release_id', 'ruleset_version', 'profile_mode'].some(key => meta[key] !== null)
    || !response.headers.get('Cache-Control')?.split(',').some(part => part.trim().toLowerCase() === 'no-store')) throw new DirectoryError(200)
  return validateDirectoryData(value.data, request)
}
export function createDirectoryApi(fetcher: typeof fetch = fetch): DirectoryApi {
  async function read(request: DirectoryRequest, signal: AbortSignal): Promise<ReferenceDirectoryData> {
    if (signal.aborted || !validRequest(request)) throw new DirectoryError(422)
    const frozen: DirectoryRequest = { ...request, filters: { ...request.filters } }
    const url = new URL(`/reference/v2/reference/${frozen.resource}`, window.location.origin)
    for (const [key, value] of Object.entries(frozen.filters)) if (value !== null) url.searchParams.set(key, value)
    url.searchParams.set('limit', '20')
    if (frozen.cursor !== null) url.searchParams.set('cursor', frozen.cursor)
    const abort = new AbortController(), cancel = () => abort.abort()
    signal.addEventListener('abort', cancel, { once: true })
    const timeout = window.setTimeout(cancel, 15000)
    try {
      if (signal.aborted) throw new DirectoryError(0)
      const response = await fetcher(url, { method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error', signal: abort.signal, headers: { Accept: 'application/json' } })
      if (signal.aborted || abort.signal.aborted || response.status !== 200 || response.url !== url.href
        || !/^application\/json(?:;|$)/i.test(response.headers.get('Content-Type') ?? '') || !response.body) {
        if (response.body) await response.body.cancel()
        throw new DirectoryError(response.status)
      }
      const reader = response.body.getReader(), chunks: Uint8Array[] = []
      let size = 0
      try {
        while (true) {
          const next = await reader.read()
          if (next.done) break
          size += next.value.byteLength
          if (size > 65536 || signal.aborted || abort.signal.aborted) { await reader.cancel(); throw new DirectoryError(200) }
          chunks.push(next.value)
        }
      } finally { reader.releaseLock() }
      if (signal.aborted || abort.signal.aborted) throw new DirectoryError(0)
      const bytes = new Uint8Array(size)
      let offset = 0
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength }
      return parseResponse(JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)), frozen, response)
    } catch (error) {
      if (error instanceof DirectoryError) throw error
      throw new DirectoryError(0)
    } finally { window.clearTimeout(timeout); signal.removeEventListener('abort', cancel) }
  }
  return {
    async institutions(query, signal) {
      const data = await read({ resource: 'institutions', filters: { q: query.q.trim(), country: query.country, institution_id: null }, cursor: query.cursor ?? null }, signal)
      if (data.resource !== 'institutions') throw new DirectoryError(200)
      return data
    },
    async programs(query, signal) {
      const data = await read({ resource: 'programs', filters: { q: query.q.trim(), country: query.country, institution_id: query.institution_id }, cursor: query.cursor ?? null }, signal)
      if (data.resource !== 'programs') throw new DirectoryError(200)
      return data
    },
  }
}
