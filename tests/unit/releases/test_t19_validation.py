"""Offline intrinsic release checks; no test here establishes public authority."""

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID

from pydantic import ValidationError
import pytest

from services.api.app.releases.schemas import (
    MAX_MEMBERS, PublishMember, PublishRequest, ReleaseData, ReleaseMemberData,
    ReleasePolicy, ReleasesError, WithdrawalRequest,
)
from services.api.app.releases.validation import (
    release_content_hash, requirements_snapshot_hash, validate_release,
)


NOW = datetime(2026, 10, 3, 8, tzinfo=timezone.utc)
DATASET = UUID(int=9000)


def member(index=1, **changes):
    values = dict(fact_id=UUID(int=index), logical_key_hash=sha256(f"DEMO_group_{index}".encode()).hexdigest(),
        decision_id=UUID(int=100 + index), case_revision=1, offering_id=UUID(int=200 + index),
        offering_version=1, entry_year=2026, source_id=UUID(int=300), source_version=1,
        evidence_id=UUID(int=400 + index), fact_sha256="1" * 64, scope_sha256="2" * 64,
        evidence_sha256="3" * 64, source_sha256="4" * 64, file_sha256="5" * 64,
        public_evidence=False)
    return ReleaseMemberData.model_validate({**values, **changes})


def request(snapshots=None, **changes):
    current = (member(),) if snapshots is None else snapshots
    values = dict(dataset_id=DATASET, expected_dataset_revision=1, entry_year=2026,
        kind="test_fixture", valid_from=NOW - timedelta(hours=1), valid_until=NOW + timedelta(days=1),
        members=tuple(PublishMember(fact_id=item.fact_id, expected_case_revision=item.case_revision,
            expected_decision_id=item.decision_id, public_evidence=item.public_evidence) for item in current),
        replaces_release_id=None, expected_replaced_state_revision=None)
    return PublishRequest.model_validate({**values, **changes})


def release(current=None, snapshots=None, **changes):
    snapshots = (member(),) if snapshots is None else snapshots
    current = request(snapshots) if current is None else current
    values = dict(release_id=UUID(int=500), version=1, dataset_id=current.dataset_id,
        entry_year=current.entry_year, kind=current.kind, is_synthetic=current.kind == "test_fixture",
        valid_from=current.valid_from, valid_until=current.valid_until,
        content_sha256=release_content_hash(current, snapshots), requirements_version=requirements_snapshot_hash(snapshots),
        ruleset_version=None, members=snapshots, state="published", state_revision=1, published_at=NOW,
        publisher_user_id=UUID(int=600), replaces_release_id=current.replaces_release_id,
        replaced_by_release_id=None, replayed=False)
    return ReleaseData.model_validate({**values, **changes})


def test_valid_fixture_snapshot_is_sorted_explicit_and_has_no_executable_rules():
    snapshots = (member(2), member(1))
    current = request(snapshots)
    checked = validate_release(current, snapshots, is_synthetic=True)
    data = release(current, snapshots)
    assert [item.fact_id.int for item in checked] == [1, 2]
    assert [item.fact_id.int for item in current.members] == [1, 2]
    assert data.members == checked and data.ruleset_version is None
    assert data.requirements_version == requirements_snapshot_hash(checked)
    assert data.members[0].public_evidence is False
    assert "file_id" not in data.members[0].model_dump()


def test_every_request_field_and_nullable_replacement_are_explicit():
    original = request().model_dump()
    for name in PublishRequest.model_fields:
        with pytest.raises(ValidationError):
            PublishRequest.model_validate({key: value for key, value in original.items() if key != name})
    for changes in ({"owner_user_id": UUID(int=1)}, {"role": "data_admin"},
        {"published_at": NOW}, {"content_sha256": "a" * 64}, {"idempotency_key": "SENTINEL_secret"}):
        with pytest.raises(ValidationError):
            PublishRequest.model_validate({**original, **changes})


def test_members_have_a_real_bound_and_preserve_the_frozen_set():
    snapshots = tuple(member(index) for index in range(1, MAX_MEMBERS + 1))
    current = request(snapshots)
    assert len(validate_release(current, snapshots, is_synthetic=True)) == 50
    for sequence in ((), snapshots + (member(51),), iter(snapshots), {item.fact_id for item in snapshots}):
        with pytest.raises(ValidationError):
            request(members=sequence)
    with pytest.raises(ReleasesError):
        validate_release(current, snapshots[:49], is_synthetic=True)
    assert len(current.members) == 50


def test_duplicate_fact_and_server_logical_group_are_distinct_rejections():
    first = member()
    with pytest.raises(ValidationError):
        request((first, first))
    second = member(2, logical_key_hash=first.logical_key_hash)
    current = request((first, second))
    with pytest.raises(ReleasesError) as error:
        validate_release(current, (first, second), is_synthetic=True)
    assert error.value.status_code == 422
    with pytest.raises(ValidationError):
        ReleaseData.model_validate(release().model_copy(update={"members": (first, second)}))


