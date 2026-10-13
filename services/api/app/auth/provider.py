"""Replaceable identity boundary: pure descriptors and synthetic offline proofs."""

import base64
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from hashlib import sha256
import hmac
import re
import secrets
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

from pydantic import SecretStr, ValidationError

from ..settings import V2RuntimeSettings
from .schemas import (
    AuthProviderSettings, AuthorizationRequest, CallbackArtifact, IdentityKey,
    LoginContext, OfflineIdentityFixture, ProviderMetadata, VerifiedIdentity,
)


_SAFE_ERRORS = {
    "INVALID_CONFIGURATION": "Identity provider configuration is invalid",
    "INVALID_CONTEXT": "Identity login context or binding is invalid",
    "INVALID_FIXTURES": "Offline identity fixtures are invalid",
    "PROVIDER_UNAVAILABLE": "Identity provider is unavailable; no fallback is permitted",
}


class AuthProviderError(ValueError):
    def __init__(self, code: str = "INVALID_CONTEXT"):
        self.code = code if code in _SAFE_ERRORS else "INVALID_CONTEXT"
        super().__init__(_SAFE_ERRORS[self.code])


class AuthProviderUnavailable(AuthProviderError):
    def __init__(self):
        super().__init__("PROVIDER_UNAVAILABLE")


def _settings(value) -> AuthProviderSettings:
    try:
        return AuthProviderSettings.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        raise AuthProviderError("INVALID_CONFIGURATION") from None


def _runtime(value) -> V2RuntimeSettings:
    try:
        return V2RuntimeSettings.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        raise AuthProviderError("INVALID_CONFIGURATION") from None


