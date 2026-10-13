"""Offline checks for the generated v2 contract and the bounded generator."""

import copy
import re
import socket
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from scripts import generate_contracts as generator
from scripts.verify_contract import Contract, assert_schema_matches
from services.api.app.api.v2 import create_v2_app


def baseline_application():
    from services.api.app.settings import V2RuntimeSettings

    return create_v2_app(V2RuntimeSettings(
        app_environment="development", data_mode="demo", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None,
    ))


@pytest.fixture(autouse=True)
def deny_external_network(monkeypatch):
    # Windows asyncio's internal socketpair uses loopback, not an external API.
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def offline_connect(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        raise AssertionError("v2 contract test attempted external network access")

    def offline_connect_ex(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect_ex(sock, address)
        raise AssertionError("v2 contract test attempted external network access")

    monkeypatch.setattr(socket.socket, "connect", offline_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", offline_connect_ex)


def closed_object(properties, required=()):
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": list(required)}


def document_with(schema):
    return {"components": {"schemas": {"Sample": schema}}, "paths": {}}


def reverse_mappings(value):
    if isinstance(value, dict):
        return {key: reverse_mappings(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reverse_mappings(item) for item in value]
    return value


def test_real_factory_artifacts_are_current_and_deterministic():
    first = generator.generate_artifacts(generator.load_openapi())
    second = generator.generate_artifacts(generator.load_openapi())
    assert first == second
    assert first == generator.generate_artifacts(reverse_mappings(generator.load_openapi()))
    for filename, content in first.items():
        assert (generator.OUTPUT_DIR / filename).read_bytes() == content.encode("utf-8")
    assert not re.search(r"\b(?:any|unknown)\b", first["generated.ts"])
    assert "Generated at" not in first["generated.ts"]


@pytest.mark.parametrize("process_settings", [
    {"V2_APP_ENVIRONMENT": "production", "V2_DATA_MODE": "verified", "V2_MODEL_MODE": "disabled"},
    {"V2_APP_ENVIRONMENT": "invalid", "V2_DATA_MODE": "invalid", "V2_MODEL_MODE": "invalid",
     "V2_DATABASE_URL": "sqlite:///must-not-open.db", "DEMO_MODE": "not-a-bool"},
    {"V2_APP_ENVIRONMENT": "production", "V2_DATA_MODE": "demo", "V2_MODEL_MODE": "live",
     "V2_DATABASE_URL": "postgresql+psycopg://demo:demo_local_only@external.invalid/admissions_demo",
     "DEMO_MODE": "false", "V2_LEGACY_DEMO_MODE": "invalid", "MODEL_MODE": "live"},
])
def test_export_ignores_all_server_and_legacy_process_configuration(monkeypatch, process_settings):
    expected = {name: (generator.OUTPUT_DIR / name).read_bytes()
                for name in ("openapi.json", "generated.ts")}
    for name, value in process_settings.items():
        monkeypatch.setenv(name, value)
    actual = generator.generate_artifacts(generator.load_openapi())
    assert {name: text.encode("utf-8") for name, text in actual.items()} == expected
    assert generator.main(["--check"]) == 0


def test_export_does_not_read_local_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    local_env = tmp_path / ".env"
    local_env.write_text("V2_APP_ENVIRONMENT=production\nV2_DATA_MODE=demo\n"
                         "V2_MODEL_MODE=live\nV2_DATABASE_URL=sqlite:///must-not-open.db\n"
                         "DEMO_MODE=not-a-bool\nMODEL_MODE=invalid\n", encoding="utf-8")
    before = local_env.read_bytes()
    assert generator.main(["--check"]) == 0
    assert local_env.read_bytes() == before
    assert not (tmp_path / "must-not-open.db").exists()


def test_every_component_and_operation_matches_openapi_semantics():
    document = generator.load_openapi()
    contract = Contract(generator.generate_types(document))
    for name, schema in document["components"]["schemas"].items():
        assert_schema_matches(contract, name, schema, document)
        assert schema.get("additionalProperties") is False
    for path_item in document["paths"].values():
        for operation in path_item.values():
            identifier = operation["operationId"]
            prefix = identifier[0].upper() + identifier[1:]
            parameters = operation.get("parameters", [])
            query_schema = closed_object(
                {parameter["name"]: parameter["schema"] for parameter in parameters},
                [parameter["name"] for parameter in parameters if parameter.get("required", False)],
            )
            assert_schema_matches(contract, prefix + "Query", query_schema, document)
            for status, response in operation["responses"].items():
                assert_schema_matches(contract, prefix + "Response" + status,
                                      response["content"]["application/json"]["schema"], document)


@pytest.mark.parametrize("path,status,declaration", [
    ("/config", 200, "GetV2ConfigResponse200"),
    ("/offerings?limit=1", 200, "ListV2OfferingsResponse200"),
    ("/offerings?limit=0", 422, "ListV2OfferingsResponse422"),
    ("/offerings?cursor=unissued", 422, "ListV2OfferingsResponse422"),
    ("/unknown", 404, "ErrorEnvelope"),
])
def test_real_http_json_matches_generated_types(path, status, declaration):
    contract = Contract(generator.generate_types(generator.load_openapi()))
    with TestClient(baseline_application()) as client:
        response = client.get(path)
    assert response.status_code == status
    contract.assert_payload(declaration, response.json())


def test_required_nulls_and_false_literals_cannot_drift():
    document = generator.load_openapi()
    contract = Contract(generator.generate_types(document))
    meta = document["components"]["schemas"]["Meta"]
    assert set(meta["required"]) == set(meta["properties"])
    for name in ("data_as_of", "profile_version_id", "release_id", "ruleset_version", "profile_mode"):
        assert meta["properties"][name]["type"] == "null"
    config = document["components"]["schemas"]["FoundationConfig"]
    assert set(config["required"]) == set(config["properties"])
    assert config["properties"]["business_available"]["const"] is False
    assert config["properties"]["live_available"]["const"] is False
    assert config["properties"]["schema_version"]["const"] == "v2.t03"
    assert set(config["properties"]["app_environment"]["enum"]) == {"development", "test", "production"}
    assert set(config["properties"]["query_role"]["enum"]) == {"demo_only", "published_readonly"}
    for schema in (config, meta):
        assert set(schema["properties"]["data_mode"]["enum"]) == {"demo", "verified"}
        assert set(schema["properties"]["model_mode"]["enum"]) == {"disabled", "mock"}
    mutated = copy.deepcopy(config)
    mutated["properties"]["business_available"] = {"type": "boolean"}
    with pytest.raises(AssertionError, match="semantic mismatch"):
        assert_schema_matches(contract, "FoundationConfig", mutated, document)


def test_refs_literals_nullable_arrays_and_nested_closed_objects():
    document = document_with(closed_object({
        "status": {"type": "string", "enum": ["unknown", "eligible"]},
        "flag": {"type": "boolean", "const": False},
        "nullable": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "nothing": {"type": "null"},
        "items": {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
        "nested": closed_object({"value": {"type": "number"}}, ["value"]),
        "reference": {"$ref": "#/components/schemas/Other"},
    }, ["status", "flag", "nullable", "nothing", "items", "nested", "reference"]))
    document["components"]["schemas"]["Other"] = closed_object({"id": {"type": "string"}}, ["id"])
    source = generator.generate_types(document)
    contract = Contract(source)
    for name, schema in document["components"]["schemas"].items():
        assert_schema_matches(contract, name, schema, document)
    contract.assert_payload("Sample", {"status": "unknown", "flag": False, "nullable": None,
                                      "nothing": None, "items": [None, "text"],
                                      "nested": {"value": 1}, "reference": {"id": "example"}})
    assert "(null | string)[]" not in source  # Named item alias stays compatible with the existing verifier.


@pytest.mark.parametrize("schema,message", [
    ({}, "missing schema type"),
    (True, "schema must be an object"),
    ({"type": "object", "properties": {}}, "additionalProperties=false"),
    ({"type": "object", "additionalProperties": {"type": "string"}}, "additionalProperties=false"),
    ({"type": "array"}, "declare its item schema"),
    ({"type": "array", "items": {}, "prefixItems": []}, "prefixItems"),
    ({"allOf": [{"type": "string"}]}, "missing schema type"),
    ({"type": "string", "not": {"const": "x"}}, "not"),
    ({"$ref": "https://example.invalid/schema"}, "local component"),
    ({"$ref": "#/components/schemas/Missing"}, "unknown schema reference"),
    ({"anyOf": []}, "at least one"),
    ({"type": "string", "enum": []}, "nonempty"),
    ({"type": "string", "const": 42}, "literal disagrees"),
    ({"const": {"value": "x"}}, "primitive literal"),
    ({"type": {}}, "schema type must be"),
    (closed_object({1: {"type": "string"}}), "malformed properties"),
    (closed_object({}, ["missing"]), "declared properties"),
])
def test_unsupported_schemas_fail_explicitly(schema, message):
    with pytest.raises(generator.UnsupportedSchema, match=message):
        generator.generate_artifacts(document_with(schema))


@pytest.mark.parametrize("mutation,message", [
    ({"requestBody": {"content": {}}}, "request bodies"),
    ({"parameters": [{"in": "header", "name": "secret", "schema": {"type": "string"}}]}, "inline query"),
    ({"parameters": {}}, "parameters must be an array"),
    ({"responses": {"200": {"content": {"text/plain": {"schema": {"type": "string"}}}}}}, "JSON responses"),
])
def test_new_unsupported_operation_shapes_are_not_silently_ignored(mutation, message):
    document = generator.load_openapi()
    document["paths"]["/config"]["get"].update(mutation)
    with pytest.raises(generator.UnsupportedSchema, match=message):
        generator.generate_artifacts(document)


@pytest.mark.parametrize("filename", ["openapi.json", "generated.ts"])
def test_check_detects_each_artifact_drift_without_writing(tmp_path, monkeypatch, capsys, filename):
    document = generator.load_openapi()
    monkeypatch.setattr(generator, "load_openapi", lambda: document)
    monkeypatch.setattr(generator, "OUTPUT_DIR", tmp_path)
    assert generator.main([]) == 0
    (tmp_path / filename).write_bytes(b"deliberately drifted\n")
    before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir()}
    assert generator.main(["--check"]) == 1
    assert filename in capsys.readouterr().err
    after = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir()}
    assert before == after


def test_check_missing_outputs_is_read_only(tmp_path, monkeypatch):
    output_dir = tmp_path / "does-not-exist"
    monkeypatch.setattr(generator, "OUTPUT_DIR", output_dir)
    assert generator.main(["--check"]) == 1
    assert not output_dir.exists()


def test_unsupported_schema_leaves_existing_artifacts_untouched(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(generator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(generator, "load_openapi", lambda: document_with({"type": "unrecognized"}))
    for filename in ("openapi.json", "generated.ts"):
        (tmp_path / filename).write_bytes(b"existing user content\n")
    assert generator.main([]) == 1
    assert "unsupported" in capsys.readouterr().err
    assert all(path.read_bytes() == b"existing user content\n" for path in tmp_path.iterdir())


def test_generator_runs_in_clean_process_without_database_models_or_network():
    probe = """
import os
import socket
import sys
def deny(*args, **kwargs):
    raise AssertionError('contract generation attempted network')
socket.socket.connect = deny
socket.socket.connect_ex = deny
socket.getaddrinfo = deny
os.environ.update({'V2_APP_ENVIRONMENT': 'invalid', 'V2_DATA_MODE': 'invalid',
                   'V2_MODEL_MODE': 'live', 'V2_DATABASE_URL': 'sqlite:///forbidden.db',
                   'DEMO_MODE': 'not-a-bool', 'MODEL_MODE': 'invalid',
                   'DATABASE_URL': 'sqlite:///forbidden.db', 'M0_MODEL_MODE': 'invalid'})
from scripts.generate_contracts import generate_artifacts, load_openapi
artifacts = generate_artifacts(load_openapi())
for name in sys.modules:
    assert not name.startswith(('sqlalchemy', 'alembic', 'services.api.app.db',
                                'services.api.app.models', 'services.api.app.seed',
                                'services.api.app.providers', 'services.api.app.main')), name
assert set(artifacts) == {'openapi.json', 'generated.ts'}
from pathlib import Path
for name, text in artifacts.items():
    assert (Path('packages/contracts/v2') / name).read_bytes() == text.encode('utf-8')
print('independent offline v2 export passed')
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", probe], cwd=generator.ROOT,
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "independent offline v2 export passed" in result.stdout
