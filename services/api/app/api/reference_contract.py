"""Closed empty-reference protocol; no records or publishable reader injection."""
from typing import Literal
import re
from pydantic import Field, field_validator, model_validator
from fastapi import Request
from ..admissions_catalog.schemas import CatalogModel, Identifier
from ..statistics.candidates import Text
from ..statistics.regions import REGION_NAMES
from .v2.schemas import Envelope, PageInfo
from .v2.router import foundation_meta
from .v2.errors import ApiError


class ReferenceQuery(CatalogModel):
    year: int = Field(ge=1, le=9999)
    region_key: Identifier | None = None
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=512)

    @field_validator("year", "limit", mode="before")
    @classmethod
    def decimal_integer(cls, value):
        if type(value) is str and re.fullmatch(r"[1-9][0-9]{0,3}", value):
            return int(value)
        if type(value) is not int:
            raise ValueError("Exact decimal integer required")
        return value

    @model_validator(mode="after")
    def known_region_cursor(self):
        if self.region_key is not None and self.region_key not in REGION_NAMES:
            raise ValueError("Unknown region")
        if self.cursor is not None:
            raise ValueError("No cursors issued by an empty dataset")
        return self


class StatisticalQuery(ReferenceQuery):
    region_key: Identifier
    pathway: Literal["ordinary_gaokao"] = "ordinary_gaokao"
    subject_category: Text | None = None
    batch: Text | None = None
    round: Text | None = None


class EmptyReferenceData(CatalogModel):
    schema_version: Literal["reference.minimal.1"] = "reference.minimal.1"
    resource: str = Field(max_length=32)
    filters: dict[str, str | int | None]
    items: tuple[()] = ()
    page: PageInfo
    release_id: None = None
    expected_total: None = None
    coverage_ratio: None = None
    missing_reason: Literal["source_not_enabled", "not_applicable", "scope_incomplete"]
    business_available: Literal[False] = False


def unique_parameters(request: Request):
    names = [key for key, _ in request.query_params.multi_items()]
    if len(names) != len(set(names)):
        raise ApiError(422, "VALIDATION_ERROR")


def empty_reference(request: Request, resource: str, query: ReferenceQuery, *, extra_filters=None):
    filters = query.model_dump(by_alias=True, exclude={"limit", "cursor"})
    filters.update(extra_filters or {})  # Server-constructed fixed path values only.
    reason = "source_not_enabled"
    if isinstance(query, StatisticalQuery):
        if query.region_key in {"hk", "mo", "tw"}:
            reason = "not_applicable"
        elif None in (query.subject_category, query.batch, query.round):
            reason = "scope_incomplete"
    return Envelope(data=EmptyReferenceData(resource=resource, filters=filters,
        page=PageInfo(limit=query.limit, next_cursor=None, has_more=False), missing_reason=reason), meta=foundation_meta(request))
