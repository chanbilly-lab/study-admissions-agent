"""Real T35 pairs in a dedicated loopback database and fresh schema per case."""

from datetime import timedelta
import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine,inspect,text

from tests.integration.changes.conftest import (
    clock,session_settings_factory,session_settings,runtime,idp,oidc_adapter,
    auth_store,auth_service,actor_factory,privacy_settings,privacy_service,
    catalog_store,catalog_tree,source_store,administrator_factory,source_request_factory,
    blob_root,io_probe,storage_store,storage_factory,idempotency_store,imports_store,
    imports_factory,candidate_factory,evidence_store,evidence_factory,facts_store,
    facts_factory,classification_factory,reviews_store,releases_store,import_case_factory,
    isolate_releases_environment_and_network,profiles_store,assessments_store,
    assessment_case_factory,plans_store,plan_case_factory,execution_store,execution_case_factory,
    changes_store,change_case_factory,
)


@pytest.fixture
def pg_engine():
    raw=os.getenv("T23_TEST_POSTGRES_URL")
    if not raw:
        pytest.fail("T35 requires the dedicated T23_TEST_POSTGRES_URL",pytrace=False)
    parsed=urlsplit(raw)
    if parsed.scheme!="postgresql+psycopg" or parsed.hostname!="127.0.0.1" or parsed.port!=55438 or parsed.path!="/study_t23_20261003":
        pytest.fail("T35 requires the dedicated loopback study_t23_20261003 database",pytrace=False)
    schema="revisions_t35_"+uuid4().hex
    admin=create_engine(raw,hide_parameters=True,connect_args={"connect_timeout":5})
    engine,created=None,False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created=True
        engine=create_engine(raw,hide_parameters=True,connect_args={"options":"-csearch_path="+schema,"connect_timeout":5})
        assert inspect(engine).get_table_names()==[]
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def revisions_store(changes_store,pg_engine):
    from services.api.app.plan_revisions.store import RevisionsStore,migrate_revisions
    migrate_revisions(pg_engine)
    return RevisionsStore(pg_engine)


def ready_workspace(case,value):
    from services.api.app.plan_execution.schemas import WorkspaceInput,ScheduleConfiguration
    from services.api.app.plans.schemas import EstimateOverride
    from services.api.app.plans.schedule_schemas import AvailabilitySlot
    now=case.clock()
    return case.execution.update_workspace(case.principal,value.plan_id,
        WorkspaceInput(expected_version=value.state_version,
            estimate_overrides=tuple(EstimateOverride(task_key=t.task_key,estimated_hours="0.01") for t in value.proposal.effective_draft.tasks),
            schedule=ScheduleConfiguration(horizon_start=now+timedelta(minutes=5),horizon_end=now+timedelta(hours=2),
                display_timezone="UTC",weekly_hours="2",slots=(AvailabilitySlot(slot_id=uuid4(),start_at=now+timedelta(minutes=5),end_at=now+timedelta(minutes=65)),),
                internal_goals=(),availability_confirmed=True,rest_excluded=True)))


@pytest.fixture
def revision_case_factory(revisions_store,change_case_factory):
    from services.api.app.plan_revisions.schemas import RevisionPolicy,ProposeInput
    from services.api.app.plan_revisions.service import RevisionService
    from services.api.app.plan_execution.schemas import ConfirmInput,CompleteInput
    from services.api.app.profiles.schemas import AppendInput
    from services.api.app.plans.schemas import PlanCreateInput

    def make(*,complete_old=True,profile_change=True,**options):
        base=change_case_factory(**options)
        values=dict(vars(base))
        values.update(changes=base.service,execution=base.execution,auth=base.execution.auth_service,clock=base.execution.auth_service.clock)
        case=SimpleNamespace(**values)
        old=ready_workspace(case,base.plan)
        old=case.execution.confirm_plan(case.principal,old.plan_id,ConfirmInput(expected_version=old.state_version,
            expected_draft_sha256=old.proposal.effective_draft.draft_sha256,expected_schedule_sha256=old.proposal.schedule.schedule_sha256,
            confirmed=True,acknowledge_unverified_deadlines=True),SecretStr("DEMO_T35_OLD_CONFIRM")).execution
        if complete_old:
            first=next(t for t in old.proposal.effective_draft.tasks if not t.dependency_keys)
            old=case.execution.complete_task(case.principal,old.plan_id,first.task_key,
                CompleteInput(expected_version=old.state_version,confirmed=True)).execution
        if profile_change:
            payload=case.profile.profile.model_dump()
            payload["weekly_hours"]="12" if payload["weekly_hours"]!="12" else "13"
            profile=case.profiles.append_version(case.principal,case.profile.profile_id,
                AppendInput(expected_current_version=case.profile.version,profile=payload,confirmed=True)).version
        else:
            profile=case.profile
        from services.api.app.rules.schemas import AssessmentRequest
        request=AssessmentRequest(profile_id=profile.profile_id,profile_version_id=profile.version_id,target=case.assessment.target,
            release_id=case.release.release_id,stage=case.assessment.stage,confirmed=True,
            **{name:getattr(case.bundle.scope,name) for name in ("intake","application_cycle","channel","exam_system","subject_scope","batch_group")})
        assessment=case.eligibility.evaluate(case.principal,request)
        new=case.execution.create_plan(case.principal,PlanCreateInput(assessment_ids=(assessment.assessment_id,),confirmed=True))
        service=RevisionService(case.execution,case.changes,revisions_store,RevisionPolicy(enabled=True,allow_test_revisions=True))
        values=dict(vars(case))
        values.update(service=service,old=old,new=new,old_plan=old,new_plan=new,new_profile=profile,new_assessment=assessment,
            request=ProposeInput(old_plan_id=old.plan_id,new_plan_id=new.plan_id,expected_old_state_version=old.state_version,
                expected_new_state_version=new.state_version,student_confirmed=True))
        return SimpleNamespace(**values)
    return make
