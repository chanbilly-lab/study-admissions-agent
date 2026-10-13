"""Bounded release comparison snapshots, never current publication authority."""

from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ..admissions_catalog.date_schemas import ConversionStatus, EventType, Precision
from ..admissions_catalog.schemas import CatalogModel, Identifier, PositiveVersion, _identifier
from ..evidence.schemas import EvidenceScope, SnippetData
from ..facts.schemas import (
    ClaimKind, Period, StatisticsBasis, TypedCandidate, UnitCode, _bounded_context,
)
from ..ingestion.schemas import MissingReason, _text, _uuid
from ..releases.schemas import Hash, ReleaseData, ReleaseMemberData


CHANGES_HEAD = "0001_changes_t34"
MAX_MEMBERS = 50
MAX_GROUPS = 100
EventTypeName = Literal["published", "replaced", "withdrawn"]
FactType = Literal["requirement", "score", "fee", "material", "date", "statistic"]
BusinessField = Literal[
    "value_kind", "value", "unit", "classification", "missing_reason", "footnote",
    "scope", "date", "public_evidence", "association",
]
ReleaseField = Literal["validity", "ruleset", "availability"]
ImpactReason = Literal[
    "MEMBER_ADDED", "MEMBER_REMOVED", "BUSINESS_CHANGED", "RELEASE_WINDOW_CHANGED",
    "RULESET_CHANGED", "RELEASE_WITHDRAWN", "REFERENCE_REPLACED",
]


class ChangesError(ValueError):
    def __init__(self, status_code=503, code=None):
        codes = {422: "INVALID_CHANGE_INPUT", 404: "CHANGE_NOT_FOUND",
                 409: "CHANGE_CONFLICT", 503: "CHANGE_UNAVAILABLE"}
        if type(status_code) is not int or status_code not in codes or (code is not None and code != codes[status_code]):
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        super().__init__(self.code)


def _sequence(value, maximum, *, minimum=0):
    if type(value) not in (tuple, list) or not minimum <= len(value) <= maximum:
        raise ValueError("an explicit bounded sequence is required")
    return value


def _native_utc(value):
    # Inspect the tzinfo type before invoking any callback supplied by it.
    if (type(value) is not datetime or type(value.tzinfo) is not timezone or value.fold):
        raise ValueError("a native unambiguous server timestamp is required")
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise ValueError("a representable server timestamp is required") from None


def fingerprint(value) -> str:
    """Exactly the T19 compact JSON fingerprint, without importing its store."""
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _values(value):
    if type(value) is dict:
        return value
    if isinstance(value, CatalogModel):
        return value.__dict__
    raise ValueError("a fixed snapshot model or plain object is required")


def _snapshot_time_guards(fact, evidence):
    for value in (fact, evidence):
        fields = _values(value)
        _native_utc(fields.get("created_at"))
    date_value = _values(fact).get("date_resolution")
    if date_value is not None:
        fields = _values(date_value)
        if fields.get("calculated_utc_instant") is not None:
            _native_utc(fields["calculated_utc_instant"])


class ChangesPolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    allow_test_changes: bool = Field(default=False, strict=True)
    real_changes_ready: Literal[False] = False

    @field_validator("real_changes_ready", mode="before")
    @classmethod
    def real_gate_closed(cls, value):
        if value is not False:
            raise ValueError("real changes processing is unavailable")
        return value


class PublishedMember(CatalogModel):
    release_member: ReleaseMemberData
    fact: TypedCandidate
    evidence: SnippetData

    @model_validator(mode="before")
    @classmethod
    def native_snapshot_times(cls, value):
        fields = _values(value)
        _snapshot_time_guards(fields.get("fact"), fields.get("evidence"))
        return value

    @model_validator(mode="after")
    def exact_fixed_snapshot(self):
        member, fact, evidence = self.release_member, self.fact, self.evidence
        if (member.fact_id != fact.id or member.evidence_id != evidence.id or fact.evidence_id != evidence.id
            or (member.offering_id, member.offering_version, member.entry_year) !=
               (fact.offering_id, fact.offering_version, fact.entry_year)
            or (fact.offering_id, fact.offering_version, fact.entry_year, fact.is_synthetic) !=
               (evidence.offering_id, evidence.offering_version, evidence.entry_year, evidence.is_synthetic)
            or evidence.scope.dataset_id != fact.dataset_id
            or member.fact_sha256 != fingerprint(fact.model_dump(mode="json"))
            or member.evidence_sha256 != fingerprint(evidence.model_dump(mode="json"))
            or member.scope_sha256 != fingerprint(evidence.scope.model_dump(mode="json"))
            or member.file_sha256 != evidence.document_sha256):
            raise ValueError("release member identity, full scope and snapshot fingerprints must agree")
        return self


