import { vi } from 'vitest'
import type { Eligibility, Envelope, Evidence, Offering, PlanDraft, Profile, ProfileInput, RuntimeConfig } from '../../../packages/contracts/index'
import type { DemoUser, M0Api } from '../src/api'

export function envelope<T>(data: T): Envelope<T> {
  return { data, meta: { request_id: 'DEMO_request', data_as_of: '2026-09-30', profile_version: 1, ruleset_version: 'DEMO_rules_v1', demo_mode: true, model_mode: 'mock' } }
}
export const config: RuntimeConfig = { supported_province: '浙江', demo_mode: true, model_mode: 'mock', entry_year: 2027, live_available: false }
export function profile(user: DemoUser = 'alice', suffix = ''): Profile {
  return { id: `DEMO_profile_${user}${suffix}`, version: 1, owner_id: `demo_${user}`, display_name: `DEMO_${user}${suffix}`, is_synthetic: true, confirmed: true, study_level: 'bachelor', course_system: 'gaokao', entry_year: 2027, province: '浙江', applicant_category: 'cn_mainland', subjects: ['physics', 'chemistry'], assessments: { gaokao_total: { value: 610, scale: 750, unit: 'points', kind: 'achieved' }, math: { value: 120, scale: 150, unit: 'points', kind: 'achieved' } }, weekly_hours: 8 }
}
export const offering: Offering = {
  id: 'DEMO_CN_course', institution_id: 'DEMO_CN_institution', institution_name: 'DEMO_演示学院', title: 'DEMO_计算科学本科', is_synthetic: true,
  country: 'CN', study_level: 'bachelor', entry_year: 2027, province: '浙江', applicant_category: 'cn_mainland', course_system: 'gaokao', pathway: 'gaokao',
  deadline: null, deadline_evidence_id: null, deadline_status: 'not_published',
  rules: [{ id: 'DEMO_math_rule', offering_id: 'DEMO_CN_course', field: 'assessments.math', op: 'gte', value: 100, unit: 'points', scale: 150, stage: 'application', evidence_id: 'DEMO_evidence', review_status: 'demo_reviewed', version: 'DEMO_rules_v1', deferral: null }],
}
export function eligibility(status: Eligibility['status'] = 'unknown'): Eligibility {
  return { id: 'DEMO_result', profile_version_id: profile().id, offering_id: offering.id, status, reasons: [{ rule_id: 'DEMO_math_rule', outcome: 'unknown', message: '缺少实得成绩，且没有有效后补依据', evidence_ids: ['DEMO_evidence'] }], evidence_ids: ['DEMO_evidence'], missing_fields: ['assessments.english_language'], conditions: [], competition_context: 'M0 未实现', preference_fit: 'M0 未实现', data_quality: ['合成数据，不是真实官方依据'], ruleset_version: 'DEMO_rules_v1' }
}
export const evidence: Evidence = { id: 'DEMO_evidence', title: 'DEMO_合成规则', is_synthetic: true, source_url: 'demo://evidence/math', document_version_id: 'DEMO_doc_v1', document_sha256: 'a'.repeat(64), locator: '合成文档 §1', excerpt: '<script>bad()</script> 这只是原文，不执行。', entry_year: 2027, country: 'CN', province: '浙江', applicant_category: 'cn_mainland', pathway: 'gaokao', review_status: 'demo_reviewed', data_as_of: '2026-09-30', offering_ids: [offering.id] }
export const plan: PlanDraft = { id: 'DEMO_plan', profile_version_id: profile().id, status: 'draft', is_synthetic: true, model_mode: 'mock', narrative: 'DEMO 合成草案', tasks: [{ id: 'DEMO_task', offering_id: offering.id, title: '补充核验资料', estimated_hours: 1, acceptance_criteria: '由用户核验并确认资料', dependencies: [], evidence_ids: ['DEMO_evidence'], hard_deadline_id: null, target_date: null, user_confirmed: false }], warnings: ['无已知申请期限'], eligibility_results: [eligibility()] }
export function makeApi() {
  return {
    config: vi.fn(async (_user: DemoUser) => envelope(config)),
    profiles: vi.fn(async (user: DemoUser) => envelope([profile(user)])),
    createProfile: vi.fn(async (user: DemoUser, input: ProfileInput) => envelope({ ...input, id: `DEMO_new_${user}`, version: 1, owner_id: `demo_${user}` })),
    offerings: vi.fn(async (_user: DemoUser, _filter: Parameters<M0Api['offerings']>[1]) => envelope([offering])),
    check: vi.fn(async (_user: DemoUser, _input: Parameters<M0Api['check']>[1]) => envelope([eligibility()])),
    draft: vi.fn(async (_user: DemoUser, _input: Parameters<M0Api['draft']>[1]) => envelope(plan)),
    evidence: vi.fn(async (_user: DemoUser, _id: string) => envelope(evidence)),
  } satisfies M0Api
}
export function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((complete) => { resolve = complete })
  return { promise, resolve }
}
