"""Production foundation assembly, without importing the M0 application."""

from collections.abc import Mapping, Sequence

from fastapi import FastAPI

from ..settings import V2RuntimeSettings
from .catalog_access import CatalogCandidate
from .v2 import create_v2_app
from .v2.errors import ApiError, error_response
from .v2.router import reject_demo_credentials


def create_public_app(settings: V2RuntimeSettings | None = None, *,
                      catalog_candidates: Sequence[CatalogCandidate | Mapping] | None = None) -> FastAPI:
    settings = V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    if settings.app_environment != "production" or settings.data_mode != "verified":
        raise ValueError("public foundation requires production and verified runtime settings")
    app = FastAPI(title="升学咨询 production foundation", version="v2.t03",
                  description="仅隔离的配置与空目录；公众业务尚不可用。",
                  openapi_url=None, docs_url=None, redoc_url=None)
    app.state.runtime_settings = settings

    @app.middleware("http")
    async def public_v2_credentials(request, call_next):
        # Starlette can redirect the exact mount path before the child runs.
        # Keep all v2 paths covered, while root and absent v1 stay unreachable.
        path = request.scope["path"]
        if path == "/v2" or path.startswith("/v2/"):
            try:
                reject_demo_credentials(request)
            except ApiError as error:
                return error_response(request, error.status_code, error.code,
                                      details=error.details, headers=error.headers)
        return await call_next(request)

    app.mount("/v2", create_v2_app(settings, catalog_candidates=catalog_candidates))
    return app


__all__ = ["create_public_app"]
