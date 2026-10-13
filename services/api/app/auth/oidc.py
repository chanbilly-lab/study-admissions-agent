"""Fixed Keycloak code exchange and RS256 verification; no discovery or fallback."""

import base64
import hmac
import json
import math
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Protocol, runtime_checkable
from urllib.parse import quote_plus

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey
from pydantic import SecretStr, ValidationError

from .config import AuthFlowError, SessionAuthSettings, validate_auth_configuration
from .assurance import SessionAssurance, VerifiedSessionIdentity
from .provider import AuthProviderError, _context
from .schemas import AuthorizationRequest, IdentityKey, LoginContext, VerifiedIdentity
from .store import utc_time


def secret_value(value) -> str:
    result = value.get_secret_value() if isinstance(value, SecretStr) else value
    if not isinstance(result, str) or not result or len(result) > 16384:
        raise AuthFlowError()
    try:
        result.encode("utf-8")
    except UnicodeError:
        raise AuthFlowError() from None
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


class StrictJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        kwargs["object_pairs_hook"] = unique_object
        kwargs["parse_constant"] = self.invalid_constant
        super().__init__(*args, **kwargs)

    @staticmethod
    def invalid_constant(value):
        raise ValueError("non-finite JSON number")


@runtime_checkable
class OidcCodeProvider(Protocol):
    def prepare_authorization(self, context: LoginContext) -> AuthorizationRequest: ...
    def exchange_code(self, code: SecretStr, context: LoginContext, *, now: datetime) -> VerifiedIdentity: ...


