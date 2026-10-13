"""Actual Edge -> loopback HTTP -> profile ASGI -> isolated PostgreSQL acceptance."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import threading
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUILD = ROOT / ".cache" / "t24-auth-frontend-validation"
pytestmark = pytest.mark.postgres


class _Delay:
    """Only delays delivery of an already-executed real GET, not its API result."""
    def __init__(self):
        self.lock = threading.Lock()
        self.armed = False
        self.blocked = threading.Event()
        self.release = threading.Event()
        self.completed = threading.Event()
        self.status = None

    def arm(self):
        with self.lock:
            assert not self.armed and not self.blocked.is_set()
            self.armed = True
            self.release.clear()
            self.completed.clear()

    def take(self, path, response):
        with self.lock:
            if not self.armed or not path.startswith("/v2/profiles/") or path == "/v2/profiles/context":
                return False
            self.armed = False
            self.status = response.status_code
            self.blocked.set()
            return True


class _Bridge(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def _send(self, status, payload, headers=()):
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
            # The browser deliberately aborts a delayed response on logout.
            pass
        self.close_connection = True

    def _handle(self):
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send(400, b"")
            return
        if not 0 <= length <= 2 * 1048576:
            self._send(413, b"")
            return
        body = self.rfile.read(length) if length else None
        if path == "/__t24/control":
            delay = self.server.delay
            if self.command == "POST":
                value = json.loads(body or b"{}")
                if value == {"action": "arm"}:
                    delay.arm()
                elif value == {"action": "release"}:
                    delay.release.set()
                else:
                    self._send(422, b"{}")
                    return
            elif self.command != "GET":
                self._send(405, b"{}")
                return
            result = {"blocked": delay.blocked.is_set(), "completed": delay.completed.is_set(),
                      "response_status": delay.status}
            self._send(200, json.dumps(result).encode(), [("Content-Type", "application/json"),
                        ("Cache-Control", "no-store")])
            return
        if path.startswith("/api/"):
            target = self.path[4:]
            headers = [(name, value) for name, value in self.headers.raw_items()
                       if name.lower() not in {"content-length", "connection", "transfer-encoding"}]
            response = self.server.client.request(self.command, target, content=body,
                headers=headers, follow_redirects=False)
            delayed = self.command == "GET" and self.server.delay.take(urlsplit(target).path, response)
            if delayed:
                if not self.server.delay.release.wait(45):
                    self._send(504, b"{}")
                    return
            self._send(response.status_code, response.content, response.headers.multi_items())
            if delayed:
                self.server.delay.completed.set()
            return
        if self.command not in {"GET", "HEAD"}:
            self._send(405, b"")
            return
        requested = (self.server.build / path.lstrip("/")).resolve()
        if not requested.is_relative_to(self.server.build):
            self._send(404, b"")
            return
        if not requested.is_file() and not Path(path).suffix:
            requested = self.server.build / "index.html"
        if not requested.is_file():
            self._send(404, b"")
            return
        mime = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
        self._send(200, requested.read_bytes(), [("Content-Type", mime), ("Cache-Control", "no-store")])

    do_GET = do_HEAD = do_POST = do_DELETE = do_PUT = do_PATCH = _handle


@contextmanager
def _serve(build_app, build):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Bridge)
    server.daemon_threads = True
    server.delay, server.build = _Delay(), build
    origin = "http://127.0.0.1:" + str(server.server_address[1])
    thread = None
    try:
        app, services = build_app(origin)
        with TestClient(app, base_url=origin, follow_redirects=False) as client:
            server.client = client
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            yield origin, services, server.delay
    finally:
        server.delay.release.set()
        if thread is not None:
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()
        server.server_close()


def _runtime_and_build():
    node = Path(os.environ.get("USERPROFILE", "")) / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
    assert node.is_file(), "Required T24 real-browser check not executed: bundled Node missing"
    build = Path(os.environ.get("T24_WEB_BUILD", str(DEFAULT_BUILD))).resolve()
    assert build.is_relative_to((ROOT / ".cache").resolve()), "T24 build must be an ignored workspace cache"
    assert (build / "index.html").is_file(), "Required T24 auth frontend build not executed"
    allowed = {"PATH", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA",
               "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "SYSTEMDRIVE",
               "PROGRAMFILES", "PROGRAMFILES(X86)", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    child = {name: value for name, value in os.environ.items() if name.upper() in allowed}
    if os.getenv("T24_PLAYWRIGHT_MODULE"):
        child["T24_PLAYWRIGHT_MODULE"] = os.environ["T24_PLAYWRIGHT_MODULE"]
    return node, build, child


def test_t24_real_student_confirmation_and_versions(pg_engine, clock, runtime, session_settings,
        auth_store, actor_factory, privacy_settings, profiles_store):
    from services.api.app.api.profiles import create_profiles_app
    from services.api.app.auth.config import SessionAuthSettings
    from services.api.app.auth.models import AuthSession
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.schemas import AuthProviderSettings
    from services.api.app.auth.service import AuthService
    from services.api.app.idempotency.schemas import IdempotencyPolicy
    from services.api.app.idempotency.service import IdempotencyService
    from services.api.app.idempotency.store import IdempotencyStore
    from services.api.app.privacy.models import PrivacyAdmissionRecord
    from services.api.app.privacy.service import PrivacyService
    from services.api.app.profiles.models import ProfileRoot, ProfileVersion
    from services.api.app.profiles.schemas import ProfilePolicy
    from services.api.app.profiles.service import ProfileService

    node, build, environment = _runtime_and_build()
    owner = actor_factory()  # Registered session only. The UI must establish its admission.
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(PrivacyAdmissionRecord)) == 0
        assert session.scalar(select(func.count()).select_from(ProfileRoot)) == 0
        assert session.scalar(select(func.count()).select_from(ProfileVersion)) == 0
    counts = {"idp_requests": 0}

    def build_app(origin):
        callback = origin + "/api/v2/auth/callback"
        provider = AuthProviderSettings.model_validate({**session_settings.provider.model_dump(),
            "callback_allowlist": (callback,)})
        settings = SessionAuthSettings.model_validate({**session_settings.model_dump(),
            "provider": provider, "redirect_uri": callback})
        def no_idp_io(_request):
            counts["idp_requests"] += 1
            raise AssertionError("T24's registered synthetic session never contacts an identity provider")
        auth = AuthService(settings, runtime, auth_store,
            KeycloakOidcAdapter(settings, runtime, transport=httpx.MockTransport(no_idp_io)), clock=clock)
        privacy = PrivacyService(auth, privacy_settings)
        idem = IdempotencyService(auth, privacy, IdempotencyStore(pg_engine),
            IdempotencyPolicy(enabled=True, ttl_seconds=86400))
        profiles = ProfileService(auth, privacy, idem, profiles_store, ProfilePolicy(enabled=True))
        return create_profiles_app(runtime, identity_service=auth, profile_service=profiles), profiles

    with _serve(build_app, build) as (origin, _services, delay):
        fixture = {"origin": origin, "cookie": owner.cookie.get_secret_value(), "user_id": str(owner.user_id)}
        result = subprocess.run([str(node), str(ROOT / "scripts/profiles_t24_browser_smoke.mjs")],
            input=json.dumps(fixture), cwd=ROOT, env=environment, text=True, encoding="utf-8",
            errors="replace", capture_output=True, timeout=240)
        # A failed harness must still release its pending real HTTP response.
        delay.release.set()
        assert fixture["cookie"] not in result.stdout + result.stderr
        lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
        assert lines, "The T24 browser did not produce its bounded report"
        report = json.loads(lines[-1])
        assert result.returncode == 0, json.dumps(report, ensure_ascii=False) + result.stderr[-2000:]
        assert report["status"] == "passed"
        assert len(report["checks"]) >= 10
        assert report["page_errors"] == [] and report["blocked_requests"] == []
        assert report["ids"]["profile_id"]
        assert delay.blocked.is_set() and delay.completed.wait(5)
        assert delay.status == 200, "The delayed response must come from an actually successful profile read"
    assert counts == {"idp_requests": 0}
    with Session(pg_engine) as session:
        roots = session.scalars(select(ProfileRoot)).all()
        assert len(roots) == 2
        assert {str(row.id) for row in roots} == {
            report["ids"]["profile_id"], report["ids"]["post_withdraw_profile_id"]}
        versions = session.scalars(select(ProfileVersion).where(
            ProfileVersion.profile_id == UUID(report["ids"]["profile_id"]))
            .order_by(ProfileVersion.version)).all()
        assert len(versions) == len(report["ids"]["version_ids"]) == 6
        assert [str(row.id) for row in versions] == report["ids"]["version_ids"]
        assert all(row.owner_user_id == owner.user_id and row.is_synthetic for row in versions)
        first, cleared = versions[:2]
        assert first.payload["assessments"]["gaokao_total"]["achieved"]["value"] == "625.25"
        assert first.payload["assessments"]["gaokao_total"]["predicted"]["value"] == "700.000001"
        assert first.payload["assessments"]["math"]["achieved"]["value"] == "0"
        assert first.payload["preferences"] == {"preferred_fields": ["DEMO engineering"],
            "preferred_countries": ["GB"], "budget": {"amount": "25000", "currency": "GBP"}}
        assert cleared.payload["assessments"]["gaokao_total"]["achieved"]["value"] is None
        assert cleared.payload["weekly_hours"] == "0"
        assert any(row.payload["course_system"]["status"] == "unknown" and row.payload["assessments"] == {} for row in versions)
        assert any(row.payload["course_system"]["value"] == "HKDSE" and row.payload["assessments"] == {} for row in versions)
        later = session.get(ProfileVersion, UUID(report["ids"]["post_withdraw_version_id"]))
        assert later.profile_id == UUID(report["ids"]["post_withdraw_profile_id"])
        assert later.version == 1 and later.consent_id != first.consent_id
        assert later.owner_user_id == owner.user_id and later.is_synthetic
        assert session.scalar(select(func.count()).select_from(ProfileVersion)) == 7
        assert all(row.owner_user_id == owner.user_id and row.is_synthetic for row in roots)
        assert later.payload["assessments"] == {} and later.payload["weekly_hours"] is None
        records = session.scalars(select(PrivacyAdmissionRecord).order_by(PrivacyAdmissionRecord.revision)).all()
        assert records[0].event_type == "adult_declared"
        assert records[1].event_type == "consent_confirmed"
        assert any(row.event_type == "consent_withdrawn" for row in records)
        assert records[-1].consent_status == "active"
        assert session.get(AuthSession, owner.session_id).revoked_at is not None
    assert UUID(report["ids"]["profile_id"])
    print("T24 Edge checks:", len(report["checks"]), "browser:", report["browser"],
          "cache:", report["cache_directory"])
