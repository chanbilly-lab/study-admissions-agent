"""Current anonymous proof after real offline model and PostgreSQL waits."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
import json
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

from pydantic import SecretStr
import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion
from services.api.app.model_gateway.budget import BudgetLedger
from services.api.app.model_gateway.gateway import ModelGateway
from services.api.app.model_gateway.schemas import (
    BudgetKey, BudgetPolicy, Claim, GatewayPolicy, ModelRequest, ProviderResponse, StructuredAnswer,
)
from services.api.app.qa.schemas import QAError
from services.api.app.qa.validation import validate_answer
from services.api.app.releases.schemas import PublishMember, WithdrawalRequest
from services.api.app.storage.models import StorageObject


pytestmark = pytest.mark.postgres
PRIVATE_TABLES = ("auth_users", "auth_sessions", "auth_user_roles", "auth_owned_resources",
    "privacy_consents", "student_profiles", "student_profile_versions", "eligibility_assessments",
    "plan_draft_roots", "execution_heads")
ORIGINAL_TABLES = ("catalog_datasets", "catalog_sources", "catalog_source_versions", "storage_objects",
    "import_batches", "import_candidate_rows", "evidence_documents", "evidence_document_versions",
    "evidence_snippets", "fact_candidates", "fact_conflicts", "review_cases", "review_decisions",
    "catalog_releases", "catalog_release_members", "catalog_release_states", "catalog_change_events",
    "catalog_outbox", "auth_audit_events", "idempotency_records")


def physical_snapshot(engine):
    """Only synthetic rows are hashed; neither row values nor DB URLs are printed."""
    with engine.connect() as connection:
        return tuple((name, sha256(json.dumps(sorted(connection.execute(
            text(f'SELECT to_jsonb(t)::text FROM "{name}" AS t')).scalars()),
            ensure_ascii=False).encode("utf-8")).hexdigest()) for name in ORIGINAL_TABLES)


def publish(case, **changes):
    members = tuple(PublishMember(fact_id=item.fact_id, expected_case_revision=item.case_revision,
        expected_decision_id=item.decision_id, public_evidence=True) for item in case.decisions)
    return case.releases.publish(case.reviewer.principal, case.publish_request(members=members, **changes),
        SecretStr("DEMO_T38_SAFETY_" + uuid4().hex))


def answered(bundle):
    return StructuredAnswer(status="answered", claims=(Claim(citation_id=bundle.atoms[0].citation_id,
        value=bundle.atoms[0].value),), advice_codes=("REVIEW_SOURCE",))


def assert_only_anonymous_reads(statements):
    assert statements
    assert all(not sql.lstrip().startswith(("insert", "update", "delete", "alter", "create", "drop"))
        for sql in statements)
    assert not any(name in sql for sql in statements for name in PRIVATE_TABLES)


@pytest.mark.parametrize("change", ["withdraw", "replace", "source_expiry"])
def test_offline_model_wait_cannot_reuse_current_proof_after_publication_or_source_changes(
        qa_case_factory, pg_engine, clock, change):
    case = qa_case_factory(published=False)
    if change == "source_expiry":
        # Establish an independently longer original-file interval BEFORE the
        # first publication captures it; never extend a previously expired pin.
        with Session(pg_engine) as session, session.begin():
            asset = session.get(StorageObject, case.file.id)
            asset.expires_at = asset.created_at + timedelta(days=2)
    case.release = publish(case, valid_until=clock() + timedelta(days=2))
    case.request = case.request.model_copy(update={"release_id": case.release.release_id})
    bundle = case.retriever.retrieve(case.request)
    assert len(bundle.atoms) == 1 and bundle.unknown_reasons == ()

    async def scenario():
        entered, resume = asyncio.Event(), asyncio.Event()
        calls = []
        class OfflineWaitingProvider:
            async def complete(self, request):
                calls.append(request)
                entered.set()
                await resume.wait()
                return ProviderResponse(answer=answered(bundle), input_usage=0, output_usage=0, is_synthetic=True)
        ledger = BudgetLedger(BudgetPolicy(max_output_tokens=4096, timeout_ms=60000))
        gateway = ModelGateway(policy=GatewayPolicy(app_environment="test", data_mode="demo", model_mode="mock"),
            provider=OfflineWaitingProvider(), budget=ledger)
        model_request = ModelRequest(scope=bundle.model_scope, question="DEMO_请核对指定公开要求", evidence=bundle.atoms)
        key = BudgetKey(key_id=uuid4())
        pending = asyncio.create_task(gateway.complete(key, model_request))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            if change == "withdraw":
                def mutate():
                    return case.releases.withdraw(case.reviewer.principal,
                        WithdrawalRequest(release_id=case.release.release_id,
                            expected_state_revision=case.release.state_revision, reason_code="ADMIN_REQUEST"))
                removed = await asyncio.wait_for(asyncio.to_thread(mutate), timeout=25)
                assert removed.state == "withdrawn"
            elif change == "replace":
                def mutate():
                    return publish(case, replaces_release_id=case.release.release_id,
                        expected_replaced_state_revision=case.release.state_revision)
                replacement = await asyncio.wait_for(asyncio.to_thread(mutate), timeout=25)
                assert replacement.release_id != case.release.release_id and replacement.state == "published"
            else:
                clock.advance(86400)
            # Actual publication mutation committed while the provider is still
            # waiting. Retrieval therefore did not keep its DB locks for IO.
            assert not pending.done()
            before = physical_snapshot(pg_engine)
            statements = []
            def capture(connection, cursor, statement, parameters, context, many):
                statements.append(statement.lower())
            event.listen(pg_engine, "before_cursor_execute", capture)
            try:
                resume.set()
                response = await asyncio.wait_for(pending, timeout=2)
                assert response.answer == answered(bundle) and len(calls) == 1
                with pytest.raises(QAError) as caught:
                    validate_answer(case.retriever, bundle, response.answer)
                assert caught.value.code == "CITATION_CONFLICT"
                fresh = case.retriever.retrieve(case.request)
                assert fresh.unknown_reasons == ("RELEASE_UNAVAILABLE",)
                assert fresh.atoms == fresh.citations == () and fresh.model_scope is None
            finally:
                event.remove(pg_engine, "before_cursor_execute", capture)
            assert_only_anonymous_reads(statements)
            assert physical_snapshot(pg_engine) == before
            assert ledger.snapshot(key).inflight == 0
        finally:
            resume.set()
            if not pending.done():
                pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
    asyncio.run(scenario())


def wait_for_real_lock(engine, started, pids, blocker, pending):
    until = monotonic() + 20
    while not started.wait(timeout=0.05):
        if pending.done():
            pending.result()
            pytest.fail("Retriever completed before the selected SQL wait boundary")
        if monotonic() >= until:
            pytest.fail("Retriever did not reach its SQL wait boundary within 20 seconds")
    until = monotonic() + 5
    while monotonic() < until:
        with engine.connect() as connection:
            locked = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                "WHERE pid=:pid AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)))"),
                {"pid": pids[0], "blocker": blocker})
        if locked:
            return
    pytest.fail("A real PostgreSQL lock wait was not observed")


@pytest.mark.parametrize("deadline", ["source", "file"])
def test_later_member_proof_sql_wait_rechecks_first_member_deadline_before_releasing_any_citation(
        qa_case_factory, candidate_factory, pg_engine, clock, deadline):
    one = qa_case_factory(published=False, rows=[candidate_factory(field_key="DEMO_T38_FIRST")])
    two = qa_case_factory(published=False, rows=[candidate_factory(field_key="DEMO_T38_SECOND")])
    first, later = sorted((one, two), key=lambda case: case.candidates[0].id)
    with Session(pg_engine) as session, session.begin():
        late_source = session.get(CatalogSourceVersion, later.source.id)
        late_source.recheck_days = 2
        late_source.recheck_due_at = late_source.created_at + timedelta(days=2)
        for current in (first, later):
            asset = session.get(StorageObject, current.file.id)
            asset.expires_at = asset.created_at + timedelta(days=2 if deadline == "source" or current is later else 1)
        if deadline == "file":
            early_source = session.get(CatalogSourceVersion, first.source.id)
            early_source.recheck_days = 2
            early_source.recheck_due_at = early_source.created_at + timedelta(days=2)
    members = tuple(PublishMember(fact_id=current.decisions[0].fact_id,
        expected_case_revision=current.decisions[0].case_revision,
        expected_decision_id=current.decisions[0].decision_id, public_evidence=True) for current in (first, later))
    release = first.releases.publish(first.reviewer.principal,
        first.publish_request(members=members, valid_until=clock() + timedelta(days=2)),
        SecretStr("DEMO_T38_SQL_WAIT_" + uuid4().hex))
    current_request = first.request.model_copy(update={"release_id": release.release_id})
    clock.advance(86400 - 1)
    before_bundle = first.retriever.retrieve(current_request)
    assert len(before_bundle.citations) == 2
    before = physical_snapshot(pg_engine)
    started, pids, main_thread = Event(), [], get_ident()
    def observe(connection, cursor, statement, parameters, context, many):
        values = parameters.values() if type(parameters) is dict else parameters
        if (get_ident() != main_thread and "FROM catalog_sources" in statement and "FOR UPDATE" in statement
                and any(str(value) == str(later.source.source_id) for value in values) and not started.is_set()):
            pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            started.set()
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with Session(pg_engine) as locked:
            locked.begin()
            blocker = locked.scalar(text("SELECT pg_backend_pid()"))
            locked.execute(select(CatalogSource).where(CatalogSource.id == later.source.source_id).with_for_update())
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(first.retriever.retrieve, current_request)
                try:
                    wait_for_real_lock(pg_engine, started, pids, blocker, pending)
                    clock.advance(1)
                finally:
                    locked.rollback()
                result = pending.result(timeout=30)
        assert result.unknown_reasons == ("RELEASE_UNAVAILABLE",)
        assert result.model_scope is None and result.citations == result.atoms == ()
        with pytest.raises(QAError):
            validate_answer(first.retriever, before_bundle, answered(before_bundle))
        assert physical_snapshot(pg_engine) == before
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
