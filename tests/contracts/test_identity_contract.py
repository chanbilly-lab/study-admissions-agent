"""Offline identity profile/schema checks; no provider or database construction."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from scripts.generate_contracts import generate_artifacts, load_openapi, UnsupportedSchema, write_or_check
from services.api.app.api.identity import create_identity_app, create_identity_v2_app, load_session_auth_settings
from services.api.app.api.public import create_public_app
from services.api.app.auth.config import AuthFlowError, SessionAuthSettings
from services.api.app.settings import V2RuntimeSettings


ROOT = Path(__file__).resolve().parents[2]


def runtime():
    return V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
                             database_url=None, legacy_demo_mode=None, _env_file=None)


@pytest.mark.parametrize("path", ["/auth/login", "/auth/session", "/auth/csrf", "/auth/callback?state=" + "s" * 43 + "&code=code"])
def test_closed_profile_is_safe_unavailable(path):
    with TestClient(create_identity_v2_app(runtime())) as client:
        response = client.get(path, follow_redirects=False)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "set-cookie" not in response.headers


def test_identity_parent_only_mounts_v2_and_keeps_foundation():
    app = create_identity_app(runtime(), SessionAuthSettings())
    with TestClient(app) as client:
        unavailable = client.get("/v2/auth/session")
        assert unavailable.status_code == 503
        assert unavailable.headers["cache-control"] == "no-store"
        assert unavailable.headers["referrer-policy"] == "no-referrer"
        assert client.get("/v2/config").json()["data"]["schema_version"] == "v2.t03"
        assert client.get("/v2/offerings").json()["data"]["items"] == []
        for path in ["/", "/v1/config", "/v1/auth/session", "/auth/session", "/docs"]:
            assert client.get(path).status_code == 404
        assert client.get("/v2/auth/session", headers={"Authorization": "Bearer demo-alice-token"}).status_code == 401


def test_original_public_foundation_still_has_no_auth_routes():
    with TestClient(create_public_app(runtime())) as client:
        assert client.get("/v2/auth/session").status_code == 404
    assert set(load_openapi()["paths"]) == {"/config", "/offerings"}


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("path", ["/v2/config", "/v2/absent"])
def test_parent_demo_write_rejection_is_private_before_child_guard(method, path):
    with TestClient(create_identity_app(runtime(), SessionAuthSettings())) as client:
        response = client.request(method, path, headers={"Authorization": "Bearer demo-alice-token"})
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_closed_factory_and_identity_schema_do_not_import_persistence_or_crypto():
    code = """
import sys
from services.api.app.api.identity import create_identity_app
from services.api.app.auth.config import SessionAuthSettings
from services.api.app.settings import V2RuntimeSettings
from scripts.generate_contracts import load_openapi, generate_artifacts
settings=V2RuntimeSettings(app_environment='production',data_mode='verified',model_mode='disabled',database_url=None,legacy_demo_mode=None,_env_file=None)
create_identity_app(settings,SessionAuthSettings())
generate_artifacts(load_openapi('identity'),allow_identity_redirects=True)
for prefix in ('sqlalchemy','psycopg','alembic','joserfc','cryptography','services.api.app.db','services.api.app.models','services.api.app.api.main','services.api.app.auth.store','services.api.app.auth.service','services.api.app.auth.oidc'):
    assert not any(m == prefix or m.startswith(prefix+'.') for m in sys.modules), prefix
