// Generated offline from create_v2_app().openapi() by scripts/generate_contracts.py.
// Do not edit. JSON Schema validation constraints remain in openapi.json.

export interface Envelope_FoundationConfig_ {
  data: FoundationConfig;
  meta: Meta;
}

export interface Envelope_Page_OfferingReference__ {
  data: Page_OfferingReference_;
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
