"""Finite read-only model data, deliberately separate from student services."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GatewayCode = Literal[
    "OK", "INVALID_MODEL_INPUT", "MODEL_DISABLED", "LIVE_UNAVAILABLE",
    "PRODUCTION_MODEL_DISABLED", "BUDGET_EXHAUSTED", "CONCURRENCY_LIMIT",
    "KEY_LIMIT", "BUDGET_UNAVAILABLE", "MODEL_TIMEOUT", "MODEL_CANCELLED",
    "INVALID_PROVIDER_RESPONSE", "PROVIDER_FAILURE",
]
AdviceCode = Literal["REVIEW_SOURCE", "CONFIRM_WITH_INSTITUTION", "MISSING_EVIDENCE"]


class GatewayError(Exception):
    def __init__(self, code: GatewayCode):
        statuses = {"INVALID_MODEL_INPUT":422, "BUDGET_EXHAUSTED":429,
            "CONCURRENCY_LIMIT":429, "KEY_LIMIT":429, "MODEL_TIMEOUT":504,
            "MODEL_CANCELLED":499, "INVALID_PROVIDER_RESPONSE":502, "PROVIDER_FAILURE":502}
        self.code = code if code in GatewayCode.__args__ and code != "OK" else "BUDGET_UNAVAILABLE"
        self.status_code = statuses.get(self.code,503)
        super().__init__(self.code)


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always",
        strict=True, hide_input_in_errors=True, validate_default=True, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def exact_object(cls, value):
        if type(value) is cls:
            return dict(value.__dict__)
        if type(value) is not dict:
            raise ValueError("a closed native object is required")
        return value


def identifier(value):
    if type(value) is str and len(value)==36:
        parsed=UUID(value)
        if str(parsed)!=value:
            raise ValueError("a canonical identifier is required")
        value=parsed
    if type(value) is not UUID or value.version!=4:
        raise ValueError("a version-four identifier is required")
    return value


def text_value(value, maximum, *, markup=True):
    if (type(value) is not str or not 1<=len(value)<=maximum or not value.strip()
        or any(ord(c)<32 and c not in "\n\t" or 127<=ord(c)<=159 for c in value)):
        raise ValueError("bounded text is required")
    value.encode("utf-8")
    if not markup and any(c in value for c in "<>"):
        raise ValueError("plain claim text is required")
    return value


def sequence(value, maximum):
    if type(value) not in {tuple,list} or len(value)>maximum:
        raise ValueError("a bounded native sequence is required")
    return tuple(value)


class GatewayPolicy(GatewayModel):
    app_environment: Literal["development","test","production"] = "development"
    data_mode: Literal["demo","verified"] = "verified"
    model_mode: Literal["disabled","mock","live"] = "disabled"

    @model_validator(mode="after")
    def mode_boundary(self):
        if self.data_mode=="verified" and self.model_mode=="mock":
            raise ValueError("verified data rejects mock")
        if self.app_environment=="production" and self.data_mode!="verified":
            raise ValueError("production requires verified data")
        return self


class ModelScope(GatewayModel):
    dataset_id: UUID
    entry_year: int = Field(ge=2000,le=2100)
    offering_id: UUID
    offering_version: int = Field(ge=1,le=2147483647)
    _ids=field_validator("dataset_id","offering_id",mode="before")(identifier)


class EvidenceAtom(GatewayModel):
    citation_id: UUID
    version: int = Field(ge=1,le=2147483647)
    scope: ModelScope
    kind: Literal["text","number","date"]
    value: str = Field(max_length=2000,repr=False)
    is_synthetic: bool
    _id=field_validator("citation_id",mode="before")(identifier)

    @field_validator("value",mode="before")
    @classmethod
    def bounded_value(cls,value):
        return text_value(value,2000)


class ModelRequest(GatewayModel):
    scope: ModelScope
    question: str = Field(max_length=1000,repr=False)
    evidence: tuple[EvidenceAtom,...] = Field(max_length=20,repr=False)

    @field_validator("question",mode="before")
    @classmethod
    def bounded_question(cls,value):
        return text_value(value,1000)

    @field_validator("evidence",mode="before")
    @classmethod
    def bounded_evidence(cls,value):
        return sequence(value,20)

    @model_validator(mode="after")
    def exact_scope(self):
        if any(atom.scope!=self.scope for atom in self.evidence):
            raise ValueError("all evidence must belong to the explicit scope")
        if len({atom.citation_id for atom in self.evidence})!=len(self.evidence):
            raise ValueError("citation identities must be distinct")
        return self


class Claim(GatewayModel):
    citation_id: UUID
    value: str = Field(max_length=2000,repr=False)
    _id=field_validator("citation_id",mode="before")(identifier)

    @field_validator("value",mode="before")
    @classmethod
    def plain_value(cls,value):
        return text_value(value,2000,markup=False)


class StructuredAnswer(GatewayModel):
    status: Literal["answered","unknown"]
    claims: tuple[Claim,...] = Field(max_length=20,repr=False)
    advice_codes: tuple[AdviceCode,...] = Field(max_length=3)

    @field_validator("claims","advice_codes",mode="before")
    @classmethod
    def finite_sequence(cls,value,info):
        return sequence(value,20 if info.field_name=="claims" else 3)

    @model_validator(mode="after")
    def coherence(self):
        if (self.status=="answered")!=bool(self.claims):
            raise ValueError("answer status and claims must agree")
        if len(set(self.advice_codes))!=len(self.advice_codes):
            raise ValueError("advice codes must be distinct")
        return self


class ProviderResponse(GatewayModel):
    answer: StructuredAnswer = Field(repr=False)
    input_usage: int = Field(ge=0,le=1000000)
    output_usage: int = Field(ge=0,le=1000000)
    is_synthetic: Literal[True]

    @field_validator("is_synthetic",mode="before")
    @classmethod
    def exact_marker(cls,value):
        if value is not True:
            raise ValueError("the offline response must be synthetic")
        return value


class BudgetKey(GatewayModel):
    key_id: UUID
    _id=field_validator("key_id",mode="before")(identifier)


class BudgetPolicy(GatewayModel):
    request_limit: int = Field(default=10,ge=1,le=10000)
    input_limit: int = Field(default=100000,ge=1,le=100000000)
    output_limit: int = Field(default=10000,ge=1,le=10000000)
    concurrency_limit: int = Field(default=2,ge=1,le=64)
    global_request_limit: int = Field(default=100,ge=1,le=100000)
    global_input_limit: int = Field(default=1000000,ge=1,le=1000000000)
    global_output_limit: int = Field(default=100000,ge=1,le=100000000)
    global_concurrency_limit: int = Field(default=4,ge=1,le=64)
    max_output_tokens: int = Field(default=512,ge=1,le=4096)
    timeout_ms: int = Field(default=1000,ge=1,le=60000)
    window_seconds: int = Field(default=60,ge=1,le=86400)
    max_keys: int = Field(default=128,ge=1,le=1024)
    history_limit: int = Field(default=256,ge=1,le=1024)


class UsageRecord(GatewayModel):
    reason: GatewayCode
    reserved_input_units: int = Field(ge=1)
    reserved_output_tokens: int = Field(ge=1)
    input_usage: int | None
    output_usage: int | None

    @model_validator(mode="after")
    def bounded_usage(self):
        if (self.input_usage is None)!=(self.output_usage is None):
            raise ValueError("usage is either complete or unavailable")
        if self.input_usage is not None and (not 0<=self.input_usage<=self.reserved_input_units
            or not 0<=self.output_usage<=self.reserved_output_tokens):
            raise ValueError("usage cannot exceed its reservation")
        if self.reason=="OK" and self.input_usage is None:
            raise ValueError("successful calls have validated usage")
        return self


class BudgetSnapshot(GatewayModel):
    requests: int = Field(ge=0)
    input_units: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    inflight: int = Field(ge=0)
    key_count: int = Field(ge=0)


def validate_request(value):
    try:
        return ModelRequest.model_validate(value)
    except Exception:
        raise GatewayError("INVALID_MODEL_INPUT") from None


def input_units(request):
    request=validate_request(request)
    # Offline accounting deliberately uses UTF-8 bytes of the complete finite
    # provider DTO, not vendor tokenization or a supplier's lower usage report.
    return len(request.model_dump_json().encode("utf-8"))
