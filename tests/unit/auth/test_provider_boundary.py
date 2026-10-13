"""Test subject mapping and interchangeable providers without real login routes."""

import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[3]
SECRET = "T04_CALLBACK_SECRET_REDACTION_f3041"


def test_identity_keys_use_exact_two_part_values_not_ambiguous_concatenation():
    from services.api.app.auth.schemas import IdentityKey

    left = IdentityKey(issuer="https://idp.test.invalid/realms/a", subject="bc")
    right = IdentityKey(issuer="https://idp.test.invalid/realms/ab", subject="c")
    assert "".join(left.as_tuple()) == "".join(right.as_tuple())
    assert left.as_tuple() != right.as_tuple() and left != right
    other_issuer = IdentityKey(issuer="https://other.test.invalid/realms/a", subject="bc")
    other_case = IdentityKey(issuer=left.issuer, subject="BC")
    assert len({left.as_tuple(), right.as_tuple(), other_issuer.as_tuple(), other_case.as_tuple()}) == 4
    assert left.as_tuple() == (left.issuer, "bc")


@pytest.mark.parametrize("field,value", [("subject", ""), ("subject", None), ("subject", 13), ("issuer", ""), ("issuer", None)])
def test_missing_or_wrongly_typed_identity_keys_are_not_mapped(field, value):
    from services.api.app.auth.schemas import IdentityKey

    values = {"issuer": "https://idp.test.invalid/realms/students", "subject": "synthetic-student"}
    values[field] = value
    with pytest.raises(ValueError):
        IdentityKey(**values)


@pytest.mark.parametrize("extra", ["email", "display_name", "roles", "owner_id", "grants"])
def test_client_identity_fields_do_not_become_subject_mapping_or_permissions(extra):
    from services.api.app.auth.schemas import IdentityKey

    with pytest.raises(ValueError) as caught:
        IdentityKey(issuer="https://idp.test.invalid/realms/students", subject="student", **{extra: SECRET})
    assert SECRET not in str(caught.value)


def test_offline_fixture_is_synthetic_and_returns_no_business_permissions(offline_provider, identity_fixture, login_context, now):
    result = offline_provider.verify_callback(
        offline_provider.make_callback(login_context, identity_fixture.assertion_id), login_context, now=now,
    )
    assert result.identity == identity_fixture.identity
    assert result.provider_id == login_context.provider_id and result.is_synthetic is True
    assert result.verification_kind
    assert not {"roles", "owner_id", "grants", "account_id", "user_id"} & set(result.model_dump())
    assert identity_fixture.assertion_id.get_secret_value() not in str(identity_fixture) + repr(identity_fixture)


@pytest.mark.parametrize("collision", ["identity", "assertion"])
def test_duplicate_fixture_identity_or_assertion_is_rejected(auth_settings, runtime_settings, identity_fixture, collision):
    from services.api.app.auth.provider import create_identity_provider
    from services.api.app.auth.schemas import IdentityKey, OfflineIdentityFixture

    second = OfflineIdentityFixture(
        assertion_id="DIFFERENT_OFFLINE_ASSERTION" if collision == "identity" else identity_fixture.assertion_id,
        identity=identity_fixture.identity if collision == "identity" else IdentityKey(
            issuer=auth_settings.issuer, subject="another-student",
        ), is_synthetic=True,
    )
    with pytest.raises(ValueError):
        create_identity_provider(auth_settings, runtime_settings, fixtures=[identity_fixture, second])


def test_fixture_with_real_label_or_client_permission_is_rejected(identity_fixture):
    from services.api.app.auth.schemas import OfflineIdentityFixture

    for changes in ({"is_synthetic": False}, {"roles": ["data_admin"]}, {"owner_id": SECRET}):
        with pytest.raises(ValueError) as caught:
            OfflineIdentityFixture.model_validate({**identity_fixture.model_dump(), **changes})
        assert SECRET not in str(caught.value)


def test_unknown_assertion_is_not_an_identity_and_never_echoed(
    offline_provider, identity_fixture, login_context, now,
):
    from services.api.app.auth.schemas import CallbackArtifact

    valid = offline_provider.make_callback(login_context, identity_fixture.assertion_id)
    callback = CallbackArtifact.model_validate({**valid.model_dump(), "assertion_id": SECRET})
    assert SECRET not in str(callback) + repr(callback) + callback.model_dump_json()
    with pytest.raises(ValueError) as caught:
        offline_provider.verify_callback(callback, login_context, now=now)
    assert SECRET not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize("field", ["state", "nonce", "assertion_id", "code_verifier"])
