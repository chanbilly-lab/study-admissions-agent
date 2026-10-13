import { createHash } from 'node:crypto'
import { vi } from 'vitest'
import type { CatalogApi, PublicOfferingData, PublicEvidenceData, PublicOfferingsData } from '../src/features/catalog/client'
import type { EligibilityApi, AssessmentData, AssessmentRequest } from '../src/features/eligibility/client'
import { scopeFields } from '../src/features/catalog/validation'
import { hash, clone, version, rootId, versionId } from './profilesFixtures'
export { hash, clone, version, rootId, versionId }
export const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
export function offering(n = 1): PublicOfferingData {
  const scope = { dataset_id: id(100), institution_id: id(101), program_id: id(102), country: 'CN', study_level: 'undergraduate', entry_year: 2027,
    ...Object.fromEntries(scopeFields.map(k => [k, { status: 'known', value: 'DEMO_' + k }])) } as PublicOfferingData['scope']
  return { release_id: id(103), release_version: 1, requirements_version: 'a'.repeat(64), content_sha256: 'b'.repeat(64), ruleset_version: null, id: id(n), version: 1, entry_year: 2027, is_synthetic: true, institution_id: scope.institution_id, institution_name: 'DEMO_School', program_id: scope.program_id, program_name: 'DEMO_Program', scope,
    facts: [{ fact_type: 'requirement', field_key: 'math', value_kind: 'decimal', value_text: '600', normalized_value: '600', unit: 'points', missing_reason: null, footnote_state: 'none', footnote_text: null, claim_kind: 'minimum_requirement', unit_code: 'points', period: 'not_applicable', statistics_basis: 'not_applicable', statistic_population: null, statistic_denominator: null, cohort_year: null, survey_period: null, evidence_id: id(104), date_resolution: null }] }
}
export function config() { return { api_version: 'v2' as const, schema_version: 'v2.t20' as const, contract_stage: 'public_catalog' as const, app_environment: 'test' as const, query_role: 'demo_only' as const, data_mode: 'demo' as const, model_mode: 'disabled' as const, live_available: false as const, business_available: true, allow_test_fixture_read: true, demo_banner: 'DEMO：合成测试资料，不是真实招生依据' as const, supported_scope: [], supported_province: null, entry_year: null } }
export function page(items = [offering()], limit = 20, cursor: string | null = null): PublicOfferingsData { return { items, page: { limit, has_more: cursor !== null, next_cursor: cursor }, coverage: { returned_count: items.length, status: items.length ? 'partial' : 'no_published_records', expected_total: null, coverage_ratio: null } } }
export function evidence(item = offering(), quote = '<img src=x onerror=alert(1)>数学600分'): PublicEvidenceData { const bytes = new TextEncoder().encode(quote)
  return { evidence_id: item.facts[0]!.evidence_id!, release_id: item.release_id, release_version: 1, requirements_version: item.requirements_version, is_synthetic: item.is_synthetic, offering_id: item.id, offering_version: item.version, entry_year: item.entry_year, language: 'zh-Hans', quote, snippet_sha256: createHash('sha256').update(bytes).digest('hex'), document_sha256: 'd'.repeat(64), locator: { byte_start: 0, byte_end: bytes.length, line_start: 1, line_end: 1, page: null, section: null, location_kind: 'utf8_byte_lines' }, scope: clone(item.scope), publisher: 'DEMO_Publisher', authority_claim: 'claimed_official' }
}
export const context = () => ({ schema_version: 'v2.t28' as const, can_evaluate: true, can_read: true, can_replay: true, is_synthetic: true, reason: 'ruleset_unavailable' as const })
export function request(item = offering()): AssessmentRequest { return { confirmed: true, profile_id: rootId, profile_version_id: versionId, release_id: item.release_id, target: { dataset_id: item.scope.dataset_id, institution_id: item.institution_id, program_id: item.program_id, offering_id: item.id, offering_version: item.version, country: item.scope.country as 'CN', scope_sha256: hash(item.scope) }, stage: 'application', intake: null, application_cycle: null, channel: null, exam_system: null, subject_scope: null, batch_group: null } }
export function assessment(overrides: Partial<AssessmentData> = {}): AssessmentData {
  const v = version(), r = request(), unknown = { status: 'unknown' as const, reason: 'DATA_UNAVAILABLE' as const }
  const data: AssessmentData = { assessment_id: id(200), version: 1, profile_id: v.profile_id, profile_version_id: v.version_id, profile_version: v.version, profile_sha256: v.profile_sha256, target: r.target, release_id: r.release_id, requirements_version: offering().requirements_version, ruleset_version: null, stage: r.stage, assessment_at: '2026-10-03T00:00:00.123456Z', expires_at: '2028-10-03T00:00:00.123456Z', engine_version: 'T28_v1', binding_mode: 'unavailable', profile_is_synthetic: true, catalogue_is_synthetic: true, eligibility: { status: 'unknown', reason: 'RULESET_UNAVAILABLE', evaluation: null, obligations: [] }, competition_context: clone(unknown), preference_fit: clone(unknown), data_quality: clone(unknown), rule_refs: [], result_sha256: '0'.repeat(64), current_validity: 'current', replayed: false, ...overrides }
  data.result_sha256 = hash(Object.fromEntries(Object.entries(data).filter(([k]) => !['result_sha256', 'current_validity', 'replayed'].includes(k))))
  return data
}
export function response(data: unknown, { privateData = false, overrides = {} }: { privateData?: boolean; overrides?: Record<string, unknown> } = {}) {
  const a = data as AssessmentData
  const meta = { api_version: 'v2', request_id: 'e'.repeat(32), data_as_of: null, profile_version_id: privateData ? a.profile_version_id : null, release_id: null, ruleset_version: null, profile_mode: privateData ? a.profile_is_synthetic ? 'synthetic' : 'real' : null, data_mode: privateData ? 'verified' : 'demo', model_mode: 'disabled', ...overrides }
  return new Response(JSON.stringify({ data, meta }), { status: 200, headers: { 'X-Request-ID': 'e'.repeat(32), 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } })
}
export function csrf() { return new Response(JSON.stringify({ data: { csrf_token: 'T'.repeat(43), expires_at: '2030-01-01T00:00:00Z' }, meta: {} }), { status: 200 }) }
export function catalogApi(overrides: Partial<CatalogApi> = {}): CatalogApi { return { config: vi.fn(async () => config()), offerings: vi.fn(async query => page([offering()], query.limit ?? 20)), evidence: vi.fn(async () => evidence()), ...overrides } }
export function eligibilityApi(overrides: Partial<EligibilityApi> = {}): EligibilityApi { return { context: vi.fn(async () => context()), evaluate: vi.fn(async input => assessment({ target: clone(input.target), stage: input.stage })), get: vi.fn(async () => assessment()), replay: vi.fn(async () => assessment({ replayed: true })), ...overrides } }
