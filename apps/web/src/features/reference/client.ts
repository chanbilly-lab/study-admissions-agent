import type { EmptyReferenceData, LocalCutoffData, ReferenceData } from '../../../../../packages/contracts/reference'

export type StatisticsResource = 'coverage' | 'province_cutoffs' | 'score_distributions' | 'admissions'
export type ReferenceResource = StatisticsResource | 'curricula' | 'outcomes'
export type ReferenceFilters = Record<string, string | number | null>
export interface ReferenceRequest { resource: ReferenceResource; filters: ReferenceFilters }
const endpoints: Record<StatisticsResource, string> = { coverage: 'coverage', province_cutoffs: 'province-cutoffs', score_distributions: 'score-distributions', admissions: 'admissions' }
const failure = () => new Error('参考资料不可用或响应不符合当前参考契约，请稍后重试。')
function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}
function closed(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return record(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key))
}
function boundedText(value: unknown, max: number): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= max && value.trim() === value && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)
}
function utcTimestamp(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value)) return false
  const milliseconds = Date.parse(value)
  return Number.isFinite(milliseconds) && new Date(milliseconds).toISOString().slice(0, 19) === value.slice(0, 19)
}
function officialSourceUrl(value: unknown): value is string {
  return value === 'https://www.zjzs.net/art/2026/6/25/art_155_12467.html'
}
const hash = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
const originalLabels: Record<string, string> = { segment_first: '第一段', segment_second: '第二段', special_category: '特殊类型招生控制线' }
function localCutoffData(data: unknown, filters: ReferenceFilters): LocalCutoffData {
  if (!closed(data, ['schema_version', 'resource', 'filters', 'items', 'page', 'release_id', 'expected_total', 'coverage_ratio', 'missing_reason', 'business_available', 'local_reference_only', 'reference_available', 'source', 'batch'])
    || data.schema_version !== 'reference.cutoffs.local.1' || data.resource !== 'province_cutoffs' || data.local_reference_only !== true
    || data.business_available !== false || data.release_id !== null || data.expected_total !== null || data.coverage_ratio !== null
    || typeof data.reference_available !== 'boolean' || !Array.isArray(data.items) || data.items.length > 3
    || !closed(data.page, ['limit', 'next_cursor', 'has_more']) || data.page.limit !== 20 || data.page.next_cursor !== null || data.page.has_more !== false
    || !closed(data.filters, Object.keys(filters)) || Object.entries(filters).some(([key, expected]) => (data.filters as Record<string, unknown>)[key] !== expected)) throw failure()
  if (!data.reference_available) {
    if (data.items.length !== 0 || data.source !== null || data.batch !== null || typeof data.missing_reason !== 'string'
      || !['not_collected', 'not_applicable', 'scope_not_supported', 'withdrawn', 'review_pending'].includes(data.missing_reason)) throw failure()
    return data as unknown as LocalCutoffData
  }
  if (data.missing_reason !== null || data.items.length !== 3 || filters.year !== 2026 || filters.region_key !== 'cn_region_11'
    || filters.pathway !== 'ordinary_gaokao' || filters.subject_category !== null && filters.subject_category !== '普通类') throw failure()
  const { source, batch } = data
  if (!closed(source, ['publisher', 'url', 'title', 'published_label', 'published_timezone', 'retrieved_at', 'original_sha256', 'body_bytes', 'authority_status', 'public_reuse_permission'])
    || source.publisher !== '浙江省教育考试院' || !officialSourceUrl(source.url) || source.title !== '2026年浙江省普通高校招生各类别分数线'
    || !boundedText(source.published_label, 100) || source.published_timezone !== null || !utcTimestamp(source.retrieved_at)
    || !hash(source.original_sha256) || typeof source.body_bytes !== 'number' || !Number.isSafeInteger(source.body_bytes) || source.body_bytes < 1 || source.body_bytes > 2 * 1024 * 1024
    || source.authority_status !== 'official_site_checked' || source.public_reuse_permission !== 'unknown') throw failure()
  if (!closed(batch, ['batch_id', 'manifest_sha256', 'state', 'review_ref', 'approved_at'])
    || typeof batch.batch_id !== 'string' || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(batch.batch_id)
    || !hash(batch.manifest_sha256) || batch.state !== 'approved_local' || !boundedText(batch.review_ref, 256) || !utcTimestamp(batch.approved_at)) throw failure()
  const kinds = new Set<string>(), keys = new Set<string>()
  for (const item of data.items) {
    if (!closed(item, ['record_key', 'exam_year', 'region_key', 'subject_category', 'line_kind', 'original_label', 'value', 'unit', 'is_synthetic', 'max_score', 'bonus_definition', 'max_score_missing_reason', 'bonus_missing_reason', 'excerpt', 'locator'])
      || !boundedText(item.record_key, 100) || item.record_key.toUpperCase().startsWith('DEMO_') || keys.has(item.record_key) || item.exam_year !== 2026 || item.region_key !== 'cn_region_11' || item.subject_category !== '普通类'
      || typeof item.line_kind !== 'string' || !['segment_first', 'segment_second', 'special_category'].includes(item.line_kind) || kinds.has(item.line_kind)
      || item.original_label !== originalLabels[item.line_kind] || typeof item.value !== 'number' || !Number.isSafeInteger(item.value) || item.value < 0
      || item.unit !== 'points' || item.is_synthetic !== false || item.max_score !== null || item.bonus_definition !== null
      || item.max_score_missing_reason !== 'not_stated_in_source' || item.bonus_missing_reason !== 'not_stated_in_source'
      || !boundedText(item.excerpt, 2048) || !boundedText(item.locator, 512)) throw failure()
    keys.add(item.record_key); kinds.add(item.line_kind)
  }
  return data as unknown as LocalCutoffData
}
export function parseReferenceResponse(value: unknown, resource: ReferenceResource, filters: ReferenceFilters, requestId: string | null): ReferenceData {
  if (!closed(value, ['data', 'meta'])) throw failure()
  const { data, meta } = value
  if (!closed(meta, ['api_version', 'request_id', 'data_as_of', 'profile_version_id', 'release_id', 'ruleset_version', 'profile_mode', 'data_mode', 'model_mode'])
    || meta.api_version !== 'v2' || meta.data_mode !== 'verified' || meta.model_mode !== 'disabled'
    || typeof meta.request_id !== 'string' || !/^[0-9a-f]{32}$/.test(meta.request_id) || meta.request_id !== requestId
    || ['data_as_of', 'profile_version_id', 'release_id', 'ruleset_version', 'profile_mode'].some(key => meta[key] !== null)) throw failure()
  if (resource === 'province_cutoffs' && record(data) && data.schema_version === 'reference.cutoffs.local.1') return localCutoffData(data, filters)
  if (!closed(data, ['schema_version', 'resource', 'filters', 'items', 'page', 'release_id', 'expected_total', 'coverage_ratio', 'missing_reason', 'business_available'])
    || data.schema_version !== 'reference.minimal.1' || data.resource !== resource || data.business_available !== false
    || data.release_id !== null || data.expected_total !== null || data.coverage_ratio !== null
    || !Array.isArray(data.items) || data.items.length !== 0
    || typeof data.missing_reason !== 'string' || !['source_not_enabled', 'not_applicable', 'scope_incomplete'].includes(data.missing_reason)
    || !closed(data.page, ['limit', 'next_cursor', 'has_more']) || data.page.limit !== 20 || data.page.next_cursor !== null || data.page.has_more !== false
    || !closed(data.filters, Object.keys(filters)) || Object.entries(filters).some(([key, expected]) => (data.filters as Record<string, unknown>)[key] !== expected)) throw failure()
  return data as unknown as EmptyReferenceData
}
export async function fetchReference({ resource, filters }: ReferenceRequest, signal: AbortSignal): Promise<ReferenceData> {
  if (signal.aborted) throw failure()
  let endpoint: string
  if (resource === 'curricula') {
    if (typeof filters.program_id !== 'string' || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(filters.program_id)) throw failure()
    endpoint = `programs/${filters.program_id}/curricula`
  } else if (resource === 'outcomes') endpoint = 'outcomes'
  else endpoint = endpoints[resource]
  const url = new URL(`/reference/v2/reference/${endpoint}`, window.location.origin)
  for (const [key, value] of Object.entries(filters)) if (value !== null && key !== 'program_id') url.searchParams.set(key, String(value))
  url.searchParams.set('limit', '20')
  const response = await fetch(url, { method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error', signal, headers: { Accept: 'application/json' } })
  if (signal.aborted || !response.ok || response.url !== url.href || !/^application\/json(?:;|$)/i.test(response.headers.get('Content-Type') ?? '') || !response.body) throw failure()
  const reader = response.body.getReader(), parts: Uint8Array[] = []
  let size = 0
  try {
    while (true) {
      const chunk = await reader.read()
      if (chunk.done) break
      size += chunk.value.byteLength
      if (size > 65536) { await reader.cancel(); throw failure() }
      parts.push(chunk.value)
    }
  } finally { reader.releaseLock() }
  if (signal.aborted) throw failure()
  const bytes = new Uint8Array(size)
  let offset = 0
  for (const part of parts) { bytes.set(part, offset); offset += part.byteLength }
  return parseReferenceResponse(JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)), resource, filters, response.headers.get('X-Request-ID'))
}
