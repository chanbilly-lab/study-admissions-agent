"""Independent T31 boundary tests: a capacity proposal is not plan authority."""

from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from pathlib import Path
import socket
import subprocess
import sys
from uuid import UUID

import pytest
from pydantic import TypeAdapter

from app.plans.schemas import EstimateOverride, PlanDraft, plan_draft_fingerprint
from app.plans.schedule_schemas import (AvailabilitySlot, InternalGoal, ScheduleDraft, ScheduleError,
    ScheduleInput, schedule_fingerprint)
from app.plans.scheduler import schedule_plan
from app.rules.assessment_engine import EligibilityEngineResult
from tests.unit.planning.test_t30_safety import NOW, assessment, build, rehash


SENTINEL = "DEMO_T31_PRIVATE_SENTINEL"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("T31 safety tests must not connect to a network")
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


def case(*, status="eligible", validity="current", estimated="0.25"):
    source, rule = assessment(status, validity=validity)
    draft = build(source, rules=(rule,))
    draft = build(source, rules=(rule,), estimate_overrides=tuple(
        EstimateOverride(task_key=task.task_key, estimated_hours=estimated) for task in draft.tasks))
    return source, draft


def request(source=None, draft=None, **updates):
    if source is None:
        source, draft = case()
    values = dict(draft=draft, assessments=(source,), generated_at=NOW,
        horizon_start=NOW, horizon_end=NOW+timedelta(minutes=45), display_timezone="UTC",
        availability_confirmed=True, rest_excluded=True, weekly_hours="1",
        slots=(AvailabilitySlot(slot_id=UUID(int=701), start_at=NOW,
            end_at=NOW+timedelta(minutes=30)),), internal_goals=())
    values.update(updates)
    # The public function must recursively validate copied/constructed objects.
    return ScheduleInput.model_construct(**values)


def changed_draft(draft, **updates):
    values = dict(draft.__dict__)
    values.update(updates)
    values["draft_sha256"] = plan_draft_fingerprint(TypeAdapter(dict).dump_python(values, mode="json"))
    return PlanDraft.model_construct(**values)


def rejected(value, status=422):
    with pytest.raises(ScheduleError) as failure:
        schedule_plan(value)
    assert failure.value.status_code == status
    assert failure.value.code == {422:"INVALID_SCHEDULE_INPUT",409:"SCHEDULE_SOURCE_CONFLICT",503:"SCHEDULE_UNAVAILABLE"}[status]
    assert SENTINEL not in str(failure.value)+repr(failure.value)


def test_proposal_is_bound_to_original_input_and_does_not_mutate_or_confirm_it():
    original = request()
    before = original.model_dump(mode="json")
    output = schedule_plan(original)
    assert output.status == "ready" and output.confirmed is False
    assert output.constraints_complete is False
    assert output.draft_sha256 == original.draft.draft_sha256
    assert original.model_dump(mode="json") == before
    assert original.draft.confirmed is False and original.draft.scheduled is False


@pytest.mark.parametrize("field,value", [("availability_confirmed",1),("rest_excluded",1),
    ("availability_confirmed",False),("rest_excluded",False),
    ("weekly_hours",True),("weekly_hours",1),("weekly_hours",1.0),("weekly_hours",Decimal("1")),
    ("weekly_hours","40.000001"),("weekly_hours","-1"),("weekly_hours","1e0"),
    ("weekly_hours","0.0000001"),("weekly_hours",SENTINEL)])
def test_capacity_and_availability_confirmation_are_exact_declared_inputs(field,value):
    rejected(request(**{field:value}))


@pytest.mark.parametrize("zone", ["", "PST", "+08:00", "../UTC", "Europe/../London", "UTC\n", SENTINEL])
def test_display_zone_is_explicit_supported_iana_and_never_a_path_or_offset(zone):
    rejected(request(display_timezone=zone))


