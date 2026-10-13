// Generated offline from create_admin_review_v2_app().openapi() by scripts/generate_contracts.py.
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

export interface AdminContextData {
  can_import: boolean;
  can_manage_sources: boolean;
  is_synthetic: boolean;
  schema_version: "v2.t21";
}

export interface AdminDocumentInput {
  confirmed: true;
  dataset_id: string;
  document_reference: string;
  language: "en" | "und" | "zh-Hans" | "zh-Hant";
  source_id: string;
  source_version: number;
}

export interface AdminFactInput {
  classification: Classification;
  confirmed: true;
  evidence_id: null | string;
  import_id: string;
  import_row_id: string;
}

export interface AdminImportInput {
  confirmed: true;
  dataset_id: string;
  file_id: string;
  file_sha256: string;
  format: "csv" | "json";
  source_id: string;
  source_version: number;
}

export interface AdminPublishInput {
  confirmed: true;
  dataset_id: string;
  entry_year: number;
  expected_dataset_revision: number;
  expected_replaced_state_revision: null | number;
  kind: "formal" | "test_fixture";
  members: PublishMember[];
  replaces_release_id: null | string;
  valid_from: string;
  valid_until: string;
}

export interface AdminReviewInput {
  action: "approve" | "return";
  checks: ReviewCheck[];
  confirmed: true;
  conflict_resolutions: ConflictResolution[];
  expected_case_revision: number;
  expected_fact_version: 1;
  fact_id: string;
  return_reason: "CONFLICT_UNRESOLVED" | "FOOTNOTE_UNRESOLVED" | "INVALID_VALUE" | "MISSING_CONTEXT" | "MISSING_EVIDENCE" | "PERIOD_UNCLEAR" | "SCOPE_MISMATCH" | "SOURCE_UNAVAILABLE" | "UNIT_MISMATCH" | "UNSUPPORTED_LITERAL" | null;
}

export interface AdminSnippetInput {
  byte_end: number;
  byte_start: number;
  confirmed: true;
  document_id: string;
  document_version: number;
  entry_year: number;
  offering_id: string;
  offering_version: number;
}

export interface AdminSourceData {
  authority_claim: "claimed_official" | "not_official" | "unclassified";
  auto_fetch_enabled: false;
  automated_fetch_permission: "denied" | "granted" | "pending";
  created_at: string;
  data_type: "admission_observations" | "application_dates" | "curriculum" | "entry_requirements" | "institution_directory" | "outcomes" | "regional_cutoffs";
  dataset_id: string;
  dataset_revision: number;
  entry_url: string;
  id: string;
  is_synthetic: boolean;
  license_basis: null | string;
  manual_import_enabled: boolean;
  manual_import_permission: "denied" | "granted" | "pending";
  permission_record_reference: null | string;
  permission_reviewed_at: null | string;
  publication_permission: "denied" | "granted" | "pending";
  publisher: string;
  purpose: "admissions_reference";
  recheck_days: number;
  recheck_due_at: string;
  scope_note: string;
  source_id: string;
  version: number;
}

export interface AdminSourceFileInput {
  confirmed: true;
  content_type: "application/json" | "text/csv";
  content_utf8: string;
  filename: string;
  source_id: string;
  source_version: number;
}

export interface AdminSourceRegisterInput {
  confirmed: true;
  expected_dataset_revision: number;
  source: SourceCreateInput;
}

export interface AdminSourceRevisionInput {
  confirmed: true;
  definition: SourceDefinition;
  expected_dataset_revision: number;
  expected_source_version: number;
}

export interface AdminVersionInput {
  confirmed: true;
  document_id: string;
  expected_current_version: number;
  file_id: string;
  file_sha256: string;
}

