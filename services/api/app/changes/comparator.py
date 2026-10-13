"""Pure multiset comparison of fixed release business, without student data."""

import re
from uuid import UUID

from pydantic import ValidationError

from ..admissions_catalog.schemas import MAX_VERSION
from ..ingestion.schemas import _uuid

from .schemas import (
    BusinessClassification, BusinessDate, BusinessDiff, BusinessProjection,
    ChangesError, MemberDiff, PublishedMember, ReleaseSnapshot, fingerprint,
)


_FIELDS = ("value_kind", "value", "unit", "classification", "missing_reason",
           "footnote", "scope", "date", "public_evidence")


def business_projection(value: PublishedMember) -> BusinessProjection:
    """Keep original bounded values; remove only identity from interpretation."""
    member = PublishedMember.model_validate(value)
    fact = member.fact
    classification = fact.classification.model_dump(exclude={"date_event_id"})
    date_value = None if fact.date_resolution is None else BusinessDate.model_validate({
        name: getattr(fact.date_resolution, name) for name in BusinessDate.model_fields
    })
    return BusinessProjection(value_kind=fact.value_kind, value_text=fact.value_text,
        normalized_value=fact.normalized_value, unit=fact.unit,
        classification=BusinessClassification.model_validate(classification),
        missing_reason=fact.missing_reason, footnote_state=fact.footnote_state,
        footnote_text=fact.footnote_text, scope=member.evidence.scope,
        date_resolution=date_value, public_evidence=member.release_member.public_evidence)


def _semantic(value: BusinessProjection):
    fields = value.model_dump(mode="json")
    # The original decimal is still retained in output, but lexical trailing
    # zeroes do not alter its exact numeric meaning. Text remains verbatim.
    fields.pop("value_text")
    return {
        "value_kind": fields["value_kind"], "value": fields["normalized_value"],
        "unit": fields["unit"], "classification": fields["classification"],
        "missing_reason": fields["missing_reason"],
        "footnote": {"state": fields["footnote_state"], "text": fields["footnote_text"]},
        "scope": fields["scope"], "date": fields["date_resolution"],
        "public_evidence": fields["public_evidence"],
    }


def _multiset(values):
    # Sorting the complete list preserves multiplicity instead of discarding
    # duplicates as a set would. All values came from closed validated models.
    return tuple(sorted(fingerprint(value) for value in values))


def _group(snapshot):
    result = {}
    if snapshot is not None:
        for member in snapshot.members:
            key = (member.fact.offering_id, member.fact.fact_type, member.fact.field_key)
            result.setdefault(key, []).append(member)
    return result


def _member_diff(key, before, after):
    old = tuple(sorted(before, key=lambda member: str(member.fact.id)))
    new = tuple(sorted(after, key=lambda member: str(member.fact.id)))
    old_projection = tuple(business_projection(member) for member in old)
    new_projection = tuple(business_projection(member) for member in new)
    old_references = tuple(member.release_member for member in old)
    new_references = tuple(member.release_member for member in new)
    reference_changed = _multiset(member.model_dump(mode="json") for member in old) != _multiset(
        member.model_dump(mode="json") for member in new)
    return _projection_diff(key, old_projection, new_projection, old_references, new_references,
                            reference_changed=reference_changed)


def _projection_diff(key, old_projection, new_projection, old_references, new_references, *, reference_changed):
    old_semantic, new_semantic = tuple(map(_semantic, old_projection)), tuple(map(_semantic, new_projection))
    changed = _multiset(old_semantic) != _multiset(new_semantic)
    fields = tuple(field for field in _FIELDS if
        _multiset(value[field] for value in old_semantic) != _multiset(value[field] for value in new_semantic))
    if changed and not fields:
        fields = ("association",)
    kind = "added" if not old_projection else "removed" if not new_projection else "changed" if changed else "unchanged"
    return MemberDiff(kind=kind, offering_id=key[0], fact_type=key[1], field_key=key[2],
        before_fact_ids=tuple(member.fact_id for member in old_references),
        after_fact_ids=tuple(member.fact_id for member in new_references), before=old_projection, after=new_projection,
        before_references=old_references, after_references=new_references, changed_fields=fields,
        reference_changed=reference_changed, semantic_business_changed=changed)


