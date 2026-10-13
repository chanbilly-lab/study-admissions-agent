"""T34 real committed publication history, fanout and additive schema checks."""

from datetime import timedelta
from uuid import uuid4

from alembic import command
from pydantic import SecretStr
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.admissions_catalog.models import CatalogDataset
from services.api.app.changes.models import ChangeEventReceipt, AssessmentChangeImpact, PlanChangeImpact
from services.api.app.changes.schemas import ChangesError
from services.api.app.changes.store import HEADS, migration_config, migrate_changes
from services.api.app.plan_execution.schemas import CompleteInput
from services.api.app.releases.models import ChangeEvent
from services.api.app.releases.schemas import PublishMember, PublishRequest, WithdrawalRequest
from tests.integration.plan_execution.test_t32_store import workspace_input, confirm

pytestmark = pytest.mark.postgres


def event_id(engine, release_id, kind):
    with Session(engine) as session:
        return session.scalar(select(ChangeEvent.id).where(ChangeEvent.release_id==release_id,ChangeEvent.event_type==kind))


def replace(case, engine, *, members=None, extend=True):
    original = case.release
    with Session(engine) as session:
        revision = session.get(CatalogDataset,original.dataset_id).revision
    return case.releases.publish(case.reviewer.principal,PublishRequest(
        dataset_id=original.dataset_id,expected_dataset_revision=revision,entry_year=original.entry_year,
        kind="test_fixture",valid_from=original.valid_from,
        valid_until=original.valid_until+(timedelta(hours=1) if extend else timedelta()),
        members=members or tuple(PublishMember(fact_id=m.fact_id,expected_case_revision=m.case_revision,
            expected_decision_id=m.decision_id,public_evidence=m.public_evidence) for m in original.members),
        replaces_release_id=original.release_id,expected_replaced_state_revision=original.state_revision),
        SecretStr("DEMO_T34_REPLACE_"+uuid4().hex))


def withdraw(case):
    return case.releases.withdraw(case.reviewer.principal,WithdrawalRequest(release_id=case.release.release_id,
        expected_state_revision=case.release.state_revision,reason_code="SOURCE_UNAVAILABLE"))


def counts(engine):
    with engine.connect() as connection:
        return tuple(connection.execute(text("SELECT count(*) FROM "+table)).scalar_one() for table in
            ("change_event_receipts","assessment_change_impacts","plan_change_impacts"))


def immutable_rows(engine):
    tables=("eligibility_assessments","plan_draft_roots","plan_draft_versions","plan_draft_tasks",
        "plan_draft_assessments","plan_draft_dependencies","plan_execution_heads","plan_execution_proposals",
        "plan_execution_confirmations","plan_task_completions","catalog_outbox")
    with engine.connect() as connection:
        return tuple(tuple(connection.execute(text("SELECT row_to_json(t) FROM "+table+" t ORDER BY row_to_json(t)::text")).scalars()) for table in tables)


def test_published_backlog_is_zero_impact_even_after_withdrawal(change_case_factory,pg_engine):
    case=change_case_factory()
    published=event_id(pg_engine,case.release.release_id,"published")
    withdraw(case)
    frozen=immutable_rows(pg_engine)
    result=case.service.process_event(published)
    assert (result.event_type,result.assessment_count,result.plan_count,result.replayed)==("published",0,0,False)
    assert case.service.process_event(published).replayed is True
    assert counts(pg_engine)==(1,0,0)
    assert immutable_rows(pg_engine)==frozen


def test_replacement_fanout_keeps_confirmed_progress_and_old_hashes(change_case_factory,pg_engine):
    case=change_case_factory()
    execution=case.execution
    current=execution.get_plan(case.principal,case.plan.plan_id)
    ready=execution.update_workspace(case.principal,current.plan_id,
        workspace_input(case,current,start_offset=timedelta(minutes=5)))
    # The shared old helper uses case.service. Retain the real ExecutionService
    # explicitly for this server operation; no authority or DTO is mocked.
    from types import SimpleNamespace
    bridge=SimpleNamespace(**{**vars(case),"service":execution})
    accepted,_=confirm(bridge,ready,key="DEMO_T34_CONFIRM")
    current=accepted.execution
    for task in ready.proposal.schedule.tasks:
        current=execution.complete_task(case.principal,current.plan_id,task.task_key,
            CompleteInput(expected_version=current.state_version,confirmed=True)).execution
    after=replace(case,pg_engine)
    frozen=immutable_rows(pg_engine)
    identifier=event_id(pg_engine,case.release.release_id,"replaced")
    result=case.service.process_event(identifier)
    assert (result.assessment_count,result.plan_count)==(1,1)
    assessment=case.service.get_assessment_impacts(case.principal,case.assessment.assessment_id)
    plan=case.service.get_plan_impacts(case.principal,current.plan_id)
    assert len(assessment.items)==len(plan.items)==1
    assert assessment.items[0].needs_review is True
    assert "RELEASE_WINDOW_CHANGED" in assessment.items[0].reasons
    assert plan.items[0].after_release_id==after.release_id
    assert immutable_rows(pg_engine)==frozen
    assert case.service.process_event(identifier).replayed is True
    assert counts(pg_engine)==(1,1,1)


