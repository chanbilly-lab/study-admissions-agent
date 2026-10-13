// Generated offline from create_notifications_v2_app().openapi() by scripts/generate_contracts.py.
// Do not edit. JSON Schema validation constraints remain in openapi.json.

export interface AcceptGrantInput {
  confirmed: true;
  expected_version: number;
  sharing_policy_hash: string;
  sharing_policy_version: string;
}

export interface AcceptV2AccessGrantPath {
  grant_id: string;
}

export interface AcceptV2AccessGrantQuery {

}

export type AcceptV2AccessGrantRequestBody = AcceptGrantInput;

export type AcceptV2AccessGrantResponse200 = Envelope_GrantMutationData_;

export type AcceptV2AccessGrantResponse401 = ErrorEnvelope;

export type AcceptV2AccessGrantResponse403 = ErrorEnvelope;

export type AcceptV2AccessGrantResponse404 = ErrorEnvelope;

export type AcceptV2AccessGrantResponse405 = ErrorEnvelope;

export type AcceptV2AccessGrantResponse409 = ErrorEnvelope;

export type AcceptV2AccessGrantResponse422 = ErrorEnvelope;

export type AcceptV2AccessGrantResponse429 = ErrorEnvelope;

export type AcceptV2AccessGrantResponse500 = ErrorEnvelope;

export type AcceptV2AccessGrantResponse503 = ErrorEnvelope;

export interface AdaptationData {
  reason: "ADAPTER_NOT_IMPLEMENTED" | "APPLICANT_NOT_SUPPORTED" | "COURSE_NOT_SUPPORTED" | "MISSING_SCOPE" | "PATHWAY_NOT_SUPPORTED";
  status: "unknown" | "unsupported";
}

export interface AdmissionData {
  age_assurance: "declared" | "unknown";
  age_band: "18_plus" | null;
  consent_id: null | string;
  consent_status: "active" | "invalidated" | "not_confirmed" | "withdrawn";
  core_consultation_allowed: boolean;
  declaration_expires_at: null | string;
  declared_at: null | string;
  is_synthetic: boolean;
  notice_id: null | string;
  notice_version: null | string;
  policy_version: string;
  private_business_available: false;
  readiness: boolean;
  reason: "age_expired" | "age_missing" | "allowed" | "consent_invalidated" | "consent_missing" | "consent_withdrawn" | "notice_changed" | "policy_changed" | "processing_disabled" | "role_missing";
  revision: number;
  user_id: string;
}

export interface AgeDeclarationInput {
  age_band: "14_17" | "18_plus" | "under_14" | "unknown";
  confirmed: true;
  expected_revision: number;
  notice_id: string;
}

export interface AppendInput {
  confirmed: true;
  expected_current_version: number;
  profile: ProfileSnapshot;
}

export interface AppendV2ProfileVersionPath {
  profile_id: string;
}

export interface AppendV2ProfileVersionQuery {

}

export type AppendV2ProfileVersionRequestBody = AppendInput;

export type AppendV2ProfileVersionResponse200 = ProfileEnvelope_ProfileWriteData_;

export type AppendV2ProfileVersionResponse401 = ErrorEnvelope;

export type AppendV2ProfileVersionResponse403 = ErrorEnvelope;

export type AppendV2ProfileVersionResponse404 = ErrorEnvelope;

export type AppendV2ProfileVersionResponse405 = ErrorEnvelope;

export type AppendV2ProfileVersionResponse409 = ErrorEnvelope;

export type AppendV2ProfileVersionResponse422 = ErrorEnvelope;

export type AppendV2ProfileVersionResponse429 = ErrorEnvelope;

export type AppendV2ProfileVersionResponse500 = ErrorEnvelope;

export type AppendV2ProfileVersionResponse503 = ErrorEnvelope;

export interface AssessmentContextData {
  can_evaluate: boolean;
  can_read: boolean;
  can_replay: boolean;
  is_synthetic: boolean;
  reason: "processing_disabled" | "ready" | "ruleset_unavailable";
  schema_version: "v2.t28";
}

export interface AssessmentData {
  assessment_at: string;
  assessment_id: string;
  binding_mode: "test_fixture" | "unavailable";
  catalogue_is_synthetic: boolean;
  competition_context: UnknownDimension;
  current_validity: "current" | "needs_review" | "replaced" | "unavailable" | "withdrawn";
  data_quality: UnknownDimension;
  eligibility: EligibilityEngineResult;
  engine_version: "T28_v1";
  expires_at: string;
  preference_fit: UnknownDimension;
  profile_id: string;
  profile_is_synthetic: boolean;
  profile_sha256: string;
  profile_version: number;
  profile_version_id: string;
  release_id: string;
  replayed: boolean;
  requirements_version: string;
  result_sha256: string;
  rule_refs: RuleReference[];
  ruleset_version: null | string;
  stage: "application" | "enrollment";
  target: TargetReference;
  version: 1;
}

export interface AssessmentEnvelope_AssessmentContextData_ {
  data: AssessmentContextData;
  meta: ProfileMeta;
}

export interface AssessmentEnvelope_AssessmentData_ {
  data: AssessmentData;
  meta: ProfileMeta;
}

export interface AssessmentPair {
  achieved: GradeSlot;
  predicted: GradeSlot;
}

export interface AssessmentRequest {
  application_cycle: ScopeKey | null;
  batch_group: ScopeKey | null;
  channel: ScopeKey | null;
  confirmed: true;
  exam_system: ScopeKey | null;
  intake: ScopeKey | null;
  profile_id: string;
  profile_version_id: string;
  release_id: string;
  stage: "application" | "enrollment";
  subject_scope: ScopeKey | null;
  target: TargetReference;
}

export interface AuthCsrfData {
  csrf_token: string;
  expires_at: string;
}

export interface AuthLogoutData {
  logged_out: true;
}

export interface AuthSessionData {
  authenticated: true;
  expires_at: string;
  is_synthetic: boolean;
  private_business_available: false;
  user_id: string;
}

export interface AvailabilitySlot {
  end_at: string;
  slot_id: string;
  start_at: string;
}

export interface Budget {
  amount: string;
  currency: "CNY" | "GBP";
}

export interface CompleteInput {
  confirmed: true;
  expected_version: number;
}

export interface CompleteResult {
  execution: ExecutionData;
  replayed: boolean;
}

export interface CompleteV2LoginQuery {
  code?: null | string;
  error?: null | string;
  iss?: null | string;
  state: string;
}

export type CompleteV2LoginResponse303 = undefined;

export interface CompleteV2LoginResponse303Headers {
  Location: string;
  "Set-Cookie": string;
  "X-Request-ID": string;
}

export type CompleteV2LoginResponse401 = ErrorEnvelope;

export type CompleteV2LoginResponse403 = ErrorEnvelope;

export type CompleteV2LoginResponse404 = ErrorEnvelope;

export type CompleteV2LoginResponse405 = ErrorEnvelope;

export type CompleteV2LoginResponse409 = ErrorEnvelope;

export type CompleteV2LoginResponse422 = ErrorEnvelope;

export type CompleteV2LoginResponse429 = ErrorEnvelope;

export type CompleteV2LoginResponse500 = ErrorEnvelope;

export type CompleteV2LoginResponse503 = ErrorEnvelope;

export interface CompleteV2PlanTaskPath {
  plan_id: string;
  task_key: string;
}

export interface CompleteV2PlanTaskQuery {

}

export type CompleteV2PlanTaskRequestBody = CompleteInput;

export type CompleteV2PlanTaskResponse200 = PlanEnvelope_CompleteResult_;

export type CompleteV2PlanTaskResponse401 = ErrorEnvelope;

export type CompleteV2PlanTaskResponse403 = ErrorEnvelope;

export type CompleteV2PlanTaskResponse404 = ErrorEnvelope;

export type CompleteV2PlanTaskResponse405 = ErrorEnvelope;

export type CompleteV2PlanTaskResponse409 = ErrorEnvelope;

export type CompleteV2PlanTaskResponse422 = ErrorEnvelope;

export type CompleteV2PlanTaskResponse429 = ErrorEnvelope;

export type CompleteV2PlanTaskResponse500 = ErrorEnvelope;

export type CompleteV2PlanTaskResponse503 = ErrorEnvelope;

export interface CompletionData {
  completed_at: string;
  completed_state_version: number;
  source: "student_declared";
  task_key: string;
}

export interface CompletionObligation {
  assessment_key: "biology" | "chemistry" | "chinese" | "gaokao_english" | "gaokao_total" | "geography" | "history" | "ielts_listening" | "ielts_overall" | "ielts_reading" | "ielts_speaking" | "ielts_writing" | "math" | "physics" | "politics";
  basis: "achieved";
  deferral: DeferralResult;
}

export interface CompletionReference {
  completed_at: string;
  completed_state_version: number;
  completion_id: string;
  confirmation_id: string;
  source: "student_declared";
  task_key: string;
}

export interface ConfirmInput {
  acknowledge_unverified_deadlines: true;
  confirmed: true;
  expected_draft_sha256: string;
  expected_schedule_sha256: string;
  expected_version: number;
}

export interface ConfirmResult {
  confirmed_state_version: number;
  execution: ExecutionData;
  replayed: boolean;
}

export interface ConfirmV2CoreConsentQuery {

}

export type ConfirmV2CoreConsentRequestBody = CoreConsentInput;

export type ConfirmV2CoreConsentResponse200 = Envelope_AdmissionData_;

