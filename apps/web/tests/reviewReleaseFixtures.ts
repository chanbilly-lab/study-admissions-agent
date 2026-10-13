import { vi } from 'vitest'
import { createHash } from 'node:crypto'
import type { PublicOfferingData, PublicOfferingsData, PublicFactData, EvidenceScope } from '../../../packages/contracts/v2/public_catalog/generated'
import type { ReviewWorkspaceApi, ReviewContextData, ImportRowsData, DocumentData, VersionData, SnippetData,
  TypedCandidate, Classification, ReviewCandidatesData, ReviewDetailData, ReviewDecisionData, CurrentReleaseData, PublishPrecheckData, ReleaseData } from '../src/features/admin/reviews/client'
import { actor, otherActor } from './privacyFixtures'
import { datasetId, sourceId, fileId, importId } from './adminFixtures'
export { actor, otherActor, deferred } from './privacyFixtures'
export { datasetId, sourceId, fileId, importId } from './adminFixtures'
export const factId = 'ad85a738-6aca-4160-a5ef-6ad7247199bc'
export const evidenceId = 'c0fbead9-314b-4587-b344-95e809f49e0f'
export const releaseId = '94c797c4-6f1d-4923-b48a-2f1050e93e96'
export const offeringId = 'f93e0832-4419-472c-b544-46b87e8aaf65'
export const scope: EvidenceScope = {
  dataset_id: '588e905d-8a66-41eb-8b6e-985d297252d1', program_id: '05f401fb-4cbf-42c9-b7ed-0c5b02dbd4f6',
  institution_id: 'e749e91b-d539-4cb7-9d83-4c669555b275', country: 'CN', study_level: 'undergraduate', entry_year: 2027,
  degree: { status: 'known', value: 'DEMO_degree' }, course: { status: 'known', value: 'DEMO_course' }, campus: { status: 'known', value: 'DEMO_campus' },
  teaching_language: { status: 'known', value: 'DEMO_language' }, progression_pathway: { status: 'not_applicable', value: null },
  intake: { status: 'known', value: 'DEMO_intake' }, application_cycle: { status: 'not_applicable', value: null }, channel: { status: 'known', value: 'DEMO_channel' },
  course_system: { status: 'known', value: 'DEMO_gaokao' }, pathway: { status: 'known', value: 'DEMO_pathway' }, applicant_category: { status: 'known', value: 'DEMO_category' },
  province: { status: 'known', value: 'DEMO_province' }, exam_system: { status: 'known', value: 'DEMO_exam' }, subject_scope: { status: 'known', value: 'DEMO_subjects' },
  batch_group: { status: 'known', value: 'DEMO_batch' },
}
export function publicFact(overrides: Partial<PublicFactData> = {}): PublicFactData {
  return { fact_type: 'score', field_key: 'DEMO_total', value_kind: 'decimal', value_text: '600.00', normalized_value: '600', unit: 'points',
    missing_reason: null, footnote_state: 'none', footnote_text: null, claim_kind: 'minimum_requirement', unit_code: 'points', period: 'not_applicable',
    statistics_basis: 'not_applicable', statistic_population: null, statistic_denominator: null, cohort_year: null, survey_period: null,
    evidence_id: evidenceId, date_resolution: null, ...overrides }
}
export function publicOffering(overrides: Partial<PublicOfferingData> = {}): PublicOfferingData {
  return { release_id: releaseId, release_version: 1, content_sha256: 'a'.repeat(64), requirements_version: 'b'.repeat(64), ruleset_version: null,
    id: offeringId, version: 1, entry_year: 2027, is_synthetic: true, institution_id: scope.institution_id, institution_name: 'DEMO_合成机构',
    program_id: scope.program_id, program_name: 'DEMO_合成专业', scope, facts: [publicFact()], ...overrides }
}
export function publicRecords(items: PublicOfferingData[] = [publicOffering()]): PublicOfferingsData {
  return { items, page: { limit: 20, has_more: false, next_cursor: null }, coverage: {
    status: items.length ? 'partial' : 'no_published_records', returned_count: items.length, expected_total: null, coverage_ratio: null,
  } }
}
export const publicApi = () => ({ offerings: vi.fn(async () => publicRecords()) })
export const rowId = '5c50b733-7edf-4246-b6b1-0479cd201536', documentId = 'f5bb3b55-a272-48cd-823c-3265efb99432'
export const decisionId = '57bfc4af-aafc-434a-8f91-e4a820fab641', caseId = '1df55d96-280f-4496-be21-86b477b054fb'
export const row = { offering_id: offeringId, offering_version: 1, entry_year: 2027, source_record_reference: 'DEMO_row', fact_type: 'score' as const,
  field_key: 'DEMO_total', value_kind: 'decimal' as const, value_text: '600.00', unit: 'points', missing_reason: null,
  footnote_state: 'none' as const, footnote_text: null, locator: null, row_number: 1 }
