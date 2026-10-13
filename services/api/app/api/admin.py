"""Opt-in administration profile; frozen applications are not modified."""

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from ..admin.http.router import REQUEST_MODELS, router as admin_router
from ..audit.context import current_actor, failure_handled, request_context
from ..auth.config import AuthFlowError
from ..settings import V2RuntimeSettings
from .identity import create_identity_v2_app
from .v2.errors import ApiError, error_response, request_id


def create_admin_v2_app(settings: V2RuntimeSettings | None = None, *, identity_service=None,
                        source_service=None, storage_service=None, import_service=None) -> FastAPI:
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    app = create_identity_v2_app(runtime, identity_service=identity_service)
    app.title, app.version = "升学咨询 T21 source/import administration", "v2.t21"
    app.state.admin_facade = None
    services = (source_service, storage_service, import_service)
    if any(service is not None for service in services):
        if identity_service is None or any(service is None for service in services):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        from ..admin.http.facade import AdminFacade
        app.state.admin_facade = AdminFacade(identity_service, *services, runtime)
    app.include_router(admin_router)

    @app.middleware("http")
    async def admin_context(request, call_next):
        path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
        if not path.startswith("/admin/"):
            return await call_next(request)
        with request_context(request_id(request)):
            try:
                response = await call_next(request)
            except Exception:
                response = error_response(request, 500, "INTERNAL_ERROR")
            if response.status_code >= 400 and identity_service is not None and not failure_handled():
                status = response.status_code if response.status_code in (401, 403, 404, 409, 422, 503, 500) else 500
                from .v2.errors import STATUS_CODES
                try:
                    await run_in_threadpool(identity_service.store.audit.failure, "administrator.action",
                        ApiError(status, STATUS_CODES[status]), actor=current_actor())
                except Exception:
                    pass
            response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache",
                                     "Referrer-Policy": "no-referrer"})
            return response

    original_openapi = app.openapi

    def admin_openapi():
        schema = original_openapi()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in REQUEST_MODELS:
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            components.update(definition.pop("$defs", {}))
            components[model.__name__] = definition
        for path, methods in schema["paths"].items():
            if path.startswith("/admin/"):
                for method, operation in methods.items():
                    if method not in {"get", "post", "put"}:
                        continue
                    security = {"SessionCookie": []}
                    if method in {"post", "put"}:
                        security.update({"CsrfHeader": [], "RequestOrigin": []})
                    operation["security"] = [security]
                    for parameter in operation.get("parameters", []):
                        if parameter.get("in") == "path" and parameter.get("name") in {"source_id", "import_id"}:
                            parameter["schema"]["format"] = "uuid"
        return schema

    app.openapi = admin_openapi
    return app


def create_admin_app(settings: V2RuntimeSettings | None = None, **services) -> FastAPI:
    app = FastAPI(title="Explicit source/import administration", docs_url=None,
                  redoc_url=None, openapi_url=None)
    app.mount("/v2", create_admin_v2_app(settings, **services))
    return app
