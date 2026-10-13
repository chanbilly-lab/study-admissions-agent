"""Four-state classification over the original bounded AST, without authority.

Counterfactual values are ephemeral search representatives, never student grades.
Callers separately prove current scope, rule, policy, identity and consent bindings.
"""

from itertools import combinations, product
from typing import Literal

from pydantic import Field, model_validator

from .deferral import DeferralResult
from .evaluator import evaluate_expression
from .expression import (ASSESSMENT_KEYS, AssessmentKey, ContextField, DecimalValue,
                         EvaluationResult, FieldRef, RuleInputError, RuleModel,
                         TypedDatum, parse_expression, validate_context)

ENGINE_VERSION = "T28_v1"
MAX_COMBINATIONS = 4096
MICRO_UNITS = 1_000_000
MAX_GRADE_UNITS = 9_999_999 * MICRO_UNITS + 999_999
EngineReason = Literal["RULE_TRUE", "RULE_FALSE", "DEFERRAL_SATISFIABLE", "RULE_UNKNOWN",
    "NO_COMPLETABLE_FIELD", "DOMAIN_UNAVAILABLE", "SEARCH_BUDGET_EXCEEDED",
    "RULESET_UNAVAILABLE", "BINDING_UNAVAILABLE", "SCOPE_UNAVAILABLE"]


class CompletionObligation(RuleModel):
    assessment_key: AssessmentKey
    basis: Literal["achieved"]
    deferral: DeferralResult

    @model_validator(mode="after")
    def actual_permission(self):
        if self.deferral.deferral_status != "allowed":
            raise ValueError("a completion obligation needs an allowed item binding")
        return self


class EligibilityEngineResult(RuleModel):
    status: Literal["eligible", "ineligible", "conditional", "unknown"]
    reason: EngineReason
    evaluation: EvaluationResult | None
    obligations: tuple[CompletionObligation, ...] = Field(max_length=15)

    @model_validator(mode="after")
    def coherent_outcome(self):
        if len({item.assessment_key for item in self.obligations}) != len(self.obligations):
            raise ValueError("completion obligations must be unique")
        if self.status == "conditional":
            if (self.reason != "DEFERRAL_SATISFIABLE" or not self.obligations
                or self.evaluation is None or self.evaluation.truth != "unknown"):
                raise ValueError("conditional needs the original unknown trace and obligations")
        elif self.obligations:
            raise ValueError("only conditional outcomes have obligations")
        elif self.status in {"eligible", "ineligible"}:
            expected = "true" if self.status == "eligible" else "false"
            if (self.evaluation is None or self.evaluation.truth != expected
                or self.reason != ("RULE_TRUE" if expected == "true" else "RULE_FALSE")):
                raise ValueError("a definite outcome needs its original complete rule result")
        elif self.evaluation is None:
            if self.reason not in {"RULESET_UNAVAILABLE", "BINDING_UNAVAILABLE", "SCOPE_UNAVAILABLE"}:
                raise ValueError("an unavailable rule cannot claim an evaluated trace")
        elif (self.evaluation.truth != "unknown" or self.reason not in {
            "RULE_UNKNOWN", "NO_COMPLETABLE_FIELD", "DOMAIN_UNAVAILABLE", "SEARCH_BUDGET_EXCEEDED"}):
            raise ValueError("unknown classification needs an unknown original rule")
        return self


def _deferrals(value):
    if value is None:
        return {}
    if type(value) is not dict or len(value) > len(ASSESSMENT_KEYS):
        raise RuleInputError()
    result = {}
    try:
        for key, permission in value.items():
            if type(key) is not str or key not in ASSESSMENT_KEYS or type(permission) not in (dict, DeferralResult):
                raise RuleInputError()
            result[key] = DeferralResult.model_validate(permission)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise RuleInputError() from None
    return result


def _atoms(expression):
    if expression.op in {"all", "any"}:
        for child in expression.children:
            yield from _atoms(child)
    elif expression.op == "not":
        yield from _atoms(expression.child)
    else:
        yield expression


def _micro_bounds(value):
    """Exact floor/ceil on the 1e-6 lattice, with no Decimal context rounding."""
    whole, _, fraction = value.partition(".")
    floor = int(whole) * MICRO_UNITS + int((fraction[:6] + "000000")[:6])
    return floor, floor + int(any(character != "0" for character in fraction[6:]))


def _micro_text(units):
    whole, fraction = divmod(units, MICRO_UNITS)
    return str(whole) if not fraction else str(whole) + "." + str(fraction).rjust(6, "0").rstrip("0")


