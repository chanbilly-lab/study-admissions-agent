"""PKCE and pure offline binding checks; no persistent OIDC login is claimed."""

from datetime import timedelta, timezone

import pytest


RFC_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
# RFC 7636 Appendix B, including its final M (43 base64url characters).
RFC_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_pkce_s256_matches_rfc7636_appendix_b():
    from services.api.app.auth.provider import pkce_s256

    assert pkce_s256(RFC_VERIFIER) == RFC_CHALLENGE


@pytest.mark.parametrize("verifier", ["x" * 43, "x" * 128, "aA0._~-" * 7])
def test_pkce_accepts_rfc_length_boundaries_and_unreserved_characters(verifier):
    from services.api.app.auth.provider import pkce_s256

    challenge = pkce_s256(verifier)
    assert len(challenge) == 43 and "=" not in challenge


@pytest.mark.parametrize("verifier", [
    "", "x" * 42, "x" * 129, "x" * 42 + "=", "x" * 42 + "+", "x" * 42 + "/",
    "x" * 42 + " ", "x" * 42 + "\n", "x" * 42 + "中", "x" * 42 + "%",
])
def test_pkce_rejects_short_long_or_non_rfc_characters(verifier):
    from services.api.app.auth.provider import pkce_s256

    with pytest.raises(ValueError):
        pkce_s256(verifier)


def test_generated_context_is_bound_and_secrets_are_not_displayed(auth_settings, login_context, now):
    from services.api.app.auth.provider import create_login_context, pkce_s256

    assert login_context.provider_id == auth_settings.provider_id
    assert login_context.issuer == auth_settings.issuer and login_context.client_id == auth_settings.client_id
    assert login_context.redirect_uri == auth_settings.callback_allowlist[0]
    assert login_context.issued_at == now and login_context.expires_at == now + timedelta(seconds=300)
    assert login_context.code_challenge == pkce_s256(login_context.code_verifier.get_secret_value())
    visible = repr(login_context) + str(login_context) + login_context.model_dump_json()
    for name in ("state", "nonce", "code_verifier"):
        secret = getattr(login_context, name).get_secret_value()
        assert secret and secret not in visible
    second = create_login_context(auth_settings, auth_settings.callback_allowlist[0], now=now)
    for name in ("state", "nonce", "code_verifier"):
        assert getattr(second, name) != getattr(login_context, name)


@pytest.mark.parametrize("redirect", [
    "https://attacker.invalid/v2/auth/callback", "https://app.test.invalid/v2/auth/callback/",
    "https://app.test.invalid/v2/auth/callback?next=evil", "https://app.test.invalid/v2/auth/Callback",
])
def test_context_requires_exact_registered_callback(auth_settings, now, redirect):
    from services.api.app.auth.provider import create_login_context

    with pytest.raises(ValueError):
        create_login_context(auth_settings, redirect, now=now)


@pytest.mark.parametrize("ttl", [0, -1])
def test_context_cannot_be_created_with_empty_or_negative_lifetime(auth_settings, now, ttl):
    from services.api.app.auth.provider import create_login_context

    with pytest.raises(ValueError):
        create_login_context(auth_settings, auth_settings.callback_allowlist[0], now=now, ttl_seconds=ttl)


def test_context_time_validation_rejects_naive_or_inverted_intervals(auth_settings, login_context, now):
    from services.api.app.auth.provider import create_login_context
    from services.api.app.auth.schemas import LoginContext

    with pytest.raises(ValueError):
        create_login_context(auth_settings, auth_settings.callback_allowlist[0], now=now.replace(tzinfo=None))
    for values in (
        {"issued_at": now.replace(tzinfo=None)}, {"expires_at": now.replace(tzinfo=None)},
        {"expires_at": now}, {"expires_at": now - timedelta(seconds=1)},
    ):
        with pytest.raises(ValueError):
            LoginContext.model_validate({**login_context.model_dump(), **values})


@pytest.mark.parametrize("field,value", [
    ("provider_mode", "oidc_boundary"),
    ("provider_id", "other-provider"), ("issuer", "https://other.invalid/realms/students"),
    ("client_id", "different-client"), ("redirect_uri", "https://attacker.invalid/callback"),
    ("state", "WRONG_STATE_T04" + "x" * 40), ("nonce", "WRONG_NONCE_T04" + "x" * 40),
    ("code_verifier", "y" * 43),
])
def test_adapter_rejects_callback_binding_changes(offline_provider, identity_fixture, login_context, now, field, value):
    from services.api.app.auth.schemas import CallbackArtifact

    callback = offline_provider.make_callback(login_context, identity_fixture.assertion_id)
    invalid = CallbackArtifact.model_validate({**callback.model_dump(), field: value})
    with pytest.raises(ValueError):
        offline_provider.verify_callback(invalid, login_context, now=now)


@pytest.mark.parametrize("elapsed", [-1, 300, 301])
def test_adapter_rejects_before_issue_and_at_or_after_expiry(offline_provider, identity_fixture, login_context, now, elapsed):
    callback = offline_provider.make_callback(login_context, identity_fixture.assertion_id)
    with pytest.raises(ValueError):
        offline_provider.verify_callback(callback, login_context, now=now + timedelta(seconds=elapsed))


def test_adapter_accepts_aware_equivalent_time_and_last_unexpired_instant(offline_provider, identity_fixture, login_context, now):
    callback = offline_provider.make_callback(login_context, identity_fixture.assertion_id)
    for instant in (now.astimezone(timezone(timedelta(hours=8))), now + timedelta(seconds=299)):
        identity = offline_provider.verify_callback(callback, login_context, now=instant)
        assert identity.identity == identity_fixture.identity
    with pytest.raises(ValueError):
        offline_provider.verify_callback(callback, login_context, now=now.replace(tzinfo=None))


@pytest.mark.parametrize("field,value", [("state", ""), ("nonce", ""), ("code_challenge", "WRONG_CHALLENGE")])
def test_context_rejects_empty_proofs_or_unmatched_s256_challenge(login_context, field, value):
    from services.api.app.auth.schemas import LoginContext

    with pytest.raises(ValueError):
        LoginContext.model_validate({**login_context.model_dump(), field: value})


def test_validly_shaped_wrong_challenge_is_rejected_at_provider_boundary(
    offline_provider, identity_fixture, login_context, now,
):
    from services.api.app.auth.schemas import LoginContext

    callback = offline_provider.make_callback(login_context, identity_fixture.assertion_id)
    changed = LoginContext.model_validate({**login_context.model_dump(), "code_challenge": "x" * 43})
    with pytest.raises(ValueError):
        offline_provider.prepare_authorization(changed)
    with pytest.raises(ValueError):
        offline_provider.verify_callback(callback, changed, now=now)


@pytest.mark.parametrize("bypass", ["copy", "construct"])
def test_provider_revalidates_context_instances_before_using_them(
    offline_provider, identity_fixture, login_context, now, bypass,
):
    from services.api.app.auth.schemas import LoginContext

    callback = offline_provider.make_callback(login_context, identity_fixture.assertion_id)
    changes = {"expires_at": now.replace(tzinfo=None)}
    changed = login_context.model_copy(update=changes) if bypass == "copy" else LoginContext.model_construct(
        **{**login_context.model_dump(), **changes},
    )
    with pytest.raises(ValueError):
        offline_provider.prepare_authorization(changed)
    with pytest.raises(ValueError):
        offline_provider.verify_callback(callback, changed, now=now)
