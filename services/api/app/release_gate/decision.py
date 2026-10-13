from typing import Literal
from pydantic import Field, model_validator
from ..admissions_catalog.schemas import CatalogModel, Identifier

Gate = Literal["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "security", "restore", "monitoring", "capacity", "domain_review", "quality"]
REQUIRED = frozenset(("D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "security", "restore", "monitoring", "capacity", "domain_review", "quality"))


class EvidenceEntry(CatalogModel):
    gate: Gate
    status: Literal["missing", "not_run", "failed", "reported_pass"] = "missing"
    owner_ref: Identifier | None = None
    evidence_ref: Identifier | None = None
    source_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")

    @model_validator(mode="after")
    def required_evidence(self):
        if self.status == "reported_pass" and None in (self.owner_ref, self.evidence_ref, self.source_commit):
            raise ValueError("Reported pass needs owner and versioned evidence")
        return self


def assess(entries: tuple[EvidenceEntry, ...]) -> dict:
    if type(entries) is not tuple or len(entries) > len(REQUIRED):
        raise ValueError("Bounded gate list required")
    items = tuple(EvidenceEntry.model_validate(item) for item in entries)
    by_gate = {item.gate: item for item in items}
    if len(by_gate) != len(items):
        raise ValueError("Duplicate gate")
    blockers = sorted(gate for gate in REQUIRED if gate not in by_gate or by_gate[gate].status != "reported_pass")
    return {"status": "blocked" if blockers else "needs_independent_verification",
            "blockers": blockers, "reported_count": len(items), "required_count": len(REQUIRED),
            "ready": False, "deployed": False, "activation_supported": False}
