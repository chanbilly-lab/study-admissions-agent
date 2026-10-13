"""Real current published facts, exact scope filtering and read-only retrieval."""

from datetime import timedelta
from uuid import uuid4

from pydantic import SecretStr
import pytest
from sqlalchemy import event, text

from services.api.app.admissions_catalog.schemas import ScopeKey
from services.api.app.model_gateway.schemas import Claim, StructuredAnswer
from services.api.app.qa import QAError, QAPolicy, validate_answer
from services.api.app.qa.retrieval import ScopedRetriever
from services.api.app.releases.schemas import PublishMember, WithdrawalRequest

pytestmark = pytest.mark.postgres


def test_current_publication_is_exact_and_anonymous_without_writes_or_student_sql(qa_case_factory, pg_engine):
    case = qa_case_factory()
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())
    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        bundle = case.retriever.retrieve(case.request)
        assert len(bundle.citations) == len(bundle.atoms) == 1 and bundle.unknown_reasons == ()
        assert bundle.model_scope.dataset_id == case.source.dataset_id
        assert bundle.citations[0].fact.value_text == "600.00"
        assert '"unit":"points"' in bundle.atoms[0].value
        answer = StructuredAnswer(status="answered", claims=(Claim(citation_id=bundle.atoms[0].citation_id,
            value=bundle.atoms[0].value),), advice_codes=())
        assert validate_answer(case.retriever, bundle, answer) == answer
        assert statements and all(not statement.lstrip().startswith(("insert", "update", "delete")) for statement in statements)
        assert not any(any(name in statement for name in ("student_profiles", "auth_sessions", "auth_user_roles",
            "eligibility_assessments", "plan_draft_roots")) for statement in statements)
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)


def test_scope_and_literal_keywords_cannot_expand_the_target(qa_case_factory):
    case = qa_case_factory()
    for request in (case.request.model_copy(update={"offering_id": uuid4()}),
        case.request.model_copy(update={"offering_version": 2}),
        case.request.model_copy(update={"entry_year": 2027, "scope": case.request.scope.model_copy(update={"entry_year": 2027})}),
        case.request.model_copy(update={"scope": case.request.scope.model_copy(update={"province": ScopeKey(status="known", value="DEMO_OTHER")})})):
        result = case.retriever.retrieve(request)
        assert result.unknown_reasons == ("TARGET_MISMATCH",) and not result.citations
    unknown = case.request.model_copy(update={"scope": case.request.scope.model_copy(update={"province": ScopeKey(status="unknown", value=None)})})
    assert case.retriever.retrieve(unknown).unknown_reasons == ("SCOPE_UNKNOWN",)
    injection = case.request.model_copy(update={"keywords": ("' OR 1=1 --",)})
    assert case.retriever.retrieve(injection).unknown_reasons == ("NO_MATCHING_FACTS",)
    assert len(case.retriever.retrieve(case.request.model_copy(update={"keywords": ("600",)})).citations) == 1


def test_candidates_and_unpublished_quotes_do_not_become_model_atoms(qa_case_factory):
    case = qa_case_factory(public_evidence=False)
    result = case.retriever.retrieve(case.request)
    assert result.unknown_reasons == ("NO_PUBLIC_EVIDENCE",) and not result.atoms and not result.citations
    case.releases.withdraw(case.reviewer.principal, WithdrawalRequest(release_id=case.release.release_id,
        expected_state_revision=case.release.state_revision, reason_code="ADMIN_REQUEST"))
    assert case.retriever.retrieve(case.request).unknown_reasons == ("RELEASE_UNAVAILABLE",)


def test_waiting_answer_cannot_use_a_replaced_release(qa_case_factory):
    case = qa_case_factory()
    bundle = case.retriever.retrieve(case.request)
    answer = StructuredAnswer(status="answered", claims=(Claim(citation_id=bundle.atoms[0].citation_id,
        value=bundle.atoms[0].value),), advice_codes=())
    members = tuple(PublishMember(fact_id=item.fact_id, expected_case_revision=item.case_revision,
        expected_decision_id=item.decision_id, public_evidence=True) for item in case.decisions)
    case.releases.publish(case.reviewer.principal, case.publish_request(members=members,
        replaces_release_id=case.release.release_id, expected_replaced_state_revision=case.release.state_revision),
        SecretStr("DEMO_T38_REPLACE_" + uuid4().hex))
    with pytest.raises(QAError) as caught:
        validate_answer(case.retriever, bundle, answer)
    assert caught.value.code == "CITATION_CONFLICT"


def test_default_and_configuration_drift_close_before_sql(qa_case_factory, pg_engine):
    case = qa_case_factory()
    statements = []
    def capture(*args):
        statements.append(True)
    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        with pytest.raises(QAError):
            ScopedRetriever(case.reader).retrieve(case.request)
        case.reader.policy.__dict__["enabled"] = False
        with pytest.raises(QAError):
            case.retriever.retrieve(case.request)
        assert statements == []
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)
