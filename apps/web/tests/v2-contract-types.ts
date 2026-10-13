// Compile-only acceptance: these declarations come from the v2 OpenAPI exporter.
import type {
  ErrorEnvelope,
  FoundationConfig,
  GetV2ConfigResponse200,
  ListV2OfferingsQuery,
  ListV2OfferingsResponse200,
  ListV2OfferingsResponse422,
  Meta,
  PageInfo,
} from '../../../packages/contracts/v2/generated';

type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends (<T>() => T extends B ? 1 : 2) ? true : false;
type Assert<T extends true> = T;
type RequiredKeys<T> = { [K in keyof T]-?: object extends Pick<T, K> ? never : K }[keyof T];

export type MetaFieldsAreRequired = Assert<Equal<RequiredKeys<Meta>, keyof Meta>>;
export type FactVersionRemainsNull = Assert<Equal<Meta['release_id'], null>>;
export type UnknownDataClockRemainsNull = Assert<Equal<Meta['data_as_of'], null>>;
export type DataModesMatchRunnableInstances = Assert<Equal<Meta['data_mode'], 'demo' | 'verified'>>;
export type ModelModesMatchRunnableInstances = Assert<Equal<Meta['model_mode'], 'disabled' | 'mock'>>;
export type ConfigFieldsAreRequired = Assert<Equal<RequiredKeys<FoundationConfig>, keyof FoundationConfig>>;
export type EnvironmentsMatchSettings = Assert<Equal<FoundationConfig['app_environment'], 'development' | 'test' | 'production'>>;
export type QueryRolesAreServerDerived = Assert<Equal<FoundationConfig['query_role'], 'demo_only' | 'published_readonly'>>;
export type SchemaVersionIsT03 = Assert<Equal<FoundationConfig['schema_version'], 'v2.t03'>>;
export type FoundationUnavailable = Assert<Equal<FoundationConfig['business_available'], false>>;
export type RequiredNullableCursor = Assert<Equal<PageInfo['next_cursor'], string | null>>;
export type CursorIsRequired = Assert<Equal<RequiredKeys<PageInfo>, keyof PageInfo>>;
export type QueryLimitIsOptional = Assert<Equal<ListV2OfferingsQuery['limit'], number | undefined>>;
export type QueryCursorMatchesSchema = Assert<Equal<ListV2OfferingsQuery['cursor'], string | null | undefined>>;
export type SuccessUsesActualConfig = Assert<Equal<GetV2ConfigResponse200['data'], FoundationConfig>>;
export type ErrorUsesActualEnvelope = Assert<Equal<ListV2OfferingsResponse422, ErrorEnvelope>>;

const meta: Meta = {
  api_version: 'v2', request_id: '0123456789abcdef0123456789abcdef',
  data_as_of: null, profile_version_id: null, release_id: null,
  ruleset_version: null, profile_mode: null, data_mode: 'demo', model_mode: 'disabled',
};
const emptyCatalog: ListV2OfferingsResponse200 = {
  data: { items: [], page: { limit: 20, next_cursor: null, has_more: false } }, meta,
};
const verifiedMeta: Meta = { ...meta, data_mode: 'verified', model_mode: 'disabled' };
const demoMockMeta: Meta = { ...meta, data_mode: 'demo', model_mode: 'mock' };
const productionConfig: GetV2ConfigResponse200 = {
  data: {
    api_version: 'v2', schema_version: 'v2.t03', contract_stage: 'foundation',
    app_environment: 'production', query_role: 'published_readonly',
    data_mode: 'verified', model_mode: 'disabled', business_available: false,
    live_available: false, supported_scope: [], supported_province: null, entry_year: null,
  },
  meta: verifiedMeta,
};
const defaultQuery: ListV2OfferingsQuery = {};
const boundedQuery: ListV2OfferingsQuery = { limit: 1, cursor: 'unissued' };
const cursorError: ListV2OfferingsResponse422 = {
  error: {
    code: 'INVALID_CURSOR', message: '本阶段未发行有效分页游标', request_id: meta.request_id,
    details: [{ field_path: 'query.cursor', code: 'INVALID_CURSOR', message: '待核验' }],
  },
};

// @ts-expect-error Unknown fact clocks cannot become request timestamps.
const falseDataClock: Meta['data_as_of'] = '2026-10-01';
// @ts-expect-error Only demo/verified are data modes.
const falseDataMode: Meta['data_mode'] = 'production';
// @ts-expect-error No runnable v2 instance can report live before a provider exists.
const falseModelMode: Meta['model_mode'] = 'live';
// @ts-expect-error Application query_role is not a database/admin authority.
const falseQueryRole: FoundationConfig['query_role'] = 'admin';
// @ts-expect-error An environment must use the settings' explicit enum.
const falseEnvironment: FoundationConfig['app_environment'] = 'staging';
// @ts-expect-error A required null cursor cannot be omitted.
const missingCursor: PageInfo = { limit: 20, has_more: false };
// @ts-expect-error Query values are generated from the numeric OpenAPI limit.
const badLimit: ListV2OfferingsQuery = { limit: '20' };
// @ts-expect-error Future catalog filters are not part of the T02 query.
const unsupportedFilter: ListV2OfferingsQuery = { country: 'GB' };
// @ts-expect-error An error body cannot be substituted for a success envelope.
const wrongSuccess: ListV2OfferingsResponse200 = cursorError;

void [emptyCatalog, verifiedMeta, demoMockMeta, productionConfig, defaultQuery,
  boundedQuery, cursorError, falseDataClock, falseDataMode, falseModelMode,
  falseQueryRole, falseEnvironment, missingCursor, badLimit, unsupportedFilter, wrongSuccess];
