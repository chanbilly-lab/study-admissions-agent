"""Explicit activation, server trust and production test-provider rejection."""

import json

from pydantic import ValidationError
import pytest


SENSITIVE = "T05_SENSITIVE_CONFIGURATION"


def test_disabled_defaults_do_not_read_process_or_dotenv(monkeypatch, tmp_path):
    from services.api.app.auth.config import SessionAuthSettings

    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("IDENTITY_CONTEXT_KEY", SENSITIVE)
    (tmp_path / ".env").write_text("AUTH_ENABLED=true\nIDENTITY_CLIENT_SECRET=" + SENSITIVE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    settings = SessionAuthSettings()
    assert settings.enabled is False and settings.provider.provider_mode == "disabled"
    assert settings.context_encryption_key is None and settings.redirect_uri is None


@pytest.mark.parametrize("field,value", [
    ("enabled", "true"), ("redirect_uri", "https://attacker.invalid/callback"), ("context_encryption_key", None),
    ("context_encryption_key", SENSITIVE), ("login_ttl_seconds", 0), ("login_ttl_seconds", 3601),
    ("session_ttl_seconds", 0), ("session_ttl_seconds", 86401), ("session_ttl_seconds", True),
    ("transport_timeout_seconds", 0), ("transport_timeout_seconds", float("inf")),
    ("max_response_bytes", 0), ("unknown_option", SENSITIVE),
])
def test_invalid_active_configuration_is_closed_and_text_errors_hide_input(session_settings_factory, field, value):
    with pytest.raises(ValueError) as caught:
        session_settings_factory(**{field: value})
    assert SENSITIVE not in str(caught.value) + repr(caught.value)


def test_active_settings_are_frozen_and_both_secrets_are_masked(session_settings):
    with pytest.raises(ValidationError):
        session_settings.enabled = False
    visible = repr(session_settings) + str(session_settings) + session_settings.model_dump_json()
    assert session_settings.context_encryption_key.get_secret_value() not in visible
    assert session_settings.provider.client_secret.get_secret_value() not in visible


@pytest.mark.parametrize("bypass", ["copy", "construct"])
def test_activation_boundary_revalidates_constructed_or_copied_settings(session_settings, runtime, bypass):
    from services.api.app.auth.config import AuthFlowError, SessionAuthSettings, validate_auth_configuration

    changes = {"redirect_uri": "https://attacker.invalid/" + SENSITIVE}
    invalid = session_settings.model_copy(update=changes) if bypass == "copy" else SessionAuthSettings.model_construct(
        **{**session_settings.model_dump(), **changes},
    )
    with pytest.raises(AuthFlowError) as caught:
        validate_auth_configuration(invalid, runtime)
    assert caught.value.status_code == 503 and not hasattr(caught.value, "errors")
    assert SENSITIVE not in str(caught.value) + repr(caught.value)


def test_enabled_authentication_cannot_use_demo_runtime(session_settings):
    from services.api.app.auth.config import AuthFlowError, validate_auth_configuration
    from services.api.app.settings import V2RuntimeSettings

    runtime = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    with pytest.raises(AuthFlowError):
        validate_auth_configuration(session_settings, runtime)


def test_production_rejects_mock_transport_and_checks_mutation_again(session_settings, idp, runtime):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.settings import V2RuntimeSettings

    production = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    with pytest.raises(AuthFlowError):
        KeycloakOidcAdapter(session_settings, production, transport=idp.transport)
    adapter = KeycloakOidcAdapter(session_settings, production)
    adapter.transport = idp.transport
    with pytest.raises(AuthFlowError):
        adapter.prepare_authorization(object())
    assert idp.requests == []


def test_production_does_not_accept_independent_fake_code_provider(session_settings):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.service import AuthService
    from services.api.app.auth.store import AuthStore
    from services.api.app.settings import V2RuntimeSettings

    class Fake:
        def prepare_authorization(self, context):
            raise AssertionError("Production fake provider must never run")

        def exchange_code(self, code, context, *, now):
            raise AssertionError("Production fake provider must never run")

    production = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    with pytest.raises(AuthFlowError):
        AuthService(session_settings, production, AuthStore(None), Fake())


def test_production_direct_service_rejects_sqlite_before_connecting(session_settings):
    from sqlalchemy import create_engine, event

    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.service import AuthService
    from services.api.app.auth.store import AuthStore
    from services.api.app.settings import V2RuntimeSettings

    production = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    connections = []

    @event.listens_for(engine, "do_connect")
    def unexpected_connection(*args):
        connections.append(True)
        raise AssertionError("Production must reject this store before any database connection")

    try:
        adapter = KeycloakOidcAdapter(session_settings, production)
        with pytest.raises(AuthFlowError) as caught:
            AuthService(session_settings, production, AuthStore(engine), adapter)
        assert caught.value.status_code == 503 and caught.value.code == "SERVICE_UNAVAILABLE"
        assert connections == []
    finally:
        engine.dispose()


def test_production_rejects_registered_http_loopback_callback(session_settings_factory, runtime):
    from services.api.app.auth.config import AuthFlowError, validate_auth_configuration
    from services.api.app.auth.schemas import AuthProviderSettings

    address = "http://127.0.0.1:8843/auth/callback"
    provider = AuthProviderSettings(provider_mode="oidc_boundary", provider_id="T05_PINNED_KEYCLOAK",
        issuer="https://idp.test.invalid/realms/students", client_id="T05_TEST_CLIENT",
        client_secret="T05_SYNTHETIC_CLIENT_SECRET", callback_allowlist=(address,))
    settings = session_settings_factory(provider=provider, redirect_uri=address)
    production = runtime.model_copy(update={"app_environment": "production"})
    with pytest.raises(AuthFlowError):
        validate_auth_configuration(settings, production)


@pytest.mark.parametrize("secret_field", ["context_encryption_key", "client_secret"])
def test_file_configuration_cannot_embed_operational_secrets(
    session_settings, tmp_path, monkeypatch, secret_field,
):
    from services.api.app.api.identity import load_session_auth_settings
    from services.api.app.auth.config import AuthFlowError

    payload = session_settings.model_dump(mode="json")
    payload.pop("context_encryption_key")
    payload["provider"].pop("client_secret")
    if secret_field == "client_secret":
        payload["provider"][secret_field] = SENSITIVE
    else:
        payload[secret_field] = SENSITIVE
    path = tmp_path / "private-auth-settings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("IDENTITY_CONFIG_FILE", str(path))
    with pytest.raises(AuthFlowError) as caught:
        load_session_auth_settings()
    assert SENSITIVE not in str(caught.value) + repr(caught.value)
