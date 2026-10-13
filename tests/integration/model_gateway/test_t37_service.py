"""Actual asynchronous offline port tests; no network, SQL, or HTTP substitute."""

import asyncio

import pytest

from services.api.app.model_gateway.budget import BudgetLedger
from services.api.app.model_gateway.gateway import ModelGateway
from services.api.app.model_gateway.provider import OfflineMock
from services.api.app.model_gateway.schemas import (
    BudgetPolicy,Claim,GatewayError,GatewayPolicy,ProviderResponse,StructuredAnswer,
)
from tests.unit.model_gateway.test_t37_gateway import Clock,key,request


POLICY=GatewayPolicy(app_environment="test",data_mode="demo",model_mode="mock")


def response(value=None):
    answer=StructuredAnswer(status="answered",claims=(Claim(citation_id=value.evidence[0].citation_id,
        value="DEMO 0"),),advice_codes=()) if value is not None else StructuredAnswer(
        status="unknown",claims=(),advice_codes=("MISSING_EVIDENCE",))
    return ProviderResponse(answer=answer,input_usage=0,output_usage=0,is_synthetic=True)


class Stub:
    def __init__(self,error=None):
        self.calls=0;self.error=error
    async def complete(self,value):
        self.calls+=1
        await asyncio.sleep(0)
        if self.error is not None:
            raise self.error
        return response(value)


def gateway(provider,**budget):
    ledger=BudgetLedger(BudgetPolicy(**budget),clock=Clock())
    return ModelGateway(policy=POLICY,provider=provider,budget=ledger),ledger


def test_real_async_offline_mock_uses_only_explicit_synthetic_evidence():
    async def run():
        port,ledger=gateway(OfflineMock())
        value=request()
        result=await port.complete(key(),value)
        assert result.answer.status=="answered"
        assert result.answer.claims[0].value==value.evidence[0].value
        assert ledger.snapshot().inflight==0 and ledger.history[0].reason=="OK"
        empty=await port.complete(key(),request(count=0))
        assert empty.answer.status=="unknown" and empty.answer.claims==()
    asyncio.run(run())


@pytest.mark.parametrize("mode,code",[("disabled","MODEL_DISABLED"),("live","LIVE_UNAVAILABLE")])
def test_closed_mode_ignores_provider_and_budget_clock(mode,code):
    async def run():
        provider=Stub()
        def forbidden_clock():
            raise AssertionError("disabled model must not access quota")
        ledger=BudgetLedger(clock=forbidden_clock)
        port=ModelGateway(policy=GatewayPolicy(model_mode=mode),provider=provider,budget=ledger)
        with pytest.raises(GatewayError) as failure:
            await port.complete(key(),object())
        assert failure.value.code==code and provider.calls==0 and ledger.history==()
    asyncio.run(run())


def test_provider_failure_is_fixed_and_still_consumes_the_worst_reservation(caplog):
    async def run():
        provider=Stub(RuntimeError("DEMO_PRIVATE_PROMPT_SECRET"))
        port,ledger=gateway(provider,request_limit=1)
        with pytest.raises(GatewayError) as failure:
            await port.complete(key(),request(question="DEMO_PRIVATE_PROMPT_SECRET"))
        assert failure.value.code=="PROVIDER_FAILURE"
        assert "DEMO_PRIVATE" not in str(failure.value)+repr(failure.value)+caplog.text
        assert ledger.snapshot().requests==1 and ledger.snapshot().output_tokens==512
        assert ledger.snapshot().inflight==0 and ledger.history[0].reason=="PROVIDER_FAILURE"
        class WrongSignature:
            calls=0
            async def complete(self):
                self.calls+=1
                raise AssertionError("a wrong signature cannot enter the provider")
        malformed=WrongSignature();closed,quota=gateway(malformed)
        with pytest.raises(GatewayError) as failure:
            await closed.complete(key(),request())
        assert failure.value.code=="PROVIDER_FAILURE" and malformed.calls==0
        assert quota.snapshot().requests==1 and quota.snapshot().output_tokens==512
        assert quota.snapshot().inflight==0 and quota.history[0].reason=="PROVIDER_FAILURE"
        assert "DEMO_PRIVATE" not in str(failure.value)+repr(failure.value)+caplog.text
    asyncio.run(run())


def test_actual_async_global_quota_applies_across_distinct_trusted_keys():
    async def run():
        provider=Stub();port,ledger=gateway(provider,global_request_limit=2)
        for _ in range(2):
            assert (await port.complete(key(),request())).answer.status=="answered"
        with pytest.raises(GatewayError) as failure:
            await port.complete(key(),request())
        assert failure.value.code=="BUDGET_EXHAUSTED" and provider.calls==2
        assert ledger.snapshot().requests==2 and ledger.snapshot().output_tokens==1024
    asyncio.run(run())


def test_cooperative_timeout_records_failure_and_releases_actual_provider_slot():
    async def run():
        entered=asyncio.Event();finished=asyncio.Event()
        class Waiting:
            async def complete(self,value):
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    finished.set()
        port,ledger=gateway(Waiting(),timeout_ms=5,global_concurrency_limit=1)
        started=asyncio.get_running_loop().time()
        with pytest.raises(GatewayError) as failure:
            await asyncio.wait_for(port.complete(key(),request()),0.5)
        assert failure.value.code=="MODEL_TIMEOUT" and entered.is_set()
        assert asyncio.get_running_loop().time()-started<0.5
        await asyncio.wait_for(finished.wait(),0.2)
        await asyncio.sleep(0)
        assert ledger.snapshot().inflight==0 and ledger.history[0].reason=="MODEL_TIMEOUT"
        assert ledger.snapshot().requests==1
    asyncio.run(run())


def test_caller_cancel_records_worst_usage_and_has_no_late_answer():
    async def run():
        entered=asyncio.Event();finished=asyncio.Event()
        class Waiting:
            async def complete(self,value):
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    finished.set()
        port,ledger=gateway(Waiting(),timeout_ms=1000)
        pending=asyncio.create_task(port.complete(key(),request()))
        await asyncio.wait_for(entered.wait(),0.2)
        pending.cancel()
        with pytest.raises(GatewayError) as failure:
            await pending
        assert failure.value.code=="MODEL_CANCELLED"
        await asyncio.wait_for(finished.wait(),0.2);await asyncio.sleep(0)
        assert ledger.snapshot().inflight==0 and ledger.snapshot().output_tokens==512
        assert ledger.history[0].reason=="MODEL_CANCELLED"
    asyncio.run(run())


def test_answer_size_cannot_escape_worst_output_by_reporting_zero_usage():
    async def run():
        class TooLarge:
            async def complete(self,value):
                return ProviderResponse(answer=StructuredAnswer(status="answered",claims=(Claim(
                    citation_id=value.evidence[0].citation_id,value="大"*1000),),advice_codes=()),
                    input_usage=0,output_usage=0,is_synthetic=True)
        port,ledger=gateway(TooLarge(),max_output_tokens=512)
        with pytest.raises(GatewayError) as failure:
            await port.complete(key(),request())
        assert failure.value.code=="INVALID_PROVIDER_RESPONSE"
        assert ledger.snapshot().output_tokens==512 and ledger.snapshot().inflight==0
    asyncio.run(run())
