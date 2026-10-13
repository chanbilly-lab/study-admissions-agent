"""Standalone v2 application factory; does not import database or model services."""

from collections.abc import Mapping, Sequence

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from ...settings import V2RuntimeSettings
from ..catalog_access import CatalogAccessPolicy, CatalogCandidate
from .errors import (
    ApiError, error_response, handle_api_error, handle_http_error,
    handle_validation_error, request_id,
)
from .router import reject_demo_credentials, router


def create_v2_app(settings: V2RuntimeSettings | None = None, *,
                  catalog_candidates: Sequence[CatalogCandidate | Mapping] | None = None) -> FastAPI:
    settings = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    app = FastAPI(title="升学咨询 v2 foundation", version="v2.t03",
                  description="仅基础契约和空目录；未提供真实或合成招生业务。",
                  servers=[{"url": "/v2"}], root_path_in_servers=False,
                  docs_url=None, redoc_url=None)
    app.state.runtime_settings = settings
    app.state.catalog_policy = CatalogAccessPolicy(data_mode=settings.data_mode)
    app.state.catalog_candidates = tuple(catalog_candidates or ())
    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)

    @app.middleware("http")
    async def v2_request_context(request, call_next):
        identifier = request_id(request)
        try:
            reject_demo_credentials(request)
            response = await call_next(request)
        except ApiError as error:
            response = error_response(request, error.status_code, error.code,
                                      details=error.details, headers=error.headers)
        except Exception:
            # Handle ordinary endpoint/serialization failures inside v2 so the
            # mounted parent's middleware receives a normal safe response.
            response = error_response(request, 500, "INTERNAL_ERROR")
        response.headers["X-Request-ID"] = identifier
        return response

    app.include_router(router)
    return app


__all__ = ["create_v2_app"]
