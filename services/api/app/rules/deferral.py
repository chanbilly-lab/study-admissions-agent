"""Bounded test-only deferral bindings; this module never decides eligibility."""

from datetime import date, datetime, time
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.date_schemas import DateEventData
from ..admissions_catalog.schemas import CatalogModel, Identifier, PositiveVersion, _identifier
from ..evidence.schemas import EvidenceScope, _uuid
from .adapters.schemas import Hash, Stage, TargetReference, scope_fingerprint
from .expression import AssessmentKey, explicit_instant


MAX_BUNDLES = 32
MissingState = Literal["known", "missing", "pending", "not_applicable", "conflicted"]
DeadlineStatus = Literal["before", "expired", "unknown", "not_applicable"]
DeferralReason = Literal["ALLOWED", "POLICY_DISABLED", "REAL_POLICIES_UNAVAILABLE",
    "RULESET_UNAVAILABLE", "POLICY_UNAVAILABLE", "INVALID_BUNDLE", "SYNTHETIC_BOUNDARY",
    "TARGET_MISMATCH", "YEAR_MISMATCH", "STAGE_MISMATCH", "VERSION_MISMATCH",
    "ITEM_NOT_ALLOWED", "MISSING_STATE_NOT_ALLOWED", "PREDICTED_NOT_ACHIEVED",
    "POLICY_EXPIRED", "SCOPE_UNKNOWN", "DEADLINE_MISSING", "DEADLINE_MISMATCH",
    "DEADLINE_UNCERTAIN", "DEADLINE_EXPIRED", "VERIFIER_UNAVAILABLE",
    "BINDING_UNVERIFIED", "AMBIGUOUS_POLICIES"]


class DeferralInputError(ValueError):
    status_code = 422
    code = "INVALID_DEFERRAL_INPUT"

    def __init__(self):
        super().__init__("Deferral input is invalid")


def _refs(value, *, maximum=32, minimum=1):
    if type(value) not in (tuple, list) or not minimum <= len(value) <= maximum:
        raise ValueError("bounded explicit references are required")
    current = tuple(_uuid(item) for item in value)
    if len(set(current)) != len(current):
        raise ValueError("references must be unique")
    return current


class DeferralRequest(CatalogModel):
    target: TargetReference
    entry_year: int = Field(strict=True, ge=1, le=9999)
    stage: Stage
    release_id: UUID
    release_version: PositiveVersion
    requirements_version: Hash
    ruleset_version: Hash | None
    assessment_key: AssessmentKey
    basis: Literal["achieved", "predicted"]
    missing_state: MissingState
    assessment_at: datetime = Field(strict=True)

    _id = field_validator("release_id", mode="before")(_uuid)
    _time = field_validator("assessment_at", mode="before")(explicit_instant)


class DeferralQuery(CatalogModel):
    target: TargetReference
    entry_year: int = Field(strict=True, ge=1, le=9999)
    stage: Stage
    release_id: UUID
    release_version: PositiveVersion
    requirements_version: Hash
    ruleset_version: Hash | None
    assessment_key: AssessmentKey
    basis: Literal["achieved", "predicted"]

    _id = field_validator("release_id", mode="before")(_uuid)


class DeadlineBinding(CatalogModel):
    date_event: DateEventData
    evidence_ids: tuple[UUID, ...] = Field(min_length=1, max_length=32)
    reference_calendar: str | None = Field(strict=True, min_length=1, max_length=100)

    _evidence = field_validator("evidence_ids", mode="before")(_refs)

    @field_validator("date_event", mode="before")
    @classmethod
    def safe_native_dates(cls, value):
        # Guard native values before the older T12 validators can call offset
        # methods. No custom timezone code may run, including on forged copies.
        if type(value) is DateEventData:
            raw = value.__dict__
        elif type(value) is dict:
            raw = value
        else:
            raise ValueError("an exact date event is required")
        local_date, local_time = raw.get("local_date"), raw.get("local_time")
        if local_date is not None and type(local_date) is not date:
            raise ValueError("a native local date is required")
        if local_time is not None and (type(local_time) is not time or local_time.tzinfo is not None
            or local_time.fold or local_time.microsecond):
            raise ValueError("a native unambiguous local time is required")
        if raw.get("timezone") is not None and type(raw["timezone"]) is not str:
            raise ValueError("an explicit timezone key is required")
        for name in ("calculated_utc_instant", "utc_instant"):
            instant = raw.get(name)
            if instant is not None:
                if type(instant) is not datetime:
                    raise ValueError("a native calculated instant is required")
                explicit_instant(instant)
        return value

    @field_validator("reference_calendar")
    @classmethod
    def exact_calendar(cls, value):
        if value is not None and (type(value) is not str or any(ord(c) < 33 or ord(c) > 126 for c in value)):
            raise ValueError("an explicit calendar key is required")
        return value