def test_same_business_replacement_is_reference_trace_only(change_case_factory,pg_engine):
    case=change_case_factory()
    replace(case,pg_engine,extend=False)
    result=case.service.process_event(event_id(pg_engine,case.release.release_id,"replaced"))
    assert result.assessment_count==1
    value=case.service.get_assessment_impacts(case.principal,case.assessment.assessment_id).items[0]
    assert value.needs_review is False and value.reasons==("REFERENCE_REPLACED",)
    # Old release authority remains replaced. A sidecar does not renew actions.
    from services.api.app.plan_execution.schemas import ExecutionError
    with pytest.raises(ExecutionError) as error:
        case.execution.get_plan(case.principal,case.plan.plan_id)
    assert error.value.status_code==409


def test_withdrawal_trace_works_after_original_file_expiry(change_case_factory,pg_engine,clock):
    case=change_case_factory(file_lifetime_seconds=40)
    clock.advance(41)
    withdraw(case)
    result=case.service.process_event(event_id(pg_engine,case.release.release_id,"withdrawn"))
    assert result.assessment_count==result.plan_count==1
    value=case.service.get_plan_impacts(case.principal,case.plan.plan_id).items[0]
    assert value.needs_review and value.reasons==("RELEASE_WITHDRAWN",)
    assert value.after_release_id is None


def test_receipt_and_impact_integrity_is_checked_on_repeat_and_read(change_case_factory,pg_engine):
    case=change_case_factory()
    withdraw(case)
    identifier=event_id(pg_engine,case.release.release_id,"withdrawn")
    case.service.process_event(identifier)
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE change_event_receipts DISABLE TRIGGER change_event_receipts_no_update"))
        connection.execute(text("UPDATE change_event_receipts SET payload_sha256=:hash WHERE event_id=:id"),{"hash":"f"*64,"id":identifier})
        connection.execute(text("ALTER TABLE change_event_receipts ENABLE TRIGGER change_event_receipts_no_update"))
    with pytest.raises(ChangesError) as error:
        case.service.process_event(identifier)
    assert error.value.status_code==409
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE assessment_change_impacts DISABLE TRIGGER assessment_change_impacts_no_update"))
        connection.execute(text("UPDATE assessment_change_impacts SET payload_sha256=:hash WHERE event_id=:id"),{"hash":"e"*64,"id":identifier})
        connection.execute(text("ALTER TABLE assessment_change_impacts ENABLE TRIGGER assessment_change_impacts_no_update"))
    with pytest.raises(ChangesError) as error:
        case.service.get_assessment_impacts(case.principal,case.assessment.assessment_id)
    assert error.value.status_code==503


def test_new_chain_round_trip_indexes_and_immutable_relationships(change_case_factory,pg_engine,changes_store):
    case=change_case_factory()
    withdraw(case)
    identifier=event_id(pg_engine,case.release.release_id,"withdrawn")
    case.service.process_event(identifier)
    for table in ("change_event_receipts","assessment_change_impacts","plan_change_impacts"):
        with pytest.raises(IntegrityError):
            with pg_engine.begin() as connection:
                connection.execute(text("UPDATE "+table+" SET created_at=created_at" if table!="change_event_receipts" else "UPDATE change_event_receipts SET processed_at=processed_at"))
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as connection:
            connection.execute(text("INSERT INTO change_event_receipts SELECT :id,dataset_id,entry_year,is_synthetic,event_type,before_release_id,after_release_id,event_sha256,payload_sha256,payload,assessment_count,plan_count,processed_at,audit_event_id FROM change_event_receipts LIMIT 1"),{"id":uuid4()})
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as connection:
            connection.execute(text("INSERT INTO assessment_change_impacts SELECT event_id,:id,owner_user_id,is_synthetic,needs_review,payload,payload_sha256,created_at FROM assessment_change_impacts LIMIT 1"),{"id":uuid4()})
    with pg_engine.connect() as connection:
        heads={name:connection.execute(text("SELECT version_num FROM "+name)).scalar_one() for name in HEADS}
    with pg_engine.begin() as connection:
        config=migration_config(); config.attributes["connection"]=connection
        command.downgrade(config,"base")
        for name,head in heads.items():
            assert connection.execute(text("SELECT version_num FROM "+name)).scalar_one()==head
        assert connection.execute(text("SELECT to_regclass('ix_assessment_release_target')")).scalar_one() is None
        assert connection.execute(text("SELECT to_regclass('ix_plan_source_assessment')")).scalar_one() is None
    migrate_changes(pg_engine)
    changes_store.assert_schema_ready()
    assert counts(pg_engine)==(0,0,0)


