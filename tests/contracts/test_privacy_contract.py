"""T08 default-closed privacy protocol; no external services or real data."""

from hashlib import sha256
from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from scripts.generate_contracts import load_openapi, generate_artifacts, UnsupportedSchema
from services.api.app.api.identity import create_identity_v2_app
from services.api.app.api.v2 import create_v2_app
from services.api.app.settings import V2RuntimeSettings


def runtime():
    return V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled",
                             database_url=None, legacy_demo_mode=None, _env_file=None)


def test_closed_notice_is_a_draft_and_does_not_invent_controller_or_ready_notice():
    with TestClient(create_identity_v2_app(runtime())) as client:
        response = client.get("/privacy/notices/current")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["readiness"] is False
    assert data["readiness_reason"] == "processing_disabled"
    assert data["notice_id"] is None and data["notice_version"] is None
    assert data["notice_hash"] == sha256(data["text"].encode("utf-8")).hexdigest()
    assert data["age_policy"]["guardian_verification_available"] is False
    assert data["age_policy"]["declaration_is_verification"] is False
    assert data["retention_policy"]["cleanup_implemented"] is False
    assert data["retention_policy"]["max_file_bytes"] == 10485760


def test_privacy_remains_outside_the_unconnected_foundation_profile():
    with TestClient(create_v2_app(runtime())) as client:
        assert client.get("/privacy/notices/current").status_code == 404
        assert client.get("/me/admission").status_code == 404
    assert set(load_openapi("foundation")["paths"]) == {"/config", "/offerings"}


def test_closed_private_settings_never_imply_authentication_and_cannot_be_cached():
    with TestClient(create_identity_v2_app(runtime())) as client:
        response = client.get("/me/admission")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-request-id"] == response.json()["error"]["request_id"]


def test_privacy_openapi_has_no_client_trust_inputs_and_preserves_write_security():
    schema = load_openapi("identity")
    components = schema["components"]["schemas"]
    assert set(components["AgeDeclarationInput"]["properties"]) == {
        "age_band", "confirmed", "notice_id", "expected_revision"}
    assert components["AgeDeclarationInput"]["additionalProperties"] is False
    assert components["CoreConsentInput"]["properties"]["purpose"]["const"] == "core_consultation"
    assert components["AdmissionData"]["properties"]["private_business_available"]["const"] is False
    assert schema["paths"]["/me/admission"]["get"]["security"] == [{"SessionCookie": []}]
    for path, method in [("/me/age-declarations", "post"), ("/me/consents", "post"),
                         ("/me/consents/{consent_id}", "delete")]:
        assert schema["paths"][path][method]["security"] == [
            {"SessionCookie": [], "CsrfHeader": [], "RequestOrigin": []}]


@pytest.mark.parametrize("mutation", ["optional", "form", "remote_ref", "extra_media", "missing_schema", "duplicate_path"])
def test_privacy_generator_rejects_unapproved_request_shapes(mutation):
    schema = deepcopy(load_openapi("identity"))
    body = schema["paths"]["/me/age-declarations"]["post"]["requestBody"]
    if mutation == "optional":
        body["required"] = False
    elif mutation == "form":
        body["content"] = {"application/x-www-form-urlencoded": body["content"]["application/json"]}
    elif mutation == "remote_ref":
        body["content"]["application/json"]["schema"] = {"$ref": "https://example.invalid/schema.json"}
    elif mutation == "extra_media":
        body["content"]["text/plain"] = {"schema": {"type": "string"}}
    elif mutation == "missing_schema":
        body["content"]["application/json"] = {}
    else:
        operation = schema["paths"]["/me/consents/{consent_id}"]["delete"]
        operation["parameters"].append(deepcopy(operation["parameters"][0]))
    with pytest.raises(UnsupportedSchema):
        generate_artifacts(schema, allow_identity_redirects=True)


def test_privacy_request_types_require_the_explicit_identity_profile():
    schema = load_openapi("identity")
    types = generate_artifacts(schema, allow_identity_redirects=True)["generated.ts"]
    assert "export type DeclareV2AgeRequestBody = AgeDeclarationInput;" in types
    assert "export type ConfirmV2CoreConsentRequestBody = CoreConsentInput;" in types
    assert "export interface WithdrawV2CoreConsentPath" in types
    with pytest.raises(UnsupportedSchema):
        generate_artifacts(schema)
