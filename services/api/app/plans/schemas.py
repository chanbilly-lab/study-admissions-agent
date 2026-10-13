"""Bounded internal T30 drafts, without identity, database or scheduling IO."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel, Identifier, PositiveVersion, _identifier
from ..admissions_catalog.date_schemas import DateEventData
from ..api.v2.idempotency_canonical import canonical_request_hash
from ..evidence.schemas import _uuid
from ..profiles.schemas import DecimalText, decimal_text
from ..rules.adapters.schemas import Hash, RuleBundle, Stage, TargetReference
from ..rules.deferral import DeadlineBinding, DeferralBundle
from ..rules.expression import AssessmentKey, explicit_instant
from ..rules.schemas import AssessmentData, CurrentValidity, RuleReference

PLANS_HEAD = "0001_plans_t30"
SCHEMA_VERSION = GENERATOR_VERSION = "T30_v1"
MAX_TASKS = 100
MAX_ESTIMATE_OVERRIDES = 64
MAX_DEADLINES = 120
MAX_ESTIMATED_HOURS = 1000
PlanWarning = Literal["UNCONFIRMED_DRAFT", "NOT_SCHEDULED", "ESTIMATES_ARE_EDITABLE",
    "DEADLINE_SNAPSHOT_UNAVAILABLE", "HISTORICAL_RESULT_REQUIRES_REVIEW",
    "RULES_UNAVAILABLE", "NO_EDUCATIONAL_DIAGNOSIS"]
TaskAction = Literal["VERIFY_UNKNOWN", "REVIEW_INELIGIBLE", "PREPARE_MATERIALS",
    "OBTAIN_ACHIEVED", "RECHECK_CONDITIONS", "VERIFY_HISTORY", "SELF_DIRECTED_STUDY"]


class PlanError(ValueError):
    def __init__(self, status_code=503):
        codes = {422: "INVALID_PLAN_INPUT", 404: "PLAN_NOT_FOUND",
                 409: "PLAN_CONFLICT", 503: "PLAN_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes:
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


def assessment_fingerprint(payload):
    return canonical_request_hash({key: value for key, value in payload.items()
        if key not in {"result_sha256", "current_validity", "replayed"}})


def plan_draft_fingerprint(payload):
    return canonical_request_hash({key: value for key, value in payload.items() if key != "draft_sha256"})


def estimated_hours(value):
    if value is not None and Decimal(decimal_text(value)) > MAX_ESTIMATED_HOURS:
        raise ValueError("estimated work exceeds the supported bound")
    return value


def _sequence(value, maximum, *, minimum=0):
    if type(value) not in (tuple, list) or not minimum <= len(value) <= maximum:
        raise ValueError("a bounded native sequence is required")
    return value


def _ids(value, maximum=MAX_TASKS, *, minimum=0):
    current = tuple(_uuid(item) for item in _sequence(value, maximum, minimum=minimum))
    if len(set(current)) != len(current):
        raise ValueError("references must be unique")
    return current


def _text(value):
    if (type(value) is not str or not 1 <= len(value) <= 512 or not value.strip()
        or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError("bounded nonblank text is required")
    try:
        if len(value.encode("utf-8")) > 2048:
            raise ValueError("bounded text is required")
    except UnicodeError:
        raise ValueError("bounded text is required") from None
    return value


class PlanPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_drafts: bool = Field(default=False, strict=True)
    real_plans_ready: Literal[False] = False

    @field_validator("real_plans_ready", mode="before")
    @classmethod
    def real_closed(cls, value):
        if value is not False:
            raise ValueError("real plans are unavailable")
        return value


class StudyGoalInput(CatalogModel):
    goal_key: Identifier
    goal_text: str = Field(strict=True, min_length=1, max_length=512)
    estimated_hours: DecimalText | None

    _key = field_validator("goal_key")(_identifier)
    _text = field_validator("goal_text", mode="before")(_text)
    _hours = field_validator("estimated_hours", mode="before")(estimated_hours)


class EstimateOverride(CatalogModel):
    task_key: Hash
    estimated_hours: DecimalText | None

    _hours = field_validator("estimated_hours", mode="before")(estimated_hours)


class PlanCreateInput(CatalogModel):
    assessment_ids: tuple[UUID, ...] = Field(min_length=1, max_length=4)
    confirmed: Literal[True]
    study_goals: tuple[StudyGoalInput, ...] = Field(default=(), max_length=4)
    estimate_overrides: tuple[EstimateOverride, ...] = Field(default=(), max_length=MAX_ESTIMATE_OVERRIDES)

    @field_validator("confirmed", mode="before")
    @classmethod
    def exact_confirmation(cls, value):
        if value is not True:
            raise ValueError("target selection requires explicit confirmation")
        return value

    @field_validator("assessment_ids", mode="before")
    @classmethod
    def bounded_ids(cls, value):
        return _ids(value, 4, minimum=1)

    @field_validator("study_goals", "estimate_overrides", mode="before")
    @classmethod
    def bounded_options(cls, value, info):
        return _sequence(value, 4 if info.field_name == "study_goals" else MAX_ESTIMATE_OVERRIDES)

    @model_validator(mode="after")
    def unique_options(self):
        if (len({item.goal_key for item in self.study_goals}) != len(self.study_goals)
            or len({item.task_key for item in self.estimate_overrides}) != len(self.estimate_overrides)):
            raise ValueError("draft options must be unique")
        return self


class DraftBuildInput(CatalogModel):
    assessments: tuple[AssessmentData, ...] = Field(min_length=1, max_length=4)
    confirmed: Literal[True]
    generated_at: datetime = Field(strict=True)
    study_goals: tuple[StudyGoalInput, ...] = Field(default=(), max_length=4)
    estimate_overrides: tuple[EstimateOverride, ...] = Field(default=(), max_length=MAX_ESTIMATE_OVERRIDES)
    rule_bundles: tuple[RuleBundle, ...] = Field(default=(), max_length=4)
    deadline_bundles: tuple[DeferralBundle, ...] = Field(default=(), max_length=60)

    _confirmed = field_validator("confirmed", mode="before")(PlanCreateInput.exact_confirmation.__func__)
    _time = field_validator("generated_at", mode="before")(explicit_instant)

    @field_validator("assessments", "study_goals", "estimate_overrides", "rule_bundles", "deadline_bundles", mode="before")
    @classmethod
    def bounded_values(cls, value, info):
        maximum = {"assessments": 4, "study_goals": 4, "estimate_overrides": MAX_ESTIMATE_OVERRIDES,
                   "rule_bundles": 4, "deadline_bundles": 60}[info.field_name]
        _sequence(value, maximum, minimum=1 if info.field_name == "assessments" else 0)
        if info.field_name == "assessments":
            for item in value:
                if type(item) not in (dict, AssessmentData):
                    raise ValueError("an exact server assessment is required")
                raw = item if type(item) is dict else item.__dict__
                for name in ("assessment_at", "expires_at"):
                    explicit_instant(raw.get(name))
        return value

    @model_validator(mode="after")
    def exact_sources(self):
        first = self.assessments[0]
        binding = (first.profile_id, first.profile_version_id, first.profile_version,
                   first.profile_sha256, first.profile_is_synthetic, first.catalogue_is_synthetic)
        for item in self.assessments:
            if ((item.profile_id, item.profile_version_id, item.profile_version, item.profile_sha256,
                 item.profile_is_synthetic, item.catalogue_is_synthetic) != binding
                or assessment_fingerprint(item.model_dump(mode="json")) != item.result_sha256):
                raise ValueError("sources must match the same confirmed profile and original hashes")
            if not item.assessment_at <= self.generated_at < item.expires_at:
                raise ValueError("source assessment is outside its retained lifetime")
        if (len({item.assessment_id for item in self.assessments}) != len(self.assessments)
            or len({item.bundle_id for item in self.rule_bundles}) != len(self.rule_bundles)
            or len({item.bundle_id for item in self.deadline_bundles}) != len(self.deadline_bundles)
            or len({item.goal_key for item in self.study_goals}) != len(self.study_goals)
            or len({item.task_key for item in self.estimate_overrides}) != len(self.estimate_overrides)):
            raise ValueError("draft sources and options must be unique")
        return self


class PlanAssessmentRef(CatalogModel):
    assessment_id: UUID
    result_sha256: Hash
    target: TargetReference
    release_id: UUID
    requirements_version: Hash
    ruleset_version: Hash | None
    stage: Stage
    eligibility_status: Literal["eligible", "ineligible", "conditional", "unknown"]
    current_validity: CurrentValidity
    rule_refs: tuple[RuleReference, ...] = Field(max_length=1)


class PlanDeadlineRef(CatalogModel):
    deadline_key: Hash
    assessment_id: UUID
    assessment_key: AssessmentKey
    purpose: Literal["application", "supplement"]
    status: Literal["before", "expired", "unknown", "not_applicable"]
    bundle_id: UUID
    policy_id: UUID
    policy_version: Hash
    event_id: UUID | None
    evidence_ids: tuple[UUID, ...] = Field(min_length=1, max_length=96)
    date_event: DateEventData | None
    reference_calendar: str | None = Field(strict=True, min_length=1, max_length=100)

    @field_validator("date_event", mode="before")
    @classmethod
    def safe_date(cls, value):
        if value is not None:
            DeadlineBinding.safe_native_dates(value)
        return value

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def unique_evidence(cls, value):
        return _ids(value, 96, minimum=1)

    @model_validator(mode="after")
    def exact_deadline(self):
        if self.status == "not_applicable":
            if self.purpose != "application" or self.event_id is not None or self.date_event is not None or self.reference_calendar is not None:
                raise ValueError("only an explicitly inapplicable application event may be null")
        elif self.event_id is None:
            raise ValueError("a selected deadline needs its original event reference")
        if self.date_event is None:
            if self.reference_calendar is not None:
                raise ValueError("a calendar cannot be inferred without the original date event")
        elif (self.date_event.id != self.event_id or self.date_event.utc_instant is not None
              or self.date_event.event_type != ("application_deadline" if self.purpose == "application"
                  else "language_supplement" if self.assessment_key.startswith("ielts_") else "score_supplement")):
            raise ValueError("deadline event and purpose must match the original binding")
        if self.deadline_key != canonical_request_hash({key: value for key, value in self.model_dump(mode="json").items() if key != "deadline_key"}):
            raise ValueError("deadline content must match its key")
        return self


def task_fingerprint(payload):
    return canonical_request_hash({key: payload[key] for key in ("kind", "action_code", "title",
        "acceptance_criteria", "assessment_key", "basis", "unit", "scale", "work_scope_sha256")})


class DraftTask(CatalogModel):
    task_key: Hash
    kind: Literal["verify", "prepare", "study"]
    action_code: TaskAction
    title: str = Field(strict=True, min_length=1, max_length=512)
    acceptance_criteria: str = Field(strict=True, min_length=1, max_length=512)
    assessment_key: AssessmentKey | None
    basis: Literal["achieved"] | None
    unit: Literal["points", "band"] | None
    scale: DecimalText | None
    work_scope_sha256: Hash
    estimated_hours: DecimalText | None
    estimate_source: Literal["template", "user_adjusted", "unknown"]
    estimate_editable: Literal[True]
    assessment_ids: tuple[UUID, ...] = Field(max_length=4)
    dependency_keys: tuple[Hash, ...] = Field(max_length=60)
    deadline_keys: tuple[Hash, ...] = Field(max_length=MAX_DEADLINES)
    confirmed: Literal[False]

    _text = field_validator("title", "acceptance_criteria", mode="before")(_text)
    _hours = field_validator("estimated_hours", mode="before")(estimated_hours)
    _scale = field_validator("scale", mode="before")(lambda value: decimal_text(value) if value is not None else None)

    @field_validator("estimate_editable", "confirmed", mode="before")
    @classmethod
    def exact_flags(cls, value, info):
        if value is not (info.field_name == "estimate_editable"):
            raise ValueError("draft task flags must be exact")
        return value

    @field_validator("assessment_ids", mode="before")
    @classmethod
    def ids(cls, value):
        return _ids(value, 4)

    @field_validator("dependency_keys", "deadline_keys", mode="before")
    @classmethod
    def bounded_keys(cls, value, info):
        _sequence(value, 60 if info.field_name == "dependency_keys" else MAX_DEADLINES)
        if len(set(value)) != len(value):
            raise ValueError("task references must be unique")
        return value

    @model_validator(mode="after")
    def exact_task(self):
        kind = "study" if self.action_code == "SELF_DIRECTED_STUDY" else "prepare" if self.action_code in {"PREPARE_MATERIALS", "OBTAIN_ACHIEVED"} else "verify"
        if self.kind != kind or ((self.estimated_hours is None) != (self.estimate_source == "unknown")):
            raise ValueError("task action and estimated work must match their labels")
        if (self.unit is None) != (self.scale is None) or self.scale is not None and Decimal(self.scale) <= 0:
            raise ValueError("unit and positive scale must be coupled")
        if self.action_code == "OBTAIN_ACHIEVED":
            if self.assessment_key is None or self.basis != "achieved" or not self.assessment_ids:
                raise ValueError("completion preparation needs its exact achieved item")
        elif self.assessment_key is not None or self.basis is not None or self.unit is not None:
            raise ValueError("generic tasks cannot fabricate assessment requirements")
        if self.task_key in self.dependency_keys or self.task_key != task_fingerprint(self.model_dump(mode="json")):
            raise ValueError("task identity and dependencies must match its semantic content")
        return self


class PlanDraft(CatalogModel):
    schema_version: Literal["T30_v1"]
    generator_version: Literal["T30_v1"]
    status: Literal["draft"]
    confirmed: Literal[False]
    scheduled: Literal[False]
    profile_id: UUID
    profile_version_id: UUID
    profile_sha256: Hash
    is_synthetic: bool = Field(strict=True)
    generated_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)
    assessment_refs: tuple[PlanAssessmentRef, ...] = Field(min_length=1, max_length=4)
    tasks: tuple[DraftTask, ...] = Field(min_length=1, max_length=MAX_TASKS)
    deadline_refs: tuple[PlanDeadlineRef, ...] = Field(max_length=MAX_DEADLINES)
    warnings: tuple[PlanWarning, ...] = Field(max_length=7)
    draft_sha256: Hash

    _time = field_validator("generated_at", "expires_at", mode="before")(explicit_instant)

    @field_validator("confirmed", "scheduled", mode="before")
    @classmethod
    def exact_false(cls, value):
        if value is not False:
            raise ValueError("a draft cannot confirm or schedule itself")
        return value

    @model_validator(mode="after")
    def exact_draft(self):
        sources = {item.assessment_id for item in self.assessment_refs}
        tasks = {item.task_key: item for item in self.tasks}
        deadlines = {item.deadline_key: item for item in self.deadline_refs}
        if (self.generated_at >= self.expires_at or len(sources) != len(self.assessment_refs)
            or len(tasks) != len(self.tasks) or len(deadlines) != len(self.deadline_refs)
            or len(set(self.warnings)) != len(self.warnings)):
            raise ValueError("draft identities and retention must be exact")
        for item in self.deadline_refs:
            if item.assessment_id not in sources:
                raise ValueError("deadline references must belong to this draft")
        for item in self.tasks:
            if set(item.assessment_ids) - sources or set(item.dependency_keys) - tasks.keys() or set(item.deadline_keys) - deadlines.keys():
                raise ValueError("tasks must reference this draft's sources, dependencies and deadlines")
            if any(deadlines[key].assessment_id not in item.assessment_ids for key in item.deadline_keys):
                raise ValueError("each deadline must remain bound to its target task")
        visiting, done = set(), set()
        def visit(key):
            if key in visiting:
                raise ValueError("draft dependencies must be acyclic")
            if key in done:
                return
            visiting.add(key)
            for parent in tasks[key].dependency_keys:
                visit(parent)
            visiting.remove(key)
            done.add(key)
        for key in tasks:
            visit(key)
        if self.draft_sha256 != plan_draft_fingerprint(self.model_dump(mode="json")):
            raise ValueError("draft content must match its original hash")
        return self


class PlanData(CatalogModel):
    plan_id: UUID
    version_id: UUID
    version: PositiveVersion
    draft: PlanDraft
    audit_event_id: UUID
    created_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)

    _ids = field_validator("plan_id", "version_id", "audit_event_id", mode="before")(_uuid)
    _time = field_validator("created_at", "expires_at", mode="before")(explicit_instant)

    @model_validator(mode="after")
    def lifetime(self):
        if self.created_at != self.draft.generated_at or not self.created_at < self.expires_at <= self.draft.expires_at:
            raise ValueError("persisted draft times must match their server-derived bounds")
        return self