class DeferralBundle(CatalogModel):
    bundle_id: UUID
    reference_key: Identifier
    policy_id: UUID
    policy_version: Hash
    release_id: UUID
    release_version: PositiveVersion
    requirements_version: Hash
    ruleset_version: Hash | None
    is_synthetic: bool = Field(strict=True)
    scope: EvidenceScope
    scope_sha256: Hash
    offering_id: UUID
    offering_version: PositiveVersion
    stage: Stage
    assessment_keys: tuple[AssessmentKey, ...] = Field(min_length=1, max_length=15)
    allowed_missing_states: tuple[Literal["missing", "pending"], ...] = Field(min_length=1, max_length=2)
    valid_from: datetime = Field(strict=True)
    valid_until: datetime = Field(strict=True)
    policy_evidence_ids: tuple[UUID, ...] = Field(min_length=1, max_length=32)
    application_deadline_required: bool = Field(strict=True)
    application_deadline: DeadlineBinding | None
    supplement_deadline: DeadlineBinding | None

    _identity = field_validator("bundle_id", "policy_id", "release_id", "offering_id", mode="before")(_uuid)
    _time = field_validator("valid_from", "valid_until", mode="before")(explicit_instant)
    _evidence = field_validator("policy_evidence_ids", mode="before")(_refs)

    @field_validator("assessment_keys", "allowed_missing_states", mode="before")
    @classmethod
    def exact_items(cls, value, info):
        maximum = 15 if info.field_name == "assessment_keys" else 2
        if type(value) not in (tuple, list) or not 1 <= len(value) <= maximum:
            raise ValueError("explicit bounded policy items are required")
        if any(type(item) is not str for item in value):
            raise ValueError("explicit bounded policy items are required")
        if len(set(value)) != len(value):
            raise ValueError("policy items must be unique")
        return value

    @field_validator("reference_key")
    @classmethod
    def exact_reference(cls, value):
        return _identifier(value)

    @model_validator(mode="after")
    def exact_bundle(self):
        if self.valid_from >= self.valid_until or self.scope_sha256 != scope_fingerprint(self.scope):
            raise ValueError("policy window and original scope must be exact")
        if (self.is_synthetic and not self.reference_key.startswith("DEMO_")) or (
            not self.is_synthetic and self.reference_key.upper().startswith("DEMO_")):
            raise ValueError("policy namespace must match its marker")
        if not self.application_deadline_required and self.application_deadline is not None:
            raise ValueError("an inapplicable application deadline must be null")
        return self


class DeferralPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_bundles: bool = Field(default=False, strict=True)
    real_deferrals_ready: Literal[False] = False
    app_environment: Literal["development", "test", "production"] = "production"
    data_mode: Literal["demo", "verified"] = "verified"

    @field_validator("real_deferrals_ready", mode="before")
    @classmethod
    def real_closed(cls, value):
        if value is not False:
            raise ValueError("real deferral policies are not implemented")
        return value

    @model_validator(mode="after")
    def test_boundary(self):
        if self.allow_test_bundles and (self.app_environment != "test" or self.data_mode != "demo"):
            raise ValueError("test policies require the explicit test/demo boundary")
        return self


class DeferralResult(CatalogModel):
    deferral_status: Literal["allowed", "unknown"]
    reason: DeferralReason
    application_deadline_status: DeadlineStatus
    supplement_deadline_status: Literal["before", "expired", "unknown"]
    bundle_id: UUID | None
    policy_id: UUID | None
    policy_version: Hash | None
    application_deadline_event_id: UUID | None
    supplement_deadline_event_id: UUID | None
    evidence_ids: tuple[UUID, ...] = Field(max_length=96)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def exact_evidence(cls, value):
        return _refs(value, maximum=96, minimum=0)

    @model_validator(mode="after")
    def selected_references(self):
        refs = (self.bundle_id, self.policy_id, self.policy_version, self.supplement_deadline_event_id)
        if self.deferral_status == "allowed":
            if (self.reason != "ALLOWED" or any(value is None for value in refs) or not self.evidence_ids
                or self.supplement_deadline_status != "before"
                or self.application_deadline_status not in {"before", "not_applicable"}
                or (self.application_deadline_event_id is None) != (self.application_deadline_status == "not_applicable")):
                raise ValueError("allowed deferral needs complete current references")
        elif self.reason == "ALLOWED" or any(value is not None for value in (*refs, self.application_deadline_event_id)) or self.evidence_ids:
            raise ValueError("unknown deferral cannot expose selected references")
        return self


