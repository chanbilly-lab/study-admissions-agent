"""Validate server trust rather than arbitrary caller-supplied OIDC URLs."""

import socket

from pydantic import ValidationError
import pytest


SECRET = "T04_CLIENT_SECRET_REDACTION_a1fe6"


def test_network_guard_blocks_outbound_connections_and_dns():
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="External network forbidden"):
            connection.connect(("192.0.2.1", 443))
    with pytest.raises(AssertionError, match="External DNS forbidden"):
        socket.getaddrinfo("external.invalid", 443)


def test_auth_disabled_defaults_are_closed_and_do_not_read_environment_or_dotenv(monkeypatch, tmp_path):
    from services.api.app.auth.schemas import AuthProviderSettings

    for name in ("AUTH_PROVIDER_MODE", "AUTH_ISSUER", "OIDC_ISSUER", "KEYCLOAK_CLIENT_SECRET"):
        monkeypatch.setenv(name, SECRET)
    (tmp_path / ".env").write_text(f"AUTH_PROVIDER_MODE=offline\nAUTH_CLIENT_SECRET={SECRET}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    settings = AuthProviderSettings()
    assert settings.provider_mode == settings.provider_id == "disabled"
    assert settings.issuer is None and settings.client_id is None
    assert settings.authorization_endpoint is None and settings.token_endpoint is None and settings.jwks_uri is None
    assert settings.callback_allowlist == ()
    assert settings.client_secret is None
    assert SECRET not in str(settings) + repr(settings)


def test_keycloak_endpoints_derive_only_from_exact_server_realm_issuer(auth_settings):
    prefix = auth_settings.issuer + "/protocol/openid-connect/"
    assert auth_settings.authorization_endpoint == prefix + "auth"
    assert auth_settings.token_endpoint == prefix + "token"
    assert auth_settings.jwks_uri == prefix + "certs"
    assert auth_settings.scopes == ("openid",)
    assert auth_settings.pkce_method == "S256"
    assert auth_settings.client_auth_method == "client_secret_basic"
    assert auth_settings.allowed_signing_algorithms == ("RS256",)
    with pytest.raises(ValidationError):
        auth_settings.issuer = "https://attacker.invalid/realms/students"


@pytest.mark.parametrize("field,value", [
    ("provider_mode", SECRET), ("unknown_option", SECRET), ("issuer", None), ("client_id", None),
    ("client_id", ""), ("callback_allowlist", ()), ("pkce_method", "plain"),
    ("client_auth_method", "none"), ("allowed_signing_algorithms", ("none",)),
])
def test_bad_or_partial_configuration_rejected_without_input_echo(auth_settings_factory, field, value):
    with pytest.raises(ValueError) as caught:
        auth_settings_factory(**{field: value})
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("issuer", [
    "http://idp.test.invalid/realms/students", "javascript:alert(1)",
    f"https://user:{SECRET}@idp.test.invalid/realms/students",
    "https://idp.test.invalid/realms/students#fragment", "https://idp.test.invalid/realms/students?query=value",
    "https://idp.test.invalid/realms/*", "https://idp.test.invalid/not-a-realm",
    "https://idp.test.invalid/realms/students/", "https://idp.test.invalid/realms/students/extra",
])
def test_invalid_realm_issuer_never_becomes_a_trusted_endpoint(auth_settings_factory, issuer):
    with pytest.raises(ValueError) as caught:
        auth_settings_factory(issuer=issuer)
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("redirect", [
    "http://app.test.invalid/v2/auth/callback", "//attacker.invalid/callback",
    "https://*.test.invalid/v2/auth/callback", f"https://user:{SECRET}@app.test.invalid/v2/auth/callback",
    "https://app.test.invalid/v2/auth/callback#fragment", "https://app.test.invalid/v2/auth/callback?next=evil",
    "javascript:alert(1)", "https://app.test.invalid/*",
])
def test_registered_callbacks_are_exact_safe_urls_not_wildcards(auth_settings_factory, redirect):
    with pytest.raises(ValueError) as caught:
        auth_settings_factory(callback_allowlist=(redirect,))
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("authority,path_prefix", [
    (".", ""), ("idp.test.invalid:", ""), ("idp.test.invalid:0", ""),
    ("idp.test.invalid", "/%2e%2e"), ("idp.test.invalid", "/%2E."),
    ("idp.test.invalid", "/%00"), ("idp.test.invalid", "/%0d"),
])
@pytest.mark.parametrize("field", ["issuer", "callback_allowlist"])
def test_encoded_control_traversal_and_invalid_authorities_are_not_trusted(
    auth_settings_factory, authority, path_prefix, field,
):
    suffix = "/realms/students" if field == "issuer" else "/v2/auth/callback"
    value = "https://" + authority + path_prefix + suffix
    with pytest.raises(ValueError):
        auth_settings_factory(**{field: value if field == "issuer" else (value,)})


@pytest.mark.parametrize("bypass", ["copy", "construct"])
def test_metadata_projection_is_revalidated_and_factory_error_has_no_input(
    auth_settings, runtime_settings, identity_fixture, bypass,
):
    from services.api.app.auth.provider import AuthProviderError, create_identity_provider
    from services.api.app.auth.schemas import ProviderMetadata

    valid = ProviderMetadata(**metadata_values(auth_settings))
    changes = {"jwks_uri": "https://user:" + SECRET + "@attacker.invalid/keys"}
    metadata = valid.model_copy(update=changes) if bypass == "copy" else ProviderMetadata.model_construct(
        **{**valid.model_dump(), **changes},
    )
    with pytest.raises(AuthProviderError) as caught:
        create_identity_provider(auth_settings, runtime_settings, fixtures=[identity_fixture], metadata=metadata)
    assert SECRET not in str(caught.value) + repr(caught.value)
    assert not hasattr(caught.value, "errors")


def test_callback_allowlist_cannot_have_duplicate_entries(auth_settings_factory):
    callback = "https://app.test.invalid/v2/auth/callback"
    with pytest.raises(ValueError):
        auth_settings_factory(callback_allowlist=(callback, callback))


@pytest.mark.parametrize("field,suffix", [
    ("authorization_endpoint", "auth"), ("token_endpoint", "token"), ("jwks_uri", "certs"),
])
def test_explicit_endpoints_must_match_derived_exact_urls(auth_settings_factory, field, suffix):
    correct = "https://idp.test.invalid/realms/students/protocol/openid-connect/" + suffix
    assert getattr(auth_settings_factory(**{field: correct}), field) == correct
    for replacement in (correct + "/", correct + "?query=value", correct + "#fragment",
                        correct.replace("idp.test.invalid", "attacker.invalid")):
        with pytest.raises(ValueError):
            auth_settings_factory(**{field: replacement})


def metadata_values(settings):
    return {name: getattr(settings, name) for name in (
        "issuer", "authorization_endpoint", "token_endpoint", "jwks_uri",
    )}


def test_pinned_metadata_is_checked_offline_and_cannot_extend_trust(auth_settings):
    from services.api.app.auth.provider import validate_provider_metadata
    from services.api.app.auth.schemas import ProviderMetadata

    metadata = ProviderMetadata(**metadata_values(auth_settings))
    validate_provider_metadata(auth_settings, metadata)
    for name in metadata_values(auth_settings):
        changed = metadata_values(auth_settings)
        changed[name] = "https://attacker.invalid/realms/other"
        with pytest.raises(ValueError):
            validate_provider_metadata(auth_settings, ProviderMetadata(**changed))
    for malicious_name in ("jku", "x5u", "discovery_url", "client_id", "roles"):
        with pytest.raises(ValueError) as caught:
            ProviderMetadata(**{**metadata_values(auth_settings), malicious_name: SECRET})
        assert SECRET not in str(caught.value)


@pytest.mark.parametrize("bypass,updates", [
    ("copy", {"issuer": "https://attacker.invalid/not-a-realm"}),
    ("copy", {"callback_allowlist": ("https://*.invalid/callback",)}),
    ("construct", {"provider_mode": SECRET}), ("construct", {"pkce_method": "plain"}),
])
def test_provider_factory_revalidates_bypassed_configuration(auth_settings, runtime_settings, identity_fixture, bypass, updates):
    from services.api.app.auth.provider import create_identity_provider
    from services.api.app.auth.schemas import AuthProviderSettings

    invalid = auth_settings.model_copy(update=updates) if bypass == "copy" else AuthProviderSettings.model_construct(
        **{**auth_settings.model_dump(), **updates},
    )
    with pytest.raises(ValueError) as caught:
        create_identity_provider(invalid, runtime_settings, fixtures=[identity_fixture])
    assert SECRET not in str(caught.value)


def test_client_secret_is_masked_in_models_and_invalid_settings(auth_settings_factory):
    settings = auth_settings_factory(client_secret=SECRET)
    assert settings.client_secret.get_secret_value() == SECRET
    assert SECRET not in repr(settings) + str(settings)
    assert SECRET not in settings.model_dump_json()
    with pytest.raises(ValueError) as caught:
        auth_settings_factory(client_secret=SECRET, unknown_option=SECRET)
    assert SECRET not in str(caught.value) + repr(caught.value)
