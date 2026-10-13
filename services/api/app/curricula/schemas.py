from typing import Literal
from pydantic import Field, model_validator
from ..admissions_catalog.schemas import CatalogModel, Identifier, _namespace
from ..statistics.candidates import Candidate, Year, Text, Value


class CurriculumModule(CatalogModel):
    original_code: Text
    name: Text
    kind: Literal["required", "optional", "practice", "unknown"]
    teaching_year: Year | None = None
    semester: int | None = Field(default=None, strict=True, ge=1, le=20)
    status: Literal["reported", "provisional"] = "reported"
    credits: Value | None = None
    hours: Value | None = None
    credits_missing_reason: Literal["ambiguous", "not_reported"] | None = None

    @model_validator(mode="after")
    def credits_definition(self):
        if (self.credits is None) != (self.credits_missing_reason is not None):
            raise ValueError("Unknown credits require reason")
        return self


class CurriculumVersion(Candidate):
    institution_ref: Identifier
    program_ref: Identifier
    campus_ref: Identifier | None = None
    entry_cohort: Year
    teaching_year: Year | None = None
    document_version: Text
    degree: Text | None = None
    duration_years: Value | None = None
    observed_year: Year
    graduation_requirements: Text | None = None
    modules: tuple[CurriculumModule, ...] = Field(default=(), max_length=200)

    @model_validator(mode="after")
    def references(self):
        for reference in (self.institution_ref, self.program_ref, self.campus_ref):
            if reference is not None:
                _namespace(reference, self.is_synthetic)
        if self.duration_years is not None and self.duration_years <= 0:
            raise ValueError("Duration must be positive when reported")
        if len({module.original_code for module in self.modules}) != len(self.modules):
            raise ValueError("Duplicate module code")
        if any(module.teaching_year is not None and module.teaching_year > self.observed_year and module.status != "provisional" for module in self.modules):
            raise ValueError("Future modules must remain provisional")
        return self
