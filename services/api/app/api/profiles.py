"""Opt-in T23 profile; default construction has no database or provider I/O."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from ..audit.context import current_actor, failure_handled, request_context
from ..auth.config import AuthFlowError
from ..profiles.router import REQUEST_MODELS, router
from ..settings import V2RuntimeSettings
from .identity import create_identity_v2_app
from .v2.errors import ApiError, STATUS_CODES, error_response, request_id


def create_profiles_v2_app(settings: V2RuntimeSettings | None = None, *, identity_service=None,
                           profile_service=None) -> FastAPI:
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    privacy_settings = None
    if profile_service is not None:
        from ..profiles.service import ProfileService
        if (identity_service is None or not isinstance(profile_service, ProfileService)
            or profile_service.auth_service is not identity_service):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        profile_service._validate()
        privacy_settings = profile_service.privacy_service.settings
    app = create_identity_v2_app(runtime, identity_service=identity_service, privacy_settings=privacy_settings)
    app.title, app.version = "升学咨询 T23 private profile versions", "v2.t23"
    app.state.profile_service = None
    if profile_service is not None:
        from ..profiles.service import ProfileService
        if (identity_service is None or not isinstance(profile_service, ProfileService)
            or profile_service.auth_service is not identity_service):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        profile_service._validate()
        app.state.profile_service = profile_service
        previous_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(application):
            async with previous_lifespan(application):
                await run_in_threadpool(identity_service.store.assert_schema_ready)
                await run_in_threadpool(profile_service.idempotency_service.store.assert_schema_ready)
                await run_in_threadpool(profile_service.store.assert_schema_ready)
                yield

        app.router.lifespan_context = lifespan
    app.include_router(router)

    @app.middleware("http")
    async def profile_context(request, call_next):
        path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
        if path != "/profiles" and not path.startswith("/profiles/"):
            return await call_next(request)
        with request_context(request_id(request)):
            try:
                response = await call_next(request)
            except Exception:
                response = error_response(request, 500, "INTERNAL_ERROR")
            if response.status_code >= 400 and identity_service is not None and not failure_handled():
                status = response.status_code if response.status_code in STATUS_CODES else 500
                try:
                    await run_in_threadpool(identity_service.store.audit.failure, "authorization.owned.check",
                        ApiError(status, STATUS_CODES[status]), actor=current_actor())
                except Exception:
                    pass
            response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"})
            return response

    original = app.openapi

    def profile_openapi():
        schema = original()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in REQUEST_MODELS:
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            components.update(definition.pop("$defs", {}))
            components[model.__name__] = definition
        for path, operations in schema["paths"].items():
            if path == "/profiles" or path.startswith("/profiles/"):
                for method, operation in operations.items():
                    if method not in {"get", "post"}:
                        continue
                    security = {"SessionCookie": []}
                    if method == "post":
                        security.update({"CsrfHeader": [], "RequestOrigin": []})
                    operation["security"] = [security]
                    for parameter in operation.get("parameters", []):
                        if parameter.get("in") == "path" and parameter.get("name") in {"profile_id", "version_id"}:
                            parameter["schema"]["format"] = "uuid"
        return schema

    app.openapi = profile_openapi
    return app


def create_profiles_app(settings: V2RuntimeSettings | None = None, **services) -> FastAPI:
    app = FastAPI(title="Explicit private profile application", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/v2", create_profiles_v2_app(settings, **services))
    return app
