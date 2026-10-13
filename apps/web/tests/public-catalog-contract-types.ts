// Compile-only T20 acceptance uses only the independently generated public wire.
import type {
  CoverageData, ErrorEnvelope, GetV2PublicConfigResponse200,
  GetV2PublicEvidencePath, GetV2PublicEvidenceQuery, GetV2PublicEvidenceResponse200,
  ListV2PublicOfferingsQuery, ListV2PublicOfferingsResponse200, ListV2PublicOfferingsResponse503,
  Meta, PublicDateData, PublicEvidenceData, PublicFactData, PublicOfferingData,
} from '../../../packages/contracts/v2/public_catalog/generated';

type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends (<T>() => T extends B ? 1 : 2) ? true : false;
type Assert<T extends true> = T;
type RequiredKeys<T> = { [K in keyof T]-?: object extends Pick<T, K> ? never : K }[keyof T];

export type QueryRequiresExplicitYear = Assert<Equal<RequiredKeys<ListV2PublicOfferingsQuery>, 'entry_year'>>;
export type EvidenceRequiresRelease = Assert<Equal<RequiredKeys<GetV2PublicEvidenceQuery>, 'release_id'>>;
export type EvidencePathIsExact = Assert<Equal<keyof GetV2PublicEvidencePath, 'evidence_id'>>;
export type EvidenceResponseIsProjection = Assert<Equal<GetV2PublicEvidenceResponse200['data'], PublicEvidenceData>>;
export type PublicPageUsesActualOffering = Assert<Equal<ListV2PublicOfferingsResponse200['data']['items'][number], PublicOfferingData>>;
export type PublicErrorsAreCommonEnvelope = Assert<Equal<ListV2PublicOfferingsResponse503, ErrorEnvelope>>;
export type SchemaIsT20 = Assert<Equal<GetV2PublicConfigResponse200['data']['schema_version'], 'v2.t20'>>;
export type MetaHasNoInventedSnapshot = Assert<Equal<Meta['release_id'], null>>;
export type ActualReleaseVersionIsLiteral = Assert<Equal<PublicOfferingData['release_version'], 1>>;
export type RuleVersionUnavailable = Assert<Equal<PublicOfferingData['ruleset_version'], null>>;
export type NoInventedOfficialUTC = Assert<Equal<PublicDateData['utc_instant'], null>>;
export type UnknownNationalTotal = Assert<Equal<CoverageData['expected_total'], null>>;
export type NoClaimedNationalCoverage = Assert<Equal<CoverageData['status'], 'no_published_records' | 'partial'>>;
export type PrivateEvidenceReferenceCanBeNull = Assert<Equal<PublicFactData['evidence_id'], string | null>>;
export type FactHasNoPrivateIDs = Assert<Equal<Extract<keyof PublicFactData, 'file_id' | 'import_id' | 'import_row_id' | 'owner_user_id'>, never>>;
export type EvidenceHasNoSourceURL = Assert<Equal<Extract<keyof PublicEvidenceData, 'entry_url' | 'path' | 'storage_key' | 'source_id' | 'document_id'>, never>>;
export type FactNullsRemainRequired = Assert<Equal<RequiredKeys<PublicFactData>, keyof PublicFactData>>;

const query: ListV2PublicOfferingsQuery = { entry_year: 2026, country: 'CN', province: 'known:DEMO_PROVINCE', limit: 20 };
const evidence: GetV2PublicEvidenceQuery = { release_id: '00000000-0000-4000-8000-000000000001' };
// @ts-expect-error A year is never silently defaulted.
const missingYear: ListV2PublicOfferingsQuery = {};
// @ts-expect-error HTTP integer values are represented by numeric schema types.
const lexicalYear: ListV2PublicOfferingsQuery = { entry_year: '2026' };
// @ts-expect-error A public query cannot request another student's owner scope.
const injectedOwner: ListV2PublicOfferingsQuery = { entry_year: 2026, owner_user_id: 'user' };
// @ts-expect-error Public evidence is always tied to an explicit release.
const noRelease: GetV2PublicEvidenceQuery = {};
// @ts-expect-error T25 has not supplied a ruleset version.
const inventedRule: PublicOfferingData['ruleset_version'] = 'rules-v1';
// @ts-expect-error T12 candidate conversion does not become an official UTC deadline.
const officialDeadline: PublicDateData['utc_instant'] = '2026-10-03T00:00:00Z';
// @ts-expect-error The reference coverage is not declared complete.
const complete: CoverageData['status'] = 'complete';
void [query, evidence, missingYear, lexicalYear, injectedOwner, noRelease, inventedRule, officialDeadline, complete];
