"""Independent five-operation T35 boundary and preservation of old profiles."""

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
OPERATIONS = {
    ("/plan-revisions/context", "get"),
    ("/plan-revisions/history/{plan_id}", "get"),
    ("/plan-revisions", "post"),
    ("/plan-revisions/{revision_id}", "get"),
    ("/plan-revisions/{revision_id}/decision", "post"),
}
FLAGS = dict(allow_identity_redirects=True, allow_profiles=True,
    allow_assessments=True, allow_plans=True, allow_revisions=True)


def artifacts(document=None, **changes):
    return generator.generate_artifacts(document or generator.load_openapi("revisions"), **(FLAGS | changes))


class RevisionContract(verifier.Contract):
    """An isolated extension for the existing bounded literal versions 1 and 2."""
    def __init__(self, source):
        token = re.compile(verifier.TOKEN.pattern + r"|[12](?![\w.])", verifier.TOKEN.flags)
        with patch.object(verifier, "TOKEN", token):
            super().__init__(source)

    def primary(self):
        if self.position < len(self.tokens) and self.tokens[self.position] in {"1", "2"}:
            return verifier.TypeExpression("literal", int(self.take()))
        return super().primary()


def test_exact_new_routes_are_deterministic_and_lf_without_unbounded_types():
    document = generator.load_openapi("revisions")
    previous = (generator.PROFILES_PARENT_OPERATIONS | generator.PROFILES_OPERATIONS |
        generator.ASSESSMENTS_OPERATIONS | generator.PLANS_OPERATIONS)
    actual = {(path, method) for path, methods in document["paths"].items() for method in methods}
    assert actual == previous | OPERATIONS
    assert len(OPERATIONS) == 5
    generated = artifacts(document)
    assert generated == artifacts()
    assert not generator.write_or_check(generated, ROOT / "packages/contracts/v2/revisions", check=True)
    assert all("\r" not in item for item in generated.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", generated["generated.ts"])
    assert document["servers"] == [{"url": "/v2"}]
    matches = list(re.finditer(r"export (?:interface|type) ([A-Za-z_$][\w$]*)", generated["generated.ts"]))
    declarations = {match[1]: generated["generated.ts"][match.start():
        matches[index+1].start() if index+1 < len(matches) else len(generated["generated.ts"])]
        for index, match in enumerate(matches)}
    pending = set()
    for path, method in OPERATIONS:
        operation = document["paths"][path][method]["operationId"]
        prefix = operation[0].upper()+operation[1:]
        pending |= {name for name in declarations if name.startswith(prefix)}
    selected = set()
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected.add(name)
        pending |= set(re.findall(r"\b[A-Za-z_$][\w$]*\b", declarations[name])) & declarations.keys() - selected
    contract = RevisionContract("\n".join(declarations[name] for name in sorted(selected)))
    assert {"RevisionData", "RevisionHistoryData", "ProposeInput", "DecisionInput"} <= selected
    for name in selected & document["components"]["schemas"].keys():
        verifier.assert_schema_matches(contract, name, document["components"]["schemas"][name], document)


@pytest.mark.parametrize("mutation", ["extra", "missing", "put", "no_body", "query_owner",
    "missing_uuid", "string_uuid", "optional_uuid", "unbounded_integer", "idempotency_header", "no_parent"])
def test_new_profile_rejects_route_parameter_and_security_expansion(mutation):
    document = deepcopy(generator.load_openapi("revisions"))
    route = document["paths"]["/plan-revisions/{revision_id}/decision"]["post"]
    if mutation == "extra":
        document["paths"]["/plan-revisions/list"] = {"get": deepcopy(document["paths"]["/plan-revisions/context"]["get"])}
    elif mutation == "missing":
        del document["paths"]["/plan-revisions/history/{plan_id}"]
    elif mutation == "put":
        item = document["paths"]["/plan-revisions"]
        item["put"] = item.pop("post")
    elif mutation == "no_body":
        del route["requestBody"]
    elif mutation == "query_owner":
        route["parameters"].append({"in": "query", "name": "owner", "schema": {"type": "string"}})
    elif mutation == "idempotency_header":
        route["parameters"].append({"in": "header", "name": "Idempotency-Key", "required": True,
            "schema": {"type": "string"}})
    elif mutation == "no_parent":
        with pytest.raises(generator.UnsupportedSchema):
            artifacts(document, allow_plans=False)
        return
    else:
        parameter = next(item for item in route["parameters"] if item["name"] == "revision_id")
        if mutation == "missing_uuid":
            route["parameters"].remove(parameter)
        elif mutation == "string_uuid":
            parameter["schema"] = {"type": "string"}
        elif mutation == "optional_uuid":
            parameter["required"] = False
        else:
            parameter["schema"] = {"type": "integer"}
    with pytest.raises(generator.UnsupportedSchema):
        artifacts(document)


def test_body_fields_and_cookie_csrf_origin_do_not_allow_client_authority():
    document = generator.load_openapi("revisions")
    components = document["components"]["schemas"]
    for model, fields in {
        "ProposeInput": {"old_plan_id", "new_plan_id", "expected_old_state_version", "expected_new_state_version", "student_confirmed"},
        "DecisionInput": {"expected_revision_version", "action", "student_confirmed"},
    }.items():
        assert set(components[model]["properties"]) == set(components[model]["required"]) == fields
        assert components[model]["additionalProperties"] is False
        assert components[model]["properties"]["student_confirmed"]["const"] is True
    for path, method in OPERATIONS:
        operation = document["paths"][path][method]
        assert operation["security"] == [{"SessionCookie": [], **(
            {"CsrfHeader": [], "RequestOrigin": []} if method == "post" else {})}]
        assert not any(p["in"] in {"query", "header"} for p in operation.get("parameters", []))


def test_all_eight_previous_generated_profiles_remain_identical():
    profiles = {"foundation": {}, "identity": {"allow_identity_redirects": True},
        "public_catalog": {"allow_public_catalog": True},
        "admin": {"allow_identity_redirects": True, "allow_admin": True},
        "admin_review": {"allow_identity_redirects": True, "allow_admin": True, "allow_admin_review": True},
        "profiles": {"allow_identity_redirects": True, "allow_profiles": True},
        "assessments": {"allow_identity_redirects": True, "allow_profiles": True, "allow_assessments": True},
        "plans": {"allow_identity_redirects": True, "allow_profiles": True, "allow_assessments": True, "allow_plans": True}}
    for name, flags in profiles.items():
        directory = ROOT / "packages/contracts/v2" / ("" if name == "foundation" else name)
        old = {file: (directory / file).read_bytes() for file in ("openapi.json", "generated.ts")}
        generated = generator.generate_artifacts(generator.load_openapi(name), **flags)
        assert all(old[file] == value.encode("utf-8") for file, value in generated.items()), name


def test_disabled_factory_returns_only_safe_closed_errors_without_domain_io():
    from fastapi.testclient import TestClient
    from services.api.app.api.revisions import create_revisions_app, create_revisions_v2_app
    from services.api.app.settings import V2RuntimeSettings

    runtime = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    with TestClient(create_revisions_v2_app(runtime)) as client:
        for path, method in OPERATIONS:
            actual = path.replace("{plan_id}", "00000000-0000-0000-0000-000000000001").replace(
                "{revision_id}", "00000000-0000-0000-0000-000000000002")
            response = client.request(method, actual, **({"json": {"private": "DEMO_PRIVATE_SENTINEL"}} if method == "post" else {}))
            assert response.status_code == 503
            assert "DEMO_PRIVATE_SENTINEL" not in response.text
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["pragma"] == "no-cache"
            assert response.headers["referrer-policy"] == "no-referrer"
            assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
        assert client.get("/config").status_code == 200
    with TestClient(create_revisions_app(runtime)) as client:
        assert client.get("/v1/profiles").status_code == 404
        assert client.get("/v2/plan-revisions/context").status_code == 503


def test_fresh_contract_export_never_imports_persistence_or_opens_network(tmp_path):
    source = "import sys,socket\nsys.path.insert(0,"+repr(str(ROOT))+")\n"+"""
def deny(*args,**kwargs): raise AssertionError('unexpected connection')
socket.create_connection=deny
from scripts.generate_contracts import load_openapi,generate_artifacts
generate_artifacts(load_openapi('revisions'),allow_identity_redirects=True,allow_profiles=True,allow_assessments=True,allow_plans=True,allow_revisions=True)
for prefix in ('sqlalchemy','psycopg','alembic','services.api.app.plan_revisions.service','services.api.app.main'):
 assert not any(n==prefix or n.startswith(prefix+'.') for n in sys.modules),prefix
print('T35 offline contract only')
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", source], cwd=tmp_path,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