export type ConfirmV2CoreConsentResponse401 = ErrorEnvelope;

export type ConfirmV2CoreConsentResponse403 = ErrorEnvelope;

export type ConfirmV2CoreConsentResponse404 = ErrorEnvelope;

export type ConfirmV2CoreConsentResponse405 = ErrorEnvelope;

export type ConfirmV2CoreConsentResponse409 = ErrorEnvelope;

export type ConfirmV2CoreConsentResponse422 = ErrorEnvelope;

export type ConfirmV2CoreConsentResponse429 = ErrorEnvelope;

export type ConfirmV2CoreConsentResponse500 = ErrorEnvelope;

export type ConfirmV2CoreConsentResponse503 = ErrorEnvelope;

export interface ConfirmV2PlanHeaders {
  "Idempotency-Key": string;
}

export interface ConfirmV2PlanPath {
  plan_id: string;
}

export interface ConfirmV2PlanQuery {

}

export type ConfirmV2PlanRequestBody = ConfirmInput;

export type ConfirmV2PlanResponse200 = PlanEnvelope_ConfirmResult_;

export type ConfirmV2PlanResponse401 = ErrorEnvelope;

export type ConfirmV2PlanResponse403 = ErrorEnvelope;

export type ConfirmV2PlanResponse404 = ErrorEnvelope;

export type ConfirmV2PlanResponse405 = ErrorEnvelope;

export type ConfirmV2PlanResponse409 = ErrorEnvelope;

export type ConfirmV2PlanResponse422 = ErrorEnvelope;

export type ConfirmV2PlanResponse429 = ErrorEnvelope;

export type ConfirmV2PlanResponse500 = ErrorEnvelope;

export type ConfirmV2PlanResponse503 = ErrorEnvelope;

export interface ConfirmationData {
  acknowledge_unverified_deadlines: true;
  confirmed_at: string;
  confirmed_state_version: number;
  id: string;
  proposal_id: string;
}

export interface CoreConsentInput {
  confirmed: true;
  expected_revision: number;
  notice_id: string;
  purpose: "core_consultation";
}

export interface CreateGrantInput {
  actions: CreateGrantInput__actions__ItemType[];
  confirmed: true;
  expected_resource_version: number;
  expected_revision: number;
  expires_at: string;
  fields: CreateGrantInput__fields__ItemType[];
  grantee_user_id: string;
  owner_consent_id: string;
  resource_id: string;
  resource_type: "attachment" | "export" | "job" | "plan" | "profile";
  sharing_policy_hash: string;
  sharing_policy_version: string;
}

export type CreateGrantInput__actions__ItemType = "list" | "read";

export type CreateGrantInput__fields__ItemType = "status" | "version";

export interface CreateInput {
  confirmed: true;
  profile: ProfileSnapshot;
}

export interface CreateV2AccessGrantQuery {

}

export type CreateV2AccessGrantRequestBody = CreateGrantInput;

export type CreateV2AccessGrantResponse200 = Envelope_GrantMutationData_;

export type CreateV2AccessGrantResponse401 = ErrorEnvelope;

export type CreateV2AccessGrantResponse403 = ErrorEnvelope;

export type CreateV2AccessGrantResponse404 = ErrorEnvelope;

export type CreateV2AccessGrantResponse405 = ErrorEnvelope;

export type CreateV2AccessGrantResponse409 = ErrorEnvelope;

export type CreateV2AccessGrantResponse422 = ErrorEnvelope;

export type CreateV2AccessGrantResponse429 = ErrorEnvelope;

export type CreateV2AccessGrantResponse500 = ErrorEnvelope;

export type CreateV2AccessGrantResponse503 = ErrorEnvelope;

export interface CreateV2PlanQuery {

}

export type CreateV2PlanRequestBody = PlanCreateInput;

export type CreateV2PlanResponse200 = PlanEnvelope_ExecutionData_;

export type CreateV2PlanResponse401 = ErrorEnvelope;

export type CreateV2PlanResponse403 = ErrorEnvelope;

export type CreateV2PlanResponse404 = ErrorEnvelope;

export type CreateV2PlanResponse405 = ErrorEnvelope;

export type CreateV2PlanResponse409 = ErrorEnvelope;

export type CreateV2PlanResponse422 = ErrorEnvelope;

export type CreateV2PlanResponse429 = ErrorEnvelope;

export type CreateV2PlanResponse500 = ErrorEnvelope;

export type CreateV2PlanResponse503 = ErrorEnvelope;

export interface CreateV2ProfileHeaders {
  "Idempotency-Key": string;
}

export interface CreateV2ProfileQuery {

}

export type CreateV2ProfileRequestBody = CreateInput;

export type CreateV2ProfileResponse200 = ProfileEnvelope_ProfileWriteData_;

export type CreateV2ProfileResponse401 = ErrorEnvelope;

export type CreateV2ProfileResponse403 = ErrorEnvelope;

export type CreateV2ProfileResponse404 = ErrorEnvelope;

export type CreateV2ProfileResponse405 = ErrorEnvelope;

export type CreateV2ProfileResponse409 = ErrorEnvelope;

export type CreateV2ProfileResponse422 = ErrorEnvelope;

export type CreateV2ProfileResponse429 = ErrorEnvelope;

export type CreateV2ProfileResponse500 = ErrorEnvelope;

export type CreateV2ProfileResponse503 = ErrorEnvelope;

export interface DateEventData {
  calculated_utc_instant: null | string;
  conversion_status: "ambiguous" | "date_only" | "missing_timezone" | "nonexistent" | "out_of_range" | "source_conflict" | "unique" | "unknown";
  dataset_id: string;
  entry_year: number;
  event_type: "application_deadline" | "application_open" | "enrollment" | "equal_consideration" | "language_supplement" | "materials_deadline" | "offer_acceptance" | "scholarship_deadline" | "score_supplement";
  evidence_reference: null | string;
  evidence_state: "unresolved";
  id: string;
  is_synthetic: boolean;
  local_date: null | string;
  local_time: null | string;
  offering_id: string;
  offering_version: number;
  original_text: string;
  precision: "date" | "minute" | "second" | "unknown";
  reference_key: string;
  review_state: "draft";
  source_alignment: "conflict" | "pending";
  timezone: null | string;
  tzdata_version: "2026.4";
  utc_instant: null;
}

export interface DeadlineReference {
  assessment_id: string;
  assessment_key: string;
  deadline_key: string;
  event_id: null | string;
  local_date: null | string;
  local_time: null | string;
  official_utc_instant: null;
  precision: "date" | "minute" | "second" | "unknown" | null;
  purpose: "application" | "supplement";
  reference_calendar: null | string;
  status: "before" | "expired" | "not_applicable" | "unknown";
  timezone: null | string;
}

export interface DecideV2PlanRevisionPath {
  revision_id: string;
}

export interface DecideV2PlanRevisionQuery {

}

export type DecideV2PlanRevisionRequestBody = DecisionInput;

export type DecideV2PlanRevisionResponse200 = RevisionEnvelope_RevisionResult_;

export type DecideV2PlanRevisionResponse401 = ErrorEnvelope;

export type DecideV2PlanRevisionResponse403 = ErrorEnvelope;

export type DecideV2PlanRevisionResponse404 = ErrorEnvelope;

export type DecideV2PlanRevisionResponse405 = ErrorEnvelope;

export type DecideV2PlanRevisionResponse409 = ErrorEnvelope;

export type DecideV2PlanRevisionResponse422 = ErrorEnvelope;

export type DecideV2PlanRevisionResponse429 = ErrorEnvelope;

export type DecideV2PlanRevisionResponse500 = ErrorEnvelope;

export type DecideV2PlanRevisionResponse503 = ErrorEnvelope;

export interface DecisionInput {
  action: "accept" | "reject";
  expected_revision_version: number;
  student_confirmed: true;
}

export interface DeclareV2AgeQuery {

}

export type DeclareV2AgeRequestBody = AgeDeclarationInput;

export type DeclareV2AgeResponse200 = Envelope_AdmissionData_;

export type DeclareV2AgeResponse401 = ErrorEnvelope;

export type DeclareV2AgeResponse403 = ErrorEnvelope;

export type DeclareV2AgeResponse404 = ErrorEnvelope;

export type DeclareV2AgeResponse405 = ErrorEnvelope;

export type DeclareV2AgeResponse409 = ErrorEnvelope;

export type DeclareV2AgeResponse422 = ErrorEnvelope;

export type DeclareV2AgeResponse429 = ErrorEnvelope;

export type DeclareV2AgeResponse500 = ErrorEnvelope;

export type DeclareV2AgeResponse503 = ErrorEnvelope;

export interface DeferralResult {
  application_deadline_event_id: null | string;
  application_deadline_status: "before" | "expired" | "not_applicable" | "unknown";
  bundle_id: null | string;
  deferral_status: "allowed" | "unknown";
  evidence_ids: string[];
  policy_id: null | string;
  policy_version: null | string;
  reason: "ALLOWED" | "AMBIGUOUS_POLICIES" | "BINDING_UNVERIFIED" | "DEADLINE_EXPIRED" | "DEADLINE_MISMATCH" | "DEADLINE_MISSING" | "DEADLINE_UNCERTAIN" | "INVALID_BUNDLE" | "ITEM_NOT_ALLOWED" | "MISSING_STATE_NOT_ALLOWED" | "POLICY_DISABLED" | "POLICY_EXPIRED" | "POLICY_UNAVAILABLE" | "PREDICTED_NOT_ACHIEVED" | "REAL_POLICIES_UNAVAILABLE" | "RULESET_UNAVAILABLE" | "SCOPE_UNKNOWN" | "STAGE_MISMATCH" | "SYNTHETIC_BOUNDARY" | "TARGET_MISMATCH" | "VERIFIER_UNAVAILABLE" | "VERSION_MISMATCH" | "YEAR_MISMATCH";
  supplement_deadline_event_id: null | string;
  supplement_deadline_status: "before" | "expired" | "unknown";
}

