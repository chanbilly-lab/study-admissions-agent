"""T39 anonymous HTTP around actual synthetic PG proof and offline async IO."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Event, get_ident
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import httpx
from pydantic import SecretStr
import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion
from services.api.app.api.qa import create_qa_app
from services.api.app.auth.router import SESSION_COOKIE
from services.api.app.model_gateway.budget import BudgetLedger
from services.api.app.model_gateway.gateway import ModelGateway
from services.api.app.model_gateway.schemas import BudgetPolicy, Claim, GatewayError, GatewayPolicy, ProviderResponse, StructuredAnswer
from services.api.app.public_catalog.reader import CatalogReader
from services.api.app.public_catalog.schemas import PublicCatalogPolicy
from services.api.app.qa.retrieval import ScopedRetriever
from services.api.app.qa.schemas import QAPolicy
from services.api.app.qa.service import QAService, QUESTIONS
from services.api.app.releases.schemas import PublishMember, WithdrawalRequest
from services.api.app.settings import V2RuntimeSettings
from services.api.app.storage.models import StorageObject
from tests.integration.qa.test_t38_safety import physical_snapshot, assert_only_anonymous_reads, wait_for_real_lock


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T39_PRIVATE_PROVIDER_SENTINEL"


class ExactOfflineProvider:
    def __init__(self):
        self.calls = []

    async def complete(self, request):
        self.calls.append(request)
        return ProviderResponse(answer=StructuredAnswer(status="answered", claims=tuple(
            Claim(citation_id=item.citation_id, value=item.value) for item in request.evidence),
            advice_codes=("REVIEW_SOURCE",)), input_usage=0, output_usage=0, is_synthetic=True)


def local_qa(case, *, provider=None, budget=None):
    """Create the new mock reader, leaving the frozen T38 disabled reader intact."""
    runtime = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="mock", _env_file=None)
    reader = CatalogReader(case.releases, runtime,
        PublicCatalogPolicy(enabled=True, allow_test_fixture_read=True))
    retriever = ScopedRetriever(reader, QAPolicy(enabled=True, allow_test_fixture_read=True))
    provider = provider if provider is not None else ExactOfflineProvider()
    budget = budget if budget is not None else BudgetLedger(BudgetPolicy(max_output_tokens=4096,
        output_limit=100000, global_output_limit=200000, request_limit=20, timeout_ms=60000))
    gateway = ModelGateway(policy=GatewayPolicy(app_environment="test", data_mode="demo", model_mode="mock"),
        provider=provider, budget=budget)
    service = QAService(runtime, retriever=retriever, gateway=gateway)
    app = create_qa_app(runtime, reader=reader, qa_service=service)
    return SimpleNamespace(runtime=runtime, reader=reader, retriever=retriever,
        provider=provider, budget=budget, gateway=gateway, service=service, app=app)


def safe_response(response, status):
    assert response.status_code == status
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    identifier = response.headers["X-Request-ID"]
    assert len(identifier) == 32 and body.get("meta", body.get("error"))["request_id"] == identifier
    assert SENTINEL not in response.text and "Traceback" not in response.text
    return body


def publish(case, **changes):
    members = tuple(PublishMember(fact_id=item.fact_id, expected_case_revision=item.case_revision,
        expected_decision_id=item.decision_id, public_evidence=True) for item in case.decisions)
    return case.releases.publish(case.reviewer.principal, case.publish_request(members=members, **changes),
        SecretStr("DEMO_T39_SAFETY_" + uuid4().hex))


def test_anonymous_http_ignores_two_real_owner_sessions_and_rejects_private_or_ambiguous_input_before_budget(
        qa_case_factory, actor_factory, pg_engine):
    case = qa_case_factory()
    one, two = actor_factory(), actor_factory()
    qa = local_qa(case)
    raw = case.request.model_dump(mode="json")
    before = physical_snapshot(pg_engine)
    sql = []
    def capture(connection, cursor, statement, parameters, context, many):
        sql.append(statement.lower())
    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        with TestClient(qa.app, base_url="https://qa.test.invalid") as browser:
            context = safe_response(browser.get("/v2/qa/context"), 200)
            assert context["data"]["can_ask"] is True
            identities = (None, one.cookie.get_secret_value(), two.cookie.get_secret_value())
            replies = []
            for cookie in identities:
                headers = {} if cookie is None else {"Cookie": f"{SESSION_COOKIE}={cookie}"}
                reply = safe_response(browser.post("/v2/qa/answers", json=raw, headers=headers), 200)
                assert reply["data"]["status"] == "answered"
                assert reply["meta"]["data_mode"] == "demo" and reply["meta"]["model_mode"] == "mock"
                assert all(reply["meta"][name] is None for name in ("profile_version_id", "release_id", "ruleset_version"))
                assert len(reply["data"]["citations"]) == 1
                assert not set(reply["data"]).intersection({"atoms", "answer", "owner", "profile", "grades"})
                replies.append(reply["data"])
            assert replies[0] == replies[1] == replies[2]
            assert len(qa.provider.calls) == 3 and qa.budget.snapshot().key_count == 1
            charged = qa.budget.snapshot()
            encoded = json.dumps(raw)
            bad_json = [encoded[:-1] + ',"entry_year":2026}',
                encoded.replace('"entry_year": 2026', '"entry_year": NaN'),
                json.dumps({**raw, "owner_user_id": SENTINEL}),
                json.dumps({**raw, "question": SENTINEL}),
                json.dumps({**raw, "tools": ["fetch_url"]}),
                json.dumps({**raw, "scope": {k: v for k, v in raw["scope"].items() if k != "province"}}),
                "[" + encoded + "]", " " * 16385]
            for body in bad_json:
                safe_response(browser.post("/v2/qa/answers", content=body,
                    headers={"Content-Type": "application/json"}), 422)
            for headers in ({"Content-Type": "text/plain"},
                    {"Content-Type": "application/json", "Idempotency-Key": SENTINEL}):
                safe_response(browser.post("/v2/qa/answers", content=encoded, headers=headers), 422)
            for query in ("?owner=" + SENTINEL, "?entry_year=2026&entry_year=2027", "?cursor=" + SENTINEL):
                safe_response(browser.post("/v2/qa/answers" + query, json=raw), 422)
            assert qa.budget.snapshot() == charged and len(qa.provider.calls) == 3
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)
    assert_only_anonymous_reads(sql)
    assert physical_snapshot(pg_engine) == before
    assert all(call.question == QUESTIONS[case.request.intent] for call in qa.provider.calls)
    assert case.reader.settings.model_mode == "disabled"


def test_no_public_atom_never_invokes_provider_or_reads_quota_clock(qa_case_factory, pg_engine):
    case = qa_case_factory(public_evidence=False)
    hits = []
    def no_clock():
        hits.append(True)
        raise AssertionError("No-atom answer read quota clock")
    class ForbiddenProvider:
        async def complete(self, request):
            hits.append(True)
            raise AssertionError("No-atom answer invoked provider")
    qa = local_qa(case, provider=ForbiddenProvider(),
        budget=BudgetLedger(BudgetPolicy(max_output_tokens=4096), clock=no_clock))
    before = physical_snapshot(pg_engine)
    with TestClient(qa.app, base_url="https://qa.test.invalid") as browser:
        safe_response(browser.get("/v2/qa/context"), 200)
        data = safe_response(browser.post("/v2/qa/answers", json=case.request.model_dump(mode="json")), 200)["data"]
    assert data["status"] == "unknown" and data["citations"] == []
    assert data["unknown_reasons"] == ["NO_PUBLIC_EVIDENCE"]
    assert hits == [] and physical_snapshot(pg_engine) == before


@pytest.mark.parametrize("change", ["withdraw", "replace"])
def test_actual_http_model_wait_rechecks_current_release_and_rejects_the_whole_old_answer(
        qa_case_factory, pg_engine, change):
    case = qa_case_factory()
    async def scenario():
        entered, resume = asyncio.Event(), asyncio.Event()
        class WaitingProvider(ExactOfflineProvider):
            async def complete(self, request):
                entered.set()
                await resume.wait()
                return await super().complete(request)
        qa = local_qa(case, provider=WaitingProvider())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=qa.app),
                base_url="https://qa.test.invalid") as browser:
            pending = asyncio.create_task(browser.post("/v2/qa/answers", json=case.request.model_dump(mode="json")))
            try:
                await asyncio.wait_for(entered.wait(), timeout=15)
                def mutate():
                    if change == "withdraw":
                        return case.releases.withdraw(case.reviewer.principal,
                            WithdrawalRequest(release_id=case.release.release_id,
                                expected_state_revision=case.release.state_revision, reason_code="ADMIN_REQUEST"))
                    return publish(case, replaces_release_id=case.release.release_id,
                        expected_replaced_state_revision=case.release.state_revision)
                changed = await asyncio.wait_for(asyncio.to_thread(mutate), timeout=30)
                assert changed.state == ("withdrawn" if change == "withdraw" else "published")
                assert not pending.done()  # DB mutation committed without waiting on the model's transaction.
                before = physical_snapshot(pg_engine)
                sql = []
                def capture(connection, cursor, statement, parameters, context, many):
                    sql.append(statement.lower())
                event.listen(pg_engine, "before_cursor_execute", capture)
                try:
                    resume.set()
                    response = await asyncio.wait_for(pending, timeout=15)
                    body = safe_response(response, 409)
                    assert body["error"]["details"][0]["code"] == "CITATION_CONFLICT"
                    assert "data" not in body and "600" not in response.text
                finally:
                    event.remove(pg_engine, "before_cursor_execute", capture)
                assert_only_anonymous_reads(sql)
                assert physical_snapshot(pg_engine) == before
                assert qa.budget.snapshot().requests == 1 and qa.budget.snapshot().inflight == 0
            finally:
                resume.set()
                if not pending.done():
                    pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
    asyncio.run(scenario())


def test_answer_validation_later_member_sql_wait_rechecks_first_file_expiry_before_http_returns(
        qa_case_factory, candidate_factory, pg_engine, clock):
    one = qa_case_factory(published=False, rows=[candidate_factory(field_key="DEMO_T39_FIRST")])
    two = qa_case_factory(published=False, rows=[candidate_factory(field_key="DEMO_T39_LATER")])
    first, later = sorted((one, two), key=lambda item: item.candidates[0].id)
    with Session(pg_engine) as session, session.begin():
        for current in (first, later):
            source = session.get(CatalogSourceVersion, current.source.id)
            source.recheck_days = 2
            source.recheck_due_at = source.created_at + timedelta(days=2)
            asset = session.get(StorageObject, current.file.id)
            asset.expires_at = asset.created_at + timedelta(days=1 if current is first else 2)
    members = tuple(PublishMember(fact_id=current.decisions[0].fact_id,
        expected_case_revision=current.decisions[0].case_revision,
        expected_decision_id=current.decisions[0].decision_id, public_evidence=True) for current in (first, later))
    release = first.releases.publish(first.reviewer.principal,
        first.publish_request(members=members, valid_until=clock() + timedelta(days=2)),
        SecretStr("DEMO_T39_HTTP_SQL_" + uuid4().hex))
    request = first.request.model_copy(update={"release_id": release.release_id})
    clock.advance(86400 - 1)
    entered, resume = Event(), Event()
    class WaitingProvider(ExactOfflineProvider):
        async def complete(self, value):
            entered.set()
            while not resume.is_set():
                await asyncio.sleep(0.01)
            return await super().complete(value)
    qa = local_qa(first, provider=WaitingProvider())
    before = physical_snapshot(pg_engine)
    started, pids, main_thread = Event(), [], get_ident()
    def observe(connection, cursor, statement, parameters, context, many):
        values = parameters.values() if type(parameters) is dict else parameters
        if (get_ident() != main_thread and resume.is_set() and "FROM catalog_sources" in statement
                and "FOR UPDATE" in statement and any(str(value) == str(later.source.source_id) for value in values)
                and not started.is_set()):
            pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            started.set()
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with TestClient(qa.app, base_url="https://qa.test.invalid") as browser, ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(browser.post, "/v2/qa/answers", json=request.model_dump(mode="json"))
            try:
                assert entered.wait(timeout=15), "Actual provider was not reached"
                with Session(pg_engine) as locked:
                    locked.begin()
                    blocker = locked.scalar(text("SELECT pg_backend_pid()"))
                    locked.execute(select(CatalogSource).where(CatalogSource.id == later.source.source_id).with_for_update())
                    try:
                        resume.set()
                        wait_for_real_lock(pg_engine, started, pids, blocker, pending)
                        clock.advance(1)
                    finally:
                        locked.rollback()
                body = safe_response(pending.result(timeout=30), 409)
                assert body["error"]["details"][0]["code"] == "CITATION_CONFLICT" and "data" not in body
            finally:
                resume.set()
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
    assert len(qa.provider.calls) == 1 and physical_snapshot(pg_engine) == before


def test_offline_http_failure_timeout_wrong_citation_and_cancellation_never_refund_or_return_raw_output(
        qa_case_factory):
    case = qa_case_factory()
    async def scenario():
        entered, hold, provider_finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        class FaultProvider:
            def __init__(self):
                self.mode = "failure"
            async def complete(self, request):
                if self.mode == "failure":
                    raise RuntimeError(SENTINEL)
                if self.mode == "wrong":
                    return ProviderResponse(answer=StructuredAnswer(status="answered",
                        claims=(Claim(citation_id=uuid4(), value=SENTINEL),), advice_codes=()),
                        input_usage=0, output_usage=0, is_synthetic=True)
                entered.set()
                try:
                    await hold.wait()
                    raise AssertionError("Blocked provider must be cancelled")
                finally:
                    provider_finished.set()
        provider = FaultProvider()
        qa = local_qa(case, provider=provider, budget=BudgetLedger(BudgetPolicy(max_output_tokens=4096,
            timeout_ms=100, output_limit=100000, global_output_limit=200000)))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=qa.app), base_url="https://qa.test.invalid") as browser:
            for mode, status, code in (("failure", 503, "PROVIDER_FAILURE"),
                    ("wrong", 409, "CITATION_CONFLICT"), ("timeout", 503, "MODEL_TIMEOUT")):
                provider.mode = mode
                body = safe_response(await browser.post("/v2/qa/answers", json=case.request.model_dump(mode="json")), status)
                assert body["error"]["details"][0]["code"] == code and "data" not in body
        provider.mode = "cancel"
        entered.clear()
        provider_finished.clear()
        pending = asyncio.create_task(qa.service.answer(case.request))
        try:
            await asyncio.wait_for(entered.wait(), timeout=15)
            pending.cancel()
            with pytest.raises(GatewayError) as cancelled:
                await asyncio.wait_for(pending, timeout=2)
            assert cancelled.value.code == "MODEL_CANCELLED"
            await asyncio.wait_for(provider_finished.wait(), timeout=0.1)
            # The gateway callback releases the slot only after the provider's
            # actual finally has run; one loop turn schedules that callback.
            await asyncio.sleep(0)
        finally:
            hold.set()
            await asyncio.gather(pending, return_exceptions=True)
        snap = qa.budget.snapshot(qa.service.budget_key)
        assert snap.requests == 4 and snap.output_tokens == 4 * 4096 and snap.inflight == 0
        assert len(qa.budget.history) == 4
    asyncio.run(scenario())
