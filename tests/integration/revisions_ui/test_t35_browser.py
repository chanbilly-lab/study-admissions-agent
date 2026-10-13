"""Actual Edge -> loopback -> T35 ASGI -> isolated synthetic PostgreSQL."""

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import json
import mimetypes
import os
import secrets
from pathlib import Path
import subprocess
import threading
from urllib.parse import unquote, urlsplit
from uuid import UUID

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.integration.catalog_ui.test_t29_browser import _Bridge as _CatalogBridge

ROOT = Path(__file__).resolve().parents[3]
WEB_BUILD = ROOT / ".cache/t35-auth-frontend-validation"
SCRIPT = ROOT / "scripts/plans_t35_browser_smoke.mjs"
pytestmark = pytest.mark.postgres


class _Delivery:
    """Hold delivery only after the real authorized history GET has succeeded."""
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
            if not self.armed or not path.startswith("/v2/plan-revisions/history/"):
                return False
            assert response.status_code == 200, "The delayed history must be a real successful response"
            self.armed = False
            self.status = response.status_code
            self.blocked.set()
            return True


class _Bridge(_CatalogBridge):
    def _handle(self):
        original = self.path
        path = urlsplit(original).path
        if not path.startswith(("/api/", "/public/v2/")) and path != "/__t35/control":
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
        if path == "/__t35/control":
            if not secrets.compare_digest(self.headers.get("X-T35-Control", ""), self.server.control_secret):
                self._send(403, b"{}")
                return
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
            server.control_secret = workspace.browser_fixture["control_secret"]
            thread = threading.Thread(target=server.serve_forever, name="t35-loopback", daemon=True)
            thread.start()
            try:
                yield origin, workspace, delay
            finally:
                delay.release.set()
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive(), "T35 transport did not stop"
    finally:
        server.server_close()


def _browser_runtime():
    dependencies = Path(os.environ.get("USERPROFILE", "")) / ".cache/codex-runtimes/codex-primary-runtime/dependencies"
    node = dependencies / "node/bin/node.exe"
    assert node.is_file() and (WEB_BUILD / "index.html").is_file(), "T35 browser/build runtime not prepared"
    keep = {"PATH", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA",
        "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "SYSTEMDRIVE", "PROGRAMFILES",
        "PROGRAMFILES(X86)", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    environment = {name: value for name, value in os.environ.items() if name.upper() in keep}
    if os.getenv("T35_PLAYWRIGHT_MODULE"):
        environment["T35_PLAYWRIGHT_MODULE"] = os.environ["T35_PLAYWRIGHT_MODULE"]
    return node, environment


def test_actual_browser_reject_accept_history_and_late_success_cleanup(workspace_factory, browser_origin, pg_engine, clock):
    from services.api.app.auth.models import AuthOwnedResource
    from services.api.app.plan_execution.models import ExecutionHead, ExecutionConfirmation, TaskCompletion
    from services.api.app.plan_revisions.models import RevisionProposal, RevisionDecision, PlanReplacement

    node, environment = _browser_runtime()
    with _serve(workspace_factory, browser_origin) as (origin, workspace, delay):
        fixture = {**workspace.browser_fixture, "origin": origin, "server_now": clock().isoformat()}
        with Session(pg_engine) as session:
            old_id = UUID(fixture["old_plan_id"])
            old_head = session.get(ExecutionHead, old_id)
            original_state = old_head.state_version
            original_completions = tuple(session.scalars(select(TaskCompletion).where(TaskCompletion.plan_id == old_id)).all())
            old_snapshot = tuple((row.id, row.confirmation_id, row.task_key, row.state_version, row.completed_at) for row in original_completions)
            assert old_snapshot and session.get(AuthOwnedResource, old_id).version == 1
        completed = subprocess.run([str(node), str(SCRIPT)], input=json.dumps(fixture), cwd=ROOT,
            env=environment, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=360)
        delay.release.set()
        if any(secret in completed.stdout + completed.stderr for secret in (fixture["owner_cookie"], fixture["other_cookie"], fixture["control_secret"])):
            pytest.fail("T35 browser returned a private credential; output withheld", pytrace=False)
        try:
            report = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            pytest.fail("T35 browser did not return a bounded safe report", pytrace=False)
        cache = Path(report["cache_directory"]).resolve()
        assert cache.is_relative_to((ROOT / ".cache/t35-ui").resolve())
        (cache / "stdout.log").write_text(completed.stdout, encoding="utf-8")
        (cache / "stderr.log").write_text(completed.stderr, encoding="utf-8")
        assert completed.returncode == 0 and report["status"] == "passed", report
        assert report["page_errors"] == [] and report["blocked_requests"] == [] and len(report["checks"]) >= 12, report
        assert delay.blocked.is_set() and delay.completed.wait(5) and delay.status == 200
        with Session(pg_engine) as session:
            old_head = session.get(ExecutionHead, old_id)
            now_rows = tuple(session.scalars(select(TaskCompletion).where(TaskCompletion.plan_id == old_id)).all())
            assert old_head.state_version == original_state and old_head.state == "confirmed"
            assert {(row.id, row.confirmation_id, row.task_key, row.state_version, row.completed_at) for row in now_rows} == set(old_snapshot)
            for new_id in (fixture["new_plan_id"], fixture["reject_new_plan_id"]):
                head = session.get(ExecutionHead, UUID(new_id))
                assert head.state == "draft" and head.confirmation_id is None
                assert session.scalar(select(ExecutionConfirmation).where(ExecutionConfirmation.plan_id == head.plan_id)) is None
                assert session.scalar(select(TaskCompletion).where(TaskCompletion.plan_id == head.plan_id)) is None
            decisions = tuple(session.scalars(select(RevisionDecision)).all())
            assert {value.action for value in decisions} == {"accept", "reject"} and len(decisions) == 2
            links = tuple(session.scalars(select(PlanReplacement)).all())
            assert len(links) == 1 and links[0].old_plan_id == old_id and links[0].new_plan_id == UUID(fixture["new_plan_id"])
            assert len(tuple(session.scalars(select(RevisionProposal)).all())) == 2
        print("T35 Edge checks:", len(report["checks"]), "browser:", report["browser"], "cache:", report["cache_directory"])
