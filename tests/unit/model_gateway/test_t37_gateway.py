"""Golden finite DTO and offline quota accounting, without database fixtures."""

import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.app.model_gateway.budget import BudgetLedger
from services.api.app.model_gateway.schemas import (
    BudgetKey,BudgetPolicy,Claim,EvidenceAtom,GatewayError,GatewayPolicy,
    ModelRequest,ModelScope,ProviderResponse,StructuredAnswer,input_units,
)


def request(*,value="DEMO：明确合成的公开资料",question="请说明这条合成资料",count=1):
    scope=ModelScope(dataset_id=uuid4(),entry_year=2027,offering_id=uuid4(),offering_version=1)
    return ModelRequest(scope=scope,question=question,evidence=tuple(EvidenceAtom(
        citation_id=uuid4(),version=1,scope=scope,kind="text",value=value,is_synthetic=True)
        for _ in range(count)))


def key():
    return BudgetKey(key_id=uuid4())


class Clock:
    now=100.0
    def __call__(self):
        return self.now


@pytest.mark.parametrize("environment,data,mode",[
    ("test","verified","mock"),("production","demo","disabled"),
    ("production","demo","live"),
])
def test_gateway_policy_rejects_cross_modes(environment,data,mode):
    with pytest.raises(ValidationError):
        GatewayPolicy(app_environment=environment,data_mode=data,model_mode=mode)


def test_full_request_limits_are_valid_and_preserve_raw_text():
    value=request(count=20,question="问"*1000,value="原文"*1000)
    assert len(value.evidence)==20 and value.question=="问"*1000
    assert all(atom.value=="原文"*1000 and atom.scope==value.scope for atom in value.evidence)
    assert ModelRequest.model_validate(value)==value


@pytest.mark.parametrize("status,claims",[("answered",()),("unknown",(True,))])
def test_answer_status_has_exact_claim_coherence(status,claims):
    with pytest.raises(ValidationError):
        StructuredAnswer(status=status,claims=claims,advice_codes=())


def test_answer_keeps_fixed_advice_and_plain_text():
    claim=Claim(citation_id=uuid4(),value="DEMO 数值 0")
    answer=StructuredAnswer(status="answered",claims=(claim,),advice_codes=("REVIEW_SOURCE",))
    assert answer.claims==(claim,)
    with pytest.raises(ValidationError):
        Claim(citation_id=claim.citation_id,value="<script>DEMO</script>")
    with pytest.raises(ValidationError):
        StructuredAnswer(status="unknown",claims=(),advice_codes=("CONFIRM_WITH_INSTITUTION",)*2)


def test_input_reserves_full_utf8_json_not_characters_or_usage():
    value=request()
    amount=input_units(value)
    assert amount==len(value.model_dump_json().encode("utf-8"))
    assert amount>len(value.model_dump_json())>len(value.question)
    assert "明确合成" not in repr(value)


def test_zero_usage_never_refunds_reserved_per_key_or_global_quota():
    policy=BudgetPolicy(request_limit=1,global_request_limit=2,max_output_tokens=512)
    ledger=BudgetLedger(policy,clock=Clock())
    first=key();units=input_units(request())
    reservation=ledger.reserve(first,units)
    ledger.finish(reservation,"OK",input_usage=0,output_usage=0)
    ledger.release(reservation)
    assert ledger.snapshot(first).requests==1
    assert (ledger.snapshot().input_units,ledger.snapshot().output_tokens)==(units,512)
    with pytest.raises(GatewayError) as failure:
        ledger.reserve(first,units)
    assert failure.value.code=="BUDGET_EXHAUSTED"
    second=ledger.reserve(key(),units)
    ledger.finish(second,"PROVIDER_FAILURE");ledger.release(second)
    with pytest.raises(GatewayError) as failure:
        ledger.reserve(key(),units)
    assert failure.value.code=="BUDGET_EXHAUSTED"
    assert ledger.snapshot().requests==2


