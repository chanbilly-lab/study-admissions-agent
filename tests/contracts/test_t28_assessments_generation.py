"""Independent T28 operation whitelist and actual schema/TS shape checks."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4

import pytest

from scripts import generate_contracts as generator
from scripts import verify_contract as verifier
from scripts.verify_contract import Contract, assert_schema_matches


ROOT = Path(__file__).resolve().parents[2]
FLAGS = dict(allow_identity_redirects=True, allow_profiles=True, allow_assessments=True)


class AssessmentContract(Contract):
    """Add the single new exact integer literal; leave the frozen M0 parser alone."""

    def __init__(self, source):
        token = re.compile(verifier.TOKEN.pattern + r"|1(?![\w.])", verifier.TOKEN.flags)
        with patch.object(verifier, "TOKEN", token):
            super().__init__(source)

    def primary(self):
        if self.position < len(self.tokens) and self.tokens[self.position] == "1":
            self.take()
            return verifier.TypeExpression("literal", 1)
        return super().primary()


def artifacts(document=None, **overrides):
    return generator.generate_artifacts(document or generator.load_openapi("assessments"),
        **(FLAGS | overrides))


def selected_contract(document):
    source = artifacts(document)["generated.ts"]
    matches = list(re.finditer(r"export (?:interface|type) ([A-Za-z_$][\w$]*)", source))
    declarations = {m[1]: source[m.start():matches[i + 1].start() if i + 1 < len(matches) else len(source)]
                    for i, m in enumerate(matches)}
    pending = set()
    for path, method in generator.ASSESSMENTS_OPERATIONS:
        operation = document["paths"][path][method]["operationId"]
        prefix = operation[0].upper() + operation[1:]
        pending |= {name for name in declarations if name.startswith(prefix)}
    selected = set()
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected.add(name)
        pending |= set(re.findall(r"\b[A-Za-z_$][\w$]*\b", declarations[name])) & declarations.keys() - selected
    assert selected
    return AssessmentContract("\n".join(declarations[name] for name in sorted(selected))), selected


def test_deterministic_assessment_artifacts_and_complete_operation_set():
    document = generator.load_openapi("assessments")
    generated = artifacts(document)
    assert generated == artifacts()
    assert not generator.write_or_check(generated, ROOT / "packages/contracts/v2/assessments", check=True)
    actual = {(path, method) for path, item in document["paths"].items() for method in item}
    assert actual == generator.PROFILES_PARENT_OPERATIONS | generator.PROFILES_OPERATIONS | generator.ASSESSMENTS_OPERATIONS
    assert document["servers"] == [{"url": "/v2"}]
    assert "create_assessments_v2_app()" in generated["generated.ts"]
    assert all("\r" not in value for value in generated.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", generated["generated.ts"])


def test_all_new_wire_component_shapes_agree_with_generated_types():
    document = generator.load_openapi("assessments")
    contract, selected = selected_contract(document)
    for name in selected & document["components"]["schemas"].keys():
        assert_schema_matches(contract, name, document["components"]["schemas"][name], document)


@pytest.mark.parametrize("mutation", ["extra", "missing", "query", "no_body", "no_replay_body", "no_uuid", "parent_only"])
def test_selected_profile_never_expands_an_unrelated_operation(mutation):
    document = deepcopy(generator.load_openapi("assessments"))
    write = document["paths"]["/eligibility/evaluations"]["post"]
    if mutation == "extra":
        document["paths"]["/arbitrary"] = {"get": deepcopy(document["paths"]["/config"]["get"])}
    elif mutation == "missing":
        del document["paths"]["/eligibility/context"]
    elif mutation == "query":
        write["parameters"] = [{"in": "query", "name": "owner", "schema": {"type": "string"}}]
    elif mutation == "no_body":
        del write["requestBody"]
    elif mutation == "no_replay_body":
        del document["paths"]["/eligibility/evaluations/{assessment_id}/replay"]["post"]["requestBody"]
    elif mutation == "no_uuid":
        document["paths"]["/eligibility/evaluations/{assessment_id}"]["get"]["parameters"] = []
    else:
        with pytest.raises(generator.UnsupportedSchema):
            artifacts(document, allow_assessments=False)
        return
    with pytest.raises(generator.UnsupportedSchema):
        artifacts(document)


def test_assessment_flag_requires_explicit_profiles_and_identity_selection():
    with pytest.raises(generator.UnsupportedSchema):
        artifacts(allow_profiles=False)
    with pytest.raises(generator.UnsupportedSchema):
        artifacts(allow_identity_redirects=False)
    with pytest.raises(generator.UnsupportedSchema):
        artifacts(allow_public_catalog=True)


def test_exact_initial_version_does_not_allow_boolean_or_general_number():
    contract = AssessmentContract("export interface Version { version: 1; }")
    contract.assert_payload("Version", {"version": 1})
    for value in (True, False, 0, 2, "1", None, 1.0):
        with pytest.raises(verifier.ContractMismatch):
            contract.assert_payload("Version", {"version": value})


def test_default_closed_http_returns_bounded_error_and_no_store():
    from fastapi.testclient import TestClient
    from services.api.app.api.assessments import create_assessments_app, create_assessments_v2_app
    from services.api.app.settings import V2RuntimeSettings

    runtime = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    document = generator.load_openapi("assessments")
    contract, _ = selected_contract(document)
    operation = document["paths"]["/eligibility/context"]["get"]["operationId"]
    prefix = operation[0].upper() + operation[1:]
    with TestClient(create_assessments_v2_app(runtime)) as client:
        response = client.get("/eligibility/context")
        assert response.status_code == 503
        contract.assert_payload(prefix + "Response503", response.json())
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert client.get("/config").status_code == 200
    with TestClient(create_assessments_app(runtime)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/v2/eligibility/context").status_code == 503


def test_closed_factory_and_exporter_have_no_persistence_or_network_imports(tmp_path):
    code = "import sys\nsys.path.insert(0," + repr(str(ROOT)) + ")\n" + """