def test_opaque_proof_with_lone_surrogate_is_safely_rejected(
    offline_provider, identity_fixture, login_context, now, field,
):
    from services.api.app.auth.provider import AuthProviderError
    from services.api.app.auth.schemas import CallbackArtifact

    valid = offline_provider.make_callback(login_context, identity_fixture.assertion_id)
    invalid = CallbackArtifact.model_validate({**valid.model_dump(), field: SECRET + "\ud800"})
    with pytest.raises(AuthProviderError) as caught:
        offline_provider.verify_callback(invalid, login_context, now=now)
    assert SECRET not in str(caught.value) + repr(caught.value)


def test_provider_can_be_replaced_without_changing_subject_or_adding_permissions(
    auth_settings_factory, runtime_settings, identity_fixture, now,
):
    from services.api.app.auth.provider import create_identity_provider, create_login_context

    identities = []
    for provider_id in ("test-provider-one", "test-provider-two"):
        settings = auth_settings_factory(provider_id=provider_id)
        provider = create_identity_provider(settings, runtime_settings, fixtures=[identity_fixture])
        context = create_login_context(settings, settings.callback_allowlist[0], now=now)
        request = provider.prepare_authorization(context)
        assert request.client_id == settings.client_id and request.redirect_uri == context.redirect_uri
        assert request.response_type == "code" and request.scope == "openid"
        assert request.code_challenge_method == "S256" and request.code_challenge == context.code_challenge
        assert "client_secret" not in request.model_dump() and "code_verifier" not in request.model_dump()
        visible = repr(request) + str(request) + request.model_dump_json()
        for name in ("state", "nonce", "code_verifier"):
            assert getattr(context, name).get_secret_value() not in visible
        result = provider.verify_callback(provider.make_callback(context, identity_fixture.assertion_id), context, now=now)
        identities.append(result.identity.as_tuple())
        assert result.provider_id == provider_id
    assert identities == [identity_fixture.identity.as_tuple(), identity_fixture.identity.as_tuple()]


def test_consumer_accepts_independent_protocol_implementations_without_concrete_helpers(
    offline_provider, auth_settings, identity_fixture, login_context, now,
):
    from services.api.app.auth.provider import IdentityProvider, validate_callback_binding
    from services.api.app.auth.schemas import AuthorizationRequest, CallbackArtifact, VerifiedIdentity

    class FakeProvider:
        """Independent test implementation returning only a synthetic identity."""

        def __init__(self, settings, identity):
            self._settings = settings
            self._identity = identity
            self.calls = []

        @property
        def settings(self):
            return self._settings

        def prepare_authorization(self, context):
            self.calls.append("prepare_authorization")
            return AuthorizationRequest(
                endpoint=self.settings.authorization_endpoint, client_id=self.settings.client_id,
                redirect_uri=context.redirect_uri, state=context.state, nonce=context.nonce,
                code_challenge=context.code_challenge,
            )

        def verify_callback(self, callback, context, *, now):
            self.calls.append("verify_callback")
            validate_callback_binding(self.settings, callback, context, now=now)
            return VerifiedIdentity(identity=self._identity, provider_id=self.settings.provider_id,
                                    is_synthetic=True, verification_kind="offline_fixture")

    def consume(provider: IdentityProvider, callback, context, *, now):
        settings = provider.settings
        authorization = provider.prepare_authorization(context)
        identity = provider.verify_callback(callback, context, now=now)
        assert authorization.client_id == settings.client_id
        return authorization, identity

    callback = CallbackArtifact(
        provider_mode=login_context.provider_mode, provider_id=login_context.provider_id,
        issuer=login_context.issuer, client_id=login_context.client_id, redirect_uri=login_context.redirect_uri,
        state=login_context.state, nonce=login_context.nonce, code_verifier=login_context.code_verifier,
        assertion_id=identity_fixture.assertion_id,
    )
    independent = FakeProvider(auth_settings, identity_fixture.identity)
    assert isinstance(offline_provider, IdentityProvider) and isinstance(independent, IdentityProvider)
    assert not isinstance(independent, type(offline_provider))
    assert not hasattr(independent, "make_callback")
    results = [consume(provider, callback, login_context, now=now)
               for provider in (offline_provider, independent)]
    assert independent.calls == ["prepare_authorization", "verify_callback"]
    for authorization, identity in results:
        assert authorization.response_type == "code" and authorization.code_challenge_method == "S256"
        assert identity.identity.as_tuple() == identity_fixture.identity.as_tuple()
        assert identity.is_synthetic is True
        assert not {"roles", "owner_id", "grants", "account_id", "user_id"} & set(identity.model_dump())


