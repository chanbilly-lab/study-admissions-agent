"""Exact scope and test-only rule binding contracts; none confer authority."""

from datetime import datetime
from hashlib import sha256
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ...admissions_catalog.schemas import CatalogModel, Identifier, PositiveVersion, ScopeKey, _identifier
from ...evidence.schemas import EvidenceScope, _uuid
from ..expression import Expr, explicit_instant, parse_expression

MAX_BUNDLES = 32
Hash = Annotated[str, Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
Stage = Literal["application", "enrollment"]
AdapterName = Literal["CN_GAOKAO", "UK_UNDERGRADUATE"]
SelectionReason = Literal["MATCHED", "POLICY_DISABLED", "MISSING_SCOPE",
    "UNSUPPORTED_COUNTRY", "UNSUPPORTED_COURSE", "UNSUPPORTED_APPLICANT", "UNSUPPORTED_PATHWAY",
    "PROVINCE_UNRECOGNIZED", "UK_YEAR_UNSUPPORTED", "RULESET_UNAVAILABLE", "REAL_RULES_UNAVAILABLE",
    "PROVIDER_UNAVAILABLE", "BINDING_UNVERIFIED", "VERIFIER_UNAVAILABLE", "SYNTHETIC_BOUNDARY",
    "TARGET_MISMATCH", "YEAR_MISMATCH", "STAGE_MISMATCH", "SCOPE_MISMATCH", "BUNDLE_EXPIRED",
    "AMBIGUOUS_RULESETS"]


class AdapterInputError(ValueError):
    status_code = 422
    code = "INVALID_ADAPTER_INPUT"

    def __init__(self):
        super().__init__("Adapter input is invalid")


def scope_fingerprint(scope):
    scope = EvidenceScope.model_validate(scope)
    encoded = json.dumps(scope.model_dump(mode="json"), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def expression_fingerprint(expression):
    current = parse_expression(expression)
    encoded = json.dumps(current.model_dump(mode="json"), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return sha256(encoded).hexdigest()


class TargetReference(CatalogModel):
    dataset_id: UUID
    institution_id: UUID
    program_id: UUID
    offering_id: UUID
    offering_version: PositiveVersion
    country: Literal["CN", "GB"]
    scope_sha256: Hash

    @field_validator("dataset_id", "institution_id", "program_id", "offering_id", mode="before")
    @classmethod
    def exact_identity(cls, value):
        return _uuid(value)

class ScopeRequest(CatalogModel):
    entry_year: int = Field(strict=True, ge=1, le=9999)
    study_level: Literal["bachelor"]
    residence_region: ScopeKey
    course_system: ScopeKey
    applicant_category: ScopeKey
    exam_province: ScopeKey
    pathway: ScopeKey
    target: TargetReference
    stage: Stage
    intake: ScopeKey | None
    application_cycle: ScopeKey | None
    channel: ScopeKey | None
    exam_system: ScopeKey | None
    subject_scope: ScopeKey | None
    batch_group: ScopeKey | None
    assessment_at: datetime = Field(strict=True)

    _time = field_validator("assessment_at", mode="before")(explicit_instant)


class BundleQuery(CatalogModel):
    target: TargetReference
    entry_year: int = Field(strict=True, ge=1, le=9999)
    stage: Stage


class AdapterPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_bundles: bool = Field(default=False, strict=True)
    real_adapters_ready: Literal[False] = False
    app_environment: Literal["development", "test", "production"] = "production"
    data_mode: Literal["demo", "verified"] = "verified"

    @field_validator("real_adapters_ready", mode="before")
    @classmethod
    def never_enable_real_rules(cls, value):
        if value is not False:
            raise ValueError("real adapters are not implemented")
        return value

    @model_validator(mode="after")
    def test_boundary(self):
        if self.allow_test_bundles and (self.app_environment != "test" or self.data_mode != "demo"):
            raise ValueError("test bundles require the explicit test/demo runtime")
        return self


class RuleBundle(CatalogModel):
    bundle_id: UUID
    reference_key: Identifier
    release_id: UUID
    release_version: PositiveVersion
    requirements_version: Hash
    ruleset_version: Hash | None
    is_synthetic: bool = Field(strict=True)
    scope: EvidenceScope
    scope_sha256: Hash
    offering_id: UUID
    offering_version: PositiveVersion
    stage: Stage
    valid_from: datetime = Field(strict=True)
    valid_until: datetime = Field(strict=True)
    expression: Expr
    expression_sha256: Hash
    fact_ids: tuple[UUID, ...] = Field(min_length=1, max_length=MAX_BUNDLES)
    evidence_ids: tuple[UUID, ...] = Field(min_length=1, max_length=MAX_BUNDLES)

    @field_validator("bundle_id", "release_id", "offering_id", mode="before")
    @classmethod
    def exact_identity(cls, value):
        return _uuid(value)

    @field_validator("reference_key")
    @classmethod
    def exact_reference(cls, value):
        return _identifier(value)

    _time = field_validator("valid_from", "valid_until", mode="before")(explicit_instant)

    @field_validator("expression", mode="before")
    @classmethod
    def bounded_full_tree(cls, value):
        return parse_expression(value)

    @field_validator("fact_ids", "evidence_ids", mode="before")
    @classmethod
    def exact_refs(cls, value):
        if type(value) not in (tuple, list) or not 1 <= len(value) <= MAX_BUNDLES:
            raise ValueError("a bounded explicit reference list is required")
        result = tuple(_uuid(item) for item in value)
        if len(set(result)) != len(result):
            raise ValueError("reference lists must be unique")
        return result

    @model_validator(mode="after")
    def exact_content(self):
        if self.valid_from >= self.valid_until:
            raise ValueError("the bundle window must be nonempty")
        if (self.is_synthetic and not self.reference_key.startswith("DEMO_")) or (
            not self.is_synthetic and self.reference_key.upper().startswith("DEMO_")):
            raise ValueError("the reference namespace must match its marker")
        if (self.scope_sha256 != scope_fingerprint(self.scope)
            or self.expression_sha256 != expression_fingerprint(self.expression)):
            raise ValueError("scope and expression hashes must describe the exact bundle")
        return self


class AdapterSelection(CatalogModel):
    selection_status: Literal["matched", "unknown", "unsupported"]
    reason: SelectionReason
    adapter: AdapterName | None
    bundle_id: UUID | None
    release_id: UUID | None
    requirements_version: Hash | None
    ruleset_version: Hash | None

    @model_validator(mode="after")
    def selected_refs_only(self):
        refs = (self.bundle_id, self.release_id, self.requirements_version, self.ruleset_version)
        if self.selection_status == "matched":
            if self.reason != "MATCHED" or self.adapter is None or any(value is None for value in refs):
                raise ValueError("matched selection needs all exact references")
        elif self.reason == "MATCHED" or any(value is not None for value in refs):
            raise ValueError("unavailable selection cannot expose selected references")
        return self
