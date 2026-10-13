"""Actual PostgreSQL atomicity, immutable drafts and independent migration chain."""

from copy import deepcopy
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.auth.models import AuthOwnedResource
from services.api.app.plans.models import PlansBase, PlanRoot, PlanVersion, PlanTask, PlanSourceAssessment, PlanTaskDependency
from services.api.app.plans.schemas import PlanError
from services.api.app.plans.store import HEADS, migrate_plans, migration_config

pytestmark = pytest.mark.postgres


def count(engine, table):
    with engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM " + table)).scalar_one()


def test_real_draft_stores_five_relations_and_owner_registry(plan_case_factory, pg_engine):
    case = plan_case_factory()
    result = case.service.create_draft(case.principal, case.request)
    assert result.version == 1 and result.draft.status == "draft"
    assert result.draft.confirmed is False and result.draft.scheduled is False
    assert result == case.service.get_draft(case.principal, result.plan_id)
    with Session(pg_engine) as session:
        registry = session.get(AuthOwnedResource, result.plan_id)
        assert (registry.owner_user_id,registry.resource_type,registry.status) == (case.principal.user_id,"plan","active")
        assert session.get(PlanVersion,result.version_id).draft_sha256 == result.draft.draft_sha256
        source = session.scalar(select(PlanSourceAssessment))
        assert (source.assessment_id,source.result_sha256) == (case.assessment.assessment_id,case.assessment.result_sha256)
        assert session.scalars(select(PlanTask)).all()
    assert count(pg_engine,"plan_draft_roots") == count(pg_engine,"plan_draft_versions") == 1


def test_actual_conditional_has_independent_native_deadlines_and_same_version_dependencies(plan_case_factory, pg_engine):
    expr = {"op":"gte","field":{"name":"assessment","key":"math","basis":"achieved"},
            "value":{"kind":"decimal","value":"100","unit":"points","scale":"150"}}
    case = plan_case_factory(expression=expr,deferral=True)
    assert case.assessment.eligibility.status == "conditional"
    result = case.service.create_draft(case.principal,case.request)
    assert {d.purpose for d in result.draft.deadline_refs} == {"application","supplement"}
    assert len({d.event_id for d in result.draft.deadline_refs}) == 2
    assert all(d.date_event.utc_instant is None for d in result.draft.deadline_refs)
    assert all(d.date_event.calculated_utc_instant is not None for d in result.draft.deadline_refs)
    assert case.service.get_draft(case.principal,result.plan_id) == result
    with Session(pg_engine) as session:
        edges = session.scalars(select(PlanTaskDependency)).all()
        assert len(edges) == 1 and edges[0].version_id == result.version_id
        assert session.get(PlanTask,(result.version_id,edges[0].dependency_key)).payload["action_code"] == "OBTAIN_ACHIEVED"


def test_required_final_audit_failure_rolls_back_domain_and_registry(plan_case_factory,pg_engine):
    case = plan_case_factory()
    with pg_engine.begin() as connection:
        connection.execute(text("""CREATE FUNCTION t30_fail_final_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF NEW.object_type='plan' AND EXISTS(SELECT 1 FROM plan_draft_versions) THEN RAISE EXCEPTION 'required failure' USING ERRCODE='23514'; END IF; RETURN NEW; END $$"""))
        connection.execute(text("CREATE TRIGGER t30_fail_final_audit BEFORE INSERT ON auth_audit_events FOR EACH ROW EXECUTE FUNCTION t30_fail_final_audit()"))
    with pytest.raises(Exception) as error:
        case.service.create_draft(case.principal,case.request)
    assert error.value.status_code == 503
    assert all(count(pg_engine,table)==0 for table in PlansBase.metadata.tables)
    with Session(pg_engine) as session:
        assert session.scalars(select(AuthOwnedResource).where(AuthOwnedResource.resource_type=="plan")).all() == []


def test_deferred_commit_failure_never_returns_success(plan_case_factory,pg_engine):
    case = plan_case_factory()
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t30_commit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'deferred failure' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t30_commit_fail AFTER INSERT ON plan_draft_roots DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t30_commit_fail()"))
    with pytest.raises(PlanError) as error:
        case.service.create_draft(case.principal,case.request)
    assert error.value.status_code == 503
    assert count(pg_engine,"plan_draft_roots") == count(pg_engine,"plan_draft_versions") == 0