def test_new_field_in_published_replacement_marks_existing_target(change_case_factory,pg_engine,
        import_case_factory,candidate_factory,evidence_factory,facts_factory,classification_factory,reviews_store):
    """A new requirement must not be hidden by an old narrow rule.fact_ids list."""
    from services.api.app.admin.imports.models import ImportCandidateRow
    from services.api.app.evidence.schemas import DocumentCreate,VersionCreate,SnippetCreate
    from services.api.app.facts.schemas import FactCreate
    from services.api.app.reviews.schemas import CHECK_FIELDS,ReviewRequest,ReviewCheck,ReviewPolicy
    from services.api.app.reviews.service import ReviewService
    case=change_case_factory()
    incoming=import_case_factory(rows=[candidate_factory(fact_type="requirement",value_kind="text",
        field_key="DEMO_T34_NEW_REQUIREMENT",value_text="DEMO_EXPLICIT_NEW_MATERIAL",unit="text")])
    imported=incoming.service.import_file(incoming.admin.principal,incoming.request(),SecretStr("DEMO_T34_NEW_IMPORT"))
    evidence=evidence_factory(incoming.storage)
    doc=evidence.create_document(incoming.admin.principal,DocumentCreate(dataset_id=incoming.source.dataset_id,
        source_id=incoming.source.source_id,source_version=incoming.source.version,document_reference="DEMO_T34_NEW_DOC",language="und"))
    evidence.create_version(incoming.admin.principal,VersionCreate(document_id=doc.id,expected_current_version=0,
        file_id=incoming.file.id,file_sha256=incoming.file.sha256))
    snippet=evidence.create_snippet(incoming.admin.principal,SnippetCreate(document_id=doc.id,document_version=1,
        offering_id=case.bundle.offering_id,offering_version=1,entry_year=2026,byte_start=0,byte_end=len(incoming.data)))
    with Session(pg_engine) as session:
        row=session.scalar(select(ImportCandidateRow.id).where(ImportCandidateRow.import_id==imported.id))
    facts=facts_factory(incoming.storage,imports=incoming.service,evidence=evidence)
    fact=facts.create_fact(incoming.admin.principal,FactCreate(import_id=imported.id,import_row_id=row,
        classification=classification_factory(unit_code="text",claim_kind="minimum_requirement"),evidence_id=snippet.id))
    reviews=ReviewService(facts,reviews_store,ReviewPolicy(enabled=True))
    decision=reviews.decide(case.reviewer.principal,ReviewRequest(fact_id=fact.id,expected_fact_version=1,
        expected_case_revision=0,action="approve",checks=tuple(ReviewCheck(field=field,
            status="not_applicable" if field in {"statistics_context","date_context"} else "accepted") for field in CHECK_FIELDS),
        conflict_resolutions=(),return_reason=None))
    members=tuple(PublishMember(fact_id=m.fact_id,expected_case_revision=m.case_revision,
        expected_decision_id=m.decision_id,public_evidence=m.public_evidence) for m in case.release.members)
    replace(case,pg_engine,extend=False,members=members+(PublishMember(fact_id=fact.id,expected_case_revision=decision.case_revision,
        expected_decision_id=decision.decision_id,public_evidence=False),))
    case.service.process_event(event_id(pg_engine,case.release.release_id,"replaced"))
    result=case.service.get_assessment_impacts(case.principal,case.assessment.assessment_id)
    assert result.items[0].needs_review is True and "MEMBER_ADDED" in result.items[0].reasons
