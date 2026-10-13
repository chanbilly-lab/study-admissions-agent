"""Explicit assessment factory; closed construction performs no domain I/O."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from ..audit.context import current_actor, failure_handled, request_context
from ..auth.config import AuthFlowError
from ..rules.router import REQUEST_MODELS, router
from ..settings import V2RuntimeSettings
from .profiles import create_profiles_v2_app
from .v2.errors import ApiError, STATUS_CODES, error_response, request_id


def create_assessments_v2_app(settings: V2RuntimeSettings | None = None, *, identity_service=None,
                              profile_service=None, assessment_service=None) -> FastAPI:
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    if assessment_service is not None:
        from ..rules.service import EligibilityService
        if (not isinstance(assessment_service, EligibilityService) or identity_service is None
            or assessment_service.auth_service is not identity_service
            or assessment_service.profile_service is not profile_service):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        assessment_service._validate()
    app = create_profiles_v2_app(runtime, identity_service=identity_service, profile_service=profile_service)
    app.title, app.version = "升学咨询 T28 private assessments", "v2.t28"
    app.state.assessment_service = assessment_service
    app.include_router(router)
    if assessment_service is not None:
        previous_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(application):
            async with previous_lifespan(application):
                await run_in_threadpool(assessment_service.store.assert_schema_ready)
                yield
        app.router.lifespan_context = lifespan

    @app.middleware("http")
    async def assessment_context(request, call_next):
        path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
        if not path.startswith("/eligibility/"):
            return await call_next(request)
        with request_context(request_id(request)):
            try:
                response = await call_next(request)
            except Exception:
                response = error_response(request, 500, "INTERNAL_ERROR")
            if response.status_code >= 400 and identity_service is not None and not failure_handled():
                status = response.status_code if response.status_code in STATUS_CODES else 500
                try:
                    await run_in_threadpool(identity_service.store.audit.failure, "authorization.owned.execute",
                        ApiError(status, STATUS_CODES[status]), actor=current_actor())
                except Exception:
                    pass
            response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"})
            return response

    original = app.openapi
    def assessment_openapi():
        schema = original()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in REQUEST_MODELS:
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            components.update(definition.pop("$defs", {}))
            components[model.__name__] = definition
        for path, operations in schema["paths"].items():
            if path.startswith("/eligibility/"):
                for method, operation in operations.items():
                    if method not in {"get", "post"}:
                        continue
                    security = {"SessionCookie": []}
                    if method == "post":
                        security.update({"CsrfHeader": [], "RequestOrigin": []})
                    operation["security"] = [security]
                    for parameter in operation.get("parameters", []):
                        if parameter.get("in") == "path" and parameter.get("name") == "assessment_id":
                            parameter["schema"]["format"] = "uuid"
        return schema
    app.openapi = assessment_openapi
    return app


def create_assessments_app(settings: V2RuntimeSettings | None = None, **services) -> FastAPI:
    app = FastAPI(title="Explicit private assessment application", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/v2", create_assessments_v2_app(settings, **services))
    return app
