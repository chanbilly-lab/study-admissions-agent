import type { ListV2PublicOfferingsQuery, PublicConfigData, PublicEvidenceData, PublicOfferingData, PublicOfferingsData } from '../../../../../packages/contracts/v2/public_catalog/generated'
import { canonicalScopeKey, exact, integer, offeringKey, prefixBase, uuid, validConfig, validEvidence, validMeta, validPage } from './validation'
export type { ListV2PublicOfferingsQuery, PublicConfigData, PublicEvidenceData, PublicOfferingData, PublicOfferingsData }
export { offeringKey, offeringKey as offeringsKey, scopeFingerprint } from './validation'
export class CatalogError extends Error {
  constructor(public readonly status: number) { super(({ 404: '指定公开资料不存在或不可读取。', 409: '公开版本或分页已变化，请明确重新查询。', 422: '请填写明确年份和合法范围。', 503: '公开目录尚未开放或暂不可用。' }[status] ?? '公开资料未通过验证，本次结果未确认。')); this.name = 'CatalogError' }
}
export interface CatalogApi {
  config(signal?: AbortSignal): Promise<PublicConfigData>
  offerings(query: ListV2PublicOfferingsQuery, signal?: AbortSignal): Promise<PublicOfferingsData>
  evidence(evidenceId: string, releaseId: string, signal?: AbortSignal): Promise<PublicEvidenceData>
}
const queryKeys = ['entry_year', 'country', 'study_level', 'province', 'pathway', 'course_system', 'applicant_category', 'release_id', 'limit', 'cursor']
export function validQuery(value: unknown): value is ListV2PublicOfferingsQuery {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype || Object.keys(value).some(k => !queryKeys.includes(k))) return false
  const v = value as Record<string, unknown>
  return integer(v.entry_year, 1, 9999) && (v.limit === undefined || integer(v.limit, 1, 100)) && (v.country == null || typeof v.country === 'string' && /^[A-Z]{2}$/.test(v.country)) && (v.study_level == null || v.study_level === 'undergraduate') && (v.release_id == null || uuid(v.release_id)) && (v.cursor == null || typeof v.cursor === 'string' && /^[!-~]{1,512}$/.test(v.cursor)) && ['province', 'pathway', 'course_system', 'applicant_category'].every(k => v[k] == null || typeof v[k] === 'string' && (v[k] === 'not_applicable' || /^known:[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$/.test(v[k])))
}
export function matchesQuery(item: PublicOfferingData, q: ListV2PublicOfferingsQuery): boolean {
  return item.entry_year === q.entry_year && (q.country == null || item.scope.country === q.country) && (q.study_level == null || item.scope.study_level === q.study_level) && (q.release_id == null || item.release_id === q.release_id) && (['province', 'pathway', 'course_system', 'applicant_category'] as const).every(k => q[k] == null || canonicalScopeKey(item.scope[k]) === q[k])
}
export function createCatalogApi(prefix = '/public', fetcher: typeof fetch = fetch): CatalogApi {
  let base: string
  try { base = prefixBase(prefix) } catch { throw new CatalogError(422) }
  async function request<T>(path: string, validate: (v: unknown) => boolean | Promise<boolean>, signal?: AbortSignal): Promise<T> {
    try {
      const response = await fetcher(base + path, { method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error', headers: { Accept: 'application/json' }, signal })
      if (response.status !== 200) throw new CatalogError(response.status)
      const body: unknown = await response.json()
      if (!exact(body, ['data', 'meta']) || !validMeta(body.meta, response) || !await validate(body.data)) throw new CatalogError(200)
      const meta = body.meta as { data_mode: string; model_mode: string }
      if (path === '/config' ? (body.data as PublicConfigData).data_mode !== meta.data_mode || (body.data as PublicConfigData).model_mode !== meta.model_mode : path.startsWith('/offerings?') ? (body.data as PublicOfferingsData).items.some(item => item.is_synthetic !== (meta.data_mode === 'demo')) : (body.data as PublicEvidenceData).is_synthetic !== (meta.data_mode === 'demo')) throw new CatalogError(200)
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      return body.data as T
    } catch (error) { if (error instanceof CatalogError || signal?.aborted) throw error; throw new CatalogError(0) }
  }
  return {
    config: signal => request('/config', validConfig, signal),
    offerings(query, signal) {
      if (!validQuery(query)) throw new CatalogError(422)
      const frozen: ListV2PublicOfferingsQuery = JSON.parse(JSON.stringify(query)), params = new URLSearchParams()
      for (const [k, v] of Object.entries(frozen)) if (v !== null && v !== undefined) params.set(k, String(v))
      return request('/offerings?' + params, v => validPage(v) && v.page.limit === (frozen.limit ?? 20) && v.items.every(item => matchesQuery(item, frozen)), signal)
    },
    evidence(id, releaseId, signal) {
      if (!uuid(id) || !uuid(releaseId)) throw new CatalogError(422)
      return request('/evidence/' + id + '?release_id=' + releaseId, async v => await validEvidence(v) && (v as PublicEvidenceData).evidence_id === id && (v as PublicEvidenceData).release_id === releaseId, signal)
    },
  }
}
