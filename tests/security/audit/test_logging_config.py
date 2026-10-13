"""Run the committed logging configuration in isolated, offline processes."""

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config" / "logging" / "identity.json"
SENTINEL = "T10_CONFIG_SYNTHETIC_CREDENTIAL_SCORE_PROMPT"
FIELDS = {"operation_id", "request_id", "status", "reason_code", "duration_ms"}


def run_python(source, *arguments):
    return subprocess.run([sys.executable, "-B", "-c", source, *map(str, arguments)],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False)


@pytest.mark.parametrize("loader", ["dictConfig", "uvicorn"])
def test_actual_configuration_closes_existing_server_library_and_root_outputs(loader):
    completed = run_python(r'''
import json
import logging
import logging.config
import sys

sentinel = "T10_CONFIG_SYNTHETIC_CREDENTIAL_SCORE_PROMPT"
# These existing handlers must be replaced, including known logger children.
for name in ("", "admissions", "admissions.already_loaded", "sqlalchemy.engine.Engine"):
    logger = logging.getLogger(name)
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.DEBUG)
for name in ("admissions", "admissions.audit", "sqlalchemy.engine.Engine", "httpx"):
    logging.getLogger(name).disabled = True

if sys.argv[2] == "dictConfig":
    with open(sys.argv[1], encoding="utf-8") as source:
        logging.config.dictConfig(json.load(source))
else:
    from uvicorn import Config
    # Uses Uvicorn's real log-config loader, without loading the app/listening.
    Config("services.api.app.api.identity:create_identity_app", factory=True,
        log_config=sys.argv[1], access_log=True)

from services.api.app.audit.context import request_context
from services.api.app.audit.logging import CONFIGURED_LOGGERS, emit

names = ("", *CONFIGURED_LOGGERS, "sqlalchemy", "sqlalchemy.engine.Engine",
    "uvicorn.asgi", "admissions.already_loaded", "unconfigured.propagating.library")
try:
    raise RuntimeError("private exception " + sentinel)
except RuntimeError:
    with request_context("a" * 32):
        for name in names:
            logging.getLogger(name).error("/auth/callback?code=%s score=750 prompt=%s",
                sentinel, sentinel, exc_info=True, stack_info=True,
                extra={"headers": sentinel, "query": sentinel, "body": sentinel,
                    "safe_event": {"operation_id": "request.failed", "request_id": "b" * 32,
                        "status": 403, "reason_code": "FORBIDDEN", "duration_ms": 2}})
        emit("request.completed", status=200, duration_ms=3)

class Unprintable:
    def __str__(self):
        raise AssertionError("private message stringified " + sentinel)

for candidate in (sentinel, "b" * 32):
    logging.getLogger("httpx").error(Unprintable(), sentinel,
        extra={"_audit_server_request_id": candidate, "safe_event": sentinel})

forbidden = ("sqlalchemy", "services.api.app.main", "services.api.app.db",
    "services.api.app.storage", "services.api.app.auth.store", "services.api.app.auth.service",
    "services.api.app.providers")
print(json.dumps({"expected_lines": len(names) + 3,
    "forbidden_imports": [name for name in sys.modules
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)]}))
''', CONFIG, loader)
    assert completed.returncode == 0, completed.stderr
    assert SENTINEL not in completed.stdout + completed.stderr
    assert "Traceback" not in completed.stderr and "score=750" not in completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["forbidden_imports"] == []
    events = [json.loads(line) for line in completed.stderr.splitlines()]
    assert len(events) == summary["expected_lines"]
    assert all(set(event) == FIELDS for event in events)
    assert all(re.fullmatch(r"[0-9a-f]{32}", event["request_id"]) for event in events)
    assert all(event["request_id"] == "a" * 32 for event in events[:-2])
    assert all(event["operation_id"] == "request.failed" and event["status"] == 403
        and event["reason_code"] == "FORBIDDEN" for event in events[:-3])
    assert events[-3] == dict(operation_id="request.completed", request_id="a" * 32,
        status=200, reason_code=None, duration_ms=3)
    assert all(event["request_id"] not in {"a" * 32, "b" * 32}
        and event["operation_id"] == "runtime.message" for event in events[-2:])