@pytest.mark.parametrize("field", ["generated_at","horizon_start","horizon_end"])
def test_clock_input_does_not_accept_string_epoch_or_naive_datetime(field):
    for value in (NOW.isoformat(), 1791115200, NOW.replace(tzinfo=None)):
        rejected(request(**{field:value}))


def test_custom_timezone_is_rejected_before_any_offset_or_dst_callback():
    calls=[]
    class EvilTimezone(tzinfo):
        def utcoffset(self, current):
            calls.append(SENTINEL)
            raise AssertionError(SENTINEL)
        def dst(self, current):
            calls.append(SENTINEL)
            raise AssertionError(SENTINEL)
    forged=datetime(2026,10,4,12,tzinfo=EvilTimezone())
    for field in ("generated_at","horizon_start","horizon_end"):
        rejected(request(**{field:forged}))
    valid=request()
    forged_slot=valid.slots[0].model_copy(update={"start_at":forged})
    rejected(request(slots=(forged_slot,)))
    goal=InternalGoal.model_construct(task_key=valid.draft.tasks[0].task_key,due_at=forged)
    rejected(request(internal_goals=(goal,)))
    assert calls==[]


def test_utc_fields_do_not_accept_folded_or_local_zoneinfo_wall_times():
    from zoneinfo import ZoneInfo
    for value in (NOW.replace(fold=1),NOW.replace(tzinfo=timezone(timedelta(hours=8))),
                  NOW.replace(tzinfo=ZoneInfo("Europe/London"))):
        rejected(request(generated_at=value))


@pytest.mark.parametrize("tamper", ["original_hash","nested_flag","estimate","source_hash"])
def test_constructed_nested_objects_cannot_bypass_original_hash_or_exact_flags(tamper):
    source,draft=case()
    if tamper=="original_hash":
        draft=draft.model_copy(update={"draft_sha256":"0"*64})
    elif tamper=="source_hash":
        source=source.model_copy(update={"result_sha256":"0"*64})
    else:
        task=draft.tasks[0].model_copy(update={"confirmed":1} if tamper=="nested_flag" else {"estimated_hours":SENTINEL})
        draft=changed_draft(draft,tasks=(task,))
    rejected(request(source,draft),409 if tamper=="source_hash" else 422)


@pytest.mark.parametrize("field,value", [("release_id",UUID(int=9991)),("requirements_version","c"*64),
    ("ruleset_version","d"*64),("stage","enrollment"),("eligibility_status","ineligible")])
def test_current_source_projection_cannot_be_replaced_even_after_rehashing_draft(field,value):
    source,draft=case()
    ref=draft.assessment_refs[0].model_copy(update={field:value})
    forged=changed_draft(draft,assessment_refs=(ref,))
    # The source and the forged draft each have valid hashes; only their binding is wrong.
    PlanDraft.model_validate(forged)
    rejected(request(source,forged),409)


def test_complete_target_and_rule_reference_projection_is_checked_beyond_source_hash():
    source,draft=case()
    ref=draft.assessment_refs[0]
    for target in (ref.target.model_copy(update={"offering_id":UUID(int=9992)}),
                   ref.target.model_copy(update={"scope_sha256":"e"*64})):
        forged=changed_draft(draft,assessment_refs=(ref.model_copy(update={"target":target}),))
        PlanDraft.model_validate(forged)
        rejected(request(source,forged),409)
    rule=ref.rule_refs[0].model_copy(update={"evidence_ids":(UUID(int=9993),)})
    forged=changed_draft(draft,assessment_refs=(ref.model_copy(update={"rule_refs":(rule,)}),))
    PlanDraft.model_validate(forged)
    rejected(request(source,forged),409)


@pytest.mark.parametrize("state", ["needs_review","replaced","withdrawn"])
def test_current_validity_change_cannot_reuse_an_old_action_draft(state):
    source,draft=case()
    current=source.model_copy(update={"current_validity":state})
    assert current.result_sha256==source.result_sha256
    rejected(request(current,draft),409)


