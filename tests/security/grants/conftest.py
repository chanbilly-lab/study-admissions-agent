"""T09 synthetic participants on a required, dedicated loopback PostgreSQL DB."""

from datetime import timedelta
import os
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.security.privacy.conftest import (Actor, privacy_environment_and_network, clock, session_settings_factory,
    session_settings, runtime, idp, oidc_adapter, auth_store, auth_service, actor_factory,
    privacy_settings, privacy_service)
from services.api.app.auth.authorization import Authorizer
from services.api.app.auth.grants.schemas import AcceptGrantInput, CreateGrantInput, SharingSettings
from services.api.app.auth.grants.policy import POLICY_HASH, POLICY_VERSION
from services.api.app.auth.grants.service import SharingService
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput


@pytest.fixture
def pg_engine():
    url = os.getenv("T09_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T09 PostgreSQL check not run: T09_TEST_POSTGRES_URL absent", pytrace=False)
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/sharing_t09_test":
        pytest.fail("T09 requires the dedicated loopback sharing_t09_test database", pytrace=False)
    schema = "sharing_t09_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine, created = None, False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(url, hide_parameters=True,
            connect_args={"options": "-csearch_path=" + schema, "connect_timeout": 5})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
        assert inspect(engine).get_table_names() == []
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def principal_factory(auth_service, actor_factory):
    def make(actor=None, **kwargs):
        return auth_service.get_principal((actor if actor is not None else actor_factory(**kwargs)).cookie)
    return make


@pytest.fixture
def admitted_actor_factory(actor_factory, auth_service, privacy_service):
    def make(**kwargs):
        actor = actor_factory(**kwargs)
        principal = auth_service.get_principal(actor.cookie)
        current = privacy_service.get_admission(principal)
        adult = privacy_service.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
            notice_id=current.notice_id, expected_revision=current.revision))
        if "student" in principal.roles:
            privacy_service.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
                notice_id=adult.notice_id, expected_revision=adult.revision))
        return actor
    return make


@pytest.fixture
def resource_factory(auth_service):
    def make(actor, kind="profile", parent=None):
        principal = auth_service.get_principal(actor.cookie)
        authorizer = Authorizer(auth_service)
        if kind not in {"profile", "plan"} and parent is None:
            parent = authorizer.register_owned(principal, "profile")
        parent_id = getattr(parent, "id", parent)
        return authorizer.register_owned(principal, kind, parent_id=parent_id)
    return make


@pytest.fixture
def sharing_settings():
    return SharingSettings(fixture_mode=True)


@pytest.fixture
def sharing_service(auth_service, privacy_service, sharing_settings):
    return SharingService(auth_service, privacy_service, sharing_settings)


@pytest.fixture
def create_request_factory(sharing_service, clock):
    def make(owner, recipient, resource, **updates):
        principal = sharing_service.auth_service.get_principal(owner.cookie)
        current = sharing_service.list_grants(principal)
        values = dict(resource_type=resource.resource_type, resource_id=resource.id,
            expected_resource_version=resource.version, grantee_user_id=recipient.user_id,
            fields=["status", "version"], actions=["read", "list"], expires_at=clock() + timedelta(seconds=600),
            confirmed=True, expected_revision=current.revision, owner_consent_id=current.owner_consent_id,
            sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH)
        values.update(updates)
        return CreateGrantInput(**values)
    return make


@pytest.fixture
def accepted_grant_factory(sharing_service, admitted_actor_factory, resource_factory, create_request_factory):
    def make(owner=None, recipient=None, resource=None, **updates):
        owner = owner or admitted_actor_factory()
        recipient = recipient or admitted_actor_factory(role=None)
        resource = resource or resource_factory(owner)
        created = sharing_service.create_grant(sharing_service.auth_service.get_principal(owner.cookie),
            create_request_factory(owner, recipient, resource, **updates))
        accepted = sharing_service.accept_grant(sharing_service.auth_service.get_principal(recipient.cookie), created.grant.id,
            AcceptGrantInput(confirmed=True, expected_version=created.grant.version,
                sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))
        return owner, recipient, resource, accepted.grant
    return make


@pytest.fixture
def client(auth_service, privacy_settings, sharing_settings, runtime):
    from fastapi.testclient import TestClient
    from services.api.app.api.identity import create_identity_v2_app
    with TestClient(create_identity_v2_app(runtime, identity_service=auth_service, privacy_settings=privacy_settings,
                    sharing_settings=sharing_settings), base_url="https://app.test.invalid", follow_redirects=False) as http:
        yield http
