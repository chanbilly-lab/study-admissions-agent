"""Explicit loopback-only reference factory. No startup DDL, seed, worker, or model."""

from contextlib import asynccontextmanager
import ipaddress
import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine
from starlette.exceptions import HTTPException

from ..settings import V2RuntimeSettings
from ..statistics.reference_cutoffs.service import local_database_url, require_reader
from .v2.errors import (ApiError, error_response, handle_api_error, handle_http_error,
                        handle_validation_error, request_id)
from .v2.router import reject_demo_credentials


def _loopback_authority(value: str, *, origin: bool = False) -> bool:
    try:
        if type(value) is not str or not 1 <= len(value) <= 128 or any(ord(c) <= 32 for c in value):
            return False
        parsed = urlsplit(value if origin else "http://" + value)
        if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            return False
        return parsed.port is None or 1 <= parsed.port <= 65535
    except ValueError:
        return False


def create_local_reference_app(*, directory_reader=None) -> FastAPI:
    # Deliberately require a separate DSN; M0 DATABASE_URL and .env are never read.
    url = local_database_url(os.environ.get("REFERENCE_CUTOFFS_READ_DATABASE_URL"))
    runtime = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
                                legacy_demo_mode=False, database_url=None, _env_file=None)
    child = FastAPI(title="Local reviewed Zhejiang reference", openapi_url=None, docs_url=None, redoc_url=None)
    child.state.runtime_settings = runtime
    from .reference_directory import install_directory
    directory_guard = install_directory(child, directory_reader)
    child.add_exception_handler(ApiError, handle_api_error)
    child.add_exception_handler(HTTPException, handle_http_error)
    child.add_exception_handler(RequestValidationError, handle_validation_error)
    from .local_reference_cutoffs import router
    child.include_router(router)
    from .reference_admissions import router as admissions_router
    child.include_router(admissions_router)
    from .reference_curricula import router as curricula_router
    child.include_router(curricula_router)
    from .reference_outcomes import router as outcomes_router
    child.include_router(outcomes_router)

    @child.middleware("http")
    async def local_context(request, call_next):
        identifier = request_id(request)
        try:
            directory_guard()
            peer = request.client.host if request.client is not None else ""
            if not ipaddress.ip_address(peer).is_loopback:
                raise ApiError(403, "FORBIDDEN")
            hosts = request.headers.getlist("host")
            origins = request.headers.getlist("origin")
            if (len(hosts) != 1 or not _loopback_authority(hosts[0]) or len(origins) > 1
                    or origins and not _loopback_authority(origins[0], origin=True)
                    or any(request.headers.getlist(name) for name in
                           ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto"))):
                raise ApiError(403, "FORBIDDEN")
            reject_demo_credentials(request)
            response = await call_next(request)
        except ApiError as error:
            response = error_response(request, error.status_code, error.code, details=error.details, headers=error.headers)
        except Exception:
            response = error_response(request, 503, "SERVICE_UNAVAILABLE")
        response.headers["X-Request-ID"] = identifier
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @asynccontextmanager
    async def lifespan(app):
        engine = create_engine(url, hide_parameters=True, echo=False,
                               connect_args={"connect_timeout": 5}, pool_pre_ping=True)
        try:
            with engine.connect() as connection, connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                require_reader(connection)
            child.state.reference_engine = engine
            yield
        except Exception:
            raise ValueError("Local SELECT-only reference service could not start") from None
        finally:
            engine.dispose()

    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.mount("/v2", child)
    return app
