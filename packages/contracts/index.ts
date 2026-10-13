// M0 wire contract. Validated against FastAPI OpenAPI by offline contract tests.
export type EligibilityStatus = 'eligible' | 'ineligible' | 'conditional' | 'unknown'
export type AssessmentKey = 'gaokao_total' | 'math' | 'english_language'
export interface Score { value: number; scale: number; unit: 'points' | 'band'; kind: 'achieved' | 'predicted' }
export interface ProfileInput {
  display_name: string; is_synthetic: true; confirmed: true;
  study_level: 'bachelor'; course_system: 'gaokao'; entry_year: number;
  province: string; applicant_category: 'cn_mainland'; subjects: string[];
  assessments: Record<string, Score>; weekly_hours: number;
}
export interface Profile extends ProfileInput { id: string; version: number; owner_id: string }
export interface Deferral { evidence_id: string; deadline: string; deadline_evidence_id: string }
export interface Rule {
  id: string; offering_id: string; field: string; op: 'gte' | 'eq' | 'in' | 'exists';
  value: number | string | string[] | null; unit: string | null; scale: number | null;
  stage: 'application' | 'enrollment'; evidence_id: string;
  review_status: 'demo_reviewed' | 'review_required' | 'conflicted' | 'expired';
  version: string; deferral: Deferral | null;
}
export interface Evidence {
  id: string; title: string; is_synthetic: true; source_url: string;
  document_version_id: string; document_sha256: string; locator: string;
  excerpt: string; entry_year: number; country: 'CN' | 'GB'; province: string | null;
  offering_ids: string[];
  applicant_category: 'cn_mainland'; pathway: 'gaokao' | 'uk_undergraduate';
  review_status: 'demo_reviewed' | 'review_required' | 'conflicted' | 'expired';
  data_as_of: string;
}
export interface Offering {
  id: string; institution_id: string; institution_name: string; title: string;
  is_synthetic: true; country: 'CN' | 'GB'; study_level: 'bachelor';
  entry_year: number; province: string | null; applicant_category: 'cn_mainland';
  course_system: 'gaokao'; pathway: 'gaokao' | 'uk_undergraduate';
  deadline: string | null; deadline_evidence_id: string | null;
  deadline_status: 'known' | 'not_published'; rules: Rule[];
}
export interface RuleResult {
  rule_id: string; outcome: 'true' | 'false' | 'unknown' | 'deferred';
  message: string; evidence_ids: string[];
}
export interface Eligibility {
  id: string; profile_version_id: string; offering_id: string; status: EligibilityStatus;
  reasons: RuleResult[]; evidence_ids: string[]; missing_fields: string[];
  conditions: string[]; competition_context: string; preference_fit: string;
  data_quality: string[]; ruleset_version: string;
}
export interface DraftTask {
  id: string; offering_id: string; title: string; estimated_hours: number;
  acceptance_criteria: string; dependencies: string[]; evidence_ids: string[];
  hard_deadline_id: string | null; target_date: string | null; user_confirmed: false;
}
export interface PlanDraft {
  id: string; profile_version_id: string; status: 'draft'; is_synthetic: true;
  model_mode: 'mock' | 'live'; narrative: string; tasks: DraftTask[];
  warnings: string[]; eligibility_results: Eligibility[];
}
export interface Meta {
  request_id: string; data_as_of: string; profile_version: number | null;
  ruleset_version: string; demo_mode: true; model_mode: 'mock' | 'live';
}
export interface Envelope<T> { data: T; meta: Meta }
export interface RuntimeConfig {
  supported_province: string; demo_mode: true; model_mode: 'mock' | 'live';
  entry_year: number; live_available: false;
}
