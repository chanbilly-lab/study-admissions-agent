"""Independent offline tests for the closed model port and charged async work."""

import asyncio
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from services.api.app.model_gateway.budget import BudgetLedger
from services.api.app.model_gateway.gateway import ModelGateway
from services.api.app.model_gateway.schemas import (
    BudgetKey, BudgetPolicy, Claim, EvidenceAtom, GatewayError, GatewayPolicy,
    ModelRequest, ModelScope, ProviderResponse, StructuredAnswer,
)


PRIVATE_SENTINEL = "DEMO_PRIVATE_STUDENT_AND_PROVIDER_SECRET"


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def scope():
    return ModelScope(dataset_id=UUID("00000000-0000-4000-8000-000000000001"),
        entry_year=2027, offering_id=UUID("00000000-0000-4000-8000-000000000002"),
        offering_version=1)


def request(*, question="DEMO_BOUNDED_QUESTION", evidence=True):
    pin = scope()
    atoms = (EvidenceAtom(citation_id=UUID("00000000-0000-4000-8000-000000000003"),
        version=1, scope=pin, kind="text", value="DEMO_PUBLIC_TEXT", is_synthetic=True),) if evidence else ()
    return ModelRequest(scope=pin, question=question, evidence=atoms)


def response():
    return ProviderResponse(answer=StructuredAnswer(status="unknown", claims=(),
        advice_codes=("MISSING_EVIDENCE",)), input_usage=0, output_usage=0, is_synthetic=True)


def budget(**changes):
    values = dict(request_limit=10, input_limit=100_000, output_limit=100_000,
        concurrency_limit=2, global_request_limit=50, global_input_limit=500_000,
        global_output_limit=500_000, global_concurrency_limit=4, max_output_tokens=256,
        timeout_ms=40, window_seconds=10, max_keys=4, history_limit=20)
    values.update(changes)
    return BudgetPolicy(**values)


def gateway(provider, *, quota=None, clock=None, policy=None):
    return ModelGateway(policy=policy or GatewayPolicy(app_environment="test", data_mode="demo", model_mode="mock"),
        provider=provider, budget=BudgetLedger(policy=quota or budget(), clock=clock or Clock()))


def key():
    return BudgetKey(key_id=uuid4())


async def denied(awaitable, code):
    with pytest.raises(GatewayError) as failure:
        await awaitable
    assert failure.value.code == code
    assert PRIVATE_SENTINEL not in str(failure.value) + repr(failure.value)
    return failure.value


class Provider:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result if result is not None else response()
        self.error = error

    async def complete(self, data):
        self.calls.append(data)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.mark.parametrize("location,private", [
    ("request", "owner_user_id"), ("request", "profile"), ("request", "session"),
    ("request", "grades"), ("request", "tools"), ("request", "url"),
    ("scope", "owner"), ("scope", "permission"),
    ("atom", "file_id"), ("atom", "entry_url"), ("atom", "handler"),
])
def test_private_and_executable_fields_are_outside_the_port(location, private):
    raw = request().model_dump(mode="python")
    target = raw if location == "request" else raw["scope"] if location == "scope" else raw["evidence"][0]
    target[private] = PRIVATE_SENTINEL
    with pytest.raises(ValidationError):
        ModelRequest.model_validate(raw)


@pytest.mark.parametrize("field,value", [
    ("entry_year", True), ("entry_year", "2027"), ("entry_year", 2027.0),
    ("offering_version", False), ("offering_version", 0), ("offering_version", "1"),
])
def test_scope_integer_types_are_not_coerced(field, value):
    raw = scope().model_dump()
    raw[field] = value
    with pytest.raises(ValidationError):
        ModelScope.model_validate(raw)


