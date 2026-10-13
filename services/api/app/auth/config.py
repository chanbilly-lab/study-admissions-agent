"""Explicit T05 configuration; no dotenv, database, crypto or network setup."""

import base64
import re

from pydantic import Field, SecretStr, ValidationError, model_validator

from ..settings import V2RuntimeSettings
from .assurance import AdminAssurancePolicy
from .schemas import AuthModel, AuthProviderSettings, validate_identity_url


class AuthFlowError(ValueError):
    """Only fixed protocol errors cross the authentication boundary."""

    def __init__(self, status_code: int = 401, code: str = "UNAUTHORIZED"):
        pairs = {(401, "UNAUTHORIZED"), (403, "FORBIDDEN"), (503, "SERVICE_UNAVAILABLE")}
        if (status_code, code) not in pairs:
            status_code, code = 503, "SERVICE_UNAVAILABLE"
        self.status_code, self.code = status_code, code
        super().__init__({401: "Authentication is required or invalid",
                          403: "Account access is not permitted",
                          503: "Authentication service is unavailable"}[status_code])


class SessionAuthSettings(AuthModel):
    enabled: bool = Field(default=False, strict=True)
    provider: AuthProviderSettings = Field(default_factory=AuthProviderSettings)
    redirect_uri: str | None = Field(default=None, min_length=1, max_length=2048, strict=True)
    context_encryption_key: SecretStr | None = Field(default=None, repr=False)
    login_ttl_seconds: int = Field(default=300, ge=1, le=3600, strict=True)
    session_ttl_seconds: int = Field(default=3600, ge=1, le=86400, strict=True)
    transport_timeout_seconds: float = Field(default=10.0, gt=0, le=30, allow_inf_nan=False, strict=True)
    max_response_bytes: int = Field(default=262144, ge=1024, le=1048576, strict=True)
    admin_assurance_policy: AdminAssurancePolicy = Field(default_factory=AdminAssurancePolicy)

    @model_validator(mode="after")
    def active_configuration(self):
        if not self.enabled:
            if (self.provider.provider_mode != "disabled" or self.redirect_uri is not None
                or self.context_encryption_key is not None or self.admin_assurance_policy.enabled):
                raise ValueError("disabled authentication cannot carry active trust configuration")
            return self
        if (self.provider.provider_mode != "oidc_boundary" or self.provider.client_secret is None
            or self.redirect_uri is None or self.redirect_uri not in self.provider.callback_allowlist
            or self.context_encryption_key is None):
            raise ValueError("enabled authentication requires explicit OIDC trust and secrets")
        if (len(self.provider.issuer) > 2048 or len(self.provider.provider_id) > 255
            or len(self.provider.client_id) > 255):
            raise ValueError("authentication trust identifiers exceed storage bounds")
        validate_identity_url(self.redirect_uri, allow_loopback_http=True)
        policy = self.admin_assurance_policy
        if policy.enabled and (policy.trusted_issuer != self.provider.issuer
            or self.provider.client_id not in (policy.student_client_id, policy.admin_client_id)):
            raise ValueError("administrator assurance policy does not match configured provider trust")
        try:
            key = self.context_encryption_key.get_secret_value().encode("ascii")
            if not re.fullmatch(rb"[A-Za-z0-9_-]{43}=", key):
                raise ValueError
            decoded = base64.b64decode(key, altchars=b"-_", validate=True)
            if len(decoded) != 32 or base64.urlsafe_b64encode(decoded) != key:
                raise ValueError
        except (ValueError, UnicodeError):
            raise ValueError("authentication context key must be a canonical Fernet key") from None
        return self


def validate_auth_configuration(settings, runtime_settings) -> tuple[SessionAuthSettings, V2RuntimeSettings]:
    try:
        settings = SessionAuthSettings.model_validate(settings)
        runtime = V2RuntimeSettings.model_validate(runtime_settings)
        if settings.enabled and runtime.data_mode != "verified":
            raise ValueError
        if runtime.app_environment == "production" and settings.enabled:
            for callback in settings.provider.callback_allowlist:
                validate_identity_url(callback)
            validate_identity_url(settings.redirect_uri)
        return settings, runtime
    except (ValidationError, ValueError, TypeError, UnicodeError):
        raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None
