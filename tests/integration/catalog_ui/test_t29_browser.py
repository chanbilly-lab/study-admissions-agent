"""Real T29 browser and synthetic PostgreSQL acceptance; no API route mocks."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import threading
from urllib.parse import unquote, urlsplit

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[3]
WEB_BUILD = ROOT / ".cache" / "t29-auth-frontend-validation"
SCRIPT = ROOT / "scripts" / "catalog_t29_browser_smoke.mjs"
pytestmark = pytest.mark.postgres


class _Delivery:
    """Delay only an actually completed private GET's delivery to the browser."""
    def __init__(self):
        self.lock = threading.Lock()
        self.armed = False
        self.blocked = threading.Event()
        self.release = threading.Event()
        self.completed = threading.Event()
        self.status = None

    def arm(self):
        with self.lock:
            assert not self.armed and (not self.blocked.is_set() or self.completed.is_set())
            self.armed = True
            self.blocked.clear()
            self.release.clear()
            self.completed.clear()
            self.status = None

    def take(self, path, response):
        with self.lock:
            if not self.armed or not path.startswith("/v2/eligibility/evaluations/"):
                return False
            assert response.status_code == 200, "Late-response proof must be an actually successful GET"
            self.armed = False
            self.status = response.status_code
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
            pass  # Intentional AbortController cancellation of a real late GET.
        self.close_connection = True

    def _handle(self):
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send(400)
            return
        if not 0 <= length <= 2*1048576:
            self._send(413)
            return
        body = self.rfile.read(length) if length else b""
        if path == "/__t29/control":
            delay = self.server.delay
            if self.command == "POST":
                raw = json.loads(body or b"{}")
                if raw == {"action": "arm"}:
                    delay.arm()
                elif raw == {"action": "release"}:
                    delay.release.set()
                else:
                    self._send(422, b"{}")
                    return
            elif self.command != "GET":
                self._send(405)
                return
            self._send(200, json.dumps({"blocked": delay.blocked.is_set(),
                "completed": delay.completed.is_set(), "response_status": delay.status}).encode(),
                (("Content-Type", "application/json"), ("Cache-Control", "no-store")))
            return
        if path.startswith(("/api/", "/public/v2/")):
            target = self.path[4:] if path.startswith("/api/") else self.path
            headers = [(name, value) for name, value in self.headers.raw_items()
                if name.lower() not in {"content-length", "connection", "transfer-encoding"}]
            response = self.server.client.request(self.command, target, headers=headers,
                content=body, follow_redirects=False)
            delayed = self.command == "GET" and self.server.delay.take(urlsplit(target).path, response)
            if delayed and not self.server.delay.release.wait(45):
                self._send(504, b"{}")
                return
            self._send(response.status_code, response.content, response.headers.multi_items())
            if delayed:
                self.server.delay.completed.set()
            return
        if self.command not in {"GET", "HEAD"}:
            self._send(405)
            return
        relative = unquote(path).lstrip("/")
        requested = (WEB_BUILD / relative).resolve()
        if not requested.is_relative_to(WEB_BUILD.resolve()):
            self._send(404)
            return
        if not requested.is_file() and not Path(relative).suffix:
            requested = WEB_BUILD / "index.html"
        if not requested.is_file():
            self._send(404)
            return
        self._send(200, requested.read_bytes(), (("Content-Type", mimetypes.guess_type(requested)[0]
            or "application/octet-stream"), ("Cache-Control", "no-store")))

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = _handle


@contextmanager
def _serve(workspace_factory, browser_origin):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Bridge)
    server.daemon_threads = True
    origin = "http://127.0.0.1:" + str(server.server_port)
    browser_origin["value"] = origin
    delay = _Delivery()
    try:
        workspace = workspace_factory()
        with TestClient(workspace.app, base_url=origin, follow_redirects=False) as client:
            server.client, server.delay = client, delay
            thread = threading.Thread(target=server.serve_forever, name="t29-loopback-browser", daemon=True)
            thread.start()
            try:
                yield origin, workspace, delay
            finally:
                delay.release.set()
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive(), "T29 loopback bridge did not stop"
    finally:
        server.server_close()


