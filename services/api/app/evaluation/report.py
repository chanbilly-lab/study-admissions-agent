from typing import Literal
from pydantic import Field, model_validator
from ..admissions_catalog.schemas import CatalogModel, Identifier


class CaseReport(CatalogModel):
    case_id: Identifier
    status: Literal["not_run", "passed", "failed"] = "not_run"
    actual: str | None = Field(default=None, max_length=100)
    command: str | None = Field(default=None, max_length=300)
    source_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    evidence_ref: Identifier | None = None
    critical: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def evidence(self):
        if self.status == "not_run" and any(v is not None for v in (self.actual, self.command, self.source_commit, self.evidence_ref)):
            raise ValueError("Unexecuted result has no actual evidence")
        if self.status != "not_run" and (not self.actual or not self.command or not self.source_commit or not self.evidence_ref):
            raise ValueError("Executed result requires command, version and evidence")
        return self


def summarize(cases: tuple[CaseReport, ...], *, expected_ids: frozenset[str]) -> dict:
    if type(cases) is not tuple or not 1 <= len(cases) <= 100 or not expected_ids:
        raise ValueError("Bounded explicit report required")
    current = tuple(CaseReport.model_validate(case) for case in cases)
    ids = [case.case_id for case in current]
    if len(ids) != len(set(ids)) or set(ids) - expected_ids:
        raise ValueError("Duplicate or unknown case")
    failed = [case.case_id for case in current if case.status == "failed"]
    missing = sorted(expected_ids - set(ids))
    unexecuted = [case.case_id for case in current if case.status == "not_run"]
    return {"sample_count": len(expected_ids), "executed": sum(case.status != "not_run" for case in current),
            "passed": sum(case.status == "passed" for case in current), "failed_ids": failed,
            "not_run_ids": unexecuted, "missing_ids": missing,
            "reported_gate": "blocked" if failed or missing or unexecuted else "reported_pass",
            "manual_review_completed": False, "public_release_ready": False}
