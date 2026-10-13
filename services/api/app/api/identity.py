"""Explicit identity application profile; default closed, no implicit DDL."""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import re
from time import monotonic

from fastapi import FastAPI

from ..auth.config import AuthFlowError, SessionAuthSettings, validate_auth_configuration
from ..auth.router import router as identity_router
from ..auth.http_security import identity_security
from ..privacy.config import PrivacySettings
from ..privacy.router import router as privacy_router
from ..auth.grants.schemas import SharingSettings
from ..auth.grants.router import router as sharing_router
from ..settings import V2RuntimeSettings
from .v2 import create_v2_app
from .v2.errors import ApiError, error_response
from .v2.errors import request_id
from .v2.router import reject_demo_credentials
from ..audit.context import request_context, current_actor, failure_handled
from ..audit.logging import emit


_REQUEST_OPERATIONS = (
    ("GET", r"/auth/login", "startV2Login", "auth.login.start"),
    ("GET", r"/auth/callback", "completeV2Login", "auth.login.complete"),
    ("POST", r"/auth/logout", "logoutV2Session", "auth.logout"),
    ("POST", r"/me/age-declarations", "declareV2Age", "privacy.adult.declare"),
    ("POST", r"/me/consents", "confirmV2CoreConsent", "privacy.core.confirm"),
    ("DELETE", r"/me/consents/[^/]+", "withdrawV2CoreConsent", "privacy.core.withdraw"),
    ("POST", r"/access-grants", "createV2AccessGrant", "sharing.grant.create"),
    ("POST", r"/access-grants/[^/]+/accept", "acceptV2AccessGrant", "sharing.grant.accept"),
    ("DELETE", r"/access-grants/[^/]+", "revokeV2AccessGrant", "sharing.grant.revoke"),
)


async def identity_audit_context(request, call_next):
    """Fixed request metadata only; neither URL values nor exception text leak."""
    from starlette.concurrency import run_in_threadpool
    identifier, started = request_id(request), monotonic()
    with request_context(identifier):
        try:
            response = await call_next(request)
        except Exception:
            response = error_response(request, 500, "INTERNAL_ERROR")
        route = request.scope.get("route")
        operation = getattr(route, "operation_id", None)
        path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
        action = None
        for method, pattern, fixed_operation, fixed_action in _REQUEST_OPERATIONS:
            if request.method == method and re.fullmatch(pattern, path):
                operation, action = fixed_operation, fixed_action
                break
        from typing import get_args
        from ..audit.logging import OperationId
        if operation not in get_args(OperationId):
            operation = "request.completed" if response.status_code < 400 else "request.failed"
        reasons = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT",
                   422: "VALIDATION_ERROR", 503: "SERVICE_UNAVAILABLE", 500: "INTERNAL_ERROR"}
        reason = reasons.get(response.status_code, "INTERNAL_ERROR" if response.status_code >= 400 else "OK")
        service = getattr(request.app.state, "identity_service", None)
        if action is not None and response.status_code >= 400 and service is not None and not failure_handled():
            # Guard/validation failures occur before an operation transaction.
            # Supplied-session failures mark deferred and remain the outer
            # transaction owner's responsibility rather than opening a connection.
            await run_in_threadpool(service.store.audit.failure, action,
                                    ApiError(response.status_code, reason), actor=current_actor())
        emit(operation, status=response.status_code, reason_code=reason,
             duration_ms=min(86400000, max(0, int((monotonic() - started) * 1000))))
        return response


def create_identity_v2_app(settings: V2RuntimeSettings | None = None, *,
                           identity_service=None, privacy_settings: PrivacySettings | None = None,
                           sharing_settings: SharingSettings | None = None) -> FastAPI:
    """Schema/test child factory: never constructs a provider, engine or migration."""
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    try:
        privacy = PrivacySettings.model_validate(privacy_settings) if privacy_settings is not None else PrivacySettings()
        if privacy.fixture_mode and (runtime.app_environment != "test" or identity_service is None):
            raise ValueError
        sharing = SharingSettings.model_validate(sharing_settings) if sharing_settings is not None else SharingSettings()
        if sharing.fixture_mode and (runtime.app_environment != "test" or not privacy.fixture_mode or identity_service is None):
            raise ValueError
    except (ValueError, TypeError):
        raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None
    if identity_service is not None:
        # Injection is an internal assembly seam, never a client-selected provider.
        from ..auth.service import AuthService
        if not isinstance(identity_service, AuthService):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        validate_auth_configuration(identity_service.settings, runtime)
        if identity_service.runtime_settings != runtime:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        identity_service._validate()
    app = create_v2_app(runtime)
    app.title, app.version = "升学咨询 T09 identity", "v2.t09"
    app.description = "显式认证配置；登录不开放真实画像、申请或业务权限。"
    app.state.identity_service = identity_service
    app.state.authorization_service = None
    app.state.privacy_settings = privacy
    app.state.privacy_service = None
    app.state.sharing_settings = sharing
    app.state.sharing_service = None
    if identity_service is not None:
        from ..auth.authorization import Authorizer
        app.state.authorization_service = Authorizer(identity_service)
        from ..privacy.service import PrivacyService
        app.state.privacy_service = PrivacyService(identity_service, privacy)
        from ..auth.grants.service import SharingService
        app.state.sharing_service = SharingService(identity_service, app.state.privacy_service, sharing)

    async def identity_flow_error(request, error):
        # Authorization service errors retain their safe 401/403/404/409/503
        # semantics even in future routes that call the service directly.
        return error_response(request, error.status_code, error.code)

    app.add_exception_handler(AuthFlowError, identity_flow_error)

    app.middleware("http")(identity_security)
    app.middleware("http")(identity_audit_context)

    app.include_router(identity_router)
    app.include_router(privacy_router)
    app.include_router(sharing_router)
    original_openapi = app.openapi

    def identity_openapi():
        schema = original_openapi()
        schema.setdefault("components", {})["securitySchemes"] = {
            "SessionCookie": {"type": "apiKey", "in": "cookie", "name": "__Host-admissions-session"},
            "LoginBindingCookie": {"type": "apiKey", "in": "cookie", "name": "__Host-admissions-login"},
            "CsrfHeader": {"type": "apiKey", "in": "header", "name": "X-CSRF-Token"},
            "RequestOrigin": {"type": "apiKey", "in": "header", "name": "Origin",
                              "description": "Must exactly match the server-registered application origin"},
        }
        schema["paths"]["/auth/session"]["get"]["security"] = [{"SessionCookie": []}]
        schema["paths"]["/auth/callback"]["get"]["security"] = [{"LoginBindingCookie": []}]
        schema["paths"]["/auth/csrf"]["get"]["security"] = [{"SessionCookie": []}]
        schema["paths"]["/auth/logout"]["post"]["security"] = [
            {"SessionCookie": [], "CsrfHeader": [], "RequestOrigin": []}]
        schema["paths"]["/me/admission"]["get"]["security"] = [{"SessionCookie": []}]
        for path, method in (("/me/age-declarations", "post"), ("/me/consents", "post"),
                             ("/me/consents/{consent_id}", "delete"), ("/access-grants", "post"),
                             ("/access-grants/{grant_id}/accept", "post"), ("/access-grants/{grant_id}", "delete")):
            schema["paths"][path][method]["security"] = [
                {"SessionCookie": [], "CsrfHeader": [], "RequestOrigin": []}]
        schema["paths"]["/access-grants"]["get"]["security"] = [{"SessionCookie": []}]
        return schema

    app.openapi = identity_openapi
    return app


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate configuration field")
        result[key] = value
    return result


