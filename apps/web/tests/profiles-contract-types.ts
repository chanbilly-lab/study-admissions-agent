// Compile-only T23 acceptance imports the actual independent OpenAPI output.
import type {
  AdaptationData, AppendInput, AppendV2ProfileVersionPath, AppendV2ProfileVersionRequestBody,
  AssessmentPair, CreateInput, CreateV2ProfileHeaders, CreateV2ProfileRequestBody,
  CreateV2ProfileResponse200, GetV2ProfileResponse200, GetV2ProfileVersionPath,
  GetV2ProfilesContextResponse200, GradeAssessments, GradeSlot, ListV2ProfilesQuery,
  ListV2ProfilesResponse200, ListV2ProfilesResponse503, ErrorEnvelope, ProfileRef,
  ProfileSnapshot, ProfileVersionData, Preferences, ProfileMeta, Meta,
} from '../../../packages/contracts/v2/profiles/generated';

type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends (<T>() => T extends B ? 1 : 2) ? true : false;
type Assert<T extends true> = T;
type RequiredKeys<T> = { [K in keyof T]-?: object extends Pick<T, K> ? never : K }[keyof T];

export type SnapshotHasNoImplicitNullableDefaults = Assert<Equal<RequiredKeys<ProfileSnapshot>, keyof ProfileSnapshot>>;
export type IndependentSlotsAreRequired = Assert<Equal<RequiredKeys<AssessmentPair>, 'achieved' | 'predicted'>>;
export type GradeNullsRemainRequired = Assert<Equal<RequiredKeys<GradeSlot>, keyof GradeSlot>>;
export type GradeDecimalDoesNotBecomeFloat = Assert<Equal<GradeSlot['value'], string | null>>;
export type CapacityNullIsNotZero = Assert<Equal<ProfileSnapshot['weekly_hours'], string | null>>;
export type AssessmentKeysAreExplicit = Assert<Equal<keyof GradeAssessments,
  'gaokao_total' | 'chinese' | 'math' | 'gaokao_english' | 'physics' | 'chemistry' | 'biology' |
  'politics' | 'history' | 'geography' | 'ielts_overall' | 'ielts_listening' | 'ielts_reading' | 'ielts_writing' | 'ielts_speaking'>>;
export type UnprovidedAssessmentKeysCanBeOmitted = Assert<Equal<RequiredKeys<GradeAssessments>, never>>;
export type ResidenceAndExamProvinceAreSeparateRequiredKeys = Assert<Equal<Extract<RequiredKeys<ProfileSnapshot>, 'residence_region' | 'exam_province'>, 'residence_region' | 'exam_province'>>;
export type ConfirmationIsActualBoolean = Assert<Equal<CreateInput['confirmed'], true>>;
export type AppendHasRequiredCAS = Assert<Equal<AppendInput['expected_current_version'], number>>;
export type CreateBodyComesFromActualInput = Assert<Equal<CreateV2ProfileRequestBody, CreateInput>>;
export type AppendBodyComesFromActualInput = Assert<Equal<AppendV2ProfileVersionRequestBody, AppendInput>>;
export type CreationHasOneHeader = Assert<Equal<keyof CreateV2ProfileHeaders, 'Idempotency-Key'>>;
export type AppendHasOnlyRootPath = Assert<Equal<keyof AppendV2ProfileVersionPath, 'profile_id'>>;
export type HistoricalReferenceRequiresTwoUUIDs = Assert<Equal<RequiredKeys<GetV2ProfileVersionPath>, 'profile_id' | 'version_id'>>;
export type ExplicitCreateReceiptContainsConfirmedVersion = Assert<Equal<CreateV2ProfileResponse200['data']['version'], ProfileVersionData>>;
export type ReadReturnsTheActualSnapshot = Assert<Equal<GetV2ProfileResponse200['data'], ProfileVersionData>>;
export type BoundedListContainsReferences = Assert<Equal<ListV2ProfilesResponse200['data']['items'][number], ProfileRef>>;
export type ListErrorsUseSafeEnvelope = Assert<Equal<ListV2ProfilesResponse503, ErrorEnvelope>>;
export type NoEligibilityOrImplementedAdapterClaim = Assert<Equal<AdaptationData['status'], 'unknown' | 'unsupported'>>;
export type DeclaredSourceIsNotVerified = Assert<Equal<ProfileVersionData['source'], 'student_declared'>>;
export type ContextVersionIsT23 = Assert<Equal<GetV2ProfilesContextResponse200['data']['schema_version'], 'v2.t23'>>;
export type ActualVersionMetaIsRequiredNullable = Assert<Equal<ProfileMeta['profile_version_id'], string | null>>;
export type DeclaredModeMetaIsRequiredNullable = Assert<Equal<ProfileMeta['profile_mode'], 'synthetic' | 'real' | null>>;
export type VersionResponseUsesLocalMeta = Assert<Equal<GetV2ProfileResponse200['meta'], ProfileMeta>>;
export type OriginalParentMetaRemainsEmpty = Assert<Equal<Meta['profile_version_id'] | Meta['profile_mode'], null>>;
export type NoClientAuthorityFields = Assert<Equal<Extract<keyof CreateInput | keyof ProfileSnapshot, 'owner_id' | 'role' | 'verified' | 'is_synthetic' | 'consent_id'>, never>>;
export type PreferencesBudgetIsExplicitlyNullable = Assert<Equal<Preferences['budget'], { amount: string; currency: 'CNY' | 'GBP' } | null>>;

