from typing import Literal
from pydantic import Field, model_validator
from ..admissions_catalog.schemas import Identifier, _namespace
from .candidates import Candidate, Year, Text, Value
from .cutoffs import ExamScope


class PlanQuota(Candidate):
    scope: ExamScope
    institution_code: Text
    program_code: Text | None = None
    group_code: Text | None = None
    kind: Literal["initial", "executed", "remaining", "admitted", "enrolled"]
    people: int | None = Field(strict=True, ge=0, le=10**8)
    source_definition: Text
    missing_reason: Literal["not_reported", "ambiguous", "not_acquired"] | None = None

    @model_validator(mode="after")
    def missing(self):
        if (self.people is None) != (self.missing_reason is not None):
            raise ValueError("Unknown people is not zero")
        return self


class Fee(Candidate):
    institution_ref: Identifier
    program_ref: Identifier | None = None
    campus_ref: Identifier
    entry_year: Year
    applicant_category: Text
    kind: Literal["tuition", "accommodation", "application", "other"]
    amount: Value | None
    currency: str | None = Field(default=None, strict=True, pattern=r"^[A-Z]{3}$")
    period: Literal["per_year", "per_semester", "one_time", "unknown"] = "unknown"
    missing_reason: Literal["not_reported", "ambiguous", "not_acquired"] | None = None

    @model_validator(mode="after")
    def scope(self):
        for reference in (self.institution_ref, self.program_ref, self.campus_ref):
            if reference is not None:
                _namespace(reference, self.is_synthetic)
        if (self.amount is None) != (self.missing_reason is not None):
            raise ValueError("Missing amount needs reason")
        return self

    def total_cost(self) -> None:
        # One reported fee never defines attendance length, extras or exchange rate.
        return None
