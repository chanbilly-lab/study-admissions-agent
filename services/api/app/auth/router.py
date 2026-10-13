"""BFF HTTP contract; importing this router does not load persistence/JOSE."""

from datetime import datetime
import re
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from starlette.responses import RedirectResponse, Response

from ..api.v2.errors import ApiError, error_response
from ..api.v2.router import foundation_meta, no_config_query, ERROR_RESPONSES, REQUEST_ID_HEADER
from ..api.v2.schemas import Envelope, StrictModel


LOGIN_COOKIE = "__Host-admissions-login"
SESSION_COOKIE = "__Host-admissions-session"
COOKIE_OPTIONS = {"secure": True, "httponly": True, "samesite": "lax", "path": "/"}


class AuthSessionData(StrictModel):
    authenticated: Literal[True]
    user_id: UUID
    expires_at: datetime
    is_synthetic: bool = Field(strict=True)
    private_business_available: Literal[False]


class AuthCsrfData(StrictModel):
    csrf_token: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")
    expires_at: datetime


class AuthLogoutData(StrictModel):
    logged_out: Literal[True]


class CallbackQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    code: str | None = Field(default=None, min_length=1, max_length=4096)
    state: str = Field(min_length=32, max_length=512, pattern=r"^[A-Za-z0-9_-]+$")
    error: str | None = Field(default=None, min_length=1, max_length=128)
    iss: str | None = Field(default=None, min_length=1, max_length=2048)


def callback_query(request: Request) -> CallbackQuery:
    names = {name for name, _ in request.query_params.multi_items()}
    if any(len(request.query_params.getlist(name)) != 1 for name in names):
        raise RequestValidationError([{"type": "duplicate_parameter", "loc": ("query", "parameters")}])
    try:
        query = CallbackQuery.model_validate(dict(request.query_params))
    except ValidationError:
        raise RequestValidationError([{"type": "invalid_parameter", "loc": ("query", "parameters")}]) from None
    if (query.code is None) == (query.error is None):
        raise RequestValidationError([{"type": "invalid_parameter", "loc": ("query", "parameters")}])
    return query


def _service(request: Request):
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return service


def _cookie(request: Request, name: str) -> SecretStr | None:
    # Reject ambiguous duplicate Cookie fields rather than selecting a browser value.
    values = [part.partition("=")[2].strip()
              for header in request.headers.getlist("cookie") for part in header.split(";")
              if part.partition("=")[0].strip() == name]
    if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{32,512}", values[0]):
        return None
    return SecretStr(values[0])


def _clear(response: Response, name: str) -> None:
    response.delete_cookie(name, **COOKIE_OPTIONS)


def _flow_failure(request: Request, error, *, clear_login: bool = False,
                  clear_session: bool = False) -> Response:
    response = error_response(request, error.status_code, error.code)
    if clear_login:
        _clear(response, LOGIN_COOKIE)
    if clear_session:
        _clear(response, SESSION_COOKIE)
    return response


REDIRECT_HEADERS = {
    **REQUEST_ID_HEADER,
    "Location": {"description": "Server-fixed destination", "schema": {"type": "string"}},
    "Set-Cookie": {"description": "Opaque Secure HttpOnly cookie", "schema": {"type": "string"}},
}
router = APIRouter(prefix="/auth", responses=ERROR_RESPONSES)


@router.get("/login", operation_id="startV2Login", response_class=RedirectResponse,
            status_code=302, dependencies=[Depends(no_config_query)],
            responses={302: {"description": "Fixed IdP authorization redirect", "headers": REDIRECT_HEADERS}})
def login(request: Request) -> Response:
    service = _service(request)
    from .service import AuthFlowError
    try:
        started = service.start_login()
    except AuthFlowError as error:
        return _flow_failure(request, error)
    response = RedirectResponse(started.authorization_url.get_secret_value(), status_code=302)
    response.set_cookie(LOGIN_COOKIE, started.browser_binding.get_secret_value(),
                        max_age=service.settings.login_ttl_seconds, **COOKIE_OPTIONS)
    return response


CALLBACK_PARAMETERS = [
    {"name": name, "in": "query", "required": name == "state", "schema": schema}
    for name, schema in CallbackQuery.model_json_schema()["properties"].items()
]


