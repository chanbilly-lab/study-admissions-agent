"""Explicit T20 anonymous read profile; no implicit engine, provider or DDL."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from ..settings import V2RuntimeSettings
from .v2.errors import (
    ApiError, error_response, handle_http_error,
    handle_validation_error, request_id,
)
from .v2.router import reject_demo_credentials
from .v2.schemas import ErrorBody, ErrorEnvelope


def _public_error(request, error: ApiError):
    if error.code != "INVALID_CURSOR":
        return error_response(request, error.status_code, error.code,
                              details=error.details, headers=error.headers)
    identifier = request_id(request)
    payload = ErrorEnvelope(error=ErrorBody(code="INVALID_CURSOR",
        message="分页游标无效或与查询不匹配", request_id=identifier, details=error.details))
    return JSONResponse(status_code=422, content=payload.model_dump(mode="json"),
                        headers={"X-Request-ID": identifier, "Cache-Control": "no-store"})


async def _handle_public_error(request, error: ApiError):
    return _public_error(request, error)


def create_public_catalog_v2_app(settings: V2RuntimeSettings | None = None, *, reader=None) -> FastAPI:
    """Closed schema/config factory unless a matching frozen reader is injected."""
    runtime = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    if reader is not None:
        from ..public_catalog.reader import CatalogReader
        if not isinstance(reader, CatalogReader) or reader.settings != runtime:
            raise ApiError(503, "SERVICE_UNAVAILABLE")
        try:
            reader._validate()
        except Exception:
            raise ApiError(503, "SERVICE_UNAVAILABLE") from None
    from .v2.public_catalog import router
    app = FastAPI(title="升学咨询 T20 公共目录", version="v2.t20",
                  description="匿名只读当前已发布项目及获准公开证据；真实公开默认关闭。",
                  servers=[{"url": "/v2"}], root_path_in_servers=False,
                  openapi_url=None, docs_url=None, redoc_url=None)
    app.state.runtime_settings = runtime
    app.state.public_catalog_reader = reader
    app.add_exception_handler(ApiError, _handle_public_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)

    @app.middleware("http")
    async def public_catalog_context(request, call_next):
        identifier = request_id(request)
        try:
            reject_demo_credentials(request)
            response = await call_next(request)
        except ApiError as error:
            response = _public_error(request, error)
        except Exception:
            response = error_response(request, 500, "INTERNAL_ERROR")
        response.headers["X-Request-ID"] = identifier
        response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router)
    return app


def create_public_catalog_app(settings: V2RuntimeSettings | None = None, *, reader=None) -> FastAPI:
    """Parent exposes only the isolated /v2 read profile, including test injection."""
    child = create_public_catalog_v2_app(settings, reader=reader)
    app = FastAPI(title="升学咨询 T20 公共只读", version="v2.t20",
                  openapi_url=None, docs_url=None, redoc_url=None)
    app.state.runtime_settings = child.state.runtime_settings

    @app.middleware("http")
    async def mount_context(request, call_next):
        identifier = request_id(request)
        try:
            reject_demo_credentials(request)
            response = await call_next(request)
        except ApiError as error:
            response = _public_error(request, error)
        except Exception:
            response = error_response(request, 500, "INTERNAL_ERROR")
        response.headers["X-Request-ID"] = identifier
        response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/v2", child)
    return app


__all__ = ["create_public_catalog_app", "create_public_catalog_v2_app"]
