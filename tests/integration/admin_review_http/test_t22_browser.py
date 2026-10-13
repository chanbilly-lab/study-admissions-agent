"""Actual Edge -> loopback -> ASGI -> isolated synthetic PostgreSQL pipeline.

Only server-issued synthetic cookies and empty catalog references reach the
driver. Every import row, evidence, fact, decision and release ID is discovered
through the real HTTP application rather than being supplied by a fixture.
"""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import subprocess
from threading import Thread
from urllib.parse import unquote, urlsplit

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[3]
WEB_BUILD = ROOT / ".cache" / "t22-auth-frontend-validation"
SCRIPT = ROOT / "scripts" / "admin_t22_browser_smoke.mjs"
pytestmark = pytest.mark.postgres


class _LoopbackBridge(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        return  # Never log cookies, queries, paths or original source contents.

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
        if not 0 <= length <= 2 * 1024 * 1024:
            self._reply(413)
            return
        body = self.rfile.read(length)
        if self.path.startswith(("/api/", "/public/v2/")):
            # Anonymous /public/v2 is a separate mount; it is never rewritten to
            # the private /v2 foundation or substituted by an administrator.
            path = self.path[4:] if self.path.startswith("/api/") else self.path
            headers = [(key, value) for key, value in self.headers.raw_items()
                       if key.lower() not in {"connection", "content-length", "transfer-encoding"}]
            response = self.server.client.request(self.command, path, headers=headers,
                content=body, follow_redirects=False)
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

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _handle


@contextmanager
def _serve(build_app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LoopbackBridge)
    server.daemon_threads = True
    origin = "http://127.0.0.1:" + str(server.server_port)
    try:
        with TestClient(build_app(origin), base_url=origin, follow_redirects=False) as client:
            server.client = client
            thread = Thread(target=server.serve_forever, name="t22-loopback-browser", daemon=True)
            thread.start()
            try:
                yield origin
            finally:
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive(), "T22 loopback test server did not stop"
    finally:
        server.server_close()


def _browser_runtime():
    dependencies = Path(os.environ.get("USERPROFILE", "")) / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies"
    node = dependencies / "node" / "bin" / "node.exe"
    assert node.is_file(), "Required T22 browser check not executed: bundled Node unavailable"
    keep = {"PATH", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA",
            "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "SYSTEMDRIVE", "PROGRAMFILES",
            "PROGRAMFILES(X86)", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in keep}
    if "T22_PLAYWRIGHT_MODULE" in os.environ:
        environment["T22_PLAYWRIGHT_MODULE"] = os.environ["T22_PLAYWRIGHT_MODULE"]
    return node, environment


def test_t22_actual_browser_prepare_review_release(administrator_factory, storage_factory,
        imports_factory, evidence_factory, facts_factory, reviews_store, releases_store,
        catalog_tree, candidate_factory, pg_engine, clock):
    import httpx
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.admin.imports.models import ImportBatch, ImportCandidateRow
    from services.api.app.api.admin_review import create_admin_review_app
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.service import AuthService
    from services.api.app.evidence.models import Document, DocumentVersion, EvidenceSnippet
    from services.api.app.facts.models import FactCandidate
    from services.api.app.public_catalog.reader import CatalogReader
    from services.api.app.public_catalog.schemas import PublicCatalogPolicy
    from services.api.app.releases.models import CatalogRelease, CatalogReleaseState, ChangeEvent, OutboxEvent
    from services.api.app.releases.schemas import ReleasePolicy
    from services.api.app.releases.service import ReleaseService
    from services.api.app.reviews.models import ReviewDecision
    from services.api.app.reviews.schemas import ReviewPolicy
    from services.api.app.reviews.service import ReviewService
    from services.api.app.settings import V2RuntimeSettings

    assert (WEB_BUILD / "index.html").is_file(), "Required T22 auth frontend build is not prepared"
    node, environment = _browser_runtime()
    preparer = administrator_factory(assurance_age_limit=600)
    reviewer = administrator_factory(assurance_age_limit=600)
    assert preparer.actor.user_id != reviewer.actor.user_id

    def assemble(origin):
        callback = origin + "/api/v2/auth/callback"
        provider = preparer.service.settings.provider.model_copy(update={"callback_allowlist": (callback,)})
        settings = preparer.service.settings.model_copy(update={"provider": provider, "redirect_uri": callback})
        def no_idp_io(_request):
            raise AssertionError("T22 browser session fixtures must not contact an IdP")
        auth = AuthService(settings, preparer.service.runtime_settings, preparer.service.store,
            KeycloakOidcAdapter(settings, preparer.service.runtime_settings,
                transport=httpx.MockTransport(no_idp_io)), clock=clock)
        storage = storage_factory(identity=auth)
        imports = imports_factory(storage)
        evidence = evidence_factory(storage)
        facts = facts_factory(storage, imports=imports, evidence=evidence)
        reviews = ReviewService(facts, reviews_store, ReviewPolicy(enabled=True))
        releases = ReleaseService(reviews, imports.idempotency_service, releases_store,
            ReleasePolicy(enabled=True, allow_test_releases=True))
        public_settings = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled",
            database_url=None, legacy_demo_mode=None, _env_file=None)
        reader = CatalogReader(releases, public_settings,
            PublicCatalogPolicy(enabled=True, allow_test_fixture_read=True))
        return create_admin_review_app(auth.runtime_settings, identity_service=auth,
            source_service=storage.source_service, storage_service=storage, import_service=imports,
            evidence_service=evidence, fact_service=facts, review_service=reviews,
            release_service=releases, reader=reader)

    with Session(pg_engine) as session:
        revision = session.get(CatalogDataset, catalog_tree.dataset.id).revision
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 0
        assert session.scalar(select(func.count()).select_from(FactCandidate)) == 0
    # Two different values for the same declared semantics form a real conflict.
    # A present synthetic footnote exercises escaped original evidence as well.
    footnote = "DEMO_<img src=https://source-sentinel.invalid/x onerror=window.__t22Xss=1>"
    rows = [candidate_factory(value_text=value, unit="DEMO_points", footnote_state="present",
        footnote_text=footnote) for value in ("600.00", "601.00")]
    with _serve(assemble) as origin:
        fixture = dict(origin=origin, preparer_cookie=preparer.actor.cookie.get_secret_value(),
            reviewer_cookie=reviewer.actor.cookie.get_secret_value(), dataset_id=str(catalog_tree.dataset.id),
            dataset_revision=revision, rows=rows, now=clock().isoformat())
        completed = subprocess.run([str(node), str(SCRIPT)], cwd=ROOT, env=environment,
            input=json.dumps(fixture, ensure_ascii=False), text=True, encoding="utf-8",
            capture_output=True, timeout=600, check=False)
        for secret in (fixture["preparer_cookie"], fixture["reviewer_cookie"]):
            assert secret not in completed.stdout + completed.stderr
        try:
            report = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            pytest.fail("T22 browser driver did not return a valid safe report", pytrace=False)
        assert completed.returncode == 0, report
        assert report["status"] == "passed", report
        assert len(report["checks"]) >= 10, report
        assert report["page_errors"] == [] and report["blocked_requests"] == [], report
        print("T22 actual browser: " + str(len(report["checks"])) + " checks; " + report["browser"]
              + "; report " + report["cache_directory"])

    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 1
        assert session.scalar(select(func.count()).select_from(ImportCandidateRow)) == 2
        assert session.scalar(select(func.count()).select_from(Document)) == 1
        assert session.scalar(select(func.count()).select_from(DocumentVersion)) == 1
        assert session.scalar(select(func.count()).select_from(EvidenceSnippet)) >= 1
        assert session.scalar(select(func.count()).select_from(FactCandidate)) >= 2
        decisions = session.scalars(select(ReviewDecision)).all()
        assert decisions and all(row.reviewer_user_id == reviewer.actor.user_id for row in decisions)
        releases = session.scalars(select(CatalogRelease)).all()
        assert len(releases) == 2 and all(row.kind == "test_fixture" and row.is_synthetic for row in releases)
        assert {row.status for row in session.scalars(select(CatalogReleaseState)).all()} == {"replaced", "withdrawn"}
        events = session.scalars(select(ChangeEvent)).all()
        assert len(events) == 4 and session.scalar(select(func.count()).select_from(OutboxEvent)) == 4
