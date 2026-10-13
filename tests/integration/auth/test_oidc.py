"""T05 verifies independently signed JWTs over an entirely offline transport."""

import pytest
from pydantic import SecretStr


@pytest.fixture
def context(session_settings, clock):
    from services.api.app.auth.provider import create_login_context

    return create_login_context(session_settings.provider, session_settings.redirect_uri, now=clock())


def exchange(adapter, idp, context, clock):
    code = idp.issue_code(context.nonce.get_secret_value(), context.code_challenge)
    return adapter.exchange_code(SecretStr(code), context, now=clock())


def test_real_rs256_signature_pinned_jwks_and_s256_code_exchange_succeed(oidc_adapter, idp, context, clock, session_settings):
    identity = exchange(oidc_adapter, idp, context, clock)
    assert identity.identity.as_tuple() == (session_settings.provider.issuer, "T05_SYNTHETIC_STUDENT_A")
    assert identity.verification_kind == "oidc"
    assert not {"roles", "owner_id", "grants", "access_token", "id_token"} & set(identity.model_dump())
    assert idp.requests == [("POST", session_settings.provider.token_endpoint), ("GET", session_settings.provider.jwks_uri)]


def test_wrong_private_key_cannot_authenticate(oidc_adapter, idp, context, clock):
    from services.api.app.auth.config import AuthFlowError

    idp.wrong_signature = True
    with pytest.raises(AuthFlowError):
        exchange(oidc_adapter, idp, context, clock)


@pytest.mark.parametrize("field,value", [
    ("iss", "https://attacker.invalid/realms/students"), ("iss", "https://idp.test.invalid/realms/students/"),
    ("aud", "different-client"), ("aud", []), ("aud", ["T05_TEST_CLIENT", "other-client"]),
    ("aud", ["T05_TEST_CLIENT", "T05_TEST_CLIENT"]), ("aud", True),
    ("azp", "different-client"), ("nonce", "T05_SECRET_WRONG_NONCE"), ("nonce", None),
    ("nonce", "T05_SECRET_WRONG_NONCE\ud800"), ("sub", ""), ("sub", None),
    ("sub", "x" * 256), ("sub", "non-ascii-主体"), ("sub", "subject\ncontrol"),
    ("exp", True), ("exp", "9999999999"), ("exp", float("inf")),
    ("iat", True), ("iat", "123"), ("nbf", False), ("nbf", "123"),
])
def test_invalid_protocol_claims_are_rejected_safely(oidc_adapter, idp, context, clock, field, value):
    from services.api.app.auth.config import AuthFlowError

    idp.claim_changes[field] = value
    with pytest.raises(AuthFlowError) as caught:
        exchange(oidc_adapter, idp, context, clock)
    assert "T05_SECRET_WRONG_NONCE" not in str(caught.value) + repr(caught.value)
    assert idp.last_token not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize("claim", ["iss", "sub", "aud", "nonce", "exp", "iat"])
def test_required_claims_cannot_be_omitted(oidc_adapter, idp, context, clock, claim):
    from services.api.app.auth.config import AuthFlowError

    idp.claim_removals.add(claim)
    with pytest.raises(AuthFlowError):
        exchange(oidc_adapter, idp, context, clock)


@pytest.mark.parametrize("claim,delta", [("exp", 0), ("exp", -1), ("iat", 1), ("nbf", 1)])
def test_exact_time_boundary_without_implicit_leeway(oidc_adapter, idp, context, clock, claim, delta):
    from services.api.app.auth.config import AuthFlowError

    idp.claim_changes[claim] = int(clock().timestamp()) + delta
    with pytest.raises(AuthFlowError):
        exchange(oidc_adapter, idp, context, clock)


def test_multiple_audiences_require_matching_authorized_party(oidc_adapter, idp, context, clock):
    idp.claim_changes.update(aud=["T05_TEST_CLIENT", "other-client"], azp="T05_TEST_CLIENT")
    assert exchange(oidc_adapter, idp, context, clock).identity.subject == "T05_SYNTHETIC_STUDENT_A"


