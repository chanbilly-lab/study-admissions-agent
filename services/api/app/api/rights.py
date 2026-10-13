"""Explicit T40 factory; default closed, no database or worker construction."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from ..auth.config import AuthFlowError
from ..privacy.rights.router import REQUEST_MODELS, router
from ..privacy.rights.service import RightsService
from ..settings import V2RuntimeSettings
from .notifications import create_notifications_v2_app
from .v2.errors import error_response


def create_rights_v2_app(settings: V2RuntimeSettings | None = None, *, rights_service=None, **services):
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    if rights_service is not None:
        if type(rights_service) is not RightsService or rights_service.auth_service is not services.get("identity_service"):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        rights_service._validate()
    app = create_notifications_v2_app(runtime, **services)
    app.title, app.version = "升学咨询 T40 data rights", "v2.t40"
    app.state.rights_service = rights_service
    app.include_router(router)
    @app.middleware("http")
    async def restore_barrier(request, call_next):
        try:
            if app.state.rights_service is not rights_service:
                raise ValueError()
            if rights_service is not None:
                rights_service._validate()
                await run_in_threadpool(rights_service.guard.ensure_ready)
            return await call_next(request)
        except Exception:
            response = error_response(request, 503, "SERVICE_UNAVAILABLE")
            response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"})
            return response
    if rights_service is not None:
        previous = app.router.lifespan_context
        @asynccontextmanager
        async def lifespan(application):
            async with previous(application):
                await run_in_threadpool(rights_service.store.assert_schema_ready)
                await run_in_threadpool(rights_service.guard.ensure_ready)
                yield
        app.router.lifespan_context = lifespan

    @app.middleware("http")
    async def rights_context(request, call_next):
        path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
        if not path.startswith(("/privacy/rights/", "/privacy/exports", "/privacy/deletions")):
            return await call_next(request)
        try:
            response = await call_next(request)
        except Exception:
            response = error_response(request, 500, "INTERNAL_ERROR")
        response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"})
        return response

    original = app.openapi
    def rights_openapi():
        document = original()
        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        for model in REQUEST_MODELS:
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            schemas.update(definition.pop("$defs", {}))
            schemas[model.__name__] = definition
        for path, operations in document["paths"].items():
            if not path.startswith(("/privacy/rights/", "/privacy/exports", "/privacy/deletions")):
                continue
            for method, operation in operations.items():
                if method not in {"get", "post"}:
                    continue
                operation["security"] = [{"SessionCookie": [], **({"CsrfHeader": [], "RequestOrigin": []} if method == "post" else {})}]
                if path == "/privacy/rights/context":
                    operation["security"].append({})  # Only the disabled disclosure is anonymous.
                for parameter in operation.get("parameters", []):
                    if parameter.get("in") == "path" and parameter.get("name") == "request_id":
                        parameter["schema"] = {"type": "string", "format": "uuid"}
        return document
    app.openapi = rights_openapi
    return app


def create_rights_app(settings: V2RuntimeSettings | None = None, **services):
    app = FastAPI(title="Explicit private data rights application", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/v2", create_rights_v2_app(settings, **services))
    return app
