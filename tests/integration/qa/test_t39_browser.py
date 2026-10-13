"""Actual Edge -> finite public QA HTTP -> isolated synthetic PostgreSQL."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import threading
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from services.api.app.api.identity import create_identity_app
from services.api.app.api.public_catalog import create_public_catalog_app
from services.api.app.api.qa import create_qa_app
from services.api.app.model_gateway.budget import BudgetLedger
from services.api.app.model_gateway.gateway import ModelGateway
from services.api.app.model_gateway.schemas import BudgetPolicy, GatewayPolicy
from services.api.app.public_catalog.reader import CatalogReader
from services.api.app.public_catalog.schemas import PublicCatalogPolicy
from services.api.app.qa.retrieval import ScopedRetriever
from services.api.app.qa.schemas import QAPolicy
from services.api.app.qa.service import QAService
from services.api.app.settings import V2RuntimeSettings

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / ".cache" / "t39-auth-frontend-validation"
SCRIPT = ROOT / "scripts" / "qa_t39_browser_smoke.mjs"
pytestmark = pytest.mark.postgres


class _Delivery:
    def __init__(self):
        self.lock = threading.Lock()
        self.armed = False
        self.blocked, self.release, self.completed = (threading.Event() for _ in range(3))
        self.status = None

    def arm(self):
        with self.lock:
            assert not self.armed and not self.blocked.is_set()
            self.armed = True

    def take(self, path, response):
        with self.lock:
            if not self.armed or path != "/qa/v2/qa/answers":
                return False
            assert response.status_code == 200, "Delay must hold a completed actual successful QA answer"
            self.armed, self.status = False, response.status_code
            self.blocked.set()
            return True


class _Bridge(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def _send(self, status, payload=b"", headers=()):
        try:
            self.send_response(status)
            for name, value in headers:
                if name.lower() not in {"content-length", "connection", "transfer-encoding"}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        self.close_connection = True

    def _handle(self):
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send(400)
            return
        if not 0 <= length <= 16384:
            self._send(413)
            return
        body = self.rfile.read(length) if length else b""
        if path == "/__t39/control":
            if not secrets.compare_digest(self.headers.get("X-T39-Control", ""), self.server.control):
                self._send(403)
                return
            if self.command == "POST":
                raw = json.loads(body or b"{}")
                if raw == {"action": "arm"}:
                    self.server.delay.arm()
                elif raw == {"action": "release"}:
                    self.server.delay.release.set()
                else:
                    self._send(422)
                    return
            elif self.command != "GET":
                self._send(405)
                return
            self._send(200, json.dumps({"blocked": self.server.delay.blocked.is_set(),
                "completed": self.server.delay.completed.is_set(), "status": self.server.delay.status}).encode(),
                (("Content-Type", "application/json"), ("Cache-Control", "no-store")))
            return
        if path.startswith(("/api/", "/public/v2/", "/qa/v2/")):
            target = self.path[4:] if path.startswith("/api/") else self.path
            headers = [(key, value) for key, value in self.headers.raw_items()
                if key.lower() not in {"content-length", "connection", "transfer-encoding", "x-t39-control"}]
            response = self.server.client.request(self.command, target, headers=headers,
                content=body, follow_redirects=False)
            delayed = self.command == "POST" and self.server.delay.take(path, response)
            if delayed and not self.server.delay.release.wait(45):
                self._send(504)
                return
            self._send(response.status_code, response.content, response.headers.multi_items())
            if delayed:
                self.server.delay.completed.set()
            return
        if self.command not in {"GET", "HEAD"}:
            self._send(405)
            return
        relative = unquote(path).lstrip("/")
        requested = (BUILD / relative).resolve()
        if not requested.is_relative_to(BUILD.resolve()):
            self._send(404)
            return
        if not requested.is_file() and not Path(relative).suffix:
            requested = BUILD / "index.html"
        if not requested.is_file():
            self._send(404)
            return
        self._send(200, requested.read_bytes(), (("Content-Type", mimetypes.guess_type(requested)[0]
            or "application/octet-stream"), ("Cache-Control", "no-store")))

    do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = do_PATCH = _handle


@contextmanager
def _serve(case):
    runtime = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="mock",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    reader = CatalogReader(case.releases, runtime, PublicCatalogPolicy(enabled=True, allow_test_fixture_read=True))
    retriever = ScopedRetriever(reader, QAPolicy(enabled=True, allow_test_fixture_read=True))
    gateway = ModelGateway(policy=GatewayPolicy(app_environment="test", data_mode="demo", model_mode="mock"),
        budget=BudgetLedger(BudgetPolicy(max_output_tokens=4096)))
    service = QAService(runtime, retriever=retriever, gateway=gateway)
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    app.mount("/public", create_public_catalog_app(runtime, reader=reader))
    app.mount("/qa", create_qa_app(runtime, reader=reader, qa_service=service))
    app.mount("/", create_identity_app(V2RuntimeSettings(app_environment="test", data_mode="verified",
        model_mode="disabled", database_url=None, legacy_demo_mode=None, _env_file=None)))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Bridge)
    server.daemon_threads = True
    origin = "http://127.0.0.1:" + str(server.server_port)
    delay = _Delivery()
    server.control = secrets.token_hex(24)
    try:
        with TestClient(app, base_url=origin, follow_redirects=False) as client:
            server.client, server.delay = client, delay
            thread = threading.Thread(target=server.serve_forever, name="t39-loopback", daemon=True)
            thread.start()
            try:
                yield origin, server.control, delay
            finally:
                delay.release.set()
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive()
    finally:
        server.server_close()


def test_t39_actual_edge_public_qa_and_late_success(qa_case_factory):
    dependencies = Path(os.environ.get("USERPROFILE", "")) / ".cache/codex-runtimes/codex-primary-runtime/dependencies"
    node = dependencies / "node/bin/node.exe"
    assert node.is_file() and (BUILD / "index.html").is_file(), "Required actual Edge/build not prepared"
    keep = {"PATH", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA", "SYSTEMROOT",
        "WINDIR", "TEMP", "TMP", "COMSPEC", "SYSTEMDRIVE", "PROGRAMFILES", "PROGRAMFILES(X86)",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in keep}
    case = qa_case_factory()
    with _serve(case) as (origin, control, delay):
        fixture = {"origin": origin, "control": control, "year": 2026,
            "offering_id": str(case.request.offering_id), "version": 1, "release_id": str(case.release.release_id)}
        completed = subprocess.run([str(node), str(SCRIPT)], input=json.dumps(fixture), cwd=ROOT,
            env=environment, text=True, encoding="utf-8", capture_output=True, timeout=150)
        assert control not in completed.stdout + completed.stderr, "Browser report leaked control proof"
        report = json.loads(completed.stdout)
        assert completed.returncode == 0 and report["status"] == "passed", report
        assert len(report["checks"]) >= 8 and report["page_errors"] == report["blocked_requests"] == []
        assert sorted(report["api_config_requests"]) == ["/api/v2/auth/session",
            "/api/v2/privacy/notices/current", "/api/v2/sharing/policy"]
        assert delay.status == 200 and delay.completed.is_set()
        directory = Path(report["cache_directory"]).resolve()
        assert directory.is_relative_to((ROOT / ".cache/t39-ui").resolve())
        (ROOT / ".cache/t39-browser-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
