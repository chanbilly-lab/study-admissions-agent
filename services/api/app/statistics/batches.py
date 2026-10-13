"""Small manual batch screening; no import, review, publication or fetching action."""
from typing import Literal
from pydantic import Field, model_validator
from ..admissions_catalog.schemas import CatalogModel, Identifier, _namespace
from .candidates import Year
from .coverage import DatasetType
from .regions import RegionScope


class BatchManifest(CatalogModel):
    batch_id: Identifier
    is_synthetic: bool = Field(strict=True)
    scope: RegionScope
    reference_year: Year
    dataset_type: DatasetType
    candidate_count: int = Field(strict=True, ge=0, le=200)
    expected_total: int | None = Field(default=None, strict=True, ge=1, le=10**8)
    source_refs: tuple[Identifier, ...] = Field(default=(), max_length=10)
    source_sha256: tuple[str | None, ...] = Field(default=(), max_length=10)
    permission_status: Literal["pending", "denied", "reported_granted"] = "pending"
    reviewer_ref: Identifier | None = None
    original_review_ref: Identifier | None = None
    quality_report_ref: Identifier | None = None

    @model_validator(mode="after")
    def exact_sources(self):
        import re
        _namespace(self.batch_id, self.is_synthetic)
        if len(self.source_refs) != len(self.source_sha256) or len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("Distinct source/hash pairs required")
        if any(value is not None and re.fullmatch(r"[0-9a-f]{64}", value) is None for value in self.source_sha256):
            raise ValueError("Source hash must describe acquired original bytes")
        if self.dataset_type in {"province_cutoff", "score_distribution"} and self.scope.pathway != "ordinary_gaokao":
            raise ValueError("Gaokao records need applicable scope")
        return self


def assess_batch(manifest: BatchManifest) -> dict:
    current = BatchManifest.model_validate(manifest)
    blockers = []
    if current.is_synthetic:
        blockers.append("SYNTHETIC_NOT_REAL_PUBLICATION")
    if not current.source_refs or any(value is None for value in current.source_sha256):
        blockers.append("ORIGINAL_BYTES_EVIDENCE_MISSING")
    if current.permission_status != "reported_granted":
        blockers.append("USE_PERMISSION_UNCONFIRMED")
    for key in ("reviewer_ref", "original_review_ref", "quality_report_ref"):
        if getattr(current, key) is None:
            blockers.append(key.upper() + "_MISSING")
    return {"batch_id": current.batch_id, "status": "blocked" if blockers else "needs_trusted_review_pipeline",
            "blockers": blockers, "candidate_count": current.candidate_count, "expected_total": current.expected_total,
            "coverage_ratio": None, "reviewed_count": None, "published_count": 0,
            "real_publication_authorized": False, "apply_supported": False, "national_collection_complete": False}
