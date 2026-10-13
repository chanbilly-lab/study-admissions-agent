"""Actual PostgreSQL revision decisions preserve original execution rows."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text,select
from sqlalchemy.orm import Session
from alembic import command

from services.api.app.plan_revisions.schemas import DecisionInput,RevisionError
from services.api.app.plan_revisions.models import RevisionProposal,RevisionDecision,PlanReplacement
from services.api.app.plan_revisions.store import migration_config,migrate_revisions
from services.api.app.plan_execution.schemas import WorkspaceInput

pytestmark=pytest.mark.postgres


def physical(engine,ids):
    with engine.connect() as connection:
        return {name:tuple(connection.execute(text('SELECT row_to_json(t)::text FROM "'+name+'" t WHERE plan_id=ANY(:ids) ORDER BY row_to_json(t)::text'),
            {"ids":list(ids)}).scalars()) for name in ("plan_execution_heads","plan_execution_proposals","plan_execution_confirmations","plan_task_completions")}


def test_profile_revision_accept_preserves_old_completion_and_new_draft(revision_case_factory,pg_engine):
    case=revision_case_factory()
    before=physical(pg_engine,(case.old.plan_id,case.new.plan_id))
    try:
        result=case.service.propose(case.principal,case.request)
    except RevisionError as error:
        cause=error.__context__
        if isinstance(cause,(AttributeError,KeyError,TypeError)):
            pytest.fail(f"T35 integration API mismatch: {type(cause).__name__}: {cause}")
        from pydantic import ValidationError
        if isinstance(cause,ValidationError):
            pytest.fail("T35 integration DTO mismatch: "+str(cause.errors(include_input=False,include_context=False)))
        raise
    assert result.revision.diff.changed_fields[0]=="profile_version"
    assert len(result.revision.old.completion_refs)==1 and not result.revision.new.completion_refs
    again=case.service.propose(case.principal,case.request)
    assert again.replayed and again.revision==result.revision
    request=DecisionInput(expected_revision_version=1,action="accept",student_confirmed=True)
    decision=case.service.decide(case.principal,result.revision.revision_id,request)
    assert decision.revision.status=="accepted" and not decision.revision.replacement.new_plan_confirmed
    assert not decision.revision.replacement.completion_credit_transferred
    assert case.service.decide(case.principal,result.revision.revision_id,request).replayed
    assert physical(pg_engine,(case.old.plan_id,case.new.plan_id))==before
    history=case.service.get_history(case.principal,case.old.plan_id)
    assert history.completion_refs==result.revision.old.completion_refs and history.current_actions is False
    assert case.execution.get_plan(case.principal,case.new.plan_id).state=="draft"


def test_reject_edited_new_proposal_keeps_history(revision_case_factory):
    case=revision_case_factory()
    proposal=case.service.propose(case.principal,case.request).revision
    case.execution.update_workspace(case.principal,case.new.plan_id,WorkspaceInput(expected_version=case.new.state_version,estimate_overrides=(),schedule=None))
    with pytest.raises(RevisionError) as failure:
        case.service.decide(case.principal,proposal.revision_id,DecisionInput(expected_revision_version=1,action="accept",student_confirmed=True))
    assert failure.value.status_code==409
    rejected=case.service.decide(case.principal,proposal.revision_id,DecisionInput(expected_revision_version=1,action="reject",student_confirmed=True))
    assert rejected.revision.status=="rejected" and rejected.revision.replacement is None
    assert case.service.get_history(case.principal,case.old.plan_id).completion_refs


def test_proposal_required_audit_failure_rolls_back(revision_case_factory,pg_engine):
    case=revision_case_factory()
    from services.api.app.audit.models import AuditEvent
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION demo_revision_audit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.action='authorization.owned.execute' AND NEW.object_id='"+str(case.new.plan_id)+"'::uuid THEN RAISE EXCEPTION 'DEMO required failure' USING ERRCODE='23514'; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER demo_revision_audit_fail BEFORE INSERT ON auth_audit_events FOR EACH ROW EXECUTE FUNCTION demo_revision_audit_fail()"))
    try:
        with pytest.raises(Exception) as failure:
            case.service.propose(case.principal,case.request)
        assert failure.value.status_code==503
        with Session(pg_engine) as session:
            assert session.scalar(select(RevisionProposal)) is None
    finally:
        with pg_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER demo_revision_audit_fail ON auth_audit_events"))
            connection.execute(text("DROP FUNCTION demo_revision_audit_fail()"))


def test_revision_migration_constraints_and_parent_heads(revision_case_factory,pg_engine):
    case=revision_case_factory()
    proposal=case.service.propose(case.principal,case.request).revision
    case.service.decide(case.principal,proposal.revision_id,DecisionInput(expected_revision_version=1,action="accept",student_confirmed=True))
    from services.api.app.plan_revisions.store import HEADS
    from sqlalchemy.exc import IntegrityError
    for table in ("revision_proposals","revision_decisions","plan_replacement_links"):
        with pytest.raises(IntegrityError),pg_engine.begin() as connection:
            connection.execute(text('UPDATE "'+table+'" SET audit_event_id=audit_event_id'))
    with pg_engine.connect() as connection:
        old={name:connection.execute(text("SELECT version_num FROM "+name)).scalar_one() for name in HEADS}
    with pg_engine.begin() as connection:
        config=migration_config()
        config.attributes["connection"]=connection
        command.downgrade(config,"base")
    migrate_revisions(pg_engine)
    with pg_engine.connect() as connection:
        assert {name:connection.execute(text("SELECT version_num FROM "+name)).scalar_one() for name in HEADS}==old
    case.service.store.assert_schema_ready()