def test_subject_case_is_preserved_when_fixture_assertions_are_resolved(
    auth_settings, runtime_settings, now,
):
    from services.api.app.auth.provider import create_identity_provider, create_login_context
    from services.api.app.auth.schemas import IdentityKey, OfflineIdentityFixture

    fixtures = [OfflineIdentityFixture(assertion_id="T04_CASE_ASSERTION_" + subject,
        identity=IdentityKey(issuer=auth_settings.issuer, subject=subject), is_synthetic=True)
        for subject in ("Student", "student")]
    provider = create_identity_provider(auth_settings, runtime_settings, fixtures=fixtures)
    context = create_login_context(auth_settings, auth_settings.callback_allowlist[0], now=now)
    resolved = [provider.verify_callback(provider.make_callback(context, fixture.assertion_id), context, now=now)
                for fixture in fixtures]
    assert [result.identity.subject for result in resolved] == ["Student", "student"]
    assert resolved[0].identity.as_tuple() != resolved[1].identity.as_tuple()


def test_production_prohibits_offline_provider_even_with_valid_fixed_fixture(auth_settings, identity_fixture):
    from services.api.app.auth.provider import OfflineIdentityProvider, create_identity_provider
    from services.api.app.settings import V2RuntimeSettings

    runtime = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
                               database_url=None, legacy_demo_mode=None, _env_file=None)
    for constructor in (create_identity_provider, OfflineIdentityProvider):
        with pytest.raises(ValueError):
            constructor(auth_settings, runtime, fixtures=[identity_fixture])


def test_production_rejects_http_loopback_callback_even_though_test_configuration_can_describe_it(auth_settings_factory):
    from services.api.app.auth.provider import OidcBoundaryProvider, create_identity_provider
    from services.api.app.settings import V2RuntimeSettings

    runtime = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
                               database_url=None, legacy_demo_mode=None, _env_file=None)
    for callback in ("http://127.0.0.1:8000/v2/auth/callback", "http://localhost:8000/v2/auth/callback",
                     "http://[::1]:8000/v2/auth/callback"):
        settings = auth_settings_factory(provider_mode="oidc_boundary", callback_allowlist=(callback,))
        for constructor in (create_identity_provider, OidcBoundaryProvider):
            with pytest.raises(ValueError):
                constructor(settings, runtime)


def test_distinct_issuers_with_same_subject_are_unique_but_not_trusted_by_single_issuer_adapter(
    auth_settings, runtime_settings, identity_fixture,
):
    from services.api.app.auth.provider import create_identity_provider, validate_offline_fixtures
    from services.api.app.auth.schemas import IdentityKey, OfflineIdentityFixture

    foreign = OfflineIdentityFixture(assertion_id="T04_OTHER_ISSUER_ASSERTION", identity=IdentityKey(
        issuer="https://other.test.invalid/realms/students", subject=identity_fixture.identity.subject,
    ), is_synthetic=True)
    assert len(validate_offline_fixtures([identity_fixture, foreign])) == 2
    with pytest.raises(ValueError):
        create_identity_provider(auth_settings, runtime_settings, fixtures=[identity_fixture, foreign])


@pytest.mark.parametrize("bypass", ["copy", "construct"])
@pytest.mark.parametrize("entry", ["factory", "offline_constructor", "oidc_constructor"])
def test_provider_entries_revalidate_forged_runtime_and_hide_sensitive_errors(
    auth_settings_factory, runtime_settings, identity_fixture, bypass, entry,
):
    from pydantic import SecretStr
    from services.api.app.auth.provider import (
        AuthProviderError, OfflineIdentityProvider, OidcBoundaryProvider, create_identity_provider,
    )
    from services.api.app.settings import V2RuntimeSettings

    changes = {"app_environment": "production", "data_mode": "demo", "database_url": SecretStr(SECRET)}
    changed = runtime_settings.model_copy(update=changes) if bypass == "copy" else V2RuntimeSettings.model_construct(
        **{**runtime_settings.model_dump(), **changes},
    )
    settings = auth_settings_factory(provider_mode="oidc_boundary" if entry == "oidc_constructor" else "offline")
    constructor = {"factory": create_identity_provider, "offline_constructor": OfflineIdentityProvider,
                   "oidc_constructor": OidcBoundaryProvider}[entry]
    kwargs = {} if entry == "oidc_constructor" else {"fixtures": [identity_fixture]}
    with pytest.raises(AuthProviderError) as caught:
        constructor(settings, changed, **kwargs)
    assert SECRET not in str(caught.value) + repr(caught.value)
    assert not hasattr(caught.value, "errors")


