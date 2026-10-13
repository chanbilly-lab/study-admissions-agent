"""T32 exact operation/shape export with the seven previous profiles preserved."""

from copy import deepcopy
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch

import pytest

from scripts import generate_contracts as generator
from scripts import verify_contract as verifier


ROOT = Path(__file__).resolve().parents[2]
FLAGS = dict(allow_identity_redirects=True, allow_profiles=True, allow_assessments=True, allow_plans=True)


class PlansContract(verifier.Contract):
    """Keep the original parser frozen; support its existing T28 literal 1."""
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
    return generator.generate_artifacts(document or generator.load_openapi("plans"), **(FLAGS | overrides))


def selected_contract(document):
    source = artifacts(document)["generated.ts"]
    matches = list(re.finditer(r"export (?:interface|type) ([A-Za-z_$][\w$]*)", source))
    declarations = {m[1]: source[m.start():matches[i + 1].start() if i + 1 < len(matches) else len(source)]
                    for i, m in enumerate(matches)}
    pending = set()
    for path, method in generator.PLANS_OPERATIONS:
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
    return PlansContract("\n".join(declarations[name] for name in sorted(selected))), selected


def test_actual_artifacts_are_deterministic_complete_and_lf():
    document = generator.load_openapi("plans")
    generated = artifacts(document)
    assert generated == artifacts()
    assert not generator.write_or_check(generated, ROOT / "packages/contracts/v2/plans", check=True)
    actual = {(path, method) for path, item in document["paths"].items() for method in item}
    assert actual == generator.PROFILES_PARENT_OPERATIONS | generator.PROFILES_OPERATIONS | generator.ASSESSMENTS_OPERATIONS | generator.PLANS_OPERATIONS
    assert len({path for path, _ in generator.PLANS_OPERATIONS}) == 7
    assert len(generator.PLANS_OPERATIONS) == 8
    assert document["servers"] == [{"url": "/v2"}]
    assert "create_plans_v2_app()" in generated["generated.ts"]
    assert all("\r" not in value for value in generated.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", generated["generated.ts"])


def test_all_plan_component_shapes_match_generated_types():
    document = generator.load_openapi("plans")
    contract, selected = selected_contract(document)
    for name in selected & document["components"]["schemas"].keys():
        verifier.assert_schema_matches(contract, name, document["components"]["schemas"][name], document)


def test_seven_previous_profiles_still_match_their_exact_saved_bytes():
    profiles = {"foundation": {}, "identity": {"allow_identity_redirects": True},
        "public_catalog": {"allow_public_catalog": True},
        "admin": {"allow_identity_redirects": True, "allow_admin": True},
        "admin_review": {"allow_identity_redirects": True, "allow_admin": True, "allow_admin_review": True},
        "profiles": {"allow_identity_redirects": True, "allow_profiles": True},
        "assessments": {"allow_identity_redirects": True, "allow_profiles": True, "allow_assessments": True}}
    for name, flags in profiles.items():
        output = ROOT / "packages/contracts/v2" / ("" if name == "foundation" else name)
        old = {path: (output / path).read_bytes() for path in ("openapi.json", "generated.ts")}
        generated = generator.generate_artifacts(generator.load_openapi(name), **flags)
        assert all(old[path] == value.encode("utf-8") for path, value in generated.items()), name


@pytest.mark.parametrize("mutation", ["extra", "missing", "put", "no_body", "query", "no_uuid",
    "task_as_uuid", "unbounded_version", "unbounded_list", "no_header", "extra_header", "header_on_complete", "no_parent", "wrong_flags"])
def test_new_profile_cannot_expand_operation_or_parameter_whitelist(mutation):
    document = deepcopy(generator.load_openapi("plans"))
    confirm = document["paths"]["/plans/{plan_id}/confirm"]["post"]
    complete = document["paths"]["/plans/{plan_id}/tasks/{task_key}/complete"]["post"]
    if mutation == "extra":
        document["paths"]["/plans/arbitrary"] = {"get": deepcopy(document["paths"]["/plans/context"]["get"])}
    elif mutation == "missing":
        del document["paths"]["/plans/context"]
    elif mutation == "put":
        document["paths"]["/plans/{plan_id}/workspace"]["put"] = document["paths"]["/plans/{plan_id}/workspace"].pop("post")
    elif mutation == "no_body":
        del document["paths"]["/plans/{plan_id}/workspace"]["post"]["requestBody"]
    elif mutation == "query":
        confirm["parameters"].append({"in": "query", "name": "owner", "schema": {"type": "string"}})
    elif mutation == "no_uuid":
        confirm["parameters"] = [p for p in confirm["parameters"] if p.get("name") != "plan_id"]
    elif mutation == "task_as_uuid":
        next(p for p in complete["parameters"] if p["name"] == "task_key")["schema"] = {"type": "string", "format": "uuid"}
    elif mutation == "unbounded_version":
        history = document["paths"]["/plans/{plan_id}/versions/{state_version}"]["get"]
        next(p for p in history["parameters"] if p["name"] == "state_version")["schema"] = {"type": "integer"}
    elif mutation == "unbounded_list":
        document["paths"]["/plans"]["get"]["parameters"][0]["schema"]["maximum"] = 100000
    elif mutation == "no_header":
        confirm["parameters"] = [p for p in confirm["parameters"] if p.get("in") != "header"]
    elif mutation == "extra_header":
        confirm["parameters"].append({"in": "header", "name": "owner", "schema": {"type": "string"}})
    elif mutation == "header_on_complete":
        complete["parameters"].append(deepcopy(next(p for p in confirm["parameters"] if p.get("in") == "header")))
    else:
        with pytest.raises(generator.UnsupportedSchema):
            artifacts(document, **({"allow_plans": False} if mutation == "no_parent" else {"allow_assessments": False}))
        return
    with pytest.raises(generator.UnsupportedSchema):
        artifacts(document)


def test_exact_wire_body_and_security_schema():
    document = generator.load_openapi("plans")
    schemas = document["components"]["schemas"]
    assert schemas["HttpWorkspaceInput"]["additionalProperties"] is False
    assert set(schemas["HttpWorkspaceInput"]["required"]) == {"expected_version", "estimate_overrides", "schedule"}
    for model, fields in {"HttpScheduleConfiguration": ("horizon_start", "horizon_end"),
                          "HttpAvailabilitySlot": ("start_at", "end_at"), "HttpInternalGoal": ("due_at",)}.items():
        for field in fields:
            assert schemas[model]["properties"][field]["format"] == "date-time"
            assert schemas[model]["properties"][field]["pattern"].endswith(r"(?:Z|\+00:00)$")
    for path, method in generator.PLANS_OPERATIONS:
        security = document["paths"][path][method]["security"]
        assert security == [{"SessionCookie": [], **({"CsrfHeader": [], "RequestOrigin": []} if method == "post" else {})}]


def test_default_closed_child_and_parent_keep_safe_private_errors():
    from fastapi.testclient import TestClient
    from services.api.app.api.plans import create_plans_app, create_plans_v2_app
    from services.api.app.settings import V2RuntimeSettings

    runtime = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    document = generator.load_openapi("plans")
    contract, _ = selected_contract(document)
    with TestClient(create_plans_v2_app(runtime)) as client:
        for path, method in generator.PLANS_OPERATIONS:
            actual = path.replace("{plan_id}", "00000000-0000-0000-0000-000000000001").replace("{state_version}", "1").replace("{task_key}", "a" * 64)
            response = client.request(method, actual, **({"json": {"private_sentinel": "secret"}} if method == "post" else {}))
            assert response.status_code == 503
            operation = document["paths"][path][method]["operationId"]
            contract.assert_payload(operation[0].upper() + operation[1:] + "Response503", response.json())
            assert "secret" not in response.text
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["pragma"] == "no-cache"
            assert response.headers["referrer-policy"] == "no-referrer"
            assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
        assert client.get("/config").status_code == 200
        assert client.get("/openapi.json").status_code == 200
    with TestClient(create_plans_app(runtime)) as client:
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/v2/plans/context").status_code == 503


def test_export_and_closed_factory_do_not_import_domain_io_in_fresh_process(tmp_path):
    code = "import sys\nsys.path.insert(0," + repr(str(ROOT)) + ")\n" + """
import os,socket
os.environ.update(V2_APP_ENVIRONMENT='invalid',V2_DATA_MODE='invalid',V2_MODEL_MODE='live',DEMO_MODE='invalid')
def deny(*args,**kwargs): raise AssertionError('unexpected network/database access')
socket.create_connection=deny
from scripts.generate_contracts import load_openapi,generate_artifacts
from services.api.app.api.plans import create_plans_app,create_plans_v2_app
from services.api.app.settings import V2RuntimeSettings
settings=V2RuntimeSettings(app_environment='production',data_mode='verified',model_mode='disabled',database_url=None,legacy_demo_mode=None,_env_file=None)
create_plans_app(settings);create_plans_v2_app(settings)
generate_artifacts(load_openapi('plans'),allow_identity_redirects=True,allow_profiles=True,allow_assessments=True,allow_plans=True)
for prefix in ('sqlalchemy','psycopg','alembic','joserfc','services.api.app.auth.service','services.api.app.storage.local','services.api.app.plan_execution.service','services.api.app.main'):
 assert not any(name==prefix or name.startswith(prefix+'.') for name in sys.modules),prefix
print('closed plans export: no persistence/JOSE/network')
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code], cwd=tmp_path,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_check_mode_is_read_only_and_detects_independent_drift(tmp_path):
    expected = artifacts()
    generator.write_or_check(expected, tmp_path, check=False)
    for name in expected:
        path = tmp_path / name
        path.write_bytes(path.read_bytes() + b"\n")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert set(generator.write_or_check(expected, tmp_path, check=True)) == set(expected)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
