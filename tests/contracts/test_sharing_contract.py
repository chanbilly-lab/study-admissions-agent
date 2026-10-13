"""T09 closed, metadata-only HTTP and bounded generated contract checks."""

from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from scripts.generate_contracts import load_openapi, generate_artifacts, UnsupportedSchema
from services.api.app.api.identity import create_identity_v2_app
from services.api.app.api.v2 import create_v2_app
from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.grants.schemas import SharingSettings, SharedProjection
from services.api.app.settings import V2RuntimeSettings


def runtime():
    return V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
                            database_url=None, legacy_demo_mode=None, _env_file=None)


def test_default_policy_is_closed_independent_actual_text_and_bounded_metadata():
    with TestClient(create_identity_v2_app(runtime())) as client:
        response = client.get("/sharing/policy")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sharing_available"] is False
    assert data["readiness_reason"] == "disabled"
    assert data["is_synthetic"] is True
    assert data["private_business_available"] is False
    assert data["guardian_verification_available"] is False
    assert data["text_sha256"] == sha256(data["text"].encode("utf-8")).hexdigest()
    assert len(data["scope_matrix"]) == 5
    for row in data["scope_matrix"]:
        assert set(row["fields"]) == {"status", "version"}
        assert set(row["actions"]) == {"read", "list"}
    assert response.headers["cache-control"] == "no-store"


def test_sharing_profile_does_not_extend_foundation_or_unlock_fixture_in_production():
    with TestClient(create_v2_app(runtime())) as client:
        assert client.get("/sharing/policy").status_code == 404
        assert client.get("/access-grants").status_code == 404
    with pytest.raises(AuthFlowError) as error:
        create_identity_v2_app(runtime(), sharing_settings=SharingSettings(fixture_mode=True))
    assert error.value.status_code == 503
    assert set(load_openapi("foundation")["paths"]) == {"/config", "/offerings"}


@pytest.mark.parametrize("method,path", [("get", "/access-grants"),
    ("post", "/access-grants"), ("post", "/access-grants/" + str(uuid4()) + "/accept"),
    ("delete", "/access-grants/" + str(uuid4()))])
def test_closed_private_calls_are_safe_unavailable_and_nostore(method, path):
    with TestClient(create_identity_v2_app(runtime())) as client:
        response = getattr(client, method)(path)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-request-id"] == response.json()["error"]["request_id"]


def test_wire_separates_specific_confirmation_from_identity_and_cross_subject_proofs():
    schema = load_openapi("identity")
    components = schema["components"]["schemas"]
    assert components["CreateGrantInput"]["additionalProperties"] is False
    assert components["AcceptGrantInput"]["additionalProperties"] is False
    assert components["CreateGrantInput"]["properties"]["confirmed"]["const"] is True
    assert components["AcceptGrantInput"]["properties"]["confirmed"]["const"] is True
    forbidden = {"owner_user_id", "roles", "verified", "guardian_consent"}
    assert forbidden.isdisjoint(components["CreateGrantInput"]["properties"])
    assert {"owner_consent_id", "grantee_declaration_id"}.isdisjoint(components["GrantData"]["properties"])
    assert set(SharedProjection.model_fields) <= {
        "resource_id", "resource_type", "is_synthetic", "requested_fields", "status", "version"}
    for path, method in [("/access-grants", "post"),
        ("/access-grants/{grant_id}/accept", "post"), ("/access-grants/{grant_id}", "delete")]:
        assert schema["paths"][path][method]["security"] == [
            {"SessionCookie": [], "CsrfHeader": [], "RequestOrigin": []}]


@pytest.mark.parametrize("path,method", [("/access-grants", "post"),
    ("/access-grants/{grant_id}/accept", "post")])
@pytest.mark.parametrize("mutation", ["optional", "remote", "nonjson"])
def test_new_body_generator_refuses_unspecified_formats(path, method, mutation):
    schema = deepcopy(load_openapi("identity"))
    body = schema["paths"][path][method]["requestBody"]
    if mutation == "optional":
        body["required"] = False
    elif mutation == "remote":
        schema["paths"][path][method]["requestBody"] = {"$ref": "https://example.invalid/body"}
    else:
        body["content"]["text/plain"] = body["content"].pop("application/json")
    with pytest.raises(UnsupportedSchema):
        generate_artifacts(schema, allow_identity_redirects=True)


@pytest.mark.parametrize("path,method", [("/access-grants/{grant_id}", "delete"),
    ("/access-grants/{grant_id}/accept", "post")])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_name", "wrong_type", "naive", "nullschema"])
def test_new_uuid_generator_rejects_missing_or_changed_path_parameter(path, method, mutation):
    schema = deepcopy(load_openapi("identity"))
    parameters = schema["paths"][path][method]["parameters"]
    if mutation == "missing":
        parameters[:] = []
    elif mutation == "duplicate":
        parameters.append(deepcopy(parameters[0]))
    elif mutation == "wrong_name":
        parameters[0]["name"] = "owner_user_id"
    elif mutation == "wrong_type":
        parameters[0]["schema"] = {"type": "integer"}
    elif mutation == "naive":
        parameters[0]["schema"] = {"type": "string"}
    else:
        parameters[0]["schema"] = None
    with pytest.raises(UnsupportedSchema):
        generate_artifacts(schema, allow_identity_redirects=True)


def test_identity_ts_remains_bounded_without_any_and_contains_shared_aliases():
    ts = generate_artifacts(load_openapi("identity"), allow_identity_redirects=True)["generated.ts"]
    for name in ("CreateGrantInput", "AcceptGrantInput", "GrantListData"):
        assert f"export interface {name} {{" in ts
    assert ": any" not in ts


@pytest.mark.parametrize("value", ["1.0", "1e1", "", " 1", "1 ", "nan", True])
def test_grant_query_uses_integer_lexical_contract(value):
    from pydantic import ValidationError
    from services.api.app.auth.grants.router import GrantQuery
    with pytest.raises(ValidationError):
        GrantQuery.model_validate({"limit": value})


@pytest.mark.parametrize("value,expected", [("1", 1), ("100", 100)])
def test_grant_query_preserves_integer_url_values(value, expected):
    from services.api.app.auth.grants.router import GrantQuery
    assert GrantQuery.model_validate({"limit": value}).limit == expected