export interface DraftTask {
  acceptance_criteria: string;
  action_code: "OBTAIN_ACHIEVED" | "PREPARE_MATERIALS" | "RECHECK_CONDITIONS" | "REVIEW_INELIGIBLE" | "SELF_DIRECTED_STUDY" | "VERIFY_HISTORY" | "VERIFY_UNKNOWN";
  assessment_ids: string[];
  assessment_key: "biology" | "chemistry" | "chinese" | "gaokao_english" | "gaokao_total" | "geography" | "history" | "ielts_listening" | "ielts_overall" | "ielts_reading" | "ielts_speaking" | "ielts_writing" | "math" | "physics" | "politics" | null;
  basis: "achieved" | null;
  confirmed: false;
  deadline_keys: string[];
  dependency_keys: string[];
  estimate_editable: true;
  estimate_source: "template" | "unknown" | "user_adjusted";
  estimated_hours: null | string;
  kind: "prepare" | "study" | "verify";
  scale: null | string;
  task_key: string;
  title: string;
  unit: "band" | "points" | null;
  work_scope_sha256: string;
}

export interface EligibilityEngineResult {
  evaluation: EvaluationResult | null;
  obligations: CompletionObligation[];
  reason: "BINDING_UNAVAILABLE" | "DEFERRAL_SATISFIABLE" | "DOMAIN_UNAVAILABLE" | "NO_COMPLETABLE_FIELD" | "RULESET_UNAVAILABLE" | "RULE_FALSE" | "RULE_TRUE" | "RULE_UNKNOWN" | "SCOPE_UNAVAILABLE" | "SEARCH_BUDGET_EXCEEDED";
  status: "conditional" | "eligible" | "ineligible" | "unknown";
}

export interface Envelope_AdmissionData_ {
  data: AdmissionData;
  meta: Meta;
}

export interface Envelope_AuthCsrfData_ {
  data: AuthCsrfData;
  meta: Meta;
}

export interface Envelope_AuthLogoutData_ {
  data: AuthLogoutData;
  meta: Meta;
}

export interface Envelope_AuthSessionData_ {
  data: AuthSessionData;
  meta: Meta;
}

export interface Envelope_FoundationConfig_ {
  data: FoundationConfig;
  meta: Meta;
}

export interface Envelope_GrantListData_ {
  data: GrantListData;
  meta: Meta;
}

export interface Envelope_GrantMutationData_ {
  data: GrantMutationData;
  meta: Meta;
}

export interface Envelope_Page_OfferingReference__ {
  data: Page_OfferingReference_;
  meta: Meta;
}

export interface Envelope_PrivacyNoticeData_ {
  data: PrivacyNoticeData;
  meta: Meta;
}

export interface Envelope_SharingPolicyData_ {
  data: SharingPolicyData;
  meta: Meta;
}

export interface ErrorBody {
  code: "CONFLICT" | "FORBIDDEN" | "INTERNAL_ERROR" | "INVALID_CURSOR" | "METHOD_NOT_ALLOWED" | "NOT_FOUND" | "SERVICE_UNAVAILABLE" | "TOO_MANY_REQUESTS" | "UNAUTHORIZED" | "VALIDATION_ERROR";
  details: ErrorDetail[];
  message: string;
  request_id: string;
}

export interface ErrorDetail {
  code: string;
  field_path: string;
  message: string;
}

export interface ErrorEnvelope {
  error: ErrorBody;
}

export interface EstimateOverride {
  estimated_hours: null | string;
  task_key: string;
}

export interface EvaluateV2EligibilityQuery {

}

export type EvaluateV2EligibilityRequestBody = AssessmentRequest;

export type EvaluateV2EligibilityResponse200 = AssessmentEnvelope_AssessmentData_;

export type EvaluateV2EligibilityResponse401 = ErrorEnvelope;

export type EvaluateV2EligibilityResponse403 = ErrorEnvelope;

export type EvaluateV2EligibilityResponse404 = ErrorEnvelope;

export type EvaluateV2EligibilityResponse405 = ErrorEnvelope;

export type EvaluateV2EligibilityResponse409 = ErrorEnvelope;

export type EvaluateV2EligibilityResponse422 = ErrorEnvelope;

export type EvaluateV2EligibilityResponse429 = ErrorEnvelope;

export type EvaluateV2EligibilityResponse500 = ErrorEnvelope;

export type EvaluateV2EligibilityResponse503 = ErrorEnvelope;

export interface EvaluationResult {
  reason: "CALENDAR_MISMATCH" | "CONFLICTED" | "MATCH" | "MISSING" | "NOT_APPLICABLE" | "NO_MATCH" | "PENDING" | "PRECISION_MISMATCH" | "PREDICTED_NOT_ACHIEVED" | "REFERENCE_MISSING" | "SCALE_MISMATCH" | "TYPE_MISMATCH" | "UNIT_MISMATCH" | "UNKNOWN_CHILD";
  trace: TraceNode[];
  truth: "false" | "true" | "unknown";
}

export interface ExecutionContextData {
  can_complete: boolean;
  can_confirm: boolean;
  can_create: boolean;
  can_edit: boolean;
  can_read: boolean;
  is_synthetic: boolean;
  reason: "processing_disabled" | "ready";
  schema_version: "v2.t32";
}

export interface ExecutionData {
  completed_tasks: CompletionData[];
  confirmation: ConfirmationData | null;
  created_at: string;
  expires_at: string;
  is_synthetic: boolean;
  plan_id: string;
  proposal: ProposalData;
  schema_version: "v2.t32";
  source_draft_sha256: string;
  source_plan_version_id: string;
  state: "confirmed" | "draft";
  state_version: number;
}

export interface ExecutionPage {
  items: ExecutionSummary[];
  next_cursor: null | string;
}

export interface ExecutionSummary {
  completed_count: number;
  confirmation_id: null | string;
  created_at: string;
  draft_sha256: string;
  expires_at: string;
  is_synthetic: boolean;
  plan_id: string;
  proposal_id: string;
  schedule_sha256: null | string;
  state: "confirmed" | "draft";
  state_version: number;
}

export interface FieldRef {
  basis?: "achieved" | "predicted" | null;
  key?: "biology" | "chemistry" | "chinese" | "gaokao_english" | "gaokao_total" | "geography" | "history" | "ielts_listening" | "ielts_overall" | "ielts_reading" | "ielts_speaking" | "ielts_writing" | "math" | "physics" | "politics" | null;
  name: "applicant_category" | "assessment" | "assessment_at" | "assessment_date" | "course_system" | "entry_year" | "exam_province" | "pathway" | "residence_region" | "study_level" | "subjects";
}

export interface FoundationConfig {
  api_version: "v2";
  app_environment: "development" | "production" | "test";
  business_available: false;
  contract_stage: "foundation";
  data_mode: "demo" | "verified";
  entry_year: null;
  live_available: false;
  model_mode: "disabled" | "mock";
  query_role: "demo_only" | "published_readonly";
  schema_version: "v2.t03";
  supported_province: null;
  supported_scope: string[];
}

export interface GetV2AdmissionQuery {

}

export type GetV2AdmissionResponse200 = Envelope_AdmissionData_;

export type GetV2AdmissionResponse401 = ErrorEnvelope;

export type GetV2AdmissionResponse403 = ErrorEnvelope;

export type GetV2AdmissionResponse404 = ErrorEnvelope;

export type GetV2AdmissionResponse405 = ErrorEnvelope;

export type GetV2AdmissionResponse409 = ErrorEnvelope;

export type GetV2AdmissionResponse422 = ErrorEnvelope;

export type GetV2AdmissionResponse429 = ErrorEnvelope;

export type GetV2AdmissionResponse500 = ErrorEnvelope;

export type GetV2AdmissionResponse503 = ErrorEnvelope;

export interface GetV2ConfigQuery {

}

export type GetV2ConfigResponse200 = Envelope_FoundationConfig_;

export type GetV2ConfigResponse401 = ErrorEnvelope;

export type GetV2ConfigResponse403 = ErrorEnvelope;

export type GetV2ConfigResponse404 = ErrorEnvelope;

export type GetV2ConfigResponse405 = ErrorEnvelope;

export type GetV2ConfigResponse409 = ErrorEnvelope;

export type GetV2ConfigResponse422 = ErrorEnvelope;

export type GetV2ConfigResponse429 = ErrorEnvelope;

export type GetV2ConfigResponse500 = ErrorEnvelope;

export type GetV2ConfigResponse503 = ErrorEnvelope;

export interface GetV2CsrfQuery {

}

export type GetV2CsrfResponse200 = Envelope_AuthCsrfData_;

export type GetV2CsrfResponse401 = ErrorEnvelope;

export type GetV2CsrfResponse403 = ErrorEnvelope;

export type GetV2CsrfResponse404 = ErrorEnvelope;

