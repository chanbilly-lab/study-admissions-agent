// Compile-only checks of T28's actual generated protocol; no UI or network.
import type {
  AssessmentData, AssessmentRequest, AssessmentContextData, EligibilityEngineResult,
  CompletionObligation, EvaluationResult, UnknownDimension, ReplayRequest,
  EvaluateV2EligibilityRequestBody, EvaluateV2EligibilityResponse200,
  GetV2EligibilityEvaluationPath, GetV2EligibilityEvaluationResponse200,
  ReplayV2EligibilityEvaluationRequestBody, ReplayV2EligibilityEvaluationPath,
} from '../../../packages/contracts/v2/assessments/generated';

type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends (<T>() => T extends B ? 1 : 2) ? true : false;
type Assert<T extends true> = T;
type RequiredKeys<T> = { [K in keyof T]-?: object extends Pick<T, K> ? never : K }[keyof T];

export type FourStatesAreClosed = Assert<Equal<EligibilityEngineResult['status'], 'eligible' | 'ineligible' | 'conditional' | 'unknown'>>;
export type ActualTraceIsNullableWhenRuleMissing = Assert<Equal<EligibilityEngineResult['evaluation'], EvaluationResult | null>>;
export type CompletionIsAchievedOnly = Assert<Equal<CompletionObligation['basis'], 'achieved'>>;
export type DataDimensionsDoNotCreateScores = Assert<Equal<UnknownDimension['status'], 'unknown'>>;
export type ExactInitialVersion = Assert<Equal<AssessmentData['version'], 1>>;
export type ConfirmedIsRequiredTrue = Assert<Equal<AssessmentRequest['confirmed'], true>>;
export type ReplayRequiresExplicitConfirmation = Assert<Equal<ReplayRequest, { confirmed: true }>>;
export type NewInputHasAllNullableScopeKeysRequired = Assert<Equal<RequiredKeys<AssessmentRequest>, keyof AssessmentRequest>>;
export type NoClientAuthorityOrClock = Assert<Equal<Extract<keyof AssessmentRequest,
  'owner_id' | 'role' | 'eligibility' | 'expression' | 'assessment_at' | 'grades' | 'ruleset_version' | 'is_synthetic'>, never>>;
export type ExactFrozenContextVersion = Assert<Equal<AssessmentContextData['schema_version'], 'v2.t28'>>;
export type WirePostUsesActualInput = Assert<Equal<EvaluateV2EligibilityRequestBody, AssessmentRequest>>;
export type NewResultUsesActualOutput = Assert<Equal<EvaluateV2EligibilityResponse200['data'], AssessmentData>>;
export type ReadKeepsFrozenShape = Assert<Equal<GetV2EligibilityEvaluationResponse200['data'], AssessmentData>>;
export type HistoricalAndCurrentAreSeparate = Assert<Equal<AssessmentData['current_validity'],
  'current' | 'withdrawn' | 'replaced' | 'needs_review' | 'unavailable'>>;
export type NoFrozenPrivateContextExport = Assert<Equal<Extract<keyof AssessmentData, 'context' | 'expression' | 'profile_payload' | 'quote' | 'url'>, never>>;
export type ReplayBodyUsesOwnBoundedModel = Assert<Equal<ReplayV2EligibilityEvaluationRequestBody, ReplayRequest>>;
export type ReadCanonicalReference = Assert<Equal<keyof GetV2EligibilityEvaluationPath, 'assessment_id'>>;
export type ReplayCanonicalReference = Assert<Equal<keyof ReplayV2EligibilityEvaluationPath, 'assessment_id'>>;
export type BothCanonicalReferencesAreStrings = Assert<Equal<GetV2EligibilityEvaluationPath['assessment_id'] | ReplayV2EligibilityEvaluationPath['assessment_id'], string>>;

export function compileOnlyNegativeInputs(input: AssessmentRequest, result: AssessmentData): void {
  // @ts-expect-error qualification is a four-state contract, never a probability.
  const probability: EligibilityEngineResult['status'] = 'probability';
  // @ts-expect-error booleans cannot impersonate the literal initial version.
  const booleanVersion: AssessmentData['version'] = true;
  // @ts-expect-error historical validity is separate from the original eligibility.
  const validity: AssessmentData['current_validity'] = 'eligible';
  // @ts-expect-error predictions cannot be completion obligations.
  const basis: CompletionObligation['basis'] = 'predicted';
  // @ts-expect-error clients cannot supply an owner.
  const forgedOwner: AssessmentRequest = { ...input, owner_id: 'other-user' };
  // @ts-expect-error clients cannot send a calculated conclusion.
  const forgedResult: AssessmentRequest = { ...input, eligibility: 'eligible' };
  // @ts-expect-error clients cannot set the evaluation time.
  const forgedTime: AssessmentRequest = { ...input, assessment_at: '2027-01-01T00:00:00Z' };
  // @ts-expect-error replay cannot silently act without confirmation.
  const replay: ReplayRequest = { confirmed: false };
  // @ts-expect-error required-nullable extra scopes cannot be dropped.
  const missingNullable: AssessmentRequest = { confirmed: true, profile_id: input.profile_id,
    profile_version_id: input.profile_version_id, target: input.target, release_id: input.release_id, stage: input.stage };
  void [result, probability, booleanVersion, validity, basis, forgedOwner, forgedResult, forgedTime, replay, missingNullable];
}
