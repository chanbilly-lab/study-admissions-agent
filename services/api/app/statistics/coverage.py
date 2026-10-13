"""Pure 2026 coverage registration; unknown denominators are never zero."""

from typing import Annotated, Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from .regions import LOCAL_PATHWAYS, REGION_NAMES, Pathway, StrictCatalogModel

DATASET_TYPES = ("institution_directory", "province_cutoff", "score_distribution", "admission_statistics",
                 "admission_policy", "curriculum", "outcomes")
DatasetType = Literal["institution_directory", "province_cutoff", "score_distribution", "admission_statistics",
                      "admission_policy", "curriculum", "outcomes"]
Count = Annotated[StrictInt, Field(ge=0, le=1_000_000)]


def unit_pathway(region_key: str, dataset_type: str) -> str:
    if type(region_key) is not str or region_key not in REGION_NAMES or type(dataset_type) is not str or dataset_type not in DATASET_TYPES:
        raise ValueError("Unknown coverage scope")
    if dataset_type in {"institution_directory", "curriculum", "outcomes"}:
        return "institution_reference"
    if dataset_type in {"province_cutoff", "score_distribution"}:
        return "ordinary_gaokao"
    return LOCAL_PATHWAYS.get(region_key, "ordinary_gaokao")


class CoverageUnit(StrictCatalogModel):
    region_key: Annotated[str, Field(min_length=2, max_length=12)]
    reference_year: Literal[2026] = 2026
    dataset_type: DatasetType
    pathway: Pathway
    research_source_count: Count = 0
    pending_review_source_count: Count = 0
    synthetic_fixture_count: Count = 0
    reviewed_fact_count: Literal[0] = 0
    published_fact_count: Literal[0] = 0
    expected_total: Literal[None] = None
    coverage_ratio: Literal[None] = None
    missing_reason: Literal["not_collected", "source_candidate_only", "not_applicable"]
    collection_complete: Literal[False] = False

    @field_validator("reference_year", "reviewed_fact_count", "published_fact_count", mode="before")
    @classmethod
    def literal_integers(cls, value):
        if type(value) is not int:
            raise ValueError("Explicit integer required")
        return value

    @field_validator("collection_complete", mode="before")
    @classmethod
    def completion_boolean(cls, value):
        if type(value) is not bool:
            raise ValueError("Explicit boolean required")
        return value

    @model_validator(mode="after")
    def complete_scope(self):
        if self.pathway != unit_pathway(self.region_key, self.dataset_type):
            raise ValueError("Coverage pathway does not match exact region/type")
        if self.pending_review_source_count > self.research_source_count:
            raise ValueError("Pending source count exceeds registered research sources")
        inapplicable = self.region_key in LOCAL_PATHWAYS and self.dataset_type in {"province_cutoff", "score_distribution"}
        expected = "not_applicable" if inapplicable else "source_candidate_only" if self.research_source_count else "not_collected"
        if self.missing_reason != expected:
            raise ValueError("Missing reason conflicts with scope or source registration")
        if inapplicable and (self.research_source_count or self.pending_review_source_count or self.synthetic_fixture_count):
            raise ValueError("Inapplicable units cannot contain source or fixture counts")
        return self


def empty_matrix() -> tuple[CoverageUnit, ...]:
    return tuple(CoverageUnit(region_key=key, dataset_type=kind, pathway=unit_pathway(key, kind),
                             missing_reason="not_applicable" if key in LOCAL_PATHWAYS and kind in {"province_cutoff", "score_distribution"}
                             else "not_collected") for key in REGION_NAMES for kind in DATASET_TYPES)


def registration_summary(units: tuple[CoverageUnit, ...]) -> dict:
    if type(units) is not tuple or len(units) > 238 or any(type(value) is not CoverageUnit for value in units):
        raise ValueError("A bounded coverage registration is required")
    values = tuple(CoverageUnit.model_validate(value.model_dump()) for value in units)
    keys = tuple((row.region_key, row.dataset_type, row.reference_year, row.pathway) for row in values)
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate coverage scope")
    return {"registered_units": len(values), "registered_regions": len({row.region_key for row in values}),
            "research_source_references": sum(row.research_source_count for row in values),
            "pending_review_source_references": sum(row.pending_review_source_count for row in values),
            "synthetic_fixture_references": sum(row.synthetic_fixture_count for row in values),
            "reviewed_fact_count": 0, "published_fact_count": 0, "expected_total": None, "coverage_ratio": None,
            "collection_complete": False}