export type GetV2CsrfResponse405 = ErrorEnvelope;

export type GetV2CsrfResponse409 = ErrorEnvelope;

export type GetV2CsrfResponse422 = ErrorEnvelope;

export type GetV2CsrfResponse429 = ErrorEnvelope;

export type GetV2CsrfResponse500 = ErrorEnvelope;

export type GetV2CsrfResponse503 = ErrorEnvelope;

export interface GetV2EligibilityContextQuery {

}

export type GetV2EligibilityContextResponse200 = AssessmentEnvelope_AssessmentContextData_;

export type GetV2EligibilityContextResponse401 = ErrorEnvelope;

export type GetV2EligibilityContextResponse403 = ErrorEnvelope;

export type GetV2EligibilityContextResponse404 = ErrorEnvelope;

export type GetV2EligibilityContextResponse405 = ErrorEnvelope;

export type GetV2EligibilityContextResponse409 = ErrorEnvelope;

export type GetV2EligibilityContextResponse422 = ErrorEnvelope;

export type GetV2EligibilityContextResponse429 = ErrorEnvelope;

export type GetV2EligibilityContextResponse500 = ErrorEnvelope;

export type GetV2EligibilityContextResponse503 = ErrorEnvelope;

export interface GetV2EligibilityEvaluationPath {
  assessment_id: string;
}

export interface GetV2EligibilityEvaluationQuery {

}

export type GetV2EligibilityEvaluationResponse200 = AssessmentEnvelope_AssessmentData_;

export type GetV2EligibilityEvaluationResponse401 = ErrorEnvelope;

export type GetV2EligibilityEvaluationResponse403 = ErrorEnvelope;

export type GetV2EligibilityEvaluationResponse404 = ErrorEnvelope;

export type GetV2EligibilityEvaluationResponse405 = ErrorEnvelope;

export type GetV2EligibilityEvaluationResponse409 = ErrorEnvelope;

export type GetV2EligibilityEvaluationResponse422 = ErrorEnvelope;

export type GetV2EligibilityEvaluationResponse429 = ErrorEnvelope;

export type GetV2EligibilityEvaluationResponse500 = ErrorEnvelope;

export type GetV2EligibilityEvaluationResponse503 = ErrorEnvelope;

export interface GetV2NotificationContextQuery {

}

export type GetV2NotificationContextResponse200 = NotificationEnvelope_NotificationContextData_;

export type GetV2NotificationContextResponse401 = ErrorEnvelope;

export type GetV2NotificationContextResponse403 = ErrorEnvelope;

export type GetV2NotificationContextResponse404 = ErrorEnvelope;

export type GetV2NotificationContextResponse405 = ErrorEnvelope;

export type GetV2NotificationContextResponse409 = ErrorEnvelope;

export type GetV2NotificationContextResponse422 = ErrorEnvelope;

export type GetV2NotificationContextResponse429 = ErrorEnvelope;

export type GetV2NotificationContextResponse500 = ErrorEnvelope;

export type GetV2NotificationContextResponse503 = ErrorEnvelope;

export interface GetV2NotificationPreferencesQuery {

}

export type GetV2NotificationPreferencesResponse200 = NotificationEnvelope_NotificationPreferenceData_;

export type GetV2NotificationPreferencesResponse401 = ErrorEnvelope;

export type GetV2NotificationPreferencesResponse403 = ErrorEnvelope;

export type GetV2NotificationPreferencesResponse404 = ErrorEnvelope;

export type GetV2NotificationPreferencesResponse405 = ErrorEnvelope;

export type GetV2NotificationPreferencesResponse409 = ErrorEnvelope;

export type GetV2NotificationPreferencesResponse422 = ErrorEnvelope;

export type GetV2NotificationPreferencesResponse429 = ErrorEnvelope;

export type GetV2NotificationPreferencesResponse500 = ErrorEnvelope;

export type GetV2NotificationPreferencesResponse503 = ErrorEnvelope;

export interface GetV2PlanPath {
  plan_id: string;
}

export interface GetV2PlanQuery {

}

export type GetV2PlanResponse200 = PlanEnvelope_ExecutionData_;

export type GetV2PlanResponse401 = ErrorEnvelope;

export type GetV2PlanResponse403 = ErrorEnvelope;

export type GetV2PlanResponse404 = ErrorEnvelope;

export type GetV2PlanResponse405 = ErrorEnvelope;

export type GetV2PlanResponse409 = ErrorEnvelope;

export type GetV2PlanResponse422 = ErrorEnvelope;

export type GetV2PlanResponse429 = ErrorEnvelope;

export type GetV2PlanResponse500 = ErrorEnvelope;

export type GetV2PlanResponse503 = ErrorEnvelope;

export interface GetV2PlanRevisionHistoryPath {
  plan_id: string;
}

export interface GetV2PlanRevisionHistoryQuery {

}

export type GetV2PlanRevisionHistoryResponse200 = RevisionEnvelope_RevisionHistoryData_;

export type GetV2PlanRevisionHistoryResponse401 = ErrorEnvelope;

export type GetV2PlanRevisionHistoryResponse403 = ErrorEnvelope;

export type GetV2PlanRevisionHistoryResponse404 = ErrorEnvelope;

export type GetV2PlanRevisionHistoryResponse405 = ErrorEnvelope;

export type GetV2PlanRevisionHistoryResponse409 = ErrorEnvelope;

export type GetV2PlanRevisionHistoryResponse422 = ErrorEnvelope;

export type GetV2PlanRevisionHistoryResponse429 = ErrorEnvelope;

export type GetV2PlanRevisionHistoryResponse500 = ErrorEnvelope;

export type GetV2PlanRevisionHistoryResponse503 = ErrorEnvelope;

export interface GetV2PlanRevisionPath {
  revision_id: string;
}

export interface GetV2PlanRevisionQuery {

}

export type GetV2PlanRevisionResponse200 = RevisionEnvelope_RevisionData_;

export type GetV2PlanRevisionResponse401 = ErrorEnvelope;

export type GetV2PlanRevisionResponse403 = ErrorEnvelope;

export type GetV2PlanRevisionResponse404 = ErrorEnvelope;

export type GetV2PlanRevisionResponse405 = ErrorEnvelope;

export type GetV2PlanRevisionResponse409 = ErrorEnvelope;

export type GetV2PlanRevisionResponse422 = ErrorEnvelope;

export type GetV2PlanRevisionResponse429 = ErrorEnvelope;

export type GetV2PlanRevisionResponse500 = ErrorEnvelope;

export type GetV2PlanRevisionResponse503 = ErrorEnvelope;

export interface GetV2PlanVersionPath {
  plan_id: string;
  state_version: number;
}

export interface GetV2PlanVersionQuery {

}

export type GetV2PlanVersionResponse200 = PlanEnvelope_ExecutionData_;

export type GetV2PlanVersionResponse401 = ErrorEnvelope;

export type GetV2PlanVersionResponse403 = ErrorEnvelope;

export type GetV2PlanVersionResponse404 = ErrorEnvelope;

export type GetV2PlanVersionResponse405 = ErrorEnvelope;

export type GetV2PlanVersionResponse409 = ErrorEnvelope;

export type GetV2PlanVersionResponse422 = ErrorEnvelope;

export type GetV2PlanVersionResponse429 = ErrorEnvelope;

export type GetV2PlanVersionResponse500 = ErrorEnvelope;

export type GetV2PlanVersionResponse503 = ErrorEnvelope;

export interface GetV2PlansContextQuery {

}

export type GetV2PlansContextResponse200 = PlanEnvelope_ExecutionContextData_;

export type GetV2PlansContextResponse401 = ErrorEnvelope;

export type GetV2PlansContextResponse403 = ErrorEnvelope;

export type GetV2PlansContextResponse404 = ErrorEnvelope;

export type GetV2PlansContextResponse405 = ErrorEnvelope;

export type GetV2PlansContextResponse409 = ErrorEnvelope;

export type GetV2PlansContextResponse422 = ErrorEnvelope;

export type GetV2PlansContextResponse429 = ErrorEnvelope;

export type GetV2PlansContextResponse500 = ErrorEnvelope;

export type GetV2PlansContextResponse503 = ErrorEnvelope;

export interface GetV2PrivacyNoticeQuery {

}

export type GetV2PrivacyNoticeResponse200 = Envelope_PrivacyNoticeData_;

export type GetV2PrivacyNoticeResponse401 = ErrorEnvelope;

export type GetV2PrivacyNoticeResponse403 = ErrorEnvelope;

export type GetV2PrivacyNoticeResponse404 = ErrorEnvelope;

export type GetV2PrivacyNoticeResponse405 = ErrorEnvelope;

export type GetV2PrivacyNoticeResponse409 = ErrorEnvelope;

export type GetV2PrivacyNoticeResponse422 = ErrorEnvelope;

export type GetV2PrivacyNoticeResponse429 = ErrorEnvelope;

export type GetV2PrivacyNoticeResponse500 = ErrorEnvelope;

export type GetV2PrivacyNoticeResponse503 = ErrorEnvelope;

export interface GetV2ProfilePath {
  profile_id: string;
}

export interface GetV2ProfileQuery {

}

export type GetV2ProfileResponse200 = ProfileEnvelope_ProfileVersionData_;

export type GetV2ProfileResponse401 = ErrorEnvelope;

export type GetV2ProfileResponse403 = ErrorEnvelope;

export type GetV2ProfileResponse404 = ErrorEnvelope;

