"""Actual PostgreSQL basics; adversarial matrix is independently owned."""

from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.auth.authorization import Authorizer
from services.api.app.auth.grants.models import AccessGrant, GrantAction, GrantField, SharingState
from services.api.app.auth.grants.policy import POLICY_HASH, POLICY_VERSION
from services.api.app.auth.grants.schemas import AcceptGrantInput, SharingSettings
from services.api.app.auth.grants.service import SharingError, SharingService
from services.api.app.auth.store import AUTH_REVISION, migrate_auth, migration_config
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput


def principal(service, actor):
    return service.auth_service.get_principal(actor.cookie)


def test_empty_migration_roundtrip_and_readiness(pg_engine):
    migrate_auth(pg_engine)
    from services.api.app.auth.store import AuthStore
    AuthStore(pg_engine).assert_schema_ready()
    expected = {"auth_sharing_states", "auth_access_grants", "grant_fields", "grant_actions"}
    assert expected.issubset(inspect(pg_engine).get_table_names())
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM auth_alembic_version")) == AUTH_REVISION
    configuration = migration_config()
    with pg_engine.begin() as connection:
        configuration.attributes["connection"] = connection
        command.downgrade(configuration, "0004_privacy_t08")
    assert expected.isdisjoint(inspect(pg_engine).get_table_names())
    migrate_auth(pg_engine)
    AuthStore(pg_engine).assert_schema_ready()


def test_pending_requires_separate_acceptance(sharing_service, admitted_actor_factory, resource_factory, create_request_factory):
    owner, recipient = admitted_actor_factory(), admitted_actor_factory(role=None)
    resource = resource_factory(owner)
    created = sharing_service.create_grant(principal(sharing_service, owner), create_request_factory(owner, recipient, resource))
    assert created.revision == 1 and created.grant.state == "pending" and not created.grant.access_active
    with pytest.raises(SharingError) as error:
        sharing_service.require_shared(principal(sharing_service, recipient), "profile", resource.id, ("status",))
    assert error.value.status_code == 404
    accepted = sharing_service.accept_grant(principal(sharing_service, recipient), created.grant.id,
        AcceptGrantInput(confirmed=True, expected_version=1, sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))
    assert accepted.grant.access_active and accepted.grant.version == 2 and accepted.revision == 0
    assert sharing_service.require_shared(principal(sharing_service, recipient), "profile", resource.id, ("status",)).version is None


def test_repeat_create_after_revoke_conflicts(sharing_service, admitted_actor_factory, resource_factory, create_request_factory):
    owner, recipient = admitted_actor_factory(), admitted_actor_factory(role=None)
    resource = resource_factory(owner)
    request = create_request_factory(owner, recipient, resource)
    created = sharing_service.create_grant(principal(sharing_service, owner), request)
    revoked = sharing_service.revoke_grant(principal(sharing_service, recipient), created.grant.id)
    assert revoked.grant.state == "revoked" and revoked.revision == 0
    assert sharing_service.list_grants(principal(sharing_service, owner)).revision == 2
    with pytest.raises(SharingError) as error:
        sharing_service.create_grant(principal(sharing_service, owner), request)
    assert error.value.status_code == 409


@pytest.mark.parametrize("kind", ["profile", "plan", "attachment", "export", "job"])
def test_metadata_scope_all_five_kinds(sharing_service, accepted_grant_factory, admitted_actor_factory, resource_factory, kind):
    owner = admitted_actor_factory()
    resource = resource_factory(owner, kind)
    _, recipient, _, grant = accepted_grant_factory(owner=owner, resource=resource)
    current = principal(sharing_service, recipient)
    assert sharing_service.require_shared(current, kind, resource.id, ("status", "version")).version == 1
    page = sharing_service.list_shared(current, kind, ("version",))
    assert page.total == 1 and page.items[0].status is None
    with pytest.raises(SharingError):
        sharing_service.require_shared(current, kind, resource.id, ("status",), "download")


