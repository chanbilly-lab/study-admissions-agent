"""Actual full history erasure, latest-proof integrity and SQL rollback retries."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from services.api.app.auth.config import AuthFlowError
from services.api.app.plan_revisions.schemas import DecisionInput
from services.api.app.privacy.rights.schemas import OwnerConfirmation, RightsError
from services.api.app.storage.protocol import StorageNamespace
from tests.integration.privacy_rights.test_t40_safety import attach

pytestmark = pytest.mark.postgres
CONFIRM = OwnerConfirmation(owner_confirmed=True)


def test_full_profile_revision_confirmation_completion_replacement_export_and_erasure(rights_revision_case_factory, pg_engine):
    case = rights_revision_case_factory()
    proposal = case.revisions.propose(case.principal, case.request).revision
    case.revisions.decide(case.principal, proposal.revision_id,
        DecisionInput(expected_revision_version=1, action="accept", student_confirmed=True))
    export = case.rights.create(case.principal, "export", CONFIRM)
    assert case.rights.run(case.rights.claim(uuid4())).status == "completed"
    content = json.loads(case.rights.content(case.principal, export.request_id).content_json)
    counts = {value["collection"]: value["row_count"] for value in content["collections"]}
    assert counts["student_profile_versions"] == 2
    assert counts["plan_execution_confirmations"] == counts["plan_task_completions"] == 1
    assert counts["revision_proposals"] == counts["revision_decisions"] == counts["plan_replacement_links"] == 1
    case.rights.create(case.principal, "deletion", CONFIRM)
    assert case.rights.run(case.rights.claim(uuid4())).online_cleanup_complete
    from services.api.app.privacy.rights.resources import registry
    from sqlalchemy import select, func
    with pg_engine.connect() as connection:
        for model, condition in registry(case.owner.user_id):
            assert connection.scalar(select(func.count()).select_from(model).where(condition)) == 0


def test_current_business_and_ledger_heads_and_corrupt_chain_reject(rights_case_factory, pg_engine, schema_pair):
    case = rights_case_factory()
    case.rights.create(case.principal, "deletion", CONFIRM)
    for engine, name in ((pg_engine, "rights_alembic_version"), (schema_pair.ledger, "rights_ledger_alembic_version")):
        with engine.begin() as connection:
            previous = connection.scalar(text("SELECT version_num FROM " + name))
            connection.execute(text("UPDATE " + name + " SET version_num='DEMO_wrong_head'"))
        with pytest.raises(AuthFlowError) as closed:
            case.auth.get_principal(case.owner.cookie)
        assert closed.value.status_code == 503
        with engine.begin() as connection:
            connection.execute(text("UPDATE " + name + " SET version_num=:head"), {"head": previous})
    with schema_pair.ledger.begin() as connection:
        previous = connection.scalar(text("SELECT chain_sha256 FROM privacy_ledger_events WHERE sequence=1"))
        connection.execute(text("ALTER TABLE privacy_ledger_events DISABLE TRIGGER privacy_ledger_events_no_mutation"))
        connection.execute(text("UPDATE privacy_ledger_events SET chain_sha256=:hash WHERE sequence=1"), {"hash": "f" * 64})
        connection.execute(text("ALTER TABLE privacy_ledger_events ENABLE TRIGGER privacy_ledger_events_no_mutation"))
    with pytest.raises(AuthFlowError) as closed:
        case.auth.get_principal(case.owner.cookie)
    assert closed.value.status_code == 503
    with pytest.raises(RightsError):
        case.guard.replay()
    with schema_pair.ledger.begin() as connection:
        connection.execute(text("ALTER TABLE privacy_ledger_events DISABLE TRIGGER privacy_ledger_events_no_mutation"))
        connection.execute(text("UPDATE privacy_ledger_events SET chain_sha256=:hash WHERE sequence=1"), {"hash": previous})
        connection.execute(text("ALTER TABLE privacy_ledger_events ENABLE TRIGGER privacy_ledger_events_no_mutation"))
    assert case.auth.get_principal(case.owner.cookie).user_id == case.owner.user_id


def test_completion_audit_rollback_retries_files_already_physically_erased(rights_case_factory, storage_factory, pg_engine, monkeypatch):
    case = rights_case_factory()
    storage, file, data = attach(case, storage_factory)
    request = case.rights.create(case.principal, "deletion", CONFIRM)
    original = case.auth.store.audit.success
    def fail(session, action, **kwargs):
        if action == "administrator.action" and kwargs.get("object_type") == "deletion_job":
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        return original(session, action, **kwargs)
    monkeypatch.setattr(case.auth.store.audit, "success", fail)
    pending = case.rights.run(case.rights.claim(uuid4()))
    assert pending.status == "queued" and not pending.online_cleanup_complete
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM student_profile_versions WHERE owner_user_id=:owner"),
            {"owner": case.owner.user_id}) == 1
    with pytest.raises(Exception) as absent:
        case.io.read(StorageNamespace.student_private, file.id, len(data), file.sha256)
    assert absent.value.status_code == 404
    monkeypatch.setattr(case.auth.store.audit, "success", original)
    case.clock.advance(1)
    assert case.rights.run(case.rights.claim(uuid4())).online_cleanup_complete
    assert case.rights.get(case.principal, request.request_id, "deletion").online_cleanup_complete


def test_login_rotation_records_exact_previous_session_reduction(rights_case_factory, pg_engine):
    from datetime import timedelta
    from hashlib import sha256
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from services.api.app.auth.models import AuthIdentity, AuthSession
    from services.api.app.auth.schemas import IdentityKey
    case = rights_case_factory()
    key = IdentityKey(issuer="https://demo-t40.invalid/realm", subject="DEMO_T40_ROTATION")
    with Session(pg_engine) as session, session.begin():
        session.add(AuthIdentity(id=uuid4(), user_id=case.owner.user_id, issuer=key.issuer, subject=key.subject, created_at=case.clock()))
        previous = session.get(AuthSession, case.principal.session_id)
        old_digest = previous.session_digest
    digest = sha256(b"DEMO_T40_ONLY_ROTATED_SESSION").hexdigest()
    replacement = case.auth.store.establish_session(key, session_digest=digest, previous_digest=old_digest,
        now=case.clock(), expires_at=case.clock() + timedelta(hours=1), production=False, clock=case.clock)
    proof, events = case.ledger.snapshot()
    assert proof.sequence == 1 and events[0].kind == "session_revoked"
    assert events[0].resource_id == case.principal.session_id
    with pytest.raises(AuthFlowError) as expired:
        case.auth.get_principal(case.owner.cookie)
    assert expired.value.status_code == 401
    assert case.auth.store.read_session(digest, now=case.clock(), production=False).session_id == replacement.session_id