def test_valid_new_historical_draft_may_schedule_only_its_verification_task():
    source,draft=case(validity="withdrawn")
    assert {task.action_code for task in draft.tasks}=={"VERIFY_HISTORY"}
    output=schedule_plan(request(source,draft))
    assert output.status=="ready" and output.confirmed is False
    assert not draft.deadline_refs and output.assessment_refs==draft.assessment_refs


def test_unavailable_current_rules_are_verification_without_invented_preparation():
    source,_=assessment("unknown")
    source=rehash(source,binding_mode="unavailable",ruleset_version=None,rule_refs=(),current_validity="unavailable",
        eligibility=EligibilityEngineResult(status="unknown",reason="RULESET_UNAVAILABLE",evaluation=None,obligations=()))
    draft=build(source)
    draft=build(source,estimate_overrides=tuple(EstimateOverride(task_key=t.task_key,estimated_hours="0.25") for t in draft.tasks))
    output=schedule_plan(request(source,draft))
    assert output.status=="ready"
    assert {task.action_code for task in draft.tasks}=={"VERIFY_UNKNOWN"}
    assert output.assessment_refs==draft.assessment_refs and not output.deadline_refs


def test_cross_profile_and_cross_mode_drafts_are_not_schedule_authority():
    source,draft=case()
    for changes in ({"profile_id":UUID(int=9994)},{"profile_version_id":UUID(int=9995)},
                    {"profile_sha256":"f"*64},{"is_synthetic":False}):
        forged=changed_draft(draft,**changes)
        PlanDraft.model_validate(forged)
        rejected(request(source,forged),409)


def test_extra_or_duplicate_server_assessments_do_not_form_a_loose_membership_check():
    source,draft=case()
    another,_=assessment("eligible",index=2)
    rejected(request(source,draft,assessments=(source,source)),409)
    rejected(request(source,draft,assessments=(source,another)),409)
    rejected(request(source,draft,assessments=()))


def test_schedule_must_be_generated_within_the_exact_original_draft_and_source_lifetime():
    source,draft=case()
    for generated in (draft.generated_at-timedelta(microseconds=1),draft.expires_at):
        rejected(request(source,draft,generated_at=generated,horizon_start=generated,
            horizon_end=generated+timedelta(minutes=1),slots=()))


def test_fresh_source_deadline_is_checked_even_when_both_original_hashes_match():
    source,draft=case()
    for changes in ({"expires_at":NOW+timedelta(minutes=30)},
                    {"assessment_at":NOW+timedelta(microseconds=1)}):
        fresh=rehash(source,**changes)
        reference=draft.assessment_refs[0].model_copy(update={"result_sha256":fresh.result_sha256})
        bound=changed_draft(draft,assessment_refs=(reference,))
        PlanDraft.model_validate(bound)
        rejected(request(fresh,bound),409)


def test_availability_resource_budgets_are_checked_without_rounding_or_unbounded_work():
    source,_=assessment("eligible")
    source=rehash(source,expires_at=NOW+timedelta(days=90))
    draft=build(source)
    slots=tuple(AvailabilitySlot(slot_id=UUID(int=1000+index),start_at=NOW+timedelta(hours=8*index),
        end_at=NOW+timedelta(hours=8*(index+1))) for index in range(66))
    rejected(request(source,draft,horizon_end=NOW+timedelta(days=84),slots=slots))
    rejected(request(source,draft,horizon_end=NOW+timedelta(days=84,microseconds=1),slots=()))
    bad=AvailabilitySlot.model_construct(slot_id=UUID(int=701),start_at=NOW,
        end_at=NOW+timedelta(hours=8,microseconds=1))
    rejected(request(source,draft,horizon_end=NOW+timedelta(days=1),slots=(bad,)))


def test_week_boundary_overflow_fails_closed_with_a_bounded_safe_error():
    at=datetime(9999,12,30,12,tzinfo=timezone.utc)
    source,_=assessment("eligible")
    source=rehash(source,assessment_at=at-timedelta(minutes=1),expires_at=at+timedelta(hours=1))
    draft=build(source,generated_at=at)
    raw=request(source,draft,generated_at=at,horizon_start=at,horizon_end=at+timedelta(minutes=45),
        slots=(AvailabilitySlot(slot_id=UUID(int=701),start_at=at,end_at=at+timedelta(minutes=30)),))
    rejected(raw)