def _aware_now(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AuthProviderError()
    return value


def _opaque_bytes(value: str) -> bytes:
    try:
        return value.encode("utf-8")
    except UnicodeError:
        raise AuthProviderError() from None


def pkce_s256(verifier: SecretStr | str) -> str:
    value = verifier.get_secret_value() if isinstance(verifier, SecretStr) else verifier
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", value):
        raise AuthProviderError()
    return base64.urlsafe_b64encode(sha256(value.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def validate_provider_metadata(settings: AuthProviderSettings, metadata: ProviderMetadata | Mapping) -> ProviderMetadata:
    settings = _settings(settings)
    try:
        metadata = ProviderMetadata.model_validate(metadata)
    except (ValidationError, TypeError, ValueError):
        raise AuthProviderError("INVALID_CONFIGURATION") from None
    if settings.provider_mode == "disabled" or any(
        getattr(metadata, field) != getattr(settings, field)
        for field in ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
    ):
        raise AuthProviderError("INVALID_CONFIGURATION")
    return metadata


def _context(settings: AuthProviderSettings, context: LoginContext) -> LoginContext:
    settings = _settings(settings)
    try:
        context = LoginContext.model_validate(context)
    except (ValidationError, TypeError, ValueError):
        raise AuthProviderError() from None
    if settings.provider_mode == "disabled" or any(
        getattr(context, field) != getattr(settings, field)
        for field in ("provider_mode", "provider_id", "issuer", "client_id")
    ) or context.redirect_uri not in settings.callback_allowlist:
        raise AuthProviderError()
    if not hmac.compare_digest(pkce_s256(context.code_verifier), context.code_challenge):
        raise AuthProviderError()
    return context


def create_login_context(settings: AuthProviderSettings, redirect_uri: str, *,
                         now: datetime, ttl_seconds: int = 300) -> LoginContext:
    settings = _settings(settings)
    now = _aware_now(now)
    if settings.provider_mode == "disabled":
        raise AuthProviderUnavailable()
    if redirect_uri not in settings.callback_allowlist or type(ttl_seconds) is not int or not 0 < ttl_seconds <= 3600:
        raise AuthProviderError()
    verifier = secrets.token_urlsafe(32)
    try:
        return LoginContext(provider_mode=settings.provider_mode, provider_id=settings.provider_id,
                            issuer=settings.issuer, client_id=settings.client_id, redirect_uri=redirect_uri,
                            state=SecretStr(secrets.token_urlsafe(32)), nonce=SecretStr(secrets.token_urlsafe(32)),
                            code_verifier=SecretStr(verifier), code_challenge=pkce_s256(verifier),
                            issued_at=now, expires_at=now + timedelta(seconds=ttl_seconds))
    except (ValidationError, OverflowError, ValueError):
        raise AuthProviderError() from None


def validate_callback_binding(settings: AuthProviderSettings, callback: CallbackArtifact,
                              context: LoginContext, *, now: datetime) -> None:
    context = _context(settings, context)
    now = _aware_now(now)
    try:
        callback = CallbackArtifact.model_validate(callback)
    except (ValidationError, TypeError, ValueError):
        raise AuthProviderError() from None
    if not context.issued_at <= now < context.expires_at or any(
        getattr(callback, field) != getattr(context, field)
        for field in ("provider_mode", "provider_id", "issuer", "client_id", "redirect_uri")
    ):
        raise AuthProviderError()
    for field in ("state", "nonce", "code_verifier"):
        # UTF-8 bytes preserve exact opaque values and avoid compare_digest's
        # ASCII-only str restriction, without echoing mismatched values.
        actual = _opaque_bytes(getattr(callback, field).get_secret_value())
        expected = _opaque_bytes(getattr(context, field).get_secret_value())
        if not hmac.compare_digest(actual, expected):
            raise AuthProviderError()
    if not hmac.compare_digest(pkce_s256(callback.code_verifier), context.code_challenge):
        raise AuthProviderError()


def validate_offline_fixtures(fixtures: Sequence[OfflineIdentityFixture | Mapping]) -> tuple[OfflineIdentityFixture, ...]:
    try:
        validated = tuple(OfflineIdentityFixture.model_validate(value) for value in fixtures)
    except (ValidationError, TypeError, ValueError):
        raise AuthProviderError("INVALID_FIXTURES") from None
    identities = [fixture.identity.as_tuple() for fixture in validated]
    assertions = [fixture.assertion_id.get_secret_value() for fixture in validated]
    try:
        for assertion in assertions:
            _opaque_bytes(assertion)
    except AuthProviderError:
        raise AuthProviderError("INVALID_FIXTURES") from None
    if not validated or len(set(identities)) != len(identities) or len(set(assertions)) != len(assertions):
        raise AuthProviderError("INVALID_FIXTURES")
    return validated


@runtime_checkable
class IdentityProvider(Protocol):
    @property
    def settings(self) -> AuthProviderSettings: ...
    def prepare_authorization(self, context: LoginContext) -> AuthorizationRequest: ...
    def verify_callback(self, callback: CallbackArtifact, context: LoginContext, *, now: datetime) -> VerifiedIdentity: ...


class _ProviderBoundary:
    expected_mode = "disabled"

    def __init__(self, settings: AuthProviderSettings, runtime_settings: V2RuntimeSettings, *,
                 metadata: ProviderMetadata | Mapping | None = None):
        self._settings = _settings(settings)
        self._runtime_settings = _runtime(runtime_settings)
        self._validate_policy()
        if metadata is not None:
            validate_provider_metadata(self._settings, metadata)

    @property
    def settings(self) -> AuthProviderSettings:
        return self._settings

    def _validate_policy(self) -> AuthProviderSettings:
        settings = _settings(self._settings)
        runtime = _runtime(self._runtime_settings)
        if settings.provider_mode != self.expected_mode:
            raise AuthProviderError("INVALID_CONFIGURATION")
        if runtime.app_environment == "production" and (
            settings.provider_mode == "offline" or any(urlsplit(callback).scheme != "https" for callback in settings.callback_allowlist)
        ):
            raise AuthProviderError("INVALID_CONFIGURATION")
        return settings

    def prepare_authorization(self, context: LoginContext) -> AuthorizationRequest:
        settings = self._validate_policy()
        context = _context(settings, context)
        return AuthorizationRequest(endpoint=settings.authorization_endpoint, client_id=settings.client_id,
                                    redirect_uri=context.redirect_uri, state=context.state, nonce=context.nonce,
                                    code_challenge=context.code_challenge)


class DisabledIdentityProvider(_ProviderBoundary):
    def prepare_authorization(self, context: LoginContext) -> AuthorizationRequest:
        self._validate_policy()
        raise AuthProviderUnavailable()

    def verify_callback(self, callback: CallbackArtifact, context: LoginContext, *, now: datetime) -> VerifiedIdentity:
        self._validate_policy()
        raise AuthProviderUnavailable()


class OidcBoundaryProvider(_ProviderBoundary):
    expected_mode = "oidc_boundary"

    def verify_callback(self, callback: CallbackArtifact, context: LoginContext, *, now: datetime) -> VerifiedIdentity:
        self._validate_policy()
        # No token exchange, JWT cryptography, account lookup or fallback exists.
        raise AuthProviderUnavailable()


class OfflineIdentityProvider(_ProviderBoundary):
    expected_mode = "offline"

    def __init__(self, settings: AuthProviderSettings, runtime_settings: V2RuntimeSettings, *,
                 fixtures: Sequence[OfflineIdentityFixture | Mapping] | None = None,
                 metadata: ProviderMetadata | Mapping | None = None):
        super().__init__(settings, runtime_settings, metadata=metadata)
        if fixtures is None:
            fixtures = [OfflineIdentityFixture(assertion_id=SecretStr("OFFLINE_ASSERTION_" + name.upper()),
                                                identity=IdentityKey(issuer=self.settings.issuer, subject="offline-" + name),
                                                is_synthetic=True) for name in ("alice", "bob")]
        self._fixtures = validate_offline_fixtures(fixtures)
        if any(fixture.identity.issuer != self.settings.issuer for fixture in self._fixtures):
            raise AuthProviderError("INVALID_FIXTURES")

    def _fixture(self, assertion_id: SecretStr | str) -> OfflineIdentityFixture:
        fixtures = validate_offline_fixtures(self._fixtures)
        settings = self._validate_policy()
        if any(fixture.identity.issuer != settings.issuer for fixture in fixtures):
            raise AuthProviderError("INVALID_FIXTURES")
        value = assertion_id.get_secret_value() if isinstance(assertion_id, SecretStr) else assertion_id
        if not isinstance(value, str):
            raise AuthProviderError()
        for fixture in fixtures:
            if hmac.compare_digest(_opaque_bytes(value), _opaque_bytes(fixture.assertion_id.get_secret_value())):
                return fixture
        raise AuthProviderError()

    def make_callback(self, context: LoginContext, assertion_id: SecretStr | str) -> CallbackArtifact:
        context = _context(self._validate_policy(), context)
        fixture = self._fixture(assertion_id)
        return CallbackArtifact(provider_mode=context.provider_mode, provider_id=context.provider_id,
                                issuer=context.issuer, client_id=context.client_id, redirect_uri=context.redirect_uri,
                                state=context.state, nonce=context.nonce, code_verifier=context.code_verifier,
                                assertion_id=fixture.assertion_id)

    def verify_callback(self, callback: CallbackArtifact, context: LoginContext, *, now: datetime) -> VerifiedIdentity:
        settings = self._validate_policy()
        validate_callback_binding(settings, callback, context, now=now)
        callback = CallbackArtifact.model_validate(callback)
        fixture = self._fixture(callback.assertion_id)
        return VerifiedIdentity(identity=fixture.identity, provider_id=settings.provider_id,
                                is_synthetic=True, verification_kind="offline_fixture")


def create_identity_provider(settings: AuthProviderSettings, runtime_settings: V2RuntimeSettings, *,
                             fixtures: Sequence[OfflineIdentityFixture | Mapping] | None = None,
                             metadata: ProviderMetadata | Mapping | None = None) -> IdentityProvider:
    settings = _settings(settings)
    runtime_settings = _runtime(runtime_settings)
    if settings.provider_mode == "offline":
        return OfflineIdentityProvider(settings, runtime_settings, fixtures=fixtures, metadata=metadata)
    if fixtures is not None:
        raise AuthProviderError("INVALID_CONFIGURATION")
    boundary = OidcBoundaryProvider if settings.provider_mode == "oidc_boundary" else DisabledIdentityProvider
    return boundary(settings, runtime_settings, metadata=metadata)
