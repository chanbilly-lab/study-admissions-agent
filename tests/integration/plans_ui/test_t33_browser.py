"""Actual Edge -> transparent loopback -> plans ASGI -> isolated PostgreSQL."""

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import threading
from urllib.parse import unquote, urlsplit
from uuid import UUID

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.integration.catalog_ui.test_t29_browser import _Bridge as _CatalogBridge

ROOT = Path(__file__).resolve().parents[3]
WEB_BUILD = ROOT / ".cache" / "t33-auth-frontend-validation"
SCRIPT = ROOT / "scripts" / "plans_t33_browser_smoke.mjs"
pytestmark = pytest.mark.postgres


class _Delivery:
    """Hold only delivery of an already successful real private plan GET."""
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
            if not self.armed or not path.startswith("/v2/plans/") or path == "/v2/plans/context":
                return False
            assert response.status_code == 200, "Late delivery must originate in a real successful GET"
            self.armed = False
            self.status = response.status_code
            self.blocked.set()
            return True


class _Bridge(_CatalogBridge):
    def _handle(self):
        # Reuse the frozen transport implementation without editing it. The
        # only rewritten URL is our test control path, never a business API.
        original = self.path
        path = urlsplit(original).path
        if not path.startswith(("/api/", "/public/v2/")) and path != "/__t33/control":
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
            return
        if urlsplit(original).path == "/__t33/control":
            self.path = "/__t29/control"
        try:
            super()._handle()
        finally:
            self.path = original

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
            thread = threading.Thread(target=server.serve_forever, name="t33-loopback", daemon=True)
            thread.start()
            try:
                yield origin, workspace, delay
            finally:
                delay.release.set()
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive(), "T33 bridge did not stop"
    finally:
        server.server_close()


def _browser_runtime():
    dependencies = Path(os.environ.get("USERPROFILE", "")) / ".cache/codex-runtimes/codex-primary-runtime/dependencies"
    node = dependencies / "node/bin/node.exe"
    assert node.is_file(), "Required T33 actual browser runtime unavailable"
    assert (WEB_BUILD / "index.html").is_file(), "Required T33 frontend build not prepared"
    keep = {"PATH", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA",
        "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "SYSTEMDRIVE", "PROGRAMFILES",
        "PROGRAMFILES(X86)", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    environment = {name: value for name, value in os.environ.items() if name.upper() in keep}
    if os.getenv("T33_PLAYWRIGHT_MODULE"):
        environment["T33_PLAYWRIGHT_MODULE"] = os.environ["T33_PLAYWRIGHT_MODULE"]
    return node, environment


def test_t33_actual_browser_plan_confirmation_and_progress(workspace_factory, browser_origin, pg_engine, clock):
    from services.api.app.auth.models import AuthOwnedResource
    from services.api.app.plan_execution.models import ExecutionHead, ExecutionProposal, ExecutionConfirmation, TaskCompletion
    from services.api.app.plans.models import PlanRoot, PlanVersion
    from services.api.app.assessments.models import EligibilityAssessment

    node, environment = _browser_runtime()
    with _serve(workspace_factory, browser_origin) as (origin, workspace, delay):
        with Session(pg_engine) as session:
            for model in (ExecutionHead, ExecutionProposal, ExecutionConfirmation, TaskCompletion, PlanRoot, EligibilityAssessment):
                assert session.scalar(select(func.count()).select_from(model)) == 0
        fixture = {"origin": origin, "owner_cookie": workspace.case.owner.cookie.get_secret_value(),
            "other_cookie": workspace.receiver.cookie.get_secret_value(), "user_id": str(workspace.case.owner.user_id),
            "other_user_id": str(workspace.receiver.user_id), "year": 2026, "server_now": clock().isoformat()}
        completed = subprocess.run([str(node), str(SCRIPT)], input=json.dumps(fixture), cwd=ROOT,
            env=environment, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=360)
        delay.release.set()
        for secret in (fixture["owner_cookie"], fixture["other_cookie"]):
            assert secret not in completed.stdout + completed.stderr
        try:
            report = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            pytest.fail("T33 browser did not return a bounded safe report", pytrace=False)
        cache = Path(report["cache_directory"]).resolve()
        assert cache.is_relative_to((ROOT / ".cache/t33-ui").resolve())
        (cache / "stdout.log").write_text(completed.stdout, encoding="utf-8")
        (cache / "stderr.log").write_text(completed.stderr, encoding="utf-8")
        assert completed.returncode == 0, report
        assert report["status"] == "passed", report
        assert report["page_errors"] == [] and report["blocked_requests"] == [], report
        assert len(report["checks"]) >= 12, report
        assert delay.blocked.is_set() and delay.completed.wait(5) and delay.status == 200
        plan_id = UUID(report["ids"]["plan_id"])
        with Session(pg_engine) as session:
            head = session.get(ExecutionHead, plan_id)
            assert head.owner_user_id == workspace.case.owner.user_id and head.is_synthetic
            assert head.state == "confirmed" and head.state_version == report["ids"]["state_version"]
            confirmations = session.scalars(select(ExecutionConfirmation).where(ExecutionConfirmation.plan_id == plan_id)).all()
            completions = session.scalars(select(TaskCompletion).where(TaskCompletion.plan_id == plan_id)).all()
            assert len(confirmations) == 1
            assert {row.task_key for row in completions} == set(report["ids"]["completed_keys"])
            assert all(row.source == "student_declared" for row in completions)
            assert len(completions) == len(set(row.task_key for row in completions))
            root = session.get(PlanRoot, plan_id)
            assert root.current_version == 1
            assert session.scalar(select(func.count()).select_from(PlanVersion).where(PlanVersion.plan_id == plan_id)) == 1
            assert session.get(AuthOwnedResource, plan_id).version == 1
        print("T33 Edge checks:", len(report["checks"]), "browser:", report["browser"], "cache:", report["cache_directory"])
