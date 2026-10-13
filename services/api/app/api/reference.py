"""Explicit closed reference application; not added to production or M0."""
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from ..settings import V2RuntimeSettings
from .v2.errors import ApiError, handle_api_error, handle_http_error, handle_validation_error, request_id, error_response
from .v2.router import reject_demo_credentials


def create_reference_app(*, directory_reader=None) -> FastAPI:
    runtime = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled", _env_file=None)
    child = FastAPI(title="Closed reference data", openapi_url=None, docs_url=None, redoc_url=None)
    child.state.runtime_settings = runtime
    from .reference_directory import install_directory
    directory_guard = install_directory(child, directory_reader)
    child.add_exception_handler(ApiError, handle_api_error)
    child.add_exception_handler(HTTPException, handle_http_error)
    child.add_exception_handler(RequestValidationError, handle_validation_error)
    from .reference_cutoffs import router
    child.include_router(router)
    from .reference_admissions import router as admissions_router
    child.include_router(admissions_router)
    from .reference_curricula import router as curricula_router
    child.include_router(curricula_router)
    from .reference_outcomes import router as outcomes_router
    child.include_router(outcomes_router)

    @child.middleware("http")
    async def context(request, call_next):
        identifier = request_id(request)
        try:
            directory_guard()
            reject_demo_credentials(request)
            response = await call_next(request)
        except ApiError as error:
            response = error_response(request, error.status_code, error.code, details=error.details, headers=error.headers)
        except Exception:
            response = error_response(request, 503, "SERVICE_UNAVAILABLE")
        response.headers["X-Request-ID"] = identifier
        response.headers["Cache-Control"] = "no-store"
        return response

    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    app.mount("/v2", child)
    return app
