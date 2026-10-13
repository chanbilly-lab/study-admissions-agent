"""Actual pg_dump/pg_restore A→B and private-file restoration, not an in-memory copy.

Only this fixture's random business schema is dropped/restored. Ledger schema
and signed latest anchor remain outside the backup and are never overwritten.
"""
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.grants.schemas import AcceptGrantInput, SharingSettings
from services.api.app.auth.grants.service import SharingService
from services.api.app.auth.grants.policy import POLICY_HASH, POLICY_VERSION
from services.api.app.auth.models import AuthOwnedResource, AuthUserRole
from services.api.app.privacy.rights.models import RightsRequest
from services.api.app.privacy.rights.schemas import OwnerConfirmation, RightsError
from services.api.app.profiles.schemas import CreateInput
from services.api.app.storage.protocol import StorageNamespace
from tests.integration.privacy_rights.test_t40_safety import attach, admitted
from tests.integration.profiles.conftest import snapshot_payload

pytestmark = pytest.mark.postgres
CONFIRM = OwnerConfirmation(owner_confirmed=True)
PG_BIN = Path("D:/Projects/study/.cache/t01-postgres/runtime/pgsql/bin")


def pg_tool(name, case, schema_pair, path, *, restore=False):
    assert name in {"pg_dump", "pg_restore"} and path.is_absolute() and path.parent.is_dir()
    assert re.fullmatch(r"rights_t40_[0-9a-f]{32}", schema_pair.business_schema)
    assert re.fullmatch(r"ledger_t40_[0-9a-f]{32}", schema_pair.ledger_schema)
    assert schema_pair.business_schema != schema_pair.ledger_schema
    url = schema_pair.business.url
    assert url.host == "127.0.0.1" and url.port == 55438 and url.database == "study_t23_20261003"
    executable = PG_BIN / (name + ".exe")
    assert executable.is_file()
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("PG")}
    environment["PGPASSWORD"] = url.password
    command = [str(executable), "--host", url.host, "--port", str(url.port), "--username", url.username,
        "--dbname", url.database, "--no-password"]
    if restore:
        command += ["--exit-on-error", "--no-owner", "--no-privileges", str(path)]
    else:
        command += ["--schema", schema_pair.business_schema, "--format", "custom", "--file", str(path), "--no-owner", "--no-privileges"]
    result = subprocess.run(command, env=environment, capture_output=True, timeout=60)
    # Never expose credentials, SQL parameters, raw stderr or private payloads.
    assert result.returncode == 0, (name, "actual command failed", result.returncode)
    return result.returncode