class ReleaseSnapshot(CatalogModel):
    release: ReleaseData
    members: tuple[PublishedMember, ...] = Field(min_length=1, max_length=MAX_MEMBERS)

    @model_validator(mode="before")
    @classmethod
    def native_release_times(cls, value):
        fields = _values(value)
        release = _values(fields.get("release"))
        for name in ("valid_from", "valid_until", "published_at"):
            _native_utc(release.get(name))
        return value

    @field_validator("members", mode="before")
    @classmethod
    def finite_members(cls, value):
        return _sequence(value, MAX_MEMBERS, minimum=1)

    @model_validator(mode="after")
    def exact_release_members(self):
        members = tuple(sorted(self.members, key=lambda value: str(value.fact.id)))
        if tuple(value.release_member for value in members) != self.release.members or any(
            value.fact.dataset_id != self.release.dataset_id
            or value.fact.entry_year != self.release.entry_year
            or value.fact.is_synthetic != self.release.is_synthetic
            or value.fact.created_at > self.release.published_at
            or value.evidence.created_at > self.release.published_at for value in members
        ):
            raise ValueError("captured members must exactly equal the immutable release")
        object.__setattr__(self, "members", members)
        return self


class BusinessClassification(CatalogModel):
    claim_kind: ClaimKind
    unit_code: UnitCode
    period: Period
    statistics_basis: StatisticsBasis
    statistic_population: str | None = Field(strict=True, min_length=1, max_length=512)
    statistic_denominator: str | None = Field(strict=True, min_length=1, max_length=512)
    cohort_year: int | None = Field(strict=True, ge=1, le=9999)
    survey_period: str | None = Field(strict=True, min_length=1, max_length=100)

    @field_validator("statistic_population", "statistic_denominator")
    @classmethod
    def bounded_statistics(cls, value):
        return _bounded_context(value, 512) if value is not None else None

    @field_validator("survey_period")
    @classmethod
    def bounded_period(cls, value):
        return _bounded_context(value, 100) if value is not None else None


class BusinessDate(CatalogModel):
    event_type: EventType
    original_text: str = Field(strict=True, min_length=1, max_length=4000)
    precision: Precision
    local_date: date | None = Field(strict=True)
    local_time: time | None = Field(strict=True)
    timezone: str | None = Field(strict=True, min_length=1, max_length=100)
    source_alignment: Literal["pending", "conflict"]
    conversion_status: ConversionStatus
    calculated_utc_instant: datetime | None = Field(strict=True)
    utc_instant: None
    tzdata_version: Literal["2026.4"]

    @field_validator("local_date", mode="before")
    @classmethod
    def native_calendar(cls, value):
        if value is not None and type(value) is not date:
            raise ValueError("a native date is required")
        return value

    @field_validator("local_time", mode="before")
    @classmethod
    def native_clock(cls, value):
        if value is not None and (type(value) is not time or value.tzinfo is not None or value.fold or value.microsecond):
            raise ValueError("a native original clock component is required")
        return value

    @field_validator("calculated_utc_instant", mode="before")
    @classmethod
    def native_candidate(cls, value):
        return _native_utc(value) if value is not None else None

    @model_validator(mode="after")
    def explicit_precision_and_candidate(self):
        if self.precision == "unknown":
            if any(value is not None for value in (self.local_date, self.local_time, self.timezone)):
                raise ValueError("unknown precision has no inferred local components")
        elif self.local_date is None or self.precision == "date" and self.local_time is not None:
            raise ValueError("date precision must preserve its explicit calendar date")
        elif self.precision in {"minute", "second"} and (self.local_time is None
                or self.precision == "minute" and self.local_time.second != 0):
            raise ValueError("time precision must preserve its explicit clock components")
        if ((self.conversion_status == "unique") != (self.calculated_utc_instant is not None)
            or self.source_alignment == "conflict" and self.conversion_status != "source_conflict"):
            raise ValueError("calculated candidate state cannot become an official instant")
        return self


