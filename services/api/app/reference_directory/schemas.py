"""Closed identity search and proof projections for SEARCH-SELECT-01."""

import re
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel, PositiveVersion
from ..api.v2.schemas import PageInfo
from ..evidence.schemas import _uuid


class DirectoryQuery(CatalogModel):
    q: str = Field(default="", strict=True, max_length=100)
    country: str | None = Field(default=None, strict=True, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    limit: int = Field(default=20, ge=1, le=20, strict=True)
    cursor: str | None = Field(default=None, strict=True, min_length=1, max_length=512)

    @field_validator("q")
    @classmethod
    def literal_text(cls, value):
        if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
            raise ValueError("A bounded plain search term is required")
        value.encode("utf-8")
        return value.strip()

    @field_validator("country")
    @classmethod
    def exact_country(cls, value):
        if value is not None and re.fullmatch(r"[A-Z]{2}", value) is None:
            raise ValueError("An uppercase country code is required")
        return value

    @field_validator("cursor")
    @classmethod
    def bounded_cursor(cls, value):
        if value is not None and re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
            raise ValueError("An opaque bounded cursor is required")
        return value


class ProgramDirectoryQuery(DirectoryQuery):
    institution_id: UUID

    @field_validator("institution_id", mode="before")
    @classmethod
    def exact_institution(cls, value):
        return _uuid(value)


class IdentityProof(CatalogModel):
    release_id: UUID
    offering_id: UUID
    offering_version: PositiveVersion
    identity_evidence_entry_year: int = Field(strict=True, ge=1, le=9999)
    requirements_version: str = Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

    @field_validator("release_id", "offering_id", mode="before")
    @classmethod
    def exact_identity(cls, value):
        return _uuid(value)


class InstitutionOption(CatalogModel):
    id: UUID
    name: str = Field(strict=True, min_length=1, max_length=200)
    country: str = Field(strict=True, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    is_synthetic: Literal[False] = False
    outcome_subject_ref: str = Field(strict=True, min_length=36, max_length=36)
    proof: IdentityProof

    @field_validator("id", mode="before")
    @classmethod
    def exact_identity(cls, value):
        return _uuid(value)

    @field_validator("name")
    @classmethod
    def real_name(cls, value):
        value.encode("utf-8")
        if (not value.strip() or value.lstrip().upper().startswith("DEMO_")
                or any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value)):
            raise ValueError("A real bounded published name is required")
        return value

    @field_validator("is_synthetic", mode="before")
    @classmethod
    def real_marker(cls, value):
        if value is not False:
            raise ValueError("Synthetic identities cannot be choices")
        return value

    @model_validator(mode="after")
    def subject_identity(self):
        if self.outcome_subject_ref != str(self.id):
            raise ValueError("The outcome reference must be the exact selected identity")
        return self


class ProgramOption(InstitutionOption):
    institution_id: UUID

    @field_validator("institution_id", mode="before")
    @classmethod
    def exact_parent(cls, value):
        return _uuid(value)


class DirectoryData(CatalogModel):
    schema_version: Literal["reference.directory.1"] = "reference.directory.1"
    resource: Literal["institutions", "programs"]
    filters: dict[str, str | None]
    items: tuple[InstitutionOption | ProgramOption, ...] = Field(default=(), max_length=20)
    page: PageInfo
    directory_available: bool = Field(strict=True)
    missing_reason: Literal["directory_not_enabled", "no_published_matches"] | None
    catalog_watermark: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    expected_total: None = None

    @model_validator(mode="after")
    def exact_projection(self):
        if set(self.filters) != {"q", "country", "institution_id"}:
            raise ValueError("Directory filters must be explicit")
        if self.resource == "institutions" and self.filters["institution_id"] is not None:
            raise ValueError("Institution choices have no requested parent")
        if self.resource == "programs" and self.filters["institution_id"] is None:
            raise ValueError("Programme choices need an explicit institution")
        if (self.page.limit > 20 or len(self.items) > self.page.limit
                or len({item.id for item in self.items}) != len(self.items)):
            raise ValueError("Choices must be bounded and have distinct identities")
        if not self.directory_available:
            if (self.items or self.page.has_more or self.catalog_watermark is not None
                    or self.missing_reason != "directory_not_enabled"):
                raise ValueError("Disabled directories cannot carry choices or cursors")
        elif self.catalog_watermark is None or (self.missing_reason != (None if self.items else "no_published_matches")):
            raise ValueError("Enabled directory results need a current watermark and an exact outcome")
        if not self.items and self.page.has_more:
            raise ValueError("An empty choice page cannot have another page")
        for item in self.items:
            if self.resource == "institutions" and type(item) is not InstitutionOption:
                raise ValueError("An institution page cannot contain programme choices")
            if self.resource == "programs" and (type(item) is not ProgramOption
                    or str(item.institution_id) != self.filters["institution_id"]):
                raise ValueError("Programme choices must match the exact parent")
            if self.filters["country"] is not None and item.country != self.filters["country"]:
                raise ValueError("Choices must match the requested country")
        return self


def filters_for(query: DirectoryQuery) -> dict:
    return {"q": query.q, "country": query.country,
            "institution_id": str(query.institution_id) if isinstance(query, ProgramDirectoryQuery) else None}


def disabled_data(resource, query: DirectoryQuery) -> DirectoryData:
    return DirectoryData(resource=resource, filters=filters_for(query),
        page=PageInfo(limit=query.limit, next_cursor=None, has_more=False), directory_available=False,
        missing_reason="directory_not_enabled", catalog_watermark=None)