export type GetV2ProfileResponse405 = ErrorEnvelope;

export type GetV2ProfileResponse409 = ErrorEnvelope;

export type GetV2ProfileResponse422 = ErrorEnvelope;

export type GetV2ProfileResponse429 = ErrorEnvelope;

export type GetV2ProfileResponse500 = ErrorEnvelope;

export type GetV2ProfileResponse503 = ErrorEnvelope;

export interface GetV2ProfileVersionPath {
  profile_id: string;
  version_id: string;
}

export interface GetV2ProfileVersionQuery {

}

export type GetV2ProfileVersionResponse200 = ProfileEnvelope_ProfileVersionData_;

export type GetV2ProfileVersionResponse401 = ErrorEnvelope;

export type GetV2ProfileVersionResponse403 = ErrorEnvelope;

export type GetV2ProfileVersionResponse404 = ErrorEnvelope;

export type GetV2ProfileVersionResponse405 = ErrorEnvelope;

export type GetV2ProfileVersionResponse409 = ErrorEnvelope;

export type GetV2ProfileVersionResponse422 = ErrorEnvelope;

export type GetV2ProfileVersionResponse429 = ErrorEnvelope;

export type GetV2ProfileVersionResponse500 = ErrorEnvelope;

export type GetV2ProfileVersionResponse503 = ErrorEnvelope;

export interface GetV2ProfilesContextQuery {

}

export type GetV2ProfilesContextResponse200 = ProfileEnvelope_ProfileContextData_;

export type GetV2ProfilesContextResponse401 = ErrorEnvelope;

export type GetV2ProfilesContextResponse403 = ErrorEnvelope;

export type GetV2ProfilesContextResponse404 = ErrorEnvelope;

export type GetV2ProfilesContextResponse405 = ErrorEnvelope;

export type GetV2ProfilesContextResponse409 = ErrorEnvelope;

export type GetV2ProfilesContextResponse422 = ErrorEnvelope;

export type GetV2ProfilesContextResponse429 = ErrorEnvelope;

export type GetV2ProfilesContextResponse500 = ErrorEnvelope;

export type GetV2ProfilesContextResponse503 = ErrorEnvelope;

export interface GetV2RevisionContextQuery {

}

export type GetV2RevisionContextResponse200 = RevisionEnvelope_RevisionContextData_;

export type GetV2RevisionContextResponse401 = ErrorEnvelope;

export type GetV2RevisionContextResponse403 = ErrorEnvelope;

export type GetV2RevisionContextResponse404 = ErrorEnvelope;

export type GetV2RevisionContextResponse405 = ErrorEnvelope;

export type GetV2RevisionContextResponse409 = ErrorEnvelope;

export type GetV2RevisionContextResponse422 = ErrorEnvelope;

export type GetV2RevisionContextResponse429 = ErrorEnvelope;

export type GetV2RevisionContextResponse500 = ErrorEnvelope;

export type GetV2RevisionContextResponse503 = ErrorEnvelope;

export interface GetV2SessionQuery {

}

export type GetV2SessionResponse200 = Envelope_AuthSessionData_;

export type GetV2SessionResponse401 = ErrorEnvelope;

export type GetV2SessionResponse403 = ErrorEnvelope;

export type GetV2SessionResponse404 = ErrorEnvelope;

export type GetV2SessionResponse405 = ErrorEnvelope;

export type GetV2SessionResponse409 = ErrorEnvelope;

export type GetV2SessionResponse422 = ErrorEnvelope;

export type GetV2SessionResponse429 = ErrorEnvelope;

export type GetV2SessionResponse500 = ErrorEnvelope;

export type GetV2SessionResponse503 = ErrorEnvelope;

export interface GetV2SharingPolicyQuery {

}

export type GetV2SharingPolicyResponse200 = Envelope_SharingPolicyData_;

export type GetV2SharingPolicyResponse401 = ErrorEnvelope;

export type GetV2SharingPolicyResponse403 = ErrorEnvelope;

export type GetV2SharingPolicyResponse404 = ErrorEnvelope;

export type GetV2SharingPolicyResponse405 = ErrorEnvelope;

export type GetV2SharingPolicyResponse409 = ErrorEnvelope;

export type GetV2SharingPolicyResponse422 = ErrorEnvelope;

export type GetV2SharingPolicyResponse429 = ErrorEnvelope;

export type GetV2SharingPolicyResponse500 = ErrorEnvelope;

export type GetV2SharingPolicyResponse503 = ErrorEnvelope;

export interface GradeAssessments {
  biology?: AssessmentPair;
  chemistry?: AssessmentPair;
  chinese?: AssessmentPair;
  gaokao_english?: AssessmentPair;
  gaokao_total?: AssessmentPair;
  geography?: AssessmentPair;
  history?: AssessmentPair;
  ielts_listening?: AssessmentPair;
  ielts_overall?: AssessmentPair;
  ielts_reading?: AssessmentPair;
  ielts_speaking?: AssessmentPair;
  ielts_writing?: AssessmentPair;
  math?: AssessmentPair;
  physics?: AssessmentPair;
  politics?: AssessmentPair;
}

export interface GradeSlot {
  scale: null | string;
  status: "missing" | "not_applicable" | "pending" | "provided";
  unit: "band" | "points" | null;
  value: null | string;
}

export interface GrantData {
  accepted_at: null | string;
  access_active: boolean;
  actions: GrantData__actions__ItemType[];
  created_at: string;
  expires_at: string;
  fields: GrantData__fields__ItemType[];
  grantee_user_id: string;
  id: string;
  is_synthetic: boolean;
  owner_user_id: string;
  resource_id: string;
  resource_type: "attachment" | "export" | "job" | "plan" | "profile";
  resource_version: number;
  revoked_at: null | string;
  sharing_policy_version: string;
  state: "accepted" | "pending" | "revoked";
  version: number;
}

export type GrantData__actions__ItemType = "list" | "read";

export type GrantData__fields__ItemType = "status" | "version";

export interface GrantListData {
  actor_declaration_id: null | string;
  items: GrantData[];
  owner_consent_id: null | string;
  page: PageInfo;
  revision: number;
  sharing_available: boolean;
  total: number;
  user_id: string;
}

export interface GrantMutationData {
  grant: GrantData;
  revision: number;
  user_id: string;
}

export interface HistoricalSchedule {
  allocations: ScheduleAllocation[];
  constraints_complete: false;
  display_timezone: string;
  generated_at: string;
  horizon_end: string;
  horizon_start: string;
  status: "blocked" | "partial" | "ready";
  tasks: TaskSchedule[];
  weekly_hours: null | string;
}

export interface HttpAvailabilitySlot {
  end_at: string;
  slot_id: string;
  start_at: string;
}

export interface HttpInternalGoal {
  due_at: string;
  task_key: string;
}

export interface HttpScheduleConfiguration {
  availability_confirmed: true;
  display_timezone: string;
  horizon_end: string;
  horizon_start: string;
  internal_goals: HttpInternalGoal[];
  rest_excluded: true;
  slots: HttpAvailabilitySlot[];
  weekly_hours: null | string;
}

export interface HttpWorkspaceInput {
  estimate_overrides: EstimateOverride[];
  expected_version: number;
  schedule: HttpScheduleConfiguration | null;
}

export interface InternalGoal {
  due_at: string;
  task_key: string;
}

export interface ListV2AccessGrantsQuery {
  after_id?: null | string;
  direction?: "issued" | "received";
  limit?: number;
}

export type ListV2AccessGrantsResponse200 = Envelope_GrantListData_;

export type ListV2AccessGrantsResponse401 = ErrorEnvelope;

export type ListV2AccessGrantsResponse403 = ErrorEnvelope;

export type ListV2AccessGrantsResponse404 = ErrorEnvelope;

export type ListV2AccessGrantsResponse405 = ErrorEnvelope;

export type ListV2AccessGrantsResponse409 = ErrorEnvelope;

export type ListV2AccessGrantsResponse422 = ErrorEnvelope;

export type ListV2AccessGrantsResponse429 = ErrorEnvelope;

export type ListV2AccessGrantsResponse500 = ErrorEnvelope;

export type ListV2AccessGrantsResponse503 = ErrorEnvelope;

export interface ListV2NotificationsQuery {
  cursor?: string;
  limit?: number;
}

export type ListV2NotificationsResponse200 = NotificationEnvelope_NotificationPage_;

export type ListV2NotificationsResponse401 = ErrorEnvelope;

export type ListV2NotificationsResponse403 = ErrorEnvelope;

export type ListV2NotificationsResponse404 = ErrorEnvelope;

export type ListV2NotificationsResponse405 = ErrorEnvelope;

export type ListV2NotificationsResponse409 = ErrorEnvelope;

export type ListV2NotificationsResponse422 = ErrorEnvelope;

export type ListV2NotificationsResponse429 = ErrorEnvelope;

export type ListV2NotificationsResponse500 = ErrorEnvelope;

export type ListV2NotificationsResponse503 = ErrorEnvelope;

export interface ListV2OfferingsQuery {
  cursor?: null | string;
  limit?: number;
}

export type ListV2OfferingsResponse200 = Envelope_Page_OfferingReference__;

export type ListV2OfferingsResponse401 = ErrorEnvelope;

export type ListV2OfferingsResponse403 = ErrorEnvelope;

export type ListV2OfferingsResponse404 = ErrorEnvelope;

