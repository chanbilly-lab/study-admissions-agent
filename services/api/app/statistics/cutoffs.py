from typing import Literal
from pydantic import model_validator
from .candidates import Candidate, Year, Text, Value
from .regions import RegionScope


class ExamScope(RegionScope):
    exam_year: Year
    subject_category: Text
    batch: Text
    round: Text
    reform_ref: Text | None = None

    @model_validator(mode="after")
    def ordinary_exam(self):
        if self.pathway != "ordinary_gaokao":
            raise ValueError("Ordinary gaokao scope required")
        return self


class Cutoff(Candidate):
    scope: ExamScope
    line_kind: Literal["undergraduate_control", "segment_first", "segment_second", "special_category", "other"]
    value: Value | None
    max_score: Value | None = None
    unit: Literal["points"] = "points"
    bonus_definition: Text | None = None
    original_value: Text | None = None
    missing_reason: Literal["not_published", "not_acquired", "ambiguous", "not_reported"] | None = None

    @model_validator(mode="after")
    def value_and_definition(self):
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("Missing values require a reason, not zero")
        if self.max_score is not None and (self.max_score <= 0 or self.value is not None and self.value > self.max_score):
            raise ValueError("Score exceeds reported scale")
        return self
