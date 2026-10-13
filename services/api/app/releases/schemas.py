"""Bounded immutable release metadata; a DTO is not publication authority."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel, PositiveVersion
from ..evidence.schemas import _utc
from ..ingestion.schemas import _uuid


RELEASES_HEAD = "0001_releases_t19"
MAX_MEMBERS = 50
Hash = Annotated[str, Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
ReleaseKind = Literal["formal", "test_fixture"]
ReleaseState = Literal["published", "withdrawn", "replaced"]
WithdrawalReason = Literal["INCORRECT_FACT", "RIGHTS_REVOKED", "SOURCE_UNAVAILABLE", "ADMIN_REQUEST"]


class ReleasesError(ValueError):
    """Fixed safe codes, without keys, original values, paths or SQL details."""

    def __init__(self, status_code=503, code=None):
        codes = {422: "INVALID_RELEASE_INPUT", 404: "RELEASE_NOT_FOUND",
                 409: "RELEASE_CONFLICT", 503: "RELEASE_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


def _sequence(value):
    if type(value) not in (list, tuple) or not 1 <= len(value) <= MAX_MEMBERS:
        raise ValueError("an explicit bounded sequence of release members is required")
    return value


def _unique_members(members):
    if len({member.fact_id for member in members}) != len(members):
        raise ValueError("release facts must be distinct")
    return tuple(sorted(members, key=lambda member: str(member.fact_id)))


class PublishMember(CatalogModel):
    fact_id: UUID
    expected_case_revision: PositiveVersion
    expected_decision_id: UUID
    public_evidence: bool = Field(strict=True)

    @field_validator("fact_id", "expected_decision_id", mode="before")
    @classmethod
    def canonical_reference(cls, value):
        return _uuid(value)


class PublishRequest(CatalogModel):
    dataset_id: UUID
    expected_dataset_revision: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    kind: ReleaseKind
    valid_from: datetime = Field(strict=True)
    valid_until: datetime = Field(strict=True)
    members: tuple[PublishMember, ...] = Field(min_length=1, max_length=MAX_MEMBERS)
    replaces_release_id: UUID | None
    expected_replaced_state_revision: PositiveVersion | None

    @field_validator("dataset_id", "replaces_release_id", mode="before")
    @classmethod
    def canonical_reference(cls, value):
        return _uuid(value) if value is not None else None

    @field_validator("valid_from", "valid_until", mode="before")
    @classmethod
    def native_utc_interval(cls, value):
        return _utc(value)

    @field_validator("members", mode="before")
    @classmethod
    def explicit_members(cls, value):
        return _sequence(value)

    @field_validator("members")
    @classmethod
    def canonical_members(cls, value):
        return _unique_members(value)

    @model_validator(mode="after")
    def half_open_interval_and_replacement(self):
        if self.valid_from >= self.valid_until:
            raise ValueError("release validity requires a nonempty half-open UTC interval")
        if (self.replaces_release_id is None) != (self.expected_replaced_state_revision is None):
            raise ValueError("replacement requires its exact release and state revision")
        return self


class WithdrawalRequest(CatalogModel):
    release_id: UUID
    expected_state_revision: PositiveVersion
    reason_code: WithdrawalReason

    @field_validator("release_id", mode="before")
    @classmethod
    def canonical_reference(cls, value):
        return _uuid(value)


class ReleasePolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    real_releases_ready: bool = Field(default=False, strict=True)
    allow_test_releases: bool = Field(default=False, strict=True)


class ReleaseMemberData(CatalogModel):
    fact_id: UUID
    logical_key_hash: Hash
    decision_id: UUID
    case_revision: PositiveVersion
    offering_id: UUID
    offering_version: PositiveVersion
    entry_year: int = Field(strict=True, ge=1, le=9999)
    source_id: UUID
    source_version: PositiveVersion
    evidence_id: UUID
    fact_sha256: Hash
    scope_sha256: Hash
    evidence_sha256: Hash
    source_sha256: Hash
    file_sha256: Hash
    public_evidence: bool = Field(strict=True)

    @field_validator("fact_id", "decision_id", "offering_id", "source_id", "evidence_id", mode="before")
    @classmethod
    def canonical_reference(cls, value):
        return _uuid(value)


class ReleaseData(CatalogModel):
    release_id: UUID
    version: Literal[1]
    dataset_id: UUID
    entry_year: int = Field(strict=True, ge=1, le=9999)
    kind: ReleaseKind
    is_synthetic: bool = Field(strict=True)
    valid_from: datetime = Field(strict=True)
    valid_until: datetime = Field(strict=True)
    content_sha256: Hash
    requirements_version: Hash
    ruleset_version: None
    members: tuple[ReleaseMemberData, ...] = Field(min_length=1, max_length=MAX_MEMBERS)
    state: ReleaseState
    state_revision: PositiveVersion
    published_at: datetime = Field(strict=True)
    publisher_user_id: UUID
    replaces_release_id: UUID | None
    replaced_by_release_id: UUID | None
    replayed: bool = Field(strict=True)

    @field_validator("release_id", "dataset_id", "publisher_user_id", "replaces_release_id", "replaced_by_release_id", mode="before")
    @classmethod
    def canonical_reference(cls, value):
        return _uuid(value) if value is not None else None

    @field_validator("version", mode="before")
    @classmethod
    def strict_initial_release_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("a strict initial release version is required")
        return value

    @field_validator("valid_from", "valid_until", "published_at", mode="before")
    @classmethod
    def native_utc_timestamp(cls, value):
        return _utc(value)

    @field_validator("members", mode="before")
    @classmethod
    def explicit_members(cls, value):
        return _sequence(value)

    @field_validator("members")
    @classmethod
    def canonical_members(cls, value):
        members = _unique_members(value)
        if len({member.logical_key_hash for member in members}) != len(members):
            raise ValueError("a release contains only one chosen fact per logical group")
        return members

    @model_validator(mode="after")
    def coherent_server_snapshot(self):
        from .validation import _content_hash, requirements_snapshot_hash
        if self.valid_from >= self.valid_until or any(member.entry_year != self.entry_year for member in self.members):
            raise ValueError("member years and the nonempty UTC interval must be explicit")
        if (self.kind == "test_fixture") != self.is_synthetic:
            raise ValueError("formal and synthetic releases are separate")
        if self.replaces_release_id == self.release_id or self.replaced_by_release_id == self.release_id:
            raise ValueError("a release cannot replace itself")
        if (self.state == "replaced") != (self.replaced_by_release_id is not None):
            raise ValueError("only a replaced state has an explicit successor")
        if self.requirements_version != requirements_snapshot_hash(self.members) or self.content_sha256 != _content_hash(
            dataset_id=self.dataset_id, entry_year=self.entry_year, kind=self.kind,
            valid_from=self.valid_from, valid_until=self.valid_until, members=self.members,
            replaces_release_id=self.replaces_release_id,
        ):
            raise ValueError("release hashes must equal their bounded immutable snapshot")
        return self