def test_cycle_and_unknown_dependency_are_rejected_before_any_partial_proposal():
    source,draft=case(status="conditional")
    first,second=draft.tasks
    cyclic=(first.model_copy(update={"dependency_keys":(second.task_key,)}),
            second.model_copy(update={"dependency_keys":(first.task_key,)}))
    rejected(request(source,changed_draft(draft,tasks=cyclic)))
    missing=first.model_copy(update={"dependency_keys":("f"*64,)})
    rejected(request(source,changed_draft(draft,tasks=(missing,second))))


def test_duplicate_or_overlapping_slots_and_unknown_internal_task_are_rejected():
    original=request()
    slot=original.slots[0]
    rejected(request(slots=(slot,slot)))
    overlap=slot.model_copy(update={"slot_id":UUID(int=702),"start_at":NOW+timedelta(minutes=15),
        "end_at":NOW+timedelta(minutes=45)})
    rejected(request(slots=(slot,overlap)))
    goal=InternalGoal(task_key="f"*64,due_at=NOW+timedelta(minutes=30))
    rejected(request(internal_goals=(goal,)))


@pytest.mark.parametrize("field", ["slots","assessments","internal_goals"])
def test_non_native_container_is_rejected_without_running_iteration_callbacks(field):
    calls=[]
    class EvilList(list):
        def __iter__(self):
            calls.append(SENTINEL)
            raise AssertionError(SENTINEL)
    original=request()
    rejected(request(**{field:EvilList(getattr(original,field))}))
    assert calls==[]


def test_over_budget_sequences_are_rejected_before_visiting_attacker_items():
    calls=[]
    class EvilItem:
        def __getattribute__(self,name):
            calls.append(SENTINEL)
            raise AssertionError(SENTINEL)
    for field,maximum in (("slots",256),("assessments",4),("internal_goals",100)):
        rejected(request(**{field:(EvilItem(),)*(maximum+1)}))
    assert calls==[]


def output_with_hash(output, **changes):
    values=dict(output.__dict__)
    values.update(changes)
    values["schedule_sha256"]=schedule_fingerprint(TypeAdapter(dict).dump_python(values,mode="json"))
    return ScheduleDraft.model_construct(**values)


@pytest.mark.parametrize("tamper", ["weekly_over_limit","week_capacity_mismatch","outside_horizon",
    "task_bounds","wrong_local_week","missing_dependency"])
def test_rehash_does_not_make_a_structurally_impossible_schedule_output_valid(tamper):
    from pydantic import ValidationError
    output=schedule_plan(request())
    ScheduleDraft.model_validate(output)
    changes={}
    if tamper=="weekly_over_limit":
        changes={"weekly_hours":"41","weeks":tuple(week.model_copy(update={
            "capacity_microseconds":41*3_600_000_000}) for week in output.weeks)}
    elif tamper=="week_capacity_mismatch":
        changes={"weeks":tuple(week.model_copy(update={"capacity_microseconds":2*3_600_000_000})
            for week in output.weeks)}
    elif tamper=="outside_horizon":
        allocation=output.allocations[0]
        moved=allocation.model_copy(update={"start_at":allocation.start_at-timedelta(minutes=1),
            "end_at":allocation.end_at-timedelta(minutes=1)})
        task=output.tasks[0].model_copy(update={"start_at":moved.start_at,"end_at":moved.end_at})
        changes={"allocations":(moved,),"tasks":(task,)}
    elif tamper=="task_bounds":
        task=output.tasks[0].model_copy(update={"start_at":output.tasks[0].start_at+timedelta(minutes=1)})
        changes={"tasks":(task,)}
    elif tamper=="wrong_local_week":
        incorrect=output.weeks[0].week_start-timedelta(days=7)
        changes={"weeks":(output.weeks[0].model_copy(update={"week_start":incorrect}),),
            "allocations":tuple(item.model_copy(update={"week_start":incorrect}) for item in output.allocations)}
    else:
        changes={"tasks":(output.tasks[0].model_copy(update={"dependency_keys":("f"*64,)}),)}
    with pytest.raises(ValidationError):
        ScheduleDraft.model_validate(output_with_hash(output,**changes))