class BusinessProjection(CatalogModel):
    value_kind: Literal["text", "decimal"]
    value_text: str | None = Field(strict=True, min_length=1, max_length=4096)
    normalized_value: str | None = Field(strict=True, min_length=1, max_length=4096)
    unit: str | None = Field(strict=True, min_length=1, max_length=4096)
    classification: BusinessClassification
    missing_reason: MissingReason | None
    footnote_state: Literal["present", "none", "unknown"]
    footnote_text: str | None = Field(strict=True, min_length=1, max_length=4096)
    scope: EvidenceScope
    date_resolution: BusinessDate | None
    public_evidence: bool = Field(strict=True)

    @field_validator("value_text", "normalized_value", "unit", "footnote_text")
    @classmethod
    def bounded_text(cls, value):
        return _text(value) if value is not None else None

    @model_validator(mode="after")
    def original_and_canonical_values(self):
        from ..facts.typing import normalize_decimal
        if ((self.value_text is None) != (self.missing_reason is not None)
            or (self.footnote_state == "present") != (self.footnote_text is not None)):
            raise ValueError("explicit missing and footnote states must agree")
        expected = normalize_decimal(self.value_text) if self.value_kind == "decimal" and self.value_text is not None else self.value_text
        if self.normalized_value != expected:
            raise ValueError("normalized value must preserve the exact original value")
        return self


