"""Finite policy/receipt contracts never grant replay permission by themselves."""

from datetime import datetime, timedelta, timezone
import os
import subprocess
import sys
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
import pytest

from app.idempotency.schemas import (
    IdempotencyError, IdempotencyPolicy, IdempotencyResult, MAX_TTL_SECONDS,
    MAX_VERSION, Operation, ResourceReceipt,
)


def receipt(**changes):
    return ResourceReceipt(**{"kind": "profile", "resource_id": uuid4(), "version": 1, **changes})


def test_policy_is_closed_without_explicit_ttl_and_has_no_ambient_defaults():
    policy = IdempotencyPolicy()
    assert policy.model_dump() == {"enabled": False, "real_idempotency_ready": False, "ttl_seconds": None}
    with pytest.raises(ValidationError):
        IdempotencyPolicy(enabled=True)
    fixture = IdempotencyPolicy(enabled=True, ttl_seconds=24 * 60 * 60)
    assert fixture.real_idempotency_ready is False


@pytest.mark.parametrize("value", [0, -1, MAX_TTL_SECONDS + 1, True, 86_400.0, "86400"])
def test_ttl_is_a_strict_finite_seconds_value(value):
    with pytest.raises(ValidationError):
        IdempotencyPolicy(enabled=True, ttl_seconds=value)


def test_policy_copy_or_construct_cannot_bypass_revalidation():
    policy = IdempotencyPolicy()
    for forged in (policy.model_copy(update={"enabled": True}),
                   IdempotencyPolicy.model_construct(enabled=True, real_idempotency_ready=False, ttl_seconds=True)):
        with pytest.raises(ValidationError):
            IdempotencyPolicy.model_validate(forged)
    with pytest.raises(ValidationError):
        policy.enabled = True


def test_operation_is_closed_exact_and_not_a_generic_method_name():
    adapter = TypeAdapter(Operation)
    for name in ("catalog.import", "catalog.publish", "profile.create", "plan.confirm"):
        assert adapter.validate_python(name) == name
    for name in ("CATALOG.IMPORT", "catalog.import ", "plan.delete", "profile.*", None, True, 1):
        with pytest.raises(ValidationError):
            adapter.validate_python(name)


def test_receipt_contains_only_finite_resource_reference():
    value = receipt()
    assert set(value.model_dump()) == {"kind", "resource_id", "version"}
    assert value.resource_id.version == 4
    for extra in ({"body": {"DEMO_private": "secret"}}, {"owner_user_id": uuid4()},
                  {"expires_at": datetime.now(timezone.utc)}, {"status": "allowed"}):
        with pytest.raises(ValidationError):
            receipt(**extra)


@pytest.mark.parametrize("changes", [
    {"kind": "attachment"}, {"kind": None}, {"resource_id": "DEMO_private-invalid"},
    {"resource_id": True}, {"version": 0}, {"version": True},
    {"version": 1.0}, {"version": MAX_VERSION + 1},
])
def test_malformed_receipt_not_coerced_into_permission(changes):
    with pytest.raises(ValidationError) as caught:
        receipt(**changes)
    assert "DEMO_private-invalid" not in str(caught.value)


def test_result_revalidates_nested_copy_and_constructed_resource():
    valid = receipt()
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    for forged in (valid.model_copy(update={"version": 0}),
                   ResourceReceipt.model_construct(kind="profile", resource_id=valid.resource_id, version=True)):
        with pytest.raises(ValidationError):
            IdempotencyResult(resource=forged, replayed=False, expires_at=now)
    result = IdempotencyResult(resource=valid, replayed=False, expires_at=now)
    with pytest.raises(ValidationError):
        IdempotencyResult.model_validate(result.model_copy(update={"replayed": 1}))


def test_result_uses_native_aware_time_but_past_metadata_is_not_an_allowance():
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    result = IdempotencyResult(resource=receipt(), replayed=True, expires_at=past)
    assert result.expires_at == past  # Current replay expiry belongs to the service guard.
    local = datetime(2026, 10, 3, 8, tzinfo=timezone(timedelta(hours=8)))
    assert IdempotencyResult(resource=receipt(), replayed=False, expires_at=local).expires_at == datetime(2026, 10, 3, tzinfo=timezone.utc)
    for invalid in (datetime(2026, 10, 3), 0, "2026-10-03T00:00:00Z"):
        with pytest.raises(ValidationError):
            IdempotencyResult(resource=receipt(), replayed=False, expires_at=invalid)


def test_server_timestamp_conversion_rejects_fold_and_utc_overflow_safely():
    from app.idempotency.store import utc_time

    invalid_times = (
        datetime(2026, 10, 3, tzinfo=timezone.utc, fold=1),
        datetime.max.replace(tzinfo=timezone(timedelta(hours=-1))),
        datetime.min.replace(tzinfo=timezone(timedelta(hours=1))),
    )
    for invalid in invalid_times:
        with pytest.raises(ValidationError):
            IdempotencyResult(resource=receipt(), replayed=False, expires_at=invalid)
        with pytest.raises(IdempotencyError) as caught:
            utc_time(invalid)
        assert caught.value.status_code == 503


def test_persisted_receipt_calendar_cap_is_not_a_current_replay_permission():
    from types import SimpleNamespace
    from app.idempotency.store import IdempotencyStore

    created = datetime(2024, 2, 29, 12, tzinfo=timezone.utc)
    expiry = datetime(2026, 2, 28, 12, tzinfo=timezone.utc)
    row = SimpleNamespace(
        id=uuid4(), actor_user_id=uuid4(), operation="profile.create", is_synthetic=True,
        key_digest="a" * 64, request_hash="b" * 64, state="completed",
        created_at=created, expires_at=expiry, completed_at=created + timedelta(seconds=1),
        resource_kind="profile", resource_id=uuid4(), resource_version=1,
    )
    # Historical structurally valid metadata is readable; the service must separately
    # enforce now < expires_at, including after lock waits and required audit writes.
    IdempotencyStore._validate_row(row)
    for changes in ({"expires_at": expiry + timedelta(seconds=1)}, {"completed_at": expiry}):
        invalid = SimpleNamespace(**{**vars(row), **changes})
        with pytest.raises(IdempotencyError):
            IdempotencyStore._validate_row(invalid)


def test_safe_errors_do_not_accept_arbitrary_status_or_message():
    for status, code in ((True, None), (500, None), (409, "DEMO_secret"), (422, "bad")):
        error = IdempotencyError(status, code)
        assert error.status_code == 503 and error.code == "IDEMPOTENCY_UNAVAILABLE"
        assert "DEMO" not in str(error)


def test_fresh_schema_import_has_no_database_or_runtime_side_effects():
    program = '''
import sys
from app.idempotency.schemas import IdempotencyPolicy, ResourceReceipt
assert not IdempotencyPolicy().enabled
assert not any(name.startswith(("sqlalchemy", "httpx", "app.auth", "app.privacy",
                               "app.audit", "app.main", "app.idempotency.service"))
               for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-B", "-c", program], capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": "services/api", "IDEMPOTENCY_TTL_SECONDS": "86400"})
    assert result.returncode == 0, result.stderr