import os,socket
os.environ.update(V2_APP_ENVIRONMENT='invalid',V2_DATA_MODE='invalid',V2_MODEL_MODE='live',DEMO_MODE='invalid')
def deny(*args,**kwargs): raise AssertionError('unexpected network/database access')
socket.create_connection=deny
from scripts.generate_contracts import load_openapi,generate_artifacts
from services.api.app.api.assessments import create_assessments_app,create_assessments_v2_app
from services.api.app.settings import V2RuntimeSettings
settings=V2RuntimeSettings(app_environment='production',data_mode='verified',model_mode='disabled',database_url=None,legacy_demo_mode=None,_env_file=None)
create_assessments_app(settings);create_assessments_v2_app(settings)
generate_artifacts(load_openapi('assessments'),allow_identity_redirects=True,allow_profiles=True,allow_assessments=True)
for prefix in ('sqlalchemy','psycopg','alembic','joserfc','services.api.app.auth.service','services.api.app.storage.local','services.api.app.main'):
 assert not any(name==prefix or name.startswith(prefix+'.') for name in sys.modules),prefix
print('closed assessments export: no persistence/JOSE/network')
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code], cwd=tmp_path,
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_actual_assessment_envelope_binds_profile_metadata_and_rejects_mismatches():
    from pydantic import ValidationError
    from starlette.requests import Request
    from services.api.app.api.assessments import create_assessments_v2_app
    from services.api.app.rules.router import _response
    from services.api.app.rules.schemas import AssessmentData, AssessmentEnvelope
    from services.api.app.settings import V2RuntimeSettings

    runtime = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    app = create_assessments_v2_app(runtime)
    request = Request({"type": "http", "method": "GET", "path": "/eligibility/evaluations/unused",
        "headers": [], "app": app})
    at = datetime(2026, 10, 3, 12, 0, 0, 123456, tzinfo=timezone.utc)
    unknown = {"status": "unknown", "reason": "DATA_UNAVAILABLE"}
    value = AssessmentData.model_validate({
        "assessment_id": uuid4(), "version": 1, "profile_id": uuid4(), "profile_version_id": uuid4(),
        "profile_version": 1, "profile_sha256": "a" * 64,
        "target": {"dataset_id": uuid4(), "institution_id": uuid4(), "program_id": uuid4(),
            "offering_id": uuid4(), "offering_version": 1, "country": "CN", "scope_sha256": "b" * 64},
        "release_id": uuid4(), "requirements_version": "c" * 64, "ruleset_version": None,
        "stage": "application", "assessment_at": at, "expires_at": at + timedelta(days=1),
        "engine_version": "T28_v1", "binding_mode": "unavailable", "profile_is_synthetic": True,
        "catalogue_is_synthetic": True, "eligibility": {"status": "unknown", "reason": "RULESET_UNAVAILABLE",
            "evaluation": None, "obligations": []}, "competition_context": unknown,
        "preference_fit": unknown, "data_quality": unknown, "rule_refs": [],
        "result_sha256": "d" * 64, "current_validity": "unavailable", "replayed": False,
    })
    envelope = _response(request, value)
    assert envelope.meta.profile_version_id == value.profile_version_id
    assert envelope.meta.profile_mode == "synthetic"
    document = generator.load_openapi("assessments")
    contract, _ = selected_contract(document)
    contract.assert_payload("EvaluateV2EligibilityResponse200", envelope.model_dump(mode="json"))
    for changes in ({"profile_version_id": uuid4()}, {"profile_mode": "real"},
                    {"profile_version_id": None, "profile_mode": None}):
        meta = envelope.meta.model_copy(update=changes)
        with pytest.raises(ValidationError):
            AssessmentEnvelope(data=value, meta=meta)