export interface AdminWithdrawalInput {
  confirmed: true;
  expected_state_revision: number;
  reason_code: "ADMIN_REQUEST" | "INCORRECT_FACT" | "RIGHTS_REVOKED" | "SOURCE_UNAVAILABLE";
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

export interface Classification {
  claim_kind: "historical_statistic" | "information" | "minimum_requirement" | "typical_offer" | "unknown";
  cohort_year: null | number;
  date_event_id: null | string;
  period: "academic_year" | "not_applicable" | "one_time" | "program" | "survey_period" | "unknown";
  statistic_denominator: null | string;
  statistic_population: null | string;
  statistics_basis: "admission" | "employment" | "not_applicable" | "other" | "unknown";
  survey_period: null | string;
  unit_code: "CNY" | "GBP" | "ISO_DATE" | "fraction" | "item" | "people" | "percent" | "points" | "text" | "unknown";
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

export interface ConflictResolution {
  fact_id: string;
  reason_code: "DUPLICATE_OR_EQUIVALENT" | "INCORRECT_VALUE" | "SELECTED_SUPPORTED" | "WRONG_CONTEXT";
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

export interface CreateV2AdminImportHeaders {
  "Idempotency-Key": string;
}

export interface CreateV2AdminImportQuery {

}

export type CreateV2AdminImportRequestBody = AdminImportInput;

export type CreateV2AdminImportResponse200 = Envelope_ImportResult_;

export type CreateV2AdminImportResponse401 = ErrorEnvelope;

export type CreateV2AdminImportResponse403 = ErrorEnvelope;

export type CreateV2AdminImportResponse404 = ErrorEnvelope;

export type CreateV2AdminImportResponse405 = ErrorEnvelope;

export type CreateV2AdminImportResponse409 = ErrorEnvelope;

export type CreateV2AdminImportResponse422 = ErrorEnvelope;

export type CreateV2AdminImportResponse429 = ErrorEnvelope;

export type CreateV2AdminImportResponse500 = ErrorEnvelope;

export type CreateV2AdminImportResponse503 = ErrorEnvelope;

export interface CreateV2EvidenceDocumentQuery {

}

export type CreateV2EvidenceDocumentRequestBody = AdminDocumentInput;

export type CreateV2EvidenceDocumentResponse200 = Envelope_DocumentData_;

export type CreateV2EvidenceDocumentResponse401 = ErrorEnvelope;

export type CreateV2EvidenceDocumentResponse403 = ErrorEnvelope;

export type CreateV2EvidenceDocumentResponse404 = ErrorEnvelope;

export type CreateV2EvidenceDocumentResponse405 = ErrorEnvelope;

export type CreateV2EvidenceDocumentResponse409 = ErrorEnvelope;

export type CreateV2EvidenceDocumentResponse422 = ErrorEnvelope;

export type CreateV2EvidenceDocumentResponse429 = ErrorEnvelope;

export type CreateV2EvidenceDocumentResponse500 = ErrorEnvelope;

export type CreateV2EvidenceDocumentResponse503 = ErrorEnvelope;

export interface CreateV2EvidenceSnippetQuery {

}

export type CreateV2EvidenceSnippetRequestBody = AdminSnippetInput;

export type CreateV2EvidenceSnippetResponse200 = Envelope_SnippetData_;

export type CreateV2EvidenceSnippetResponse401 = ErrorEnvelope;

export type CreateV2EvidenceSnippetResponse403 = ErrorEnvelope;

export type CreateV2EvidenceSnippetResponse404 = ErrorEnvelope;

export type CreateV2EvidenceSnippetResponse405 = ErrorEnvelope;

export type CreateV2EvidenceSnippetResponse409 = ErrorEnvelope;

export type CreateV2EvidenceSnippetResponse422 = ErrorEnvelope;

export type CreateV2EvidenceSnippetResponse429 = ErrorEnvelope;

export type CreateV2EvidenceSnippetResponse500 = ErrorEnvelope;

export type CreateV2EvidenceSnippetResponse503 = ErrorEnvelope;

export interface CreateV2EvidenceVersionQuery {

}

export type CreateV2EvidenceVersionRequestBody = AdminVersionInput;

export type CreateV2EvidenceVersionResponse200 = Envelope_VersionData_;

export type CreateV2EvidenceVersionResponse401 = ErrorEnvelope;

export type CreateV2EvidenceVersionResponse403 = ErrorEnvelope;

export type CreateV2EvidenceVersionResponse404 = ErrorEnvelope;

export type CreateV2EvidenceVersionResponse405 = ErrorEnvelope;

export type CreateV2EvidenceVersionResponse409 = ErrorEnvelope;

export type CreateV2EvidenceVersionResponse422 = ErrorEnvelope;

export type CreateV2EvidenceVersionResponse429 = ErrorEnvelope;

export type CreateV2EvidenceVersionResponse500 = ErrorEnvelope;

export type CreateV2EvidenceVersionResponse503 = ErrorEnvelope;

export interface CreateV2ReviewDecisionQuery {

}

export type CreateV2ReviewDecisionRequestBody = AdminReviewInput;

export type CreateV2ReviewDecisionResponse200 = Envelope_ReviewDecisionData_;

export type CreateV2ReviewDecisionResponse401 = ErrorEnvelope;

export type CreateV2ReviewDecisionResponse403 = ErrorEnvelope;

export type CreateV2ReviewDecisionResponse404 = ErrorEnvelope;

export type CreateV2ReviewDecisionResponse405 = ErrorEnvelope;

export type CreateV2ReviewDecisionResponse409 = ErrorEnvelope;

export type CreateV2ReviewDecisionResponse422 = ErrorEnvelope;

export type CreateV2ReviewDecisionResponse429 = ErrorEnvelope;

export type CreateV2ReviewDecisionResponse500 = ErrorEnvelope;

export type CreateV2ReviewDecisionResponse503 = ErrorEnvelope;

export interface CreateV2TypedFactQuery {

}

export type CreateV2TypedFactRequestBody = AdminFactInput;

export type CreateV2TypedFactResponse200 = Envelope_TypedCandidate_;

export type CreateV2TypedFactResponse401 = ErrorEnvelope;

export type CreateV2TypedFactResponse403 = ErrorEnvelope;

export type CreateV2TypedFactResponse404 = ErrorEnvelope;

export type CreateV2TypedFactResponse405 = ErrorEnvelope;

export type CreateV2TypedFactResponse409 = ErrorEnvelope;

export type CreateV2TypedFactResponse422 = ErrorEnvelope;

export type CreateV2TypedFactResponse429 = ErrorEnvelope;

export type CreateV2TypedFactResponse500 = ErrorEnvelope;

export type CreateV2TypedFactResponse503 = ErrorEnvelope;

export interface CurrentReleaseData {
  dataset_id: string;
  dataset_revision: number;
  entry_year: number;
  release: ReleaseHeadData | null;
}

export interface DateResolutionSnapshot {
  calculated_utc_instant: null | string;
  conversion_status: "ambiguous" | "date_only" | "missing_timezone" | "nonexistent" | "out_of_range" | "source_conflict" | "unique" | "unknown";
  dataset_id: string;
  date_event_id: string;
  entry_year: number;
  event_type: "application_deadline" | "application_open" | "enrollment" | "equal_consideration" | "language_supplement" | "materials_deadline" | "offer_acceptance" | "scholarship_deadline" | "score_supplement";
  evidence_reference: null | string;
  is_synthetic: boolean;
  local_date: null | string;
  local_time: null | string;
  offering_id: string;
  offering_version: number;
  original_text: string;
  precision: "date" | "minute" | "second" | "unknown";
  reference_key: string;
  source_alignment: "conflict" | "pending";
  timezone: null | string;
  tzdata_version: "2026.4";
  utc_instant: null;
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

export interface DocumentData {
  created_at: string;
  current_version: number;
  dataset_id: string;
  document_reference: string;
  id: string;
  is_synthetic: boolean;
  language: "en" | "und" | "zh-Hans" | "zh-Hant";
  source_id: string;
  source_version: number;
}

export interface Envelope_AdminContextData_ {
  data: AdminContextData;
  meta: Meta;
}

export interface Envelope_AdminSourceData_ {
  data: AdminSourceData;
  meta: Meta;
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

export interface Envelope_CurrentReleaseData_ {
  data: CurrentReleaseData;
  meta: Meta;
}

export interface Envelope_DocumentData_ {
  data: DocumentData;
  meta: Meta;
}

export interface Envelope_FileData_ {
  data: FileData;
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

export interface Envelope_ImportResult_ {
  data: ImportResult;
  meta: Meta;
}

export interface Envelope_ImportRowsData_ {
  data: ImportRowsData;
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

export interface Envelope_PublishPrecheckData_ {
  data: PublishPrecheckData;
  meta: Meta;
}

export interface Envelope_ReleaseData_ {
  data: ReleaseData;
  meta: Meta;
}

export interface Envelope_ReviewCandidatesData_ {
  data: ReviewCandidatesData;
  meta: Meta;
}

export interface Envelope_ReviewContextData_ {
  data: ReviewContextData;
  meta: Meta;
}

export interface Envelope_ReviewDecisionData_ {
  data: ReviewDecisionData;
  meta: Meta;
}

export interface Envelope_ReviewDetailData_ {
  data: ReviewDetailData;
  meta: Meta;
}

export interface Envelope_SharingPolicyData_ {
  data: SharingPolicyData;
  meta: Meta;
}

export interface Envelope_SnippetData_ {
  data: SnippetData;
  meta: Meta;
}

export interface Envelope_TypedCandidate_ {
  data: TypedCandidate;
  meta: Meta;
}

export interface Envelope_VersionData_ {
  data: VersionData;
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

export interface EvidenceLocator {
  byte_end: number;
  byte_start: number;
  line_end: number;
  line_start: number;
  location_kind: "utf8_byte_lines";
  page: null;
  section: null;
}

export interface EvidenceScope {
  applicant_category: ScopeKey;
  application_cycle: ScopeKey;
  batch_group: ScopeKey;
  campus: ScopeKey;
  channel: ScopeKey;
  country: string;
  course: ScopeKey;
  course_system: ScopeKey;
  dataset_id: string;
  degree: ScopeKey;
  entry_year: number;
  exam_system: ScopeKey;
  institution_id: string;
  intake: ScopeKey;
  pathway: ScopeKey;
  program_id: string;
  progression_pathway: ScopeKey;
  province: ScopeKey;
  study_level: "undergraduate";
  subject_scope: ScopeKey;
  teaching_language: ScopeKey;
}

export interface FileData {
  created_at: string;
  expires_at: string;
  id: string;
  is_synthetic: boolean;
  media_type: "application/json" | "application/pdf" | "text/csv";
  namespace: StorageNamespace;
  sha256: string;
  size_bytes: number;
  status: "delete_pending" | "deleted" | "quarantined";
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

export interface GetV2AdminContextQuery {

}

export type GetV2AdminContextResponse200 = Envelope_AdminContextData_;

export type GetV2AdminContextResponse401 = ErrorEnvelope;

export type GetV2AdminContextResponse403 = ErrorEnvelope;

export type GetV2AdminContextResponse404 = ErrorEnvelope;

export type GetV2AdminContextResponse405 = ErrorEnvelope;

export type GetV2AdminContextResponse409 = ErrorEnvelope;

export type GetV2AdminContextResponse422 = ErrorEnvelope;

export type GetV2AdminContextResponse429 = ErrorEnvelope;

export type GetV2AdminContextResponse500 = ErrorEnvelope;

export type GetV2AdminContextResponse503 = ErrorEnvelope;

export interface GetV2AdminImportPath {
  import_id: string;
}

export interface GetV2AdminImportQuery {

}

export type GetV2AdminImportResponse200 = Envelope_ImportResult_;

export type GetV2AdminImportResponse401 = ErrorEnvelope;

export type GetV2AdminImportResponse403 = ErrorEnvelope;

export type GetV2AdminImportResponse404 = ErrorEnvelope;

export type GetV2AdminImportResponse405 = ErrorEnvelope;

export type GetV2AdminImportResponse409 = ErrorEnvelope;

export type GetV2AdminImportResponse422 = ErrorEnvelope;

export type GetV2AdminImportResponse429 = ErrorEnvelope;

export type GetV2AdminImportResponse500 = ErrorEnvelope;

export type GetV2AdminImportResponse503 = ErrorEnvelope;

export interface GetV2AdminImportRowsPath {
  import_id: string;
}

export interface GetV2AdminImportRowsQuery {
  cursor?: string;
  limit?: number;
}

export type GetV2AdminImportRowsResponse200 = Envelope_ImportRowsData_;

export type GetV2AdminImportRowsResponse401 = ErrorEnvelope;

export type GetV2AdminImportRowsResponse403 = ErrorEnvelope;

export type GetV2AdminImportRowsResponse404 = ErrorEnvelope;

export type GetV2AdminImportRowsResponse405 = ErrorEnvelope;

export type GetV2AdminImportRowsResponse409 = ErrorEnvelope;

export type GetV2AdminImportRowsResponse422 = ErrorEnvelope;

export type GetV2AdminImportRowsResponse429 = ErrorEnvelope;

export type GetV2AdminImportRowsResponse500 = ErrorEnvelope;

export type GetV2AdminImportRowsResponse503 = ErrorEnvelope;

export interface GetV2AdminReleasePath {
  release_id: string;
}

export interface GetV2AdminReleaseQuery {

}

export type GetV2AdminReleaseResponse200 = Envelope_ReleaseData_;

export type GetV2AdminReleaseResponse401 = ErrorEnvelope;

export type GetV2AdminReleaseResponse403 = ErrorEnvelope;

export type GetV2AdminReleaseResponse404 = ErrorEnvelope;

export type GetV2AdminReleaseResponse405 = ErrorEnvelope;

export type GetV2AdminReleaseResponse409 = ErrorEnvelope;

export type GetV2AdminReleaseResponse422 = ErrorEnvelope;

export type GetV2AdminReleaseResponse429 = ErrorEnvelope;

export type GetV2AdminReleaseResponse500 = ErrorEnvelope;

export type GetV2AdminReleaseResponse503 = ErrorEnvelope;

export interface GetV2AdminSourcePath {
  source_id: string;
}

export interface GetV2AdminSourceQuery {
  version?: number;
}

export type GetV2AdminSourceResponse200 = Envelope_AdminSourceData_;

export type GetV2AdminSourceResponse401 = ErrorEnvelope;

export type GetV2AdminSourceResponse403 = ErrorEnvelope;

export type GetV2AdminSourceResponse404 = ErrorEnvelope;

export type GetV2AdminSourceResponse405 = ErrorEnvelope;

export type GetV2AdminSourceResponse409 = ErrorEnvelope;

export type GetV2AdminSourceResponse422 = ErrorEnvelope;

export type GetV2AdminSourceResponse429 = ErrorEnvelope;

export type GetV2AdminSourceResponse500 = ErrorEnvelope;

export type GetV2AdminSourceResponse503 = ErrorEnvelope;

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

export interface GetV2CurrentReleaseQuery {
  dataset_id: string;
  entry_year: number;
}

export type GetV2CurrentReleaseResponse200 = Envelope_CurrentReleaseData_;

export type GetV2CurrentReleaseResponse401 = ErrorEnvelope;

export type GetV2CurrentReleaseResponse403 = ErrorEnvelope;

export type GetV2CurrentReleaseResponse404 = ErrorEnvelope;

export type GetV2CurrentReleaseResponse405 = ErrorEnvelope;

export type GetV2CurrentReleaseResponse409 = ErrorEnvelope;

export type GetV2CurrentReleaseResponse422 = ErrorEnvelope;

export type GetV2CurrentReleaseResponse429 = ErrorEnvelope;

export type GetV2CurrentReleaseResponse500 = ErrorEnvelope;

export type GetV2CurrentReleaseResponse503 = ErrorEnvelope;

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

export interface GetV2ReviewContextQuery {

}

export type GetV2ReviewContextResponse200 = Envelope_ReviewContextData_;

export type GetV2ReviewContextResponse401 = ErrorEnvelope;

export type GetV2ReviewContextResponse403 = ErrorEnvelope;

export type GetV2ReviewContextResponse404 = ErrorEnvelope;

export type GetV2ReviewContextResponse405 = ErrorEnvelope;

export type GetV2ReviewContextResponse409 = ErrorEnvelope;

export type GetV2ReviewContextResponse422 = ErrorEnvelope;

export type GetV2ReviewContextResponse429 = ErrorEnvelope;

export type GetV2ReviewContextResponse500 = ErrorEnvelope;

export type GetV2ReviewContextResponse503 = ErrorEnvelope;

export interface GetV2ReviewDetailPath {
  fact_id: string;
}

export interface GetV2ReviewDetailQuery {

}

export type GetV2ReviewDetailResponse200 = Envelope_ReviewDetailData_;

export type GetV2ReviewDetailResponse401 = ErrorEnvelope;

export type GetV2ReviewDetailResponse403 = ErrorEnvelope;

export type GetV2ReviewDetailResponse404 = ErrorEnvelope;

export type GetV2ReviewDetailResponse405 = ErrorEnvelope;

export type GetV2ReviewDetailResponse409 = ErrorEnvelope;

export type GetV2ReviewDetailResponse422 = ErrorEnvelope;

export type GetV2ReviewDetailResponse429 = ErrorEnvelope;

export type GetV2ReviewDetailResponse500 = ErrorEnvelope;

export type GetV2ReviewDetailResponse503 = ErrorEnvelope;

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

export interface ImportResult {
  error_count: number;
  errors: RowError[];
  id: string;
  replayed: boolean;
  staged_rows: number;
  status: "rejected" | "staged";
  total_rows: null | number;
}

export interface ImportRowData {
  row: ParsedRow;
  row_id: string;
}

export interface ImportRowsData {
  dataset_id: string;
  file_id: string;
  file_sha256: string;
  format: "csv" | "json";
  import_id: string;
  is_synthetic: boolean;
  next_cursor: null | string;
  rows: ImportRowData[];
  source_id: string;
  source_version: number;
  total_rows: number;
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

export interface ListV2ReviewCandidatesQuery {
  cursor?: string;
  dataset_id: string;
  entry_year: number;
  limit?: number;
}

export type ListV2ReviewCandidatesResponse200 = Envelope_ReviewCandidatesData_;

export type ListV2ReviewCandidatesResponse401 = ErrorEnvelope;

export type ListV2ReviewCandidatesResponse403 = ErrorEnvelope;

export type ListV2ReviewCandidatesResponse404 = ErrorEnvelope;

export type ListV2ReviewCandidatesResponse405 = ErrorEnvelope;

export type ListV2ReviewCandidatesResponse409 = ErrorEnvelope;

export type ListV2ReviewCandidatesResponse422 = ErrorEnvelope;

export type ListV2ReviewCandidatesResponse429 = ErrorEnvelope;

export type ListV2ReviewCandidatesResponse500 = ErrorEnvelope;

export type ListV2ReviewCandidatesResponse503 = ErrorEnvelope;

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

export interface ParsedRow {
  entry_year: number;
  fact_type: "date" | "fee" | "material" | "requirement" | "score" | "statistic";
  field_key: string;
  footnote_state: "none" | "present" | "unknown";
  footnote_text: null | string;
  locator: null | string;
  missing_reason: "ambiguous" | "not_applicable" | "not_provided" | "not_published" | "unavailable" | null;
  offering_id: string;
  offering_version: number;
  row_number: number;
  source_record_reference: string;
  unit: null | string;
  value_kind: "decimal" | "text";
  value_text: null | string;
}

export interface PrecheckV2ReleaseQuery {

}

export type PrecheckV2ReleaseRequestBody = AdminPublishInput;

export type PrecheckV2ReleaseResponse200 = Envelope_PublishPrecheckData_;

export type PrecheckV2ReleaseResponse401 = ErrorEnvelope;

export type PrecheckV2ReleaseResponse403 = ErrorEnvelope;

export type PrecheckV2ReleaseResponse404 = ErrorEnvelope;

export type PrecheckV2ReleaseResponse405 = ErrorEnvelope;

export type PrecheckV2ReleaseResponse409 = ErrorEnvelope;

export type PrecheckV2ReleaseResponse422 = ErrorEnvelope;

export type PrecheckV2ReleaseResponse429 = ErrorEnvelope;

export type PrecheckV2ReleaseResponse500 = ErrorEnvelope;

export type PrecheckV2ReleaseResponse503 = ErrorEnvelope;

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

export interface PublishMember {
  expected_case_revision: number;
  expected_decision_id: string;
  fact_id: string;
  public_evidence: boolean;
}

export interface PublishPrecheckData {
  checked_at: string;
  dataset_revision: number;
  is_synthetic: boolean;
  member_count: number;
  request_sha256: string;
  status: "precheck_passed";
}

export interface PublishV2AdminReleaseHeaders {
  "Idempotency-Key": string;
}

export interface PublishV2AdminReleaseQuery {

}

export type PublishV2AdminReleaseRequestBody = AdminPublishInput;

export type PublishV2AdminReleaseResponse200 = Envelope_ReleaseData_;

export type PublishV2AdminReleaseResponse401 = ErrorEnvelope;

export type PublishV2AdminReleaseResponse403 = ErrorEnvelope;

export type PublishV2AdminReleaseResponse404 = ErrorEnvelope;

export type PublishV2AdminReleaseResponse405 = ErrorEnvelope;

export type PublishV2AdminReleaseResponse409 = ErrorEnvelope;

export type PublishV2AdminReleaseResponse422 = ErrorEnvelope;

export type PublishV2AdminReleaseResponse429 = ErrorEnvelope;

export type PublishV2AdminReleaseResponse500 = ErrorEnvelope;

export type PublishV2AdminReleaseResponse503 = ErrorEnvelope;

export interface RegisterV2AdminSourceQuery {

}

export type RegisterV2AdminSourceRequestBody = AdminSourceRegisterInput;

export type RegisterV2AdminSourceResponse200 = Envelope_AdminSourceData_;

export type RegisterV2AdminSourceResponse401 = ErrorEnvelope;

export type RegisterV2AdminSourceResponse403 = ErrorEnvelope;

export type RegisterV2AdminSourceResponse404 = ErrorEnvelope;

export type RegisterV2AdminSourceResponse405 = ErrorEnvelope;

export type RegisterV2AdminSourceResponse409 = ErrorEnvelope;

export type RegisterV2AdminSourceResponse422 = ErrorEnvelope;

export type RegisterV2AdminSourceResponse429 = ErrorEnvelope;

export type RegisterV2AdminSourceResponse500 = ErrorEnvelope;

export type RegisterV2AdminSourceResponse503 = ErrorEnvelope;

export interface ReleaseData {
  content_sha256: string;
  dataset_id: string;
  entry_year: number;
  is_synthetic: boolean;
  kind: "formal" | "test_fixture";
  members: ReleaseMemberData[];
  published_at: string;
  publisher_user_id: string;
  release_id: string;
  replaced_by_release_id: null | string;
  replaces_release_id: null | string;
  replayed: boolean;
  requirements_version: string;
  ruleset_version: null;
  state: "published" | "replaced" | "withdrawn";
  state_revision: number;
  valid_from: string;
  valid_until: string;
  version: 1;
}

export interface ReleaseHeadData {
  content_sha256: string;
  is_synthetic: boolean;
  kind: "formal" | "test_fixture";
  member_count: number;
  release_id: string;
  replaced_by_release_id: null | string;
  replaces_release_id: null | string;
  requirements_version: string;
  state: "published" | "replaced" | "withdrawn";
  state_revision: number;
  valid_from: string;
  valid_until: string;
  version: 1;
}

export interface ReleaseMemberData {
  case_revision: number;
  decision_id: string;
  entry_year: number;
  evidence_id: string;
  evidence_sha256: string;
  fact_id: string;
  fact_sha256: string;
  file_sha256: string;
  logical_key_hash: string;
  offering_id: string;
  offering_version: number;
  public_evidence: boolean;
  scope_sha256: string;
  source_id: string;
  source_sha256: string;
  source_version: number;
}

export interface ReviewCandidateRef {
  created_at: string;
  dataset_id: string;
  entry_year: number;
  fact_id: string;
  is_synthetic: boolean;
  offering_id: string;
  offering_version: number;
  state: "conflicted" | "draft" | "review_required";
  version: 1;
}

export interface ReviewCandidatesData {
  dataset_id: string;
  dataset_revision: number;
  entry_year: number;
  items: ReviewCandidateRef[];
  next_cursor: null | string;
}

export interface ReviewCaseData {
  case_id: null | string;
  case_revision: number;
  chosen_fact_id: null | string;
  current_approved: boolean;
  current_decision_id: null | string;
  is_synthetic: boolean;
  logical_key_hash: string;
}

export interface ReviewCheck {
  field: "claim_kind" | "date_context" | "evidence_location" | "footnote" | "missingness" | "original_value" | "period" | "scope" | "statistics_context" | "unit";
  status: "accepted" | "not_applicable" | "rejected";
}

export interface ReviewConflictData {
  classification: Classification;
  evidence_id: null | string;
  fact_id: string;
  footnote_state: "none" | "present" | "unknown";
  footnote_text: null | string;
  normalized_value: null | string;
  state: "conflicted" | "draft" | "review_required";
  unit_text: null | string;
  value_kind: "decimal" | "text";
  value_text: null | string;
  version: 1;
}

export interface ReviewContextData {
  can_prepare: boolean;
  can_publish: boolean;
  can_review: boolean;
  can_withdraw: boolean;
  is_synthetic: boolean;
  schema_version: "v2.t22";
}

export interface ReviewDecisionData {
  action: "approve" | "return";
  case_id: string;
  case_revision: number;
  checks: ReviewCheck[];
  conflict_resolutions: ConflictResolution[];
  created_at: string;
  current_approved: boolean;
  decision_id: string;
  fact_id: string;
  is_synthetic: boolean;
  return_reason: "CONFLICT_UNRESOLVED" | "FOOTNOTE_UNRESOLVED" | "INVALID_VALUE" | "MISSING_CONTEXT" | "MISSING_EVIDENCE" | "PERIOD_UNCLEAR" | "SCOPE_MISMATCH" | "SOURCE_UNAVAILABLE" | "UNIT_MISMATCH" | "UNSUPPORTED_LITERAL" | null;
  reviewer_user_id: string;
}

export interface ReviewDetailData {
  case: ReviewCaseData;
  conflicts: ReviewConflictData[];
  evidence: SnippetData | null;
  fact: TypedCandidate;
  gaps: ReviewDetailData__gaps__ItemType[];
  scope: EvidenceScope;
}

export type ReviewDetailData__gaps__ItemType = "BASE_DRAFT" | "CURRENT_CONFLICTS" | "INCOMPLETE_SCOPE" | "INCOMPLETE_STATISTICS" | "MISSING_EVIDENCE" | "MISSING_VALUE" | "SELF_REVIEW_FORBIDDEN" | "UNKNOWN_FOOTNOTE" | "UNRESOLVED_DATE" | "UNRESOLVED_LOCATOR";

export interface ReviseV2AdminSourcePath {
  source_id: string;
}

export interface ReviseV2AdminSourceQuery {

}

export type ReviseV2AdminSourceRequestBody = AdminSourceRevisionInput;

export type ReviseV2AdminSourceResponse200 = Envelope_AdminSourceData_;

export type ReviseV2AdminSourceResponse401 = ErrorEnvelope;

export type ReviseV2AdminSourceResponse403 = ErrorEnvelope;

export type ReviseV2AdminSourceResponse404 = ErrorEnvelope;

export type ReviseV2AdminSourceResponse405 = ErrorEnvelope;

export type ReviseV2AdminSourceResponse409 = ErrorEnvelope;

export type ReviseV2AdminSourceResponse422 = ErrorEnvelope;

export type ReviseV2AdminSourceResponse429 = ErrorEnvelope;

export type ReviseV2AdminSourceResponse500 = ErrorEnvelope;

export type ReviseV2AdminSourceResponse503 = ErrorEnvelope;

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

export interface RowError {
  code: "DUPLICATE_KEY" | "EMPTY_IMPORT" | "FIELD_TOO_LARGE" | "INPUT_TOO_LARGE" | "INVALID_DECIMAL" | "INVALID_ENCODING" | "INVALID_FIELD" | "INVALID_FOOTNOTE" | "INVALID_HEADER" | "INVALID_INTEGER" | "INVALID_STRUCTURE" | "INVALID_UUID" | "MISSING_FIELD" | "MISSING_VALUE_REASON" | "NAMESPACE_MISMATCH" | "SCOPE_MISMATCH" | "TOO_MANY_ROWS" | "UNEXPECTED_FIELD";
  field: "document" | "entry_year" | "fact_type" | "field_key" | "footnote_state" | "footnote_text" | "locator" | "missing_reason" | "offering_id" | "offering_version" | "source_record_reference" | "unit" | "value_kind" | "value_text";
  row_number: number;
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

export interface SnippetData {
  created_at: string;
  document_id: string;
  document_sha256: string;
  document_version: number;
  entry_year: number;
  id: string;
  is_synthetic: boolean;
  language: "en" | "und" | "zh-Hans" | "zh-Hant";
  locator: EvidenceLocator;
  offering_id: string;
  offering_version: number;
  scope: EvidenceScope;
  snippet_sha256: string;
  text: string;
}

export interface SourceCreateInput {
  dataset_id: string;
  definition: SourceDefinition;
  id: string;
  is_synthetic: boolean;
  reference_key: string;
}

export interface SourceDefinition {
  authority_claim: "claimed_official" | "not_official" | "unclassified";
  automated_fetch_permission: "denied" | "granted" | "pending";
  data_type: "admission_observations" | "application_dates" | "curriculum" | "entry_requirements" | "institution_directory" | "outcomes" | "regional_cutoffs";
  entry_url: string;
  license_basis: null | string;
  manual_import_enabled: boolean;
  manual_import_permission: "denied" | "granted" | "pending";
  permission_record_reference: null | string;
  publication_permission: "denied" | "granted" | "pending";
  publisher: string;
  purpose: "admissions_reference";
  recheck_days: number;
  scope_note: string;
}

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

export type StorageNamespace = "source_quarantine" | "student_private";

export interface TypedCandidate {
  classification: Classification;
  conflicting_ids: string[];
  created_at: string;
  dataset_id: string;
  date_resolution: DateResolutionSnapshot | null;
  entry_year: number;
  evidence_id: null | string;
  fact_type: "date" | "fee" | "material" | "requirement" | "score" | "statistic";
  field_key: string;
  footnote_state: "none" | "present" | "unknown";
  footnote_text: null | string;
  hard_rule: false;
  id: string;
  import_id: string;
  import_row_id: string;
  is_synthetic: boolean;
  locator: null | string;
  missing_reason: "ambiguous" | "not_applicable" | "not_provided" | "not_published" | "unavailable" | null;
  normalized_value: null | string;
  offering_id: string;
  offering_version: number;
  publication_eligible: false;
  row_number: number;
  source_record_reference: string;
  state: "conflicted" | "draft" | "review_required";
  unit: null | string;
  value_kind: "decimal" | "text";
  value_text: null | string;
  version: 1;
}

export interface UploadV2AdminSourceFileQuery {

}

export type UploadV2AdminSourceFileRequestBody = AdminSourceFileInput;

export type UploadV2AdminSourceFileResponse200 = Envelope_FileData_;

export type UploadV2AdminSourceFileResponse401 = ErrorEnvelope;

export type UploadV2AdminSourceFileResponse403 = ErrorEnvelope;

export type UploadV2AdminSourceFileResponse404 = ErrorEnvelope;

export type UploadV2AdminSourceFileResponse405 = ErrorEnvelope;

export type UploadV2AdminSourceFileResponse409 = ErrorEnvelope;

export type UploadV2AdminSourceFileResponse422 = ErrorEnvelope;

export type UploadV2AdminSourceFileResponse429 = ErrorEnvelope;

export type UploadV2AdminSourceFileResponse500 = ErrorEnvelope;

export type UploadV2AdminSourceFileResponse503 = ErrorEnvelope;

export interface VersionData {
  created_at: string;
  document_id: string;
  document_sha256: string;
  id: string;
  is_synthetic: boolean;
  media_type: "application/json" | "text/csv";
  size_bytes: number;
  version: number;
}

export interface WithdrawV2AdminReleasePath {
  release_id: string;
}

export interface WithdrawV2AdminReleaseQuery {

}

export type WithdrawV2AdminReleaseRequestBody = AdminWithdrawalInput;

export type WithdrawV2AdminReleaseResponse200 = Envelope_ReleaseData_;

export type WithdrawV2AdminReleaseResponse401 = ErrorEnvelope;

export type WithdrawV2AdminReleaseResponse403 = ErrorEnvelope;

export type WithdrawV2AdminReleaseResponse404 = ErrorEnvelope;

export type WithdrawV2AdminReleaseResponse405 = ErrorEnvelope;

export type WithdrawV2AdminReleaseResponse409 = ErrorEnvelope;

export type WithdrawV2AdminReleaseResponse422 = ErrorEnvelope;

export type WithdrawV2AdminReleaseResponse429 = ErrorEnvelope;

export type WithdrawV2AdminReleaseResponse500 = ErrorEnvelope;

export type WithdrawV2AdminReleaseResponse503 = ErrorEnvelope;

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