export type ListV2OfferingsResponse405 = ErrorEnvelope;

export type ListV2OfferingsResponse409 = ErrorEnvelope;

export type ListV2OfferingsResponse422 = ErrorEnvelope;

export type ListV2OfferingsResponse429 = ErrorEnvelope;

export type ListV2OfferingsResponse500 = ErrorEnvelope;

export type ListV2OfferingsResponse503 = ErrorEnvelope;

export interface ListV2PlansQuery {
  cursor?: string;
  limit?: number;
}

export type ListV2PlansResponse200 = PlanEnvelope_ExecutionPage_;

export type ListV2PlansResponse401 = ErrorEnvelope;

export type ListV2PlansResponse403 = ErrorEnvelope;

export type ListV2PlansResponse404 = ErrorEnvelope;

export type ListV2PlansResponse405 = ErrorEnvelope;

export type ListV2PlansResponse409 = ErrorEnvelope;

export type ListV2PlansResponse422 = ErrorEnvelope;

export type ListV2PlansResponse429 = ErrorEnvelope;

export type ListV2PlansResponse500 = ErrorEnvelope;

export type ListV2PlansResponse503 = ErrorEnvelope;

export interface ListV2ProfilesQuery {
  cursor?: string;
  limit?: number;
}

export type ListV2ProfilesResponse200 = ProfileEnvelope_ProfilePage_;

export type ListV2ProfilesResponse401 = ErrorEnvelope;

export type ListV2ProfilesResponse403 = ErrorEnvelope;

export type ListV2ProfilesResponse404 = ErrorEnvelope;

export type ListV2ProfilesResponse405 = ErrorEnvelope;

export type ListV2ProfilesResponse409 = ErrorEnvelope;

export type ListV2ProfilesResponse422 = ErrorEnvelope;

export type ListV2ProfilesResponse429 = ErrorEnvelope;

export type ListV2ProfilesResponse500 = ErrorEnvelope;

export type ListV2ProfilesResponse503 = ErrorEnvelope;

export interface LogoutV2SessionQuery {

}

export type LogoutV2SessionResponse200 = Envelope_AuthLogoutData_;

export type LogoutV2SessionResponse401 = ErrorEnvelope;

export type LogoutV2SessionResponse403 = ErrorEnvelope;

export type LogoutV2SessionResponse404 = ErrorEnvelope;

export type LogoutV2SessionResponse405 = ErrorEnvelope;

export type LogoutV2SessionResponse409 = ErrorEnvelope;

export type LogoutV2SessionResponse422 = ErrorEnvelope;

export type LogoutV2SessionResponse429 = ErrorEnvelope;

export type LogoutV2SessionResponse500 = ErrorEnvelope;

export type LogoutV2SessionResponse503 = ErrorEnvelope;

export interface MarkReadInput {
  expected_version: number;
  student_confirmed: true;
}

export interface MarkV2NotificationReadPath {
  notification_id: string;
}

export interface MarkV2NotificationReadQuery {

}

export type MarkV2NotificationReadRequestBody = MarkReadInput;

export type MarkV2NotificationReadResponse200 = NotificationEnvelope_NotificationData_;

export type MarkV2NotificationReadResponse401 = ErrorEnvelope;

export type MarkV2NotificationReadResponse403 = ErrorEnvelope;

export type MarkV2NotificationReadResponse404 = ErrorEnvelope;

export type MarkV2NotificationReadResponse405 = ErrorEnvelope;

export type MarkV2NotificationReadResponse409 = ErrorEnvelope;

export type MarkV2NotificationReadResponse422 = ErrorEnvelope;

export type MarkV2NotificationReadResponse429 = ErrorEnvelope;

export type MarkV2NotificationReadResponse500 = ErrorEnvelope;

export type MarkV2NotificationReadResponse503 = ErrorEnvelope;

export interface Meta {
  api_version: "v2";
  data_as_of: null;
  data_mode: "demo" | "verified";
  model_mode: "disabled" | "mock";
  profile_mode: null;
  profile_version_id: null;
  release_id: null;
  request_id: string;
  ruleset_version: null;
}

export interface NotificationContextData {
  can_manage_preferences: boolean;
  can_mark_read: boolean;
  can_read: boolean;
  delivery_channel: "in_app";
  external_delivery_enabled: false;
  is_synthetic: boolean;
  schema_version: "v2.t36";
}

export interface NotificationData {
  after_release_id: null | string;
  assessment_id: string;
  before_release_id: null | string;
  created_at: string;
  dataset_id: string;
  entry_year: number;
  event_id: string;
  expires_at: string;
  id: string;
  is_synthetic: boolean;
  needs_review: boolean;
  offering_id: string;
  offering_version: number;
  profile_id: string;
  profile_sha256: string;
  profile_version_id: string;
  read_at: null | string;
  reason: "BUSINESS_CHANGED" | "MEMBER_ADDED" | "MEMBER_REMOVED" | "REFERENCE_REPLACED" | "RELEASE_WINDOW_CHANGED" | "RELEASE_WITHDRAWN" | "RULESET_CHANGED";
  version: number;
}

export interface NotificationEnvelope_NotificationContextData_ {
  data: NotificationContextData;
  meta: ProfileMeta;
}

export interface NotificationEnvelope_NotificationData_ {
  data: NotificationData;
  meta: ProfileMeta;
}

export interface NotificationEnvelope_NotificationPage_ {
  data: NotificationPage;
  meta: ProfileMeta;
}

export interface NotificationEnvelope_NotificationPreferenceData_ {
  data: NotificationPreferenceData;
  meta: ProfileMeta;
}

export interface NotificationPage {
  items: NotificationData[];
  next_cursor: null | string;
}

export interface NotificationPreferenceData {
  enabled: boolean;
  is_synthetic: boolean;
  profile_id: null | string;
  profile_sha256: null | string;
  profile_version_id: null | string;
  updated_at: null | string;
  version: number;
}

export interface OfferingReference {
  id: string;
}

export interface PageInfo {
  has_more: boolean;
  limit: number;
  next_cursor: null | string;
}

export interface Page_OfferingReference_ {
  items: OfferingReference[];
  page: PageInfo;
}

export interface PlanAssessmentRef {
  assessment_id: string;
  current_validity: "current" | "needs_review" | "replaced" | "unavailable" | "withdrawn";
  eligibility_status: "conditional" | "eligible" | "ineligible" | "unknown";
  release_id: string;
  requirements_version: string;
  result_sha256: string;
  rule_refs: RuleReference[];
  ruleset_version: null | string;
  stage: "application" | "enrollment";
  target: TargetReference;
}

export interface PlanCreateInput {
  assessment_ids: string[];
  confirmed: true;
  estimate_overrides?: EstimateOverride[];
  study_goals?: StudyGoalInput[];
}

export interface PlanDeadlineRef {
  assessment_id: string;
  assessment_key: "biology" | "chemistry" | "chinese" | "gaokao_english" | "gaokao_total" | "geography" | "history" | "ielts_listening" | "ielts_overall" | "ielts_reading" | "ielts_speaking" | "ielts_writing" | "math" | "physics" | "politics";
  bundle_id: string;
  date_event: DateEventData | null;
  deadline_key: string;
  event_id: null | string;
  evidence_ids: string[];
  policy_id: string;
  policy_version: string;
  purpose: "application" | "supplement";
  reference_calendar: null | string;
  status: "before" | "expired" | "not_applicable" | "unknown";
}

export interface PlanDraft {
  assessment_refs: PlanAssessmentRef[];
  confirmed: false;
  deadline_refs: PlanDeadlineRef[];
  draft_sha256: string;
  expires_at: string;
  generated_at: string;
  generator_version: "T30_v1";
  is_synthetic: boolean;
  profile_id: string;
  profile_sha256: string;
  profile_version_id: string;
  scheduled: false;
  schema_version: "T30_v1";
  status: "draft";
  tasks: DraftTask[];
  warnings: PlanDraft__warnings__ItemType[];
}

export type PlanDraft__warnings__ItemType = "DEADLINE_SNAPSHOT_UNAVAILABLE" | "ESTIMATES_ARE_EDITABLE" | "HISTORICAL_RESULT_REQUIRES_REVIEW" | "NOT_SCHEDULED" | "NO_EDUCATIONAL_DIAGNOSIS" | "RULES_UNAVAILABLE" | "UNCONFIRMED_DRAFT";

export interface PlanEnvelope_CompleteResult_ {
  data: CompleteResult;
  meta: PlanMeta;
}

export interface PlanEnvelope_ConfirmResult_ {
  data: ConfirmResult;
  meta: PlanMeta;
}

export interface PlanEnvelope_ExecutionContextData_ {
  data: ExecutionContextData;
  meta: PlanMeta;
}

export interface PlanEnvelope_ExecutionData_ {
  data: ExecutionData;
  meta: PlanMeta;
}

export interface PlanEnvelope_ExecutionPage_ {
  data: ExecutionPage;
  meta: PlanMeta;
}

export interface PlanMeta {
  api_version: "v2";
  data_as_of: null;
  data_mode: "demo" | "verified";
  model_mode: "disabled" | "mock";
  profile_mode: "real" | "synthetic" | null;
  profile_version_id: null | string;
  release_id: null;
  request_id: string;
  ruleset_version: null;
}

