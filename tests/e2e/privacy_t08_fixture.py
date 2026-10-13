"""Loopback-only T08 privacy fixture, never a production application entry point.

The browser visits a local HTTPS authorization page. The application adapter
exchanges its one-time code through MockTransport and verifies a real RSA
signature. Keys, certificate and the synthetic SQLite database live only in a
fresh ignored cache directory. This does not simulate a deployed Keycloak.
"""

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import sys
import threading
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def deny_external_network() -> None:
    """All actual browser-fixture sockets are loopback; backchannel is in-memory."""
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
                return original(sock, address)
            raise RuntimeError("T08 browser fixture forbids external connections")

        setattr(socket.socket, name, guarded)
    original_dns = socket.getaddrinfo

    def guarded_dns(host, *args, **kwargs):
        if host in {None, "127.0.0.1", "::1"}:
            return original_dns(host, *args, **kwargs)
        raise RuntimeError("T08 browser fixture forbids external DNS")

    socket.getaddrinfo = guarded_dns


class FixtureClock:
    def __init__(self):
        self.offset = timedelta()
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            return datetime.now(timezone.utc) + self.offset

    def advance(self):
        with self.lock:
            self.offset += timedelta(seconds=3601)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--web-origin", default="http://127.0.0.1:5188")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--idp-port", type=int, default=9448)
    args = parser.parse_args()
    web = urlsplit(args.web_origin)
    if (web.scheme != "http" or web.hostname != "127.0.0.1" or web.path or web.query
        or web.fragment or web.username or web.port is None):
        parser.error("web origin must be an exact HTTP 127.0.0.1 origin")
    if not all(1024 <= port <= 65535 for port in (web.port, args.api_port, args.idp_port)):
        parser.error("fixture ports must be explicit unprivileged ports")
    cache = Path(args.cache_dir).resolve()
    allowed = (ROOT / ".cache" / "t08-ui").resolve()
    if not cache.is_relative_to(allowed) or cache == allowed:
        parser.error("fixture output must be a new directory within .cache/t08-ui")
    cache.mkdir(parents=True, exist_ok=False)
    control_key = os.environ.get("T08_FIXTURE_CONTROL_KEY", "")
    if len(control_key) < 43 or not control_key.isascii():
        parser.error("fresh synthetic fixture control key is required")
    deny_external_network()

    from cryptography import x509
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID
    from fastapi import FastAPI, HTTPException, Request
    import httpx
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session
    import uvicorn

    from services.api.app.api.identity import create_identity_v2_app
    from services.api.app.auth.config import SessionAuthSettings
    from services.api.app.auth.models import AuthIdentity, AuthUser
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.provider import pkce_s256
    from services.api.app.auth.schemas import AuthProviderSettings
    from services.api.app.auth.service import AuthService
    from services.api.app.auth.store import AuthStore, migrate_auth
    from services.api.app.privacy.config import POLICY_VERSION, PrivacySettings
    from services.api.app.privacy.models import PrivacyNoticeVersion
    from services.api.app.privacy.policy import hash_text
    from services.api.app.privacy.service import PrivacyService
    from services.api.app.settings import V2RuntimeSettings

    real_now = datetime.now(timezone.utc)
    tls_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tls_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "T08 SYNTHETIC LOOPBACK")])
    certificate = (x509.CertificateBuilder().subject_name(tls_name).issuer_name(tls_name)
        .public_key(tls_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(real_now - timedelta(minutes=5))
        .not_valid_after(real_now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]), critical=False)
        .sign(tls_key, hashes.SHA256()))
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for filename, value in {
        "tls-key.pem": tls_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
        "tls-cert.pem": certificate.public_bytes(serialization.Encoding.PEM),
        "signing-key.pem": signing_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
    }.items():
        with (cache / filename).open("xb") as output:
            output.write(value)
    numbers = signing_key.public_key().public_numbers()
    jwk = {"kty": "RSA", "kid": "T08_SYNTHETIC_RSA", "alg": "RS256", "use": "sig",
           "n": b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
           "e": b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big"))}
    issuer = f"https://127.0.0.1:{args.idp_port}/realms/t08"
    redirect_uri = args.web_origin + "/api/v2/auth/callback"
    client_id, client_secret = "T08_BROWSER_SYNTHETIC_CLIENT", secrets.token_urlsafe(32)
    subject = "T08_SYNTHETIC_BROWSER_ALICE"
    clock, lock = FixtureClock(), threading.Lock()
    authorizations, codes = {}, {}
    counts = {"code_exchanges": 0, "jwks_reads": 0}

    def jwt_for(record):
        timestamp = int(clock().timestamp())
        header = b64(json.dumps({"alg": "RS256", "kid": jwk["kid"]}, separators=(",", ":")).encode())
        claims = b64(json.dumps({"iss": issuer, "aud": client_id, "sub": record["subject"],
            "nonce": record["nonce"], "iat": timestamp, "exp": timestamp + 120}, separators=(",", ":")).encode())
        signing_input = (header + "." + claims).encode("ascii")
        signature = signing_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        return header + "." + claims + "." + b64(signature)

    def backchannel(request):
        if request.method == "GET" and str(request.url) == issuer + "/protocol/openid-connect/certs":
            with lock:
                counts["jwks_reads"] += 1
            return httpx.Response(200, json={"keys": [jwk]})
        if request.method != "POST" or str(request.url) != issuer + "/protocol/openid-connect/token":
            raise AssertionError("unregistered fixture backchannel endpoint")
        expected_basic = "Basic " + base64.b64encode((client_id + ":" + client_secret).encode()).decode()
        form = parse_qs(request.content.decode("ascii"), strict_parsing=True)
        if request.headers.get("Authorization") != expected_basic or any(len(v) != 1 for v in form.values()):
            return httpx.Response(400, json={"error": "invalid_grant"})
        with lock:
            record = codes.pop(form.get("code", [""])[0], None)
        if (record is None or form.get("grant_type") != ["authorization_code"]
            or form.get("redirect_uri") != [redirect_uri]
            or set(form) != {"grant_type", "code", "redirect_uri", "code_verifier"}):
            return httpx.Response(400, json={"error": "invalid_grant"})
        try:
            correct = hmac.compare_digest(pkce_s256(form["code_verifier"][0]), record["code_challenge"])
        except ValueError:
            correct = False
        if not correct:
            return httpx.Response(400, json={"error": "invalid_grant"})
        with lock:
            counts["code_exchanges"] += 1
        return httpx.Response(200, json={"id_token": jwt_for(record), "token_type": "Bearer"})

    class AuthorizationPage(BaseHTTPRequestHandler):
        def log_message(self, format, *arguments):
            pass  # Authorization URL/proofs must never be written to access logs.

        def send_page(self, status, body):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            # Chromium checks the form redirect destination as well as its POST.
            self.send_header("Content-Security-Policy", "default-src 'none'; form-action 'self' " + args.web_origin + "; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path != "/realms/t08/protocol/openid-connect/auth":
                self.send_page(404, "Fixture route unavailable")
                return
            query = parse_qs(parsed.query)
            required = {"client_id", "redirect_uri", "response_type", "scope", "state", "nonce", "code_challenge", "code_challenge_method"}
            if (set(query) != required or any(len(v) != 1 for v in query.values())
                or query["client_id"] != [client_id] or query["redirect_uri"] != [redirect_uri]
                or query["response_type"] != ["code"] or query["scope"] != ["openid"]
                or query["code_challenge_method"] != ["S256"]):
                self.send_page(400, "Fixture trust mismatch")
                return
            authorization_id = secrets.token_urlsafe(32)
            with lock:
                authorizations[authorization_id] = {k: v[0] for k, v in query.items()}
            self.send_page(200, f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>T08 合成离线授权</title>
<h1>DEMO · 本机合成身份供应商</h1><p>仅验证签名和登录流程，不是真实 Keycloak，也不注册真实账号。</p>
<form method="post" action="/authorize"><input type="hidden" name="authorization_id" value="{authorization_id}">
<button name="identity" value="registered">继续使用合成主体</button>
<button name="identity" value="unregistered">使用未登记合成主体</button></form></html>''')

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            if self.path != "/authorize" or not 0 < length <= 2048:
                self.send_page(400, "Fixture request rejected")
                return
            form = parse_qs(self.rfile.read(length).decode("ascii"))
            if set(form) != {"authorization_id", "identity"} or any(len(v) != 1 for v in form.values()):
                self.send_page(400, "Fixture request rejected")
                return
            with lock:
                record = authorizations.pop(form["authorization_id"][0], None)
            if record is None or form["identity"][0] not in {"registered", "unregistered"}:
                self.send_page(400, "Fixture request rejected")
                return
            record["subject"] = subject if form["identity"] == ["registered"] else "T08_SYNTHETIC_NOT_REGISTERED"
            code = secrets.token_urlsafe(32)
            with lock:
                codes[code] = record
            self.send_response(303)
            self.send_header("Location", redirect_uri + "?" + urlencode({"code": code, "state": record["state"], "iss": issuer}))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()

    tls_server = ThreadingHTTPServer(("127.0.0.1", args.idp_port), AuthorizationPage)
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_context.load_cert_chain(cache / "tls-cert.pem", cache / "tls-key.pem")
    tls_server.socket = tls_context.wrap_socket(tls_server.socket, server_side=True)
    threading.Thread(target=tls_server.serve_forever, daemon=True).start()

    engine = create_engine("sqlite+pysqlite:///" + (cache / "synthetic-auth.sqlite").as_posix(),
                           connect_args={"check_same_thread": False})
    migrate_auth(engine)  # Explicit fixture setup; application startup does not create tables.
    user_id = uuid4()
    notice_id = uuid4()
    notice_text = ("DEMO · T08 合成离线告知，仅用于隔离浏览器验收。本人声明不等于年龄已核验。"
                   "核心用途仅为本科咨询、确定性资格与准备计划；外部模型、营销、第三方共享关闭。"
                   "可撤回核心用途确认；真实资料处理与清理作业尚未开放。")
    with Session(engine) as session, session.begin():
        session.add(AuthUser(id=user_id, status="active", is_synthetic=True, created_at=clock()))
        session.flush()
        session.add(AuthIdentity(id=uuid4(), user_id=user_id, issuer=issuer, subject=subject, created_at=clock()))
        session.add(PrivacyNoticeVersion(id=notice_id, version="DEMO_T08_browser_v1", policy_version=POLICY_VERSION,
            text=notice_text, text_sha256=hash_text(notice_text), controller_reference="DEMO_T08_TEST_CONTROLLER",
            review_status="test_reviewed", reviewed_at=clock(), is_synthetic=True))
    store = AuthStore(engine)
    store.assign_role(user_id, "student", now=clock())  # Explicit trusted fixture grant; no role UI or HTTP grant.
    runtime = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
                               database_url=None, legacy_demo_mode=None, _env_file=None)
    settings = SessionAuthSettings(enabled=True,
        provider=AuthProviderSettings(provider_mode="oidc_boundary", provider_id="T08_SYNTHETIC_BROWSER",
            issuer=issuer, client_id=client_id, client_secret=client_secret, callback_allowlist=(redirect_uri,)),
        redirect_uri=redirect_uri, context_encryption_key=Fernet.generate_key().decode("ascii"))
    service = AuthService(settings, runtime, store,
        KeycloakOidcAdapter(settings, runtime, transport=httpx.MockTransport(backchannel)), clock=clock)
    privacy_settings = PrivacySettings(fixture_mode=True, notice_id=notice_id,
        controller_reference="DEMO_T08_TEST_CONTROLLER", age_assurance_method="adult_self_declaration",
        declaration_validity_seconds=86400)
    child = create_identity_v2_app(runtime, identity_service=service, privacy_settings=privacy_settings)
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

    def require_control(request):
        if (runtime.app_environment != "test" or request.client.host != "127.0.0.1"
            or not hmac.compare_digest(request.headers.get("X-T08-Fixture-Key", "").encode(), control_key.encode())):
            raise HTTPException(403, "Fixture control denied")

    @app.get("/__test__/ready")
    def ready(request: Request):
        require_control(request)
        return {"ready": True, "is_synthetic": True, "user_id": str(user_id), "issuer": issuer}

    @app.post("/__test__/advance")
    def advance(request: Request):
        require_control(request)
        clock.advance()
        return {"advanced": True}

    @app.post("/__test__/disable")
    def disable(request: Request):
        require_control(request)
        child.state.identity_service = None
        return {"disabled": True}

    @app.post("/__test__/privacy-closed")
    def privacy_closed(request: Request):
        require_control(request)
        child.state.privacy_service = PrivacyService(service, PrivacySettings())
        return {"processing_closed": True}

    @app.get("/__test__/stats")
    def stats(request: Request):
        require_control(request)
        with Session(engine) as session:
            user_count = session.scalar(select(func.count()).select_from(AuthUser))
        with lock:
            return {"user_count": user_count, **counts}

    app.mount("/v2", child)
    print("T08_FIXTURE_READY " + json.dumps({"web_origin": args.web_origin,
        "api_origin": f"http://127.0.0.1:{args.api_port}", "issuer": issuer, "user_id": str(user_id)}), flush=True)
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.api_port, access_log=False, log_level="warning")
    finally:
        tls_server.shutdown()
        tls_server.server_close()
        engine.dispose()


if __name__ == "__main__":
    main()
