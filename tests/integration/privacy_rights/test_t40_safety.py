"""Real private files, bounded failure states, fencing and database constraints."""
from base64 import b64decode
from datetime import timedelta
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.auth.config import AuthFlowError
from services.api.app.privacy.rights.models import RightsRequest, RightsAttempt, RightsWatermark
from services.api.app.privacy.rights.schemas import OwnerConfirmation, RightsError, RightsPolicy
from services.api.app.privacy.rights.service import RightsService
from services.api.app.storage.protocol import StorageNamespace
from services.api.app.profiles.schemas import CreateInput
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from tests.integration.profiles.conftest import snapshot_payload
from tests.integration.privacy_rights.test_t40_rights import diagnostic

pytestmark = pytest.mark.postgres
CONFIRM = OwnerConfirmation(owner_confirmed=True)


def attach(case, storage_factory, data=b'{"DEMO_T40":"synthetic private bytes"}'):
    storage = storage_factory()
    row = storage.upload_private(case.principal, parent_kind="profile", parent_resource_id=case.profile.profile_id,
        filename="DEMO_T40.json", content_type="application/json", data=data)
    return storage, row, data


def admitted(case, actor):
    principal = case.auth.get_principal(actor.cookie)
    privacy = case.profiles.privacy_service
    declaration = privacy.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=privacy.settings.notice_id, expected_revision=0))
    privacy.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=declaration.notice_id, expected_revision=declaration.revision))
    return principal


def test_real_files_foreign_profile_private_idempotency_export_and_retry(rights_case_factory, storage_factory, actor_factory, pg_engine):
    case = rights_case_factory(withdraw=True)
    failures = diagnostic(case)
    # Actual opted-in notification and immutable change impacts are included.
    from tests.integration.jobs.test_t36_store import drain
    drain(case)
    storage, file, data = attach(case, storage_factory)
    foreign = actor_factory()
    foreign_principal = admitted(case, foreign)
    foreign_payload = snapshot_payload()
    foreign_payload["assessments"]["gaokao_total"]["achieved"]["value"] = "731.125"
    foreign_profile = case.profiles.create_profile(foreign_principal, CreateInput(profile=foreign_payload, confirmed=True), SecretStr("DEMO_T40_FOREIGN"))
    export = case.rights.create(case.principal, "export", CONFIRM)
    assert case.rights.run(case.rights.claim(uuid4())).status == "completed", failures
    artifact = case.rights.content(case.principal, export.request_id)
    parsed = json.loads(artifact.content_json)
    assert b64decode(parsed["attachments"][0]["content_base64"], validate=True) == data
    assert parsed["attachments"][0]["sha256"] == sha256(data).hexdigest()
    assert "731.125" not in artifact.content_json and str(foreign.user_id) not in artifact.content_json
    assert case.owner.cookie.get_secret_value() not in artifact.content_json
    assert "session_digest" not in artifact.content_json and "csrf" not in artifact.content_json
    assert "session_id" not in artifact.content_json and "lease_token" not in artifact.content_json
    with Session(pg_engine) as session:
        saved_export = session.get(RightsRequest, export.request_id)
        artifact_id = saved_export.artifact_id
        captured_source_files = session.execute(text("SELECT id, sha256 FROM storage_objects WHERE namespace='source_quarantine' ORDER BY id")).all()
        assert session.execute(text("SELECT count(*) FROM idempotency_records WHERE actor_user_id=:owner AND operation='profile.create'"), {"owner": case.owner.user_id}).scalar_one() == 1
    deletion = case.rights.create(case.principal, "deletion", CONFIRM)
    case.io.fail_delete = True
    pending = case.rights.run(case.rights.claim(uuid4()))
    assert pending.status == "queued" and pending.reason == "RETRYABLE_FAILURE" and not pending.online_cleanup_complete
    with Session(pg_engine) as session:
        assert session.execute(text("SELECT count(*) FROM student_profile_versions WHERE owner_user_id=:owner"), {"owner": case.owner.user_id}).scalar_one() == 1
    case.io.fail_delete = False
    case.clock.advance(1)
    done = case.rights.run(case.rights.claim(uuid4()))
    assert done.online_cleanup_complete, failures
    for identifier in (file.id, artifact_id):
        with pytest.raises(Exception) as missing:
            case.io.read(StorageNamespace.student_private, identifier, 1, "0" * 64)
        assert missing.value.status_code == 404
    current_foreign = case.profiles.get_profile(foreign_principal, foreign_profile.version.profile_id)
    assert current_foreign.profile.assessments["gaokao_total"].achieved.value == "731.125"
    with Session(pg_engine) as session:
        assert session.execute(text("SELECT count(*) FROM idempotency_records WHERE actor_user_id=:owner AND operation IN ('profile.create','plan.confirm')"), {"owner": case.owner.user_id}).scalar_one() == 0
        assert session.execute(text("SELECT count(*) FROM inbox_notifications WHERE owner_user_id=:owner"), {"owner": case.owner.user_id}).scalar_one() == 0
        assert session.execute(text("SELECT id, sha256 FROM storage_objects WHERE namespace='source_quarantine' ORDER BY id")).all() == captured_source_files
        erased = session.execute(text("SELECT assessment_count,plan_count FROM rights_erased_impact_counts WHERE event_id=:event"), {"event": case.event_id}).one()
        assert erased == (1, 1)
        receipt = session.execute(text("SELECT assessment_count,plan_count FROM change_event_receipts WHERE event_id=:event"), {"event": case.event_id}).one()
        assert receipt == erased
    assert case.changes.process_event(case.event_id).replayed  # Original public receipt remains valid.
    with pytest.raises(AuthFlowError) as deleted_export:
        case.rights.content(case.principal, export.request_id)
    assert deleted_export.value.status_code == 403
    assert case.rights.get(case.principal, deletion.request_id, "deletion").online_cleanup_complete