def _browser_runtime():
    dependencies = Path(os.environ.get("USERPROFILE", "")) / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies"
    node = dependencies / "node" / "bin" / "node.exe"
    assert node.is_file(), "Required T29 browser check not executed: bundled Node unavailable"
    assert (WEB_BUILD / "index.html").is_file(), "Required T29 auth frontend build not prepared"
    keep = {"PATH", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA", "SYSTEMROOT",
        "WINDIR", "TEMP", "TMP", "COMSPEC", "SYSTEMDRIVE", "PROGRAMFILES", "PROGRAMFILES(X86)",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    environment = {name: value for name, value in os.environ.items() if name.upper() in keep}
    if os.getenv("T29_PLAYWRIGHT_MODULE"):
        environment["T29_PLAYWRIGHT_MODULE"] = os.environ["T29_PLAYWRIGHT_MODULE"]
    return node, environment


def test_t29_public_pipeline_requires_actual_publication_and_serves_conditional(workspace_factory):
    """An independent setup proof, runnable before the frontend build exists."""
    workspace = workspace_factory()
    with TestClient(workspace.app, base_url="https://app.test.invalid") as client:
        page = client.get("/public/v2/offerings", params={"entry_year": 2026, "limit": 1})
        assert page.status_code == 200
        data = page.json()["data"]
        assert len(data["items"]) == 1 and data["page"]["has_more"]
        second = client.get("/public/v2/offerings", params={"entry_year": 2026, "limit": 1,
            "cursor": data["page"]["next_cursor"]})
        assert second.status_code == 200 and len(second.json()["data"]["items"]) == 1
        assert {data["items"][0]["id"], second.json()["data"]["items"][0]["id"]} == {
            str(workspace.case.bundle.offering_id), str(workspace.extra.id)}
        evidence = client.get("/public/v2/evidence/"+str(workspace.public_snippet.id),
            params={"release_id": str(workspace.release.release_id)})
        assert evidence.status_code == 200 and workspace.xss_sentinel in evidence.json()["data"]["quote"]
        for response in (page, second, evidence):
            assert response.headers["cache-control"] == "no-store"
            assert not response.request.headers.get("cookie")
        cookie = "__Host-admissions-session=" + workspace.case.owner.cookie.get_secret_value()
        headers = {"Cookie": cookie}
        csrf = client.get("/v2/auth/csrf", headers=headers)
        assert csrf.status_code == 200
        request = workspace.case.request.model_copy(update={"release_id": workspace.release.release_id})
        result = client.post("/v2/eligibility/evaluations", json=request.model_dump(mode="json"),
            headers={**headers, "Origin": "https://app.test.invalid", "X-CSRF-Token": csrf.json()["data"]["csrf_token"]})
        assert result.status_code == 200
        assert result.json()["data"]["eligibility"]["status"] == "conditional"
        assert result.json()["data"]["release_id"] == str(workspace.release.release_id)
        assert result.json()["data"]["profile_version_id"] == str(workspace.case.profile.version_id)


def test_t29_actual_browser_catalog_evidence_and_private_isolation(workspace_factory, browser_origin, pg_engine):
    node, environment = _browser_runtime()
    with _serve(workspace_factory, browser_origin) as (origin, workspace, delay):
        fixture = {"origin": origin, "owner_cookie": workspace.case.owner.cookie.get_secret_value(),
            "other_cookie": workspace.receiver.cookie.get_secret_value(), "user_id": str(workspace.case.owner.user_id),
            "other_user_id": str(workspace.receiver.user_id), "year": 2026}
        completed = subprocess.run([str(node), str(SCRIPT)], input=json.dumps(fixture), cwd=ROOT,
            env=environment, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=360)
        delay.release.set()
        for secret in (fixture["owner_cookie"], fixture["other_cookie"]):
            assert secret not in completed.stdout + completed.stderr
        try:
            report = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            pytest.fail("T29 browser did not produce its bounded safe report", pytrace=False)
        assert completed.returncode == 0, report
        assert report["status"] == "passed", report
        assert report["page_errors"] == [] and report["blocked_requests"] == [], report
        assert len(report["checks"]) >= 12, report
        assert delay.blocked.is_set() and delay.completed.wait(5)
        assert delay.status == 200
        print("T29 Edge checks:", len(report["checks"]), "browser:", report["browser"],
            "cache:", report["cache_directory"])