class DeferralVerifier(Protocol):
    def __call__(self, query: DeferralQuery, bundle: DeferralBundle) -> bool: ...


def _input(model, value):
    try:
        if type(value) not in (dict, model):
            raise DeferralInputError()
        return model.model_validate(value)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise DeferralInputError() from None


def _result(reason, *, application="unknown", supplement="unknown", bundle=None):
    deadlines = (bundle.application_deadline, bundle.supplement_deadline) if bundle else ()
    evidence = set(bundle.policy_evidence_ids) if bundle else set()
    for deadline in deadlines:
        if deadline:
            evidence.update(deadline.evidence_ids)
    return DeferralResult(deferral_status="allowed" if bundle else "unknown", reason=reason,
        application_deadline_status=application, supplement_deadline_status=supplement,
        bundle_id=bundle.bundle_id if bundle else None, policy_id=bundle.policy_id if bundle else None,
        policy_version=bundle.policy_version if bundle else None,
        application_deadline_event_id=bundle.application_deadline.date_event.id if bundle and bundle.application_deadline else None,
        supplement_deadline_event_id=bundle.supplement_deadline.date_event.id if bundle else None,
        evidence_ids=tuple(sorted(evidence, key=str)))


def _matching(request, bundle):
    target, scope = request.target, bundle.scope
    if ((scope.dataset_id, scope.institution_id, scope.program_id, scope.country,
        bundle.offering_id, bundle.offering_version, bundle.scope_sha256) !=
        (target.dataset_id, target.institution_id, target.program_id, target.country,
        target.offering_id, target.offering_version, target.scope_sha256)):
        return "TARGET_MISMATCH"
    if scope.entry_year != request.entry_year:
        return "YEAR_MISMATCH"
    if bundle.stage != request.stage:
        return "STAGE_MISMATCH"
    if request.assessment_key not in bundle.assessment_keys:
        return "ITEM_NOT_ALLOWED"
    if (bundle.release_id, bundle.release_version, bundle.requirements_version, bundle.ruleset_version) != (
        request.release_id, request.release_version, request.requirements_version, request.ruleset_version):
        return "VERSION_MISMATCH"
    if bundle.ruleset_version is None:
        return "RULESET_UNAVAILABLE"
    if request.missing_state not in bundle.allowed_missing_states:
        return "MISSING_STATE_NOT_ALLOWED"
    if any(getattr(scope, name).status == "unknown" for name in (
        "degree", "course", "campus", "teaching_language", "progression_pathway", "intake",
        "application_cycle", "channel", "course_system", "pathway", "applicant_category", "province",
        "exam_system", "subject_scope", "batch_group")):
        return "SCOPE_UNKNOWN"
    if not bundle.valid_from <= request.assessment_at < bundle.valid_until:
        return "POLICY_EXPIRED"
    return None


def _deadline_status(request, bundle, binding, event_type):
    if binding is None:
        return "unknown", "DEADLINE_MISSING"
    event = binding.date_event
    if ((event.dataset_id, event.offering_id, event.offering_version, event.entry_year, event.is_synthetic, event.event_type) !=
        (bundle.scope.dataset_id, bundle.offering_id, bundle.offering_version, bundle.scope.entry_year,
         bundle.is_synthetic, event_type)):
        return "unknown", "DEADLINE_MISMATCH"
    if binding.reference_calendar is None or event.source_alignment == "conflict":
        return "unknown", "DEADLINE_UNCERTAIN"
    try:
        # Only an explicit call loads pinned package resources. No system
        # timezone/clock or applicant location substitutes for this calendar.
        from ..admissions_catalog.dates import _load_timezone
        zone = _load_timezone(binding.reference_calendar)
        if event.precision == "date" and event.conversion_status == "date_only":
            current = request.assessment_at.astimezone(zone).date()
            deadline = event.local_date
        elif (event.precision in {"minute", "second"} and event.conversion_status == "unique"
            and event.timezone == binding.reference_calendar and event.calculated_utc_instant is not None):
            current, deadline = request.assessment_at, event.calculated_utc_instant
        else:
            return "unknown", "DEADLINE_UNCERTAIN"
        if current < deadline:
            return "before", None
        if current > deadline:
            return "expired", "DEADLINE_EXPIRED"
        return "unknown", "DEADLINE_UNCERTAIN"
    except (ValueError, TypeError, OverflowError, OSError):
        return "unknown", "DEADLINE_UNCERTAIN"