def load_session_auth_settings() -> SessionAuthSettings:
    """Only an explicit JSON path and process secrets enable the profile; no dotenv."""
    configured_path = os.environ.get("IDENTITY_CONFIG_FILE")
    if not configured_path:
        return SessionAuthSettings()
    try:
        path = Path(configured_path)
        if not path.is_file() or path.stat().st_size > 65536:
            raise ValueError
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json)
        if not isinstance(payload, dict) or "context_encryption_key" in payload:
            raise ValueError
        provider = payload.get("provider", {})
        if not isinstance(provider, dict) or "client_secret" in provider:
            raise ValueError
        if payload.get("enabled") is True:
            # Missing secrets remain missing, so model validation fails closed.
            payload["provider"] = {**provider, "client_secret": os.environ.get("IDENTITY_CLIENT_SECRET")}
            payload["context_encryption_key"] = os.environ.get("IDENTITY_CONTEXT_KEY")
        return SessionAuthSettings.model_validate(payload)
    except (OSError, ValueError, TypeError, UnicodeError):
        raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None


def create_identity_app(settings: V2RuntimeSettings | None = None,
                        auth_settings: SessionAuthSettings | None = None,
                        privacy_settings: PrivacySettings | None = None,
                        sharing_settings: SharingSettings | None = None) -> FastAPI:
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    configuration = auth_settings if auth_settings is not None else load_session_auth_settings()
    configuration, runtime = validate_auth_configuration(configuration, runtime)
    try:
        privacy_settings = PrivacySettings.model_validate(privacy_settings) if privacy_settings is not None else PrivacySettings()
        if privacy_settings.fixture_mode and (runtime.app_environment != "test" or not configuration.enabled):
            raise ValueError
        sharing_settings = SharingSettings.model_validate(sharing_settings) if sharing_settings is not None else SharingSettings()
        if sharing_settings.fixture_mode and (runtime.app_environment != "test" or not privacy_settings.fixture_mode or not configuration.enabled):
            raise ValueError
    except (ValueError, TypeError):
        raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None
    engine = None
    service = None
    if configuration.enabled:
        if runtime.database_url is None:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        # The closed profile never imports SQLAlchemy, JOSE or persistence.
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        from ..auth.oidc import KeycloakOidcAdapter
        from ..auth.service import AuthService
        from ..auth.store import AuthStore
        try:
            database = make_url(runtime.database_url.get_secret_value()).set(drivername="postgresql+psycopg")
            engine = create_engine(database, pool_pre_ping=True, hide_parameters=True)
            store = AuthStore(engine)
            store.assert_schema_ready()
            service = AuthService(configuration, runtime, store, KeycloakOidcAdapter(configuration, runtime))
        except Exception:
            if engine is not None:
                engine.dispose()
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    app = FastAPI(title="升学咨询 T09 identity", version="v2.t09", lifespan=lifespan,
                  openapi_url=None, docs_url=None, redoc_url=None)
    app.state.runtime_settings = runtime

    @app.middleware("http")
    async def parent_identity_boundary(request, call_next):
        path = request.scope["path"]
        if path == "/v2" or path.startswith("/v2/"):
            try:
                reject_demo_credentials(request)
            except ApiError as error:
                response = error_response(request, error.status_code, error.code)
                response.headers["Cache-Control"] = "no-store"
                response.headers["Pragma"] = "no-cache"
                response.headers["Referrer-Policy"] = "no-referrer"
                return response
        return await call_next(request)

    app.mount("/v2", create_identity_v2_app(runtime, identity_service=service, privacy_settings=privacy_settings,
                                         sharing_settings=sharing_settings))
    return app
