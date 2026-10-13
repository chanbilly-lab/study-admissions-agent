"""Offline finite-mode, integrity and disclosure contracts; no external sockets."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretBytes, ValidationError
import pytest

from services.api.app.api.rights import create_rights_app
from services.api.app.privacy.rights.ledger import FileAnchor, canonical, chain_hash
from services.api.app.privacy.rights.schemas import (ExportContent, LedgerEventData, LedgerProof,
    OwnerConfirmation, RightsPolicy, RightsRequestData, RightsError, ZERO_HASH)


@pytest.mark.parametrize("field,value", [("enabled", 1), ("allow_test_rights", "true"), ("real_rights_ready", True),
    ("lease_seconds", 0), ("lease_seconds", 301), ("max_attempts", 6), ("retry_seconds", False),
    ("export_ttl_seconds", 86401), ("max_export_bytes", 10485761), ("max_rows", 5001), ("max_rows", "5")])
def test_policy_closed(field, value):
    with pytest.raises(ValidationError):
        RightsPolicy(**{field: value})


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_confirmation_is_literal_boolean(value):
    with pytest.raises(ValidationError):
        OwnerConfirmation(owner_confirmed=value)
    with pytest.raises(ValidationError):
        OwnerConfirmation.model_validate(OwnerConfirmation.model_construct(owner_confirmed=value))


def test_confirmation_rejects_caller_scope():
    for key in ("owner_user_id", "resource_ids", "path", "verified", "reason", "handler"):
        with pytest.raises(ValidationError):
            OwnerConfirmation.model_validate({"owner_confirmed": True, key: "DEMO"})


@pytest.mark.parametrize("kind", ["owner_deleted", "session_revoked", "core_withdrawn", "grant_revoked", "file_deleted"])
def test_ledger_exact_reference(kind):
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        LedgerEventData(event_id=uuid4(), kind=kind, owner_user_id=uuid4(), recorded_at=now, expires_at=now + timedelta(days=1))
    valid = LedgerEventData(event_id=uuid4(), kind=kind, owner_user_id=uuid4(), resource_id=uuid4(),
        recorded_at=now, expires_at=now + timedelta(days=1))
    assert LedgerEventData.model_validate_json(valid.model_dump_json()) == valid


def test_role_reduction_pins_epoch_and_closed_fields():
    now = datetime.now(timezone.utc)
    base = dict(event_id=uuid4(), kind="role_revoked", owner_user_id=uuid4(), recorded_at=now, expires_at=now + timedelta(days=1))
    with pytest.raises(ValidationError):
        LedgerEventData(**base, role="student")
    valid = LedgerEventData(**base, role="student", role_granted_at=now)
    with pytest.raises(ValidationError):
        LedgerEventData.model_validate({**valid.model_dump(), "grades": "DEMO_PRIVATE"})
    assert "grades" not in valid.model_dump()


def test_chain_includes_order_and_each_exact_event():
    event = {"kind": "session_revoked", "id": str(uuid4())}
    first = chain_hash(ZERO_HASH, 1, event)
    assert first == chain_hash(ZERO_HASH, 1, dict(reversed(tuple(event.items()))))
    assert len({first, chain_hash(ZERO_HASH, 2, event), chain_hash("1" * 64, 1, event),
        chain_hash(ZERO_HASH, 1, {**event, "id": str(uuid4())})}) == 4


def test_anchor_requires_explicit_fresh_bootstrap_and_detects_tampering(tmp_path):
    anchor = FileAnchor(tmp_path, SecretBytes(b"DEMO_T40_ONLY_32_BYTE_ANCHOR_KEY__"))
    with pytest.raises(RightsError):
        anchor.read()
    proof = LedgerProof(ledger_id=uuid4(), sequence=0, chain_sha256=ZERO_HASH)
    with anchor.locked():
        anchor.write_locked(proof, previous=None)
    assert anchor.read() == proof
    with pytest.raises(RightsError), anchor.locked():
        anchor.write_locked(proof, previous=None)
    document = json.loads((tmp_path / "latest.json").read_bytes())
    document["proof"]["sequence"] = 1
    (tmp_path / "latest.json").write_bytes(canonical(document))
    with pytest.raises(RightsError):
        anchor.read()


def test_anchor_lock_is_exclusive_and_key_root_replacement_rejected(tmp_path):
    anchor = FileAnchor(tmp_path, SecretBytes(b"DEMO_T40_ONLY_32_BYTE_ANCHOR_KEY__"))
    with anchor.locked():
        with pytest.raises(RightsError), anchor.locked():
            pass
    assert not (tmp_path / "anchor.lock").exists()
    anchor.key = SecretBytes(b"DEMO_T40_REPLACEMENT_32_BYTE_KEY__")
    with pytest.raises(RightsError):
        anchor.read()


@pytest.mark.parametrize("change", [{"size_bytes": 1}, {"sha256": "f" * 64}, {"content_json": "[]"}])
def test_export_artifact_exact_utf8_integrity(change):
    content = '{"DEMO":"合成"}'
    data = dict(request_id=uuid4(), content_json=content, size_bytes=len(content.encode()),
        sha256=sha256(content.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    with pytest.raises(ValidationError):
        ExportContent(**{**data, **change})


def test_accepted_is_not_completed():
    now = datetime.now(timezone.utc)
    base = dict(request_id=uuid4(), kind="deletion", status="queued", reason="OK", attempts=0,
        accepted_at=now, online_cleanup_due_at=now + timedelta(days=30), completed_at=None,
        artifact_expires_at=None, online_cleanup_complete=False, retained_responsibility_until=now + timedelta(days=365))
    assert not RightsRequestData(**base).online_cleanup_complete
    for change in ({"online_cleanup_complete": True}, {"completed_at": now}, {"online_cleanup_due_at": None}):
        with pytest.raises(ValidationError):
            RightsRequestData(**{**base, **change})


def test_default_disabled_factory_discloses_mode_without_database(monkeypatch):
    import sqlalchemy
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No DB")))
    with TestClient(create_rights_app()) as client:
        context = client.get("/v2/privacy/rights/context")
        assert context.status_code == 200 and context.headers["cache-control"] == "no-store"
        assert context.json()["data"]["reason"] == "RIGHTS_DISABLED"
        assert context.json()["data"]["real_rights_ready"] is False
        assert client.post("/v2/privacy/deletions", json={"owner_confirmed": True}).status_code == 503
        assert client.get("/v2/privacy/rights/context?owner=DEMO").status_code == 422
        assert client.get("/v1/profiles").status_code == 404
