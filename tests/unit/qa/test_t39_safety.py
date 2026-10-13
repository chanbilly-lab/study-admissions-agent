"""Independent T39 entry boundaries; these tests establish no current facts."""

import os
import socket

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy.engine import Engine

from services.api.app.model_gateway.budget import BudgetLedger
from services.api.app.model_gateway.provider import OfflineMock
from services.api.app.settings import V2RuntimeSettings
from tests.unit.qa.test_t38_safety import request


SENTINEL = "DEMO_T39_PRIVATE_INPUT_SENTINEL"


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("V2_", "QA_", "MODEL_")) or name in {
            "DEMO_MODE", "DATABASE_URL", "OPENAI_API_KEY", "LLM_API_KEY"}:
            monkeypatch.delenv(name, raising=False)
    for method in ("connect", "connect_ex"):
        original = getattr(socket.socket, method)
        def guarded(sock, address, original=original):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("T39 pure HTTP tests forbid external connections")
        monkeypatch.setattr(socket.socket, method, guarded)
    def no_dns(*args, **kwargs):
        raise AssertionError("T39 pure HTTP tests forbid DNS")
    monkeypatch.setattr(socket, "getaddrinfo", no_dns)


def safe_response(response, status):
    assert response.status_code == status
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    identifier = response.headers["X-Request-ID"]
    assert len(identifier) == 32 and identifier != SENTINEL
    assert body.get("meta", body.get("error"))["request_id"] == identifier
    assert SENTINEL not in response.text
    return body


def test_default_closed_context_and_answers_never_initialize_provider_or_touch_database_and_quota(monkeypatch):
    from services.api.app.api.qa import create_qa_app
    hits = []
    def forbidden(*args, **kwargs):
        hits.append(True)
        raise AssertionError("Closed QA entry performed IO")
    async def no_provider(*args, **kwargs):
        hits.append(True)
        raise AssertionError("Closed QA entry called a provider")
    monkeypatch.setattr(Engine, "connect", forbidden)
    monkeypatch.setattr(Engine, "raw_connection", forbidden)
    monkeypatch.setattr(BudgetLedger, "reserve", forbidden)
    monkeypatch.setattr(BudgetLedger, "snapshot", forbidden)
    monkeypatch.setattr(BudgetLedger, "_window", forbidden)
    monkeypatch.setattr(OfflineMock, "complete", no_provider)
    with TestClient(create_qa_app(), base_url="https://qa.test.invalid") as browser:
        context = safe_response(browser.get("/v2/qa/context", headers={"X-Request-ID": SENTINEL}), 200)
        assert context["meta"]["data_mode"] == "verified"
        assert context["meta"]["model_mode"] == "disabled"
        data = context["data"]
        assert data["schema_version"] == "v2.t39" and data["can_ask"] is False
        assert data["model_mode"] == "disabled" and data["disabled_reason"] == "MODEL_DISABLED"
        assert data["live_available"] is data["real_processing_enabled"] is False
        assert data["budget_unit"] == "conservative_utf8_bytes"
        assert data["demo_banner"] is None
        refused = safe_response(browser.post("/v2/qa/answers", json=request().model_dump(mode="json")), 503)
        assert "MODEL_DISABLED" in str(refused["error"]["details"])
    assert hits == []


@pytest.mark.parametrize("environment,data_mode,model_mode", [
    ("production", "demo", "mock"), ("production", "verified", "mock"),
    ("test", "verified", "mock"), ("test", "demo", "live"),
    ("production", "verified", "live"),
])
def test_constructed_or_copied_startup_modes_cannot_bypass_no_live_no_production_mock(environment, data_mode, model_mode):
    from services.api.app.api.qa import create_qa_app, create_qa_v2_app
    baseline = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled", _env_file=None)
    fields = dict(app_environment=environment, data_mode=data_mode, model_mode=model_mode)
    for forged in (baseline.model_copy(update=fields),
            V2RuntimeSettings.model_construct(**{**baseline.model_dump(), **fields})):
        for factory in (create_qa_app, create_qa_v2_app):
            with pytest.raises((ValueError, ValidationError)):
                factory(forged)


def test_disabled_demo_entry_does_not_supply_an_old_demo_answer_and_unrelated_routes_stay_closed():
    from services.api.app.api.qa import create_qa_app
    settings = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled", _env_file=None)
    with TestClient(create_qa_app(settings), base_url="https://qa.test.invalid") as browser:
        context = safe_response(browser.get("/v2/qa/context"), 200)["data"]
        assert context["can_ask"] is False and context["model_mode"] == "disabled"
        answer = safe_response(browser.post("/v2/qa/answers", json=request().model_dump(mode="json")), 503)
        assert "data" not in answer and "citations" not in str(answer["error"])
        assert browser.get("/v1").status_code == 404
        for path in ("/v2/profiles", "/v2/admin/sources", "/v2/openapi.json"):
            safe_response(browser.get(path), 404)


