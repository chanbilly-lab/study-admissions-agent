"""Bounded T35 contracts. Completion references never create completion credit."""

from datetime import date, datetime, time
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel
from ..api.v2.idempotency_canonical import canonical_request_hash
from ..evidence.schemas import _uuid
from ..plans.schemas import DraftTask, _sequence
from ..plans.schedule_schemas import ScheduleAllocation, TaskSchedule
from ..profiles.schemas import ProfileMeta
from ..rules.adapters.schemas import TargetReference
from ..rules.expression import explicit_instant

REVISIONS_HEAD = "0001_revisions_t35"
MAX_BODY_BYTES = 65536
MAX_SNAPSHOT_BYTES = 2097152
Hash = str
Version = int


class RevisionError(Exception):
    def __init__(self, status_code=503):
        self.status_code = status_code
        self.code = {422: "INVALID_REVISION_INPUT",404: "REVISION_NOT_FOUND",409: "REVISION_CONFLICT"}.get(status_code,"REVISION_UNAVAILABLE")
        super().__init__(self.code)


class RevisionPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_revisions: bool = Field(default=False, strict=True)
    real_revisions_ready: Literal[False] = False

    @field_validator("real_revisions_ready", mode="before")
    @classmethod
    def real_closed(cls, value):
        if value is not False:
            raise ValueError("real revisions are unavailable")
        return value


class ProposeInput(CatalogModel):
    old_plan_id: UUID
    new_plan_id: UUID
    expected_old_state_version: int = Field(strict=True, ge=1, le=2147483647)
    expected_new_state_version: int = Field(strict=True, ge=1, le=2147483647)
    student_confirmed: Literal[True]

    _ids = field_validator("old_plan_id","new_plan_id", mode="before")(_uuid)

    @field_validator("student_confirmed", mode="before")
    @classmethod
    def explicit(cls, value):
        if value is not True:
            raise ValueError("the student must explicitly confirm this action")
        return value

    @model_validator(mode="after")
    def distinct(self):
        if self.old_plan_id == self.new_plan_id:
            raise ValueError("different plans are required")
        return self


class DecisionInput(CatalogModel):
    expected_revision_version: int = Field(strict=True, ge=1, le=2)
    action: Literal["accept","reject"]
    student_confirmed: Literal[True]

    _explicit = field_validator("student_confirmed", mode="before")(ProposeInput.explicit.__func__)


class PlanPin(CatalogModel):
    plan_id: UUID
    source_plan_version_id: UUID
    state_version: int = Field(strict=True, ge=1, le=2147483647)
    state: Literal["draft","confirmed"]
    proposal_id: UUID
    proposal_state_version: int = Field(strict=True, ge=1, le=2147483647)
    source_draft_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    draft_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    schedule_sha256: str | None = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    profile_id: UUID
    profile_version_id: UUID
    profile_version: int = Field(strict=True, ge=1, le=2147483647)
    profile_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    confirmation_id: UUID | None
    is_synthetic: bool = Field(strict=True)

    _ids = field_validator("plan_id","source_plan_version_id","proposal_id","profile_id","profile_version_id",mode="before")(_uuid)
    _optional_id = field_validator("confirmation_id",mode="before")(lambda v: None if v is None else _uuid(v))

    @model_validator(mode="after")
    def state_pin(self):
        if self.proposal_state_version > self.state_version or ((self.state=="confirmed") != (self.confirmation_id is not None)):
            raise ValueError("the state and original confirmation must agree")
        return self


