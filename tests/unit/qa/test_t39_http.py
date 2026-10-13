"""Closed HTTP/schema boundaries, without DB or a simulated published proof."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from starlette.requests import Request

from services.api.app.api.qa import create_qa_app, create_qa_v2_app
from services.api.app.model_gateway.schemas import GatewayError
from services.api.app.qa.http_schemas import QAAnswerData, QAContextData
from services.api.app.qa.router import parse_body, translate
from tests.unit.qa.test_t38_retrieval import fixture_bundle, NOW


def answer_data():
    bundle = fixture_bundle()
    return QAAnswerData(schema_version="v2.t39", status="answered", request=bundle.request,
        model_scope=bundle.model_scope, release_version=1, requirements_version=bundle.requirements_version,
        content_sha256=bundle.content_sha256, citations=bundle.citations, advice_codes=("REVIEW_SOURCE",),
        unknown_reasons=(), is_synthetic=True, model_mode="mock", live_available=False, generated_at=NOW)


def test_default_closed_profile_has_no_db_gateway_or_budget_initialization():
    code = """
import sys
from fastapi.testclient import TestClient
from services.api.app.api.qa import create_qa_app
with TestClient(create_qa_app()) as client:
    context=client.get('/v2/qa/context')
    assert context.status_code==200
    assert context.json()['meta']['data_mode']=='verified'
    assert context.json()['data']['disabled_reason']=='MODEL_DISABLED'
    assert client.post('/v2/qa/answers',json={}).status_code==503
assert 'sqlalchemy' not in sys.modules
assert not any(name.endswith(('.qa.service','.qa.retrieval','.model_gateway.gateway','.model_gateway.budget')) for name in sys.modules)
"""
    env = {key: value for key, value in os.environ.items() if not key.startswith("V2_") and key != "DEMO_MODE"}
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code], cwd=Path(__file__).resolve().parents[3],
        env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_closed_routes_have_safe_headers_and_do_not_expose_internal_atoms():
    with TestClient(create_qa_app()) as client:
        for method, path, status in [("get", "/v2/qa/context", 200), ("post", "/v2/qa/answers", 503),
            ("get", "/v2/qa/context?owner=PRIVATE_SECRET", 422), ("get", "/v1", 404)]:
            response = getattr(client, method)(path)
            assert response.status_code == status and response.headers["cache-control"] == "no-store"
            assert len(response.headers["x-request-id"]) == 32
            assert "PRIVATE_SECRET" not in response.text
    assert "atoms" not in answer_data().model_dump() and "claims" not in answer_data().model_dump()


@pytest.mark.parametrize("change", [{"live_available": 0}, {"release_version": True}, {"is_synthetic": 1},
    {"atoms": ()}, {"status": "unknown"}, {"model_mode": "live"}, {"content_sha256": "x" * 64}])
def test_answer_model_copy_cannot_bypass_finite_wire(change):
    with pytest.raises(ValidationError):
        QAAnswerData.model_validate(answer_data().model_copy(update=change))


def test_answer_references_match_whole_scope_and_model_identity():
    data = answer_data()
    wrong = data.request.model_copy(update={"entry_year": 2027,
        "scope": data.request.scope.model_copy(update={"entry_year": 2027})})
    with pytest.raises(ValidationError):
        QAAnswerData.model_validate(data.model_copy(update={"request": wrong}))
    citation = data.citations[0]
    from services.api.app.qa.schemas import citation_from_public
    other = citation_from_public(citation.fact, citation.evidence.model_copy(update={
        "scope": citation.scope.model_copy(update={"country": "GB"})}))
    with pytest.raises(ValidationError):
        QAAnswerData.model_validate(data.model_copy(update={"citations": (other,)}))


@pytest.mark.parametrize("code,status", [("MODEL_TIMEOUT", 503), ("INVALID_PROVIDER_RESPONSE", 503),
    ("PROVIDER_FAILURE", 503), ("BUDGET_EXHAUSTED", 429), ("KEY_LIMIT", 429), ("CONCURRENCY_LIMIT", 429)])
def test_gateway_error_mapping_is_fixed_and_safe(code, status):
    error = translate(GatewayError(code))
    assert error.status_code == status and error.details[0].code == code
    assert error.details[0].field_path == "qa"


def request_for(raw, *, content_type="application/json", headers=()):
    sent = False
    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": raw, "more_body": False}
        return {"type": "http.disconnect"}
    return Request({"type": "http", "method": "POST", "path": "/qa/answers", "query_string": b"",
        "headers": [(b"content-type", content_type.encode()), *headers]}, receive)


def test_bounded_utf8_body_is_the_original_retrieval_request():
    bundle = fixture_bundle()
    body = json.dumps(bundle.request.model_dump(mode="json")).encode()
    assert asyncio.run(parse_body(request_for(body))) == bundle.request


@pytest.mark.parametrize("body", [b'{"intent":"fees","intent":"dates"}', b'{"entry_year":NaN}',
    b" " * 16385, b"[]", b"\xff", b'{"student":{"score":600}}', b"{" * 1200])
def test_bad_json_is_rejected_with_fixed_detail_and_without_input(body):
    from services.api.app.api.v2.errors import ApiError
    with pytest.raises(ApiError) as caught:
        asyncio.run(parse_body(request_for(body)))
    assert caught.value.status_code == 422 and caught.value.details[0].code == "INVALID_RETRIEVAL_INPUT"


def test_context_rejects_numeric_closed_markers():
    valid = QAContextData(schema_version="v2.t39", can_ask=False, model_mode="disabled", live_available=False,
        real_processing_enabled=False, allow_test_fixture_read=False, demo_banner=None,
        disabled_reason="MODEL_DISABLED", budget_unit="conservative_utf8_bytes")
    with pytest.raises(ValidationError):
        QAContextData.model_validate(valid.model_copy(update={"real_processing_enabled": 0}))


def test_factory_keeps_exact_public_parent_routes():
    document = create_qa_v2_app().openapi()
    assert set(document["paths"]) == {"/config", "/offerings", "/evidence/{evidence_id}", "/qa/context", "/qa/answers"}


def test_runtime_and_service_state_replacement_cannot_change_closed_capabilities():
    for field, value in [("qa_service", object()), ("public_catalog_reader", object())]:
        app = create_qa_v2_app()
        setattr(app.state, field, value)
        with TestClient(app) as client:
            response = client.get("/qa/context")
            assert response.status_code == 503
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["error"]["details"][0]["code"] == "QA_UNAVAILABLE"
    app = create_qa_v2_app()
    app.state.runtime_settings.__dict__["data_mode"] = "demo"
    with TestClient(app) as client:
        assert client.post("/qa/answers", json={}).status_code == 503
