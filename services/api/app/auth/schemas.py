"""Frozen internal identity contracts; no HTTP payload or verified JWT parser."""

from datetime import datetime
from ipaddress import ip_address
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class AuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always")


def validate_identity_url(value: str, *, allow_loopback_http: bool = False) -> str:
    """Validate fixed server URLs without fetching, rewriting, or resolving DNS."""
    try:
        if (not isinstance(value, str) or not value
            or any(character.isspace() or ord(character) < 32 for character in value)
            or any(character in value for character in "\\*?#")):
            raise ValueError
        value.encode("utf-8")
        parsed = urlsplit(value)
        if (not parsed.netloc or not parsed.hostname or parsed.username is not None or parsed.password is not None
            or "%" in parsed.netloc or parsed.fragment or parsed.query):
            raise ValueError
        port = parsed.port
        if parsed.netloc.endswith(":") or (port is not None and not 1 <= port <= 65535):
            raise ValueError
        try:
            ip_address(parsed.hostname)
        except ValueError:
            if len(parsed.hostname) > 253 or any(
                not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in parsed.hostname.split(".")
            ):
                raise ValueError
        if parsed.scheme != "https" and not (
            allow_loopback_http and parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError
        # This bounded configuration uses fixed registered routes, so reject encoded
        # paths instead of guessing how a proxy or IdP decodes them.
        if "%" in parsed.path or any(part in {".", ".."} for part in parsed.path.split("/")):
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError("identity URL is not an allowed fixed address") from None
    return value


def keycloak_endpoints(issuer: str) -> tuple[str, str, str]:
    validate_identity_url(issuer)
    path = urlsplit(issuer).path
    if not re.fullmatch(r"(?:/[A-Za-z0-9._~-]+)*/realms/[A-Za-z0-9._~-]+", path):
        raise ValueError("Keycloak issuer must be an exact realm issuer without a trailing slash")
    prefix = issuer + "/protocol/openid-connect/"
    return prefix + "auth", prefix + "token", prefix + "certs"


class AuthProviderSettings(AuthModel):
    provider_mode: Literal["disabled", "offline", "oidc_boundary"] = "disabled"
    provider_id: str = Field(default="disabled", min_length=1, strict=True)
    issuer: str | None = Field(default=None, min_length=1, strict=True)
    client_id: str | None = Field(default=None, min_length=1, strict=True)
    authorization_endpoint: str | None = Field(default=None, min_length=1, strict=True)
    token_endpoint: str | None = Field(default=None, min_length=1, strict=True)
    jwks_uri: str | None = Field(default=None, min_length=1, strict=True)
    callback_allowlist: tuple[str, ...] = ()
    scopes: tuple[Literal["openid"], ...] = ("openid",)
    pkce_method: Literal["S256"] = "S256"
    client_auth_method: Literal["client_secret_basic"] = "client_secret_basic"
    allowed_signing_algorithms: tuple[Literal["RS256"], ...] = ("RS256",)
    client_secret: SecretStr | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def fixed_trust(self):
        if not self.provider_id.strip() or self.scopes != ("openid",) or self.allowed_signing_algorithms != ("RS256",):
            raise ValueError("identity configuration must use the explicit bounded protocol baseline")
        if self.provider_mode == "disabled":
            if any(value is not None for value in (self.issuer, self.client_id, self.authorization_endpoint,
                                                   self.token_endpoint, self.jwks_uri, self.client_secret)) or self.callback_allowlist:
                raise ValueError("disabled identity mode cannot carry an active provider configuration")
            return self
        if self.provider_id == "disabled" or self.issuer is None or self.client_id is None or not self.client_id.strip():
            raise ValueError("active identity mode requires a fixed provider, issuer and client")
        expected = keycloak_endpoints(self.issuer)
        for field, endpoint in zip(("authorization_endpoint", "token_endpoint", "jwks_uri"), expected):
            supplied = getattr(self, field)
            if supplied is not None and supplied != endpoint:
                raise ValueError("identity endpoint must exactly match the fixed Keycloak issuer")
            object.__setattr__(self, field, endpoint)
        if not self.callback_allowlist or len(set(self.callback_allowlist)) != len(self.callback_allowlist):
            raise ValueError("identity configuration requires a nonempty exact callback allowlist")
        for callback in self.callback_allowlist:
            validate_identity_url(callback, allow_loopback_http=True)
        if self.client_secret is not None and not self.client_secret.get_secret_value():
            raise ValueError("configured client secret cannot be empty")
        return self


class ProviderMetadata(AuthModel):
    """Explicit four-field subset, never an implicitly trusted discovery document."""
    issuer: str = Field(min_length=1, strict=True)
    authorization_endpoint: str = Field(min_length=1, strict=True)
    token_endpoint: str = Field(min_length=1, strict=True)
    jwks_uri: str = Field(min_length=1, strict=True)

    @field_validator("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
    @classmethod
    def safe_address(cls, value):
        return validate_identity_url(value)


class IdentityKey(AuthModel):
    issuer: str = Field(min_length=1, strict=True)
    subject: str = Field(min_length=1, strict=True)

    @field_validator("issuer")
    @classmethod
    def safe_issuer(cls, value):
        return validate_identity_url(value)

    @field_validator("subject")
    @classmethod
    def nonblank_subject(cls, value):
        if not value.strip():
            raise ValueError("subject cannot be blank")
        return value

    def as_tuple(self) -> tuple[str, str]:
        return self.issuer, self.subject


class OfflineIdentityFixture(AuthModel):
    assertion_id: SecretStr = Field(repr=False)
    identity: IdentityKey
    is_synthetic: Literal[True] = True

    @field_validator("assertion_id")
    @classmethod
    def nonempty_assertion(cls, value):
        if not value.get_secret_value().strip():
            raise ValueError("offline assertion identifier cannot be blank")
        return value

    @field_validator("is_synthetic", mode="before")
    @classmethod
    def explicit_synthetic(cls, value):
        if value is not True:
            raise ValueError("offline identities must be explicitly synthetic")
        return value


class LoginContext(AuthModel):
    provider_mode: Literal["offline", "oidc_boundary"]
    provider_id: str = Field(min_length=1, strict=True)
    issuer: str = Field(min_length=1, strict=True)
    client_id: str = Field(min_length=1, strict=True)
    redirect_uri: str = Field(min_length=1, strict=True)
    state: SecretStr = Field(repr=False)
    nonce: SecretStr = Field(repr=False)
    code_verifier: SecretStr = Field(repr=False)
    code_challenge: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    issued_at: datetime
    expires_at: datetime

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("identity timestamps must be timezone-aware")
        return value

    @field_validator("state", "nonce", "code_verifier")
    @classmethod
    def nonempty_material(cls, value):
        if not value.get_secret_value().strip():
            raise ValueError("login binding material cannot be blank")
        return value

    @model_validator(mode="after")
    def positive_lifetime(self):
        if self.expires_at <= self.issued_at:
            raise ValueError("login expiry must be after its issue time")
        return self


class CallbackArtifact(AuthModel):
    """Internal offline proof; actual HTTP callbacks do not carry these fields."""
    provider_mode: Literal["offline", "oidc_boundary"]
    provider_id: str = Field(min_length=1, strict=True)
    issuer: str = Field(min_length=1, strict=True)
    client_id: str = Field(min_length=1, strict=True)
    redirect_uri: str = Field(min_length=1, strict=True)
    state: SecretStr = Field(repr=False)
    nonce: SecretStr = Field(repr=False)
    code_verifier: SecretStr = Field(repr=False)
    assertion_id: SecretStr = Field(repr=False)


class AuthorizationRequest(AuthModel):
    """Data for future BFF use, without constructing or logging an authorization URL."""
    endpoint: str
    client_id: str
    redirect_uri: str
    response_type: Literal["code"] = "code"
    scope: Literal["openid"] = "openid"
    state: SecretStr = Field(repr=False)
    nonce: SecretStr = Field(repr=False)
    code_challenge: str
    code_challenge_method: Literal["S256"] = "S256"


class VerifiedIdentity(AuthModel):
    identity: IdentityKey
    provider_id: str
    is_synthetic: bool = Field(strict=True)
    verification_kind: Literal["offline_fixture", "oidc"]

    @model_validator(mode="after")
    def distinct_provenance(self):
        if self.is_synthetic != (self.verification_kind == "offline_fixture"):
            raise ValueError("identity provenance is inconsistent")
        return self
