"""Independent T02 HTTP acceptance, including failures on test-only routes."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
import subprocess
import sys

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest


REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
SECRET = "T02_PRIVATE_TOKEN_SQL_STUDENT_7c389"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def v2_app():
    from services.api.app.api.v2 import create_v2_app

    return create_v2_app()


@pytest.fixture
def v2_client(v2_app):
    with TestClient(v2_app, raise_server_exceptions=False) as client:
        yield client


def assert_identity(response, payload):
    request_id = payload["meta"]["request_id"] if "meta" in payload else payload["error"]["request_id"]
    assert REQUEST_ID.fullmatch(request_id), response.text
    assert response.headers["X-Request-ID"] == request_id
    return request_id


def assert_error(response, status, code=None):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert set(payload) == {"error"}
    error = payload["error"]
    assert set(error) == {"code", "message", "request_id", "details"}
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["details"], list)
    if code is not None:
        assert error["code"] == code
    for detail in error["details"]:
        assert set(detail) == {"field_path", "code", "message"}
        assert all(isinstance(value, str) and value for value in detail.values())
    assert SECRET not in response.text
    assert_identity(response, payload)
    return payload


def test_foundation_config_is_closed_and_does_not_advertise_m0_business(v2_client):
    response = v2_client.get("/config")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data", "meta"}
    assert payload["data"] == {
        "api_version": "v2", "schema_version": "v2.t03", "contract_stage": "foundation",
        "app_environment": "development", "query_role": "demo_only",
        "data_mode": "demo", "model_mode": "disabled", "live_available": False,
        "business_available": False, "supported_scope": [], "supported_province": None,
        "entry_year": None,
    }
    meta = payload["meta"]
    assert set(meta) == {
        "api_version", "request_id", "data_as_of", "profile_version_id", "release_id",
        "ruleset_version", "profile_mode", "data_mode", "model_mode",
    }
    assert meta["api_version"] == "v2"
    assert meta["data_mode"] == "demo" and meta["model_mode"] == "disabled"
    assert all(meta[key] is None for key in (
        "data_as_of", "profile_version_id", "release_id", "ruleset_version", "profile_mode",
    ))
    assert_identity(response, payload)


def test_request_identity_is_server_owned_and_changes_for_success_and_errors(v2_client):
    incoming = "a" * 32
    identifiers = []
    for path in ("/config", "/offerings", "/not-supported", "/offerings?limit=0"):
        response = v2_client.get(path, headers={"X-Request-ID": incoming, "Authorization": f"Bearer {SECRET}"})
        identifiers.append(assert_identity(response, response.json()))
        assert SECRET not in response.text
    assert incoming not in identifiers
    assert len(set(identifiers)) == len(identifiers)


@pytest.mark.parametrize("limit", [None, 1, 100])
def test_empty_catalog_preserves_requested_limit_and_has_no_false_next_page(v2_client, limit):
    response = v2_client.get("/offerings", params={} if limit is None else {"limit": limit})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["data"] == {"items": [], "page": {
        "limit": 20 if limit is None else limit, "next_cursor": None, "has_more": False,
    }}
    assert_identity(response, payload)


@pytest.mark.parametrize("value", ["0", "101", "-1", "1.5", "true", "NaN", "", SECRET])
def test_limit_boundaries_and_types_have_locatable_sanitized_errors(v2_client, value):
    payload = assert_error(v2_client.get("/offerings", params={"limit": value}), 422)
    assert any(item["field_path"] == "query.limit" for item in payload["error"]["details"])


@pytest.mark.parametrize("path,params", [
    ("/offerings", [("limit", "1"), ("limit", "2")]),
    ("/offerings", [("cursor", "first"), ("cursor", "second")]),
    ("/offerings", {"country": "CN"}),
    ("/offerings", {SECRET: SECRET}),
    ("/config", {"entry_year": "2027"}),
    ("/config", [("limit", "1"), ("limit", "1")]),
])
def test_extra_and_duplicate_query_parameters_cannot_be_ignored(v2_client, path, params):
    assert_error(v2_client.get(path, params=params), 422)


@pytest.mark.parametrize("cursor", ["", "x" * 513])
def test_malformed_cursor_is_validation_error(v2_client, cursor):
    payload = assert_error(v2_client.get("/offerings", params={"cursor": cursor}), 422)
    assert any(item["field_path"] == "query.cursor" for item in payload["error"]["details"])


@pytest.mark.parametrize("cursor", ["x", "x" * 512, SECRET, "tampered:release=2026"])
def test_well_shaped_but_unissued_cursor_is_explicitly_rejected(v2_client, cursor):
    assert_error(v2_client.get("/offerings", params={"cursor": cursor}), 422, "INVALID_CURSOR")


@pytest.mark.parametrize("method,path,status", [
    ("get", "/missing", 404), ("get", "/profiles", 404),
    ("post", "/profiles", 404), ("post", "/eligibility/check", 404),
    ("post", "/config", 405), ("delete", "/offerings", 405),
])
def test_unknown_paths_and_methods_use_v2_errors(v2_client, method, path, status):
    response = v2_client.request(method, path)
    assert_error(response, status)
    if status == 405:
        assert "GET" in response.headers["Allow"]


@pytest.mark.parametrize("status,code,headers", [
    (401, "UNAUTHORIZED", {"WWW-Authenticate": "Bearer"}),
    (403, "FORBIDDEN", {}), (404, "NOT_FOUND", {}),
    (405, "METHOD_NOT_ALLOWED", {"Allow": "GET"}),
    (409, "CONFLICT", {}), (422, "VALIDATION_ERROR", {}),
    (429, "TOO_MANY_REQUESTS", {"Retry-After": "30"}),
    (503, "SERVICE_UNAVAILABLE", {"Retry-After": "60"}),
])
def test_http_exceptions_use_safe_mapping_and_keep_protocol_headers(v2_app, status, code, headers):
    @v2_app.get("/_test/http-fault", include_in_schema=False)
    def fault():
        raise HTTPException(status, detail={"token": SECRET, "sql": f"SELECT '{SECRET}'"}, headers=headers)

    with TestClient(v2_app, raise_server_exceptions=False) as client:
        response = client.get("/_test/http-fault")
    assert_error(response, status, code)
    for key, value in headers.items():
        assert response.headers[key] == value
    assert "_test" not in json.dumps(v2_app.openapi())


def test_api_error_and_response_validation_failure_cannot_leak_exception_values(v2_app):
    from services.api.app.api.v2.errors import ApiError
    from services.api.app.api.v2.schemas import FoundationConfig

    @v2_app.get("/_test/domain-fault", include_in_schema=False)
    def domain_fault():
        raise ApiError(409, "CONFLICT")

    @v2_app.get("/_test/unexpected-fault", include_in_schema=False)
    def unexpected_fault():
        raise RuntimeError(f"password={SECRET}; SELECT * FROM students")

    @v2_app.get("/_test/serialization-fault", response_model=FoundationConfig, include_in_schema=False)
    def serialization_fault():
        return {"entry_year": SECRET}

    with TestClient(v2_app, raise_server_exceptions=False) as client:
        assert_error(client.get("/_test/domain-fault"), 409, "CONFLICT")
        for path in ("/_test/unexpected-fault", "/_test/serialization-fault"):
            assert_error(client.get(path), 500, "INTERNAL_ERROR")
    assert "_test" not in json.dumps(v2_app.openapi())


def test_page_model_validates_item_count_and_cursor_consistency():
    from services.api.app.api.v2.schemas import OfferingReference, Page

    valid = {"items": [{"id": "reference-only"}], "page": {"limit": 1, "next_cursor": "opaque", "has_more": True}}
    assert Page[OfferingReference].model_validate(valid).model_dump(mode="json") == valid
    invalid = [
        {"items": [{"id": "one"}, {"id": "two"}], "page": {"limit": 1, "next_cursor": None, "has_more": False}},
        {"items": [], "page": {"limit": 20, "next_cursor": None, "has_more": True}},
        {"items": [], "page": {"limit": 20, "next_cursor": "opaque", "has_more": False}},
        {"items": [], "page": {"limit": 20, "next_cursor": "", "has_more": True}},
        {"items": [], "page": {"limit": 20, "next_cursor": "   ", "has_more": True}},
        {"items": [], "page": {"limit": 0, "next_cursor": None, "has_more": False}},
        {"items": [], "page": {"limit": 101, "next_cursor": None, "has_more": False}},
    ]
    for payload in invalid:
        with pytest.raises(ValidationError):
            Page[OfferingReference].model_validate(payload)


def test_mounted_v2_never_touches_unmigrated_m0_database_or_provider(monkeypatch):
    from services.api.app.main import create_app
    from services.api.app.settings import Settings

    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:", sqlite_test_mode=True,
                        supported_province="浙江", entry_year=2027, model_mode="mock", assessment_date=date(2026, 9, 30))
    application = create_app(settings)

    def forbidden(*args, **kwargs):
        raise AssertionError("T02 attempted database/model use")

    monkeypatch.setattr(application.state.engine, "connect", forbidden)
    monkeypatch.setattr(application.state.provider, "draft_narrative", forbidden)
    try:
        with TestClient(application, raise_server_exceptions=False) as client:
            identities = []
            for path, status in (("/v1/config", 200), ("/v2/config", 200), ("/v2/offerings", 200),
                                 ("/v2/offerings?limit=0", 422), ("/v2/not-supported", 404)):
                response = client.get(path, headers={"X-Request-ID": "b" * 32})
                assert response.status_code == status, response.text
                identities.append(assert_identity(response, response.json()))
            assert len(set(identities)) == len(identities)
            assert "b" * 32 not in identities
            parent_schema = client.get("/openapi.json").json()
            child_schema = client.get("/v2/openapi.json").json()
            assert all(not path.startswith("/v2") for path in parent_schema["paths"])
            assert set(child_schema["paths"]) == {"/config", "/offerings"}
            assert child_schema["servers"] == [{"url": "/v2"}]
    finally:
        application.state.engine.dispose()


def test_mount_keeps_v1_success_and_error_wire_contract(client):
    response = client.get("/v1/config")
    payload = response.json()
    assert payload["data"]["supported_province"] == "浙江"
    assert payload["data"]["entry_year"] == 2027
    assert payload["meta"]["model_mode"] == "mock"
    assert "api_version" not in payload["meta"]
    assert_identity(response, payload)
    unauthorized = client.get("/v1/profiles")
    assert unauthorized.status_code == 401
    assert set(unauthorized.json()) == {"detail"}
    assert unauthorized.headers["WWW-Authenticate"] == "Bearer"
    assert REQUEST_ID.fullmatch(unauthorized.headers["X-Request-ID"])
    assert len(client.get("/v1/offerings").json()["data"]) == 4


@pytest.mark.parametrize("fault_kind", ["runtime", "serialization"])
def test_m0_mounted_v2_500_preserves_safe_body_and_parent_child_identity(app, fault_kind):
    from starlette.routing import Mount
    from services.api.app.api.v2.schemas import FoundationConfig

    # The existing app fixture creates a fresh isolated M0 application per case.
    # Only that fixture's mounted child receives this unpublished fault probe.
    child = next(route.app for route in app.routes if isinstance(route, Mount) and route.path == "/v2")
    if fault_kind == "runtime":
        @child.get("/_test/mounted-fault", include_in_schema=False)
        def runtime_fault():
            raise RuntimeError(f"token={SECRET}; SELECT * FROM students")
    else:
        @child.get("/_test/mounted-fault", response_model=FoundationConfig, include_in_schema=False)
        def serialization_fault():
            return {"entry_year": SECRET}

    incoming = "e" * 32
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/v2/_test/mounted-fault", headers={
            "X-Request-ID": incoming, "Authorization": f"Bearer {SECRET}",
        })
        payload = assert_error(response, 500, "INTERNAL_ERROR")
        assert payload["error"]["request_id"] != incoming
        assert payload["error"]["details"] == []
        # A handled child fault must leave both parent and child usable.
        for path in ("/v1/config", "/v2/config"):
            healthy = client.get(path)
            assert healthy.status_code == 200, healthy.text
            assert assert_identity(healthy, healthy.json()) != payload["error"]["request_id"]
    assert "_test" not in json.dumps(child.openapi())


def test_standalone_factory_does_not_import_m0_database_seed_or_model_modules():
    # A clean interpreter catches forbidden imports even when the main suite has
    # already imported M0 modules. Its socket guard also applies inside this child.
    program = r'''
import socket, sys
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
def guarded(original):
    def connect(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original(sock, address)
        raise AssertionError("External network forbidden in T02 subprocess")
    return connect
socket.socket.connect = guarded(original_connect)
socket.socket.connect_ex = guarded(original_connect_ex)
from fastapi.testclient import TestClient
from services.api.app.api.v2 import create_v2_app
app = create_v2_app()
with TestClient(app) as client:
    assert client.get("/config").status_code == 200
    assert client.get("/offerings").status_code == 200
for prefix in ("services.api.app.", "app."):
    for suffix in ("main", "database", "models", "migrations", "seed", "providers", "planning"):
        assert prefix + suffix not in sys.modules, prefix + suffix
print("standalone has no M0 database, seed, or provider dependencies")
'''
    result = subprocess.run([sys.executable, "-c", program], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