@pytest.mark.parametrize("changes", [
    {"expected_dataset_revision": True}, {"expected_dataset_revision": "1"},
    {"entry_year": 2026.0}, {"entry_year": 0}, {"entry_year": 10000},
])
def test_year_and_revision_are_strict_bounded_assertions(changes):
    with pytest.raises(ValidationError):
        PublishRequest.model_validate(request().model_copy(update=changes))


def test_member_references_are_canonical_and_case_versions_are_positive():
    original = request().members[0]
    for changes in ({"fact_id": "00000000-0000-0000-0000-00000000000A"},
        {"fact_id": b"00000000-0000-0000-0000-000000000001"}, {"fact_id": 1},
        {"expected_case_revision": True}, {"expected_case_revision": 0},
        {"expected_case_revision": 2147483648}, {"public_evidence": "false"}):
        with pytest.raises(ValidationError):
            PublishMember.model_validate(original.model_copy(update=changes))
    assert PublishMember.model_validate({**original.model_dump(), "fact_id": str(original.fact_id)}) == original


def test_utc_intervals_normalize_native_offsets_without_inventing_year_or_deadline():
    offset = timezone(timedelta(hours=8))
    current = request(valid_from=NOW.astimezone(offset), valid_until=(NOW + timedelta(seconds=1)).astimezone(offset))
    assert current.valid_from == NOW and current.valid_from.utcoffset() == timedelta(0)
    assert current.valid_until - current.valid_from == timedelta(seconds=1)
    # Applicability and entry year are independent explicit assertions.
    different_year = request(entry_year=2027, valid_from=NOW, valid_until=NOW + timedelta(seconds=1))
    assert different_year.entry_year == 2027 and different_year.valid_from.year == 2026


def test_naive_fold_string_numeric_date_and_utc_overflow_are_not_coerced():
    values = (NOW.replace(tzinfo=None), NOW.replace(fold=1), NOW.isoformat(), NOW.timestamp(),
        date(2026, 10, 3), datetime.min.replace(tzinfo=timezone(timedelta(hours=8))))
    for value in values:
        with pytest.raises(ValidationError):
            request(valid_from=value)
    for end in (NOW - timedelta(hours=1), NOW - timedelta(days=1)):
        with pytest.raises(ValidationError):
            request(valid_until=end)


def test_replacement_requires_exact_pair_and_changes_content_identity():
    first = request()
    target = UUID(int=700)
    for changes in ({"replaces_release_id": target}, {"expected_replaced_state_revision": 1},
        {"replaces_release_id": target, "expected_replaced_state_revision": True}):
        with pytest.raises(ValidationError):
            PublishRequest.model_validate(first.model_copy(update=changes))
    replacement = request(replaces_release_id=target, expected_replaced_state_revision=1)
    another = request(replaces_release_id=UUID(int=701), expected_replaced_state_revision=1)
    assert release_content_hash(first, (member(),)) != release_content_hash(replacement, (member(),))
    assert release_content_hash(another, (member(),)) != release_content_hash(replacement, (member(),))
    assert release_content_hash(replacement.model_copy(update={"expected_replaced_state_revision": 2}), (member(),)) == release_content_hash(replacement, (member(),))


def test_formal_synthetic_and_fixture_real_are_rejected_without_claiming_truth():
    snapshots = (member(),)
    formal = request(kind="formal")
    assert validate_release(formal, snapshots, is_synthetic=False) == snapshots
    for current, marker in ((formal, True), (request(), False), (request(), 1)):
        with pytest.raises(ReleasesError) as error:
            validate_release(current, snapshots, is_synthetic=marker)
        assert error.value.status_code == 422
    # This intrinsic gate alone does not verify institution identity or authorize a real publication.
    for kind in ("demo", "verified", "published", "FORMAL"):
        with pytest.raises(ValidationError):
            request(kind=kind)


def test_members_bind_actual_approved_decision_revision_year_and_public_choice():
    current, original = request(), member()
    for changes in ({"fact_id": UUID(int=9)}, {"decision_id": UUID(int=9)},
        {"case_revision": 2}, {"entry_year": 2027}, {"public_evidence": True}):
        with pytest.raises(ReleasesError) as error:
            validate_release(current, (original.model_copy(update=changes),), is_synthetic=True)
        assert error.value.status_code == 409


def test_member_order_is_canonical_and_client_dataset_cas_does_not_change_content():
    snapshots = (member(2), member(1))
    original = request(snapshots)
    changed = original.model_copy(update={"expected_dataset_revision": 2})
    assert requirements_snapshot_hash(snapshots) == requirements_snapshot_hash(tuple(reversed(snapshots)))
    assert release_content_hash(original, snapshots) == release_content_hash(changed, tuple(reversed(snapshots)))
    shifted = request(snapshots, valid_until=original.valid_until + timedelta(seconds=1))
    assert release_content_hash(original, snapshots) != release_content_hash(shifted, snapshots)


