import type { CitationData, QAAnswerData, QAContextData, RetrievalRequest } from '../../../../../packages/contracts/v2/qa/generated'
import type { PublicOfferingData } from '../../../../../packages/contracts/v2/public_catalog/generated'
import { canonicalHash, exact, hash, identifier, integer, member, nullable, scopeFields, text, utc, validEvidence, validFact, validOffering, validScope, validScopeKey } from '../catalog/validation'

export const intents = ['requirements', 'materials', 'dates', 'fees', 'background'] as const
export const adviceCodes = ['REVIEW_SOURCE', 'CONFIRM_WITH_INSTITUTION', 'MISSING_EVIDENCE'] as const
export const unknownCodes = ['SCOPE_UNKNOWN', 'RELEASE_UNAVAILABLE', 'TARGET_MISMATCH', 'NO_MATCHING_FACTS', 'NO_PUBLIC_EVIDENCE', 'VALUE_UNAVAILABLE', 'DATE_UNRESOLVED', 'LIMIT_EXCEEDED'] as const
export const uuid4 = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(v)
const boundedText = (v: unknown, maximum: number): v is string => text(v, maximum * 4) && [...v].length <= maximum && v.trim().length > 0 && !/[\u0080-\u009f\r]/.test(v)
const scopeKeys = ['institution_id', 'program_id', 'country', 'study_level', 'entry_year', ...scopeFields]