print('closed identity/schema: no persistence, crypto, provider or M0')
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_identity_wire_and_artifacts_are_explicit():
    schema = load_openapi("identity")
    assert schema["info"]["version"] == "v2.t09"
    assert set(schema["paths"]) == {"/config", "/offerings", "/auth/login", "/auth/callback", "/auth/session",
                                    "/auth/csrf", "/auth/logout", "/privacy/notices/current", "/me/admission",
                                    "/me/age-declarations", "/me/consents", "/me/consents/{consent_id}",
        "/sharing/policy", "/access-grants", "/access-grants/{grant_id}", "/access-grants/{grant_id}/accept"}
    assert schema["components"]["securitySchemes"]["SessionCookie"]["name"] == "__Host-admissions-session"
    properties = schema["components"]["schemas"]["AuthSessionData"]["properties"]
    assert set(properties) == {"authenticated", "user_id", "expires_at", "is_synthetic", "private_business_available"}
    assert properties["private_business_available"]["const"] is False
    assert set(schema["components"]["schemas"]["AuthCsrfData"]["properties"]) == {"csrf_token", "expires_at"}
    assert schema["components"]["schemas"]["AuthLogoutData"]["properties"]["logged_out"]["const"] is True
    assert schema["paths"]["/auth/logout"]["post"]["security"] == [
        {"SessionCookie": [], "CsrfHeader": [], "RequestOrigin": []}]
    assert schema["components"]["securitySchemes"]["CsrfHeader"]["name"] == "X-CSRF-Token"
    assert "requestBody" not in schema["paths"]["/auth/logout"]["post"]
    artifacts = generate_artifacts(schema, allow_identity_redirects=True)
    assert "export type StartV2LoginResponse302 = undefined;" in artifacts["generated.ts"]
    assert "Response302Headers" in artifacts["generated.ts"]
    assert not write_or_check(artifacts, ROOT / "packages/contracts/v2/identity", check=True)
    for value in artifacts.values():
        assert "\r" not in value
    assert not write_or_check(generate_artifacts(load_openapi()), ROOT / "packages/contracts/v2", check=True)


@pytest.mark.parametrize("mutation", ["missing_location", "header_ref", "bad_header_schema", "other_redirect", "no_optin", "bad_content"])
def test_generator_rejects_unbounded_redirects(mutation):
    document = deepcopy(load_openapi("identity"))
    response = document["paths"]["/auth/login"]["get"]["responses"]["302"]
    if mutation == "missing_location":
        del response["headers"]["Location"]
    elif mutation == "header_ref":
        response["headers"]["Location"] = {"$ref": "#/components/headers/Location"}
    elif mutation == "bad_header_schema":
        response["headers"]["Location"]["schema"] = {"type": "object"}
    elif mutation == "other_redirect":
        document["paths"]["/config"]["get"]["responses"]["302"] = response
    elif mutation == "bad_content":
        response["content"] = None
    with pytest.raises(UnsupportedSchema):
        generate_artifacts(document, allow_identity_redirects=mutation != "no_optin")


def test_configuration_requires_explicit_file_and_process_secrets(monkeypatch, tmp_path):
    monkeypatch.delenv("IDENTITY_CONFIG_FILE", raising=False)
    monkeypatch.setenv("IDENTITY_CLIENT_SECRET", "unused-test-secret")
    monkeypatch.setenv("IDENTITY_CONTEXT_KEY", "not-a-key")
    assert load_session_auth_settings() == SessionAuthSettings()
    config = json.loads((ROOT / "config/identity/session.example.json").read_text())
    path = tmp_path / "explicit.json"
    path.write_text(json.dumps(config))
    monkeypatch.setenv("IDENTITY_CONFIG_FILE", str(path))
    with pytest.raises(AuthFlowError):
        load_session_auth_settings()
    monkeypatch.setenv("IDENTITY_CONTEXT_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    selected = load_session_auth_settings()
    assert selected.enabled is True
    assert selected.provider.client_secret.get_secret_value() == "unused-test-secret"
    with pytest.raises(AuthFlowError):  # no database configured, no implicit SQLite/M0 fallback
        create_identity_app(runtime(), selected)


@pytest.mark.parametrize("content", ["[]", "{\"enabled\":false,\"enabled\":true}",
    "{\"enabled\":false,\"context_encryption_key\":null}",
    "{\"enabled\":false,\"provider\":{\"client_secret\":null}}", "{", "x" * 65537],
    ids=["array", "duplicate", "inline-key", "inline-secret", "syntax", "too-large"])
def test_configuration_failure_is_safe(monkeypatch, tmp_path, content):
    path = tmp_path / "invalid.json"
    path.write_text(content)
    monkeypatch.setenv("IDENTITY_CONFIG_FILE", str(path))
    with pytest.raises(AuthFlowError) as caught:
        load_session_auth_settings()
    assert caught.value.status_code == 503
    assert str(caught.value) == "Authentication service is unavailable"
