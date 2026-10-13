"""M0 wire types. All input objects reject extra fields, including owner_id."""

from typing import Generic, Literal, TypeVar
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Score(StrictModel):
    value: float = Field(ge=0)
    scale: float = Field(gt=0)
    unit: Literal["points", "band"]
    kind: Literal["achieved", "predicted"]

    @model_validator(mode="after")
    def bounded(self):
        if self.value > self.scale:
            raise ValueError("value cannot exceed scale")
        return self


class ProfileInput(StrictModel):
    display_name: str = Field(min_length=1, max_length=80)
    is_synthetic: Literal[True]
    confirmed: Literal[True]
    study_level: Literal["bachelor"]
    course_system: Literal["gaokao"]
    entry_year: int = Field(ge=2026, le=2100)
    province: str = Field(min_length=1, max_length=30)
    applicant_category: Literal["cn_mainland"]
    subjects: list[str] = Field(max_length=8)
    assessments: dict[str, Score] = Field(max_length=12)
    weekly_hours: float = Field(gt=0, le=40)

    @field_validator("subjects")
    @classmethod
    def unique_subjects(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("subjects must be unique")
        return values

    @field_validator("assessments")
    @classmethod
    def supported_scores(cls, values):
        if set(values) - {"gaokao_total", "math", "english_language"}:
            raise ValueError("M0 assessment keys: gaokao_total, math, english_language")
        return values

    @field_validator("is_synthetic", "confirmed", mode="before")
    @classmethod
    def strict_true(cls, value):
        if value is not True:
            raise ValueError("must explicitly be true")
        return value


class Profile(ProfileInput):
    id: str
    version: int
    owner_id: str


ReviewStatus = Literal["demo_reviewed", "review_required", "conflicted", "expired"]


class Deferral(StrictModel):
    evidence_id: str
    deadline: str
    deadline_evidence_id: str

    @field_validator("deadline")
    @classmethod
    def calendar_date(cls, value):
        date.fromisoformat(value)
        return value


class Rule(StrictModel):
    id: str
    offering_id: str
    field: str
    op: Literal["gte", "eq", "in", "exists"]
    value: float | str | list[str] | None
    unit: str | None
    scale: float | None
    stage: Literal["application", "enrollment"]
    evidence_id: str
    review_status: ReviewStatus
    version: str
    deferral: Deferral | None


class Evidence(StrictModel):
    id: str
    offering_ids: list[str] = Field(min_length=1)
    title: str
    is_synthetic: Literal[True]
    source_url: str
    document_version_id: str
    document_sha256: str
    locator: str
    excerpt: str
    entry_year: int
    country: Literal["CN", "GB"]
    province: str | None
    applicant_category: Literal["cn_mainland"]
    pathway: Literal["gaokao", "uk_undergraduate"]
    review_status: ReviewStatus
    data_as_of: str

    @model_validator(mode="after")
    def synthetic_source(self):
        if not self.id.startswith("DEMO_") or not self.title.startswith("DEMO_"):
            raise ValueError("demo evidence identifiers and titles need DEMO_ prefix")
        if not self.source_url.startswith("demo://"):
            raise ValueError("synthetic evidence cannot claim an official source URL")
        return self


class Institution(StrictModel):
    id: str
    name: str
    country: Literal["CN", "GB"]
    is_synthetic: Literal[True]

    @model_validator(mode="after")
    def demo_names(self):
        if not self.id.startswith("DEMO_") or not self.name.startswith("DEMO_"):
            raise ValueError("institutions need DEMO_ prefix")
        return self


class Offering(StrictModel):
    id: str
    institution_id: str
    institution_name: str
    title: str
    is_synthetic: Literal[True]
    country: Literal["CN", "GB"]
    study_level: Literal["bachelor"]
    entry_year: int
    province: str | None
    applicant_category: Literal["cn_mainland"]
    course_system: Literal["gaokao"]
    pathway: Literal["gaokao", "uk_undergraduate"]
    deadline: str | None
    deadline_evidence_id: str | None
    deadline_status: Literal["known", "not_published"]
    rules: list[Rule]

    @model_validator(mode="after")
    def demo_names_and_dates(self):
        if any(not value.startswith("DEMO_") for value in (
            self.id, self.institution_id, self.institution_name, self.title
        )):
            raise ValueError("demo institutions and offerings need DEMO_ prefix")
        if self.deadline_status == "known":
            if self.deadline is None or self.deadline_evidence_id is None:
                raise ValueError("known deadline needs both date and evidence")
            date.fromisoformat(self.deadline)
        elif self.deadline is not None or self.deadline_evidence_id is not None:
            raise ValueError("not_published dates remain null")
        return self


class RuleResult(StrictModel):
    rule_id: str
    outcome: Literal["true", "false", "unknown", "deferred"]
    message: str
    evidence_ids: list[str]


EligibilityStatus = Literal["eligible", "ineligible", "conditional", "unknown"]


class Eligibility(StrictModel):
    id: str
    profile_version_id: str
    offering_id: str
    status: EligibilityStatus
    reasons: list[RuleResult]
    evidence_ids: list[str]
    missing_fields: list[str]
    conditions: list[str]
    competition_context: str
    preference_fit: str
    data_quality: list[str]
    ruleset_version: str


class DraftTask(StrictModel):
    id: str
    offering_id: str
    title: str
    estimated_hours: float
    acceptance_criteria: str
    dependencies: list[str]
    evidence_ids: list[str]
    hard_deadline_id: str | None
    target_date: str | None
    user_confirmed: Literal[False]


class PlanDraft(StrictModel):
    id: str
    profile_version_id: str
    status: Literal["draft"]
    is_synthetic: Literal[True]
    model_mode: Literal["mock", "live"]
    narrative: str
    tasks: list[DraftTask]
    warnings: list[str]
    eligibility_results: list[Eligibility]


class Meta(StrictModel):
    request_id: str
    data_as_of: str
    profile_version: int | None
    ruleset_version: str
    demo_mode: Literal[True]
    model_mode: Literal["mock", "live"]


T = TypeVar("T")


class Envelope(StrictModel, Generic[T]):
    data: T
    meta: Meta


class RuntimeConfig(StrictModel):
    supported_province: str
    demo_mode: Literal[True]
    model_mode: Literal["mock", "live"]
    entry_year: int
    live_available: Literal[False]


class CheckRequest(StrictModel):
    profile_version_id: str
    offering_ids: list[str] = Field(min_length=1, max_length=10)

    @field_validator("offering_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("offering_ids must be unique")
        return values