class CompletionReference(CatalogModel):
    completion_id: UUID
    confirmation_id: UUID
    task_key: str = Field(strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    completed_state_version: int = Field(strict=True, ge=3, le=2147483647)
    completed_at: datetime = Field(strict=True)
    source: Literal["student_declared"]

    _ids = field_validator("completion_id","confirmation_id",mode="before")(_uuid)
    _time = field_validator("completed_at",mode="before")(explicit_instant)


class RevisionSourceRef(CatalogModel):
    assessment_id: UUID
    result_sha256: str = Field(strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    target: TargetReference
    entry_year: int = Field(strict=True, ge=2000, le=2100)
    release_id: UUID
    requirements_version: str = Field(strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    ruleset_version: str | None = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    stage: Literal["application","enrollment"]
    original_eligibility_status: Literal["eligible","ineligible","conditional","unknown"]
    original_validity: Literal["current","unavailable","needs_review","withdrawn","replaced"]
    current_validity: Literal["unavailable","needs_review","withdrawn","replaced"]

    _ids = field_validator("assessment_id","release_id",mode="before")(_uuid)


class DeadlineReference(CatalogModel):
    deadline_key: str = Field(strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    assessment_id: UUID
    assessment_key: str = Field(strict=True, min_length=1, max_length=32)
    purpose: Literal["application","supplement"]
    status: Literal["before","expired","unknown","not_applicable"]
    event_id: UUID | None
    precision: Literal["date","minute","second","unknown"] | None
    local_date: date | None = Field(strict=True)
    local_time: time | None = Field(strict=True)
    timezone: str | None = Field(strict=True, max_length=100)
    reference_calendar: str | None = Field(strict=True, max_length=100)
    official_utc_instant: Literal[None]

    _id = field_validator("assessment_id",mode="before")(_uuid)
    _optional = field_validator("event_id",mode="before")(lambda v: None if v is None else _uuid(v))

    @model_validator(mode="after")
    def original_precision_fields(self):
        if self.precision in {None,"unknown"}:
            if any(value is not None for value in (self.local_date,self.local_time,self.timezone)):
                raise ValueError("unknown deadline precision has no date, time or timezone")
        elif self.precision=="date":
            if self.local_date is None or self.local_time is not None:
                raise ValueError("date precision has a date and no invented time")
        elif (self.local_date is None or self.local_time is None or self.local_time.tzinfo is not None
            or self.local_time.fold!=0 or self.local_time.microsecond!=0
            or (self.precision=="minute" and self.local_time.second!=0)):
            raise ValueError("precise deadlines retain the original native local time")
        return self


class HistoricalSchedule(CatalogModel):
    status: Literal["ready","partial","blocked"]
    generated_at: datetime = Field(strict=True)
    horizon_start: datetime = Field(strict=True)
    horizon_end: datetime = Field(strict=True)
    display_timezone: str = Field(strict=True, min_length=1, max_length=100)
    weekly_hours: str | None = Field(strict=True, max_length=64)
    constraints_complete: Literal[False]
    tasks: tuple[TaskSchedule,...] = Field(min_length=1,max_length=100)
    allocations: tuple[ScheduleAllocation,...] = Field(max_length=4096)

    _time = field_validator("generated_at","horizon_start","horizon_end",mode="before")(explicit_instant)
    _tasks = field_validator("tasks",mode="before")(lambda v: _sequence(v,100,minimum=1))
    _allocations = field_validator("allocations",mode="before")(lambda v: _sequence(v,4096))

    @field_validator("constraints_complete",mode="before")
    @classmethod
    def exact_false(cls,value):
        if value is not False:
            raise ValueError("official feasibility remains unverified")
        return value


class RevisionHistoryData(CatalogModel):
    schema_version: Literal["v2.t35"]
    pin: PlanPin
    tasks: tuple[DraftTask,...] = Field(min_length=1,max_length=100)
    sources: tuple[RevisionSourceRef,...] = Field(min_length=1,max_length=4)
    deadlines: tuple[DeadlineReference,...] = Field(max_length=120)
    schedule: HistoricalSchedule | None
    completion_refs: tuple[CompletionReference,...] = Field(max_length=100)
    created_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)
    current_actions: Literal[False]

    _time = field_validator("created_at","expires_at",mode="before")(explicit_instant)
    _false = field_validator("current_actions",mode="before")(HistoricalSchedule.exact_false.__func__)
    @field_validator("tasks","sources","deadlines","completion_refs",mode="before")
    @classmethod
    def bounded(cls,value,info):
        return _sequence(value,{"tasks":100,"sources":4,"deadlines":120,"completion_refs":100}[info.field_name],
                         minimum=1 if info.field_name in {"tasks","sources"} else 0)

    @model_validator(mode="after")
    def reference_integrity(self):
        tasks={t.task_key for t in self.tasks}
        if len(tasks)!=len(self.tasks) or len({r.assessment_id for r in self.sources})!=len(self.sources):
            raise ValueError("history references must be unique")
        if (not self.created_at<self.expires_at or len({c.completion_id for c in self.completion_refs})!=len(self.completion_refs)
            or len({c.task_key for c in self.completion_refs})!=len(self.completion_refs)
            or any(c.task_key not in tasks or c.confirmation_id!=self.pin.confirmation_id
                or c.completed_state_version>self.pin.state_version or not self.created_at<=c.completed_at<self.expires_at
                for c in self.completion_refs)):
            raise ValueError("original completions must belong to this exact retained plan")
        return self


ChangedField = Literal["profile_version","task_business","estimates","dependencies","deadlines","schedule","targets","source_references","source_business"]


class RevisionDiff(CatalogModel):
    changed_fields: tuple[ChangedField,...] = Field(min_length=1,max_length=9)
    business_changed: bool = Field(strict=True)
    diff_sha256: str = Field(strict=True,min_length=64,max_length=64,pattern="^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_hash(self):
        if len(set(self.changed_fields))!=len(self.changed_fields) or not self.business_changed:
            raise ValueError("a reviewable business or confirmed profile change is required")
        if self.diff_sha256!=canonical_request_hash(self.model_dump(mode="json",exclude={"diff_sha256"})):
            raise ValueError("the difference must match its hash")
        return self


class RevisionDecisionData(CatalogModel):
    decision_id: UUID
    action: Literal["accept","reject"]
    revision_version: Literal[2]
    decided_at: datetime = Field(strict=True)

    _id = field_validator("decision_id",mode="before")(_uuid)
    _time = field_validator("decided_at",mode="before")(explicit_instant)


class ReplacementData(CatalogModel):
    relationship_id: UUID
    old_plan_id: UUID
    new_plan_id: UUID
    accepted_at: datetime = Field(strict=True)
    new_plan_confirmed: Literal[False]
    completion_credit_transferred: Literal[False]

    _ids = field_validator("relationship_id","old_plan_id","new_plan_id",mode="before")(_uuid)
    _time = field_validator("accepted_at",mode="before")(explicit_instant)
    _false = field_validator("new_plan_confirmed","completion_credit_transferred",mode="before")(HistoricalSchedule.exact_false.__func__)


class RevisionData(CatalogModel):
    schema_version: Literal["v2.t35"]
    revision_id: UUID
    revision_version: int = Field(strict=True,ge=1,le=2)
    status: Literal["proposed","accepted","rejected"]
    old: RevisionHistoryData
    new: RevisionHistoryData
    diff: RevisionDiff
    decision: RevisionDecisionData | None
    replacement: ReplacementData | None
    created_at: datetime = Field(strict=True)
    expires_at: datetime = Field(strict=True)
    is_synthetic: bool = Field(strict=True)
    proposal_sha256: str = Field(strict=True,min_length=64,max_length=64,pattern="^[0-9a-f]{64}$")

    _id = field_validator("revision_id",mode="before")(_uuid)
    _time = field_validator("created_at","expires_at",mode="before")(explicit_instant)

    @model_validator(mode="after")
    def matching(self):
        a,b=self.old.pin,self.new.pin
        if (a.plan_id==b.plan_id or a.state!="confirmed" or b.state!="draft" or a.profile_id!=b.profile_id
            or a.is_synthetic!=b.is_synthetic or a.is_synthetic!=self.is_synthetic
            or not max(self.old.created_at,self.new.created_at)<=self.created_at<self.expires_at<=min(self.old.expires_at,self.new.expires_at)
            or self.new.completion_refs):
            raise ValueError("a suggestion binds the retained old confirmation and a distinct unconfirmed new draft")
        if self.decision is None:
            if self.status!="proposed" or self.revision_version!=1 or self.replacement is not None:
                raise ValueError("an undecided proposal has no accepted relationship")
        else:
            if (self.revision_version!=2 or self.status!={"accept":"accepted","reject":"rejected"}[self.decision.action]
                or not self.created_at<=self.decision.decided_at<self.expires_at):
                raise ValueError("a decision must match its immutable proposal")
            if (self.decision.action=="accept")!=(self.replacement is not None):
                raise ValueError("only acceptance establishes a replacement suggestion")
            if self.replacement is not None and (self.replacement.old_plan_id!=a.plan_id or self.replacement.new_plan_id!=b.plan_id
                or self.replacement.accepted_at!=self.decision.decided_at):
                raise ValueError("the relationship must match the accepted decision")
        if self.proposal_sha256!=proposal_fingerprint(self):
            raise ValueError("the original proposal snapshot must match its fingerprint")
        return self


def proposal_fingerprint(value):
    raw=value.model_dump(mode="json") if isinstance(value,RevisionData) else value
    return canonical_request_hash({k:raw[k] for k in ("revision_id","old","new","diff","created_at","expires_at","is_synthetic")})


class RevisionResult(CatalogModel):
    revision: RevisionData
    replayed: bool = Field(strict=True)


class RevisionContextData(CatalogModel):
    schema_version: Literal["v2.t35"]
    can_read_history: bool = Field(strict=True)
    can_propose: bool = Field(strict=True)
    can_decide: bool = Field(strict=True)
    reason: Literal["ready","processing_disabled"]
    is_synthetic: bool = Field(strict=True)


T=TypeVar("T")
class RevisionEnvelope(CatalogModel,Generic[T]):
    data:T
    meta:ProfileMeta

    @model_validator(mode="after")
    def exact_meta(self):
        value=self.data.revision if isinstance(self.data,RevisionResult) else self.data
        pin=value.new.pin if isinstance(value,RevisionData) else value.pin if isinstance(value,RevisionHistoryData) else None
        expected=(pin.profile_version_id,"synthetic" if pin.is_synthetic else "real") if pin is not None else (None,None)
        if (self.meta.profile_version_id,self.meta.profile_mode)!=expected:
            raise ValueError("metadata must bind the actual confirmed profile snapshot")
        return self
