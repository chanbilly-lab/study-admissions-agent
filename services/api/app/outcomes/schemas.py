from datetime import date
from typing import Literal
from pydantic import Field, field_validator, model_validator
from ..admissions_catalog.schemas import CatalogModel, Identifier, _namespace
from ..statistics.candidates import Candidate, Year, Text, Value


class Population(CatalogModel):
    level: Literal["institution", "college", "program", "discipline"]
    subject_ref: Identifier
    graduation_cohort: Year | None = None
    degree: Text | None = None
    study_mode: Text | None = None
    observation_start: date | None = None
    observation_end: date | None = None
    method: Text | None = None
    sample_definition: Text | None = None
    sample_count: int | None = Field(default=None, strict=True, ge=0, le=10**8)
    response_count: int | None = Field(default=None, strict=True, ge=0, le=10**8)
    denominator: int | None = Field(default=None, strict=True, ge=1, le=10**8)
    denominator_definition: Text | None = None

    @field_validator("observation_start", "observation_end", mode="before")
    @classmethod
    def explicit_calendar_date(cls, value):
        import re
        if value is None or type(value) is date:
            return value
        if type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            return date.fromisoformat(value)
        raise ValueError("Explicit original calendar date required")

    @model_validator(mode="after")
    def limits(self):
        if self.observation_start is not None and self.observation_end is not None and self.observation_end < self.observation_start:
            raise ValueError("Invalid observation window")
        if self.sample_count is not None and self.response_count is not None and self.response_count > self.sample_count:
            raise ValueError("Responses exceed invited sample")
        return self


class OutcomeMetric(CatalogModel):
    metric_id: Identifier
    kind: Literal["working", "further_study", "destination_confirmed", "salary"]
    population: Population
    definition: Text
    value: Value | None = None
    unit: Literal["percent", "people", "currency"]
    suppressed: bool = Field(default=False, strict=True)
    missing_reason: Literal["suppressed", "not_reported", "not_acquired", "ambiguous"] | None = None
    currency: str | None = Field(default=None, strict=True, pattern=r"^[A-Z]{3}$")
    salary_period: Literal["monthly", "annual", "hourly", "unknown"] = "unknown"
    tax_basis: Literal["gross", "net", "unknown"] = "unknown"

    @model_validator(mode="after")
    def metric_definition(self):
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("Missing metric needs reason")
        if self.suppressed and (self.value is not None or self.missing_reason != "suppressed"):
            raise ValueError("Suppressed value cannot be exposed")
        if (self.kind == "salary") != (self.unit == "currency"):
            raise ValueError("Salary has a separate unit")
        if self.value is not None and (self.unit == "percent" and self.value > 100 or self.unit == "people" and self.value != self.value.to_integral_value()):
            raise ValueError("Invalid reported metric unit")
        if self.kind != "salary" and (self.currency is not None or self.salary_period != "unknown" or self.tax_basis != "unknown"):
            raise ValueError("Salary definitions do not apply to other metrics")
        return self


class OutcomeReport(Candidate):
    publication_year: Year
    institution_ref: Identifier
    metrics: tuple[OutcomeMetric, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def exact_populations(self):
        _namespace(self.institution_ref, self.is_synthetic)
        if len({item.metric_id for item in self.metrics}) != len(self.metrics):
            raise ValueError("Duplicate metric")
        for item in self.metrics:
            _namespace(item.metric_id, self.is_synthetic)
            _namespace(item.population.subject_ref, self.is_synthetic)
        return self
