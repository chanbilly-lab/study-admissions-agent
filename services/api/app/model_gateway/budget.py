"""Bounded in-process worst-case accounting, with no refunds or credentials."""

from collections import deque
from dataclasses import dataclass
import math
from threading import RLock
import time
from uuid import uuid4

from .schemas import BudgetKey,BudgetPolicy,BudgetSnapshot,GatewayError,UsageRecord


@dataclass(eq=False,frozen=True)
class BudgetReservation:
    token: object
    key: BudgetKey
    input_units: int
    output_tokens: int


@dataclass
class _Counter:
    requests: int = 0
    input_units: int = 0
    output_tokens: int = 0
    inflight: int = 0


class BudgetLedger:
    def __init__(self,policy=BudgetPolicy(),*,clock=time.monotonic):
        try:
            self.policy=BudgetPolicy.model_validate(policy)
            if not callable(clock):
                raise ValueError()
        except Exception:
            raise GatewayError("BUDGET_UNAVAILABLE") from None
        self.clock=clock
        self._initial=(BudgetPolicy.model_validate(self.policy),clock)
        self._lock=RLock()
        self._keys={}
        self._global=_Counter()
        self._active={}
        self._finished=set()
        self._history=deque(maxlen=self.policy.history_limit)
        self._start=self._last=None
        self._blocked=False

    def _validate(self):
        try:
            policy,clock=self._initial
            if BudgetPolicy.model_validate(self.policy)!=policy or self.clock is not clock or self._blocked:
                raise ValueError()
            return policy
        except Exception:
            raise GatewayError("BUDGET_UNAVAILABLE") from None

    def _window(self):
        policy=self._validate()
        try:
            now=self.clock()
            if type(now) not in {int,float} or not math.isfinite(now) or now<0 or self._last is not None and now<self._last:
                raise ValueError()
        except Exception:
            self._blocked=True
            raise GatewayError("BUDGET_UNAVAILABLE") from None
        self._last=now
        if self._start is None:
            self._start=now
        elif now-self._start>=policy.window_seconds:
            # Active calls survive window rollover and continue occupying their
            # key/global concurrency. Expired idle keys can safely be reclaimed.
            self._keys={key:_Counter(inflight=value.inflight) for key,value in self._keys.items() if value.inflight}
            self._global=_Counter(inflight=self._global.inflight)
            self._start=now
        return policy

    def reserve(self,key,units):
        try:
            key=BudgetKey.model_validate(key)
            if type(units) is not int or not 1<=units<=1000000:
                raise ValueError()
        except Exception:
            raise GatewayError("INVALID_MODEL_INPUT") from None
        with self._lock:
            policy=self._window()
            counter=self._keys.get(key)
            if counter is None:
                if len(self._keys)>=policy.max_keys:
                    raise GatewayError("KEY_LIMIT")
                counter=_Counter()
            if counter.inflight>=policy.concurrency_limit or self._global.inflight>=policy.global_concurrency_limit:
                raise GatewayError("CONCURRENCY_LIMIT")
            output=policy.max_output_tokens
            for current,limits in ((counter,(policy.request_limit,policy.input_limit,policy.output_limit)),
                (self._global,(policy.global_request_limit,policy.global_input_limit,policy.global_output_limit))):
                if current.requests+1>limits[0] or current.input_units+units>limits[1] or current.output_tokens+output>limits[2]:
                    raise GatewayError("BUDGET_EXHAUSTED")
            self._keys[key]=counter
            for current in (counter,self._global):
                current.requests+=1;current.input_units+=units;current.output_tokens+=output;current.inflight+=1
            reservation=BudgetReservation(uuid4(),key,units,output)
            self._active[reservation.token]=reservation
            return reservation

    def finish(self,reservation,reason,*,input_usage=None,output_usage=None):
        with self._lock:
            if self._active.get(reservation.token) is not reservation or reservation.token in self._finished:
                raise GatewayError("BUDGET_UNAVAILABLE")
            try:
                record=UsageRecord(reason=reason,reserved_input_units=reservation.input_units,
                    reserved_output_tokens=reservation.output_tokens,input_usage=input_usage,output_usage=output_usage)
            except Exception:
                raise GatewayError("INVALID_PROVIDER_RESPONSE") from None
            self._finished.add(reservation.token)
            self._history.append(record)

    def release(self,reservation):
        with self._lock:
            if self._active.get(reservation.token) is not reservation:
                return
            del self._active[reservation.token]
            self._finished.discard(reservation.token)
            self._keys[reservation.key].inflight-=1
            self._global.inflight-=1

    def snapshot(self,key=None):
        with self._lock:
            self._window()
            if key is None:
                counter=self._global
            else:
                try:
                    key=BudgetKey.model_validate(key)
                except Exception:
                    raise GatewayError("INVALID_MODEL_INPUT") from None
                counter=self._keys.get(key,_Counter())
            return BudgetSnapshot(requests=counter.requests,input_units=counter.input_units,
                output_tokens=counter.output_tokens,inflight=counter.inflight,key_count=len(self._keys))

    @property
    def history(self):
        with self._lock:
            return tuple(self._history)
