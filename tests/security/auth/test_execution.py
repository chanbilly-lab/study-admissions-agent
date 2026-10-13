"""Queued identity references must revalidate current state and explicit permission."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from .conftest import SENSITIVE


pytestmark = pytest.mark.postgres


def test_execution_reference_contains_only_server_session_and_owner(auth_service, logged_in, active_account):
    reference = auth_service.create_execution_reference(logged_in)
    assert set(reference.model_dump()) == {"session_id", "user_id"}
    assert reference.user_id == active_account and reference.session_id != reference.user_id
    assert logged_in not in reference.model_dump_json() + repr(reference)
    checked = auth_service.revalidate_execution(reference, permission_verifier=lambda current: current.user_id == active_account)
    assert checked.user_id == active_account
    effects = []
    result = auth_service.execute_authenticated(reference, lambda current: effects.append(current.user_id) or "done",
        permission_verifier=lambda current: current.user_id == active_account)
    assert result == "done" and effects == [active_account]


@pytest.mark.parametrize("permission", [None, False, 1, "true"], ids=["missing", "denied", "truthy-number", "truthy-string"])
def test_execution_permission_is_explicit_and_strict_true(auth_service, logged_in, permission):
    from services.api.app.auth.config import AuthFlowError

    reference = auth_service.create_execution_reference(logged_in)
    verifier = None if permission is None else lambda current: permission
    effects = []
    with pytest.raises(AuthFlowError) as caught:
        auth_service.execute_authenticated(reference, lambda current: effects.append("unsafe"),
            permission_verifier=verifier)
    assert caught.value.status_code == 403 and effects == []


@pytest.mark.parametrize("field", ["user_id", "session_id"])
def test_execution_reference_tampering_cannot_select_another_owner(auth_service, logged_in, field):
    from services.api.app.auth.config import AuthFlowError

    reference = auth_service.create_execution_reference(logged_in).model_copy(update={field: uuid4()})
    effects = []
    with pytest.raises(AuthFlowError):
        auth_service.execute_authenticated(reference, lambda current: effects.append("unsafe"),
            permission_verifier=lambda current: True)
    assert effects == []


@pytest.mark.parametrize("change", ["disable", "revoke", "expire"])
def test_execution_queued_before_revocation_reads_fresh_database_state(
    auth_service, logged_in, active_account, pg_engine, clock, session_settings, change,
):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.models import AuthSession, AuthUser

    reference = auth_service.create_execution_reference(logged_in)
    if change == "expire":
        clock.advance(session_settings.session_ttl_seconds)
    else:
        with Session(pg_engine) as database, database.begin():
            if change == "disable":
                database.get(AuthUser, active_account).status = "disabled"
            else:
                database.get(AuthSession, reference.session_id).revoked_at = clock()
    effects = []
    with pytest.raises(AuthFlowError):
        auth_service.execute_authenticated(reference, lambda current: effects.append("unsafe"),
            permission_verifier=lambda current: True)
    assert effects == []


def test_permission_revocation_after_enqueue_cannot_use_cached_allow(auth_service, logged_in):
    from services.api.app.auth.config import AuthFlowError

    reference = auth_service.create_execution_reference(logged_in)
    permissions = {"allowed": True}
    verifier = lambda current: permissions["allowed"]
    assert auth_service.revalidate_execution(reference, permission_verifier=verifier)
    permissions["allowed"] = False
    effects = []
    with pytest.raises(AuthFlowError) as caught:
        auth_service.execute_authenticated(reference, lambda current: effects.append("unsafe"), permission_verifier=verifier)
    assert caught.value.status_code == 403 and effects == []


def test_expiry_during_permission_check_prevents_operation(auth_service, logged_in, clock, session_settings):
    from services.api.app.auth.config import AuthFlowError

    reference = auth_service.create_execution_reference(logged_in)
    effects = []

    def slow_permission(current):
        clock.advance(session_settings.session_ttl_seconds)
        return True

    with pytest.raises(AuthFlowError):
        auth_service.execute_authenticated(reference, lambda current: effects.append("unsafe"),
            permission_verifier=slow_permission)
    assert effects == []


def test_internal_proof_errors_are_safe_and_do_not_escape(auth_service, logged_in):
    from services.api.app.auth.config import AuthFlowError

    for proof in (SENSITIVE, SENSITIVE + "\ud800", ""):
        with pytest.raises(AuthFlowError) as caught:
            auth_service.verify_csrf(logged_in, proof)
        assert SENSITIVE not in str(caught.value) + repr(caught.value)
