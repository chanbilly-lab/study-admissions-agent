import { createHash } from 'node:crypto'
import { vi } from 'vitest'
import type { AssessmentContextData, AssessmentData, AssessmentRequest, EligibilityEngineResult } from '../../../packages/contracts/v2/assessments/generated'
import type { EvidenceScope, PublicConfigData, PublicEvidenceData, PublicFactData, PublicOfferingData, PublicOfferingsData, ScopeKey } from '../../../packages/contracts/v2/public_catalog/generated'
import type { CatalogApi } from '../src/features/catalog/client'
import type { EligibilityApi } from '../src/features/eligibility/client'
import { hash, version } from './profilesFixtures'

export const uid = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12,'0')}`
export const known = (value: string): ScopeKey => ({ status: 'known', value })
export function publicScope(): EvidenceScope {
  return { dataset_id: uid(1), institution_id: uid(2), program_id: uid(3), country: 'CN', study_level: 'undergraduate', entry_year: 2027,
    degree: known('DEMO_BACHELOR'), course: known('DEMO_CS'), campus: known('DEMO_CAMPUS'), teaching_language: known('DEMO_ZH'), progression_pathway: known('DEMO_DIRECT'),
    intake: known('DEMO_AUTUMN'), application_cycle: known('DEMO_CYCLE'), channel: known('DEMO_CHANNEL'), course_system: known('gaokao'), pathway: known('gaokao'), applicant_category: known('cn_mainland'), province: known('DEMO_PROVINCE'), exam_system: known('DEMO_EXAM'), subject_scope: known('DEMO_PHYSICS'), batch_group: known('DEMO_BATCH') }
}
export function publicFact(overrides: Partial<PublicFactData> = {}): PublicFactData {
  return { fact_type: 'score', field_key: 'DEMO_math', value_kind: 'decimal', value_text: '60.00', normalized_value: '60', unit: 'points', missing_reason: null,
    footnote_state: 'present', footnote_text: 'DEMO_<img src=https://sentinel.invalid/x onerror=window.__t29=1>', claim_kind: 'minimum_requirement', unit_code: 'points', period: 'not_applicable', statistics_basis: 'not_applicable', statistic_population: null, statistic_denominator: null, cohort_year: null, survey_period: null, evidence_id: uid(6), date_resolution: null, ...overrides }
}
export function offering(overrides: Partial<PublicOfferingData> = {}): PublicOfferingData {
  return { release_id: uid(4), release_version: 1, requirements_version: 'b'.repeat(64), content_sha256: 'a'.repeat(64), ruleset_version: null,
    id: uid(5), version: 1, entry_year: 2027, is_synthetic: true, institution_id: uid(2), institution_name: 'DEMO_合成机构', program_id: uid(3), program_name: 'DEMO_合成计算机项目', scope: publicScope(), facts: [publicFact()], ...overrides }
}
export function publicConfig(overrides: Partial<PublicConfigData> = {}): PublicConfigData { return { api_version: 'v2', schema_version: 'v2.t20', contract_stage: 'public_catalog', app_environment: 'test', query_role: 'demo_only', data_mode: 'demo', model_mode: 'disabled', live_available: false, business_available: true, allow_test_fixture_read: true, demo_banner: 'DEMO：合成测试资料，不是真实招生依据', supported_scope: [], supported_province: null, entry_year: null, ...overrides } }
export function publicPage(items = [offering()], limit = 20, more = false): PublicOfferingsData { return { items, page: { limit, has_more: more, next_cursor: more ? 'DEMO_cursor' : null }, coverage: { returned_count: items.length, status: items.length ? 'partial' : 'no_published_records', expected_total: null, coverage_ratio: null } } }
export function publicEvidence(item = offering()): PublicEvidenceData {
  const quote = 'DEMO_原文 <img src=https://sentinel.invalid/x onerror=window.__t29=1>\n60.00 points'
  return { evidence_id: uid(6), release_id: item.release_id, release_version: 1, requirements_version: item.requirements_version, is_synthetic: true, offering_id: item.id, offering_version: item.version, entry_year: item.entry_year, language: 'zh-Hans', quote, document_sha256: 'd'.repeat(64), snippet_sha256: createHash('sha256').update(quote).digest('hex'), locator: { byte_start: 0, byte_end: new TextEncoder().encode(quote).length, line_start: 1, line_end: 2, location_kind: 'utf8_byte_lines', page: null, section: null }, scope: item.scope, publisher: 'DEMO_合成发布者', authority_claim: 'claimed_official' }
}
export function outcome(status: EligibilityEngineResult['status']): EligibilityEngineResult {
  const truth = status === 'eligible' ? 'true' : status === 'ineligible' ? 'false' : 'unknown'
  const reason = truth === 'true' ? 'MATCH' : truth === 'false' ? 'NO_MATCH' : 'MISSING'
  return { status, reason: status === 'eligible' ? 'RULE_TRUE' : status === 'ineligible' ? 'RULE_FALSE' : status === 'conditional' ? 'DEFERRAL_SATISFIABLE' : 'RULE_UNKNOWN', evaluation: { truth, reason, trace: [{ op: 'gte', field: { name: 'assessment', key: 'math', basis: 'achieved' }, outcome: truth, reason, children: [] }] }, obligations: status === 'conditional' ? [{ assessment_key: 'math', basis: 'achieved', deferral: { deferral_status: 'allowed', reason: 'ALLOWED', application_deadline_status: 'before', supplement_deadline_status: 'before', bundle_id: uid(8), policy_id: uid(9), policy_version: 'e'.repeat(64), application_deadline_event_id: uid(10), supplement_deadline_event_id: uid(11), evidence_ids: [uid(6)] } }] : [] }
}
export function assessment(status: EligibilityEngineResult['status'] = 'eligible', overrides: Partial<AssessmentData> = {}): AssessmentData {
  const profile = version(), item = offering()
  const data: AssessmentData = { assessment_id: uid(12), version: 1, profile_id: profile.profile_id, profile_version_id: profile.version_id, profile_version: profile.version, profile_sha256: profile.profile_sha256,
    target: { dataset_id: item.scope.dataset_id, institution_id: item.institution_id, program_id: item.program_id, offering_id: item.id, offering_version: item.version, country: 'CN', scope_sha256: hash(item.scope) }, release_id: item.release_id, requirements_version: item.requirements_version, ruleset_version: 'c'.repeat(64), stage: 'application', assessment_at: '2026-10-04T00:00:00Z', expires_at: '2028-10-04T00:00:00Z', engine_version: 'T28_v1', binding_mode: 'test_fixture', profile_is_synthetic: true, catalogue_is_synthetic: true,
    eligibility: outcome(status), competition_context: { status: 'unknown', reason: 'DATA_UNAVAILABLE' }, preference_fit: { status: 'unknown', reason: 'DATA_UNAVAILABLE' }, data_quality: { status: 'unknown', reason: 'DATA_UNAVAILABLE' }, rule_refs: [{ bundle_id: uid(8), expression_sha256: 'f'.repeat(64), fact_ids: [uid(13)], evidence_ids: [uid(6)] }], result_sha256: '0'.repeat(64), current_validity: 'current', replayed: false, ...overrides }
  data.result_sha256 = hash(Object.fromEntries(Object.entries(data).filter(([key]) => !['result_sha256','current_validity','replayed'].includes(key))))
  return data
}
export function catalogApi(overrides: Partial<CatalogApi> = {}): CatalogApi { return { config: vi.fn(async () => publicConfig()), offerings: vi.fn(async query => publicPage([offering()],query.limit ?? 20)), evidence: vi.fn(async () => publicEvidence()), ...overrides } }
export function eligibilityContext(overrides: Partial<AssessmentContextData> = {}): AssessmentContextData { return { schema_version: 'v2.t28', can_evaluate: true, can_read: true, can_replay: true, is_synthetic: true, reason: 'ready', ...overrides } }
export function eligibilityApi(overrides: Partial<EligibilityApi> = {}): EligibilityApi { return { context: vi.fn(async () => eligibilityContext()), evaluate: vi.fn(async (input: AssessmentRequest) => assessment('eligible', { stage: input.stage, target: input.target })), get: vi.fn(async () => assessment()), replay: vi.fn(async () => assessment('eligible', { replayed: true })), ...overrides } }