def test_snapshot_hash_includes_actual_approval_evidence_source_and_public_fields():
    original = member()
    initial = requirements_snapshot_hash((original,))
    for changes in ({"case_revision": 2}, {"decision_id": UUID(int=99)}, {"evidence_id": UUID(int=99)},
        {"source_version": 2}, {"file_sha256": "6" * 64}, {"public_evidence": True}):
        changed = ReleaseMemberData.model_validate(original.model_copy(update=changes))
        assert requirements_snapshot_hash((changed,)) != initial
    assert len(initial) == 64


def test_release_output_revalidates_hashes_and_does_not_derive_rule_versions():
    original = release()
    for changes in ({"content_sha256": "a" * 64}, {"requirements_version": "a" * 64},
        {"ruleset_version": "DEMO_compiled"}, {"version": True}, {"version": 2},
        {"is_synthetic": False}, {"replayed": 1}, {"storage_path": "SENTINEL_path"}):
        with pytest.raises(ValidationError):
            ReleaseData.model_validate(original.model_copy(update=changes))
    assert ReleaseData.model_validate(original.model_copy(update={"replayed": True})).replayed is True


def test_release_metadata_state_and_successor_are_separate_from_content_snapshot():
    original = release()
    withdrawn = ReleaseData.model_validate(original.model_copy(update={"state": "withdrawn", "state_revision": 2}))
    replaced = ReleaseData.model_validate(original.model_copy(update={"state": "replaced", "state_revision": 2,
        "replaced_by_release_id": UUID(int=701)}))
    assert original.content_sha256 == withdrawn.content_sha256 == replaced.content_sha256
    for changes in ({"state": "replaced"}, {"replaced_by_release_id": UUID(int=701)},
        {"state": "replaced", "replaced_by_release_id": original.release_id}, {"state_revision": 0}):
        with pytest.raises(ValidationError):
            ReleaseData.model_validate(original.model_copy(update=changes))


def test_required_nullable_fields_and_server_timestamps_cannot_be_forged():
    original = release()
    for name in ("ruleset_version", "replaces_release_id", "replaced_by_release_id", "publisher_user_id"):
        with pytest.raises(ValidationError):
            ReleaseData.model_validate(original.model_dump(exclude={name}))
    for changes in ({"published_at": "2026-10-03T08:00:00Z"}, {"published_at": NOW.replace(fold=1)},
        {"publisher_user_id": True}):
        with pytest.raises(ValidationError):
            ReleaseData.model_validate(original.model_copy(update=changes))


def test_withdrawal_is_only_explicit_fixed_reason_and_exact_state_cas():
    original = WithdrawalRequest(release_id=UUID(int=500), expected_state_revision=1, reason_code="RIGHTS_REVOKED")
    for changes in ({"reason_code": "SENTINEL_free_text"}, {"expected_state_revision": True},
        {"expected_state_revision": 0}, {"reason": "SENTINEL_private"}, {"model_action": "withdraw"}):
        with pytest.raises(ValidationError):
            WithdrawalRequest.model_validate(original.model_copy(update=changes))
    assert WithdrawalRequest.model_fields.keys() == {"release_id", "expected_state_revision", "reason_code"}


def test_copied_nested_and_constructed_payloads_are_revalidated_with_safe_errors():
    current, original = request(), member()
    for fake in (current.model_copy(update={"valid_until": current.valid_from}),
        PublishRequest.model_construct(**{**current.model_dump(), "expected_dataset_revision": True})):
        with pytest.raises(ReleasesError) as error:
            validate_release(fake, (original,), is_synthetic=True)
        assert str(error.value) == "INVALID_RELEASE_INPUT"
    for fake in (original.model_copy(update={"file_sha256": "SENTINEL_hash"}),
        ReleaseMemberData.model_construct(**{**original.model_dump(), "public_evidence": 1})):
        with pytest.raises(ReleasesError):
            requirements_snapshot_hash((fake,))
    with pytest.raises(ValidationError):
        ReleaseData.model_validate(release().model_copy(update={"members": (original.model_copy(update={"public_evidence": True}),)}))
    with pytest.raises(ValidationError):
        current.kind = "formal"


def test_policy_is_closed_and_errors_never_reproduce_caller_text():
    assert ReleasePolicy().model_dump() == {"enabled": False, "real_releases_ready": False, "allow_test_releases": False}
    with pytest.raises(ValidationError):
        ReleasePolicy.model_validate(ReleasePolicy().model_copy(update={"allow_test_releases": "true"}))
    for value in (ReleasesError(500, "SENTINEL_SQL"), ReleasesError(True), ReleasesError(422, "SENTINEL_key")):
        assert str(value) == "RELEASE_UNAVAILABLE" and value.status_code == 503


def test_fresh_pure_import_does_not_connect_enable_policy_or_load_runtime_modules():
    code = """
import sys
from services.api.app.releases.schemas import ReleasePolicy
from services.api.app.releases.validation import validate_release
for prefix in ('sqlalchemy', 'httpx', 'services.api.app.auth', 'services.api.app.main', 'services.api.app.database', 'services.api.app.providers'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
assert not any(ReleasePolicy().model_dump().values())
print('pure releases')
"""
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(__file__).resolve().parents[3],
        env={**os.environ, "RELEASES_ENABLED": "true", "ALLOW_TEST_RELEASES": "true"},
        text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "pure releases"