def test_window_roll_keeps_real_inflight_and_reclaims_only_idle_keys():
    clock=Clock();ledger=BudgetLedger(BudgetPolicy(max_keys=1,window_seconds=10,
        concurrency_limit=1,global_concurrency_limit=1),clock=clock)
    original=key();active=ledger.reserve(original,100)
    clock.now+=10
    assert ledger.snapshot().inflight==1 and ledger.snapshot().requests==0
    with pytest.raises(GatewayError) as failure:
        ledger.reserve(key(),100)
    assert failure.value.code=="KEY_LIMIT"
    ledger.finish(active,"MODEL_TIMEOUT");ledger.release(active)
    clock.now+=10
    replacement=ledger.reserve(key(),100)
    ledger.finish(replacement,"PROVIDER_FAILURE");ledger.release(replacement)
    assert ledger.snapshot().key_count==1


@pytest.mark.parametrize("now",[99.0,float("nan"),float("inf"),True])
def test_bad_monotonic_clock_closes_budget_without_reset(now):
    clock=Clock();ledger=BudgetLedger(clock=clock)
    active=ledger.reserve(key(),100)
    ledger.finish(active,"PROVIDER_FAILURE");ledger.release(active)
    clock.now=now
    with pytest.raises(GatewayError) as failure:
        ledger.snapshot()
    assert failure.value.code=="BUDGET_UNAVAILABLE"
    clock.now=200
    with pytest.raises(GatewayError):
        ledger.reserve(key(),100)
    assert len(ledger.history)==1


def test_history_has_only_usage_and_fixed_reason_and_is_bounded():
    ledger=BudgetLedger(BudgetPolicy(history_limit=1),clock=Clock())
    identity=key()
    for reason in ("MODEL_TIMEOUT","PROVIDER_FAILURE"):
        active=ledger.reserve(identity,100)
        ledger.finish(active,reason);ledger.release(active)
    assert len(ledger.history)==1 and ledger.history[0].reason=="PROVIDER_FAILURE"
    assert set(ledger.history[0].model_dump())=={"reason","reserved_input_units",
        "reserved_output_tokens","input_usage","output_usage"}


def test_provider_zero_is_usage_but_not_a_synthetic_boolean():
    answer=StructuredAnswer(status="unknown",claims=(),advice_codes=("MISSING_EVIDENCE",))
    assert ProviderResponse(answer=answer,input_usage=0,output_usage=0,is_synthetic=True).input_usage==0
    with pytest.raises(ValidationError):
        ProviderResponse(answer=answer,input_usage=0,output_usage=0,is_synthetic=1)


def test_valid_quota_field_mutation_cannot_change_the_frozen_dispatch_limit():
    from services.api.app.model_gateway.gateway import ModelGateway
    class Provider:
        calls=0
        async def complete(self,value):
            self.calls+=1
            raise AssertionError("quota drift must fail before provider IO")
    async def run():
        provider=Provider();ledger=BudgetLedger(clock=Clock())
        port=ModelGateway(policy=GatewayPolicy(app_environment="test",data_mode="demo",model_mode="mock"),
            provider=provider,budget=ledger)
        ledger.policy.__dict__["request_limit"]=20  # Valid syntax, changed authority.
        with pytest.raises(GatewayError) as failure:
            await port.complete(key(),request())
        assert failure.value.code=="BUDGET_UNAVAILABLE" and provider.calls==0
        assert ledger.history==()
    asyncio.run(run())


def test_valid_runtime_field_mutation_during_call_cannot_return_a_late_answer():
    from services.api.app.model_gateway.gateway import ModelGateway
    async def run():
        class Provider:
            calls=0
            async def complete(self,value):
                self.calls+=1
                await asyncio.sleep(0)
                port.policy.__dict__["app_environment"]="development"  # Still a legal demo mode.
                return ProviderResponse(answer=StructuredAnswer(status="unknown",claims=(),
                    advice_codes=("MISSING_EVIDENCE",)),input_usage=0,output_usage=0,is_synthetic=True)
        provider=Provider();ledger=BudgetLedger(clock=Clock())
        port=ModelGateway(policy=GatewayPolicy(app_environment="test",data_mode="demo",model_mode="mock"),
            provider=provider,budget=ledger)
        with pytest.raises(GatewayError) as failure:
            await port.complete(key(),request())
        assert failure.value.code=="BUDGET_UNAVAILABLE" and provider.calls==1
        assert ledger.history[0].reason=="BUDGET_UNAVAILABLE"
        assert ledger.snapshot().requests==1 and ledger.snapshot().inflight==0
    asyncio.run(run())