def test_configured_oidc_authorization_is_a_description_and_verification_is_unavailable(
    auth_settings_factory, runtime_settings, now, monkeypatch,
):
    from services.api.app.auth import provider as module
    from services.api.app.auth.provider import AuthProviderUnavailable, create_identity_provider, create_login_context
    from services.api.app.auth.schemas import CallbackArtifact

    settings = auth_settings_factory(provider_mode="oidc_boundary", client_secret=SECRET)
    def forbidden_offline(*args, **kwargs):
        pytest.fail("Configured OIDC silently fell back to offline identity")
    monkeypatch.setattr(module, "OfflineIdentityProvider", forbidden_offline)
    provider = create_identity_provider(settings, runtime_settings)
    context = create_login_context(settings, settings.callback_allowlist[0], now=now)
    request = provider.prepare_authorization(context)
    assert request.endpoint == settings.authorization_endpoint
    assert SECRET not in repr(request) + str(request) + request.model_dump_json()
    callback = CallbackArtifact(
        provider_mode=context.provider_mode, provider_id=context.provider_id, issuer=context.issuer,
        client_id=context.client_id, redirect_uri=context.redirect_uri, state=context.state,
        nonce=context.nonce, code_verifier=context.code_verifier, assertion_id=SECRET,
    )
    with pytest.raises(AuthProviderUnavailable) as caught:
        provider.verify_callback(callback, context, now=now)
    assert SECRET not in str(caught.value) + repr(caught.value)


def test_disabled_provider_cannot_issue_authorization_or_verify_an_offline_assertion(
    runtime_settings, login_context, offline_provider, identity_fixture, now,
):
    from services.api.app.auth.provider import AuthProviderUnavailable, create_identity_provider
    from services.api.app.auth.schemas import AuthProviderSettings

    disabled = create_identity_provider(AuthProviderSettings(), runtime_settings)
    with pytest.raises(AuthProviderUnavailable):
        disabled.prepare_authorization(login_context)
    callback = offline_provider.make_callback(login_context, identity_fixture.assertion_id)
    with pytest.raises(AuthProviderUnavailable):
        disabled.verify_callback(callback, login_context, now=now)


def test_auth_package_and_providers_in_fresh_process_have_no_m0_database_or_network_dependencies():
    program = r'''
import importlib.abc, socket, sys
blocked = {"main", "database", "models", "migrations", "seed", "providers", "planning", "catalog", "schemas"}
class RejectM0(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        for prefix in ("services.api.app.", "app."):
            if fullname.startswith(prefix) and fullname[len(prefix):].split(".")[0] in blocked:
                raise AssertionError("Forbidden M0 import " + fullname)
        return None
sys.meta_path.insert(0, RejectM0())
for name in ("connect", "connect_ex"):
    def no_socket(*args, **kwargs):
        raise AssertionError("Network forbidden before auth import")
    setattr(socket.socket, name, no_socket)
def no_dns(*args, **kwargs):
    raise AssertionError("DNS forbidden before auth import")
socket.getaddrinfo = no_dns
from datetime import datetime, timezone
from services.api.app.auth.provider import create_identity_provider, create_login_context, pkce_s256
from services.api.app.auth.schemas import AuthProviderSettings
from services.api.app.settings import V2RuntimeSettings
runtime = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled",
                            database_url=None, legacy_demo_mode=None, _env_file=None)
settings = AuthProviderSettings(provider_mode="offline", provider_id="offline-test",
    issuer="https://idp.test.invalid/realms/students", client_id="test-client",
    callback_allowlist=("https://app.test.invalid/v2/auth/callback",))
provider = create_identity_provider(settings, runtime)
context = create_login_context(settings, settings.callback_allowlist[0], now=datetime.now(timezone.utc))
assert provider.prepare_authorization(context).code_challenge == pkce_s256(context.code_verifier.get_secret_value())
assert not any(name.startswith(("sqlalchemy", "psycopg")) for name in sys.modules)
for prefix in ("services.api.app.", "app."):
    assert not any(prefix + name in sys.modules for name in blocked)
print("auth imports and pure authorization have no M0, DB or network dependencies")
'''
    result = subprocess.run([sys.executable, "-c", program], cwd=ROOT, env=dict(os.environ),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no M0, DB or network dependencies" in result.stdout


def test_provider_module_does_not_open_http_login_private_data_or_sessions():
    from services.api.app.api.public import create_public_app
    from services.api.app.settings import V2RuntimeSettings

    runtime = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
                               database_url=None, legacy_demo_mode=None, _env_file=None)
    with TestClient(create_public_app(runtime)) as client:
        config = client.get("/v2/config")
        assert config.status_code == 200 and config.json()["data"]["business_available"] is False
        for path in ("/v2/auth/login", "/v2/auth/callback", "/v2/auth/session", "/v2/profiles"):
            response = client.get(path)
            assert response.status_code == 404, response.text
            assert "set-cookie" not in response.headers
        assert set(client.get("/v2/openapi.json").json()["paths"]) == {"/config", "/offerings"}