@pytest.mark.parametrize("header", [
    {"alg": "none"}, {"alg": "HS256"}, {"alg": "RS512"}, {"kid": "unknown"},
    {"jku": "https://attacker.invalid/keys"}, {"x5u": "https://attacker.invalid/cert"},
    {"jwk": {"kty": "RSA"}}, {"crit": ["b64"]}, {"b64": False},
])
def test_jwt_cannot_select_algorithm_or_external_keys(oidc_adapter, idp, context, clock, header):
    from services.api.app.auth.config import AuthFlowError

    idp.header_changes.update(header)
    with pytest.raises(AuthFlowError):
        exchange(oidc_adapter, idp, context, clock)
    assert all("attacker.invalid" not in url for _, url in idp.requests)


@pytest.mark.parametrize("change", ["empty", "duplicate", "wrong_type", "encryption", "algorithm", "private", "operations", "missing_modulus"])
def test_malformed_or_ambiguous_jwks_cannot_supply_signing_key(oidc_adapter, idp, context, clock, change):
    from services.api.app.auth.config import AuthFlowError

    key = idp.public_jwk()
    if change == "empty":
        keys = []
    elif change == "duplicate":
        keys = [key, dict(key)]
    else:
        updates = {"wrong_type": {"kty": "EC"}, "encryption": {"use": "enc"}, "algorithm": {"alg": "HS256"},
                   "private": {"d": "T05_PRIVATE_JWK_SECRET"}, "operations": {"key_ops": ["sign"]}}
        key.update(updates.get(change, {}))
        if change == "missing_modulus":
            key.pop("n")
        keys = [key]
    idp.jwks_payload_override = {"keys": keys}
    with pytest.raises(AuthFlowError) as caught:
        exchange(oidc_adapter, idp, context, clock)
    assert "T05_PRIVATE_JWK_SECRET" not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize("endpoint", ["token", "jwks"])
def test_dependency_redirects_are_not_followed(oidc_adapter, idp, context, clock, endpoint):
    from services.api.app.auth.config import AuthFlowError

    setattr(idp, endpoint + "_redirect", "https://attacker.invalid/T05_SECRET_REDIRECT")
    with pytest.raises(AuthFlowError) as caught:
        exchange(oidc_adapter, idp, context, clock)
    assert all("attacker.invalid" not in url for _, url in idp.requests)
    assert "T05_SECRET_REDIRECT" not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize("payload", [{}, {"id_token": ""}, {"id_token": 13}, {"id_token": "a.b.c", "error": "T05_SECRET_PROVIDER"}])
def test_invalid_token_response_has_safe_error(oidc_adapter, idp, context, clock, payload):
    from services.api.app.auth.config import AuthFlowError

    idp.token_payload_override = payload
    with pytest.raises(AuthFlowError) as caught:
        exchange(oidc_adapter, idp, context, clock)
    assert "T05_SECRET_PROVIDER" not in str(caught.value) + repr(caught.value)


def test_provider_timeout_has_no_silent_offline_fallback(oidc_adapter, idp, context, clock):
    from services.api.app.auth.config import AuthFlowError

    idp.timeout = True
    with pytest.raises(AuthFlowError) as caught:
        exchange(oidc_adapter, idp, context, clock)
    assert caught.value.status_code == 503
    assert "T05_SENSITIVE_PROVIDER_FAILURE" not in str(caught.value) + repr(caught.value)


def test_context_expiry_or_wrong_redirect_is_rejected_before_io(oidc_adapter, idp, context, clock):
    from services.api.app.auth.config import AuthFlowError

    code = idp.issue_code(context.nonce.get_secret_value(), context.code_challenge)
    for changed, now in ((context, context.expires_at),
                         (context.model_copy(update={"redirect_uri": "https://attacker.invalid/callback"}), clock()),
                         (context, clock().replace(tzinfo=None))):
        with pytest.raises(AuthFlowError):
            oidc_adapter.exchange_code(SecretStr(code), changed, now=now)
    assert idp.requests == []


@pytest.mark.parametrize("elapsed", [121, 300])
def test_time_spent_in_provider_io_cannot_extend_token_or_transaction_lifetime(
    oidc_adapter, idp, context, clock, monkeypatch, elapsed,
):
    from services.api.app.auth import oidc
    from services.api.app.auth.config import AuthFlowError

    samples = iter((1000, 1000 + elapsed))
    monkeypatch.setattr(oidc, "monotonic", lambda: next(samples))
    with pytest.raises(AuthFlowError):
        exchange(oidc_adapter, idp, context, clock)