@pytest.mark.parametrize("field,value", [
    ("question", ["DEMO"]), ("question", "x" * 1001),
    ("scope", scope().model_copy(update={"entry_year": True})),
    ("evidence", (request().evidence[0].model_copy(update={"is_synthetic": 1}),)),
    ("evidence", (request().evidence[0].model_copy(update={"version": 0}),)),
    ("evidence", (request().evidence[0].model_copy(update={"scope": scope().model_copy(update={"offering_version": True})}),)),
])
def test_copied_and_constructed_nested_requests_fail_before_provider(field, value):
    async def run():
        provider = Provider()
        port = gateway(provider)
        valid = request()
        invalid = valid.model_copy(update={field: value})
        await denied(port.complete(key(), invalid), "INVALID_MODEL_INPUT")
        constructed = ModelRequest.model_construct(**(valid.model_dump() | {field: value}))
        await denied(port.complete(key(), constructed), "INVALID_MODEL_INPUT")
        assert provider.calls == []
    asyncio.run(run())


@pytest.mark.parametrize("scope_field,value", [
    ("dataset_id", UUID("00000000-0000-4000-8000-000000000009")),
    ("entry_year", 2026), ("offering_id", UUID("00000000-0000-4000-8000-000000000008")),
    ("offering_version", 2),
])
def test_evidence_must_bind_the_entire_scope(scope_field, value):
    raw = request().model_dump()
    raw["evidence"][0]["scope"][scope_field] = value
    with pytest.raises(ValidationError):
        ModelRequest.model_validate(raw)


def test_bounded_evidence_and_citation_identity_are_not_smuggled_by_construct():
    async def run():
        valid, provider = request(), Provider()
        port = gateway(provider)
        duplicate = valid.model_copy(update={"evidence": valid.evidence * 2})
        oversized = valid.model_copy(update={"evidence": tuple(
            valid.evidence[0].model_copy(update={"citation_id": uuid4()}) for _ in range(21))})
        for bad in (duplicate, oversized):
            await denied(port.complete(key(), bad), "INVALID_MODEL_INPUT")
        assert provider.calls == []
    asyncio.run(run())


