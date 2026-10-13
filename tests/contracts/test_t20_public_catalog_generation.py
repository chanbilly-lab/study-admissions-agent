"""Offline public profile generation and real closed HTTP wire acceptance."""

from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from scripts import generate_contracts as generator
from scripts import verify_contract as verifier
from services.api.app.api.public_catalog import create_public_catalog_app, create_public_catalog_v2_app
from services.api.app.public_catalog.schemas import PublicFactData, PublicOfferingQuery
from services.api.app.settings import V2RuntimeSettings


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "packages/contracts/v2/public_catalog"


def runtime():
    return V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
                             database_url=None, legacy_demo_mode=None, _env_file=None)


class NumericContract(verifier.Contract):
    """T20-only numeric literal bridge; the frozen M0 verifier stays unchanged."""

    def primary(self):
        if self.position < len(self.tokens) and re.fullmatch(r"[0-9]+", self.tokens[self.position]):
            return verifier.TypeExpression("literal", int(self.take()))
        return super().primary()


def contract(source, monkeypatch):
    with monkeypatch.context() as local:
        local.setattr(verifier, "TOKEN", re.compile(verifier.TOKEN.pattern + r"|[0-9]+"))
        return NumericContract(source)


def test_public_artifacts_match_are_lf_and_deterministic():
    document = generator.load_openapi("public_catalog")
    artifacts = generator.generate_artifacts(document, allow_public_catalog=True)
    assert artifacts == generator.generate_artifacts(generator.load_openapi("public_catalog"), allow_public_catalog=True)
    assert not generator.write_or_check(artifacts, OUTPUT, check=True)
    assert document["servers"] == [{"url": "/v2"}]
    assert document["info"]["version"] == "v2.t20"
    assert set(document["paths"]) == {"/config", "/offerings", "/evidence/{evidence_id}"}
    assert all(set(item) == {"get"} for item in document["paths"].values())
    assert all("\r" not in content for content in artifacts.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", artifacts["generated.ts"])
    assert "release_version: 1;" in artifacts["generated.ts"]
    for profile, redirect in (("foundation", False), ("identity", True)):
        original = generator.generate_artifacts(generator.load_openapi(profile), allow_identity_redirects=redirect)
        directory = generator.OUTPUT_DIR if profile == "foundation" else generator.OUTPUT_DIR / profile
        assert not generator.write_or_check(original, directory, check=True)


def test_every_public_component_query_path_and_response_matches_schema(monkeypatch):
    document = generator.load_openapi("public_catalog")
    declarations = contract(generator.generate_types(document, allow_public_catalog=True), monkeypatch)
    for name, schema in document["components"]["schemas"].items():
        verifier.assert_schema_matches(declarations, name, schema, document)
        assert schema.get("additionalProperties") is False
    for item in document["paths"].values():
        operation = item["get"]
        prefix = operation["operationId"][0].upper() + operation["operationId"][1:]
        parameters = operation.get("parameters", [])
        for kind, suffix in (("query", "Query"), ("path", "Path")):
            selected = [p for p in parameters if p["in"] == kind]
            if kind == "path" and not selected:
                continue
            schema = {"type": "object", "additionalProperties": False,
                      "properties": {p["name"]: p["schema"] for p in selected},
                      "required": [p["name"] for p in selected if p.get("required")]}
            verifier.assert_schema_matches(declarations, prefix + suffix, schema, document)
        for status, response in operation["responses"].items():
            verifier.assert_schema_matches(declarations, prefix + "Response" + status,
                response["content"]["application/json"]["schema"], document)


@pytest.mark.parametrize("mutation", ["no_optin", "missing_path", "wrong_path_name", "bad_uuid", "write", "unknown_schema"])
def test_generator_refuses_unselected_or_unknown_public_structure(mutation):
    document = deepcopy(generator.load_openapi("public_catalog"))
    operation = document["paths"]["/evidence/{evidence_id}"]["get"]
    path = next(p for p in operation["parameters"] if p["in"] == "path")
    if mutation == "missing_path":
        operation["parameters"].remove(path)
    elif mutation == "wrong_path_name":
        path["name"] = "file_id"
    elif mutation == "bad_uuid":
        path["schema"]["format"] = "uri"
    elif mutation == "write":
        document["paths"]["/config"]["post"] = deepcopy(document["paths"]["/config"]["get"])
    elif mutation == "unknown_schema":
        document["components"]["schemas"]["PublicFactData"]["properties"]["value_text"]["not"] = {"type": "string"}
    with pytest.raises(generator.UnsupportedSchema):
        generator.generate_artifacts(document, allow_public_catalog=mutation != "no_optin")


def test_check_is_readonly_and_drift_is_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(generator, "OUTPUT_DIR", tmp_path)
    assert generator.main(["--profile", "public_catalog", "--check"]) == 1
    assert not list(tmp_path.iterdir())
    assert generator.main(["--profile", "public_catalog"]) == 0
    generated = tmp_path / "public_catalog/generated.ts"
    generated.write_bytes(generated.read_bytes() + b"// drift\n")
    before = {p.name: p.read_bytes() for p in generated.parent.iterdir()}
    assert generator.main(["--profile", "public_catalog", "--check"]) == 1
    assert before == {p.name: p.read_bytes() for p in generated.parent.iterdir()}


def test_export_ignores_invalid_environment_and_closed_factory_imports_no_database(tmp_path):
    code = "sys.path.insert(0, " + repr(str(ROOT)) + ")\n" + """
import os,sys,socket
os.environ.update(V2_APP_ENVIRONMENT='invalid',V2_DATA_MODE='invalid',V2_MODEL_MODE='live',V2_DATABASE_URL='sqlite:///SENTINEL.db',DEMO_MODE='invalid')
def deny(*args,**kwargs): raise AssertionError('network is forbidden')
socket.create_connection=deny
from scripts.generate_contracts import load_openapi,generate_artifacts
from services.api.app.api.public_catalog import create_public_catalog_app
from services.api.app.settings import V2RuntimeSettings
settings=V2RuntimeSettings(app_environment='production',data_mode='verified',model_mode='disabled',database_url=None,legacy_demo_mode=None,_env_file=None)
create_public_catalog_app(settings)
generate_artifacts(load_openapi('public_catalog'),allow_public_catalog=True)
for prefix in ('sqlalchemy','psycopg','alembic','services.api.app.api.main','services.api.app.public_catalog.reader','services.api.app.db','services.api.app.auth.service','services.api.app.storage.local'):
 assert not any(m==prefix or m.startswith(prefix+'.') for m in sys.modules),prefix
print('public schema and closed factory are offline without persistence')
"""
    (tmp_path / ".env").write_text("V2_MODEL_MODE=live\nDEMO_MODE=invalid\n", encoding="utf-8")
    code = "import sys\n" + code
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "SENTINEL.db").exists()