def test_caller_commit_and_rollback_include_all_domain_rows(plan_case_factory,pg_engine):
    case = plan_case_factory()
    with Session(pg_engine) as session:
        with session.begin():
            first = case.service.create_draft(case.principal,case.request,session=session)
            assert count(pg_engine,"plan_draft_roots") == 0
        assert count(pg_engine,"plan_draft_roots") == 1
        with pytest.raises(RuntimeError):
            with session.begin():
                case.service.create_draft(case.principal,case.request,session=session)
                raise RuntimeError("caller abort")
    assert count(pg_engine,"plan_draft_roots") == 1
    assert case.service.get_draft(case.principal,first.plan_id).plan_id == first.plan_id


def test_new_confirmed_profile_version_blocks_old_assessment_create_and_read(plan_case_factory,pg_engine):
    from services.api.app.profiles.schemas import AppendInput
    case=plan_case_factory()
    original=case.service.create_draft(case.principal,case.request)
    payload=case.profile.profile.model_dump(mode="json")
    payload["weekly_hours"]="0"
    updated=case.profiles.append_version(case.principal,case.profile.profile_id,
        AppendInput(profile=payload,confirmed=True,expected_current_version=case.profile.version))
    assert updated.version.version==2
    for operation in (lambda:case.service.create_draft(case.principal,case.request),
                      lambda:case.service.get_draft(case.principal,original.plan_id)):
        with pytest.raises(PlanError) as error:
            operation()
        assert error.value.status_code==409
    assert count(pg_engine,"plan_draft_roots")==1
    assert count(pg_engine,"student_profile_versions")==2


@pytest.mark.parametrize("table",list(PlansBase.metadata.tables))
def test_all_persisted_draft_relations_reject_update(plan_case_factory,pg_engine,table):
    expr = {"op":"gte","field":{"name":"assessment","key":"math","basis":"achieved"},
            "value":{"kind":"decimal","value":"100","unit":"points","scale":"150"}}
    case = plan_case_factory(expression=expr,deferral=True)
    result = case.service.create_draft(case.principal,case.request)
    column = "task_key" if table in {"plan_draft_tasks","plan_draft_dependencies"} else "assessment_id" if table=="plan_draft_assessments" else "id"
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as connection:
            connection.execute(text(f"UPDATE {table} SET {column}={column}"))
    assert case.service.get_draft(case.principal,result.plan_id) == result