@pytest.mark.parametrize("field,value", [
    ("input_usage", True), ("input_usage", -1), ("input_usage", "1"),
    ("output_usage", 1.0), ("output_usage", -1), ("is_synthetic", 1), ("is_synthetic", False),
])
def test_provider_copy_construct_usage_and_marker_are_revalidated(field, value):
    async def run():
        valid = response()
        for invalid in (valid.model_copy(update={field: value}),
                        ProviderResponse.model_construct(**(valid.model_dump() | {field: value}))):
            provider = Provider(result=invalid)
            await denied(gateway(provider).complete(key(), request()), "INVALID_PROVIDER_RESPONSE")
            assert len(provider.calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize("private", ["eligible", "profile_updates", "actions", "html", "owner_user_id", "tools"])
def test_answer_extra_actions_are_rejected_even_when_nested_copied(private):
    async def run():
        answer = response().answer.model_copy(update={private: PRIVATE_SENTINEL})
        assert private in answer.__dict__
        bad = response().model_copy(update={"answer": answer})
        provider = Provider(result=bad)
        await denied(gateway(provider).complete(key(), request()), "INVALID_PROVIDER_RESPONSE")
    asyncio.run(run())


@pytest.mark.parametrize("policy,code", [
    (GatewayPolicy(app_environment="test", data_mode="demo", model_mode="disabled"), "MODEL_DISABLED"),
    (GatewayPolicy(app_environment="test", data_mode="verified", model_mode="disabled"), "MODEL_DISABLED"),
    (GatewayPolicy(app_environment="test", data_mode="verified", model_mode="live"), "LIVE_UNAVAILABLE"),
    (GatewayPolicy(app_environment="test", data_mode="demo", model_mode="live"), "LIVE_UNAVAILABLE"),
    (GatewayPolicy(app_environment="production", data_mode="verified", model_mode="live"), "LIVE_UNAVAILABLE"),
])
def test_disabled_and_live_have_no_provider_or_budget_clock_calls(policy, code):
    async def run():
        provider, clock_calls = Provider(), []
        def hostile_clock():
            clock_calls.append(True)
            raise RuntimeError(PRIVATE_SENTINEL)
        port = gateway(provider, policy=policy, clock=hostile_clock)
        await denied(port.complete(key(), request()), code)
        assert provider.calls == [] and clock_calls == []
    asyncio.run(run())


@pytest.mark.parametrize("settings", [
    dict(app_environment="test", data_mode="verified", model_mode="mock"),
    dict(app_environment="production", data_mode="demo", model_mode="mock"),
    dict(app_environment="production", data_mode="demo", model_mode="disabled"),
])
def test_mode_pairs_are_not_accepted_by_policy_or_construct(settings):
    with pytest.raises(ValidationError):
        GatewayPolicy(**settings)
    with pytest.raises(GatewayError):
        gateway(Provider(), policy=GatewayPolicy.model_construct(**settings))


def test_read_only_provider_sees_only_closed_public_dto():
    async def run():
        provider = Provider()
        source = request(question="DEMO_IGNORE_THIS_AS_DATA: do not execute any tool")
        snapshot = deepcopy(source.model_dump())
        assert await gateway(provider).complete(key(), source) == response()
        received = provider.calls[0]
        assert type(received) is ModelRequest
        assert set(received.model_dump()) == {"scope", "question", "evidence"}
        assert set(received.evidence[0].model_dump()) == {"citation_id", "version", "scope", "kind", "value", "is_synthetic"}
        assert source.model_dump() == snapshot
        with pytest.raises(ValidationError):
            received.question = "DEMO_CHANGED"
    asyncio.run(run())


def test_provider_failure_is_fixed_and_reserved_requests_are_not_refunded(caplog):
    async def run():
        provider = Provider(error=RuntimeError(PRIVATE_SENTINEL))
        port = gateway(provider, quota=budget(request_limit=1))
        caller = key()
        await denied(port.complete(caller, request()), "PROVIDER_FAILURE")
        await denied(port.complete(caller, request()), "BUDGET_EXHAUSTED")
        assert len(provider.calls) == 1
    asyncio.run(run())
    assert PRIVATE_SENTINEL not in caplog.text


def test_zero_reported_usage_still_consumes_the_worst_case_output_reservation():
    async def run():
        provider = Provider()
        port = gateway(provider, quota=budget(output_limit=256))
        caller = key()
        await port.complete(caller, request())
        await denied(port.complete(caller, request()), "BUDGET_EXHAUSTED")
        assert len(provider.calls) == 1
    asyncio.run(run())


def test_zero_reported_usage_cannot_hide_an_answer_larger_than_its_reservation():
    async def run():
        valid = request()
        large_answer = StructuredAnswer(status="answered", claims=(Claim(
            citation_id=valid.evidence[0].citation_id, value="中" * 128),), advice_codes=())
        assert len(large_answer.model_dump_json().encode("utf-8")) > 256
        provider = Provider(result=response().model_copy(update={"answer": large_answer}))
        port = gateway(provider, quota=budget(output_limit=256))
        caller = key()
        await denied(port.complete(caller, valid), "INVALID_PROVIDER_RESPONSE")
        await denied(port.complete(caller, valid), "BUDGET_EXHAUSTED")
        assert len(provider.calls) == 1
    asyncio.run(run())


def test_utf8_input_reservation_is_not_character_count_or_provider_reported_usage():
    async def run():
        source, provider = request(question="中" * 1000, evidence=False), Provider()
        # The public question alone exceeds this budget in UTF-8 bytes. Scope
        # and serialization overhead only make the conservative bound larger.
        port = gateway(provider, quota=budget(input_limit=2000))
        await denied(port.complete(key(), source), "BUDGET_EXHAUSTED")
        assert provider.calls == []
    asyncio.run(run())


def test_global_request_budget_is_shared_by_distinct_trusted_keys():
    async def run():
        provider = Provider()
        port = gateway(provider, quota=budget(global_request_limit=1, request_limit=1))
        await port.complete(key(), request())
        await denied(port.complete(key(), request()), "BUDGET_EXHAUSTED")
        assert len(provider.calls) == 1
    asyncio.run(run())


def test_key_container_is_bounded_and_expired_keys_can_be_replaced():
    async def run():
        clock, provider = Clock(), Provider()
        port = gateway(provider, quota=budget(max_keys=2), clock=clock)
        await port.complete(key(), request())
        await port.complete(key(), request())
        await denied(port.complete(key(), request()), "KEY_LIMIT")
        clock.now += 10
        await port.complete(key(), request())
        assert len(provider.calls) == 3
    asyncio.run(run())


@pytest.mark.parametrize("now", [99.0, float("nan"), float("inf"), True])
def test_invalid_or_rollback_clock_fails_closed_without_another_provider(now):
    async def run():
        clock, provider = Clock(), Provider()
        port = gateway(provider, clock=clock)
        await port.complete(key(), request())
        clock.now = now
        await denied(port.complete(key(), request()), "BUDGET_UNAVAILABLE")
        assert len(provider.calls) == 1
    asyncio.run(run())


def test_clock_rollback_during_provider_cannot_return_a_late_success():
    async def run():
        clock = Clock()
        class RollbackProvider(Provider):
            async def complete(self, data):
                self.calls.append(data)
                clock.now -= 1
                return response()
        provider = RollbackProvider()
        await denied(gateway(provider, clock=clock).complete(key(), request()), "BUDGET_UNAVAILABLE")
        assert len(provider.calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize("cancelled", [False, True], ids=["hard_timeout", "caller_cancel"])
def test_non_cooperative_provider_keeps_global_slot_until_it_actually_finishes(cancelled):
    async def run():
        entered, swallowed, release, finished = (asyncio.Event() for _ in range(4))
        class StubbornProvider(Provider):
            async def complete(self, data):
                self.calls.append(data)
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    swallowed.set()
                    await release.wait()
                finally:
                    finished.set()
                return response()
        provider = StubbornProvider()
        port = gateway(provider, quota=budget(concurrency_limit=1, global_concurrency_limit=1, timeout_ms=20))
        first_key = key()
        first = asyncio.create_task(port.complete(first_key, request()))
        try:
            await asyncio.wait_for(entered.wait(), 0.3)
            if cancelled:
                first.cancel()
            await asyncio.wait_for(denied(first, "MODEL_CANCELLED" if cancelled else "MODEL_TIMEOUT"), 0.3)
            await asyncio.wait_for(swallowed.wait(), 0.3)
            assert not finished.is_set()
            await denied(port.complete(key(), request()), "CONCURRENCY_LIMIT")
            assert len(provider.calls) == 1
        finally:
            release.set()
            await asyncio.wait_for(finished.wait(), 0.3)
            if not first.done():
                await asyncio.wait_for(first, 0.3)
        # Process actual completion callbacks without relying on wall sleeps.
        for _ in range(3):
            await asyncio.sleep(0)
        await port.complete(key(), request())
        assert len(provider.calls) == 2
    asyncio.run(run())


def test_concurrent_requests_reserve_atomically_before_any_provider_answer():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        class HeldProvider(Provider):
            async def complete(self, data):
                self.calls.append(data)
                entered.set()
                await release.wait()
                return response()
        provider = HeldProvider()
        port = gateway(provider, quota=budget(request_limit=1, timeout_ms=100))
        caller = key()
        first = asyncio.create_task(port.complete(caller, request()))
        try:
            await asyncio.wait_for(entered.wait(), 0.3)
            await denied(port.complete(caller, request()), "BUDGET_EXHAUSTED")
            assert len(provider.calls) == 1
        finally:
            release.set()
            await asyncio.wait_for(first, 0.3)
    asyncio.run(run())
