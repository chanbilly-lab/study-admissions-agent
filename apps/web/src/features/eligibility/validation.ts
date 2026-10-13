import type { AssessmentContextData, AssessmentData, AssessmentRequest, EligibilityEngineResult, EvaluationResult, TargetReference } from '../../../../../packages/contracts/v2/assessments/generated'
import type { ProfileVersionData } from '../profiles/client'
import { adaptationOf, assessmentKeys, validSnapshot } from '../profiles/form'
import { snapshotHash } from '../profiles/client'
import { canonicalHash, exact, hash, integer, member, nullable, utc, uuid, validScopeKey } from '../catalog/validation'
export const extraScopeFields = ['intake', 'application_cycle', 'channel', 'exam_system', 'subject_scope', 'batch_group'] as const
export function validTarget(v: unknown): v is TargetReference {
  return exact(v, ['country', 'dataset_id', 'institution_id', 'program_id', 'offering_id', 'offering_version', 'scope_sha256']) && member(v.country, ['CN', 'GB']) && ['dataset_id', 'institution_id', 'program_id', 'offering_id'].every(k => uuid(v[k])) && integer(v.offering_version) && hash(v.scope_sha256)
}
export function validRequest(v: unknown): v is AssessmentRequest {
  return exact(v, ['profile_id', 'profile_version_id', 'release_id', 'target', 'stage', 'confirmed', ...extraScopeFields]) && ['profile_id', 'profile_version_id', 'release_id'].every(k => uuid(v[k])) && validTarget(v.target) && member(v.stage, ['application', 'enrollment']) && v.confirmed === true && extraScopeFields.every(k => nullable(v[k], validScopeKey))
}
export function validContext(v: unknown): v is AssessmentContextData {
  return exact(v, ['schema_version', 'can_evaluate', 'can_read', 'can_replay', 'reason', 'is_synthetic']) && v.schema_version === 'v2.t28' && ['can_evaluate', 'can_read', 'can_replay', 'is_synthetic'].every(k => typeof v[k] === 'boolean') && member(v.reason, ['ready', 'processing_disabled', 'ruleset_unavailable']) && (v.reason !== 'processing_disabled' || v.can_evaluate === false && v.can_read === false && v.can_replay === false)
}
export async function validProfile(v: unknown): Promise<boolean> {
  if (!exact(v, ['profile_id', 'version_id', 'version', 'profile', 'profile_sha256', 'confirmed_at', 'source', 'expires_at', 'is_synthetic', 'adaptation']) || !uuid(v.profile_id) || !uuid(v.version_id) || !integer(v.version) || !validSnapshot(v.profile) || !hash(v.profile_sha256) || !utc(v.confirmed_at) || !utc(v.expires_at) || Date.parse(v.expires_at) <= Date.parse(v.confirmed_at) || v.source !== 'student_declared' || typeof v.is_synthetic !== 'boolean' || !exact(v.adaptation, ['status', 'reason'])) return false
  const adaptation = adaptationOf(v.profile)
  return v.adaptation.status === adaptation.status && v.adaptation.reason === adaptation.reason && v.profile_sha256 === await snapshotHash(v.profile)
}
const truths = ['true', 'false', 'unknown'], traceReasons = ['MATCH', 'NO_MATCH', 'MISSING', 'PENDING', 'NOT_APPLICABLE', 'CONFLICTED', 'TYPE_MISMATCH', 'UNIT_MISMATCH', 'SCALE_MISMATCH', 'PREDICTED_NOT_ACHIEVED', 'CALENDAR_MISMATCH', 'PRECISION_MISMATCH', 'REFERENCE_MISSING', 'UNKNOWN_CHILD']
function field(v: unknown): boolean {
  return exact(v, ['name', 'key', 'basis']) && member(v.name, ['study_level', 'entry_year', 'residence_region', 'course_system', 'applicant_category', 'exam_province', 'pathway', 'subjects', 'assessment', 'assessment_date', 'assessment_at']) && (v.name === 'assessment' ? member(v.key, assessmentKeys) && member(v.basis, ['achieved', 'predicted']) : v.key === null && v.basis === null)
}
export function validEvaluation(v: unknown): v is EvaluationResult {
  if (!exact(v, ['truth', 'reason', 'trace']) || !member(v.truth, truths) || !member(v.reason, traceReasons) || !Array.isArray(v.trace) || v.trace.length < 1 || v.trace.length > 256) return false
  const trace = v.trace
  const seen = new Set<number>()
  const visit = (index: number, depth: number): boolean => {
    if (seen.has(index) || depth > 16) return false
    seen.add(index)
    const n: unknown = trace[index]
    if (!exact(n, ['op', 'field', 'outcome', 'reason', 'children']) || !member(n.op, ['all', 'any', 'not', 'exists', 'eq', 'in', 'gte', 'lte', 'date_before', 'valid_at']) || !member(n.outcome, truths) || !member(n.reason, traceReasons) || !Array.isArray(n.children) || n.children.length > 32 || !n.children.every(i => integer(i, index + 1, trace.length - 1))) return false
    const group = n.op === 'all' || n.op === 'any' || n.op === 'not'
    if (group ? n.field !== null || (n.op === 'not' ? n.children.length !== 1 : n.children.length < 1) : n.children.length !== 0 || (n.op === 'valid_at' ? n.field !== null : !field(n.field))) return false
    return n.children.every(i => visit(i as number, depth + 1))
  }
  return visit(0, 1) && seen.size === v.trace.length && v.trace[0].outcome === v.truth && v.trace[0].reason === v.reason
}
function allowedDeferral(v: unknown): boolean {
  return exact(v, ['deferral_status', 'reason', 'application_deadline_status', 'supplement_deadline_status', 'bundle_id', 'policy_id', 'policy_version', 'application_deadline_event_id', 'supplement_deadline_event_id', 'evidence_ids']) && v.deferral_status === 'allowed' && v.reason === 'ALLOWED' && member(v.application_deadline_status, ['before', 'not_applicable']) && v.supplement_deadline_status === 'before' && uuid(v.bundle_id) && uuid(v.policy_id) && hash(v.policy_version) && uuid(v.supplement_deadline_event_id) && (v.application_deadline_status === 'not_applicable' ? v.application_deadline_event_id === null : uuid(v.application_deadline_event_id)) && Array.isArray(v.evidence_ids) && v.evidence_ids.length >= 1 && v.evidence_ids.length <= 96 && v.evidence_ids.every(uuid) && new Set(v.evidence_ids).size === v.evidence_ids.length
}
export function validOutcome(v: unknown): v is EligibilityEngineResult {
  if (!exact(v, ['status', 'reason', 'evaluation', 'obligations']) || !Array.isArray(v.obligations) || v.obligations.length > 15 || !nullable(v.evaluation, validEvaluation) || !v.obligations.every(o => exact(o, ['assessment_key', 'basis', 'deferral']) && member(o.assessment_key, assessmentKeys) && o.basis === 'achieved' && allowedDeferral(o.deferral)) || new Set(v.obligations.map(o => o.assessment_key)).size !== v.obligations.length) return false
  if (v.status === 'conditional') return v.reason === 'DEFERRAL_SATISFIABLE' && v.obligations.length >= 1 && v.evaluation !== null && (v.evaluation as EvaluationResult).truth === 'unknown'
  if (v.obligations.length !== 0) return false
  if (v.status === 'eligible' || v.status === 'ineligible') return v.reason === (v.status === 'eligible' ? 'RULE_TRUE' : 'RULE_FALSE') && v.evaluation !== null && (v.evaluation as EvaluationResult).truth === (v.status === 'eligible' ? 'true' : 'false')
  return v.status === 'unknown' && (v.evaluation === null ? member(v.reason, ['RULESET_UNAVAILABLE', 'BINDING_UNAVAILABLE', 'SCOPE_UNAVAILABLE']) : member(v.reason, ['RULE_UNKNOWN', 'NO_COMPLETABLE_FIELD', 'DOMAIN_UNAVAILABLE', 'SEARCH_BUDGET_EXCEEDED']) && (v.evaluation as EvaluationResult).truth === 'unknown')
}
export async function resultFingerprint(value: AssessmentData): Promise<string> {
  return canonicalHash(Object.fromEntries(Object.entries(value).filter(([key]) => !['result_sha256', 'current_validity', 'replayed'].includes(key))))
}
export async function validAssessment(v: unknown): Promise<boolean> {
  if (!exact(v, ['assessment_id', 'version', 'profile_id', 'profile_version_id', 'profile_version', 'profile_sha256', 'target', 'release_id', 'requirements_version', 'ruleset_version', 'stage', 'assessment_at', 'expires_at', 'engine_version', 'binding_mode', 'profile_is_synthetic', 'catalogue_is_synthetic', 'eligibility', 'competition_context', 'preference_fit', 'data_quality', 'rule_refs', 'result_sha256', 'current_validity', 'replayed']) || !['assessment_id', 'profile_id', 'profile_version_id', 'release_id'].every(k => uuid(v[k])) || v.version !== 1 || !integer(v.profile_version) || !hash(v.profile_sha256) || !hash(v.requirements_version) || !nullable(v.ruleset_version, hash) || !validTarget(v.target) || !member(v.stage, ['application', 'enrollment']) || !utc(v.assessment_at) || !utc(v.expires_at) || Date.parse(v.expires_at) <= Date.parse(v.assessment_at) || v.engine_version !== 'T28_v1' || !member(v.binding_mode, ['unavailable', 'test_fixture']) || typeof v.profile_is_synthetic !== 'boolean' || typeof v.catalogue_is_synthetic !== 'boolean' || !validOutcome(v.eligibility) || !['competition_context', 'preference_fit', 'data_quality'].every(k => exact(v[k], ['status', 'reason']) && v[k].status === 'unknown' && v[k].reason === 'DATA_UNAVAILABLE') || !Array.isArray(v.rule_refs) || v.rule_refs.length > 1 || !v.rule_refs.every(r => exact(r, ['bundle_id', 'expression_sha256', 'fact_ids', 'evidence_ids']) && uuid(r.bundle_id) && hash(r.expression_sha256) && ['fact_ids', 'evidence_ids'].every(k => Array.isArray(r[k]) && r[k].length >= 1 && r[k].length <= 32 && r[k].every(uuid))) || !hash(v.result_sha256) || !member(v.current_validity, ['current', 'withdrawn', 'replaced', 'needs_review', 'unavailable']) || typeof v.replayed !== 'boolean') return false
  if (v.binding_mode === 'test_fixture' ? v.profile_is_synthetic !== true || v.catalogue_is_synthetic !== true || v.ruleset_version === null || v.rule_refs.length !== 1 : v.ruleset_version !== null || v.rule_refs.length !== 0 || v.eligibility.status !== 'unknown' || v.eligibility.evaluation !== null || !member(v.eligibility.reason, ['RULESET_UNAVAILABLE', 'BINDING_UNAVAILABLE', 'SCOPE_UNAVAILABLE'])) return false
  return v.result_sha256 === await resultFingerprint(v as unknown as AssessmentData)
}
export function bindProfile(data: AssessmentData, profile: ProfileVersionData): boolean { return data.profile_id === profile.profile_id && data.profile_version_id === profile.version_id && data.profile_version === profile.version && data.profile_sha256 === profile.profile_sha256 && data.profile_is_synthetic === profile.is_synthetic }