def _deadlines(request, bundle):
    if request.stage == "application" and not bundle.application_deadline_required:
        return "unknown", "unknown", "DEADLINE_MISSING"
    if bundle.application_deadline_required:
        application, problem = _deadline_status(request, bundle, bundle.application_deadline, "application_deadline")
    else:
        application, problem = "not_applicable", None
    expected = "language_supplement" if request.assessment_key.startswith("ielts_") else "score_supplement"
    supplement, supplement_problem = _deadline_status(request, bundle, bundle.supplement_deadline, expected)
    return application, supplement, problem or supplement_problem


def evaluate_deferral(request, *, bundles=None, policy=None, verifier: DeferralVerifier | None = None) -> DeferralResult:
    """Check one necessary unresolved item; callers separately authorize it.

    Trusted local verifiers are not a Python sandbox. Their exact True proves
    only an explicitly synthetic current binding in this task, never formal
    review or an entire project's conditional/eligible outcome.
    """
    request = _input(DeferralRequest, request)
    policy = _input(DeferralPolicy, DeferralPolicy() if policy is None else policy)
    if not policy.enabled:
        return _result("POLICY_DISABLED")
    if not (policy.allow_test_bundles and policy.app_environment == "test" and policy.data_mode == "demo"):
        return _result("REAL_POLICIES_UNAVAILABLE")
    if bundles is None:
        return _result("POLICY_UNAVAILABLE")
    if type(bundles) not in (tuple, list) or len(bundles) > MAX_BUNDLES:
        return _result("INVALID_BUNDLE")
    try:
        current = tuple(_input(DeferralBundle, bundle) for bundle in bundles)
    except Exception:
        return _result("INVALID_BUNDLE")
    if not current:
        return _result("POLICY_UNAVAILABLE")
    if request.basis != "achieved":
        return _result("PREDICTED_NOT_ACHIEVED")
    if request.missing_state not in {"missing", "pending"}:
        return _result("MISSING_STATE_NOT_ALLOWED")
    if request.ruleset_version is None:
        return _result("RULESET_UNAVAILABLE")
    if any(not bundle.is_synthetic for bundle in current):
        return _result("SYNTHETIC_BOUNDARY")
    matches, outside, problems = [], [], []
    for bundle in current:
        problem = _matching(request, bundle)
        if problem in {"TARGET_MISMATCH", "YEAR_MISMATCH", "STAGE_MISMATCH", "ITEM_NOT_ALLOWED"}:
            outside.append(problem)
        elif problem:
            problems.append(problem)
        else:
            matches.append(bundle)
    if problems or not matches:
        choices = problems or outside
        for reason in ("RULESET_UNAVAILABLE", "VERSION_MISMATCH", "MISSING_STATE_NOT_ALLOWED", "SCOPE_UNKNOWN",
            "POLICY_EXPIRED", "ITEM_NOT_ALLOWED", "STAGE_MISMATCH", "YEAR_MISMATCH", "TARGET_MISMATCH"):
            if reason in choices:
                return _result(reason)
        return _result("POLICY_UNAVAILABLE")
    if verifier is None:
        return _result("VERIFIER_UNAVAILABLE")
    query = DeferralQuery(**{name: getattr(request, name) for name in DeferralQuery.model_fields})
    query_snapshot, policy_snapshot = query.model_dump(mode="json"), policy.model_dump(mode="json")
    request_snapshot = request.model_dump(mode="json")
    snapshots = tuple(bundle.model_dump(mode="json") for bundle in matches)
    try:
        for bundle in matches:
            verified = verifier(query, bundle)
            if type(verified) is not bool or not verified:
                return _result("BINDING_UNVERIFIED")
        if (_input(DeferralQuery, query).model_dump(mode="json") != query_snapshot
            or _input(DeferralPolicy, policy).model_dump(mode="json") != policy_snapshot
            or _input(DeferralRequest, request).model_dump(mode="json") != request_snapshot
            or any(_input(DeferralBundle, bundle).model_dump(mode="json") != original
                for bundle, original in zip(matches, snapshots, strict=True))):
            return _result("BINDING_UNVERIFIED")
    except Exception:
        return _result("VERIFIER_UNAVAILABLE")
    if any(snapshot != snapshots[0] for snapshot in snapshots[1:]):
        return _result("AMBIGUOUS_POLICIES")
    bundle = matches[0]
    application, supplement, problem = _deadlines(request, bundle)
    if problem:
        return _result(problem, application=application, supplement=supplement)
    return _result("ALLOWED", application=application, supplement=supplement, bundle=bundle)
