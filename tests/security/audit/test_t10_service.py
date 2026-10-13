"""T10 transaction integration and calendar retention on isolated PostgreSQL."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.audit.context import request_context
from services.api.app.audit.models import AuditEvent
from services.api.app.audit.retention import expires_after_months
from services.api.app.audit.schemas import AuditEventInput
from services.api.app.audit.service import AuditError
from services.api.app.auth.authorization import Authorizer, AuthorizationError
from services.api.app.auth.models import AuthOwnedResource, AuthSession
from services.api.app.auth.store import migrate_auth, migration_config
from services.api.app.privacy.errors import PrivacyError
from services.api.app.privacy.models import PrivacyAdmissionRecord
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput


def events(engine, action=None):
    with Session(engine) as session:
        query = select(AuditEvent)
        if action is not None:
            query = query.where(AuditEvent.action == action)
        return session.scalars(query.order_by(AuditEvent.occurred_at, AuditEvent.id)).all()


def count(engine, model):
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model))


@pytest.mark.postgres
def test_incremental_migration_keeps_accounts_and_old_chain(auth_store, actor_factory):
    actor = actor_factory()
    prior = count(auth_store.engine, AuditEvent)
    migrate_auth(auth_store.engine)
    auth_store.assert_schema_ready()
    assert count(auth_store.engine, AuditEvent) == prior
    assert inspect(auth_store.engine).get_foreign_keys("auth_audit_events") == []
    with auth_store.engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM auth_alembic_version")) == "0006_audit_t10"
        assert connection.scalar(text("SELECT count(*) FROM auth_users")) == 1
    config = migration_config()
    with auth_store.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0005_shared_grants_t09")
    assert "auth_audit_events" not in inspect(auth_store.engine).get_table_names()
    with Session(auth_store.engine) as session:
        assert session.get(AuthSession, actor.session_id) is not None
    migrate_auth(auth_store.engine)
    auth_store.assert_schema_ready()


@pytest.mark.postgres
def test_business_and_audit_share_commit_or_rollback(auth_service, actor_factory):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    authorizer = Authorizer(auth_service)
    resource_id = uuid4()
    before = count(auth_service.store.engine, AuditEvent)
    with pytest.raises(RuntimeError):
        with Session(auth_service.store.engine) as session, session.begin():
            authorizer.register_owned(principal, "profile", resource_id=resource_id, session=session)
            assert session.get(AuthOwnedResource, resource_id) is not None
            raise RuntimeError("T10_SYNTHETIC_ROLLBACK_SENTINEL")
    assert count(auth_service.store.engine, AuditEvent) == before
    with Session(auth_service.store.engine) as session:
        assert session.get(AuthOwnedResource, resource_id) is None
    with Session(auth_service.store.engine) as session, session.begin():
        authorizer.register_owned(principal, "profile", resource_id=resource_id, session=session)
    recorded = events(auth_service.store.engine, "authorization.owned.register")
    assert len(recorded) == 1 and recorded[0].object_id == resource_id


@pytest.mark.postgres
def test_required_audit_failure_rolls_back_registry(auth_service, actor_factory, monkeypatch):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    resource_id = uuid4()
    def unavailable(*args, **kwargs):
        raise AuditError(503)
    monkeypatch.setattr(auth_service.store.audit, "success", unavailable)
    with pytest.raises(AuthorizationError) as error:
        Authorizer(auth_service).register_owned(principal, "profile", resource_id=resource_id)
    assert error.value.status_code == 503
    with Session(auth_service.store.engine) as session:
        assert session.get(AuthOwnedResource, resource_id) is None
    failures = events(auth_service.store.engine, "authorization.owned.register")
    assert len(failures) == 1 and failures[0].outcome == "failed"
    assert failures[0].object_id is None and failures[0].object_version is None


@pytest.mark.postgres
def test_foreign_object_denial_keeps_only_verified_actor(auth_service, actor_factory, resource_factory):
    first, second = actor_factory(), actor_factory()
    resource = resource_factory(first)
    principal = auth_service.get_principal(second.cookie)
    with request_context("a" * 32), pytest.raises(AuthorizationError) as error:
        Authorizer(auth_service).require_owned(principal, "profile", resource.id)
    assert error.value.status_code == 404
    denied = [item for item in events(auth_service.store.engine, "authorization.owned.check") if item.outcome == "denied"]
    assert len(denied) == 1
    assert denied[0].actor_user_id == second.user_id
    assert denied[0].actor_session_id == second.session_id
    assert denied[0].object_id is None and denied[0].request_id == "a" * 32


@pytest.mark.postgres
def test_supplied_transaction_failure_never_opens_failure_writer(auth_service, actor_factory, monkeypatch):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    authorizer = Authorizer(auth_service)
    calls = []
    monkeypatch.setattr(auth_service.store.audit, "failure", lambda *a, **kw: calls.append(a))
    with Session(auth_service.store.engine) as session, session.begin():
        with pytest.raises(AuthorizationError):
            authorizer.register_owned(principal, "attachment", parent_id=uuid4(), session=session)
    assert calls == []


@pytest.mark.postgres
def test_positional_privacy_guard_failure_defers_to_outer_transaction(auth_service, actor_factory, privacy_service, monkeypatch):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    calls = []
    monkeypatch.setattr(auth_service.store.audit, "failure", lambda *a, **kw: calls.append(a))
    with Session(auth_service.store.engine) as session, session.begin():
        with pytest.raises(PrivacyError):
            privacy_service.require_purpose(session, principal, "core_consultation")
    assert calls == []


@pytest.mark.postgres
def test_failure_diagnostic_never_masks_original_error(auth_service, actor_factory, monkeypatch):
    principal = auth_service.get_principal(actor_factory().cookie)
    def failure(*args, **kwargs):
        raise RuntimeError("T10_SYNTHETIC_DIAGNOSTIC_SENTINEL")
    monkeypatch.setattr(auth_service.store.audit, "failure", failure)
    with pytest.raises(AuthorizationError) as error:
        Authorizer(auth_service).require_owned(principal, "profile", uuid4())
    assert error.value.status_code == 404
    assert "SENTINEL" not in str(error.value)


@pytest.mark.postgres
def test_adult_confirmation_withdrawal_and_committed_invalidation_events(auth_service, actor_factory, privacy_service):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    current = privacy_service.get_admission(principal)
    adult = privacy_service.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=current.notice_id, expected_revision=current.revision))
    consent = privacy_service.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=adult.notice_id, expected_revision=adult.revision))
    privacy_service.withdraw_core(principal, consent.consent_id)
    with pytest.raises(PrivacyError):
        privacy_service.declare_age(principal, AgeDeclarationInput(age_band="under_14", confirmed=True,
            notice_id=adult.notice_id, expected_revision=0))
    for action in ("privacy.adult.declare", "privacy.core.confirm", "privacy.core.withdraw", "privacy.admission.invalidate"):
        assert any(item.outcome == "succeeded" and item.actor_user_id == actor.user_id
                   for item in events(auth_service.store.engine, action))
    with Session(auth_service.store.engine) as session:
        latest = session.scalar(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == actor.user_id)
            .order_by(PrivacyAdmissionRecord.revision.desc()))
        assert latest.age_band is None


@pytest.mark.postgres
def test_grant_lifecycle_and_metadata_read_events(accepted_grant_factory, sharing_service, auth_service):
    owner, recipient, resource, grant = accepted_grant_factory()
    receiver = auth_service.get_principal(recipient.cookie)
    assert sharing_service.require_shared(receiver, "profile", resource.id, ("status",)).status == "active"
    sharing_service.revoke_grant(auth_service.get_principal(owner.cookie), grant.id)
    for action in ("sharing.grant.create", "sharing.grant.accept", "sharing.read", "sharing.grant.revoke"):
        assert any(item.outcome == "succeeded" for item in events(auth_service.store.engine, action))
    records = events(auth_service.store.engine)
    assert all(item.request_id and len(item.request_id) == 32 and item.is_synthetic for item in records)
    assert all("payload" not in item.__dict__ and "subject" not in item.__dict__ for item in records)


@pytest.mark.postgres
def test_role_events_are_system_traces_not_authority(auth_service, actor_factory, clock):
    actor = actor_factory()
    auth_service.store.revoke_role(actor.user_id, "student", now=clock())
    records = events(auth_service.store.engine, "auth.role.assign") + events(auth_service.store.engine, "auth.role.revoke")
    assert len(records) == 2
    assert all(item.actor_kind == "system" and item.actor_user_id is None and item.actor_session_id is None for item in records)
    assert all(item.object_type == "user" and item.object_id == actor.user_id for item in records)


@pytest.mark.postgres
@pytest.mark.parametrize("role", [None, "student", "data_admin", "operations"])
def test_reader_and_cleanup_default_deny_without_assurance(audit_service, auth_service, actor_factory, role):
    principal = auth_service.get_principal(actor_factory(role=role).cookie)
    for operation in (audit_service.list_events, audit_service.purge_expired):
        with pytest.raises(AuthorizationError) as error:
            operation(principal)
        assert error.value.status_code == 403


@pytest.mark.postgres
def test_logout_audit_failure_keeps_current_session(auth_service, actor_factory, monkeypatch):
    actor = actor_factory()
    token = auth_service.get_csrf_token(actor.cookie).token
    original = auth_service.store.audit.success
    def unavailable(*args, **kwargs):
        raise AuditError(503)
    monkeypatch.setattr(auth_service.store.audit, "success", unavailable)
    with pytest.raises(AuditError):
        auth_service.logout(actor.cookie, token)
    assert auth_service.get_session(actor.cookie).user_id == actor.user_id
    monkeypatch.setattr(auth_service.store.audit, "success", original)
    auth_service.logout(actor.cookie, token)
    assert len([item for item in events(auth_service.store.engine, "auth.logout") if item.outcome == "succeeded"]) == 1


@pytest.mark.postgres
@pytest.mark.parametrize("field,value", [("action", "T10_SECRET_ACTION"), ("reason_code", "T10_SECRET_REASON"),
    ("object_type", "T10_SECRET_TYPE")])
def test_database_fixed_whitelists(auth_store, clock, field, value):
    values = dict(id=uuid4(), occurred_at=clock(), actor_kind="anonymous", actor_user_id=None, actor_session_id=None,
        action="auth.login.start", object_type=None, object_id=None, object_version=None,
        outcome="denied", reason_code="UNAUTHORIZED", request_id="c" * 32,
        is_synthetic=True, policy_version="T10_audit_v1", expires_at=expires_after_months(clock()))
    values[field] = value
    with pytest.raises(IntegrityError):
        with Session(auth_store.engine) as session, session.begin():
            session.add(AuditEvent(**values))
            session.flush()


@pytest.mark.parametrize("moment,expected", [
    (datetime(2024, 2, 29, 12, tzinfo=timezone.utc), datetime(2026, 2, 28, 12, tzinfo=timezone.utc)),
    (datetime(2026, 10, 3, 12, tzinfo=timezone.utc), datetime(2028, 10, 3, 12, tzinfo=timezone.utc)),
])
def test_retention_uses_actual_calendar_months(moment, expected):
    assert expires_after_months(moment) == expected
    assert expires_after_months(moment) != moment + timedelta(days=720)


@pytest.mark.postgres
def test_writer_revalidates_forged_input_and_requires_current_transaction(auth_store, audit_writer):
    forged = AuditEventInput.model_construct(action="auth.login.start", outcome="denied", reason_code="OK")
    with Session(auth_store.engine) as session:
        with pytest.raises(AuditError):
            audit_writer.append(session, AuditEventInput(action="auth.login.start", outcome="denied", reason_code="UNAUTHORIZED"))
        with session.begin(), pytest.raises(AuditError):
            audit_writer.append(session, forged)