def test_export_limit_fails_without_partial_artifact_and_logout_cancels(rights_case_factory, pg_engine):
    case = rights_case_factory(policy=RightsPolicy(enabled=True, allow_test_rights=True, max_export_bytes=32))
    request = case.rights.create(case.principal, "export", CONFIRM)
    result = case.rights.run(case.rights.claim(uuid4()))
    assert result.status == "failed" and result.reason == "EXPORT_LIMIT"
    with Session(pg_engine) as session:
        assert session.get(RightsRequest, request.request_id).artifact_id is None
    another = case.rights.create(case.principal, "export", CONFIRM)
    csrf = case.auth.get_csrf_token(case.owner.cookie)
    case.auth.logout(case.owner.cookie, csrf.token)
    cancelled = case.rights.run(case.rights.claim(uuid4()))
    assert cancelled.request_id == another.request_id and cancelled.status == "cancelled"
    assert cancelled.reason == "AUTHORITY_REVOKED"


def test_expired_lease_fencing_and_bounded_exhaustion_persist(rights_case_factory, pg_engine):
    case = rights_case_factory(policy=RightsPolicy(enabled=True, allow_test_rights=True, lease_seconds=1, max_attempts=2))
    request = case.rights.create(case.principal, "deletion", CONFIRM)
    first = case.rights.claim(uuid4())
    case.clock.advance(1)
    second = case.rights.claim(uuid4())
    assert second.generation == 2 and second.request_id == first.request_id
    with pytest.raises(RightsError) as late:
        case.rights.run(first)
    assert late.value.status_code == 409
    case.clock.advance(1)
    assert case.rights.claim(uuid4()) is None
    result = case.rights.get(case.principal, request.request_id, "deletion")
    assert result.status == "failed" and result.reason == "ATTEMPTS_EXHAUSTED" and not result.online_cleanup_complete
    with Session(pg_engine) as session:
        assert session.get(RightsAttempt, (request.request_id, 2)).outcome == "failed"
    # Explicit trusted policy extension is finite, and preserves the original authority.
    extended = RightsService(case.auth, case.rights.store, case.guard,
        RightsPolicy(enabled=True, allow_test_rights=True, lease_seconds=1, max_attempts=3))
    extended.retry_deletion(request.request_id)
    done = extended.run(extended.claim(uuid4()))
    assert done.online_cleanup_complete and done.attempts == 3


def test_same_schema_engine_substitution_missing_anchor_and_guard_removal_close(rights_case_factory, pg_engine, schema_pair):
    case = rights_case_factory()
    original = case.auth.store.rights_guard
    case.auth.store.rights_guard = None
    with pytest.raises(AuthFlowError) as missing:
        case.auth.get_principal(case.owner.cookie)
    assert missing.value.status_code == 503
    case.auth.store.rights_guard = original
    path = case.ledger.anchor.root / "latest.json"
    data = path.read_bytes()
    path.unlink()
    with pytest.raises(AuthFlowError) as blocked:
        case.auth.get_principal(case.owner.cookie)
    assert blocked.value.status_code == 503
    path.write_bytes(data)
    assert case.auth.get_principal(case.owner.cookie).user_id == case.owner.user_id
    from services.api.app.privacy.rights.guard import RightsGuard
    from services.api.app.privacy.rights.ledger import ExternalLedger
    from sqlalchemy import create_engine
    duplicate = create_engine(pg_engine.url, hide_parameters=True,
        connect_args={"options": "-csearch_path=" + schema_pair.business_schema})
    try:
        same_schema_ledger = ExternalLedger(duplicate, case.ledger.anchor)
        invalid = RightsGuard(pg_engine, same_schema_ledger, case.io, clock=case.auth.clock)
        with pytest.raises(RightsError):
            with Session(pg_engine) as session, session.begin():
                invalid.ensure_business(session)
    finally:
        duplicate.dispose()


def test_database_authority_scope_backup_caps_and_migration_idempotence(rights_case_factory, pg_engine, schema_pair):
    case = rights_case_factory()
    from services.api.app.privacy.rights.store import HEADS, migrate
    migrate(pg_engine)
    migrate(schema_pair.ledger, ledger=True)
    case.rights.store.assert_schema_ready()
    case.ledger.assert_schema_ready()
    request = case.rights.create(case.principal, "deletion", CONFIRM)
    for statement, values in (("UPDATE privacy_rights_requests SET owner_user_id=:other WHERE id=:id", {"other": uuid4(), "id": request.request_id}),
        ("UPDATE privacy_rights_requests SET scope='{}'::jsonb WHERE id=:id", {"id": request.request_id})):
        with pytest.raises(IntegrityError), pg_engine.begin() as connection:
            connection.execute(text(statement), values)
    with pytest.raises(IntegrityError), schema_pair.ledger.begin() as connection:
        connection.execute(text("DELETE FROM privacy_ledger_events"))
    with pg_engine.connect() as connection:
        for table, head in HEADS.items():
            assert connection.execute(text("SELECT version_num FROM " + table)).scalars().all() == [head]
    backup = case.rights.register_backup("a" * 64, captured_at=case.clock(), expires_at=case.clock() + timedelta(days=35))
    assert backup.version == 4
    with pytest.raises(RightsError):
        case.rights.register_backup("a" * 64, captured_at=case.clock(), expires_at=case.clock() + timedelta(days=36))
