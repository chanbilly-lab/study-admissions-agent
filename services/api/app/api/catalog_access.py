"""Fail-closed application catalog policy, without database roles or real facts."""

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CatalogAccessError(RuntimeError):
    def __init__(self):
        super().__init__("Catalog data is unavailable in this foundation")


class CatalogCandidate(BaseModel):
    """An internal policy descriptor; labels cannot establish publication."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always")
    id: str = Field(min_length=1, strict=True)
    dataset_id: str = Field(min_length=1, strict=True)
    data_mode: Literal["demo", "verified"]
    is_synthetic: bool = Field(strict=True)
    review_status: str = Field(min_length=1, strict=True)
    publication_status: str = Field(min_length=1, strict=True)
    withdrawn: bool = Field(strict=True)


class CatalogAccessPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    data_mode: Literal["demo", "verified"]

    @property
    def query_role(self) -> Literal["demo_only", "published_readonly"]:
        return "demo_only" if self.data_mode == "demo" else "published_readonly"

    @property
    def dataset_id(self) -> str:
        return "demo_catalog" if self.data_mode == "demo" else "verified_catalog"

    def read_foundation(self, candidates: Sequence[CatalogCandidate | Mapping]) -> list:
        """Check the whole candidate set; never return partially filtered rows."""
        try:
            for value in candidates:
                candidate = CatalogCandidate.model_validate(value)
                demo_identifier = candidate.id.upper().startswith("DEMO_")
                expected_review = "demo_reviewed" if self.data_mode == "demo" else "reviewed"
                if (candidate.dataset_id != self.dataset_id or candidate.data_mode != self.data_mode
                    or candidate.withdrawn or candidate.publication_status != "published"
                    or candidate.review_status != expected_review
                    or candidate.is_synthetic != (self.data_mode == "demo")
                    or demo_identifier != (self.data_mode == "demo")):
                    raise CatalogAccessError()
        except (ValidationError, TypeError):
            raise CatalogAccessError() from None
        # No release-backed storage exists yet. Even compliant labels cannot
        # supply genuine publication provenance, so only the empty set is usable.
        if candidates:
            raise CatalogAccessError()
        return []