def _domain(key, atoms):
    unit = "band" if key.startswith("ielts_") else "points"
    numeric = []
    for atom in atoms:
        if atom.op == "exists":
            continue
        if atom.op not in {"eq", "in", "gte", "lte"}:
            return None
        literals = atom.values if atom.op == "in" else (atom.value,)
        if any(type(literal) is not DecimalValue or literal.unit != unit for literal in literals):
            return None
        numeric.extend(literals)
    if not numeric:
        # All uses of this field are presence predicates. This legal internal
        # representative carries no claim about an institution's grading scale.
        return (DecimalValue(value="0", unit=unit, scale="1"),)
    scale_bounds = tuple(_micro_bounds(literal.scale) for literal in numeric)
    first = scale_bounds[0]
    if (first[0] != first[1] or not 0 < first[0] <= MAX_GRADE_UNITS
        or any(bounds != first for bounds in scale_bounds)):
        return None
    scale = first[0]
    candidates = {0, scale}
    for literal in numeric:
        floor, ceil = _micro_bounds(literal.value)
        for boundary in (floor, ceil):
            candidates.update(point for point in (boundary - 1, boundary, boundary + 1) if 0 <= point <= scale)
    ordered = sorted(candidates)
    for left, right in zip(ordered, ordered[1:]):
        candidates.update(((left + right) // 2, (left + right + 1) // 2))
    scale_text = _micro_text(scale)
    return tuple(DecimalValue(value=_micro_text(point), unit=unit, scale=scale_text) for point in sorted(candidates))


def _completed_context(context, keys, values):
    replacements = dict(zip(keys, values, strict=True))
    fields, seen = [], set()
    for item in context.fields:
        key = item.field.key if item.field.name == "assessment" and item.field.basis == "achieved" else None
        if key in replacements:
            fields.append(ContextField(field=item.field, datum=TypedDatum(status="known", value=replacements[key])))
            seen.add(key)
        else:
            fields.append(item)
    for key in keys:
        if key not in seen:
            fields.append(ContextField(field=FieldRef(name="assessment", key=key, basis="achieved"),
                datum=TypedDatum(status="known", value=replacements[key])))
    return validate_context({"fields": fields, "assessment_date": context.assessment_date,
                             "assessment_at": context.assessment_at})


def evaluate_eligibility(expression, context, *, deferrals=None) -> EligibilityEngineResult:
    """Find a minimal legal completion subset; never replace unknown AST leaves.

    The mapping contains only independently verified item results supplied by the
    calling service. A DTO or a symbolic search result does not prove authority.
    """
    expression, context = parse_expression(expression), validate_context(context)
    permissions = _deferrals(deferrals)
    original = evaluate_expression(expression, context)

    def outcome(status, reason, obligations=()):
        return EligibilityEngineResult(status=status, reason=reason, evaluation=original, obligations=obligations)

    if original.truth != "unknown":
        return outcome("eligible" if original.truth == "true" else "ineligible",
                       "RULE_TRUE" if original.truth == "true" else "RULE_FALSE")
    uses = {}
    for atom in _atoms(expression):
        field = atom.field
        if field is not None and field.name == "assessment" and field.basis == "achieved":
            uses.setdefault(field.key, []).append(atom)
    states = {item.field.key: item.datum.status for item in context.fields
              if item.field.name == "assessment" and item.field.basis == "achieved"}
    available = tuple(key for key in ASSESSMENT_KEYS if key in uses
        and states.get(key, "missing") in {"missing", "pending"}
        and key in permissions and permissions[key].deferral_status == "allowed")
    if not available:
        return outcome("unknown", "NO_COMPLETABLE_FIELD")
    domains = {key: _domain(key, uses[key]) for key in available}
    searchable = tuple(key for key in available if domains[key] is not None)
    if not searchable:
        return outcome("unknown", "DOMAIN_UNAVAILABLE")
    attempts = 0
    for count in range(1, len(searchable) + 1):
        for keys in combinations(searchable, count):
            for values in product(*(domains[key] for key in keys)):
                if attempts >= MAX_COMBINATIONS:
                    return outcome("unknown", "SEARCH_BUDGET_EXCEEDED")
                attempts += 1
                completed = _completed_context(context, keys, values)
                if evaluate_expression(expression, completed).truth == "true":
                    return outcome("conditional", "DEFERRAL_SATISFIABLE", tuple(
                        CompletionObligation(assessment_key=key, basis="achieved", deferral=permissions[key]) for key in keys))
    return outcome("unknown", "RULE_UNKNOWN")