class MemberDiff(CatalogModel):
    kind: Literal["added", "removed", "changed", "unchanged"]
    offering_id: UUID
    fact_type: FactType
    field_key: Identifier
    before_fact_ids: tuple[UUID, ...] = Field(max_length=MAX_MEMBERS)
    after_fact_ids: tuple[UUID, ...] = Field(max_length=MAX_MEMBERS)
    before: tuple[BusinessProjection, ...] = Field(max_length=MAX_MEMBERS)
    after: tuple[BusinessProjection, ...] = Field(max_length=MAX_MEMBERS)
    before_references: tuple[ReleaseMemberData, ...] = Field(max_length=MAX_MEMBERS)
    after_references: tuple[ReleaseMemberData, ...] = Field(max_length=MAX_MEMBERS)
    changed_fields: tuple[BusinessField, ...] = Field(max_length=10)
    reference_changed: bool = Field(strict=True)
    semantic_business_changed: bool = Field(strict=True)

    @field_validator("offering_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value)

    @field_validator("field_key")
    @classmethod
    def fixed_key(cls, value):
        return _identifier(value)

    @field_validator("before_fact_ids", "after_fact_ids", "before", "after", "before_references", "after_references", mode="before")
    @classmethod
    def finite_group(cls, value):
        return _sequence(value, MAX_MEMBERS)

    @field_validator("changed_fields", mode="before")
    @classmethod
    def finite_fields(cls, value):
        return _sequence(value, 10)

    @model_validator(mode="after")
    def coherent_group(self):
        from .comparator import _FIELDS, _multiset, _semantic
        for ids, references, projections in ((self.before_fact_ids, self.before_references, self.before),
                                            (self.after_fact_ids, self.after_references, self.after)):
            if (len(ids) != len(projections) or ids != tuple(value.fact_id for value in references)
                or len(set(ids)) != len(ids) or any(value.offering_id != self.offering_id for value in references)):
                raise ValueError("each bounded group must preserve its exact member references")
            if any(reference.scope_sha256 != fingerprint(projection.scope.model_dump(mode="json"))
                   or reference.entry_year != projection.scope.entry_year
                   for reference, projection in zip(references, projections)):
                raise ValueError("each member reference must retain its complete original scope")
        if not self.before and not self.after or len(set(self.changed_fields)) != len(self.changed_fields):
            raise ValueError("a group needs members and distinct change fields")
        old, new = tuple(map(_semantic, self.before)), tuple(map(_semantic, self.after))
        changed = _multiset(old) != _multiset(new)
        fields = tuple(field for field in _FIELDS if _multiset(value[field] for value in old) !=
                       _multiset(value[field] for value in new))
        if changed and not fields:
            fields = ("association",)
        expected = "added" if not self.before else "removed" if not self.after else "changed" if changed else "unchanged"
        if self.kind != expected or self.semantic_business_changed != changed or self.changed_fields != fields:
            raise ValueError("group kind and business change markers must agree")
        return self


class BusinessDiff(CatalogModel):
    event_type: EventTypeName
    before_release_id: UUID | None
    after_release_id: UUID | None
    dataset_id: UUID
    entry_year: int = Field(strict=True, ge=1, le=9999)
    is_synthetic: bool = Field(strict=True)
    release_changed_fields: tuple[ReleaseField, ...] = Field(max_length=3)
    member_diffs: tuple[MemberDiff, ...] = Field(max_length=MAX_GROUPS)
    semantic_business_changed: bool = Field(strict=True)
    reference_changed: bool = Field(strict=True)

    @model_validator(mode="before")
    @classmethod
    def finite_release_totals_before_walk(cls, value):
        groups = _sequence(_values(value).get("member_diffs"), MAX_GROUPS, minimum=1)
        before_count = after_count = 0
        for group in groups:
            fields = _values(group)
            before_count += len(_sequence(fields.get("before"), MAX_MEMBERS))
            after_count += len(_sequence(fields.get("after"), MAX_MEMBERS))
            if before_count > MAX_MEMBERS or after_count > MAX_MEMBERS:
                raise ValueError("each release side has at most its bounded original members")
        return value

    @field_validator("before_release_id", "after_release_id", "dataset_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value) if value is not None else None

    @field_validator("member_diffs", mode="before")
    @classmethod
    def finite_groups(cls, value):
        return _sequence(value, MAX_GROUPS)

    @field_validator("release_changed_fields", mode="before")
    @classmethod
    def finite_fields(cls, value):
        return _sequence(value, 3)

    @model_validator(mode="after")
    def coherent_event(self):
        present = (self.before_release_id is not None, self.after_release_id is not None)
        if present != {"published": (False, True), "replaced": (True, True), "withdrawn": (True, False)}[self.event_type]:
            raise ValueError("event references must have the exact before and after shape")
        keys = {(item.offering_id, item.fact_type, item.field_key) for item in self.member_diffs}
        if len(keys) != len(self.member_diffs) or len(set(self.release_changed_fields)) != len(self.release_changed_fields):
            raise ValueError("change groups and release fields must be distinct")
        if self.semantic_business_changed != bool(self.release_changed_fields or any(item.semantic_business_changed for item in self.member_diffs)):
            raise ValueError("release business marker must equal its bounded changes")
        if any(projection.scope.dataset_id != self.dataset_id or projection.scope.entry_year != self.entry_year
               for item in self.member_diffs for projection in (*item.before, *item.after)):
            raise ValueError("all projected scopes must belong to the exact release dataset and year")
        for name in ("before_fact_ids", "after_fact_ids"):
            ids = tuple(reference for item in self.member_diffs for reference in getattr(item, name))
            if len(ids) != len(set(ids)):
                raise ValueError("an exact fact appears only once on each release side")
        return self


class ChangeProcessingData(CatalogModel):
    event_id: UUID
    event_type: EventTypeName
    payload_sha256: Hash
    processed_at: datetime
    assessment_count: int = Field(strict=True, ge=0)
    plan_count: int = Field(strict=True, ge=0)
    replayed: bool = Field(strict=True)

    @field_validator("event_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value)

    @field_validator("processed_at", mode="before")
    @classmethod
    def native_time(cls, value):
        return _native_utc(value)


class ChangeImpactData(CatalogModel):
    event_id: UUID
    assessment_id: UUID
    plan_id: UUID | None
    before_release_id: UUID | None
    after_release_id: UUID | None
    needs_review: bool = Field(strict=True)
    reasons: tuple[ImpactReason, ...] = Field(min_length=1, max_length=7)
    offering_id: UUID
    entry_year: int = Field(strict=True, ge=1, le=9999)
    created_at: datetime

    @field_validator("event_id", "assessment_id", "plan_id", "before_release_id", "after_release_id", "offering_id", mode="before")
    @classmethod
    def canonical_identity(cls, value):
        return _uuid(value) if value is not None else None

    @field_validator("created_at", mode="before")
    @classmethod
    def native_time(cls, value):
        return _native_utc(value)

    @field_validator("reasons", mode="before")
    @classmethod
    def finite_reasons(cls, value):
        return _sequence(value, 7, minimum=1)

    @model_validator(mode="after")
    def explicit_reasons(self):
        if len(set(self.reasons)) != len(self.reasons) or self.before_release_id is None and self.after_release_id is None:
            raise ValueError("an impact must have distinct reasons and a release reference")
        if self.needs_review != any(reason != "REFERENCE_REPLACED" for reason in self.reasons):
            raise ValueError("reference-only changes do not create business review flags")
        return self


class ChangeImpactPage(CatalogModel):
    items: tuple[ChangeImpactData, ...] = Field(max_length=100)

    @field_validator("items", mode="before")
    @classmethod
    def finite_items(cls, value):
        return _sequence(value, 100)
