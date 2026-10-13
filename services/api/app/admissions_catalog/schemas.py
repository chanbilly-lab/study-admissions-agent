"""T11 internal candidate identities and exact scopes, without published facts."""

import re
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_VERSION = 2_147_483_647
IDENTIFIER_MAX_LENGTH = 100
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:+-]*$"
Identifier = Annotated[str, Field(strict=True, min_length=1,
    max_length=IDENTIFIER_MAX_LENGTH, pattern=IDENTIFIER_PATTERN)]
PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=MAX_VERSION)]


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always",
        hide_input_in_errors=True, allow_inf_nan=False, validate_default=True)


def _identifier(value: str) -> str:
    # Full matching also rejects a trailing newline. Values are fixed ASCII keys,
    # not localized labels; this bounds the entire PostgreSQL composite index.
    if re.fullmatch(IDENTIFIER_PATTERN, value) is None:
        raise ValueError("a fixed ASCII identifier is required")
    return value


def _namespace(value: str, is_synthetic: bool) -> None:
    if (is_synthetic and not value.startswith("DEMO_")) or (
        not is_synthetic and value.upper().startswith("DEMO_")
    ):
        raise ValueError("namespace must match the synthetic marker")


class ScopeKey(CatalogModel):
    status: Literal["known", "unknown", "not_applicable"]
    value: Identifier | None

    @field_validator("value")
    @classmethod
    def exact_value(cls, value):
        return _identifier(value) if value is not None else None

    @model_validator(mode="after")
    def state_and_value(self):
        if (self.status == "known") != (self.value is not None):
            raise ValueError("known scopes need a value; other states require null")
        return self

    def canonical_key(self) -> str:
        current = type(self).model_validate(self)
        return "known:" + current.value if current.status == "known" else current.status

    @classmethod
    def from_canonical_key(cls, key: str) -> Self:
        if isinstance(key, str):
            if key in {"unknown", "not_applicable"}:
                return cls(status=key, value=None)
            if key.startswith("known:"):
                return cls(status="known", value=key[len("known:"):])
        raise ValueError("a canonical scope key is required")


class _IdentityInput(CatalogModel):
    reference_key: Identifier
    is_synthetic: bool = Field(strict=True)

    @field_validator("reference_key")
    @classmethod
    def exact_reference(cls, value):
        return _identifier(value)

    @model_validator(mode="after")
    def reference_namespace(self):
        _namespace(self.reference_key, self.is_synthetic)
        return self


class _NamedInput(_IdentityInput):
    name: str = Field(strict=True, min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def display_text(cls, value):
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ValueError("display name must be valid text") from None
        if not value.strip() or any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("display name must be nonblank text without controls")
        return value

    @model_validator(mode="after")
    def display_namespace(self):
        _namespace(self.name, self.is_synthetic)
        return self


class DatasetInput(_IdentityInput):
    id: UUID
    data_mode: Literal["demo", "verified"]
    visibility: Literal["private"] = "private"

    @model_validator(mode="after")
    def mode_namespace(self):
        if (self.data_mode == "demo") != self.is_synthetic:
            raise ValueError("dataset mode must match the synthetic marker")
        return self


class DatasetData(DatasetInput):
    revision: PositiveVersion


class InstitutionInput(_NamedInput):
    id: UUID
    dataset_id: UUID
    country: str = Field(strict=True, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")


class InstitutionData(InstitutionInput):
    pass


class ProgramInput(_NamedInput):
    id: UUID
    dataset_id: UUID
    institution_id: UUID
    study_level: Literal["undergraduate"]
    degree: ScopeKey
    course: ScopeKey
    campus: ScopeKey
    teaching_language: ScopeKey
    progression_pathway: ScopeKey


class ProgramData(ProgramInput):
    pass


class OfferingInput(_IdentityInput):
    id: UUID
    dataset_id: UUID
    program_id: UUID
    entry_year: int = Field(strict=True, ge=1, le=9999)
    intake: ScopeKey
    application_cycle: ScopeKey
    channel: ScopeKey
    course_system: ScopeKey
    pathway: ScopeKey
    applicant_category: ScopeKey
    province: ScopeKey
    exam_system: ScopeKey
    subject_scope: ScopeKey
    batch_group: ScopeKey


class OfferingData(OfferingInput):
    current_version: PositiveVersion


class OfferingVersionData(CatalogModel):
    id: UUID
    dataset_id: UUID
    offering_id: UUID
    version: PositiveVersion
    is_synthetic: bool = Field(strict=True)


class OfferingVersionRef(CatalogModel):
    dataset_id: UUID
    offering_id: UUID
    version: PositiveVersion