@pytest.mark.parametrize("mounted", [False, True])
def test_closed_http_config_and_business_errors_match_generated_contract(mounted, monkeypatch):
    app = create_public_catalog_app(runtime()) if mounted else create_public_catalog_v2_app(runtime())
    prefix = "/v2" if mounted else ""
    schema = generator.load_openapi("public_catalog")
    declarations = contract(generator.generate_types(schema, allow_public_catalog=True), monkeypatch)
    cases = [("/config", 200, "GetV2PublicConfigResponse200"),
             ("/offerings?entry_year=2026", 503, "ListV2PublicOfferingsResponse503"),
             ("/evidence/00000000-0000-4000-8000-000000000001?release_id=00000000-0000-4000-8000-000000000002", 503, "GetV2PublicEvidenceResponse503")]
    with TestClient(app) as client:
        for path, status, declaration in cases:
            response = client.get(prefix + path, headers={"X-Request-ID": "foreign-sentinel"})
            assert response.status_code == status, response.text
            payload = response.json()
            declarations.assert_payload(declaration, payload)
            assert response.headers["cache-control"] == "no-store"
            assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
            assert (payload.get("meta") or payload["error"])["request_id"] == response.headers["x-request-id"]
            assert "foreign-sentinel" not in response.text
            if status == 200:
                assert payload["data"]["business_available"] is False
                assert payload["data"]["demo_banner"] is None


@pytest.mark.parametrize("path", [
    "/offerings", "/offerings?entry_year=2026&entry_year=2027", "/offerings?entry_year=2026&owner=SENTINEL",
    "/offerings?entry_year=2026.0", "/offerings?entry_year=0", "/offerings?entry_year=2026&country=cn",
    "/offerings?entry_year=2026&province=unknown", "/offerings?entry_year=2026&limit=101",
    "/evidence/not-a-uuid?release_id=SENTINEL", "/evidence/00000000-0000-4000-8000-000000000001",
    "/evidence/00000000-0000-4000-8000-000000000001?release_id=00000000-0000-4000-8000-000000000002&release_id=00000000-0000-4000-8000-000000000002",
])
def test_query_rejection_never_echoes_untrusted_values(path):
    with TestClient(create_public_catalog_v2_app(runtime())) as client:
        response = client.get(path)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.headers["cache-control"] == "no-store"
    assert "SENTINEL" not in response.text


def test_public_dto_allowlist_excludes_private_identifiers_and_urls():
    schemas = generator.load_openapi("public_catalog")["components"]["schemas"]
    forbidden = {"file_id", "import_id", "import_row_id", "source_id", "source_version", "document_id",
                 "owner_user_id", "user_id", "session_id", "entry_url", "storage_key", "path", "date_event_id"}
    for name, schema in schemas.items():
        assert not (set(schema.get("properties", {})) & forbidden), name
    fact = dict(fact_type="score", field_key="total", value_kind="decimal", value_text="600.00",
        normalized_value="600", unit="points", missing_reason=None, footnote_state="none", footnote_text=None,
        claim_kind="minimum_requirement", unit_code="points", period="not_applicable", statistics_basis="not_applicable",
        statistic_population=None, statistic_denominator=None, cohort_year=None, survey_period=None, evidence_id=None, date_resolution=None)
    with pytest.raises(ValueError):
        PublicFactData.model_validate({**fact, "file_id": "SENTINEL"})
    forged = PublicOfferingQuery(entry_year=2026).model_copy(update={"entry_year": True})
    with pytest.raises(ValueError):
        PublicOfferingQuery.model_validate(forged)
