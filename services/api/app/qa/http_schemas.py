"""T39 finite public answers; provider claims and atom JSON stay internal."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ..model_gateway.schemas import AdviceCode, ModelScope, sequence
from ..public_catalog.schemas import DEMO_BANNER
from ..settings import V2RuntimeSettings
from .schemas import CitationData, Hash, QAModel, RetrievalRequest, UnknownReason


class QAV2RuntimeSettings(V2RuntimeSettings):
    data_mode: Literal["demo", "verified"] = "verified"
    model_mode: Literal["disabled", "mock", "live"] = "disabled"


class QAContextData(QAModel):
    schema_version: Literal["v2.t39"]
    can_ask: bool
    model_mode: Literal["disabled", "mock"]
    live_available: Literal[False]
    real_processing_enabled: Literal[False]
    allow_test_fixture_read: bool
    demo_banner: Literal[DEMO_BANNER] | None
    disabled_reason: Literal["MODEL_DISABLED", "QA_UNAVAILABLE", "BUDGET_UNAVAILABLE"] | None
    budget_unit: Literal["conservative_utf8_bytes"]

    @field_validator("live_available", "real_processing_enabled", mode="before")
    @classmethod
    def false_marker(cls, value):
        if value is not False:
            raise ValueError("closed capability required")
        return value

    @model_validator(mode="after")
    def capabilities(self):
        if self.can_ask != (self.disabled_reason is None):
            raise ValueError("capability and reason must agree")
        if self.can_ask and (self.model_mode != "mock" or not self.allow_test_fixture_read):
            raise ValueError("only an explicit offline fixture is available")
        if (self.demo_banner is not None) != self.allow_test_fixture_read:
            raise ValueError("fixture label must agree")
        return self


class QAAnswerData(QAModel):
    schema_version: Literal["v2.t39"]
    status: Literal["answered", "unknown"]
    request: RetrievalRequest
    model_scope: ModelScope | None
    release_version: Literal[1] | None
    requirements_version: Hash | None
    content_sha256: Hash | None
    citations: tuple[CitationData, ...] = Field(max_length=20)
    advice_codes: tuple[AdviceCode, ...] = Field(max_length=3)
    unknown_reasons: tuple[UnknownReason, ...] = Field(max_length=8)
    is_synthetic: bool | None
    model_mode: Literal["mock"]
    live_available: Literal[False]
    generated_at: datetime

    @field_validator("citations", "advice_codes", "unknown_reasons", mode="before")
    @classmethod
    def bounded_items(cls, value, info):
        return sequence(value, {"citations": 20, "advice_codes": 3, "unknown_reasons": 8}[info.field_name])

    @field_validator("release_version", mode="before")
    @classmethod
    def version(cls, value):
        if value is not None and (type(value) is not int or value != 1):
            raise ValueError("the publication version is explicit")
        return value

    @field_validator("live_available", mode="before")
    @classmethod
    def closed(cls, value):
        if value is not False:
            raise ValueError("live is closed")
        return value

    @field_validator("generated_at")
    @classmethod
    def utc_time(cls, value):
        if type(value) is not datetime or type(value.tzinfo) is not timezone or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("an explicit UTC timestamp is required")
        return value

    @model_validator(mode="after")
    def exact_answer(self):
        if (self.status == "answered") != bool(self.citations):
            raise ValueError("only referenced answers are returned")
        if len({item.id for item in self.citations}) != len(self.citations):
            raise ValueError("citations must be unique")
        if len(set(self.advice_codes)) != len(self.advice_codes) or len(set(self.unknown_reasons)) != len(self.unknown_reasons):
            raise ValueError("finite reasons must be unique")
        pins = (self.release_version, self.requirements_version, self.content_sha256, self.is_synthetic)
        if self.model_scope is None:
            if any(value is not None for value in pins) or self.citations or not self.unknown_reasons:
                raise ValueError("unavailable scope has no publication claims")
        else:
            if any(value is None for value in pins) or self.is_synthetic is not True:
                raise ValueError("the offline publication pins are required")
            if (self.model_scope.offering_id, self.model_scope.offering_version, self.model_scope.entry_year) != (
                self.request.offering_id, self.request.offering_version, self.request.entry_year):
                raise ValueError("scope must match the request")
            for citation in self.citations:
                if ((citation.release_id, citation.release_version, citation.requirements_version,
                     citation.offering_id, citation.offering_version, citation.entry_year, citation.is_synthetic) !=
                    (self.request.release_id, self.release_version, self.requirements_version,
                     self.request.offering_id, self.request.offering_version, self.request.entry_year, self.is_synthetic)
                    or citation.scope.dataset_id != self.model_scope.dataset_id
                    or citation.scope.model_dump(exclude={"dataset_id"}) != self.request.scope.model_dump()):
                    raise ValueError("all references must match the selected publication")
        return self
