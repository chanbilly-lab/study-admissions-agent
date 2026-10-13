"""Independent closed public-catalog-backed QA factory; no implicit services."""

from fastapi import FastAPI

from ..qa.http_schemas import QAV2RuntimeSettings
from ..qa.router import router
from ..qa.schemas import RetrievalRequest
from ..settings import V2RuntimeSettings
from .public_catalog import create_public_catalog_v2_app, _public_error
from .v2.errors import ApiError, error_response, request_id
from .v2.router import reject_demo_credentials
from .v2.schemas import ErrorDetail


def create_qa_v2_app(settings=None, *, reader=None, qa_service=None):
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else QAV2RuntimeSettings()
    if qa_service is not None:
        from ..qa.service import QAService
        if (type(qa_service) is not QAService or qa_service.settings != runtime
            or qa_service.retriever.reader is not reader):
            raise ApiError(503, "SERVICE_UNAVAILABLE")
        qa_service.preflight()
    app = create_public_catalog_v2_app(runtime, reader=reader)
    app.title, app.version = "升学咨询 T39 公开证据问答", "v2.t39"
    app.state.qa_service = qa_service
    app.include_router(router)
    initial_runtime = V2RuntimeSettings.model_validate(runtime)
    @app.middleware("http")
    async def frozen_qa_context(request, call_next):
        path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
        if not path.startswith("/qa/"):
            return await call_next(request)
        try:
            current = V2RuntimeSettings.model_validate(request.app.state.runtime_settings)
            if (current != initial_runtime or request.app.state.public_catalog_reader is not reader
                or request.app.state.qa_service is not qa_service):
                raise ValueError()
        except Exception:
            response = error_response(request, 503, "SERVICE_UNAVAILABLE", details=[ErrorDetail(
                field_path="qa", code="QA_UNAVAILABLE", message="问答配置当前不可用")])
            response.headers["Cache-Control"] = "no-store"
            return response
        return await call_next(request)
    original = app.openapi

    def qa_openapi():
        document = original()
        components = document.setdefault("components", {}).setdefault("schemas", {})
        definition = RetrievalRequest.model_json_schema(ref_template="#/components/schemas/{model}")
        components.update(definition.pop("$defs", {}))
        components["RetrievalRequest"] = definition
        return document

    app.openapi = qa_openapi
    return app


def create_qa_app(settings=None, *, reader=None, qa_service=None):
    child = create_qa_v2_app(settings, reader=reader, qa_service=qa_service)
    app = FastAPI(title="升学咨询 T39 公开问答", version="v2.t39", openapi_url=None, docs_url=None, redoc_url=None)
    app.state.runtime_settings = child.state.runtime_settings
    @app.middleware("http")
    async def public_context(request, call_next):
        identifier = request_id(request)
        try:
            reject_demo_credentials(request)
            response = await call_next(request)
        except ApiError as error:
            response = _public_error(request, error)
        except Exception:
            response = error_response(request, 500, "INTERNAL_ERROR")
        response.headers.update({"X-Request-ID": identifier, "Cache-Control": "no-store"})
        return response
    app.mount("/v2", child)
    return app


__all__ = ["create_qa_app", "create_qa_v2_app"]
