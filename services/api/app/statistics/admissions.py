from typing import Literal
from pydantic import model_validator
from .candidates import Candidate, Text, Value
from .cutoffs import ExamScope


class AdmissionObservation(Candidate):
    scope: ExamScope
    original_institution_code: Text
    code_version: Text
    grain: Literal["institution", "group", "program"]
    group_code: Text | None = None
    program_code: Text | None = None
    mapping_status: Literal["unresolved"] = "unresolved"
    metric_kind: Literal["filing_minimum", "admission_minimum", "admission_mean", "admission_rank", "single_subject_statistic"]
    value: Value | None
    unit: Literal["points", "rank"]
    max_score: Value | None = None
    missing_reason: Literal["not_published", "not_acquired", "ambiguous", "not_reported"] | None = None

    @model_validator(mode="after")
    def grain_and_unit(self):
        if (self.grain == "group" and (not self.group_code or self.program_code is not None)
                or self.grain == "program" and not self.program_code
                or self.grain == "institution" and (self.group_code is not None or self.program_code is not None)):
            raise ValueError("Exact reported grain required")
        if (self.metric_kind == "admission_rank") != (self.unit == "rank"):
            raise ValueError("Rank and points are different observations")
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("Missing value needs reason")
        if self.value is not None and self.unit == "rank" and (self.value < 1 or self.value != self.value.to_integral_value()):
            raise ValueError("Rank must be a positive integer")
        if self.max_score is not None and (self.unit != "points" or self.max_score <= 0 or self.value is not None and self.value > self.max_score):
            raise ValueError("Invalid points scale")
        return self
