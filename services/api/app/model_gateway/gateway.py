"""Closed optional model calls; no credentials, network setup or student services."""

import asyncio
import inspect

from .budget import BudgetLedger
from .provider import OfflineMock
from .schemas import (BudgetKey, BudgetPolicy, GatewayError, GatewayPolicy, ProviderResponse,
                     input_units, validate_request)


class ModelGateway:
    def __init__(self, *, policy=GatewayPolicy(), provider=None, budget=None):
        try:
            self.policy = GatewayPolicy.model_validate(policy)
            self.budget = budget if budget is not None else BudgetLedger()
            if type(self.budget) is not BudgetLedger:
                raise ValueError()
            self.provider = provider if provider is not None else (
                OfflineMock() if self.policy.model_mode == "mock" else None)
            self._initial = (GatewayPolicy.model_validate(self.policy), self.provider, self.budget,
                             BudgetPolicy.model_validate(self.budget.policy), self.budget.clock)
            self._validate()
        except Exception:
            raise GatewayError("INVALID_MODEL_INPUT") from None

    def _validate(self):
        try:
            policy, provider, budget, quota, clock = self._initial
            current = GatewayPolicy.model_validate(self.policy)
            if (current != policy or self.provider is not provider or self.budget is not budget
                    or self.budget.policy != quota or self.budget.clock is not clock):
                raise ValueError()
            self.budget._validate()
            return current
        except Exception:
            raise GatewayError("BUDGET_UNAVAILABLE") from None

    def _ready(self):
        policy = self._validate()
        if policy.model_mode == "disabled":
            raise GatewayError("MODEL_DISABLED")
        if policy.model_mode == "live":
            raise GatewayError("LIVE_UNAVAILABLE")
        if policy.app_environment == "production":
            raise GatewayError("PRODUCTION_MODEL_DISABLED")
        if policy.data_mode != "demo" or policy.model_mode != "mock":
            raise GatewayError("INVALID_MODEL_INPUT")
        return policy

    async def complete(self, key, request):
        # Closed modes precede request parsing, the quota clock and provider IO.
        self._ready()
        request = validate_request(request)
        try:
            key = BudgetKey.model_validate(key)
            if any(atom.is_synthetic is not True for atom in request.evidence):
                raise ValueError()
            complete = self.provider.complete
            if not inspect.iscoroutinefunction(complete):
                raise ValueError()
        except Exception:
            raise GatewayError("INVALID_MODEL_INPUT") from None
        reservation = self.budget.reserve(key, input_units(request))
        ledger = self.budget
        loop = asyncio.get_running_loop()
        deadline = loop.time() + ledger.policy.timeout_ms / 1000
        coroutine = None
        try:
            coroutine = complete(request)
            task = asyncio.create_task(coroutine)
        except Exception:
            if inspect.iscoroutine(coroutine):
                coroutine.close()
            ledger.finish(reservation, "PROVIDER_FAILURE")
            ledger.release(reservation)
            raise GatewayError("PROVIDER_FAILURE") from None
        recorded = False

        def release_when_done(finished):
            # Consume late exceptions without logging provider content. The slot
            # remains occupied until an adapter swallowing cancellation is done.
            if not finished.cancelled():
                try:
                    finished.exception()
                except BaseException:
                    pass
            ledger.release(reservation)

        def record(code, *, response=None):
            nonlocal recorded
            if not recorded:
                ledger.finish(reservation, code,
                    input_usage=response.input_usage if response is not None else None,
                    output_usage=response.output_usage if response is not None else None)
                recorded = True

        try:
            done, _ = await asyncio.wait({task}, timeout=max(0, deadline-loop.time()))
            if task not in done or loop.time() >= deadline:
                record("MODEL_TIMEOUT")
                task.cancel()
                raise GatewayError("MODEL_TIMEOUT")
            try:
                raw = task.result()
            except BaseException:
                raise GatewayError("PROVIDER_FAILURE") from None
            try:
                response = ProviderResponse.model_validate(raw)
                output_size = len(response.answer.model_dump_json().encode("utf-8"))
                if (response.input_usage > reservation.input_units
                        or response.output_usage > reservation.output_tokens
                        or output_size > reservation.output_tokens):
                    raise ValueError()
            except Exception:
                raise GatewayError("INVALID_PROVIDER_RESPONSE") from None
            self._ready()
            ledger.snapshot(key)  # fresh monotonic integrity after provider IO
            if loop.time() >= deadline:
                raise GatewayError("MODEL_TIMEOUT")
            record("OK", response=response)
            return response
        except asyncio.CancelledError:
            record("MODEL_CANCELLED")
            task.cancel()
            raise GatewayError("MODEL_CANCELLED") from None
        except GatewayError as error:
            record(error.code)
            raise
        except Exception:
            record("PROVIDER_FAILURE")
            task.cancel()
            raise GatewayError("PROVIDER_FAILURE") from None
        finally:
            if task.done():
                release_when_done(task)
            else:
                task.add_done_callback(release_when_done)