def test_touch_and_owner_withdraw_do_not_revive(sharing_service, accepted_grant_factory, privacy_service):
    owner, recipient, resource, grant = accepted_grant_factory()
    owner_principal, recipient_principal = principal(sharing_service, owner), principal(sharing_service, recipient)
    Authorizer(sharing_service.auth_service).touch_owned(owner_principal, "profile", resource.id, 1)
    assert sharing_service.list_shared(recipient_principal, "profile", ("status",)).total == 0
    with pytest.raises(SharingError):
        sharing_service.require_shared(recipient_principal, "profile", resource.id, ("status",))
    current = privacy_service.get_admission(owner_principal)
    privacy_service.withdraw_core(owner_principal, current.consent_id)
    current = privacy_service.get_admission(owner_principal)
    privacy_service.confirm_core(owner_principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=current.notice_id, expected_revision=current.revision))
    assert not sharing_service.list_grants(recipient_principal, "received").items[0].access_active


def test_cache_only_current_projection_and_delayed_read(sharing_service, accepted_grant_factory):
    _, recipient, resource, _ = accepted_grant_factory()
    current = principal(sharing_service, recipient)
    projection = sharing_service.require_shared(current, "profile", resource.id, ("status",))
    key = sharing_service.cache_key(current, "profile", resource.id, ("status",))
    assert sharing_service.cached_value(current, "profile", resource.id, ("status",), {key: projection}) == projection
    assert sharing_service.cached_value(current, "profile", resource.id, ("status",), {key: {**projection.model_dump(), "conversation": "PRIVATE"}}) is None
    assert sharing_service.execute_shared(current, "profile", resource.id, ("status",), lambda session, actor, value: value) == projection


def test_cross_subject_proof_foreign_key(sharing_service, accepted_grant_factory):
    _, recipient, _, grant = accepted_grant_factory()
    with pytest.raises(IntegrityError), Session(sharing_service.auth_service.store.engine) as session, session.begin():
        row = session.get(AccessGrant, grant.id)
        row.owner_consent_id = row.grantee_declaration_id
        session.flush()


def test_adult_guard_reusable_session_new_transaction(sharing_service, admitted_actor_factory):
    actor = admitted_actor_factory(role=None)
    current = principal(sharing_service, actor)
    with Session(sharing_service.auth_service.store.engine) as session:
        with session.begin():
            first = sharing_service.privacy_service.require_declared_adult(session, current)
        with session.begin():
            second = sharing_service.privacy_service.require_declared_adult(session, current)
        assert second == first


def test_default_sharing_closed(sharing_service, accepted_grant_factory):
    owner, recipient, resource, grant = accepted_grant_factory()
    closed = SharingService(sharing_service.auth_service, sharing_service.privacy_service, SharingSettings())
    assert not closed.get_policy().sharing_available
    with pytest.raises(SharingError) as error:
        closed.require_shared(principal(closed, recipient), "profile", resource.id, ("status",))
    assert error.value.status_code == 503
    assert closed.revoke_grant(principal(closed, recipient), grant.id).grant.state == "revoked"


def test_owner_role_expiry_during_field_read_is_rechecked(sharing_service, accepted_grant_factory, clock, monkeypatch):
    owner, recipient, resource, _ = accepted_grant_factory()
    sharing_service.auth_service.store.assign_role(owner.user_id, "student", now=clock(),
        expires_at=clock() + timedelta(seconds=1))
    original, advanced = sharing_service._fields, False
    def delayed_fields(session, row):
        nonlocal advanced
        result = original(session, row)
        if not advanced:
            advanced = True
            clock.advance(1)
        return result
    monkeypatch.setattr(sharing_service, "_fields", delayed_fields)
    with pytest.raises(SharingError) as error:
        sharing_service.require_shared(principal(sharing_service, recipient), "profile", resource.id, ("status",))
    assert error.value.status_code in {403, 404}
