"""T04 tests own their offline guard and do not inherit M0 fixtures."""

import os
import socket
from datetime import datetime, timezone

import pytest


@pytest.fixture(autouse=True)
def isolated_auth_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("AUTH_", "OIDC_", "KEYCLOAK_", "V2_")) or name in {
            "DEMO_MODE", "LLM_API_KEY", "OPENAI_API_KEY",
        }:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def forbid_auth_network(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def guarded(sock, address, original=original):
            # Windows asyncio's socketpair needs its internal loopback pair.
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("External network forbidden in T04 auth tests")

        monkeypatch.setattr(socket.socket, name, guarded)
    original_resolution = socket.getaddrinfo

    def guarded_resolution(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_resolution(host, *args, **kwargs)
        raise AssertionError("External DNS forbidden in T04 auth tests")

    monkeypatch.setattr(socket, "getaddrinfo", guarded_resolution)


@pytest.fixture
def now():
    return datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def auth_settings_factory():
    from services.api.app.auth.schemas import AuthProviderSettings

    def make(**changes):
        values = {
            "provider_mode": "offline", "provider_id": "t04-offline-provider",
            "issuer": "https://idp.test.invalid/realms/students", "client_id": "t04-test-client",
            "callback_allowlist": ("https://app.test.invalid/v2/auth/callback",),
        }
        values.update(changes)
        return AuthProviderSettings(**values)

    return make


@pytest.fixture
def auth_settings(auth_settings_factory):
    return auth_settings_factory()


@pytest.fixture
def runtime_settings():
    from services.api.app.settings import V2RuntimeSettings

    return V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled",
                             database_url=None, legacy_demo_mode=None, _env_file=None)


@pytest.fixture
def identity_fixture(auth_settings):
    from services.api.app.auth.schemas import IdentityKey, OfflineIdentityFixture

    return OfflineIdentityFixture(assertion_id="T04_SYNTHETIC_ASSERTION_6f982",
                                  identity=IdentityKey(issuer=auth_settings.issuer, subject="T04_SYNTHETIC_STUDENT_A"),
                                  is_synthetic=True)


@pytest.fixture
def login_context(auth_settings, now):
    from services.api.app.auth.provider import create_login_context

    return create_login_context(auth_settings, auth_settings.callback_allowlist[0], now=now)


@pytest.fixture
def offline_provider(auth_settings, runtime_settings, identity_fixture):
    from services.api.app.auth.provider import create_identity_provider

    return create_identity_provider(auth_settings, runtime_settings, fixtures=[identity_fixture])
