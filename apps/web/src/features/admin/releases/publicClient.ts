import type { PublicOfferingsData } from '../../../../../../packages/contracts/v2/public_catalog/generated'
export type { PublicOfferingsData }
export interface PublicPreviewApi { offerings(year: number, signal?: AbortSignal): Promise<PublicOfferingsData> }
export class PublicPreviewError extends Error {
  constructor(public readonly status: number) {
    super(status === 503 ? '公共目录未开放或暂不可用；不会用管理资料替代。' : '无法确认当前公共目录，请重新读取。')
  }
}
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function hash(value: unknown) { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value) }
function valid(value: unknown): value is PublicOfferingsData {
  if (!record(value) || Object.keys(value).sort().join() !== 'coverage,items,page' || !Array.isArray(value.items) || value.items.length > 100
    || !record(value.page) || typeof value.page.has_more !== 'boolean' || !Number.isInteger(value.page.limit)
    || Number(value.page.limit) < 1 || Number(value.page.limit) > 100 || value.items.length > Number(value.page.limit)
    || !(value.page.next_cursor === null || typeof value.page.next_cursor === 'string')
    || value.page.has_more !== (typeof value.page.next_cursor === 'string' && value.page.next_cursor.length > 0)
    || !record(value.coverage) || !['no_published_records', 'partial'].includes(String(value.coverage.status))
    || value.coverage.expected_total !== null || value.coverage.coverage_ratio !== null || value.coverage.returned_count !== value.items.length
    || value.coverage.status === 'no_published_records' && value.items.length > 0) return false
  const keys = ['content_sha256', 'entry_year', 'facts', 'id', 'institution_id', 'institution_name', 'is_synthetic', 'program_id',
    'program_name', 'release_id', 'release_version', 'requirements_version', 'ruleset_version', 'scope', 'version']
  const factKeys = ['claim_kind', 'cohort_year', 'date_resolution', 'evidence_id', 'fact_type', 'field_key', 'footnote_state',
    'footnote_text', 'missing_reason', 'normalized_value', 'period', 'statistic_denominator', 'statistic_population',
    'statistics_basis', 'survey_period', 'unit', 'unit_code', 'value_kind', 'value_text']
  return value.items.every(item => record(item) && Object.keys(item).length === keys.length && keys.every(key => key in item)
    && typeof item.release_id === 'string' && item.release_version === 1 && typeof item.is_synthetic === 'boolean'
    && typeof item.institution_name === 'string' && typeof item.program_name === 'string' && item.ruleset_version === null
    && Number.isInteger(item.entry_year) && hash(item.requirements_version) && hash(item.content_sha256) && Array.isArray(item.facts)
    && item.facts.length >= 1 && item.facts.length <= 50 && item.facts.every(fact => record(fact)
      && Object.keys(fact).length === factKeys.length && factKeys.every(key => key in fact)
      && typeof fact.field_key === 'string' && (fact.value_text === null || typeof fact.value_text === 'string')
      && ['historical_statistic', 'information', 'minimum_requirement', 'typical_offer', 'unknown'].includes(String(fact.claim_kind))))
}
export function createPublicPreviewApi(fetcher: typeof fetch = fetch): PublicPreviewApi {
  return { async offerings(year, signal) {
    if (!Number.isInteger(year) || year < 1 || year > 9999) throw new PublicPreviewError(422)
    try {
      const response = await fetcher(`/public/v2/offerings?entry_year=${year}&limit=20`, {
        method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error', headers: { Accept: 'application/json' }, signal,
      })
      if (response.status !== 200) throw new PublicPreviewError(response.status)
      const body: unknown = await response.json()
      if (!record(body) || !record(body.meta) || body.meta.api_version !== 'v2' || !valid(body.data)
        || body.data.items.some(item => item.entry_year !== year)) throw new PublicPreviewError(200)
      return body.data
    } catch (error) {
      if (error instanceof PublicPreviewError || signal?.aborted) throw error
      throw new PublicPreviewError(0)
    }
  } }
}