export const original = JSON.stringify([row]), originalHash = createHash('sha256').update(original).digest('hex')
export function reviewContext(overrides: Partial<ReviewContextData> = {}): ReviewContextData {
  return { schema_version: 'v2.t22', can_prepare: true, can_review: true, can_publish: true, can_withdraw: true, is_synthetic: true, ...overrides }
}
export function rows(overrides: Partial<ImportRowsData> = {}): ImportRowsData {
  return { import_id: importId, dataset_id: datasetId, source_id: sourceId, source_version: 1, file_id: fileId, file_sha256: originalHash,
    is_synthetic: true, format: 'json', total_rows: 1, rows: [{ row_id: rowId, row }], next_cursor: null, ...overrides }
}
export function document(overrides: Partial<DocumentData> = {}): DocumentData {
  return { id: documentId, dataset_id: datasetId, source_id: sourceId, source_version: 1, document_reference: 'DEMO_document', language: 'en',
    is_synthetic: true, current_version: 0, created_at: '2026-10-03T00:00:00Z', ...overrides }
}
export function version(overrides: Partial<VersionData> = {}): VersionData {
  return { id: 'b8b45663-ea8a-4a54-919b-4313e21e9e77', document_id: documentId, version: 1, document_sha256: originalHash,
    size_bytes: Buffer.byteLength(original), media_type: 'application/json', is_synthetic: true, created_at: '2026-10-03T00:00:00Z', ...overrides }
}
export function snippet(overrides: Partial<SnippetData> = {}): SnippetData {
  return { id: evidenceId, document_id: documentId, document_version: 1, offering_id: offeringId, offering_version: 1, entry_year: 2027, language: 'en',
    document_sha256: originalHash, snippet_sha256: originalHash, text: original, locator: { byte_start: 0, byte_end: Buffer.byteLength(original),
      line_start: 1, line_end: 1, page: null, section: null, location_kind: 'utf8_byte_lines' }, is_synthetic: true, created_at: '2026-10-03T00:00:00Z', scope, ...overrides }
}
export function classification(overrides: Partial<Classification> = {}): Classification {
  return { claim_kind: 'minimum_requirement', unit_code: 'points', period: 'not_applicable', statistics_basis: 'not_applicable',
    statistic_population: null, statistic_denominator: null, cohort_year: null, survey_period: null, date_event_id: null, ...overrides }
}
export function fact(overrides: Partial<TypedCandidate> = {}): TypedCandidate {
  return { ...row, classification: classification(), evidence_id: evidenceId, normalized_value: '600', date_resolution: null, state: 'review_required',
    hard_rule: false, publication_eligible: false, id: factId, version: 1, import_id: importId, import_row_id: rowId, dataset_id: datasetId,
    is_synthetic: true, created_at: '2026-10-03T00:00:00Z', conflicting_ids: [], ...overrides }
}
export function candidates(overrides: Partial<ReviewCandidatesData> = {}): ReviewCandidatesData {
  const f = fact(); return { dataset_id: datasetId, entry_year: 2027, dataset_revision: 4, items: [{ fact_id: f.id, version: 1, dataset_id: datasetId,
    offering_id: offeringId, offering_version: 1, entry_year: 2027, state: f.state, is_synthetic: true, created_at: f.created_at }], next_cursor: null, ...overrides }
}
export function detail(overrides: Partial<ReviewDetailData> = {}): ReviewDetailData {
  return { fact: fact(), case: { case_id: null, logical_key_hash: 'd'.repeat(64), case_revision: 0, chosen_fact_id: null, current_decision_id: null,
    current_approved: false, is_synthetic: true }, evidence: snippet(), scope, gaps: [], conflicts: [], ...overrides }
}
export function decision(overrides: Partial<ReviewDecisionData> = {}): ReviewDecisionData {
  return { fact_id: factId, action: 'approve', checks: ['original_value','claim_kind','unit','period','scope','evidence_location','missingness','footnote','statistics_context','date_context']
    .map(field => ({ field: field as ReviewDecisionData['checks'][number]['field'], status: 'accepted' })), conflict_resolutions: [], return_reason: null,
    decision_id: decisionId, case_id: caseId, case_revision: 1, reviewer_user_id: otherActor.user_id, created_at: '2026-10-03T00:00:00Z', is_synthetic: true, current_approved: true, ...overrides }
}
export function current(overrides: Partial<CurrentReleaseData> = {}): CurrentReleaseData {
  return { dataset_id: datasetId, entry_year: 2027, dataset_revision: 4, release: null, ...overrides }
}
export function release(overrides: Partial<ReleaseData> = {}): ReleaseData {
  return { release_id: releaseId, version: 1, dataset_id: datasetId, entry_year: 2027, kind: 'test_fixture', is_synthetic: true,
    valid_from: '2026-10-02T00:00:00Z', valid_until: '2026-10-04T00:00:00Z', content_sha256: 'a'.repeat(64), requirements_version: 'b'.repeat(64), ruleset_version: null,
    members: [{ fact_id: factId, logical_key_hash: 'd'.repeat(64), decision_id: decisionId, case_revision: 1, offering_id: offeringId, offering_version: 1,
      entry_year: 2027, source_id: sourceId, source_version: 1, evidence_id: evidenceId, fact_sha256: 'e'.repeat(64), scope_sha256: 'f'.repeat(64),
      evidence_sha256: originalHash, source_sha256: 'c'.repeat(64), file_sha256: originalHash, public_evidence: false }], state: 'published', state_revision: 1,
    published_at: '2026-10-03T00:00:00Z', publisher_user_id: actor.user_id, replaces_release_id: null, replaced_by_release_id: null, replayed: false, ...overrides }
}
export function publishedHead(): CurrentReleaseData {
  const r = release(); return current({ release: { release_id: r.release_id, version: 1, state: r.state, state_revision: r.state_revision, kind: r.kind,
    is_synthetic: true, valid_from: r.valid_from, valid_until: r.valid_until, content_sha256: r.content_sha256, requirements_version: r.requirements_version,
    member_count: 1, replaces_release_id: null, replaced_by_release_id: null } })
}
export function prechecked(overrides: Partial<PublishPrecheckData> = {}): PublishPrecheckData {
  return { status: 'precheck_passed', request_sha256: 'a'.repeat(64), dataset_revision: 4, member_count: 1, checked_at: '2026-10-03T00:00:00Z', is_synthetic: true, ...overrides }
}
export function workspaceApi(overrides: Partial<ReviewWorkspaceApi> = {}) {
  return { context: vi.fn(async () => reviewContext()), rows: vi.fn(async () => rows()), document: vi.fn(async () => document()), version: vi.fn(async () => version()),
    snippet: vi.fn(async () => snippet()), fact: vi.fn(async () => fact()), candidates: vi.fn(async () => candidates()), detail: vi.fn(async () => detail()),
    review: vi.fn(async () => decision()), precheck: vi.fn(async () => prechecked()), publish: vi.fn(async () => release()), current: vi.fn(async () => current()),
    release: vi.fn(async () => release()), withdraw: vi.fn(async () => release({ state: 'withdrawn', state_revision: 2 })), ...overrides } satisfies ReviewWorkspaceApi
}
