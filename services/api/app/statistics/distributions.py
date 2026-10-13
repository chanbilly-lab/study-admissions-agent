from typing import Literal
from pydantic import Field, model_validator
from ..admissions_catalog.schemas import CatalogModel
from .candidates import Candidate, Text, Value
from .cutoffs import ExamScope


class DistributionRow(CatalogModel):
    score: Value
    count: int = Field(strict=True, ge=1, le=10**8)
    cumulative: int = Field(strict=True, ge=1, le=10**8)


class ScoreDistribution(Candidate):
    scope: ExamScope
    direction: Literal["descending_inclusive"] = "descending_inclusive"
    population_definition: Text | None = None
    bonus_definition: Text | None = None
    max_score: Value | None = None
    total_people: int | None = Field(default=None, strict=True, ge=1, le=10**8)
    complete: bool = Field(default=False, strict=True)
    rows: tuple[DistributionRow, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def monotonic_counts(self):
        previous_score = previous_count = None
        for row in self.rows:
            if previous_score is not None and row.score >= previous_score:
                raise ValueError("Distinct descending scores required")
            if self.max_score is not None and (self.max_score <= 0 or row.score > self.max_score):
                raise ValueError("Score exceeds reported scale")
            if row.cumulative < row.count or previous_count is not None and row.cumulative < previous_count + row.count:
                raise ValueError("Cumulative count inconsistent")
            if self.complete and row.cumulative != (previous_count or 0) + row.count:
                raise ValueError("Complete table cannot omit counts")
            if self.total_people is not None and row.cumulative > self.total_people:
                raise ValueError("Population exceeded")
            previous_score, previous_count = row.score, row.cumulative
        if self.complete and (self.total_people is None or previous_count != self.total_people):
            raise ValueError("Complete table needs exact population")
        return self

    def tie_interval(self, score: Value) -> dict:
        current = ScoreDistribution.model_validate(self)
        if not current.complete or any(value is None for value in (self.population_definition, self.bonus_definition, self.max_score)):
            return {"status": "unknown", "rank_min": None, "rank_max": None, "reason": "incomplete_definition"}
        from pydantic import TypeAdapter
        selected = TypeAdapter(Value).validate_python(score)
        row = next((row for row in current.rows if row.score == selected), None)
        if row is None:
            return {"status": "unknown", "rank_min": None, "rank_max": None, "reason": "score_not_reported"}
        return {"status": "reported_tie_interval", "rank_min": row.cumulative - row.count + 1,
                "rank_max": row.cumulative, "reason": "population_scope_only_not_personal_order"}
