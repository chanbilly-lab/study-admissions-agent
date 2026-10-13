"""Independent T03 acceptance exercises settings and the actual HTTP boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest


ROOT = Path(__file__).resolve().parents[2]
SECRET = "T03_PRIVATE_PASSWORD_STUDENT_57fa2"
REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")


def runtime(**overrides):
    from services.api.app.settings import V2RuntimeSettings

    return V2RuntimeSettings(_env_file=None, **overrides)


def production(**overrides):
    return runtime(app_environment="production", data_mode="verified", model_mode="disabled", **overrides)


def public_application(**overrides):
    from services.api.app.api.public import create_public_app

    return create_public_app(production(), **overrides)


def assert_request_id(response):
    body = response.json()
    identifier = body["meta"]["request_id"] if "meta" in body else body["error"]["request_id"]
    assert REQUEST_ID.fullmatch(identifier)
    assert response.headers["X-Request-ID"] == identifier
    return identifier


def assert_closed_verified_config(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"] == {
        "api_version": "v2", "schema_version": "v2.t03", "contract_stage": "foundation",
        "app_environment": "production", "query_role": "published_readonly",
        "data_mode": "verified", "model_mode": "disabled", "live_available": False,
        "business_available": False, "supported_scope": [], "supported_province": None,
        "entry_year": None,
    }
    assert body["meta"]["data_mode"] == "verified" and body["meta"]["model_mode"] == "disabled"
    assert all(body["meta"][name] is None for name in (
        "data_as_of", "profile_version_id", "release_id", "ruleset_version", "profile_mode",
    ))
    assert_request_id(response)


def assert_safe_error(response, status, code=None):
    assert response.status_code == status, response.text
    assert SECRET not in response.text
    assert all(SECRET not in value for value in response.headers.values())
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "request_id", "details"}
    if code:
        assert body["error"]["code"] == code
    assert_request_id(response)
    return body


def test_security_network_guard_is_active():
    with socket.socket() as client_socket:
        with pytest.raises(AssertionError, match="External network forbidden"):
            client_socket.connect(("192.0.2.1", 443))
    with pytest.raises(AssertionError, match="External DNS forbidden"):
        socket.getaddrinfo("external.invalid", 443)


@pytest.mark.parametrize("environment,data,model,role", [
    ("development", "demo", "disabled", "demo_only"),
    ("development", "demo", "mock", "demo_only"),
    ("test", "demo", "disabled", "demo_only"),
    ("test", "demo", "mock", "demo_only"),
    ("development", "verified", "disabled", "published_readonly"),
    ("test", "verified", "disabled", "published_readonly"),
    ("production", "verified", "disabled", "published_readonly"),
])
def test_valid_mode_matrix_preserves_server_modes_and_derives_query_role(environment, data, model, role):
    from services.api.app.api.v2 import create_v2_app

    settings = runtime(app_environment=environment, data_mode=data, model_mode=model)
    assert settings.query_role == role
    with TestClient(create_v2_app(settings)) as client:
        response = client.get("/config")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["app_environment"] == environment
        assert body["data"]["query_role"] == role
        assert body["data"]["data_mode"] == body["meta"]["data_mode"] == data
        assert body["data"]["model_mode"] == body["meta"]["model_mode"] == model
        assert body["data"]["business_available"] is False
        assert body["data"]["live_available"] is False
        assert_request_id(response)


@pytest.mark.parametrize("environment,data,model", [
    ("production", "demo", "disabled"), ("production", "demo", "mock"),
    ("development", "verified", "mock"), ("test", "verified", "mock"),
    ("production", "verified", "mock"),
] + [(environment, data, "live") for environment in ("development", "test", "production")
     for data in ("demo", "verified")])
def test_invalid_mode_combinations_and_unimplemented_live_fail_at_startup(environment, data, model):
    with pytest.raises(ValueError):
        runtime(app_environment=environment, data_mode=data, model_mode=model)


@pytest.mark.parametrize("field", ["app_environment", "data_mode", "model_mode", "unrecognised_option"])
def test_unknown_startup_values_fail_without_disclosing_input(field):
    with pytest.raises(ValueError) as caught:
        runtime(**{field: SECRET})
    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)


def test_settings_are_frozen_and_do_not_load_m0_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "MODEL_MODE=live\nDEMO_MODE=false\nDATABASE_URL=sqlite:///unsafe.db\n"
        "V2_APP_ENVIRONMENT=production\nV2_DATA_MODE=verified\nV2_MODEL_MODE=live\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    from services.api.app.settings import V2RuntimeSettings

    settings = V2RuntimeSettings()
    assert (settings.app_environment, settings.data_mode, settings.model_mode, settings.query_role) == (
        "development", "demo", "disabled", "demo_only",
    )
    assert settings.database_url is None
    with pytest.raises(ValidationError):
        settings.data_mode = "verified"
    assert settings.data_mode == "demo"


def test_process_v2_environment_is_snapshotted_and_m0_model_aliases_do_not_override(monkeypatch):
    from services.api.app.api.v2 import create_v2_app
    from services.api.app.settings import V2RuntimeSettings

    monkeypatch.setenv("V2_APP_ENVIRONMENT", "production")
    monkeypatch.setenv("V2_DATA_MODE", "verified")
    monkeypatch.setenv("V2_MODEL_MODE", "disabled")
    monkeypatch.setenv("MODEL_MODE", "mock")
    monkeypatch.setenv("M0_MODEL_MODE", "live")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{SECRET}.db")
    settings = V2RuntimeSettings()
    assert settings.database_url is None
    application = create_v2_app(settings)
    monkeypatch.setenv("V2_DATA_MODE", "demo")
    monkeypatch.setenv("V2_MODEL_MODE", "mock")
    with TestClient(application) as client:
        assert_closed_verified_config(client.get("/config"))


@pytest.mark.parametrize("data,legacy", [("demo", True), ("verified", False), ("demo", None), ("verified", None)])
def test_compatible_legacy_switch_only_validates_and_never_selects_modes(data, legacy):
    settings = runtime(data_mode=data, legacy_demo_mode=legacy)
    assert settings.data_mode == data


@pytest.mark.parametrize("data,legacy", [("demo", False), ("verified", True)])
def test_conflicting_legacy_switch_fails_without_changing_mode(data, legacy):
    with pytest.raises(ValueError):
        runtime(data_mode=data, legacy_demo_mode=legacy)


def test_legacy_process_switch_is_not_an_alternate_mode_selector(monkeypatch):
    from services.api.app.settings import V2RuntimeSettings

    monkeypatch.setenv("DEMO_MODE", "false")
    with pytest.raises(ValueError):
        V2RuntimeSettings()
    monkeypatch.setenv("V2_DATA_MODE", "verified")
    assert V2RuntimeSettings().data_mode == "verified"
    monkeypatch.setenv("DEMO_MODE", "true")
    with pytest.raises(ValueError):
        V2RuntimeSettings()
    monkeypatch.setenv("DEMO_MODE", SECRET)
    with pytest.raises(ValueError) as caught:
        V2RuntimeSettings()
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("dsn", [
    f"sqlite:///{SECRET}.db", f"mysql://service:{SECRET}@127.0.0.1/facts",
    f"postgresql://demo:{SECRET}@127.0.0.1/facts",
    f"postgresql://%64emo:{SECRET}@127.0.0.1/facts",
    f"postgresql://reader:{SECRET}@127.0.0.1/admissions_demo",
    f"postgresql://reader:{SECRET}@127.0.0.1/%61dmissions_demo",
    "postgresql://reader:demo_local_only@127.0.0.1/facts",
    "postgresql://reader:%64emo_local_only@127.0.0.1/facts",
    f"postgresql://DEMO_reader:{SECRET}@127.0.0.1/facts",
    f"postgresql://reader:{SECRET}@127.0.0.1/DEMO_facts",
    f"postgresqlx://reader:{SECRET}@127.0.0.1/facts",
    f"not-a-url-{SECRET}",
])
def test_verified_database_url_rejects_unsupported_or_canonical_demo_credentials_safely(dsn):
    with pytest.raises(ValueError) as caught:
        production(database_url=dsn)
    assert SECRET not in str(caught.value)
    assert dsn not in str(caught.value)


@pytest.mark.parametrize("query", [
    "user=demo", "password=demo_local_only", "dbname=admissions_demo",
    "user=demo&password=demo_local_only&dbname=admissions_demo",
    "username=demo", "database=admissions_demo", "service=demo", "passfile=private-file",
    "USER=demo", "%75ser=demo",
])
def test_database_url_query_cannot_override_canonical_identity_or_read_credentials_file(query):
    dsn = f"postgresql+psycopg://reader:{SECRET}@127.0.0.1/facts?{query}"
    with pytest.raises(ValueError) as caught:
        production(database_url=dsn)
    assert SECRET not in str(caught.value)
    assert dsn not in str(caught.value)


@pytest.mark.parametrize("dsn", [
    None,
    f"postgresql://published_reader:{SECRET}@127.0.0.1:1/published_facts",
    f"postgresql+psycopg://demography_reader:{SECRET}@127.0.0.1:1/demography_2026",
    f"postgresql+psycopg://reader:{SECRET}@127.0.0.1:1/published_facts?sslmode=require",
])
def test_verified_disabled_needs_no_key_or_database_connection(dsn):
    from services.api.app.api.public import create_public_app

    settings = production(database_url=dsn)
    assert SECRET not in repr(settings)
    assert SECRET not in str(settings)
    with TestClient(create_public_app(settings)) as client:
        assert_closed_verified_config(client.get("/v2/config"))
        response = client.get("/v2/offerings")
        assert response.status_code == 200
        assert response.json()["data"] == {"items": [], "page": {
            "limit": 20, "next_cursor": None, "has_more": False,
        }}
        assert_request_id(response)


@pytest.mark.parametrize("settings", [
    {"app_environment": "development", "data_mode": "demo"},
    {"app_environment": "test", "data_mode": "verified"},
    {"app_environment": "development", "data_mode": "verified"},
])
def test_public_factory_cannot_accept_non_production_runtime(settings):
    from services.api.app.api.public import create_public_app

    with pytest.raises(ValueError):
        create_public_app(runtime(**settings))


@pytest.mark.parametrize("bypass,updates", [
    ("copy", {"data_mode": "demo"}), ("copy", {"model_mode": "mock"}),
    ("construct", {"model_mode": "live"}), ("construct", {"model_mode": "mock"}),
    ("construct", {"data_mode": SECRET}),
])
def test_factories_revalidate_settings_even_if_pydantic_construction_was_bypassed(bypass, updates):
    from services.api.app.api.public import create_public_app
    from services.api.app.api.v2 import create_v2_app
    from services.api.app.settings import V2RuntimeSettings

    if bypass == "copy":
        invalid = production().model_copy(update=updates)
    else:
        values = {"app_environment": "production", "data_mode": "verified", "model_mode": "disabled",
                  "database_url": None, "legacy_demo_mode": None}
        values.update(updates)
        invalid = V2RuntimeSettings.model_construct(**values)
    for factory in (create_public_app, create_v2_app):
        with pytest.raises(ValueError) as caught:
            factory(invalid)
        assert SECRET not in str(caught.value)


def test_public_route_tree_has_only_v2_and_no_parent_docs_or_private_routes():
    from starlette.routing import Mount

    application = public_application()
    assert len(application.routes) == 1
    route = application.routes[0]
    assert isinstance(route, Mount) and route.path == "/v2"
    child = route.app
    assert {item.path for item in child.routes} == {"/openapi.json", "/config", "/offerings"}
    assert all(set(item.methods) <= {"GET", "HEAD"} for item in child.routes)
    with TestClient(application) as client:
        document = client.get("/v2/openapi.json").json()
        assert set(document["paths"]) == {"/config", "/offerings"}
        assert document["servers"] == [{"url": "/v2"}]
        assert "demo-alice-token" not in json.dumps(document)


@pytest.mark.parametrize("path", [
    "/v1", "/v1/", "/v1/config", "/v1/config/", "/v1/offerings", "/v1/offerings/DEMO_CN_GENERAL_2027",
    "/v1/profiles", "/v1/profiles/private-profile", "/v1/eligibility/check", "/v1/plans/drafts",
    "/v1/plans/private-plan", "/v1/evidence/private-evidence", "/v1/openapi.json", "/openapi.json",
    "/docs", "/redoc", "/health/live", "/health/ready",
])
def test_production_v1_and_parent_entrypoints_are_absent_for_every_method(path):
    with TestClient(public_application(), follow_redirects=False) as client:
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            response = client.request(method, path, headers={"Authorization": "Bearer demo-alice-token"})
            assert response.status_code == 404, (method, path, response.status_code, response.text)


@pytest.mark.parametrize("path", [
    "/v2/profiles", "/v2/profiles/", "/v2/profiles/private-profile", "/v2/eligibility/check",
    "/v2/plans/drafts", "/v2/plans/private-plan", "/v2/qa", "/v2/admin/sources", "/v2/me/data",
])
def test_production_private_paths_cannot_bypass_identity_or_minor_gates(path):
    with TestClient(public_application(), follow_redirects=False) as client:
        for credential in (None, "demo-alice-token", "demo-bob-token", SECRET):
            headers = {} if credential is None else {"Authorization": f"Bearer {credential}"}
            for method in ("GET", "POST", "PATCH", "DELETE"):
                response = client.request(method, path, headers=headers, json={
                    "owner_id": "demo_alice", "age": 18, "confirmed": True,
                    "consent": True, "data_mode": "demo", "model_mode": "mock",
                })
                if credential in {"demo-alice-token", "demo-bob-token"}:
                    assert_safe_error(response, 401, "UNAUTHORIZED")
                else:
                    assert_safe_error(response, 404, "NOT_FOUND")


@pytest.mark.parametrize("headers", [
    {"Authorization": "Bearer demo-alice-token"}, {"Authorization": "bearer demo-bob-token"},
    {"Authorization": "BEARER demo-alice-token"}, {"Authorization": " Bearer demo-bob-token "},
    {"Authorization": "Bearer    demo-alice-token"}, {"Authorization": "Bearer\tdemo-bob-token"},
    {"Authorization": f"Bearer {SECRET}, Bearer demo-alice-token"},
    {"Authorization": f"Bearer demo-bob-token, Bearer {SECRET}"},
    [("Authorization", f"Bearer {SECRET}"), ("Authorization", "Bearer demo-alice-token")],
    [("Authorization", "Bearer demo-bob-token"), ("Authorization", f"Bearer {SECRET}")],
])
def test_known_demo_bearer_variants_are_rejected_on_actual_public_routes(headers):
    with TestClient(public_application()) as client:
        for path in ("/v2/config", "/v2/offerings", "/v2/openapi.json", "/v2/private-unimplemented"):
            response = client.get(path, headers=headers)
            body = assert_safe_error(response, 401, "UNAUTHORIZED")
            assert body["error"]["details"] == []
            assert response.headers["WWW-Authenticate"] == "Bearer"
            assert "demo-alice-token" not in response.text and "demo-bob-token" not in response.text


@pytest.mark.parametrize("path", [
    "/v2", "/v2/", "/v2/config/", "/v2/offerings/", "/v2/openapi.json", "/v2/private-unimplemented",
])
def test_known_demo_credentials_cannot_bypass_rejection_via_method_docs_or_redirect(path):
    with TestClient(public_application(), follow_redirects=False) as client:
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            response = client.request(method, path, headers={"Authorization": "Bearer demo-alice-token"})
            assert response.status_code == 401, (method, path, response.status_code, response.text)
            assert "location" not in response.headers
            assert response.headers["WWW-Authenticate"] == "Bearer"
            if method == "HEAD":
                assert response.content == b""
                assert REQUEST_ID.fullmatch(response.headers["X-Request-ID"])
            else:
                assert_safe_error(response, 401, "UNAUTHORIZED")


@pytest.mark.parametrize("authorization", [
    None, f"Bearer {SECRET}", "Bearer demo-alice-token-extra", "Basic demo-alice-token",
])
def test_unknown_tokens_do_not_create_an_authenticated_identity(authorization):
    headers = {} if authorization is None else {"Authorization": authorization}
    with TestClient(public_application()) as client:
        response = client.get("/v2/config", headers=headers)
        assert_closed_verified_config(response)
        assert SECRET not in response.text
        assert "owner" not in response.text and "subject" not in response.text
        assert_safe_error(client.get("/v2/profiles", headers=headers), 404, "NOT_FOUND")


@pytest.mark.parametrize("name,value", [
    ("data_mode", "demo"), ("model_mode", "mock"), ("app_environment", "development"),
    ("query_role", "demo_only"), ("owner_id", SECRET), ("age", "18"), ("confirmed", "true"),
])
def test_request_query_cannot_select_modes_roles_or_private_processing(name, value):
    with TestClient(public_application()) as client:
        for path in ("/v2/config", "/v2/offerings"):
            assert_safe_error(client.get(path, params={name: value}), 422, "VALIDATION_ERROR")
        assert_closed_verified_config(client.get("/v2/config"))


def test_request_headers_and_body_cannot_mutate_startup_modes():
    with TestClient(public_application()) as client:
        response = client.request("GET", "/v2/config", headers={
            "X-Data-Mode": "demo", "X-Model-Mode": "mock", "X-App-Environment": "development",
            "X-Query-Role": "demo_only", "X-Request-ID": "f" * 32,
        }, json={"data_mode": "demo", "model_mode": "mock", "query_role": "demo_only"})
        if response.status_code == 200:
            assert_closed_verified_config(response)
        else:
            assert_safe_error(response, 422, "VALIDATION_ERROR")
        assert_request_id(response) != "f" * 32
        assert_safe_error(client.post("/v2/config", json={"data_mode": "demo"}), 405, "METHOD_NOT_ALLOWED")
        assert_closed_verified_config(client.get("/v2/config"))


def candidate(**overrides):
    from services.api.app.api.catalog_access import CatalogCandidate

    values = {
        "id": "reviewed-context-reference", "dataset_id": "verified_catalog", "data_mode": "verified",
        "is_synthetic": False, "review_status": "reviewed", "publication_status": "published", "withdrawn": False,
    }
    values.update(overrides)
    return CatalogCandidate(**values)


@pytest.mark.parametrize("overrides", [
    {"id": "DEMO_" + SECRET}, {"is_synthetic": True}, {"data_mode": "demo"},
    {"dataset_id": "demo_catalog"}, {"dataset_id": SECRET}, {"review_status": "pending"},
    {"publication_status": "draft"}, {"withdrawn": True}, {},
])
def test_verified_http_catalog_refuses_pollution_and_unbacked_release_labels_as_a_whole(overrides):
    # Even superficially published labels lack an actual T19 published release.
    rows = [candidate(id="first-safe-looking-reference"), candidate(**overrides)]
    with TestClient(public_application(catalog_candidates=rows)) as client:
        response = client.get("/v2/offerings")
        body = assert_safe_error(response, 503, "SERVICE_UNAVAILABLE")
        assert body["error"]["details"] == []
        assert "first-safe-looking-reference" not in response.text
        assert "reviewed-context-reference" not in response.text
        assert "items" not in body
        assert_closed_verified_config(client.get("/v2/config"))


def test_demo_http_catalog_never_accepts_verified_facts():
    from services.api.app.api.v2 import create_v2_app

    with TestClient(create_v2_app(runtime(), catalog_candidates=[candidate()])) as client:
        assert_safe_error(client.get("/offerings"), 503, "SERVICE_UNAVAILABLE")


@pytest.mark.parametrize("kind", ["copy", "construct", "missing_fields", "extra_private_field"])
def test_verified_http_catalog_revalidates_malformed_candidate_rows_before_any_release(kind):
    from services.api.app.api.catalog_access import CatalogCandidate

    if kind == "copy":
        malformed = candidate().model_copy(update={"id": None})
    elif kind == "construct":
        malformed = CatalogCandidate.model_construct(**{**candidate().model_dump(), "id": 17})
    elif kind == "missing_fields":
        malformed = {"id": SECRET}
    else:
        malformed = {**candidate().model_dump(), "private_student_attachment": SECRET}
    with TestClient(public_application(catalog_candidates=[candidate(), malformed])) as client:
        body = assert_safe_error(client.get("/v2/offerings"), 503, "SERVICE_UNAVAILABLE")
        assert body["error"]["details"] == []


@pytest.mark.parametrize("environment", [
    {"V2_APP_ENVIRONMENT": "production", "V2_DATA_MODE": "verified"},
    {"V2_DATA_MODE": "verified"}, {"DEMO_MODE": "false"},
])
def test_m0_guard_and_seed_refuse_before_fixture_read_or_engine_use(monkeypatch, environment, tmp_path):
    from services.api.app import main
    from services.api.app.seed import seed
    from services.api.app.settings import Settings, assert_m0_allowed

    old_settings = Settings(_env_file=None)
    def forbidden_initialisation(*args, **kwargs):
        pytest.fail("Blocked M0 factory initialised a database or model provider")
    monkeypatch.setattr(main, "make_engine", forbidden_initialisation)
    monkeypatch.setattr(main, "provider_for", forbidden_initialisation)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        assert_m0_allowed()
    with pytest.raises(ValueError):
        Settings(_env_file=None)
    with pytest.raises(ValueError):
        main.create_app(old_settings)

    fixture_path = tmp_path / "forbidden-demo-fixture.json"
    original_read_text = Path.read_text

    def forbid_fixture_read(path, *args, **kwargs):
        if path == fixture_path:
            pytest.fail("Blocked seed read a fixture before its mode guard")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", forbid_fixture_read)

    class ForbiddenEngine:
        def __getattr__(self, name):
            pytest.fail(f"Blocked seed touched engine member {name}")

    with pytest.raises(ValueError):
        seed(ForbiddenEngine(), fixture_path=fixture_path)


@pytest.mark.parametrize("configured_database", [False, True])
def test_fresh_public_process_has_no_m0_imports_model_keys_or_database_connection(configured_database):
    # tests/backend/conftest.py imports M0 globally; a clean interpreter is the
    # meaningful proof that the public startup graph cannot initialise M0.
    program = r'''
import importlib.abc, json, socket, sys
blocked = {"main", "database", "models", "migrations", "seed", "providers", "planning", "catalog", "schemas"}
class NoM0Imports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        for prefix in ("services.api.app.", "app."):
            if fullname.startswith(prefix) and fullname[len(prefix):].split(".")[0] in blocked:
                raise AssertionError("Forbidden M0 import: " + fullname)
        return None
sys.meta_path.insert(0, NoM0Imports())
for name in ("connect", "connect_ex"):
    original = getattr(socket.socket, name)
    def guarded(sock, address, original=original):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            assert address[1] != 1, "Attempted PostgreSQL connection"
            return original(sock, address)
        raise AssertionError("External network forbidden in T03 subprocess")
    setattr(socket.socket, name, guarded)
original_resolution = socket.getaddrinfo
def no_external_resolution(host, *args, **kwargs):
    assert host in (None, "127.0.0.1", "::1"), "External DNS forbidden"
    return original_resolution(host, *args, **kwargs)
socket.getaddrinfo = no_external_resolution
from fastapi.testclient import TestClient
from services.api.app.api.public import create_public_app
app = create_public_app()
with TestClient(app) as client:
    config = client.get("/v2/config").json()
    assert config["data"]["data_mode"] == "verified"
    assert config["data"]["model_mode"] == "disabled"
    assert config["data"]["business_available"] is False
    assert config["data"]["live_available"] is False
    assert config["data"]["query_role"] == "published_readonly"
    assert client.get("/v2/offerings").json()["data"]["items"] == []
    assert client.get("/v1/config").status_code == 404
for prefix in ("services.api.app.", "app."):
    assert not any(prefix + suffix in sys.modules for suffix in blocked)
assert not any(name.startswith(("psycopg", "psycopg2")) for name in sys.modules)
print("public startup has no M0, model or database dependencies")
'''
    environment = dict(os.environ)
    environment.update({"V2_APP_ENVIRONMENT": "production", "V2_DATA_MODE": "verified", "V2_MODEL_MODE": "disabled"})
    if configured_database:
        environment["V2_DATABASE_URL"] = f"postgresql://published_reader:{SECRET}@127.0.0.1:1/published_facts"
    result = subprocess.run([sys.executable, "-c", program], cwd=ROOT, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no M0, model or database dependencies" in result.stdout
    assert SECRET not in result.stdout + result.stderr
