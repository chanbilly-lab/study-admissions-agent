"""Safe v2 error translation; original exception values never enter JSON."""

import re
from collections.abc import Mapping
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from .schemas import ErrorBody, ErrorCode, ErrorDetail, ErrorEnvelope


STATUS_CODES: dict[int, ErrorCode] = {
    401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED", 409: "CONFLICT", 422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS", 503: "SERVICE_UNAVAILABLE", 500: "INTERNAL_ERROR",
}
MESSAGES: dict[ErrorCode, str] = {
    "UNAUTHORIZED": "需要有效身份验证",
    "FORBIDDEN": "无权执行此操作",
    "NOT_FOUND": "资源不存在或不可访问",
    "METHOD_NOT_ALLOWED": "此资源不支持该请求方法",
    "CONFLICT": "请求与当前资源状态冲突",
    "VALIDATION_ERROR": "请求参数不符合契约",
    "INVALID_CURSOR": "本阶段未发行有效分页游标",
    "TOO_MANY_REQUESTS": "请求频率超过限制",
    "SERVICE_UNAVAILABLE": "服务暂时不可用",
    "INTERNAL_ERROR": "服务内部错误",
}
SAFE_HEADERS = {"www-authenticate", "allow", "retry-after"}


def request_id(request: Request) -> str:
    """Reuse server state from the mounted parent, never a client header."""
    identifier = getattr(request.state, "request_id", None)
    if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
        identifier = uuid4().hex
        request.state.request_id = identifier
    return identifier


class ApiError(Exception):
    def __init__(self, status_code: int, code: ErrorCode, *,
                 details: list[ErrorDetail] | None = None,
                 headers: Mapping[str, str] | None = None):
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.details = details or []
        self.headers = headers


def error_response(request: Request, status_code: int, code: ErrorCode, *,
                   details: list[ErrorDetail] | None = None,
                   headers: Mapping[str, str] | None = None) -> JSONResponse:
    identifier = request_id(request)
    payload = ErrorEnvelope(error=ErrorBody(code=code, message=MESSAGES[code],
                                          request_id=identifier, details=details or []))
    response_headers = {
        name: value for name, value in (headers or {}).items()
        if name.lower() in SAFE_HEADERS and isinstance(value, str)
        and len(value) <= 512 and "\r" not in value and "\n" not in value
    }
    response_headers["X-Request-ID"] = identifier
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"),
                        headers=response_headers)


async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
    return error_response(request, error.status_code, error.code,
                          details=error.details, headers=error.headers)


async def handle_http_error(request: Request, error: HTTPException) -> JSONResponse:
    # Arbitrary HTTP detail is neither a public error code nor a safe message.
    status_code = error.status_code if error.status_code in STATUS_CODES else 500
    return error_response(request, status_code, STATUS_CODES[status_code], headers=error.headers)


def validation_detail(error: dict) -> ErrorDetail:
    kind = error.get("type", "")
    if kind == "extra_forbidden":
        code, message = "EXTRA_FIELD", "不接受额外字段"
    elif kind == "duplicate_parameter":
        code, message = "DUPLICATE_PARAMETER", "标量参数不能重复"
    elif kind == "missing":
        code, message = "MISSING_FIELD", "缺少必要字段"
    elif kind in {"greater_than", "greater_than_equal", "less_than", "less_than_equal"}:
        code, message = "OUT_OF_RANGE", "数值超出允许范围"
    elif kind in {"string_too_short", "string_too_long", "too_short", "too_long"}:
        code, message = "INVALID_LENGTH", "长度不符合要求"
    elif kind.endswith(("_parsing", "_type")):
        code, message = "INVALID_TYPE", "字段类型不正确"
    else:
        code, message = "INVALID_VALUE", "字段值不符合要求"

    location = error.get("loc", ())
    # Extra field names are also client input; do not echo them into an error.
    if kind == "extra_forbidden":
        location = location[:1]
    parts = [str(part) for part in location
             if (isinstance(part, int) and not isinstance(part, bool) and 0 <= part <= 10000)
             or (isinstance(part, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", part))]
    return ErrorDetail(field_path=".".join(parts) or "request", code=code, message=message)


async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    return error_response(request, 422, "VALIDATION_ERROR",
                          details=[validation_detail(item) for item in error.errors()])
