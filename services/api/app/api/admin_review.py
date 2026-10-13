"""Opt-in T22 private workflow and separately mounted anonymous preview."""

from fastapi import FastAPI

from ..admin.review_http.router import REQUEST_MODELS, router
from ..auth.config import AuthFlowError
from ..settings import V2RuntimeSettings
from .admin import create_admin_v2_app
from .public_catalog import create_public_catalog_v2_app


def create_admin_review_v2_app(settings: V2RuntimeSettings | None = None, *, identity_service=None,
    source_service=None, storage_service=None, import_service=None, evidence_service=None,
    fact_service=None, review_service=None, release_service=None) -> FastAPI:
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    app = create_admin_v2_app(runtime, identity_service=identity_service, source_service=source_service,
        storage_service=storage_service, import_service=import_service)
    app.title, app.version = "升学咨询 T22 审核与发布管理", "v2.t22"
    app.state.admin_review_facade = None
    chain = (evidence_service, fact_service, review_service, release_service)
    if any(service is not None for service in chain):
        if app.state.admin_facade is None or any(service is None for service in chain):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        from ..admin.review_http.facade import ReviewFacade
        app.state.admin_review_facade = ReviewFacade(app.state.admin_facade, *chain)
    app.include_router(router)
    original_openapi = app.openapi

    def review_openapi():
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
                        if parameter.get("in") == "path" and parameter.get("name") in {
                            "source_id", "import_id", "fact_id", "release_id"
                        }:
                            parameter["schema"]["format"] = "uuid"
        return schema

    app.openapi = review_openapi
    return app


def create_admin_review_app(settings: V2RuntimeSettings | None = None, *, reader=None, **services) -> FastAPI:
    private = create_admin_review_v2_app(settings, **services)
    runtime = private.state.runtime_settings
    public_runtime = runtime
    if reader is not None:
        from ..public_catalog.reader import CatalogReader
        release = services.get("release_service")
        if (not isinstance(reader, CatalogReader) or release is None or reader.release_service is not release
            or reader.store.engine is not release.store.engine):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
        reader._validate()
        public_runtime = reader.settings
        if public_runtime != runtime and not (runtime.app_environment == public_runtime.app_environment == "test"
            and runtime.data_mode == "verified" and public_runtime.data_mode == "demo"
            and public_runtime.model_mode == "disabled" and reader.policy.allow_test_fixture_read):
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
    app = FastAPI(title="T22 私有审核与匿名公开预览", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.runtime_settings = runtime
    app.mount("/v2", private)
    app.mount("/public/v2", create_public_catalog_v2_app(public_runtime, reader=reader))
    return app


__all__ = ["create_admin_review_v2_app", "create_admin_review_app"]
