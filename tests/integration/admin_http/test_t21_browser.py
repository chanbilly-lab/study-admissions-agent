"""Real loopback browser -> ASGI -> synthetic PostgreSQL administration.

The bridge is test-only. It preserves the browser Origin and cookie headers,
never substitutes an authenticated Principal, and serves only a prepared build.
"""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
from threading import Thread
from urllib.parse import unquote, urlsplit

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[3]
WEB_BUILD = ROOT / ".cache" / "t21-auth-frontend-validation"
SCRIPT = ROOT / "scripts" / "admin_t21_browser_smoke.mjs"
pytestmark = pytest.mark.postgres


class _LoopbackBridge(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        # HTTP paths, headers, cookies and source contents are never logged.
        return

    def _reply(self, status, content=b"", headers=()):
        self.send_response(status)
        for key, value in headers:
            if key.lower() not in {"content-length", "connection", "transfer-encoding"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def _handle(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._reply(400)
            return
        if length < 0 or length > 2 * 1024 * 1024:
            self._reply(413)
            return
        content = self.rfile.read(length)
        if self.path == "/__test__/revoke-admin" and self.command == "POST":
            supplied = self.headers.get("X-T21-Fixture-Key", "")
            if not hmac.compare_digest(supplied, self.server.fixture_key):
                self._reply(403)
                return
            self.server.revoke_admin()
            self._reply(200, b'{"revoked":true}', (("Content-Type", "application/json"),))
            return
        if self.path.startswith("/api/"):
            # TestClient forwards the actual Cookie, Origin and duplicate header
            # sequence. It must not invent an Origin accepted by the service.
            headers = [(key, value) for key, value in self.headers.raw_items()
                       if key.lower() not in {"connection", "content-length", "transfer-encoding"}]
            response = self.server.client.request(self.command, self.path[4:],
                headers=headers, content=content, follow_redirects=False)
            self._reply(response.status_code, response.content, response.headers.multi_items())
            return
        if self.command not in {"GET", "HEAD"}:
            self._reply(404)
            return
        relative = unquote(urlsplit(self.path).path).lstrip("/")
        candidate = (WEB_BUILD / relative).resolve()
        if not candidate.is_relative_to(WEB_BUILD.resolve()):
            self._reply(404)
            return
        if not candidate.is_file() and not Path(relative).suffix:
            candidate = WEB_BUILD / "index.html"
        if not candidate.is_file():
            self._reply(404)
            return
        self._reply(200, candidate.read_bytes(), (("Content-Type", mimetypes.guess_type(candidate)[0]
            or "application/octet-stream"), ("Cache-Control", "no-store")))

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = _handle


@contextmanager
def _serve(build_app, revoke_admin):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LoopbackBridge)
    server.daemon_threads = True
    origin = "http://127.0.0.1:" + str(server.server_port)
    server.fixture_key = secrets.token_urlsafe(32)
    server.revoke_admin = revoke_admin
    try:
        with TestClient(build_app(origin), base_url=origin, follow_redirects=False) as client:
            server.client = client
            thread = Thread(target=server.serve_forever, name="t21-loopback-browser", daemon=True)
            thread.start()
            try:
                yield origin, server.fixture_key
            finally:
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive(), "T21 loopback test server did not stop"
    finally:
        server.server_close()


def _browser_runtime():
    runtime = Path(os.environ.get("USERPROFILE", "")) / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies"
    node = runtime / "node" / "bin" / "node.exe"
    assert node.is_file(), "T21 browser check not executed: bundled Node is unavailable"
    # The browser process needs no PostgreSQL URL, secret provider configuration
    # or commercial API credential. Only synthetic session fixtures use stdin.
    keep = {"PATH", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA",
            "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "SYSTEMDRIVE",
            "PROGRAMFILES", "PROGRAMFILES(X86)", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    env = {key: value for key, value in os.environ.items() if key.upper() in keep}
    if "T21_PLAYWRIGHT_MODULE" in os.environ:
        env["T21_PLAYWRIGHT_MODULE"] = os.environ["T21_PLAYWRIGHT_MODULE"]
    return node, env


def test_t21_real_browser_admin_and_student(administrator_factory, actor_factory,
        storage_factory, imports_factory, catalog_tree, candidate_factory, pg_engine, clock):
    """Use real PG services and cookie/CSRF middleware, without a second IdP."""
    import httpx
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from services.api.app.admin.imports.models import ImportBatch, ImportCandidateRow
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion
    from services.api.app.api.admin import create_admin_app
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.service import AuthService
    from services.api.app.storage.models import StorageObject

    assert (WEB_BUILD / "index.html").is_file(), "Required T21 auth frontend build is not prepared"
    node, environment = _browser_runtime()
    administrator = administrator_factory(assurance_age_limit=600)
    student = actor_factory(role="student")
    assembled = {}

    def assemble(origin):
        # Bind the real application's configured Origin to the dynamic test
        # server. Forwarded requests retain their original browser Origin.
        callback = origin + "/api/v2/auth/callback"
        provider = administrator.service.settings.provider.model_copy(update={"callback_allowlist": (callback,)})
        settings = administrator.service.settings.model_copy(update={"provider": provider, "redirect_uri": callback})
        def no_identity_network(_request):
            raise AssertionError("T21 session-fixture browser check must not contact an IdP")
        auth = AuthService(settings, administrator.service.runtime_settings, administrator.service.store,
            KeycloakOidcAdapter(settings, administrator.service.runtime_settings,
                transport=httpx.MockTransport(no_identity_network)), clock=clock)
        storage = storage_factory(identity=auth)
        imports = imports_factory(storage)
        assembled.update(auth=auth, storage=storage)
        return create_admin_app(auth.runtime_settings, identity_service=auth,
            source_service=storage.source_service, storage_service=storage, import_service=imports)

    def revoke():
        assert assembled["auth"].store.revoke_role(administrator.actor.user_id, "data_admin", now=clock())

    with Session(pg_engine) as session:
        revision = session.get(CatalogDataset, catalog_tree.dataset.id).revision
    rows = [candidate_factory(source_record_reference="DEMO_T21_SHARED_RECORD", field_key="total_threshold"),
            candidate_factory(source_record_reference="DEMO_T21_SHARED_RECORD", field_key="math_threshold",
                              value_text="100.00"),
            candidate_factory(source_record_reference="DEMO_T21_THIRD_RECORD", field_key="language_threshold",
                              value_text="80.00")]
    with _serve(assemble, revoke) as (origin, control_key):
        fixture = dict(origin=origin, control_key=control_key,
            admin_cookie=administrator.actor.cookie.get_secret_value(),
            student_cookie=student.cookie.get_secret_value(), dataset_id=str(catalog_tree.dataset.id),
            dataset_revision=revision, rows=rows)
        completed = subprocess.run([str(node), str(SCRIPT)], cwd=ROOT, env=environment,
            input=json.dumps(fixture, ensure_ascii=False), text=True, encoding="utf-8",
            capture_output=True, timeout=240, check=False)
        # The driver's only output is a bounded, sanitized report. Never include
        # fixture cookies or DSNs in a pytest diagnostic or a saved report.
        for secret in (fixture["admin_cookie"], fixture["student_cookie"], control_key):
            assert secret not in completed.stdout + completed.stderr
        try:
            report = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            pytest.fail("T21 browser driver did not return a valid safe report", pytrace=False)
        assert completed.returncode == 0, report
        assert report["status"] == "passed", report
        assert len(report["checks"]) >= 8, report
        assert report["page_errors"] == [] and report["blocked_requests"] == [], report
        print("T21 actual browser: " + str(len(report["checks"])) + " checks; " + report["browser"]
              + "; report " + report["cache_directory"])

    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(CatalogSource)) == 1
        assert session.scalar(select(func.count()).select_from(CatalogSourceVersion)) == 1
        batches = session.scalars(select(ImportBatch)).all()
        assert len(batches) == 2 and {row.status for row in batches} == {"staged", "rejected"}
        assert session.scalar(select(func.count()).select_from(ImportCandidateRow)) == 3
        files = session.scalars(select(StorageObject)).all()
        assert len(files) == 2
        assert {row.sha256 for row in files} == set(report["file_hashes"])
        source_version = session.scalars(select(CatalogSourceVersion)).one()
        assert source_version.responsible_user_id == administrator.actor.user_id
        assert all(row.owner_user_id is None and row.namespace == "source_quarantine"
            and row.dataset_id == source_version.dataset_id and row.source_id == source_version.source_id
            and row.source_version == source_version.version for row in files)