def test_actual_business_and_file_backup_restoration_requires_latest_external_replay(rights_case_factory,
        storage_factory, actor_factory, pg_engine, schema_pair, tmp_path):
    case = rights_case_factory()
    storage, private_file, private_bytes = attach(case, storage_factory)
    foreign = actor_factory()
    foreign_principal = admitted(case, foreign)
    foreign_profile = case.profiles.create_profile(foreign_principal, CreateInput(profile=snapshot_payload(), confirmed=True), SecretStr("DEMO_T40_RESTORE_CONTROL"))
    case.auth.store.assign_role(foreign.user_id, "operations", now=case.clock())
    sharing = SharingService(case.auth, case.profiles.privacy_service, SharingSettings(fixture_mode=True))
    from services.api.app.auth.grants.schemas import CreateGrantInput
    with Session(pg_engine) as session:
        resource = session.get(AuthOwnedResource, case.profile.profile_id)
        resource_version = resource.version
    state = sharing.list_grants(case.principal)
    created = sharing.create_grant(case.principal, CreateGrantInput(resource_type="profile",
        resource_id=case.profile.profile_id, expected_resource_version=resource_version, grantee_user_id=foreign.user_id,
        fields=["status"], actions=["read"], expires_at=case.clock() + timedelta(seconds=600), confirmed=True,
        expected_revision=state.revision, owner_consent_id=state.owner_consent_id,
        sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))
    accepted = sharing.accept_grant(foreign_principal, created.grant.id, AcceptGrantInput(confirmed=True,
        expected_version=created.grant.version, sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))
    export = case.rights.create(case.principal, "export", CONFIRM)
    assert case.rights.run(case.rights.claim(uuid4())).status == "completed"
    with Session(pg_engine) as session:
        exported = session.get(RightsRequest, export.request_id)
        artifact = (exported.artifact_id, exported.artifact_size, exported.artifact_sha256)
    artifact_bytes = case.io.read(StorageNamespace.student_private, *artifact)
    # Actual local backup files, with original bytes/hash rechecked on read.
    file_backup = tmp_path / "DEMO_private_A.bin"
    artifact_backup = tmp_path / "DEMO_export_A.json"
    file_backup.write_bytes(private_bytes)
    artifact_backup.write_bytes(artifact_bytes)
    dump = tmp_path / "DEMO_business_A.dump"
    assert pg_tool("pg_dump", case, schema_pair, dump) == 0
    assert dump.stat().st_size > 0
    original_ledger_proof = case.ledger.snapshot()[0]
    original_anchor = (case.ledger.anchor.root / "latest.json").read_bytes()
    assert original_ledger_proof.sequence == 0
    case.rights.register_backup(sha256(dump.read_bytes()).hexdigest(), captured_at=case.clock(), expires_at=case.clock() + timedelta(days=35))

    # All B reductions are journalled by existing real services, not by a test DTO.
    sharing.revoke_grant(case.principal, accepted.grant.id)
    privacy = case.profiles.privacy_service
    privacy.withdraw_core(case.principal, privacy.get_admission(case.principal).consent_id)
    case.auth.store.revoke_role(foreign.user_id, "operations", now=case.clock())
    deletion = case.rights.create(case.principal, "deletion", CONFIRM)
    csrf = case.auth.get_csrf_token(case.owner.cookie)
    case.auth.logout(case.owner.cookie, csrf.token)
    assert case.rights.run(case.rights.claim(uuid4())).online_cleanup_complete
    latest, events = case.ledger.snapshot()
    assert latest.sequence == 5 and {event.kind for event in events} == {"grant_revoked", "core_withdrawn", "role_revoked", "owner_deleted", "session_revoked"}
    latest_anchor = (case.ledger.anchor.root / "latest.json").read_bytes()
    assert latest_anchor != original_anchor
    ledger_dump = tmp_path / "DEMO_ledger_B_proof.json"
    ledger_dump.write_bytes(json.dumps(latest.model_dump(mode="json"), sort_keys=True).encode())
    with schema_pair.admin.connect() as connection:
        before_ledger_rows = connection.execute(text(f'SELECT count(*) FROM "{schema_pair.ledger_schema}".privacy_ledger_events')).scalar_one()
    # Only the explicit, validated fixture schema can be dropped.
    assert re.fullmatch(r"rights_t40_[0-9a-f]{32}", schema_pair.business_schema)
    schema_pair.business.dispose()
    with schema_pair.admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema_pair.business_schema}" CASCADE'))
    assert pg_tool("pg_restore", case, schema_pair, dump, restore=True) == 0
    case.io.write(StorageNamespace.student_private, private_file.id, file_backup.read_bytes())
    case.io.write(StorageNamespace.student_private, artifact[0], artifact_backup.read_bytes())
    assert case.io.read(StorageNamespace.student_private, private_file.id, private_file.size_bytes, private_file.sha256) == private_bytes
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM student_profiles WHERE owner_user_id=:owner"), {"owner": case.owner.user_id}).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM auth_sessions WHERE id=:session AND revoked_at IS NULL"), {"session": case.owner.session_id}).scalar_one() == 1
    # Restored A cannot use its formerly valid session or current-principal reference.
    with pytest.raises(AuthFlowError) as closed:
        case.auth.get_principal(case.owner.cookie)
    assert closed.value.status_code == 503
    with pytest.raises(Exception) as direct:
        case.profiles.get_profile(case.principal, case.profile.profile_id)
    assert direct.value.status_code == 503
    with pytest.raises(AuthFlowError):
        case.auth.get_principal(foreign.cookie)
    anchor = case.ledger.anchor.root / "latest.json"
    anchor.unlink()
    with pytest.raises(RightsError):
        case.guard.replay()
    anchor.write_bytes(original_anchor)
    with pytest.raises(RightsError):
        case.guard.replay()  # A valid old signature is still stale.
    anchor.write_bytes(b'{"proof":{},"signature":"DEMO_TAMPERED"}')
    with pytest.raises(RightsError):
        case.guard.replay()
    anchor.write_bytes(latest_anchor)
    assert case.guard.replay() == latest
    assert case.guard.replay() == latest  # Explicit replay is idempotent.
    with pytest.raises(AuthFlowError) as logged_out:
        case.auth.get_principal(case.owner.cookie)
    assert logged_out.value.status_code == 401
    current_foreign = case.auth.get_principal(foreign.cookie)
    assert "operations" not in current_foreign.roles and "student" in current_foreign.roles
    assert case.profiles.get_profile(current_foreign, foreign_profile.version.profile_id).profile_id == foreign_profile.version.profile_id
    with Session(pg_engine) as session:
        row = session.get(RightsRequest, deletion.request_id)
        assert row.status == "completed" and row.scope == {} and row.session_id is None
        assert session.execute(text("SELECT count(*) FROM student_profiles WHERE owner_user_id=:owner"), {"owner": case.owner.user_id}).scalar_one() == 0
        assert session.execute(text("SELECT count(*) FROM idempotency_records WHERE actor_user_id=:owner AND operation='profile.create'"), {"owner": case.owner.user_id}).scalar_one() == 0
        last_admission = session.execute(text("SELECT consent_status FROM privacy_admission_records WHERE user_id=:owner ORDER BY revision DESC LIMIT 1"), {"owner": case.owner.user_id}).scalar_one()
        assert last_admission == "withdrawn"
    for identifier, size, digest in ((private_file.id, private_file.size_bytes, private_file.sha256), artifact):
        with pytest.raises(Exception) as missing:
            case.io.read(StorageNamespace.student_private, identifier, size, digest)
        assert missing.value.status_code == 404
    with schema_pair.admin.connect() as connection:
        assert connection.execute(text(f'SELECT count(*) FROM "{schema_pair.ledger_schema}".privacy_ledger_events')).scalar_one() == before_ledger_rows
    assert case.ledger.snapshot()[0] == latest and anchor.read_bytes() == latest_anchor
