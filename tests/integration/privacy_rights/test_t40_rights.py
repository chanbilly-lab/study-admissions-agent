"""Two-user owner boundaries, actual files, persistent cleanup and ledger barriers."""
import json
from uuid import uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from services.api.app.privacy.rights.models import RightsRequest
from services.api.app.privacy.rights.schemas import OwnerConfirmation, RightsError
from services.api.app.privacy.rights.resources import registry
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.service import digest_secret

pytestmark = pytest.mark.postgres
CONFIRM = OwnerConfirmation(owner_confirmed=True)


def diagnostic(case):
    """Failure location only: never stringify DB parameters or private input."""
    import traceback
    original = case.rights._failure
    failures = []
    def record(lease, error):
        constraint = getattr(getattr(getattr(error, "orig", None), "diag", None), "constraint_name", None)
        failures.append((type(error).__name__, constraint,
            [(item.name, item.lineno) for item in traceback.extract_tb(error.__traceback__)]))
        return original(lease, error)
    case.rights._failure = record
    return failures


def test_real_export_deletion_logout_cleanup_two_owners(rights_case_factory, actor_factory, pg_engine):
    case = rights_case_factory()
    failures = diagnostic(case)
    other = actor_factory()
    other_principal = case.auth.get_principal(other.cookie)
    export = case.rights.create(case.principal, "export", CONFIRM)
    assert export.status == "queued" and not export.online_cleanup_complete
    with pytest.raises(RightsError) as denied:
        case.rights.get(other_principal, export.request_id, "export")
    assert denied.value.status_code == 404
    lease = case.rights.claim(uuid4())
    result = case.rights.run(lease)
    assert result.status == "completed", result
    content = case.rights.content(case.principal, export.request_id)
    payload = json.loads(content.content_json)
    assert payload["owner_user_id"] == str(case.owner.user_id)
    assert any(item["collection"] == "student_profile_versions" and item["row_count"] == 1 for item in payload["collections"])
    assert str(other.user_id) not in content.content_json
    assert case.owner.cookie.get_secret_value() not in content.content_json
    deletion = case.rights.create(case.principal, "deletion", CONFIRM)
    assert deletion.status == "queued" and not deletion.online_cleanup_complete
    assert case.rights.create(case.principal, "deletion", CONFIRM).request_id == deletion.request_id
    with pytest.raises(Exception) as stopped:
        case.profiles.get_profile(case.principal, case.profile.profile_id)
    assert stopped.value.status_code in {403, 503}
    csrf = case.auth.get_csrf_token(case.owner.cookie)
    case.auth.logout(case.owner.cookie, csrf.token)
    lease = case.rights.claim(uuid4())
    completed = case.rights.run(lease)
    assert completed.status == "completed" and completed.online_cleanup_complete, failures
    with Session(pg_engine) as session:
        for model, condition in registry(case.owner.user_id):
            assert session.scalar(select(model).where(condition).limit(1)) is None, model.__tablename__
        row = session.get(RightsRequest, deletion.request_id)
        assert row.scope == {} and row.session_id is None
    assert case.auth.get_principal(other.cookie).user_id == other.user_id
    with pytest.raises(AuthFlowError):
        case.auth.get_principal(case.owner.cookie)


def test_core_withdrawal_keeps_owner_rights_and_journals_exact_consent(rights_case_factory, pg_engine):
    case = rights_case_factory()
    failures = diagnostic(case)
    privacy = case.profiles.privacy_service
    admitted = privacy.get_admission(case.principal)
    privacy.withdraw_core(case.principal, admitted.consent_id)
    proof, events = case.ledger.snapshot()
    assert proof.sequence == 1 and events[0].kind == "core_withdrawn" and events[0].resource_id == admitted.consent_id
    export = case.rights.create(case.principal, "export", CONFIRM)
    result = case.rights.run(case.rights.claim(uuid4()))
    assert result.status == "completed", result
    assert case.rights.content(case.principal, export.request_id).size_bytes > 0
    deletion = case.rights.create(case.principal, "deletion", CONFIRM)
    assert case.rights.run(case.rights.claim(uuid4())).online_cleanup_complete, failures
    assert deletion.online_cleanup_due_at is not None
