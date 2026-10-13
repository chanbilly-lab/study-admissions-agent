"""Six selected operations; old eleven generated profiles remain frozen."""
from copy import deepcopy
from pathlib import Path
import re
import pytest
from scripts import generate_contracts as generator

FLAGS = dict(allow_identity_redirects=True, allow_profiles=True, allow_assessments=True,
    allow_plans=True, allow_revisions=True, allow_notifications=True, allow_rights=True)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def document():
    return generator.load_openapi("rights")


def test_exact_six_operations_and_unchanged_parent(document):
    parent = generator.load_openapi("notifications")
    actual = {(path, method) for path, item in document["paths"].items() for method in item}
    old = {(path, method) for path, item in parent["paths"].items() for method in item}
    assert actual - old == generator.RIGHTS_OPERATIONS and len(actual - old) == 6
    assert all(document["paths"][path] == item for path, item in parent["paths"].items())
    generated = generator.generate_artifacts(document, **FLAGS)
    assert not generator.write_or_check(generated, ROOT / "packages/contracts/v2/rights", check=True)
    assert all("\r" not in value for value in generated.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", generated["generated.ts"])


def test_current_owner_confirmation_and_security(document):
    schema = document["components"]["schemas"]["OwnerConfirmation"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(schema["required"]) == {"owner_confirmed"}
    assert schema["properties"]["owner_confirmed"]["const"] is True
    for path, method in generator.RIGHTS_OPERATIONS:
        security = document["paths"][path][method]["security"]
        expected = [{"SessionCookie": [], **({"CsrfHeader": [], "RequestOrigin": []} if method == "post" else {})}]
        assert security == expected + ([{}] if path == "/privacy/rights/context" else [])
    properties = document["components"]["schemas"]["RightsRequestData"]["properties"]
    assert properties["status"]["enum"] == ["queued", "running", "completed", "failed", "cancelled"]
    assert "online_cleanup_complete" in properties and "retained_responsibility_until" in properties


@pytest.mark.parametrize("mutation", ["extra_operation", "missing_operation", "put", "missing_body", "query_owner",
    "missing_uuid", "query_path", "idempotency_header", "missing_parent"])
def test_reject_expanded_scope_or_unbounded_input(document, mutation):
    value = deepcopy(document)
    operation = value["paths"]["/privacy/exports/{request_id}"]["get"]
    if mutation == "extra_operation":
        value["paths"]["/privacy/arbitrary-delete"] = {"post": deepcopy(value["paths"]["/privacy/deletions"]["post"])}
    elif mutation == "missing_operation":
        del value["paths"]["/privacy/rights/context"]
    elif mutation == "put":
        item = value["paths"]["/privacy/deletions"]
        item["put"] = item.pop("post")
    elif mutation == "missing_body":
        del value["paths"]["/privacy/deletions"]["post"]["requestBody"]
    elif mutation == "missing_uuid":
        operation["parameters"] = []
    elif mutation == "idempotency_header":
        operation["parameters"].append({"in": "header", "name": "Idempotency-Key", "schema": {"type": "string"}})
    elif mutation in {"query_owner", "query_path"}:
        operation["parameters"].append({"in": "query", "name": "owner" if mutation == "query_owner" else "path", "schema": {"type": "string"}})
    flags = FLAGS | ({"allow_notifications": False} if mutation == "missing_parent" else {})
    with pytest.raises(generator.UnsupportedSchema):
        generator.generate_artifacts(value, **flags)