export interface PlanPin {
  confirmation_id: null | string;
  draft_sha256: string;
  is_synthetic: boolean;
  plan_id: string;
  profile_id: string;
  profile_sha256: string;
  profile_version: number;
  profile_version_id: string;
  proposal_id: string;
  proposal_state_version: number;
  schedule_sha256: null | string;
  source_draft_sha256: string;
  source_plan_version_id: string;
  state: "confirmed" | "draft";
  state_version: number;
}

export interface PreferenceInput {
  enabled: boolean;
  expected_version: number;
  profile_id: null | string;
  student_confirmed: true;
}

export interface Preferences {
  budget: Budget | null;
  preferred_countries: Preferences__preferred_countries__ItemType[];
  preferred_fields: string[];
}

export type Preferences__preferred_countries__ItemType = "CN" | "GB";

export interface PrivacyAgePolicy {
  age_14_17: "private_disabled";
  age_18_plus: "self_declaration_and_confirmation";
  declaration_is_verification: false;
  guardian_verification_available: false;
  under_14: "public_only";
  unknown: "public_only";
}

export interface PrivacyNoticeData {
  age_policy: PrivacyAgePolicy;
  is_synthetic: boolean;
  notice_hash: string;
  notice_id: null | string;
  notice_version: null | string;
  policy_version: string;
  purposes: "core_consultation"[];
  readiness: boolean;
  readiness_reason: "processing_disabled" | "test_fixture_ready";
  retention_policy: PrivacyRetentionPolicy;
  text: string;
}

export interface PrivacyRetentionPolicy {
  audit_authorization_max_months: 24;
  backup_max_days: 35;
  cleanup_implemented: false;
  file_types: PrivacyRetentionPolicy__file_types__ItemType[];
  max_file_bytes: 10485760;
  online_deletion_max_days: 30;
  private_data_max_months: 24;
  sanitized_logs_max_days: 30;
}

export type PrivacyRetentionPolicy__file_types__ItemType = "json" | "pdf" | "utf8_csv";

export interface ProfileContextData {
  can_append: boolean;
  can_create: boolean;
  can_read: boolean;
  is_synthetic: boolean;
  reason: "allowed" | "processing_disabled";
  schema_version: "v2.t23";
}

export interface ProfileEnvelope_ProfileContextData_ {
  data: ProfileContextData;
  meta: ProfileMeta;
}

export interface ProfileEnvelope_ProfilePage_ {
  data: ProfilePage;
  meta: ProfileMeta;
}

export interface ProfileEnvelope_ProfileVersionData_ {
  data: ProfileVersionData;
  meta: ProfileMeta;
}

export interface ProfileEnvelope_ProfileWriteData_ {
  data: ProfileWriteData;
  meta: ProfileMeta;
}

export interface ProfileMeta {
  api_version: "v2";
  data_as_of: null;
  data_mode: "demo" | "verified";
  model_mode: "disabled" | "mock";
  profile_mode: "real" | "synthetic" | null;
  profile_version_id: null | string;
  release_id: null;
  request_id: string;
  ruleset_version: null;
}

export interface ProfilePage {
  items: ProfileRef[];
  next_cursor: null | string;
}

export interface ProfileRef {
  confirmed_at: string;
  expires_at: string;
  is_synthetic: boolean;
  profile_id: string;
  version: number;
  version_id: string;
}

export interface ProfileSnapshot {
  applicant_category: ScopeKey;
  assessments: GradeAssessments;
  course_system: ScopeKey;
  entry_year: number;
  exam_province: ScopeKey;
  pathway: ScopeKey;
  preferences: Preferences | null;
  residence_region: ScopeKey;
  study_level: "bachelor";
  subjects: string[];
  weekly_hours: null | string;
}

export interface ProfileVersionData {
  adaptation: AdaptationData;
  confirmed_at: string;
  expires_at: string;
  is_synthetic: boolean;
  profile: ProfileSnapshot;
  profile_id: string;
  profile_sha256: string;
  source: "student_declared";
  version: number;
  version_id: string;
}

export interface ProfileWriteData {
  replayed: boolean;
  version: ProfileVersionData;
}

export interface ProposalData {
  created_at: string;
  effective_draft: PlanDraft;
  estimate_overrides: EstimateOverride[];
  id: string;
  schedule: ScheduleDraft | null;
  schedule_configuration: ScheduleConfiguration | null;
  state_version: number;
}

export interface ProposeInput {
  expected_new_state_version: number;
  expected_old_state_version: number;
  new_plan_id: string;
  old_plan_id: string;
  student_confirmed: true;
}

export interface ProposeV2PlanRevisionQuery {

}

export type ProposeV2PlanRevisionRequestBody = ProposeInput;

export type ProposeV2PlanRevisionResponse200 = RevisionEnvelope_RevisionResult_;

export type ProposeV2PlanRevisionResponse401 = ErrorEnvelope;

export type ProposeV2PlanRevisionResponse403 = ErrorEnvelope;

export type ProposeV2PlanRevisionResponse404 = ErrorEnvelope;

export type ProposeV2PlanRevisionResponse405 = ErrorEnvelope;

export type ProposeV2PlanRevisionResponse409 = ErrorEnvelope;

export type ProposeV2PlanRevisionResponse422 = ErrorEnvelope;

export type ProposeV2PlanRevisionResponse429 = ErrorEnvelope;

export type ProposeV2PlanRevisionResponse500 = ErrorEnvelope;

export type ProposeV2PlanRevisionResponse503 = ErrorEnvelope;

export interface ReplacementData {
  accepted_at: string;
  completion_credit_transferred: false;
  new_plan_confirmed: false;
  new_plan_id: string;
  old_plan_id: string;
  relationship_id: string;
}

export interface ReplayRequest {
  confirmed: true;
}

export interface ReplayV2EligibilityEvaluationPath {
  assessment_id: string;
}

export interface ReplayV2EligibilityEvaluationQuery {

}

export type ReplayV2EligibilityEvaluationRequestBody = ReplayRequest;

export type ReplayV2EligibilityEvaluationResponse200 = AssessmentEnvelope_AssessmentData_;

export type ReplayV2EligibilityEvaluationResponse401 = ErrorEnvelope;

export type ReplayV2EligibilityEvaluationResponse403 = ErrorEnvelope;

export type ReplayV2EligibilityEvaluationResponse404 = ErrorEnvelope;

export type ReplayV2EligibilityEvaluationResponse405 = ErrorEnvelope;

export type ReplayV2EligibilityEvaluationResponse409 = ErrorEnvelope;

export type ReplayV2EligibilityEvaluationResponse422 = ErrorEnvelope;

export type ReplayV2EligibilityEvaluationResponse429 = ErrorEnvelope;

export type ReplayV2EligibilityEvaluationResponse500 = ErrorEnvelope;

export type ReplayV2EligibilityEvaluationResponse503 = ErrorEnvelope;

export interface RevisionContextData {
  can_decide: boolean;
  can_propose: boolean;
  can_read_history: boolean;
  is_synthetic: boolean;
  reason: "processing_disabled" | "ready";
  schema_version: "v2.t35";
}

export interface RevisionData {
  created_at: string;
  decision: RevisionDecisionData | null;
  diff: RevisionDiff;
  expires_at: string;
  is_synthetic: boolean;
  new: RevisionHistoryData;
  old: RevisionHistoryData;
  proposal_sha256: string;
  replacement: ReplacementData | null;
  revision_id: string;
  revision_version: number;
  schema_version: "v2.t35";
  status: "accepted" | "proposed" | "rejected";
}

export interface RevisionDecisionData {
  action: "accept" | "reject";
  decided_at: string;
  decision_id: string;
  revision_version: 2;
}

export interface RevisionDiff {
  business_changed: boolean;
  changed_fields: RevisionDiff__changed_fields__ItemType[];
  diff_sha256: string;
}

export type RevisionDiff__changed_fields__ItemType = "deadlines" | "dependencies" | "estimates" | "profile_version" | "schedule" | "source_business" | "source_references" | "targets" | "task_business";

export interface RevisionEnvelope_RevisionContextData_ {
  data: RevisionContextData;
  meta: ProfileMeta;
}

export interface RevisionEnvelope_RevisionData_ {
  data: RevisionData;
  meta: ProfileMeta;
}

export interface RevisionEnvelope_RevisionHistoryData_ {
  data: RevisionHistoryData;
  meta: ProfileMeta;
}

export interface RevisionEnvelope_RevisionResult_ {
  data: RevisionResult;
  meta: ProfileMeta;
}

export interface RevisionHistoryData {
  completion_refs: CompletionReference[];
  created_at: string;
  current_actions: false;
  deadlines: DeadlineReference[];
  expires_at: string;
  pin: PlanPin;
  schedule: HistoricalSchedule | null;
  schema_version: "v2.t35";
  sources: RevisionSourceRef[];
  tasks: DraftTask[];
}

export interface RevisionResult {
  replayed: boolean;
  revision: RevisionData;
}

export interface RevisionSourceRef {
  assessment_id: string;
  current_validity: "needs_review" | "replaced" | "unavailable" | "withdrawn";
  entry_year: number;
  original_eligibility_status: "conditional" | "eligible" | "ineligible" | "unknown";
  original_validity: "current" | "needs_review" | "replaced" | "unavailable" | "withdrawn";
  release_id: string;
  requirements_version: string;
  result_sha256: string;
  ruleset_version: null | string;
  stage: "application" | "enrollment";
  target: TargetReference;
}

export interface RevokeV2AccessGrantPath {
  grant_id: string;
}

export interface RevokeV2AccessGrantQuery {

}