const missing: GradeSlot = { status: 'missing', value: null, scale: null, unit: null };
const pending: GradeSlot = { status: 'pending', value: null, scale: null, unit: null };
const pair: AssessmentPair = { achieved: { status: 'provided', value: '0', scale: '100', unit: 'points' }, predicted: pending };
const unknown = { status: 'unknown' as const, value: null };
const profile: ProfileSnapshot = {
  study_level: 'bachelor', entry_year: 2027, residence_region: unknown,
  course_system: { status: 'known', value: 'gaokao' }, applicant_category: unknown,
  exam_province: unknown, pathway: unknown, subjects: [], assessments: { math: pair }, weekly_hours: '0', preferences: null,
};
const create: CreateV2ProfileRequestBody = { profile, confirmed: true };
const append: AppendV2ProfileVersionRequestBody = { profile, expected_current_version: 1, confirmed: true };
const header: CreateV2ProfileHeaders = { 'Idempotency-Key': 'opaque-profile-request' };
const query: ListV2ProfilesQuery = { limit: 20 };
// @ts-expect-error Missing grades remain explicit null fields rather than omitted values.
const omittedNulls: GradeSlot = { status: 'missing' };
// @ts-expect-error Both independent slots must be present for a supplied assessment.
const missingPrediction: AssessmentPair = { achieved: missing };
// @ts-expect-error Exact decimals are strings, never binary floats.
const floatValue: GradeSlot = { status: 'provided', value: 0, scale: '100', unit: 'points' };
// @ts-expect-error Free or misspelled assessment keys are not part of the closed wire.
const unknownAssessment: GradeAssessments = { ielts: pair };
// @ts-expect-error A client cannot choose an owner.
const ownerInjection: CreateInput = { profile, confirmed: true, owner_id: 'other-user' };
// @ts-expect-error A new version needs exact current-version CAS.
const missingCAS: AppendInput = { profile, confirmed: true };
// @ts-expect-error Confirmation cannot be false or numeric.
const unconfirmed: CreateInput = { profile, confirmed: false };
// @ts-expect-error A historical UUID alone cannot select a different root.
const missingRoot: GetV2ProfileVersionPath = { version_id: '00000000-0000-4000-8000-000000000001' };
// @ts-expect-error Profile storage does not produce eligibility conclusions.
const inventedEligibility: AdaptationData['status'] = 'eligible';
void [missing, pending, pair, profile, create, append, header, query, omittedNulls, missingPrediction,
  floatValue, unknownAssessment, ownerInjection, missingCAS, unconfirmed, missingRoot, inventedEligibility];
