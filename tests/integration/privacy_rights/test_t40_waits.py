"""Actual concurrent acceptance, final execution time and conservative rollback."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.models import AuthUser
from services.api.app.privacy.rights.models import RightsRequest, RightsWatermark
from services.api.app.privacy.rights.schemas import OwnerConfirmation, RightsError, RightsPolicy
from services.api.app.api.rights import create_rights_v2_app
from fastapi.testclient import TestClient
from tests.integration.plan_revisions.test_t35_http import identify, safe

pytestmark = pytest.mark.postgres
CONFIRM = OwnerConfirmation(owner_confirmed=True)


def test_concurrent_deletion_has_one_durable_authority_and_distinct_claims(rights_case_factory, pg_engine):
    case = rights_case_factory()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(case.rights.create, case.principal, "deletion", CONFIRM) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert len({value.request_id for value in results}) == 1
    assert case.ledger.snapshot()[0].sequence == 1
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(case.rights.claim, uuid4()) for _ in range(2)]
        leases = [future.result(timeout=30) for future in futures]
    nonempty = [value for value in leases if value is not None]
    assert len(nonempty) == 1 and nonempty[0].generation == 1
    assert case.rights.run(nonempty[0]).online_cleanup_complete
    with Session(pg_engine) as session:
        assert len(session.scalars(select(RightsRequest).where(RightsRequest.kind == "deletion")).all()) == 1


def test_final_export_lease_expiry_has_no_download_and_is_reclaimable(rights_case_factory, blob_root):
    case = rights_case_factory(policy=RightsPolicy(enabled=True, allow_test_rights=True, lease_seconds=1))
    request = case.rights.create(case.principal, "export", CONFIRM)
    old = case.rights.claim(uuid4())
    case.io.after_write = lambda: case.clock.advance(1)
    with pytest.raises(RightsError) as lost:
        case.rights.run(old)
    assert lost.value.status_code == 409
    assert list((blob_root / "student_private").iterdir()) == []
    case.io.after_write = None
    new = case.rights.claim(uuid4())
    assert new.generation == 2
    assert case.rights.run(new).status == "completed"
    case.io.after_read = lambda: case.clock.advance(3600)
    with pytest.raises(AuthFlowError) as stale:
        case.rights.content(case.principal, request.request_id)
    assert stale.value.status_code == 401


def test_acceptance_audit_rollback_leaves_external_reduction_and_closes_until_replay(rights_case_factory, pg_engine, monkeypatch):
    case = rights_case_factory()
    original = case.auth.store.audit.success
    def failing(session, action, **kwargs):
        if action == "deletion.accept":
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        return original(session, action, **kwargs)
    monkeypatch.setattr(case.auth.store.audit, "success", failing)
    with pytest.raises(AuthFlowError):
        case.rights.create(case.principal, "deletion", CONFIRM)
    with Session(pg_engine) as session:
        assert session.scalar(select(RightsRequest).where(RightsRequest.kind == "deletion")) is None
        assert session.get(RightsWatermark, 1).sequence == 0
    assert case.ledger.snapshot()[0].sequence == 1
    with pytest.raises(AuthFlowError) as closed:
        case.auth.get_principal(case.owner.cookie)
    assert closed.value.status_code == 503
    monkeypatch.setattr(case.auth.store.audit, "success", original)
    case.guard.replay()
    assert case.rights.context(case.principal).deletion_accepted
    with Session(pg_engine) as session:
        deletion = session.scalar(select(RightsRequest).where(RightsRequest.kind == "deletion"))
        assert deletion.status == "completed" and deletion.scope == {}


def test_accepted_cleanup_survives_disabled_account_and_early_clock_config_drift(rights_case_factory, pg_engine):
    case = rights_case_factory()
    original_clock = case.auth.clock
    case.auth.clock = lambda: original_clock()
    with pytest.raises(AuthFlowError) as clock_drift:
        case.auth.get_principal(case.owner.cookie)
    assert clock_drift.value.status_code == 503
    case.auth.clock = original_clock
    request = case.rights.create(case.principal, "deletion", CONFIRM)
    with Session(pg_engine) as session, session.begin():
        session.execute(update(AuthUser).where(AuthUser.id == case.owner.user_id).values(status="disabled"))
    assert case.rights.run(case.rights.claim(uuid4())).online_cleanup_complete
    with pytest.raises(AuthFlowError):
        case.auth.get_principal(case.owner.cookie)


def test_running_http_factory_blocks_all_traffic_on_missing_latest_anchor(rights_case_factory):
    case = rights_case_factory()
    app = create_rights_v2_app(case.auth.runtime_settings, identity_service=case.auth, profile_service=case.profiles,
        assessment_service=case.eligibility, execution_service=case.execution, rights_service=case.rights)
    with TestClient(app, base_url="https://app.test.invalid") as client:
        identify(client, case.owner)
        assert client.get("/config").status_code == 200  # Inherited public configuration contract.
        anchor = case.ledger.anchor.root / "latest.json"
        data = anchor.read_bytes()
        anchor.unlink()
        for path in ("/config", "/privacy/rights/context", "/auth/session", f"/profiles/{case.profile.profile_id}"):
            safe(client.get(path), 503)
        anchor.write_bytes(data)
        assert safe(client.get("/privacy/rights/context"), 200)["enabled"]
        app.state.rights_service = None
        safe(client.get("/config"), 503)
