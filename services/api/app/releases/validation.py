"""Pure snapshot gates and deterministic hashes, never current authorization."""

from pydantic import ValidationError

from ..api.v2.idempotency_canonical import canonical_request_hash
from .schemas import MAX_MEMBERS, PublishRequest, ReleaseMemberData, ReleasesError


def _members(value) -> tuple[ReleaseMemberData, ...]:
    if type(value) not in (list, tuple) or not 1 <= len(value) <= MAX_MEMBERS:
        raise ValueError("bounded members are required")
    members = tuple(sorted((ReleaseMemberData.model_validate(item) for item in value),
                           key=lambda item: str(item.fact_id)))
    if (len({item.fact_id for item in members}) != len(members)
        or len({item.logical_key_hash for item in members}) != len(members)):
        raise ValueError("one chosen fact per distinct logical group is required")
    return members


def _matching_members(request: PublishRequest, members: tuple[ReleaseMemberData, ...]):
    if len(request.members) != len(members):
        raise ReleasesError(409)
    for expected, actual in zip(request.members, members):
        if (expected.fact_id, expected.expected_case_revision, expected.expected_decision_id,
            expected.public_evidence, request.entry_year) != (
            actual.fact_id, actual.case_revision, actual.decision_id, actual.public_evidence, actual.entry_year):
            raise ReleasesError(409)


def validate_release(request: PublishRequest, members, *, is_synthetic: bool) -> tuple[ReleaseMemberData, ...]:
    """Bind exact server snapshots; runtime, dataset and proof gates stay in SQL."""
    try:
        current = PublishRequest.model_validate(request)
        snapshot = _members(members)
        if type(is_synthetic) is not bool or (current.kind == "test_fixture") != is_synthetic:
            raise ReleasesError(422)
        _matching_members(current, snapshot)
        return snapshot
    except ReleasesError:
        raise
    except (ValidationError, ValueError, TypeError, OverflowError, AttributeError):
        raise ReleasesError(422) from None


def requirements_snapshot_hash(members) -> str:
    """Hash all sorted member metadata, including actual approval and evidence."""
    try:
        return canonical_request_hash([item.model_dump(mode="json") for item in _members(members)])
    except (ValidationError, ValueError, TypeError, OverflowError, AttributeError):
        raise ReleasesError(422) from None


def _content_hash(*, dataset_id, entry_year, kind, valid_from, valid_until, members, replaces_release_id) -> str:
    # Called only after the owning PublishRequest/ReleaseData validated native
    # IDs and UTC timestamps. State, replay and caller CAS are deliberately absent.
    return canonical_request_hash({
        "dataset_id": str(dataset_id), "entry_year": entry_year, "kind": kind,
        "valid_from": valid_from.isoformat(), "valid_until": valid_until.isoformat(),
        "members": [item.model_dump(mode="json") for item in members],
        "replaces_release_id": str(replaces_release_id) if replaces_release_id is not None else None,
    })


def release_content_hash(request: PublishRequest, members) -> str:
    """Natural content identity includes a replacement target, not an idem key."""
    try:
        current = PublishRequest.model_validate(request)
        snapshot = _members(members)
        _matching_members(current, snapshot)
        return _content_hash(dataset_id=current.dataset_id, entry_year=current.entry_year, kind=current.kind,
            valid_from=current.valid_from, valid_until=current.valid_until, members=snapshot,
            replaces_release_id=current.replaces_release_id)
    except ReleasesError:
        raise
    except (ValidationError, ValueError, TypeError, OverflowError, AttributeError):
        raise ReleasesError(422) from None
