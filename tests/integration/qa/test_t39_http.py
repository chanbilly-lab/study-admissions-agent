"""T39 actual anonymous ASGI, published PG proof and offline async gateway."""

from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event

from services.api.app.api.qa import create_qa_app
from services.api.app.model_gateway.budget import BudgetLedger
from services.api.app.model_gateway.gateway import ModelGateway
from services.api.app.model_gateway.schemas import BudgetPolicy, GatewayPolicy
from services.api.app.public_catalog.reader import CatalogReader
from services.api.app.public_catalog.schemas import PublicCatalogPolicy
from services.api.app.qa.retrieval import ScopedRetriever
from services.api.app.qa.schemas import QAPolicy
from services.api.app.qa.service import QAService
from services.api.app.settings import V2RuntimeSettings

pytestmark = pytest.mark.postgres


def make_qa_case(case, *, provider=None, budget=None):
    """New T39 runtime only; protected T38 case/reader are left unchanged."""
    runtime = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="mock",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    reader = CatalogReader(case.releases, runtime, PublicCatalogPolicy(enabled=True, allow_test_fixture_read=True))
    retriever = ScopedRetriever(reader, QAPolicy(enabled=True, allow_test_fixture_read=True))
    budget = budget if budget is not None else BudgetLedger(BudgetPolicy(max_output_tokens=4096))
    gateway = ModelGateway(policy=GatewayPolicy(app_environment="test", data_mode="demo", model_mode="mock"),
        provider=provider, budget=budget)
    service = QAService(runtime, retriever=retriever, gateway=gateway)
    app = create_qa_app(runtime, reader=reader, qa_service=service)
    return SimpleNamespace(**{**vars(case), "runtime": runtime, "reader": reader, "retriever": retriever,
        "budget": budget, "gateway": gateway, "service": service, "app": app})


def assert_safe(response, status):
    assert response.status_code == status, response.json()
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert response.headers["x-request-id"] == (body["meta"]["request_id"] if status == 200 else body["error"]["request_id"])
    return body


def test_real_current_http_typed_answer_and_closed_parser_do_not_write_or_read_students(qa_case_factory, pg_engine):
    case = make_qa_case(qa_case_factory())
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())
    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        with TestClient(case.app) as client:
            context = assert_safe(client.get("/v2/qa/context"), 200)
            assert context["data"]["can_ask"] and context["meta"]["model_mode"] == "mock"
            assert statements == []
            body = case.request.model_dump(mode="json")
            result = assert_safe(client.post("/v2/qa/answers", json=body), 200)
            data = result["data"]
            assert data["status"] == "answered" and len(data["citations"]) == 1
            citation = data["citations"][0]
            assert citation["fact"]["value_text"] == "600.00" and citation["fact"]["unit"] == "points"
            assert citation["scope"]["dataset_id"] == str(case.source.dataset_id)
            assert citation["release_id"] == str(case.request.release_id)
            assert not {"atoms", "claims", "answer", "question"} & data.keys()
            assert result["meta"]["profile_version_id"] is None
            before = len(statements)
            invalid_requests = [
                dict(json={**body, "question": "PRIVATE_STUDENT_SENTINEL"}),
                dict(content='{"intent":"requirements","intent":"fees"}', headers={"content-type": "application/json"}),
                dict(content='{"entry_year":NaN}', headers={"content-type": "application/json"}),
                dict(content=" " * 16385, headers={"content-type": "application/json"}),
                dict(json=body, headers={"Idempotency-Key": "client_cannot_supply_key"}),
                dict(content="{}", headers={"content-type": "text/plain"}),
            ]
            for kwargs in invalid_requests:
                error = assert_safe(client.post("/v2/qa/answers", **kwargs), 422)
                assert "PRIVATE_STUDENT_SENTINEL" not in str(error)
            assert_safe(client.post("/v2/qa/answers?owner=PRIVATE_STUDENT_SENTINEL", json=body), 422)
            assert len(statements) == before
        assert all(not sql.lstrip().startswith(("insert", "update", "delete")) for sql in statements)
        assert not any(any(table in sql for table in ("student_profiles", "auth_sessions", "auth_user_roles", "eligibility_assessments")) for sql in statements)
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)


def test_real_http_quota_is_shared_and_frozen_gateway_drift_closes_before_sql(qa_case_factory, pg_engine):
    budget = BudgetLedger(BudgetPolicy(max_output_tokens=4096, request_limit=1))
    case = make_qa_case(qa_case_factory(), budget=budget)
    with TestClient(case.app) as client:
        assert_safe(client.post("/v2/qa/answers", json=case.request.model_dump(mode="json")), 200)
        second = assert_safe(client.post("/v2/qa/answers", json=case.request.model_dump(mode="json")), 429)
        assert second["error"]["details"][0]["code"] == "BUDGET_EXHAUSTED"
        assert budget.snapshot(case.service.budget_key).requests == 1
        statements = []
        def capture(*args):
            statements.append(True)
        event.listen(pg_engine, "before_cursor_execute", capture)
        try:
            case.gateway.budget.policy.__dict__["timeout_ms"] = 999
            error = assert_safe(client.post("/v2/qa/answers", json=case.request.model_dump(mode="json")), 503)
            assert error["error"]["details"][0]["code"] == "BUDGET_UNAVAILABLE"
            assert statements == []
        finally:
            event.remove(pg_engine, "before_cursor_execute", capture)


def test_real_current_scope_unknown_and_unpublished_quotes_never_call_model(qa_case_factory):
    case = make_qa_case(qa_case_factory(public_evidence=False))
    with TestClient(case.app) as client:
        result = assert_safe(client.post("/v2/qa/answers", json=case.request.model_dump(mode="json")), 200)
        assert result["data"]["status"] == "unknown" and result["data"]["citations"] == []
        assert result["data"]["unknown_reasons"] == ["NO_PUBLIC_EVIDENCE"]
        unknown = case.request.model_dump(mode="json")
        unknown["scope"]["province"] = {"status": "unknown", "value": None}
        result = assert_safe(client.post("/v2/qa/answers", json=unknown), 200)
        assert result["data"]["model_scope"] is None and result["data"]["unknown_reasons"] == ["SCOPE_UNKNOWN"]
        assert case.budget.snapshot(case.service.budget_key).requests == 0
