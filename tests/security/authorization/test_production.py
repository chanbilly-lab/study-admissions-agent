"""Production assembly with simulated account rows, no IdP/network invocation."""

from datetime import timedelta
from uuid import uuid4

from cryptography.fernet import Fernet
import pytest
from sqlalchemy.orm import Session


pytestmark = pytest.mark.postgres


def test_production_authorizer_excludes_synthetic_actor_resources_and_parents(auth_store, pg_engine, clock):
    from services.api.app.auth.authorization import Authorizer, AuthorizationError, Principal
    from services.api.app.auth.config import AuthFlowError, SessionAuthSettings
    from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.schemas import AuthProviderSettings
    from services.api.app.auth.service import AuthService, digest_secret
    from services.api.app.settings import V2RuntimeSettings

    # False flags deliberately exercise production branches, with no real account
    # or student/domain payload. Reserved .test names are never contacted.
    provider_settings = AuthProviderSettings(
        provider_mode="oidc_boundary", provider_id="T07_PRODUCTION_LIKE_FIXTURE",
        issuer="https://identity.example.test/realms/students", client_id="T07_FIXTURE_STUDENT",
        client_secret="T07_SYNTHETIC_SECRET_NO_ACTUAL_IDP",
        callback_allowlist=("https://admissions.example.test/auth/callback",),
    )
    settings = SessionAuthSettings(
        provider=provider_settings, enabled=True, redirect_uri=provider_settings.callback_allowlist[0],
        context_encryption_key=Fernet.generate_key().decode("ascii"),
    )
    runtime = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    adapter = KeycloakOidcAdapter(settings, runtime)
    assert type(adapter) is KeycloakOidcAdapter and adapter.transport is None
    service = AuthService(settings, runtime, auth_store, adapter, clock=clock)
    authorizer = Authorizer(service)
    actor_id, actor_session, synthetic_id, synthetic_session = (uuid4() for _ in range(4))
    cookie = "T07_SIMULATED_PRODUCTION_COOKIE_" + uuid4().hex
    synthetic_cookie = "T07_SYNTHETIC_PRODUCTION_COOKIE_" + uuid4().hex
    good_root, synthetic_root, good_child, synthetic_child, real_child_synthetic_parent = (
        uuid4() for _ in range(5))
    with Session(pg_engine) as database, database.begin():
        for user_id, session_id, raw, is_synthetic in (
            (actor_id, actor_session, cookie, False),
            (synthetic_id, synthetic_session, synthetic_cookie, True),
        ):
            database.add(AuthUser(id=user_id, status="active", is_synthetic=is_synthetic, created_at=clock()))
            database.flush()
            database.add(AuthUserRole(user_id=user_id, role="student", granted_at=clock(),
                                      expires_at=None, revoked_at=None))
            database.add(AuthSession(id=session_id, user_id=user_id, session_digest=digest_secret(raw, "session"),
                created_at=clock(), expires_at=clock() + timedelta(hours=1), revoked_at=None))
        for resource_id, is_synthetic in ((good_root, False), (synthetic_root, True)):
            database.add(AuthOwnedResource(id=resource_id, resource_type="profile", owner_user_id=actor_id,
                status="active", version=1, is_synthetic=is_synthetic, parent_id=None))
        database.flush()
        for resource_id, parent_id, is_synthetic in (
            (good_child, good_root, False), (synthetic_child, good_root, True),
            (real_child_synthetic_parent, synthetic_root, False),
        ):
            database.add(AuthOwnedResource(id=resource_id, resource_type="attachment", owner_user_id=actor_id,
                status="active", version=1, is_synthetic=is_synthetic, parent_id=parent_id))
    principal = service.get_principal(cookie)
    assert principal.is_synthetic is False and principal.user_id == actor_id
    assert authorizer.require_owned(principal, "profile", good_root).id == good_root
    assert authorizer.require_owned(principal, "attachment", good_child).id == good_child
    assert [row.id for row in authorizer.list_owned(principal, "profile").items] == [good_root]
    page = authorizer.list_owned(principal, "attachment")
    assert [row.id for row in page.items] == [good_child] and page.total == 1
    for kind, resource_id in (
        ("profile", synthetic_root), ("attachment", synthetic_child),
        ("attachment", real_child_synthetic_parent),
    ):
        with pytest.raises(AuthorizationError) as denied:
            authorizer.require_owned(principal, kind, resource_id)
        assert denied.value.status_code == 404
    with pytest.raises(AuthFlowError) as synthetic_login:
        service.get_principal(synthetic_cookie)
    assert synthetic_login.value.status_code == 401
    forged = Principal(user_id=synthetic_id, session_id=synthetic_session, roles=("student",),
        is_synthetic=False, expires_at=clock() + timedelta(hours=1), authorization_context="0" * 64)
    with pytest.raises(AuthorizationError) as synthetic_access:
        authorizer.require_owned(forged, "profile", good_root)
    assert synthetic_access.value.status_code == 401