export function sameValue(a: unknown, b: unknown): boolean {
  const sort = (v: unknown): unknown => Array.isArray(v) ? v.map(sort) : v !== null && typeof v === 'object' ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, value]) => [key, sort(value)])) : v
  return JSON.stringify(sort(a)) === JSON.stringify(sort(b))
}
export function validRequest(v: unknown): v is RetrievalRequest {
  if (!exact(v, ['release_id', 'offering_id', 'offering_version', 'entry_year', 'scope', 'intent', 'keywords']) || !uuid4(v.release_id) || !uuid4(v.offering_id) || !integer(v.offering_version) || !integer(v.entry_year, 2000, 2100) || !member(v.intent, intents) || !Array.isArray(v.keywords) || v.keywords.length > 5 || !v.keywords.every(k => boundedText(k, 100)) || new Set(v.keywords).size !== v.keywords.length || !exact(v.scope, scopeKeys)) return false
  const s = v.scope
  return uuid4(s.institution_id) && uuid4(s.program_id) && typeof s.country === 'string' && /^[A-Z]{2}$/.test(s.country) && s.study_level === 'undergraduate' && s.entry_year === v.entry_year && scopeFields.every(key => validScopeKey(s[key]))
}
export function requestFor(target: PublicOfferingData, intent: RetrievalRequest['intent'], keywords: readonly string[] = []): RetrievalRequest {
  if (!validOffering(target)) throw new Error('Invalid QA target')
  const { dataset_id: _dataset, ...scope } = target.scope
  const input: RetrievalRequest = { release_id: target.release_id, offering_id: target.id, offering_version: target.version, entry_year: target.entry_year, scope, intent, keywords: [...keywords] }
  if (!validRequest(input)) throw new Error('Invalid QA target')
  return JSON.parse(JSON.stringify(input)) as RetrievalRequest
}
export function validContext(v: unknown): v is QAContextData {
  return exact(v, ['schema_version', 'can_ask', 'model_mode', 'live_available', 'real_processing_enabled', 'allow_test_fixture_read', 'demo_banner', 'disabled_reason', 'budget_unit']) && v.schema_version === 'v2.t39' && typeof v.can_ask === 'boolean' && member(v.model_mode, ['disabled', 'mock']) && v.live_available === false && v.real_processing_enabled === false && typeof v.allow_test_fixture_read === 'boolean' && (v.allow_test_fixture_read ? v.demo_banner === 'DEMO：合成测试资料，不是真实招生依据' : v.demo_banner === null) && nullable(v.disabled_reason, reason => member(reason, ['MODEL_DISABLED', 'QA_UNAVAILABLE', 'BUDGET_UNAVAILABLE'])) && (v.can_ask ? v.model_mode === 'mock' && v.allow_test_fixture_read && v.disabled_reason === null : v.disabled_reason !== null) && (v.model_mode !== 'disabled' || !v.can_ask) && v.budget_unit === 'conservative_utf8_bytes'
}
function projectionId(digest: string): string {
  const raw = digest.slice(0, 12) + '4' + digest.slice(13, 16) + ((parseInt(digest[16]!, 16) & 3) | 8).toString(16) + digest.slice(17, 32)
  return `${raw.slice(0, 8)}-${raw.slice(8, 12)}-${raw.slice(12, 16)}-${raw.slice(16, 20)}-${raw.slice(20, 32)}`
}
export async function validCitation(v: unknown, answer: QAAnswerData): Promise<boolean> {
  if (!exact(v, ['id', 'version', 'evidence_id', 'release_id', 'release_version', 'requirements_version', 'offering_id', 'offering_version', 'entry_year', 'scope', 'is_synthetic', 'field_key', 'fact', 'evidence', 'content_sha256']) || !['id', 'evidence_id', 'release_id', 'offering_id'].every(key => uuid4(v[key])) || v.version !== 1 || v.release_version !== 1 || !hash(v.requirements_version) || !hash(v.content_sha256) || !integer(v.offering_version) || !integer(v.entry_year, 2000, 2100) || typeof v.is_synthetic !== 'boolean' || !identifier(v.field_key) || !validScope(v.scope) || !validFact(v.fact) || !await validEvidence(v.evidence) || !answer.model_scope) return false
  const citation = v as unknown as CitationData, evidence = citation.evidence
  const { dataset_id, ...scope } = citation.scope
  if (citation.release_id !== answer.request.release_id || citation.requirements_version !== answer.requirements_version || citation.offering_id !== answer.request.offering_id || citation.offering_version !== answer.request.offering_version || citation.entry_year !== answer.request.entry_year || citation.is_synthetic !== answer.is_synthetic || dataset_id !== answer.model_scope.dataset_id || !sameValue(scope, answer.request.scope) || citation.field_key !== citation.fact.field_key || citation.fact.evidence_id !== citation.evidence_id || citation.fact.value_text === null || !sameValue(citation.scope, evidence.scope) || evidence.evidence_id !== citation.evidence_id || evidence.release_id !== citation.release_id || evidence.release_version !== citation.release_version || evidence.requirements_version !== citation.requirements_version || evidence.offering_id !== citation.offering_id || evidence.offering_version !== citation.offering_version || evidence.entry_year !== citation.entry_year || evidence.is_synthetic !== citation.is_synthetic) return false
  const { id: _id, version: _version, content_sha256, ...projection } = citation
  const digest = await canonicalHash(projection)
  return content_sha256 === digest && citation.id === projectionId(digest)
}
export async function validAnswer(v: unknown, expected: RetrievalRequest): Promise<boolean> {
  if (!exact(v, ['schema_version', 'status', 'request', 'model_scope', 'release_version', 'requirements_version', 'content_sha256', 'citations', 'advice_codes', 'unknown_reasons', 'is_synthetic', 'model_mode', 'live_available', 'generated_at']) || v.schema_version !== 'v2.t39' || !member(v.status, ['answered', 'unknown']) || !validRequest(v.request) || !sameValue(v.request, expected) || !Array.isArray(v.citations) || v.citations.length > 20 || !Array.isArray(v.advice_codes) || v.advice_codes.length > 3 || !v.advice_codes.every(code => member(code, adviceCodes)) || new Set(v.advice_codes).size !== v.advice_codes.length || !Array.isArray(v.unknown_reasons) || v.unknown_reasons.length > 8 || !v.unknown_reasons.every(code => member(code, unknownCodes)) || new Set(v.unknown_reasons).size !== v.unknown_reasons.length || v.model_mode !== 'mock' || v.live_available !== false || !utc(v.generated_at)) return false
  if (v.status === 'answered' ? v.citations.length === 0 : v.citations.length !== 0) return false
  if (v.model_scope === null) return v.status === 'unknown' && v.unknown_reasons.length > 0 && v.release_version === null && v.requirements_version === null && v.content_sha256 === null && v.is_synthetic === null
  if (!exact(v.model_scope, ['dataset_id', 'entry_year', 'offering_id', 'offering_version']) || !uuid4(v.model_scope.dataset_id) || v.model_scope.entry_year !== expected.entry_year || v.model_scope.offering_id !== expected.offering_id || v.model_scope.offering_version !== expected.offering_version || v.release_version !== 1 || !hash(v.requirements_version) || !hash(v.content_sha256) || v.is_synthetic !== true) return false
  if (new Set(v.citations.map(c => exact(c, ['id', 'version', 'evidence_id', 'release_id', 'release_version', 'requirements_version', 'offering_id', 'offering_version', 'entry_year', 'scope', 'is_synthetic', 'field_key', 'fact', 'evidence', 'content_sha256']) ? c.id : null)).size !== v.citations.length) return false
  const answer = v as unknown as QAAnswerData
  for (const citation of answer.citations) if (!await validCitation(citation, answer)) return false
  return true
}
export function bindsOffering(answer: QAAnswerData, target: PublicOfferingData): boolean {
  if (!validOffering(target)) return false
  if (answer.model_scope === null) return true
  return answer.model_scope.dataset_id === target.scope.dataset_id && answer.requirements_version === target.requirements_version && answer.content_sha256 === target.content_sha256 && answer.is_synthetic === target.is_synthetic && answer.citations.every(c => target.facts.some(fact => sameValue(fact, c.fact)))
}