def answer_data():
    from services.api.app.qa.http_schemas import QAAnswerData
    from tests.unit.qa.test_t38_safety import bundle
    current = bundle()
    return QAAnswerData(schema_version="v2.t39", status="answered", request=current.request,
        model_scope=current.model_scope, release_version=current.release_version,
        requirements_version=current.requirements_version, content_sha256=current.content_sha256,
        citations=current.citations, advice_codes=("REVIEW_SOURCE",), unknown_reasons=(),
        is_synthetic=True, model_mode="mock", live_available=False, generated_at=current.retrieved_at)


@pytest.mark.parametrize("changes", [
    {"live_available": 0}, {"live_available": True}, {"model_mode": "live"},
    {"schema_version": "v2.t38"}, {"is_synthetic": False}, {"release_version": True},
    {"requirements_version": "b" * 64}, {"status": "unknown"}, {"citations": ()},
    {"advice_codes": ("READ_PRIVATE_PROFILE",)}, {"unknown_reasons": ("SQL_FAILURE",)},
    {"atoms": ()}, {"free_answer": SENTINEL}, {"owner_user_id": SENTINEL},
])
def test_copied_or_constructed_answer_cannot_add_capabilities_private_text_or_detach_public_pins(changes):
    from services.api.app.qa.http_schemas import QAAnswerData
    original = answer_data()
    assert QAAnswerData.model_validate(original) == original
    with pytest.raises(ValidationError):
        QAAnswerData.model_validate(original.model_copy(update=changes))
    constructed = QAAnswerData.model_construct(**{**original.model_dump(), **changes})
    if set(changes).issubset(QAAnswerData.model_fields):
        with pytest.raises(ValidationError):
            QAAnswerData.model_validate(constructed)
    else:
        # Pydantic model_construct discards unknown keys when extra=forbid;
        # it has no extra field left to reject or return. Raw wire extras and
        # retained model_copy extras above still must be rejected.
        normalized = QAAnswerData.model_validate(constructed)
        assert not set(changes).intersection(normalized.model_dump())


def test_answer_requires_complete_exact_scope_even_when_a_citation_has_a_valid_self_hash():
    from services.api.app.qa.http_schemas import QAAnswerData
    from services.api.app.admissions_catalog.schemas import ScopeKey
    original = answer_data()
    for field in ("province", "campus", "course", "applicant_category"):
        changed = original.request.scope.model_copy(update={field: ScopeKey(status="known", value="DEMO_OTHER")})
        forged = original.model_copy(update={"request": original.request.model_copy(update={"scope": changed})})
        with pytest.raises(ValidationError):
            QAAnswerData.model_validate(forged)
    for name in ("release_id", "offering_id"):
        from uuid import uuid4
        forged = original.model_copy(update={"request": original.request.model_copy(update={name: uuid4()})})
        with pytest.raises(ValidationError):
            QAAnswerData.model_validate(forged)


@pytest.mark.parametrize("changes", [
    {"live_available": 0}, {"real_processing_enabled": 0}, {"can_ask": True},
    {"disabled_reason": None}, {"allow_test_fixture_read": True}, {"model_mode": "live"},
])
def test_context_revalidation_cannot_relabel_disabled_configuration_as_available(changes):
    from services.api.app.qa.http_schemas import QAContextData
    baseline = QAContextData(schema_version="v2.t39", can_ask=False, model_mode="disabled",
        live_available=False, real_processing_enabled=False, allow_test_fixture_read=False,
        demo_banner=None, disabled_reason="MODEL_DISABLED", budget_unit="conservative_utf8_bytes")
    with pytest.raises(ValidationError):
        QAContextData.model_validate(baseline.model_copy(update=changes))


@pytest.mark.parametrize("code,status", [
    ("MODEL_TIMEOUT", 503), ("MODEL_CANCELLED", 503), ("PROVIDER_FAILURE", 503),
    ("INVALID_PROVIDER_RESPONSE", 503), ("BUDGET_EXHAUSTED", 429),
])
def test_gateway_failures_map_to_finite_safe_qa_errors_without_provider_detail(code, status):
    from services.api.app.model_gateway.schemas import GatewayError
    from services.api.app.qa.router import translate
    error = translate(GatewayError(code))
    assert error.status_code == status
    assert len(error.details) == 1 and error.details[0].field_path == "qa"
    assert error.details[0].code == code
    assert SENTINEL not in str(error.details) and "Traceback" not in str(error.details)


def test_child_configuration_replacement_error_retains_no_store_and_zero_database_io(monkeypatch):
    from services.api.app.api.qa import create_qa_v2_app
    def forbidden(*args, **kwargs):
        raise AssertionError("Configuration guard accessed the database")
    monkeypatch.setattr(Engine, "connect", forbidden)
    for field in ("qa_service", "public_catalog_reader"):
        app = create_qa_v2_app()
        setattr(app.state, field, object())
        with TestClient(app, base_url="https://qa.test.invalid") as browser:
            body = safe_response(browser.get("/qa/context"), 503)
            assert body["error"]["details"][0]["code"] == "QA_UNAVAILABLE"
