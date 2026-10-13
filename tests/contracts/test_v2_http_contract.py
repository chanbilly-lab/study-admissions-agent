"""Compare generated TS, exported/live OpenAPI, and runnable v2 modes offline."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import socket

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from scripts.verify_contract import ContractMismatch, assert_schema_matches, load_contract, resolve_schema


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "packages" / "contracts" / "v2"
SECRET = "T02_CONTRACT_PRIVATE_STUDENT_83aa1"


@pytest.fixture(autouse=True)
def deny_contract_network(monkeypatch):
    """This directory does not inherit tests/backend/conftest.py's network guard."""
    for method_name in ("connect", "connect_ex"):
        original = getattr(socket.socket, method_name)

        def guarded(sock, address, original=original):
            # Windows asyncio implements socketpair using a loopback TCP pair.
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("External network forbidden in v2 contract tests")

        monkeypatch.setattr(socket.socket, method_name, guarded)
    original_resolution = socket.getaddrinfo

    def resolve_offline(host, *args, **kwargs):
        if host in (None, "127.0.0.1", "::1"):
            return original_resolution(host, *args, **kwargs)
        raise AssertionError("External DNS forbidden in v2 contract tests")

    monkeypatch.setattr(socket, "getaddrinfo", resolve_offline)


@pytest.fixture
def contract():
    return load_contract(ARTIFACTS / "generated.ts")


@pytest.fixture
def document():
    return json.loads((ARTIFACTS / "openapi.json").read_text(encoding="utf-8"))


@pytest.fixture
def application():
    from services.api.app.api.v2 import create_v2_app
    from services.api.app.settings import V2RuntimeSettings

    return create_v2_app(V2RuntimeSettings(
        app_environment="development", data_mode="demo", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None,
    ))


@pytest.fixture
def api(application):
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client


def assert_json_schema(value, schema, document):
    """Independently check JSON Schema constraints as well as TS shape.

    TS cannot express pattern, numeric bounds or empty-scope maxItems. These
    assertions deliberately exercise those facets without adding a dependency.
    Cross-field Page relationships are separately tested against Pydantic.
    """
    schema = resolve_schema(schema, document)
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            try:
                assert_json_schema(value, branch, document)
                return
            except AssertionError:
                continue
        raise AssertionError("Value satisfies no JSON Schema branch")
    kind = schema.get("type")
    if kind == "object":
        assert isinstance(value, dict)
        assert set(schema.get("required", [])) <= set(value)
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(properties)
        for key, item in value.items():
            assert_json_schema(item, properties[key], document)
    elif kind == "array":
        assert isinstance(value, list)
        assert len(value) >= schema.get("minItems", 0)
        assert len(value) <= schema.get("maxItems", len(value))
        for item in value:
            assert_json_schema(item, schema["items"], document)
    elif kind == "string":
        assert isinstance(value, str)
        assert len(value) >= schema.get("minLength", 0)
        assert len(value) <= schema.get("maxLength", len(value))
        if "pattern" in schema:
            assert re.search(schema["pattern"], value)
    elif kind == "integer":
        assert type(value) is int
    elif kind == "number":
        assert type(value) in (int, float)
    elif kind == "boolean":
        assert type(value) is bool
    elif kind == "null":
        assert value is None
    else:
        raise AssertionError(f"Unexpected unvalidated v2 schema type {kind!r}")
    if "const" in schema:
        assert type(value) is type(schema["const"]) and value == schema["const"]
    if "enum" in schema:
        assert any(type(value) is type(item) and value == item for item in schema["enum"])
    if kind in ("integer", "number"):
        if "minimum" in schema:
            assert value >= schema["minimum"]
        if "maximum" in schema:
            assert value <= schema["maximum"]


def response_schema(document, path, status):
    return document["paths"][path]["get"]["responses"][str(status)]["content"]["application/json"]["schema"]


def response_alias(document, path, status):
    identifier = document["paths"][path]["get"]["operationId"]
    return identifier[0].upper() + identifier[1:] + "Response" + str(status)