@router.get("/callback", operation_id="completeV2Login", response_class=RedirectResponse,
            status_code=303, openapi_extra={"parameters": CALLBACK_PARAMETERS},
            responses={303: {"description": "Login complete; fixed application root", "headers": REDIRECT_HEADERS}})
def callback(request: Request, query: CallbackQuery = Depends(callback_query)) -> Response:
    service = _service(request)
    from .service import AuthFlowError
    binding = _cookie(request, LOGIN_COOKIE)
    if binding is None or (query.iss is not None and query.iss != service.settings.provider.issuer):
        raise ApiError(401, "UNAUTHORIZED")
    try:
        if query.error is not None:
            service.cancel_login(state=SecretStr(query.state), browser_binding=binding)
            raise AuthFlowError(401, "UNAUTHORIZED")
        established = service.complete_login(
            code=SecretStr(query.code), state=SecretStr(query.state), browser_binding=binding,
            previous_session=_cookie(request, SESSION_COOKIE),
        )
    except AuthFlowError as error:
        return _flow_failure(request, error, clear_login=True)
    response = RedirectResponse("/", status_code=303)
    _clear(response, LOGIN_COOKIE)
    response.set_cookie(SESSION_COOKIE, established.session_cookie.get_secret_value(),
                        max_age=service.settings.session_ttl_seconds,
                        expires=established.expires_at, **COOKIE_OPTIONS)
    return response


@router.get("/session", operation_id="getV2Session", response_model=Envelope[AuthSessionData],
            dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
def session(request: Request) -> Envelope[AuthSessionData] | Response:
    service = _service(request)
    from .service import AuthFlowError
    cookie = _cookie(request, SESSION_COOKIE)
    if cookie is None:
        raise ApiError(401, "UNAUTHORIZED")
    try:
        current = service.get_session(cookie)
    except AuthFlowError as error:
        return _flow_failure(request, error, clear_session=error.status_code == 401)
    return Envelope(data=AuthSessionData(
        authenticated=True, user_id=current.user_id, expires_at=current.expires_at,
        is_synthetic=current.is_synthetic, private_business_available=False,
    ), meta=foundation_meta(request))


@router.get("/csrf", operation_id="getV2Csrf", response_model=Envelope[AuthCsrfData],
            dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
def csrf(request: Request) -> Envelope[AuthCsrfData] | Response:
    service = _service(request)
    from .config import AuthFlowError
    cookie = _cookie(request, SESSION_COOKIE)
    if cookie is None:
        raise ApiError(401, "UNAUTHORIZED")
    try:
        proof = service.get_csrf_token(cookie)
    except AuthFlowError as error:
        return _flow_failure(request, error, clear_session=error.status_code == 401)
    return Envelope(data=AuthCsrfData(csrf_token=proof.token.get_secret_value(),
                                    expires_at=proof.expires_at), meta=foundation_meta(request))


@router.post("/logout", operation_id="logoutV2Session", response_model=Envelope[AuthLogoutData],
             dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
async def logout(request: Request) -> Envelope[AuthLogoutData] | Response:
    service = _service(request)
    from .config import AuthFlowError
    from .http_security import csrf_header
    from starlette.concurrency import run_in_threadpool
    # Reject a body on the first nonempty chunk instead of buffering arbitrary
    # authenticated input for an endpoint whose contract has no request body.
    async for chunk in request.stream():
        if chunk:
            raise RequestValidationError([{"type": "invalid_parameter", "loc": ("body",)}])
    cookie = _cookie(request, SESSION_COOKIE)
    if cookie is None:
        raise ApiError(401, "UNAUTHORIZED")
    try:
        # Revalidate and revoke atomically; middleware's earlier check alone
        # cannot authorize a later mutation after expiry or revocation.
        await run_in_threadpool(service.logout, cookie, csrf_header(request))
    except AuthFlowError as error:
        return _flow_failure(request, error, clear_login=error.status_code == 401,
                             clear_session=error.status_code == 401)
    from fastapi.encoders import jsonable_encoder
    from starlette.responses import JSONResponse
    payload = Envelope(data=AuthLogoutData(logged_out=True), meta=foundation_meta(request))
    response = JSONResponse(jsonable_encoder(payload))
    _clear(response, SESSION_COOKIE)
    _clear(response, LOGIN_COOKIE)
    return response