def target_member_diffs(diff: BusinessDiff, *, offering_id: UUID, offering_version: int,
                        scope_sha256: str) -> tuple[MemberDiff, ...]:
    """Compare all fields for an original exact target, without narrowing to rule fact IDs."""
    try:
        offering_id = _uuid(offering_id)
        if (type(offering_version) is not int or not 1 <= offering_version <= MAX_VERSION
            or type(scope_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", scope_sha256) is None):
            raise ValueError("an exact bounded target reference is required")
        current = BusinessDiff.model_validate(diff)
        if not any(reference.offering_id == offering_id and reference.offering_version == offering_version
                   and reference.scope_sha256 == scope_sha256
                   for item in current.member_diffs for reference in item.before_references):
            return ()
        result = []
        for item in current.member_diffs:
            if item.offering_id != offering_id:
                continue
            old = tuple((projection, reference) for projection, reference in zip(item.before, item.before_references)
                if reference.offering_version == offering_version and reference.scope_sha256 == scope_sha256)
            new = tuple((projection, reference) for projection, reference in zip(item.after, item.after_references)
                if reference.scope_sha256 == scope_sha256)
            if not old and not new:
                continue
            old_projection, old_refs = tuple(pair[0] for pair in old), tuple(pair[1] for pair in old)
            new_projection, new_refs = tuple(pair[0] for pair in new), tuple(pair[1] for pair in new)
            reference_changed = _multiset(reference.model_dump(mode="json") for reference in old_refs) != _multiset(
                reference.model_dump(mode="json") for reference in new_refs)
            result.append(_projection_diff((item.offering_id, item.fact_type, item.field_key),
                old_projection, new_projection, old_refs, new_refs, reference_changed=reference_changed))
        return tuple(result)
    except (ValidationError, ValueError, TypeError, OverflowError, AttributeError, UnicodeError):
        raise ChangesError(422) from None


def compare_releases(before: ReleaseSnapshot | None, after: ReleaseSnapshot | None, *, event_type: str) -> BusinessDiff:
    """Classify an exact event snapshot; never mark or rewrite a private object."""
    try:
        if type(event_type) is not str or event_type not in {"published", "replaced", "withdrawn"}:
            raise ValueError("a fixed release event is required")
        if (before is not None, after is not None) != {
            "published": (False, True), "replaced": (True, True), "withdrawn": (True, False)
        }[event_type]:
            raise ValueError("exact event snapshots are required")
        old = ReleaseSnapshot.model_validate(before) if before is not None else None
        new = ReleaseSnapshot.model_validate(after) if after is not None else None
        if old is not None and new is not None:
            a, b = old.release, new.release
            if ((a.dataset_id, a.entry_year, a.kind, a.is_synthetic) !=
                (b.dataset_id, b.entry_year, b.kind, b.is_synthetic)
                or a.release_id == b.release_id or b.replaces_release_id != a.release_id
                or a.replaced_by_release_id is not None and a.replaced_by_release_id != b.release_id):
                raise ValueError("replacement must bind the same explicit dataset, year and mode")
        original = old if old is not None else new
        release_fields = ()
        if old is not None and new is not None:
            release_fields = tuple(name for name, changed in (
                ("validity", (old.release.valid_from, old.release.valid_until) !=
                             (new.release.valid_from, new.release.valid_until)),
                ("ruleset", old.release.ruleset_version != new.release.ruleset_version),
            ) if changed)
        elif event_type == "withdrawn":
            release_fields = ("availability",)
        old_groups, new_groups = _group(old), _group(new)
        keys = sorted(old_groups.keys() | new_groups.keys(), key=lambda key: (str(key[0]), key[1], key[2]))
        differences = tuple(_member_diff(key, old_groups.get(key, ()), new_groups.get(key, ())) for key in keys)
        return BusinessDiff(event_type=event_type,
            before_release_id=old.release.release_id if old is not None else None,
            after_release_id=new.release.release_id if new is not None else None,
            dataset_id=original.release.dataset_id, entry_year=original.release.entry_year,
            is_synthetic=original.release.is_synthetic, release_changed_fields=release_fields,
            member_diffs=differences,
            semantic_business_changed=bool(release_fields or any(item.semantic_business_changed for item in differences)),
            reference_changed=(event_type != "replaced" or old.release.model_dump(mode="json") != new.release.model_dump(mode="json")
                               or any(item.reference_changed for item in differences)))
    except (ValidationError, ValueError, TypeError, OverflowError, AttributeError, UnicodeError):
        raise ChangesError(422) from None
