"""Verified authentication strength, without granting application permissions."""

from datetime import datetime, timezone

from pydantic import Field, ValidationError, field_validator, model_validator

from .schemas import AuthModel, VerifiedIdentity, validate_identity_url


def _label(value: str) -> str:
    if not value.strip() or not value.isascii() or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError("authentication policy labels must be nonblank ASCII identifiers")
    return value


class SessionAssurance(AuthModel):
    acr: str | None = Field(default=None, max_length=255, strict=True)
    amr: tuple[str, ...] = ()
    auth_time: datetime | None = None

    @field_validator("acr")
    @classmethod
    def valid_acr(cls, value):
        return _label(value) if value is not None else None

    @field_validator("amr")
    @classmethod
    def valid_amr(cls, value):
        if len(value) > 32 or len(set(value)) != len(value):
            raise ValueError("authentication methods must be bounded and unique")
        for item in value:
            if not isinstance(item, str) or len(item) > 255:
                raise ValueError("authentication methods must be bounded identifiers")
            _label(item)
        return value

    @field_validator("auth_time")
    @classmethod
    def aware_auth_time(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("authentication time must be timezone-aware")
            return value.astimezone(timezone.utc)
        return value


class VerifiedSessionIdentity(VerifiedIdentity):
    """Produced only after the adapter has verified the signed OIDC claims."""

    client_id: str = Field(min_length=1, max_length=255, strict=True)
    assurance: SessionAssurance

    @model_validator(mode="after")
    def oidc_only(self):
        if self.verification_kind != "oidc" or self.is_synthetic:
            raise ValueError("session assurance requires a verified OIDC identity")
        _label(self.client_id)
        return self


class AdminAssurancePolicy(AuthModel):
    enabled: bool = Field(default=False, strict=True)
    trusted_issuer: str | None = Field(default=None, max_length=2048, strict=True)
    admin_client_id: str | None = Field(default=None, max_length=255, strict=True)
    student_client_id: str | None = Field(default=None, max_length=255, strict=True)
    allowed_acr: tuple[str, ...] = ()
    required_amr: tuple[str, ...] = ()
    max_auth_age_seconds: int | None = Field(default=None, ge=1, le=86400, strict=True)

    @model_validator(mode="after")
    def explicit_policy(self):
        configured = (self.trusted_issuer, self.admin_client_id, self.student_client_id,
                      self.allowed_acr, self.required_amr, self.max_auth_age_seconds)
        if not self.enabled:
            if any(configured):
                raise ValueError("disabled administrator assurance cannot carry active policy")
            return self
        if not all(configured) or self.admin_client_id == self.student_client_id:
            raise ValueError("administrator assurance requires distinct clients and explicit policy")
        validate_identity_url(self.trusted_issuer)
        for value in (self.admin_client_id, self.student_client_id):
            _label(value)
        for labels in (self.allowed_acr, self.required_amr):
            if len(labels) > 32 or len(labels) != len(set(labels)):
                raise ValueError("administrator policy labels must be bounded and unique")
            for value in labels:
                if not isinstance(value, str) or len(value) > 255:
                    raise ValueError("administrator policy labels must be bounded identifiers")
                _label(value)
        return self


def check_admin_assurance(assurance: SessionAssurance | None, *, issuer: str | None,
                         client_id: str | None, policy: AdminAssurancePolicy,
                         now: datetime) -> None:
    # A successful strength check is not an administrator role or resource grant.
    from .config import AuthFlowError

    try:
        policy = AdminAssurancePolicy.model_validate(policy)
        if not policy.enabled or assurance is None or issuer != policy.trusted_issuer or client_id != policy.admin_client_id:
            raise ValueError
        assurance = SessionAssurance.model_validate(assurance)
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError
        if (assurance.acr not in policy.allowed_acr or not set(policy.required_amr).issubset(assurance.amr)
            or assurance.auth_time is None):
            raise ValueError
        age = (now.astimezone(timezone.utc) - assurance.auth_time).total_seconds()
        if age < 0 or age > policy.max_auth_age_seconds:
            raise ValueError
    except (ValidationError, ValueError, TypeError, UnicodeError, OverflowError):
        raise AuthFlowError(403, "FORBIDDEN") from None


__all__ = ["SessionAssurance", "VerifiedSessionIdentity", "AdminAssurancePolicy", "check_admin_assurance"]