export type RevokeV2AccessGrantResponse200 = Envelope_GrantMutationData_;

export type RevokeV2AccessGrantResponse401 = ErrorEnvelope;

export type RevokeV2AccessGrantResponse403 = ErrorEnvelope;

export type RevokeV2AccessGrantResponse404 = ErrorEnvelope;

export type RevokeV2AccessGrantResponse405 = ErrorEnvelope;

export type RevokeV2AccessGrantResponse409 = ErrorEnvelope;

export type RevokeV2AccessGrantResponse422 = ErrorEnvelope;

export type RevokeV2AccessGrantResponse429 = ErrorEnvelope;

export type RevokeV2AccessGrantResponse500 = ErrorEnvelope;

export type RevokeV2AccessGrantResponse503 = ErrorEnvelope;

export interface RuleReference {
  bundle_id: string;
  evidence_ids: string[];
  expression_sha256: string;
  fact_ids: string[];
}

export interface ScheduleAllocation {
  duration_microseconds: number;
  end_at: string;
  slot_id: string;
  start_at: string;
  task_key: string;
  week_start: string;
}

export interface ScheduleConfiguration {
  availability_confirmed: true;
  display_timezone: string;
  horizon_end: string;
  horizon_start: string;
  internal_goals: InternalGoal[];
  rest_excluded: true;
  slots: AvailabilitySlot[];
  weekly_hours: null | string;
}

export interface ScheduleConflict {
  code: "CAPACITY_EXCEEDED" | "CAPACITY_REQUIRED" | "DEADLINE_UNRESOLVED" | "DEPENDENCY_BLOCKED" | "ESTIMATE_REQUIRED" | "INTERNAL_GOAL_CONFLICT";
  deadline_key: null | string;
  task_key: null | string;
}

export interface ScheduleDraft {
  allocations: ScheduleAllocation[];
  assessment_refs: PlanAssessmentRef[];
  confirmed: false;
  conflicts: ScheduleConflict[];
  constraints_complete: false;
  deadline_refs: PlanDeadlineRef[];
  display_timezone: string;
  draft_sha256: string;
  generated_at: string;
  horizon_end: string;
  horizon_start: string;
  is_synthetic: boolean;
  options: ScheduleDraft__options__ItemType[];
  profile_id: string;
  profile_sha256: string;
  profile_version_id: string;
  schedule_sha256: string;
  scheduler_version: "T31_v1";
  schema_version: "T31_v1";
  status: "blocked" | "partial" | "ready";
  tasks: TaskSchedule[];
  weekly_hours: null | string;
  weeks: ScheduleWeek[];
}

export type ScheduleDraft__options__ItemType = "EDIT_AVAILABILITY" | "EDIT_ESTIMATES" | "EDIT_HORIZON" | "REDUCE_GOALS" | "VERIFY_DEADLINES";

export interface ScheduleWeek {
  assigned_microseconds: number;
  capacity_microseconds: null | number;
  week_start: string;
}

export interface ScopeKey {
  status: "known" | "not_applicable" | "unknown";
  value: null | string;
}

export interface SharingPolicyData {
  guardian_verification_available: false;
  is_synthetic: boolean;
  max_duration_seconds: 2592000;
  policy_version: string;
  private_business_available: false;
  readiness_reason: "disabled" | "synthetic_test_ready";
  scope_matrix: SharingScopeData[];
  sharing_available: boolean;
  text: string;
  text_sha256: string;
}

export interface SharingScopeData {
  actions: SharingScopeData__actions__ItemType[];
  fields: SharingScopeData__fields__ItemType[];
  resource_type: "attachment" | "export" | "job" | "plan" | "profile";
}

export type SharingScopeData__actions__ItemType = "list" | "read";

export type SharingScopeData__fields__ItemType = "status" | "version";

export interface StartV2LoginQuery {

}

export type StartV2LoginResponse302 = undefined;

export interface StartV2LoginResponse302Headers {
  Location: string;
  "Set-Cookie": string;
  "X-Request-ID": string;
}

export type StartV2LoginResponse401 = ErrorEnvelope;

export type StartV2LoginResponse403 = ErrorEnvelope;

export type StartV2LoginResponse404 = ErrorEnvelope;

export type StartV2LoginResponse405 = ErrorEnvelope;

export type StartV2LoginResponse409 = ErrorEnvelope;

export type StartV2LoginResponse422 = ErrorEnvelope;

export type StartV2LoginResponse429 = ErrorEnvelope;

export type StartV2LoginResponse500 = ErrorEnvelope;

export type StartV2LoginResponse503 = ErrorEnvelope;

export interface StudyGoalInput {
  estimated_hours: null | string;
  goal_key: string;
  goal_text: string;
}

export interface TargetReference {
  country: "CN" | "GB";
  dataset_id: string;
  institution_id: string;
  offering_id: string;
  offering_version: number;
  program_id: string;
  scope_sha256: string;
}

export interface TaskSchedule {
  action_code: "OBTAIN_ACHIEVED" | "PREPARE_MATERIALS" | "RECHECK_CONDITIONS" | "REVIEW_INELIGIBLE" | "SELF_DIRECTED_STUDY" | "VERIFY_HISTORY" | "VERIFY_UNKNOWN";
  assessment_ids: string[];
  assigned_microseconds: number;
  deadline_keys: string[];
  dependency_keys: string[];
  end_at: null | string;
  estimated_hours: null | string;
  estimated_microseconds: null | number;
  internal_goal: null | string;
  remaining_microseconds: null | number;
  start_at: null | string;
  status: "blocked" | "milestone" | "scheduled";
  task_key: string;
}

export interface TraceNode {
  children: number[];
  field: FieldRef | null;
  op: "all" | "any" | "date_before" | "eq" | "exists" | "gte" | "in" | "lte" | "not" | "valid_at";
  outcome: "false" | "true" | "unknown";
  reason: "CALENDAR_MISMATCH" | "CONFLICTED" | "MATCH" | "MISSING" | "NOT_APPLICABLE" | "NO_MATCH" | "PENDING" | "PRECISION_MISMATCH" | "PREDICTED_NOT_ACHIEVED" | "REFERENCE_MISSING" | "SCALE_MISMATCH" | "TYPE_MISMATCH" | "UNIT_MISMATCH" | "UNKNOWN_CHILD";
}

export interface UnknownDimension {
  reason: "DATA_UNAVAILABLE";
  status: "unknown";
}

export interface UpdateV2NotificationPreferencesQuery {

}

export type UpdateV2NotificationPreferencesRequestBody = PreferenceInput;

export type UpdateV2NotificationPreferencesResponse200 = NotificationEnvelope_NotificationPreferenceData_;

export type UpdateV2NotificationPreferencesResponse401 = ErrorEnvelope;

export type UpdateV2NotificationPreferencesResponse403 = ErrorEnvelope;

export type UpdateV2NotificationPreferencesResponse404 = ErrorEnvelope;

export type UpdateV2NotificationPreferencesResponse405 = ErrorEnvelope;

export type UpdateV2NotificationPreferencesResponse409 = ErrorEnvelope;

export type UpdateV2NotificationPreferencesResponse422 = ErrorEnvelope;

export type UpdateV2NotificationPreferencesResponse429 = ErrorEnvelope;

export type UpdateV2NotificationPreferencesResponse500 = ErrorEnvelope;

export type UpdateV2NotificationPreferencesResponse503 = ErrorEnvelope;

export interface UpdateV2PlanWorkspacePath {
  plan_id: string;
}

export interface UpdateV2PlanWorkspaceQuery {

}

export type UpdateV2PlanWorkspaceRequestBody = HttpWorkspaceInput;

export type UpdateV2PlanWorkspaceResponse200 = PlanEnvelope_ExecutionData_;

export type UpdateV2PlanWorkspaceResponse401 = ErrorEnvelope;

export type UpdateV2PlanWorkspaceResponse403 = ErrorEnvelope;

export type UpdateV2PlanWorkspaceResponse404 = ErrorEnvelope;

export type UpdateV2PlanWorkspaceResponse405 = ErrorEnvelope;

export type UpdateV2PlanWorkspaceResponse409 = ErrorEnvelope;

export type UpdateV2PlanWorkspaceResponse422 = ErrorEnvelope;

export type UpdateV2PlanWorkspaceResponse429 = ErrorEnvelope;

export type UpdateV2PlanWorkspaceResponse500 = ErrorEnvelope;

export type UpdateV2PlanWorkspaceResponse503 = ErrorEnvelope;

export interface WithdrawV2CoreConsentPath {
  consent_id: string;
}

export interface WithdrawV2CoreConsentQuery {

}

export type WithdrawV2CoreConsentResponse200 = Envelope_AdmissionData_;

export type WithdrawV2CoreConsentResponse401 = ErrorEnvelope;

export type WithdrawV2CoreConsentResponse403 = ErrorEnvelope;

export type WithdrawV2CoreConsentResponse404 = ErrorEnvelope;

export type WithdrawV2CoreConsentResponse405 = ErrorEnvelope;

export type WithdrawV2CoreConsentResponse409 = ErrorEnvelope;

export type WithdrawV2CoreConsentResponse422 = ErrorEnvelope;

export type WithdrawV2CoreConsentResponse429 = ErrorEnvelope;

export type WithdrawV2CoreConsentResponse500 = ErrorEnvelope;

export type WithdrawV2CoreConsentResponse503 = ErrorEnvelope;
