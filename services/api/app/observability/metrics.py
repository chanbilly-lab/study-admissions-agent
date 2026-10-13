"""Bounded low-cardinality aggregates; no raw requests, student data, or exporter."""

from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict

METRICS = frozenset({"request_count", "error", "duration_sum", "duration_count",
                     "qualification_unknown", "review_backlog", "job_failures", "model_cost"})
COMPONENTS = frozenset({"api", "eligibility", "review", "jobs", "model"})
OUTCOMES = frozenset({"ok", "error", "unknown"})
MAX_INCREMENT = 10**12
MAX_TOTAL = 10**15


class ObservationError(ValueError):
    pass


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always", allow_inf_nan=False)


class ObservabilityPolicy(Closed):
    mode: Literal["disabled", "synthetic"] = "disabled"


def _enabled(policy):
    if type(policy) is not ObservabilityPolicy:
        raise ObservationError("OBSERVATION_INVALID")
    try:
        return ObservabilityPolicy.model_validate(policy.model_dump()).mode == "synthetic"
    except ValueError:
        raise ObservationError("OBSERVATION_INVALID") from None


class MetricRegistry:
    def __init__(self, policy: ObservabilityPolicy = ObservabilityPolicy()):
        _enabled(policy)
        self.policy = self._initial = policy
        self._values: dict[tuple[str, str, str], int] = {}
        self._lock = Lock()

    def _active(self):
        if self.policy is not self._initial:
            raise ObservationError("OBSERVATION_INVALID")
        return _enabled(self.policy)

    def add(self, metric: str, *, component: str, outcome: str, value: int = 1) -> bool:
        active = self._active()
        if (type(metric) is not str or metric not in METRICS or type(component) is not str or component not in COMPONENTS
                or type(outcome) is not str or outcome not in OUTCOMES or type(value) is not int
                or not 0 <= value <= MAX_INCREMENT):
            raise ObservationError("OBSERVATION_INVALID")
        if not active:
            return False
        key = (metric, component, outcome)
        with self._lock:
            updated = value if metric == "review_backlog" else self._values.get(key, 0) + value
            if updated > MAX_TOTAL:
                raise ObservationError("OBSERVATION_LIMIT")
            self._values[key] = updated
        return True

    def snapshot(self) -> dict:
        active = self._active()
        with self._lock:
            values = tuple({"metric": name, "component": component, "outcome": outcome, "value": value}
                           for (name, component, outcome), value in sorted(self._values.items())) if active else ()
        return {"mode": "synthetic" if active else "disabled", "scope": "process_local", "samples": values,
                "dependencies": dict.fromkeys(("database", "ledger", "storage", "identity", "model"), "unknown"),
                "percentiles_available": False, "release_ready": False}


class CorrectionCandidate(Closed):
    category: Literal["evidence", "score_scope", "date_precision", "institution_mapping", "curriculum", "outcome"]
    state: Literal["submitted", "triaged", "resolved", "rejected"] = "submitted"
    is_synthetic: Literal[True] = True
    published_facts_modified: Literal[False] = False


TRANSITIONS = {"submitted": frozenset({"triaged", "rejected"}),
               "triaged": frozenset({"resolved", "rejected"}), "resolved": frozenset(), "rejected": frozenset()}


def correction_candidate(category: str, *, policy: ObservabilityPolicy = ObservabilityPolicy()) -> CorrectionCandidate:
    if not _enabled(policy):
        raise ObservationError("OBSERVATION_DISABLED")
    try:
        return CorrectionCandidate(category=category)
    except ValueError:
        raise ObservationError("OBSERVATION_INVALID") from None


def transition_correction(candidate: CorrectionCandidate, state: str, *,
                          policy: ObservabilityPolicy = ObservabilityPolicy()) -> CorrectionCandidate:
    if not _enabled(policy):
        raise ObservationError("OBSERVATION_DISABLED")
    if type(candidate) is not CorrectionCandidate:
        raise ObservationError("OBSERVATION_INVALID")
    try:
        current = CorrectionCandidate.model_validate(candidate.model_dump())
        if type(state) is not str or state not in TRANSITIONS[current.state]:
            raise ObservationError("CORRECTION_TRANSITION_INVALID")
        return CorrectionCandidate.model_validate({**current.model_dump(), "state": state})
    except ValueError:
        raise ObservationError("CORRECTION_TRANSITION_INVALID") from None