def test_checks_reject_missing_marker_and_cross_version_dependency(plan_case_factory,pg_engine):
    case = plan_case_factory()
    result = case.service.create_draft(case.principal,case.request)
    with Session(pg_engine) as session:
        row = session.get(PlanVersion,result.version_id)
        payload = deepcopy(row.payload)
        payload.pop("confirmed")
        values = {c.name:getattr(row,c.name) for c in PlanVersion.__table__.columns}
    for malformed in (payload,{**payload,"confirmed":"false"}):
        values.update(id=uuid4(),version=2,payload=malformed)
        with pytest.raises(IntegrityError) as error:
            with Session(pg_engine) as session,session.begin():
                session.add(PlanVersion(**values));session.flush()
        assert error.value.orig.diag.constraint_name == "ck_plan_version_markers"
    with pytest.raises(IntegrityError) as error:
        with Session(pg_engine) as session,session.begin():
            task=result.draft.tasks[0].model_dump(mode="json")
            task.pop("confirmed")
            session.add(PlanTask(version_id=result.version_id,plan_id=result.plan_id,
                task_key="e"*64,ordinal=2,payload=task,payload_sha256="e"*64));session.flush()
    assert error.value.orig.diag.constraint_name == "ck_plan_task_payload"
    with pytest.raises(IntegrityError):
        with Session(pg_engine) as session,session.begin():
            session.add(PlanTaskDependency(version_id=result.version_id,plan_id=result.plan_id,
                task_key=result.draft.tasks[0].task_key,dependency_key="f"*64));session.flush()
    # A bad new INSERT may recompute the draft hash; exact T28 target binding
    # still prevents presenting it and aborts all caller-owned inserts.
    from services.api.app.plans.schemas import plan_draft_fingerprint
    with pytest.raises(PlanError) as error:
        with Session(pg_engine) as session,session.begin():
            old_root=session.get(PlanRoot,result.plan_id)
            old_version=session.get(PlanVersion,result.version_id)
            wrong=deepcopy(old_version.payload)
            wrong["assessment_refs"][0]["target"]["country"]="GB"
            wrong["draft_sha256"]=plan_draft_fingerprint(wrong)
            new_root,new_version=uuid4(),uuid4()
            session.add(AuthOwnedResource(id=new_root,owner_user_id=case.principal.user_id,
                resource_type="plan",status="active",version=1,is_synthetic=True,parent_id=None))
            session.flush()
            root_values={c.name:getattr(old_root,c.name) for c in PlanRoot.__table__.columns}
            root_values.update(id=new_root,current_version_id=new_version)
            session.add(PlanRoot(**root_values));session.flush()
            version_values={c.name:getattr(old_version,c.name) for c in PlanVersion.__table__.columns}
            version_values.update(id=new_version,plan_id=new_root,payload=wrong,draft_sha256=wrong["draft_sha256"])
            session.add(PlanVersion(**version_values));session.flush()
            for item in session.scalars(select(PlanTask).where(PlanTask.version_id==result.version_id)).all():
                task_values={c.name:getattr(item,c.name) for c in PlanTask.__table__.columns}
                task_values.update(version_id=new_version,plan_id=new_root)
                session.add(PlanTask(**task_values))
            session.add(PlanSourceAssessment(version_id=new_version,plan_id=new_root,
                assessment_id=case.assessment.assessment_id,result_sha256=case.assessment.result_sha256))
            session.flush()
            case.service.get_draft(case.principal,new_root,session=session)
    assert error.value.status_code==503
    assert count(pg_engine,"plan_draft_roots")==1
    with Session(pg_engine) as session:
        assert session.get(AuthOwnedResource,new_root) is None


def test_migration_round_trip_preserves_eleven_heads_and_old_rows(plans_store,plan_case_factory,pg_engine):
    case = plan_case_factory()
    result = case.service.create_draft(case.principal,case.request)
    with pg_engine.connect() as connection:
        before={table:connection.execute(text("SELECT version_num FROM "+table)).scalars().all() for table in HEADS}
    tables_before = set(inspect(pg_engine).get_table_names())
    with pg_engine.begin() as connection:
        config=migration_config();config.attributes["connection"]=connection
        command.current(config)
        command.downgrade(config,"base")
    assert not set(PlansBase.metadata.tables) & set(inspect(pg_engine).get_table_names())
    migrate_plans(pg_engine)
    plans_store.assert_schema_ready()
    assert set(inspect(pg_engine).get_table_names()) == tables_before
    with pg_engine.connect() as connection:
        after={table:connection.execute(text("SELECT version_num FROM "+table)).scalars().all() for table in HEADS}
        assert before==after
        assert connection.execute(text("SELECT result_sha256 FROM eligibility_assessments WHERE id=:id"),{"id":case.assessment.assessment_id}).scalar_one()==case.assessment.result_sha256
    # Only this isolated test draft was removed; pre-existing domain history survived.
    assert count(pg_engine,"plan_draft_roots")==0


def test_trusted_delete_removes_only_draft_children(plan_case_factory,pg_engine):
    case=plan_case_factory()
    result=case.service.create_draft(case.principal,case.request)
    with pg_engine.begin() as connection:
        for table in ("plan_draft_dependencies","plan_draft_assessments","plan_draft_tasks","plan_draft_versions"):
            connection.execute(text("DELETE FROM "+table+" WHERE plan_id=:id"),{"id":result.plan_id})
        connection.execute(text("DELETE FROM plan_draft_roots WHERE id=:id"),{"id":result.plan_id})
    assert count(pg_engine,"eligibility_assessments")==1
    assert count(pg_engine,"student_profile_versions")==1