class KeycloakOidcAdapter:
    def __init__(self, settings: SessionAuthSettings, runtime_settings, *, transport=None):
        self.settings, self.runtime_settings = validate_auth_configuration(settings, runtime_settings)
        self.transport = transport
        self._validate()

    def _validate(self) -> SessionAuthSettings:
        settings, runtime = validate_auth_configuration(self.settings, self.runtime_settings)
        if not settings.enabled or (runtime.app_environment == "production" and self.transport is not None):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        return settings

    def _bound_context(self, context: LoginContext, *, now: datetime | None = None) -> LoginContext:
        settings = self._validate()
        try:
            context = _context(settings.provider, context)
            if context.redirect_uri != settings.redirect_uri:
                raise AuthFlowError()
            if now is not None and not context.issued_at <= utc_time(now) < context.expires_at:
                raise AuthFlowError()
            return context
        except (AuthProviderError, ValidationError, ValueError, TypeError, UnicodeError):
            raise AuthFlowError() from None

    def prepare_authorization(self, context: LoginContext) -> AuthorizationRequest:
        context = self._bound_context(context)
        return AuthorizationRequest(endpoint=self.settings.provider.authorization_endpoint,
            client_id=context.client_id, redirect_uri=context.redirect_uri, state=context.state,
            nonce=context.nonce, code_challenge=context.code_challenge)

    def _json_request(self, method: str, endpoint: str, *, data=None, auth=None, token=False) -> Mapping:
        settings = self._validate()
        try:
            with httpx.Client(transport=self.transport, timeout=settings.transport_timeout_seconds,
                              follow_redirects=False, trust_env=False) as client:
                with client.stream(method, endpoint, data=data, auth=auth,
                                   headers={"Accept": "application/json"}) as response:
                    if response.status_code != 200:
                        raise AuthFlowError(401, "UNAUTHORIZED") if token and response.status_code == 400 else AuthFlowError(503, "SERVICE_UNAVAILABLE")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if len(body) + len(chunk) > settings.max_response_bytes:
                            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
                        body.extend(chunk)
            value = json.loads(bytes(body).decode("utf-8"), cls=StrictJSONDecoder)
            if not isinstance(value, dict):
                raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
            return value
        except AuthFlowError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, UnicodeError, RecursionError):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def _verification_key(self, token: str) -> RSAKey:
        try:
            segments = token.split(".")
            if len(segments) != 3 or any(not segment for segment in segments):
                raise AuthFlowError()
            header_bytes = base64.b64decode(segments[0] + "=" * (-len(segments[0]) % 4),
                                           altchars=b"-_", validate=True)
            header = json.loads(header_bytes.decode("utf-8"), cls=StrictJSONDecoder)
            if (not isinstance(header, dict) or header.get("alg") != "RS256"
                or not isinstance(header.get("kid"), str) or not header["kid"].strip()
                or len(header["kid"]) > 255
                or any(field in header for field in ("jku", "jwk", "x5u", "x5c", "crit", "b64"))):
                raise AuthFlowError()
            document = self._json_request("GET", self.settings.provider.jwks_uri)
            keys = document.get("keys")
            if not isinstance(keys, list) or not 1 <= len(keys) <= 32:
                raise AuthFlowError()
            key_ids = []
            for key in keys:
                if (not isinstance(key, dict) or not isinstance(key.get("kid"), str)
                    or not key["kid"].strip() or len(key["kid"]) > 255
                    or any(part in key for part in ("d", "p", "q", "dp", "dq", "qi", "oth"))):
                    raise AuthFlowError()
                key_ids.append(key["kid"])
            if len(set(key_ids)) != len(key_ids) or header["kid"] not in key_ids:
                raise AuthFlowError()
            selected = keys[key_ids.index(header["kid"])]
            if (selected.get("kty") != "RSA" or selected.get("alg", "RS256") != "RS256"
                or selected.get("use", "sig") != "sig"
                or ("key_ops" in selected and selected["key_ops"] != ["verify"])):
                raise AuthFlowError()
            key = RSAKey.import_key(selected)
            if key.public_key.key_size < 2048 or key.public_key.key_size > 8192:
                raise AuthFlowError()
            return key
        except AuthFlowError:
            raise
        except (JoseError, ValueError, TypeError, UnicodeError, KeyError, RecursionError):
            raise AuthFlowError() from None

    def _verify_token(self, token: str, context: LoginContext, now: datetime, *, started_at: float) -> VerifiedIdentity:
        try:
            key = self._verification_key(token)
            decoded = jwt.decode(token, key, algorithms=["RS256"], decoder_cls=StrictJSONDecoder)
            # The caller's wall clock is a deterministic test seam. Advance it by
            # real elapsed I/O time before claims checks, rather than validating
            # an exp/transaction boundary against a stale pre-network snapshot.
            verified_at = utc_time(now) + timedelta(seconds=max(0.0, monotonic() - started_at))
            context = self._bound_context(context, now=verified_at)
            claims = decoded.claims
            if not isinstance(claims, dict):
                raise AuthFlowError()
            for name in ("iss", "sub", "nonce"):
                if not isinstance(claims.get(name), str) or not claims[name].strip():
                    raise AuthFlowError()
            if (len(claims["sub"]) > 255 or not claims["sub"].isascii()
                or any(ord(character) < 32 or ord(character) == 127 for character in claims["sub"])):
                raise AuthFlowError()
            for name in ("exp", "iat", "nbf"):
                if name in claims and (type(claims[name]) not in (int, float) or not math.isfinite(claims[name])):
                    raise AuthFlowError()
            if "exp" not in claims or "iat" not in claims:
                raise AuthFlowError()
            timestamp = verified_at.timestamp()
            if (claims["exp"] <= timestamp or claims["iat"] > timestamp or claims["exp"] <= claims["iat"]
                or ("nbf" in claims and claims["nbf"] > timestamp)):
                raise AuthFlowError()
            audience = claims.get("aud")
            if isinstance(audience, str):
                audiences = [audience]
            elif isinstance(audience, list) and audience and all(isinstance(item, str) and item for item in audience):
                audiences = audience
            else:
                raise AuthFlowError()
            if self.settings.provider.client_id not in audiences or len(set(audiences)) != len(audiences):
                raise AuthFlowError()
            if ((len(audiences) > 1 and "azp" not in claims)
                or ("azp" in claims and claims["azp"] != self.settings.provider.client_id)):
                raise AuthFlowError()
            registry = jwt.JWTClaimsRegistry(now=int(timestamp), leeway=0,
                iss={"essential": True, "value": self.settings.provider.issuer},
                sub={"essential": True}, aud={"essential": True, "value": self.settings.provider.client_id},
                exp={"essential": True}, iat={"essential": True}, nonce={"essential": True})
            registry.validate(claims)
            if not hmac.compare_digest(claims["nonce"].encode("utf-8"), context.nonce.get_secret_value().encode("utf-8")):
                raise AuthFlowError()
            acr, amr, auth_time = claims.get("acr"), claims.get("amr", []), claims.get("auth_time")
            if ("acr" in claims and not isinstance(acr, str)) or not isinstance(amr, list):
                raise AuthFlowError()
            if "auth_time" in claims:
                if type(auth_time) not in (int, float) or not math.isfinite(auth_time) or auth_time > timestamp:
                    raise AuthFlowError()
                auth_time = datetime.fromtimestamp(auth_time, timezone.utc)
            assurance = SessionAssurance(acr=acr, amr=amr, auth_time=auth_time)
            return VerifiedSessionIdentity(identity=IdentityKey(issuer=claims["iss"], subject=claims["sub"]),
                provider_id=self.settings.provider.provider_id, is_synthetic=False, verification_kind="oidc",
                client_id=self.settings.provider.client_id, assurance=assurance)
        except AuthFlowError:
            raise
        except (JoseError, ValidationError, ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
            raise AuthFlowError() from None

    def exchange_code(self, code: SecretStr, context: LoginContext, *, now: datetime) -> VerifiedIdentity:
        settings = self._validate()
        context = self._bound_context(context, now=now)
        code_value = secret_value(code)
        started_at = monotonic()
        document = self._json_request("POST", settings.provider.token_endpoint, token=True,
            auth=httpx.BasicAuth(quote_plus(settings.provider.client_id, safe=""),
                                quote_plus(settings.provider.client_secret.get_secret_value(), safe="")),
            data={"grant_type": "authorization_code", "code": code_value,
                  "redirect_uri": context.redirect_uri, "code_verifier": context.code_verifier.get_secret_value()})
        raw_token = document.get("id_token")
        if not isinstance(raw_token, str) or not raw_token or len(raw_token) > 16384 or "error" in document:
            raise AuthFlowError()
        return self._verify_token(raw_token, context, now, started_at=started_at)
