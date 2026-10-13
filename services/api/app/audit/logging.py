"""Configured log outputs serialize only fixed fields, never original messages."""

from datetime import datetime, timedelta, timezone
import json
import logging
from itertools import islice
from pathlib import Path
import re
from typing import Literal

from pydantic import Field

from ..auth.schemas import AuthModel
from .context import active_request_id, current_request_id
from .retention import LOG_MAX_DAYS
from .schemas import Reason

OperationId = Literal["runtime.message", "request.completed", "request.failed", "audit.write.failed",
    "getV2Config", "listV2Offerings", "startV2Login", "completeV2Login", "getV2Session", "getV2Csrf",
    "logoutV2Session", "getV2PrivacyNotice", "getV2Admission", "declareV2Age", "confirmV2CoreConsent",
    "withdrawV2CoreConsent", "getV2SharingPolicy", "listV2AccessGrants", "createV2AccessGrant",
    "acceptV2AccessGrant", "revokeV2AccessGrant"]


class SafeLogEvent(AuthModel):
    operation_id: OperationId
    request_id: str = Field(strict=True, pattern=r"^[0-9a-f]{32}$")
    status: int | None = Field(default=None, strict=True, ge=100, le=599)
    reason_code: Reason | None = None
    duration_ms: int | None = Field(default=None, strict=True, ge=0, le=86400000)


def safe_event(record):
    # LogRecord extras are caller-controlled, including names that look private.
    # Only the server ContextVar can correlate a request. Outside a request each
    # formatting pass receives a fresh server ID; no record attribute is trusted.
    identifier = active_request_id() or current_request_id()
    try:
        event = SafeLogEvent.model_validate(getattr(record, "safe_event", None))
        return SafeLogEvent.model_validate({**event.model_dump(), "request_id": identifier})
    except Exception:
        return SafeLogEvent(operation_id="runtime.message", request_id=identifier)


class SafeLogFilter(logging.Filter):
    def filter(self, record):
        # Sanitize before parsing any optional extra, so a handler failure cannot
        # fall back to rendering the original message, arguments or traceback.
        record.msg, record.args = "runtime.message", ()
        record.exc_info = record.exc_text = record.stack_info = None
        record.safe_event = safe_event(record)
        return True


class SafeLogFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(safe_event(record).model_dump(mode="json"), ensure_ascii=True, separators=(",", ":"))


CONFIGURED_LOGGERS = ("admissions", "admissions.audit", "uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "httpcore",
                      "sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool", "fastapi", "starlette")


def configure_logging(stream=None):
    """Configure this process's known application/server/library outputs.

    This deliberately does not claim control over upstream proxies, other
    processes or subsequently attached custom handlers by trusted local code.
    """
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SafeLogFormatter())
    handler.addFilter(SafeLogFilter())
    for name in CONFIGURED_LOGGERS:
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
        # Alembic's earlier fileConfig can disable already-created loggers.
        # Explicit setup must restore the names it actually configures.
        logger.disabled = False
    logging.getLogger("admissions").setLevel(logging.INFO)
    logging.getLogger("admissions.audit").setLevel(logging.INFO)
    return handler


def emit(operation_id, *, status=None, reason_code=None, duration_ms=None):
    event = SafeLogEvent(operation_id=operation_id, request_id=current_request_id(), status=status,
                         reason_code=reason_code, duration_ms=duration_ms)
    logging.getLogger("admissions.audit").info("runtime.message", extra={"safe_event": event})


def purge_log_files(directory, *, now, limit=100, scan_limit=1000):
    """Explicit maintenance of an app-owned directory of fixed JSONL files only.

    No startup deletion, recursion, user-file traversal or collector control.
    A caller must supply a dedicated managed directory, never arbitrary data.
    """
    if (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
        or type(limit) is not int or not 1 <= limit <= 1000
        or type(scan_limit) is not int or not 1 <= scan_limit <= 10000):
        raise ValueError("bounded log retention is required")
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("a dedicated log directory is required")
    cutoff = now.astimezone(timezone.utc) - timedelta(days=LOG_MAX_DAYS)
    deleted = 0
    for path in islice(directory.iterdir(), scan_limit):
        match = re.fullmatch(r"admissions-(\d{4}-\d{2}-\d{2})\.jsonl", path.name)
        if path.is_symlink() or not path.is_file() or match is None:
            continue
        try:
            day = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if day > cutoff:
            continue
        if path.resolve().parent != directory:
            raise ValueError("log file escaped managed directory")
        path.unlink()
        deleted += 1
        if deleted == limit:
            break
    return deleted
