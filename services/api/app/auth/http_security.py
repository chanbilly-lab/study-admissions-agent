"""Central Cookie write protection, including newly added identity-profile routes.

No database or JOSE imports on the closed profile. Trust comes from the fixed
registered callback, never the incoming Host or forwarding headers.
"""

import re
from urllib.parse import urlsplit

from pydantic import SecretStr
from starlette.concurrency import run_in_threadpool

from ..api.v2.errors import ApiError, error_response, request_id
from ..api.v2.router import reject_demo_credentials
from .config import AuthFlowError
from .router import LOGIN_COOKIE, SESSION_COOKIE, _clear, _cookie
from ..audit.context import observe_actor


UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def trusted_origin(redirect_uri: str) -> str:
    """Serialize the already validated server callback's origin."""
    try:
        parsed = urlsplit(redirect_uri)
        host = parsed.hostname
        if not host or parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
            raise ValueError
        port = parsed.port
        host = f"[{host}]" if ":" in host else host
        suffix = f":{port}" if port is not None and port != {"http": 80, "https": 443}[parsed.scheme] else ""
        return f"{parsed.scheme}://{host}{suffix}"
    except (TypeError, ValueError):
        raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None


def csrf_header(request) -> SecretStr:
    values = request.headers.getlist("x-csrf-token")
    if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{43}", values[0]):
        raise AuthFlowError(403, "FORBIDDEN")
    return SecretStr(values[0])


async def identity_security(request, call_next):
    identifier = request_id(request)
    path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
    unsafe = request.method in UNSAFE_METHODS
    try:
        reject_demo_credentials(request)
        if unsafe:
            service = getattr(request.app.state, "identity_service", None)
            if service is None:
                raise AuthFlowError(503, "SERVICE_UNAVAILABLE")
            cookie = _cookie(request, SESSION_COOKIE)
            if cookie is None:
                raise AuthFlowError()
            # Check the current session before accepting a write proof. No
            # anonymous exemption, and no captured actor reused for execution.
            actor = await run_in_threadpool(service.get_session, cookie)
            observe_actor(actor)
            origins = request.headers.getlist("origin")
            if len(origins) != 1 or origins[0] != trusted_origin(service.settings.redirect_uri):
                raise AuthFlowError(403, "FORBIDDEN")
            await run_in_threadpool(service.verify_csrf, cookie, csrf_header(request))
        response = await call_next(request)
    except (AuthFlowError, ApiError) as error:
        response = error_response(request, error.status_code, error.code)
    except Exception:
        # Unexpected guard/dependency failures remain safe and fail closed.
        response = error_response(request, 503, "SERVICE_UNAVAILABLE")
    private = getattr(request.state, "private_access", False) is True
    if unsafe or path.startswith("/auth/") or private:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
    if response.status_code == 401 and (unsafe or private or path in {"/auth/session", "/auth/csrf", "/auth/logout"}):
        _clear(response, SESSION_COOKIE)
        _clear(response, LOGIN_COOKIE)
    response.headers["X-Request-ID"] = identifier
    return response