@pytest.mark.parametrize("tamper", ["overlap","cycle","dependency_finish_after_child_start"])
def test_output_graph_and_actual_intervals_are_checked_after_rehash(tamper):
    from pydantic import ValidationError
    source,draft=case(status="conditional")
    output=schedule_plan(request(source,draft))
    assert output.status=="ready" and len(output.allocations)==2
    parent=next(task for task in output.tasks if not task.dependency_keys)
    child=next(task for task in output.tasks if task.dependency_keys)
    if tamper=="cycle":
        changed=tuple(task.model_copy(update={"dependency_keys":(child.task_key,)})
            if task.task_key==parent.task_key else task for task in output.tasks)
        forged=output_with_hash(output,tasks=changed)
    else:
        child_allocation=next(item for item in output.allocations if item.task_key==child.task_key)
        shift=timedelta(minutes=15) if tamper=="overlap" else timedelta(minutes=30)
        moved=child_allocation.model_copy(update={"start_at":child_allocation.start_at-shift,
            "end_at":child_allocation.end_at-shift})
        child_update=child.model_copy(update={"start_at":moved.start_at,"end_at":moved.end_at,
            "dependency_keys":() if tamper=="overlap" else child.dependency_keys})
        allocations=tuple(moved if item.task_key==child.task_key else item for item in output.allocations)
        tasks=tuple(child_update if item.task_key==child.task_key else item for item in output.tasks)
        # In the dependency case widen the output horizon so it is independently legal.
        horizon_start=output.horizon_start-timedelta(minutes=15) if tamper!="overlap" else output.horizon_start
        generated_at=output.generated_at-timedelta(minutes=15) if tamper!="overlap" else output.generated_at
        forged=output_with_hash(output,tasks=tasks,allocations=allocations,
            horizon_start=horizon_start,generated_at=generated_at)
    with pytest.raises(ValidationError):
        ScheduleDraft.model_validate(forged)


def test_pure_scheduler_import_is_independent_of_database_model_provider_and_m0():
    code=r'''
import builtins, os, socket, sys
from importlib.util import find_spec
from pathlib import Path
sys.path.insert(0,sys.argv[1])
original=builtins.__import__
def guarded(name,*args,**kwargs):
    package=(args[0] or {}).get('__package__','') if args else ''
    if name.split('.')[0] in {'sqlalchemy','psycopg'} or name in {'app.database','app.models','app.planning','app.seed'} or name.startswith('app.providers') or (name.startswith('providers') and package.startswith('app')):
        raise AssertionError('Unexpected business IO import: '+name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
def forbidden(*args,**kwargs): raise AssertionError('Unexpected network IO')
socket.socket.connect=forbidden
socket.getaddrinfo=forbidden
os.environ.update(PLANS_DATABASE_URL='DEMO_T31_PRIVATE_SENTINEL',V2_DATA_MODE='verified',LLM_API_KEY='DEMO_T31_PRIVATE_SENTINEL')
from app.plans.scheduler import schedule_plan
assert callable(schedule_plan)
assert Path(find_spec('app.planning').origin)==Path(sys.argv[1])/'app'/'planning.py'
assert not any(name.startswith(('sqlalchemy','psycopg','app.providers','app.database','app.planning','app.seed')) for name in sys.modules)
print('scheduler import isolated')
'''
    api=Path(__file__).resolve().parents[3]/"services"/"api"
    result=subprocess.run([sys.executable,"-I","-B","-c",code,str(api)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=="scheduler import isolated"