def assert_wire_response(response, document, contract, path, status):
    assert response.status_code == status, response.text
    payload = response.json()
    declaration = response_alias(document, path, status)
    schema = response_schema(document, path, status)
    assert_schema_matches(contract, declaration, schema, document)
    contract.assert_payload(declaration, payload)
    assert_json_schema(payload, schema, document)
    identifier = payload["meta"]["request_id"] if "meta" in payload else payload["error"]["request_id"]
    assert identifier == response.headers["X-Request-ID"]
    return payload


def test_contract_guard_rejects_external_connections_and_dns():
    with pytest.raises(AssertionError, match="External network"):
        socket.socket().connect(("192.0.2.1", 443))
    with pytest.raises(AssertionError, match="External DNS"):
        socket.getaddrinfo("external.invalid", 443)


def test_exported_schema_matches_live_http_schema_and_every_generated_component(api, document, contract):
    live = api.get("/openapi.json")
    assert live.status_code == 200
    assert live.json() == document
    assert document["servers"] == [{"url": "/v2"}]
    assert set(document["paths"]) == {"/config", "/offerings"}
    for name, schema in document["components"]["schemas"].items():
        assert_schema_matches(contract, name, schema, document)
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            # All response fields, including null fields, must be present.
            assert set(schema["required"]) == set(schema["properties"])
    assert "HTTPValidationError" not in document["components"]["schemas"]


def test_every_operation_response_alias_matches_the_published_protocol(document, contract):
    statuses = {"200", "401", "403", "404", "405", "409", "422", "429", "500", "503"}
    for path, operations in document["paths"].items():
        assert set(operations) == {"get"}
        operation = operations["get"]
        assert set(operation["responses"]) == statuses
        for status in statuses:
            response = operation["responses"][status]
            assert_schema_matches(contract, response_alias(document, path, status), response_schema(document, path, status), document)
            header = response["headers"]["X-Request-ID"]["schema"]
            assert header["type"] == "string"
            assert_json_schema("a" * 32, header, document)
            with pytest.raises(AssertionError):
                assert_json_schema("client-id", header, document)


def test_query_types_preserve_optional_fields_defaults_and_limits(document, contract):
    for path, operations in document["paths"].items():
        operation = operations["get"]
        properties = {parameter["name"]: parameter["schema"] for parameter in operation.get("parameters", [])}
        schema = {"type": "object", "properties": properties, "required": [], "additionalProperties": False}
        identifier = operation["operationId"]
        declaration = identifier[0].upper() + identifier[1:] + "Query"
        assert_schema_matches(contract, declaration, schema, document)
        contract.assert_payload(declaration, {})
        with pytest.raises(ContractMismatch):
            contract.assert_payload(declaration, {"unknown": "unsupported"})
        if path == "/config":
            assert properties == {}
        else:
            assert set(properties) == {"limit", "cursor"}
            assert properties["limit"]["default"] == 20
            assert properties["limit"]["minimum"] == 1 and properties["limit"]["maximum"] == 100
            assert_json_schema({"limit": 100, "cursor": "x" * 512}, schema, document)
            for payload in ({"limit": 0}, {"limit": 101}, {"limit": True}, {"cursor": ""}, {"cursor": "x" * 513}):
                with pytest.raises(AssertionError):
                    assert_json_schema(payload, schema, document)


@pytest.mark.parametrize("path,params", [("/config", {}), ("/offerings", {}), ("/offerings", {"limit": 100})])
def test_real_success_json_matches_generated_operation_type_and_json_schema(api, document, contract, path, params):
    assert_wire_response(api.get(path, params=params), document, contract, path, 200)


