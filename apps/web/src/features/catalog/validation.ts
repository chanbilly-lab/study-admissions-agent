import type { EvidenceScope, PublicConfigData, PublicDateData, PublicEvidenceData, PublicFactData, PublicOfferingData, PublicOfferingsData } from '../../../../../packages/contracts/v2/public_catalog/generated'

export const scopeFields = ['degree', 'course', 'campus', 'teaching_language', 'progression_pathway', 'intake', 'application_cycle', 'channel', 'course_system', 'pathway', 'applicant_category', 'province', 'exam_system', 'subject_scope', 'batch_group'] as const
export const exact = (v: unknown, keys: readonly string[]): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v) && Object.getPrototypeOf(v) === Object.prototype && Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k))
export const uuid = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(v)
export const hash = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v)
export const integer = (v: unknown, min = 1, max = 2_147_483_647): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= min && v <= max
export const member = (v: unknown, values: readonly string[]): v is string => typeof v === 'string' && values.includes(v)
export const identifier = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$/.test(v)
export function text(v: unknown, max = 4096): v is string {
  return typeof v === 'string' && v.length > 0 && v.length <= max && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(v) && !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(v) && new TextEncoder().encode(v).length <= max
}
const contextText = (v: unknown, max = 4096): v is string => text(v, max) && v.trim().length > 0 && !/[\u0080-\u009f]/.test(v)
export const nullable = (v: unknown, check: (v: unknown) => boolean) => v === null || check(v)
export function calendarDate(v: unknown): v is string {
  if (typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(v)) return false
  const [year, month, day] = v.split('-').map(Number), d = new Date(0)
  d.setUTCFullYear(year!, month! - 1, day!); d.setUTCHours(0, 0, 0, 0)
  return year! >= 1 && d.getUTCFullYear() === year && d.getUTCMonth() + 1 === month && d.getUTCDate() === day
}
export function utc(v: unknown): v is string {
  if (typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(v) || !calendarDate(v.slice(0, 10))) return false
  return Number(v.slice(11, 13)) <= 23 && Number(v.slice(14, 16)) <= 59 && Number(v.slice(17, 19)) <= 59 && Number.isFinite(Date.parse(v))
}
export function validScopeKey(v: unknown, allowUnknown = true): boolean {
  return exact(v, ['status', 'value']) && (v.status === 'known' ? identifier(v.value) : (v.status === 'not_applicable' || allowUnknown && v.status === 'unknown') && v.value === null)
}
export const canonicalScopeKey = (v: unknown): string | null => validScopeKey(v, false) ? (v as { status: string; value: string }).status === 'known' ? 'known:' + (v as { value: string }).value : 'not_applicable' : null
export function validScope(v: unknown): v is EvidenceScope {
  return exact(v, ['dataset_id', 'institution_id', 'program_id', 'country', 'study_level', 'entry_year', ...scopeFields]) && uuid(v.dataset_id) && uuid(v.institution_id) && uuid(v.program_id) && typeof v.country === 'string' && /^[A-Z]{2}$/.test(v.country) && v.study_level === 'undergraduate' && integer(v.entry_year, 1, 9999) && scopeFields.every(k => validScopeKey(v[k]))
}
export async function canonicalHash(v: unknown): Promise<string> {
  let nodes = 0
  const ordered = (value: unknown, depth: number): unknown => {
    if (++nodes > 20000 || depth > 32) throw new Error('Invalid bounded data')
    if (Array.isArray(value)) { if (value.length > 20000) throw new Error('Invalid bounded data'); return value.map(item => ordered(item, depth + 1)) }
    if (value !== null && typeof value === 'object') {
      if (Object.getPrototypeOf(value) !== Object.prototype) throw new Error('Invalid bounded data')
      return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, item]) => [key, ordered(item, depth + 1)]))
    }
    if (value === null || typeof value === 'boolean' || typeof value === 'number' && Number.isSafeInteger(value) || typeof value === 'string' && value.length <= 262144) return value
    throw new Error('Invalid bounded data')
  }
  const bytes = new TextEncoder().encode(JSON.stringify(ordered(v, 0)))
  if (bytes.length > 1_048_576) throw new Error('Invalid bounded data')
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('')
}
export async function scopeFingerprint(scope: EvidenceScope): Promise<string> { if (!validScope(scope)) throw new Error('Invalid scope'); return canonicalHash(scope) }
export const same = (a: unknown, b: unknown): boolean => JSON.stringify(a) === JSON.stringify(b)
export function prefixBase(prefix: string): string {
  if (typeof prefix !== 'string' || !/^(?:\/[A-Za-z0-9_-]+)*\/?$/.test(prefix) || prefix.startsWith('//')) throw new Error('Invalid API prefix')
  return prefix.replace(/\/$/, '') + '/v2'
}
export function validMeta(v: unknown, response: Response, versionId: string | null = null, synthetic: boolean | null = null): boolean {
  return exact(v, ['api_version', 'request_id', 'data_as_of', 'profile_version_id', 'release_id', 'ruleset_version', 'profile_mode', 'data_mode', 'model_mode']) && v.api_version === 'v2' && typeof v.request_id === 'string' && /^[0-9a-f]{32}$/.test(v.request_id) && response.headers.get('X-Request-ID') === v.request_id && response.headers.get('Cache-Control')?.split(',').map(s => s.trim().toLowerCase()).includes('no-store') === true && v.data_as_of === null && v.release_id === null && v.ruleset_version === null && v.profile_version_id === versionId && v.profile_mode === (synthetic === null ? null : synthetic ? 'synthetic' : 'real') && member(v.data_mode, ['demo', 'verified']) && member(v.model_mode, ['disabled', 'mock']) && !(v.data_mode === 'verified' && v.model_mode === 'mock')
}
export function validConfig(v: unknown): v is PublicConfigData {
  return exact(v, ['api_version', 'schema_version', 'contract_stage', 'app_environment', 'query_role', 'data_mode', 'model_mode', 'live_available', 'business_available', 'allow_test_fixture_read', 'demo_banner', 'supported_scope', 'supported_province', 'entry_year']) && v.api_version === 'v2' && v.schema_version === 'v2.t20' && v.contract_stage === 'public_catalog' && member(v.app_environment, ['test', 'development', 'production']) && member(v.query_role, ['demo_only', 'published_readonly']) && member(v.data_mode, ['demo', 'verified']) && member(v.model_mode, ['disabled', 'mock']) && !(v.data_mode === 'verified' && v.model_mode === 'mock') && v.live_available === false && typeof v.business_available === 'boolean' && typeof v.allow_test_fixture_read === 'boolean' && (v.allow_test_fixture_read ? v.app_environment === 'test' && v.data_mode === 'demo' && v.demo_banner === 'DEMO：合成测试资料，不是真实招生依据' : v.demo_banner === null) && Array.isArray(v.supported_scope) && v.supported_scope.length === 0 && v.supported_province === null && v.entry_year === null
}
export function validDate(v: unknown): v is PublicDateData {
  if (!exact(v, ['event_type', 'original_text', 'precision', 'local_date', 'local_time', 'timezone', 'source_alignment', 'conversion_status', 'calculated_utc_instant', 'utc_instant', 'tzdata_version'])) return false
  const localTime = v.local_time === null || typeof v.local_time === 'string' && /^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/.test(v.local_time)
  return member(v.event_type, ['application_deadline', 'application_open', 'enrollment', 'equal_consideration', 'language_supplement', 'materials_deadline', 'offer_acceptance', 'scholarship_deadline', 'score_supplement']) && text(v.original_text, 16000) && [...v.original_text].length <= 4000 && member(v.precision, ['unknown', 'date', 'minute', 'second']) && nullable(v.local_date, calendarDate) && localTime && nullable(v.timezone, a => text(a, 100)) && member(v.source_alignment, ['pending', 'conflict']) && member(v.conversion_status, ['unique', 'date_only', 'unknown', 'missing_timezone', 'ambiguous', 'nonexistent', 'source_conflict', 'out_of_range']) && nullable(v.calculated_utc_instant, utc) && (v.conversion_status === 'unique') === (v.calculated_utc_instant !== null) && v.utc_instant === null && v.tzdata_version === '2026.4' && (v.precision !== 'unknown' || v.local_date === null && v.local_time === null && v.timezone === null) && (v.precision !== 'date' || v.local_date !== null && v.local_time === null) && (!['minute', 'second'].includes(v.precision) || v.local_date !== null && v.local_time !== null) && (v.precision !== 'minute' || typeof v.local_time === 'string' && v.local_time.endsWith(':00'))
}
export function validFact(v: unknown): v is PublicFactData {
  return exact(v, ['fact_type', 'field_key', 'value_kind', 'value_text', 'normalized_value', 'unit', 'missing_reason', 'footnote_state', 'footnote_text', 'claim_kind', 'unit_code', 'period', 'statistics_basis', 'statistic_population', 'statistic_denominator', 'cohort_year', 'survey_period', 'evidence_id', 'date_resolution']) && member(v.fact_type, ['requirement', 'score', 'fee', 'material', 'date', 'statistic']) && identifier(v.field_key) && member(v.value_kind, ['decimal', 'text']) && ['value_text', 'normalized_value', 'unit', 'footnote_text'].every(k => nullable(v[k], contextText)) && nullable(v.missing_reason, a => member(a, ['ambiguous', 'not_applicable', 'not_provided', 'not_published', 'unavailable'])) && (v.value_text === null) === (v.missing_reason !== null) && (v.value_text !== null || v.normalized_value === null) && member(v.footnote_state, ['present', 'none', 'unknown']) && (v.footnote_state === 'present') === (v.footnote_text !== null) && member(v.claim_kind, ['historical_statistic', 'information', 'minimum_requirement', 'typical_offer', 'unknown']) && member(v.unit_code, ['CNY', 'GBP', 'ISO_DATE', 'fraction', 'item', 'people', 'percent', 'points', 'text', 'unknown']) && member(v.period, ['academic_year', 'not_applicable', 'one_time', 'program', 'survey_period', 'unknown']) && member(v.statistics_basis, ['admission', 'employment', 'not_applicable', 'other', 'unknown']) && ['statistic_population', 'statistic_denominator'].every(k => nullable(v[k], a => contextText(a, 512))) && nullable(v.survey_period, a => contextText(a, 100)) && nullable(v.cohort_year, a => integer(a, 1, 9999)) && nullable(v.evidence_id, uuid) && nullable(v.date_resolution, validDate)
}
const namespace = (v: unknown, synthetic: boolean) => text(v, 800) && [...v].length <= 200 && (synthetic ? v.startsWith('DEMO_') : !v.toUpperCase().startsWith('DEMO_'))
export function validOffering(v: unknown): v is PublicOfferingData {
  return exact(v, ['release_id', 'release_version', 'requirements_version', 'content_sha256', 'ruleset_version', 'id', 'version', 'entry_year', 'is_synthetic', 'institution_id', 'institution_name', 'program_id', 'program_name', 'scope', 'facts']) && ['release_id', 'id', 'institution_id', 'program_id'].every(k => uuid(v[k])) && v.release_version === 1 && hash(v.requirements_version) && hash(v.content_sha256) && v.ruleset_version === null && integer(v.version) && integer(v.entry_year, 1, 9999) && typeof v.is_synthetic === 'boolean' && namespace(v.institution_name, v.is_synthetic) && namespace(v.program_name, v.is_synthetic) && validScope(v.scope) && v.scope.entry_year === v.entry_year && v.scope.institution_id === v.institution_id && v.scope.program_id === v.program_id && Array.isArray(v.facts) && v.facts.length >= 1 && v.facts.length <= 50 && v.facts.every(validFact)
}
export const offeringKey = (v: Pick<PublicOfferingData, 'release_id' | 'id' | 'version'>): string => `${v.release_id}:${v.id}:${v.version}`
export function validPage(v: unknown): v is PublicOfferingsData {
  return exact(v, ['items', 'page', 'coverage']) && Array.isArray(v.items) && v.items.length <= 100 && v.items.every(validOffering) && new Set(v.items.map(offeringKey)).size === v.items.length && exact(v.page, ['has_more', 'limit', 'next_cursor']) && integer(v.page.limit, 1, 100) && v.items.length <= v.page.limit && typeof v.page.has_more === 'boolean' && nullable(v.page.next_cursor, a => typeof a === 'string' && /^[!-~]{1,512}$/.test(a)) && v.page.has_more === (v.page.next_cursor !== null) && exact(v.coverage, ['status', 'returned_count', 'expected_total', 'coverage_ratio']) && member(v.coverage.status, ['partial', 'no_published_records']) && v.coverage.returned_count === v.items.length && (v.coverage.status !== 'no_published_records' || v.items.length === 0) && v.coverage.expected_total === null && v.coverage.coverage_ratio === null
}
export async function validEvidence(v: unknown): Promise<boolean> {
  if (!exact(v, ['evidence_id', 'release_id', 'release_version', 'requirements_version', 'is_synthetic', 'offering_id', 'offering_version', 'entry_year', 'language', 'quote', 'document_sha256', 'snippet_sha256', 'locator', 'scope', 'publisher', 'authority_claim']) || !['evidence_id', 'release_id', 'offering_id'].every(k => uuid(v[k])) || v.release_version !== 1 || !hash(v.requirements_version) || typeof v.is_synthetic !== 'boolean' || !integer(v.offering_version) || !integer(v.entry_year, 1, 9999) || !member(v.language, ['en', 'und', 'zh-Hans', 'zh-Hant']) || !text(v.quote) || !hash(v.document_sha256) || !hash(v.snippet_sha256) || !namespace(v.publisher, v.is_synthetic) || !member(v.authority_claim, ['claimed_official', 'not_official', 'unclassified']) || !validScope(v.scope) || v.scope.entry_year !== v.entry_year || !exact(v.locator, ['byte_start', 'byte_end', 'line_start', 'line_end', 'page', 'section', 'location_kind'])) return false
  const l = v.locator, bytes = new TextEncoder().encode(v.quote), lineBreaks = v.quote.match(/\r\n|\r|\n/g)?.length ?? 0
  if (!integer(l.byte_start, 0, 1048575) || !integer(l.byte_end, 1, 1048576) || l.byte_end - l.byte_start !== bytes.length || !integer(l.line_start, 1, 1048577) || !integer(l.line_end, 1, 1048577) || l.line_start > l.line_end || l.line_start > l.byte_start + 1 || l.line_end > l.byte_end || l.line_end - l.line_start > bytes.length - 1 || l.line_end - l.line_start > lineBreaks || l.page !== null || l.section !== null || l.location_kind !== 'utf8_byte_lines') return false
  return v.snippet_sha256 === Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('')
}
