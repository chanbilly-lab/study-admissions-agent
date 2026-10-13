"""T03 isolated foundation wire contract, independent of M0 persisted facts."""

import re
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Meta(StrictModel):
    api_version: Literal["v2"]
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    data_as_of: None
    profile_version_id: None
    release_id: None
    ruleset_version: None
    profile_mode: None
    data_mode: Literal["demo", "verified"]
    model_mode: Literal["disabled", "mock"]


class FoundationConfig(StrictModel):
    api_version: Literal["v2"]
    schema_version: Literal["v2.t03"]
    contract_stage: Literal["foundation"]
    app_environment: Literal["development", "test", "production"]
    query_role: Literal["demo_only", "published_readonly"]
    data_mode: Literal["demo", "verified"]
    model_mode: Literal["disabled", "mock"]
    live_available: Literal[False]
    business_available: Literal[False]
    supported_scope: list[str] = Field(max_length=0)
    supported_province: None
    entry_year: None


class OfferingReference(StrictModel):
    id: str = Field(min_length=1)


class PageInfo(StrictModel):
    limit: int = Field(ge=1, le=100, strict=True)
    next_cursor: str | None = Field(min_length=1, max_length=512)
    has_more: bool = Field(strict=True)

    @model_validator(mode="after")
    def consistent_cursor(self):
        if self.next_cursor is not None and not self.next_cursor.strip():
            raise ValueError("next_cursor must not be blank")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("has_more must match next_cursor presence")
        return self


Item = TypeVar("Item")


class Page(StrictModel, Generic[Item]):
    items: list[Item]
    page: PageInfo

    @model_validator(mode="after")
    def bounded_items(self):
        if len(self.items) > self.page.limit:
            raise ValueError("items cannot exceed page.limit")
        return self


class Envelope(StrictModel, Generic[Item]):
    data: Item
    meta: Meta


class OfferingQuery(StrictModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("limit", mode="before")
    @classmethod
    def integer_parameter(cls, value):
        # Pydantic otherwise accepts strings such as "1.0" as integers.
        if isinstance(value, str) and not re.fullmatch(r"[+-]?[0-9]+", value):
            raise ValueError("limit must use integer syntax")
        if isinstance(value, bool):
            raise ValueError("limit must be an integer")
        return value


ErrorCode = Literal[
    "UNAUTHORIZED", "FORBIDDEN", "NOT_FOUND", "METHOD_NOT_ALLOWED",
    "CONFLICT", "VALIDATION_ERROR", "INVALID_CURSOR", "TOO_MANY_REQUESTS",
    "SERVICE_UNAVAILABLE", "INTERNAL_ERROR",
]


class ErrorDetail(StrictModel):
    field_path: str
    code: str
    message: str


class ErrorBody(StrictModel):
    code: ErrorCode
    message: str
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    details: list[ErrorDetail]


class ErrorEnvelope(StrictModel):
    error: ErrorBody
