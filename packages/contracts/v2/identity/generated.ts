// Generated offline from create_identity_v2_app().openapi() by scripts/generate_contracts.py.
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
