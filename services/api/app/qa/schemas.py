"""Closed public retrieval projections; a content hash is never authority."""

import json
from datetime import date, datetime, time, timezone
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel, Identifier, PositiveVersion, ScopeKey
from ..evidence.schemas import EvidenceLocator, EvidenceScope
from ..model_gateway.schemas import EvidenceAtom, GatewayModel, ModelScope, identifier, sequence, text_value
from ..public_catalog.schemas import PublicDateData, PublicEvidenceData, PublicFactData

Hash = Annotated[str, Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
Intent = Literal["requirements", "materials", "dates", "fees", "background"]
UnknownReason = Literal["SCOPE_UNKNOWN", "RELEASE_UNAVAILABLE", "TARGET_MISMATCH", "NO_MATCHING_FACTS",
    "NO_PUBLIC_EVIDENCE", "VALUE_UNAVAILABLE", "DATE_UNRESOLVED", "LIMIT_EXCEEDED"]
SCOPE_FIELDS = tuple(name for name in EvidenceScope.model_fields if name not in {
    "dataset_id", "institution_id", "program_id", "country", "study_level", "entry_year"})
MAX_NATIVE_BYTES = 262144
MAX_NATIVE_NODES = 12000
MAX_NATIVE_DEPTH = 24


class ProjectionLimit(ValueError):
    """Finite output preflight; distinct from corrupt fields or proof errors."""


class QAError(ValueError):
    def __init__(self, status_code=503):
        codes = {422: "INVALID_RETRIEVAL_INPUT", 409: "CITATION_CONFLICT", 503: "QA_UNAVAILABLE"}
        self.status_code = status_code if type(status_code) is int and status_code in codes else 503
        self.code = codes[self.status_code]
        super().__init__(self.code)


def _native(value, *, budget=None, ancestors=None, depth=0):
    """Preflight bounded exact native input before old nested validators run."""
    budget = [0, 0] if budget is None else budget
    ancestors = set() if ancestors is None else ancestors
    budget[0] += 1
    if budget[0] > MAX_NATIVE_NODES or depth > MAX_NATIVE_DEPTH:
        raise ProjectionLimit("bounded public input is required")
    kind = type(value)
    if kind is str:
        if len(value) > MAX_NATIVE_BYTES - budget[1]:
            raise ProjectionLimit("bounded public input is required")
        budget[1] += len(value.encode("utf-8")) + 2
    elif kind is int:
        if not -9007199254740991 <= value <= 9007199254740991:
            raise ValueError("bounded integer is required")
        budget[1] += 20
    elif kind in {bool, type(None), UUID, date}:
        budget[1] += 40
    elif kind is datetime:
        if type(value.tzinfo) is not timezone or value.fold:
            raise ValueError("a native fixed-offset timestamp is required")
        budget[1] += 40
    elif kind is time:
        if value.tzinfo is not None or value.fold:
            raise ValueError("a native local clock time is required")
        budget[1] += 20
    else:
        nested = {EvidenceScope, ScopeKey, PublicFactData, PublicDateData, PublicEvidenceData,
                  EvidenceLocator, ModelScope, EvidenceAtom}
        if kind.__module__ == __name__ and issubclass(kind, QAModel) or kind in nested:
            value = dict(value.__dict__)
            kind = dict
        if kind not in {dict, list, tuple} or id(value) in ancestors:
            raise ValueError("a closed native object is required")
        if len(value) > 1024:
            raise ProjectionLimit("bounded public input is required")
        marker = id(value)
        ancestors.add(marker)
        try:
            if kind is dict:
                if any(type(key) is not str for key in value):
                    raise ValueError("native object keys are required")
                copied = {}
                for key, item in value.items():
                    _native(key, budget=budget, ancestors=ancestors, depth=depth + 1)
                    copied[key] = _native(item, budget=budget, ancestors=ancestors, depth=depth + 1)
                value = copied
            else:
                value = tuple(_native(item, budget=budget, ancestors=ancestors, depth=depth + 1) for item in value)
        finally:
            ancestors.remove(marker)
        return value
    if budget[1] > MAX_NATIVE_BYTES:
        raise ProjectionLimit("bounded public input is required")
    return value


class QAModel(CatalogModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always", strict=True,
        hide_input_in_errors=True, validate_default=True, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def exact_public_input(cls, value):
        if type(value) is cls:
            value = dict(value.__dict__)
        if type(value) is not dict:
            raise ValueError("a closed native object is required")
        return _native(value)


class QAPolicy(QAModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_fixture_read: bool = Field(default=False, strict=True)
    real_qa_ready: Literal[False] = False

    @field_validator("real_qa_ready", mode="before")
    @classmethod
    def closed_real_processing(cls, value):
        if value is not False:
            raise ValueError("real retrieval remains closed")
        return value


class RequestScope(QAModel):
    institution_id: UUID
    program_id: UUID
    country: str = Field(strict=True, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    study_level: Literal["undergraduate"]
    entry_year: int = Field(strict=True, ge=2000, le=2100)
    degree: ScopeKey
    course: ScopeKey
    campus: ScopeKey
    teaching_language: ScopeKey
    progression_pathway: ScopeKey
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

    _ids = field_validator("institution_id", "program_id", mode="before")(identifier)


class RetrievalRequest(QAModel):
    release_id: UUID
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=2000, le=2100)
    scope: RequestScope
    intent: Intent
    keywords: tuple[str, ...] = Field(default=(), max_length=5)

    _ids = field_validator("release_id", "offering_id", mode="before")(identifier)

    @field_validator("keywords", mode="before")
    @classmethod
    def literal_keywords(cls, value):
        items = sequence(value, 5)
        if any(type(item) is not str for item in items) or len(set(items)) != len(items):
            raise ValueError("distinct literal keywords are required")
        return tuple(text_value(item, 100) for item in items)

    @model_validator(mode="after")
    def exact_year(self):
        if self.scope.entry_year != self.entry_year:
            raise ValueError("the explicit request year must match its scope")
        return self


def fingerprint(value):
    if isinstance(value, (QAModel, CatalogModel, GatewayModel)):
        value = value.model_dump(mode="json")
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


def atom_value(fact):
    fact = PublicFactData.model_validate(_native(fact))
    value = json.dumps(fact.model_dump(mode="json", exclude={"evidence_id"}), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(value) > 2000:
        raise ProjectionLimit("the typed public atom exceeds the model boundary")
    return value


class CitationData(QAModel):
    id: UUID
    version: Literal[1]
    evidence_id: UUID
    release_id: UUID
    release_version: Literal[1]
    requirements_version: Hash
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=2000, le=2100)
    scope: EvidenceScope
    is_synthetic: bool = Field(strict=True)
    field_key: Identifier
    fact: PublicFactData
    evidence: PublicEvidenceData
    content_sha256: Hash

    _ids = field_validator("id", "evidence_id", "release_id", "offering_id", mode="before")(identifier)

    @field_validator("version", "release_version", mode="before")
    @classmethod
    def initial_versions(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("the exact fixed version is required")
        return value

    @model_validator(mode="after")
    def public_bindings(self):
        evidence = self.evidence
        if (self.field_key != self.fact.field_key or self.fact.evidence_id != self.evidence_id
            or self.scope != evidence.scope or self.scope.entry_year != self.entry_year
            or (evidence.evidence_id, evidence.release_id, evidence.release_version, evidence.requirements_version,
                evidence.offering_id, evidence.offering_version, evidence.entry_year, evidence.is_synthetic) !=
               (self.evidence_id, self.release_id, self.release_version, self.requirements_version,
                self.offering_id, self.offering_version, self.entry_year, self.is_synthetic)):
            raise ValueError("all public citation references must agree")
        digest = fingerprint(self.model_dump(mode="json", exclude={"id", "version", "content_sha256"}))
        if self.content_sha256 != digest or self.id != UUID(bytes=bytes.fromhex(digest)[:16], version=4):
            raise ValueError("the citation projection must bind its exact public content")
        atom_value(self.fact)
        return self


def citation_from_public(fact, evidence):
    fact = PublicFactData.model_validate(_native(fact))
    evidence = PublicEvidenceData.model_validate(_native(evidence))
    values = dict(evidence_id=evidence.evidence_id, release_id=evidence.release_id,
        release_version=evidence.release_version, requirements_version=evidence.requirements_version,
        offering_id=evidence.offering_id, offering_version=evidence.offering_version,
        entry_year=evidence.entry_year, scope=evidence.scope, is_synthetic=evidence.is_synthetic,
        field_key=fact.field_key, fact=fact, evidence=evidence)
    # First normalize the trusted public projections, including date precision.
    normalized = {name: item.model_dump(mode="json") if isinstance(item, CatalogModel) else
        str(item) if type(item) is UUID else item for name, item in values.items()}
    digest = fingerprint(normalized)
    return CitationData(id=UUID(bytes=bytes.fromhex(digest)[:16], version=4), version=1,
                        content_sha256=digest, **values)


class RetrievedBundle(QAModel):
    request: RetrievalRequest
    model_scope: ModelScope | None
    release_version: Literal[1] | None
    requirements_version: Hash | None
    content_sha256: Hash | None
    citations: tuple[CitationData, ...] = Field(max_length=20)
    atoms: tuple[EvidenceAtom, ...] = Field(max_length=20)
    unknown_reasons: tuple[UnknownReason, ...] = Field(max_length=8)
    retrieved_at: datetime
    is_synthetic: bool | None = Field(strict=True)
    pin_sha256: Hash

    @field_validator("retrieved_at", mode="before")
    @classmethod
    def server_utc(cls, value):
        if type(value) is not datetime or type(value.tzinfo) is not timezone or value.fold or value.utcoffset().total_seconds():
            raise ValueError("a native UTC server instant is required")
        return value

    @field_validator("release_version", mode="before")
    @classmethod
    def nullable_fixed_version(cls, value):
        if value is not None and (type(value) is not int or value != 1):
            raise ValueError("the exact fixed version is required")
        return value

    @model_validator(mode="after")
    def exact_bundle(self):
        if len(set(self.unknown_reasons)) != len(self.unknown_reasons):
            raise ValueError("unknown reasons must be distinct")
        if self.model_scope is None:
            if (self.citations or self.atoms or self.release_version is not None or self.requirements_version is not None
                or self.content_sha256 is not None or self.is_synthetic is not None or not self.unknown_reasons):
                raise ValueError("an unavailable release cannot invent current public pins")
        else:
            scope = self.model_scope
            if ((scope.offering_id, scope.offering_version, scope.entry_year) !=
                (self.request.offering_id, self.request.offering_version, self.request.entry_year)
                or self.release_version != 1 or self.requirements_version is None or self.content_sha256 is None
                or self.is_synthetic is None or len({item.id for item in self.citations}) != len(self.citations)):
                raise ValueError("the bundle must bind a single exact public target")
            expected = []
            for item in self.citations:
                if (item.release_id != self.request.release_id or item.scope.dataset_id != scope.dataset_id
                    or item.scope.model_dump(exclude={"dataset_id"}) != self.request.scope.model_dump()
                    or (item.offering_id, item.offering_version, item.entry_year, item.release_version,
                        item.requirements_version, item.is_synthetic) !=
                       (scope.offering_id, scope.offering_version, scope.entry_year, self.release_version,
                        self.requirements_version, self.is_synthetic)):
                    raise ValueError("citations must stay in the exact request scope")
                if item.fact.value_text is not None:
                    expected.append(EvidenceAtom(citation_id=item.id, version=1, scope=scope,
                        kind="date" if item.fact.fact_type == "date" else "number" if item.fact.value_kind == "decimal" else "text",
                        value=atom_value(item.fact), is_synthetic=item.is_synthetic))
            if tuple(expected) != self.atoms or not self.citations and not self.unknown_reasons:
                raise ValueError("model atoms must be the exact typed public projections")
        if self.pin_sha256 != fingerprint(self.model_dump(mode="json", exclude={"pin_sha256", "retrieved_at"})):
            raise ValueError("the bundle content pin must match its complete projection")
        return self


def bundle_from_public(request, *, model_scope=None, release_version=None, requirements_version=None,
        content_sha256=None, citations=(), unknown_reasons=(), retrieved_at, is_synthetic=None):
    request = RetrievalRequest.model_validate(request)
    citations = tuple(CitationData.model_validate(item) for item in sequence(citations, 20))
    atoms = tuple(EvidenceAtom(citation_id=item.id, version=1, scope=model_scope,
        kind="date" if item.fact.fact_type == "date" else "number" if item.fact.value_kind == "decimal" else "text",
        value=atom_value(item.fact), is_synthetic=item.is_synthetic)
        for item in citations if item.fact.value_text is not None)
    values = dict(request=request, model_scope=model_scope, release_version=release_version,
        requirements_version=requirements_version, content_sha256=content_sha256, citations=citations,
        atoms=atoms, unknown_reasons=tuple(unknown_reasons), retrieved_at=retrieved_at, is_synthetic=is_synthetic)
    # Test the complete projection before Pydantic wraps the dedicated quota
    # exception. Callers may represent this quota, but never arbitrary errors.
    _native(values)
    normalized = {name: value.model_dump(mode="json") if isinstance(value, (CatalogModel, GatewayModel)) else
        [item.model_dump(mode="json") if isinstance(item, (CatalogModel, GatewayModel)) else item for item in value]
        if type(value) in {list, tuple} else value for name, value in values.items() if name != "retrieved_at"}
    return RetrievedBundle(pin_sha256=fingerprint(normalized), **values)
