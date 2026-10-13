"""Login transaction and opaque-session orchestration without HTTP or public registration."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import re
import secrets
from urllib.parse import urlencode
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from pydantic import Field, SecretStr, ValidationError

from .config import AuthFlowError, SessionAuthSettings, validate_auth_configuration
from .assurance import AdminAssurancePolicy, VerifiedSessionIdentity, check_admin_assurance
from .oidc import KeycloakOidcAdapter, OidcCodeProvider, StrictJSONDecoder, secret_value
from .provider import AuthProviderError, _context, create_login_context
from .schemas import AuthModel, LoginContext, VerifiedIdentity
from .store import AuthStore, utc_time
from ..audit.context import audited


class LoginStart(AuthModel):
    authorization_url: SecretStr = Field(repr=False)
    browser_binding: SecretStr = Field(repr=False)
    expires_at: datetime


class SessionSnapshot(AuthModel):
    user_id: UUID
    expires_at: datetime
    is_synthetic: bool = Field(strict=True)


class SessionEstablished(SessionSnapshot):
    session_cookie: SecretStr = Field(repr=False)


class CsrfToken(AuthModel):
    token: SecretStr = Field(repr=False)
    expires_at: datetime


class ExecutionReference(AuthModel):
    """Server-issued reference; it carries neither cookie nor cached permission."""

    session_id: UUID
    user_id: UUID


def digest_secret(value: SecretStr | str, purpose: str) -> str:
    # High-entropy generated values do not need a password KDF. Domain separation
    # prevents accidental reuse of one opaque value as another kind of credential.
    return sha256((purpose + ":v1:" + secret_value(value)).encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, settings: SessionAuthSettings, runtime_settings, store: AuthStore,
                 provider: OidcCodeProvider, *, clock: Callable[[], datetime] | None = None):
        self.settings, self.runtime_settings = validate_auth_configuration(settings, runtime_settings)
        self.store, self.provider = store, provider
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._validate()
        self.store.audit.is_synthetic_default = self.runtime_settings.app_environment == "test"

    def _validate(self) -> SessionAuthSettings:
        settings, runtime = validate_auth_configuration(self.settings, self.runtime_settings)
        if not settings.enabled or not isinstance(self.provider, OidcCodeProvider) or not isinstance(self.store, AuthStore):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        self.store.validate_rights_configuration(production=runtime.app_environment == "production")
        if self.store.rights_guard is not None and self.store.rights_guard.clock is not self.clock:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        if runtime.app_environment == "production":
            if (type(self.provider) is not KeycloakOidcAdapter or self.provider.transport is not None
                or self.store.engine.dialect.name != "postgresql"):
                raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        if isinstance(self.provider, KeycloakOidcAdapter):
            provider_settings = self.provider._validate()
            if (provider_settings.model_dump(exclude={"admin_assurance_policy"})
                != settings.model_dump(exclude={"admin_assurance_policy"}) or self.provider.runtime_settings != runtime):
                raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        return settings

    def _now(self) -> datetime:
        try:
            return utc_time(self.clock())
        except (ValueError, TypeError, OverflowError):
            raise AuthFlowError() from None

    def _cipher(self) -> Fernet:
        return Fernet(self._validate().context_encryption_key.get_secret_value().encode("ascii"))

    @audited("auth.login.start")
    def start_login(self) -> LoginStart:
        settings, now = self._validate(), self._now()
        try:
            context = create_login_context(settings.provider, settings.redirect_uri,
                now=now, ttl_seconds=settings.login_ttl_seconds)
            request = self.provider.prepare_authorization(context)
            # Revalidate the provider's pure descriptor against the fixed context.
            if (request.endpoint != settings.provider.authorization_endpoint or request.client_id != context.client_id
                or request.redirect_uri != context.redirect_uri or request.response_type != "code"
                or request.scope != "openid" or request.code_challenge_method != "S256"
                or request.code_challenge != context.code_challenge
                or request.state != context.state or request.nonce != context.nonce):
                raise AuthFlowError()
            url = request.endpoint + "?" + urlencode({"client_id": request.client_id,
                "redirect_uri": request.redirect_uri, "response_type": "code", "scope": "openid",
                "state": context.state.get_secret_value(), "nonce": context.nonce.get_secret_value(),
                "code_challenge": context.code_challenge, "code_challenge_method": "S256"})
            payload = context.model_dump(mode="json")
            for name in ("state", "nonce", "code_verifier"):
                payload[name] = getattr(context, name).get_secret_value()
            encrypted = self._cipher().encrypt_at_time(json.dumps(payload, ensure_ascii=False,
                separators=(",", ":")).encode("utf-8"), int(now.timestamp())).decode("ascii")
            browser_binding = SecretStr(secrets.token_urlsafe(32))
            self.store.save_login(state_digest=digest_secret(context.state, "state"),
                browser_digest=digest_secret(browser_binding, "browser"), provider_id=context.provider_id,
                issuer=context.issuer, client_id=context.client_id, redirect_uri=context.redirect_uri,
                encrypted_context=encrypted, issued_at=context.issued_at, expires_at=context.expires_at)
            return LoginStart(authorization_url=SecretStr(url), browser_binding=browser_binding,
                              expires_at=context.expires_at)
        except AuthFlowError:
            raise
        except (AuthProviderError, ValidationError, ValueError, TypeError, UnicodeError, AttributeError):
            raise AuthFlowError() from None

    def _consume(self, state, browser_binding, *, now: datetime, audit_action="auth.login.consume") -> LoginContext:
        settings = self._validate()
        claimed = self.store.claim_login(digest_secret(state, "state"), digest_secret(browser_binding, "browser"), now=now, audit_action=audit_action)
        try:
            data = self._cipher().decrypt_at_time(claimed.encrypted_context.encode("ascii"),
                ttl=settings.login_ttl_seconds, current_time=int(now.timestamp()))
            context = LoginContext.model_validate(json.loads(data.decode("utf-8"), cls=StrictJSONDecoder))
            context = _context(settings.provider, context)
            if (context.redirect_uri != settings.redirect_uri or not context.issued_at <= now < context.expires_at
                or any(getattr(claimed, name) != getattr(context, name)
                       for name in ("provider_id", "issuer", "client_id", "redirect_uri"))
                or not hmac.compare_digest(digest_secret(context.state, "state"), digest_secret(state, "state"))):
                raise AuthFlowError()
            return context
        except (InvalidToken, AuthProviderError, ValidationError, ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
            raise AuthFlowError() from None

    @audited("auth.login.complete")
    def complete_login(self, code: SecretStr | str, state: SecretStr | str,
                       browser_binding: SecretStr | str, previous_session: SecretStr | str | None = None) -> SessionEstablished:
        settings, now = self._validate(), self._now()
        context = self._consume(state, browser_binding, now=now)
        now = self._now()
        if not context.issued_at <= now < context.expires_at:
            raise AuthFlowError()
        try:
            exchanged = self.provider.exchange_code(SecretStr(secret_value(code)), context, now=now)
            identity = (VerifiedSessionIdentity.model_validate(exchanged) if isinstance(exchanged, VerifiedSessionIdentity)
                        else VerifiedIdentity.model_validate(exchanged))
            if (identity.verification_kind != "oidc" or identity.is_synthetic
                or identity.provider_id != settings.provider.provider_id or identity.identity.issuer != settings.provider.issuer):
                raise AuthFlowError()
            if isinstance(identity, VerifiedSessionIdentity) and identity.client_id != settings.provider.client_id:
                raise AuthFlowError()
        except AuthFlowError:
            raise
        except (AuthProviderError, ValidationError, ValueError, TypeError, UnicodeError):
            raise AuthFlowError() from None
        completed_at = self._now()
        if not context.issued_at <= completed_at < context.expires_at:
            raise AuthFlowError()
        cookie = SecretStr(secrets.token_urlsafe(32))
        try:
            previous_digest = digest_secret(previous_session, "session") if previous_session is not None else None
        except AuthFlowError:
            previous_digest = None  # Malformed previous cookies do not become a new session identity.
        stored = self.store.establish_session(identity.identity, session_digest=digest_secret(cookie, "session"),
            previous_digest=previous_digest, now=completed_at,
            expires_at=completed_at + timedelta(seconds=settings.session_ttl_seconds),
            production=self.runtime_settings.app_environment == "production",
            verified_client_id=identity.client_id if isinstance(identity, VerifiedSessionIdentity) else None,
            assurance=identity.assurance if isinstance(identity, VerifiedSessionIdentity) else None,
            clock=self._now, login_expires_at=context.expires_at)
        return SessionEstablished(user_id=stored.user_id, expires_at=stored.expires_at,
                                  is_synthetic=stored.is_synthetic, session_cookie=cookie)

    @audited("auth.login.cancel")
    def cancel_login(self, state: SecretStr | str, browser_binding: SecretStr | str) -> None:
        self._consume(state, browser_binding, now=self._now(), audit_action="auth.login.cancel")

    def get_session(self, raw_cookie: SecretStr | str) -> SessionSnapshot:
        self._validate()
        stored = self.store.read_session(digest_secret(raw_cookie, "session"), now=self._now(),
            production=self.runtime_settings.app_environment == "production")
        return SessionSnapshot(user_id=stored.user_id, expires_at=stored.expires_at, is_synthetic=stored.is_synthetic)

    def get_principal(self, raw_cookie: SecretStr | str):
        """Internal authorization context; ordinary session HTTP wire is unchanged."""
        self._validate()
        return self.store.read_principal(digest_secret(raw_cookie, "session"), now=self._now(),
            production=self.runtime_settings.app_environment == "production")

    @staticmethod
    def _snapshot(stored) -> SessionSnapshot:
        return SessionSnapshot(user_id=stored.user_id, expires_at=stored.expires_at, is_synthetic=stored.is_synthetic)

    @staticmethod
    def _csrf_digest(token) -> str:
        try:
            value = secret_value(token)
            if re.fullmatch(r"[A-Za-z0-9_-]{43}", value) is None:
                raise ValueError
            return digest_secret(value, "csrf")
        except (AuthFlowError, ValueError, TypeError, UnicodeError):
            raise AuthFlowError(403, "FORBIDDEN") from None

    def get_csrf_token(self, raw_cookie: SecretStr | str) -> CsrfToken:
        self._validate()
        cipher = self._cipher()

        def mint():
            token = secrets.token_urlsafe(32)
            return digest_secret(token, "csrf"), cipher.encrypt(token.encode("ascii")).decode("ascii")

        stored = self.store.get_or_create_csrf(digest_secret(raw_cookie, "session"), now=self._now(),
            production=self.runtime_settings.app_environment == "production", mint=mint, clock=self._now)
        try:
            token = SecretStr(cipher.decrypt(stored.encrypted_token.encode("ascii")).decode("ascii"))
            if not hmac.compare_digest(self._csrf_digest(token), stored.digest):
                raise ValueError
        except (InvalidToken, ValueError, TypeError, UnicodeError):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None
        # Token recovery never extends the original absolute session lifetime.
        self.get_session(raw_cookie)
        return CsrfToken(token=token, expires_at=stored.expires_at)

    def verify_csrf(self, raw_cookie: SecretStr | str, token: SecretStr | str) -> SessionSnapshot:
        self.get_session(raw_cookie)
        stored = self.store.verify_csrf(digest_secret(raw_cookie, "session"), self._csrf_digest(token),
            now=self._now(), production=self.runtime_settings.app_environment == "production", clock=self._now)
        return self._snapshot(stored)

    @audited("auth.logout")
    def logout(self, raw_cookie: SecretStr | str, token: SecretStr | str) -> None:
        # The final proof and active-session checks share the revocation transaction.
        self.get_session(raw_cookie)
        self.store.verify_csrf(digest_secret(raw_cookie, "session"), self._csrf_digest(token),
            now=self._now(), production=self.runtime_settings.app_environment == "production", revoke=True, clock=self._now)

    def create_execution_reference(self, raw_cookie: SecretStr | str) -> ExecutionReference:
        self._validate()
        stored = self.store.read_session(digest_secret(raw_cookie, "session"), now=self._now(),
            production=self.runtime_settings.app_environment == "production")
        return ExecutionReference(session_id=stored.session_id, user_id=stored.user_id)

    def _execution(self, reference: ExecutionReference):
        self._validate()
        try:
            reference = ExecutionReference.model_validate(reference)
        except (ValidationError, ValueError, TypeError):
            raise AuthFlowError() from None
        return self.store.read_execution(reference.session_id, reference.user_id, now=self._now(),
            production=self.runtime_settings.app_environment == "production")

    @staticmethod
    def _permission(stored, verifier):
        try:
            if verifier is None or verifier(AuthService._snapshot(stored)) is not True:
                raise ValueError
        except Exception:
            raise AuthFlowError(403, "FORBIDDEN") from None

    def revalidate_execution(self, reference: ExecutionReference, *, permission_verifier=None) -> SessionSnapshot:
        stored = self._execution(reference)
        self._permission(stored, permission_verifier)
        # Permission callbacks can take time or revoke the actor; do not reuse the earlier read.
        return self._snapshot(self._execution(reference))

    def execute_authenticated(self, reference: ExecutionReference, operation: Callable, *, permission_verifier=None):
        self.revalidate_execution(reference, permission_verifier=permission_verifier)
        reference = ExecutionReference.model_validate(reference)
        # Locks serialize local session revocation while this synchronous operation runs.
        # Cross-system side effects and future queued jobs require their own execution policy.
        def checked_operation(stored):
            # Verifiers must be side-effect free. T07 will supply actual grant checks;
            # this check does not assert atomic permission updates in other resources.
            self._permission(stored, permission_verifier)
            if self._now() >= stored.expires_at:
                raise AuthFlowError()
            return operation(self._snapshot(stored))

        return self.store.execute_current(reference.session_id, reference.user_id, now=self._now,
            production=self.runtime_settings.app_environment == "production",
            operation=checked_operation)

    def check_admin_assurance(self, raw_cookie: SecretStr | str, policy: AdminAssurancePolicy | None = None,
                             *, permission_verifier=None) -> SessionSnapshot:
        settings = self._validate()
        stored = self.store.read_session(digest_secret(raw_cookie, "session"), now=self._now(),
            production=self.runtime_settings.app_environment == "production")
        try:
            current_policy = AdminAssurancePolicy.model_validate(settings.admin_assurance_policy)
            if policy is not None and AdminAssurancePolicy.model_validate(policy) != current_policy:
                raise ValueError
            if (stored.verified_issuer != settings.provider.issuer
                or stored.verified_client_id != settings.provider.client_id):
                raise ValueError
        except (ValidationError, ValueError, TypeError):
            raise AuthFlowError(403, "FORBIDDEN") from None
        check_admin_assurance(stored.assurance, issuer=stored.verified_issuer,
            client_id=stored.verified_client_id, policy=current_policy, now=self._now())
        self._permission(stored, permission_verifier)
        # Re-check session and current policy after the permission callback.
        stored = self._execution(ExecutionReference(session_id=stored.session_id, user_id=stored.user_id))
        latest = self._validate()
        if latest.admin_assurance_policy != current_policy:
            raise AuthFlowError(403, "FORBIDDEN")
        if (stored.verified_issuer != latest.provider.issuer
            or stored.verified_client_id != latest.provider.client_id):
            raise AuthFlowError(403, "FORBIDDEN")
        check_admin_assurance(stored.assurance, issuer=stored.verified_issuer,
            client_id=stored.verified_client_id, policy=current_policy, now=self._now())
        return self._snapshot(stored)


__all__ = ["AuthFlowError", "AuthService", "LoginStart", "SessionEstablished", "SessionSnapshot",
           "CsrfToken", "ExecutionReference", "digest_secret"]