def test_explicit_helper_reenables_known_loggers_disabled_by_previous_config():
    completed = run_python(r'''
import io
import json
import logging
import sys
from services.api.app.audit.context import request_context
from services.api.app.audit.logging import CONFIGURED_LOGGERS, configure_logging, emit
sentinel = "T10_CONFIG_SYNTHETIC_CREDENTIAL_SCORE_PROMPT"
for name in CONFIGURED_LOGGERS:
    logger = logging.getLogger(name)
    logger.disabled = True
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.INFO)
logging.getLogger("admissions.audit").setLevel(logging.ERROR)
output = io.StringIO()
configure_logging(output)
with request_context("a" * 32):
    for name in CONFIGURED_LOGGERS:
        logging.getLogger(name).error("private input %s", sentinel)
    emit("request.completed", status=200)
print(json.dumps({"expected_lines": len(CONFIGURED_LOGGERS) + 1,
    "events": [json.loads(line) for line in output.getvalue().splitlines()],
    "disabled": [name for name in CONFIGURED_LOGGERS if logging.getLogger(name).disabled]}))
''')
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == "" and SENTINEL not in completed.stdout
    summary = json.loads(completed.stdout)
    assert summary["disabled"] == []
    assert len(summary["events"]) == summary["expected_lines"]
    assert all(set(event) == FIELDS and event["request_id"] == "a" * 32 for event in summary["events"])
    assert summary["events"][-1]["operation_id"] == "request.completed"


def test_importing_logging_module_has_no_global_handler_or_database_side_effects():
    completed = run_python(r'''
import json
import logging
import sys
names = ("", "admissions", "uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "httpcore",
    "sqlalchemy", "sqlalchemy.engine", "sqlalchemy.pool", "fastapi", "starlette")
def snapshot():
    return [(name, tuple(id(handler) for handler in logging.getLogger(name).handlers),
        logging.getLogger(name).level, logging.getLogger(name).propagate,
        logging.getLogger(name).disabled) for name in names]
before = snapshot()
import services.api.app.audit.logging
forbidden = ("sqlalchemy", "services.api.app.main", "services.api.app.db",
    "services.api.app.storage", "services.api.app.auth.store", "services.api.app.auth.service",
    "services.api.app.providers")
print(json.dumps({"unchanged": before == snapshot(),
    "forbidden_imports": [name for name in sys.modules
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)]}))
''')
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == dict(unchanged=True, forbidden_imports=[])


def test_closed_and_schema_factories_preserve_process_logging_and_do_not_import_persistence():
    completed = run_python(r'''
import json
import logging
import os
import sys
# A deterministic closed process, independent of a developer's local settings.
for key in list(os.environ):
    if key.startswith(("V2_", "IDENTITY_")) or key == "DEMO_MODE":
        os.environ.pop(key)
os.environ.update(V2_APP_ENVIRONMENT="production", V2_DATA_MODE="verified", V2_MODEL_MODE="disabled")
names = ("", "admissions", "uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "httpcore",
    "sqlalchemy", "sqlalchemy.engine", "sqlalchemy.pool", "fastapi", "starlette")
def snapshot():
    return [(name, tuple(id(handler) for handler in logging.getLogger(name).handlers),
        logging.getLogger(name).level, logging.getLogger(name).propagate,
        logging.getLogger(name).disabled) for name in names]
before = snapshot()
from services.api.app.api.identity import create_identity_app, create_identity_v2_app
schema_app = create_identity_v2_app()
schema = schema_app.openapi()
closed_app = create_identity_app()
forbidden = ("sqlalchemy", "jose", "services.api.app.main", "services.api.app.db",
    "services.api.app.storage", "services.api.app.auth.store", "services.api.app.auth.service",
    "services.api.app.auth.oidc", "services.api.app.audit.models", "services.api.app.audit.service",
    "services.api.app.providers")
print(json.dumps({"unchanged": before == snapshot(),
    "schema_version": schema["info"]["version"], "closed_service": schema_app.state.identity_service is None,
    "only_v2_mount": [route.path for route in closed_app.routes] == ["/v2"],
    "forbidden_imports": [name for name in sys.modules
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)]}))
''')
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == dict(unchanged=True, schema_version="v2.t09",
        closed_service=True, only_v2_mount=True, forbidden_imports=[])
