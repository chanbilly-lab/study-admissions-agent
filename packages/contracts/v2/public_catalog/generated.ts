// Generated offline from create_public_catalog_v2_app().openapi() by scripts/generate_contracts.py.
// Do not edit. JSON Schema validation constraints remain in openapi.json.

export interface CoverageData {
  coverage_ratio: null;
  expected_total: null;
  returned_count: number;
  status: "no_published_records" | "partial";
}

export interface Envelope_PublicConfigData_ {
  data: PublicConfigData;
  meta: Meta;
}

export interface Envelope_PublicEvidenceData_ {
  data: PublicEvidenceData;
  meta: Meta;
}

export interface Envelope_PublicOfferingsData_ {
  data: PublicOfferingsData;
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

export interface GetV2PublicConfigQuery {

}

export type GetV2PublicConfigResponse200 = Envelope_PublicConfigData_;

export type GetV2PublicConfigResponse401 = ErrorEnvelope;

export type GetV2PublicConfigResponse403 = ErrorEnvelope;

export type GetV2PublicConfigResponse404 = ErrorEnvelope;

export type GetV2PublicConfigResponse405 = ErrorEnvelope;

export type GetV2PublicConfigResponse409 = ErrorEnvelope;

export type GetV2PublicConfigResponse422 = ErrorEnvelope;

export type GetV2PublicConfigResponse429 = ErrorEnvelope;

export type GetV2PublicConfigResponse500 = ErrorEnvelope;

export type GetV2PublicConfigResponse503 = ErrorEnvelope;

export interface GetV2PublicEvidencePath {
  evidence_id: string;
}

export interface GetV2PublicEvidenceQuery {
  release_id: string;
}

export type GetV2PublicEvidenceResponse200 = Envelope_PublicEvidenceData_;

export type GetV2PublicEvidenceResponse401 = ErrorEnvelope;

export type GetV2PublicEvidenceResponse403 = ErrorEnvelope;

export type GetV2PublicEvidenceResponse404 = ErrorEnvelope;

export type GetV2PublicEvidenceResponse405 = ErrorEnvelope;

export type GetV2PublicEvidenceResponse409 = ErrorEnvelope;

export type GetV2PublicEvidenceResponse422 = ErrorEnvelope;

export type GetV2PublicEvidenceResponse429 = ErrorEnvelope;

export type GetV2PublicEvidenceResponse500 = ErrorEnvelope;

export type GetV2PublicEvidenceResponse503 = ErrorEnvelope;

export interface ListV2PublicOfferingsQuery {
  applicant_category?: null | string;
  country?: null | string;
  course_system?: null | string;
  cursor?: null | string;
  entry_year: number;
  limit?: number;
  pathway?: null | string;
  province?: null | string;
  release_id?: null | string;
  study_level?: "undergraduate" | null;
}

export type ListV2PublicOfferingsResponse200 = Envelope_PublicOfferingsData_;

export type ListV2PublicOfferingsResponse401 = ErrorEnvelope;

export type ListV2PublicOfferingsResponse403 = ErrorEnvelope;

export type ListV2PublicOfferingsResponse404 = ErrorEnvelope;

export type ListV2PublicOfferingsResponse405 = ErrorEnvelope;

export type ListV2PublicOfferingsResponse409 = ErrorEnvelope;

export type ListV2PublicOfferingsResponse422 = ErrorEnvelope;

export type ListV2PublicOfferingsResponse429 = ErrorEnvelope;

export type ListV2PublicOfferingsResponse500 = ErrorEnvelope;

export type ListV2PublicOfferingsResponse503 = ErrorEnvelope;

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

export interface PageInfo {
  has_more: boolean;
  limit: number;
  next_cursor: null | string;
}

export interface PublicConfigData {
  allow_test_fixture_read: boolean;
  api_version: "v2";
  app_environment: "development" | "production" | "test";
  business_available: boolean;
  contract_stage: "public_catalog";
  data_mode: "demo" | "verified";
  demo_banner: "DEMO：合成测试资料，不是真实招生依据" | null;
  entry_year: null;
  live_available: false;
  model_mode: "disabled" | "mock";
  query_role: "demo_only" | "published_readonly";
  schema_version: "v2.t20";
  supported_province: null;
  supported_scope: string[];
}

export interface PublicDateData {
  calculated_utc_instant: null | string;
  conversion_status: "ambiguous" | "date_only" | "missing_timezone" | "nonexistent" | "out_of_range" | "source_conflict" | "unique" | "unknown";
  event_type: "application_deadline" | "application_open" | "enrollment" | "equal_consideration" | "language_supplement" | "materials_deadline" | "offer_acceptance" | "scholarship_deadline" | "score_supplement";
  local_date: null | string;
  local_time: null | string;
  original_text: string;
  precision: "date" | "minute" | "second" | "unknown";
  source_alignment: "conflict" | "pending";
  timezone: null | string;
  tzdata_version: "2026.4";
  utc_instant: null;
}

export interface PublicEvidenceData {
  authority_claim: "claimed_official" | "not_official" | "unclassified";
  document_sha256: string;
  entry_year: number;
  evidence_id: string;
  is_synthetic: boolean;
  language: "en" | "und" | "zh-Hans" | "zh-Hant";
  locator: EvidenceLocator;
  offering_id: string;
  offering_version: number;
  publisher: string;
  quote: string;
  release_id: string;
  release_version: 1;
  requirements_version: string;
  scope: EvidenceScope;
  snippet_sha256: string;
}

export interface PublicFactData {
  claim_kind: "historical_statistic" | "information" | "minimum_requirement" | "typical_offer" | "unknown";
  cohort_year: null | number;
  date_resolution: PublicDateData | null;
  evidence_id: null | string;
  fact_type: "date" | "fee" | "material" | "requirement" | "score" | "statistic";
  field_key: string;
  footnote_state: "none" | "present" | "unknown";
  footnote_text: null | string;
  missing_reason: "ambiguous" | "not_applicable" | "not_provided" | "not_published" | "unavailable" | null;
  normalized_value: null | string;
  period: "academic_year" | "not_applicable" | "one_time" | "program" | "survey_period" | "unknown";
  statistic_denominator: null | string;
  statistic_population: null | string;
  statistics_basis: "admission" | "employment" | "not_applicable" | "other" | "unknown";
  survey_period: null | string;
  unit: null | string;
  unit_code: "CNY" | "GBP" | "ISO_DATE" | "fraction" | "item" | "people" | "percent" | "points" | "text" | "unknown";
  value_kind: "decimal" | "text";
  value_text: null | string;
}

export interface PublicOfferingData {
  content_sha256: string;
  entry_year: number;
  facts: PublicFactData[];
  id: string;
  institution_id: string;
  institution_name: string;
  is_synthetic: boolean;
  program_id: string;
  program_name: string;
  release_id: string;
  release_version: 1;
  requirements_version: string;
  ruleset_version: null;
  scope: EvidenceScope;
  version: number;
}

export interface PublicOfferingsData {
  coverage: CoverageData;
  items: PublicOfferingData[];
  page: PageInfo;
}

export interface ScopeKey {
  status: "known" | "not_applicable" | "unknown";
  value: null | string;
}