@pytest.mark.parametrize("environment,data_mode,model_mode,query_role", [
    ("development", "demo", "disabled", "demo_only"),
    ("development", "demo", "mock", "demo_only"),
    ("test", "demo", "disabled", "demo_only"),
    ("test", "demo", "mock", "demo_only"),
    ("development", "verified", "disabled", "published_readonly"),
    ("test", "verified", "disabled", "published_readonly"),
    ("production", "verified", "disabled", "published_readonly"),
])
@pytest.mark.parametrize("path,params,status", [
    ("/config", {}, 200), ("/offerings", {}, 200), ("/offerings", {"limit": 0}, 422),
])
def test_actual_runtime_modes_share_exported_protocol(
    document, contract, environment, data_mode, model_mode, query_role, path, params, status,
):
    from services.api.app.api.v2 import create_v2_app
    from services.api.app.settings import V2RuntimeSettings

    application = create_v2_app(V2RuntimeSettings(
        app_environment=environment, data_mode=data_mode, model_mode=model_mode,
        database_url=None, legacy_demo_mode=None, _env_file=None,
    ))
    with TestClient(application, raise_server_exceptions=False) as client:
        assert client.get("/openapi.json").json() == document
        payload = assert_wire_response(client.get(path, params=params), document, contract, path, status)
    if status == 200:
        assert payload["meta"]["data_mode"] == data_mode
        assert payload["meta"]["model_mode"] == model_mode
        for field in ("data_as_of", "profile_version_id", "release_id", "ruleset_version", "profile_mode"):
            assert payload["meta"][field] is None
        if path == "/config":
            assert payload["data"]["app_environment"] == environment
            assert payload["data"]["query_role"] == query_role
            assert payload["data"]["schema_version"] == "v2.t03"
            assert payload["data"]["data_mode"] == data_mode
            assert payload["data"]["model_mode"] == model_mode
            assert payload["data"]["business_available"] is False
            assert payload["data"]["live_available"] is False
            assert payload["data"]["supported_scope"] == []
        else:
            assert payload["data"]["items"] == []


@pytest.mark.parametrize("path,method,params,status", [
    ("/config", "get", {"unknown": SECRET}, 422),
    ("/offerings", "get", {"limit": SECRET}, 422),
    ("/offerings", "get", {"cursor": SECRET}, 422),
    ("/absent", "get", {}, 404),
    ("/config", "post", {}, 405),
])
def test_actual_validation_routing_and_cursor_errors_match_published_error_json(api, document, contract, path, method, params, status):
    response = api.request(method, path, params=params)
    assert SECRET not in response.text
    assert_wire_response(response, document, contract, "/config" if path != "/offerings" else path, status)


@pytest.mark.parametrize("status", [401, 403, 404, 405, 409, 422, 429, 500, 503])
def test_actual_fault_json_matches_all_generated_error_response_aliases(application, document, contract, status):
    @application.get("/_test/error", include_in_schema=False)
    def error_probe():
        if status == 500:
            raise RuntimeError(f"SQL password={SECRET}")
        raise HTTPException(status, detail=SECRET)

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/_test/error")
        assert SECRET not in response.text
        assert_wire_response(response, document, contract, "/config", status)
    assert "_test" not in json.dumps(application.openapi())


@pytest.mark.parametrize("mutation", ["missing_null", "year", "business", "mode", "data_mode",
                                      "environment", "query_role", "unexpected_owner", "wrong_array"])
def test_real_http_contract_rejects_missing_fields_and_business_drift(api, document, contract, mutation):
    payload = deepcopy(api.get("/config").json())
    if mutation == "missing_null":
        del payload["data"]["supported_province"]
    elif mutation == "year":
        payload["data"]["entry_year"] = 2027
    elif mutation == "business":
        payload["data"]["business_available"] = True
    elif mutation == "mode":
        payload["meta"]["model_mode"] = "live"
    elif mutation == "data_mode":
        payload["meta"]["data_mode"] = "production"
    elif mutation == "environment":
        payload["data"]["app_environment"] = "staging"
    elif mutation == "query_role":
        payload["data"]["query_role"] = "admin"
    elif mutation == "unexpected_owner":
        payload["meta"]["owner_id"] = SECRET
    else:
        payload["data"]["supported_scope"] = None
    with pytest.raises(ContractMismatch):
        contract.assert_payload(response_alias(document, "/config", 200), payload)
    with pytest.raises(AssertionError):
        assert_json_schema(payload, response_schema(document, "/config", 200), document)


def test_json_schema_enforces_constraints_typescript_cannot_express(api, document, contract):
    valid = api.get("/config").json()
    request_id = deepcopy(valid)
    request_id["meta"]["request_id"] = "A" * 32
    scope = deepcopy(valid)
    scope["data"]["supported_scope"] = ["gaokao"]
    declaration = response_alias(document, "/config", 200)
    for payload in (request_id, scope):
        # Correct TS wire types still do not make an invalid schema value safe.
        contract.assert_payload(declaration, payload)
        with pytest.raises(AssertionError):
            assert_json_schema(payload, response_schema(document, "/config", 200), document)
