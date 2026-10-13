"""Deterministic Kleene evaluation; no authorization or eligibility decision."""

from decimal import Decimal

from .expression import (
    ASSESSMENT_KEYS, ContextField, DateValue, DecimalValue, EvaluationContext, EvaluationResult,
    FieldRef, InstantValue, IntegerValue, RuleInputError, StringSetValue, TextValue,
    TraceNode, TypedDatum, parse_expression, validate_context,
)


def _field_value(field, context):
    if field.basis == "predicted":
        return None, "PREDICTED_NOT_ACHIEVED"
    if field.name == "assessment_date":
        return context.assessment_date, "REFERENCE_MISSING" if context.assessment_date is None else None
    if field.name == "assessment_at":
        return context.assessment_at, "REFERENCE_MISSING" if context.assessment_at is None else None
    for item in context.fields:
        if item.field == field:
            if item.datum.status == "known":
                value = item.datum.value
                expected_kind = (IntegerValue if field.name == "entry_year" else
                    StringSetValue if field.name == "subjects" else
                    DecimalValue if field.name == "assessment" else TextValue)
                if type(value) is not expected_kind:
                    return None, "TYPE_MISMATCH"
                if field.name == "assessment" and value.unit != ("band" if field.key.startswith("ielts_") else "points"):
                    return None, "UNIT_MISMATCH"
                return value, None
            return None, {"missing": "MISSING", "pending": "PENDING",
                          "not_applicable": "NOT_APPLICABLE", "conflicted": "CONFLICTED"}[item.datum.status]
    return None, "MISSING"


def _compatibility(actual, expected):
    if type(actual) is not type(expected):
        return "TYPE_MISMATCH"
    if type(actual) is DecimalValue:
        if actual.unit != expected.unit:
            return "UNIT_MISMATCH"
        if Decimal(actual.scale) != Decimal(expected.scale):
            return "SCALE_MISMATCH"
    elif type(actual) is DateValue:
        if actual.calendar != expected.calendar:
            return "CALENDAR_MISMATCH"
    elif type(actual) is InstantValue:
        if actual.precision != expected.precision:
            return "PRECISION_MISMATCH"
    return None


def _equal(actual, expected):
    if type(actual) is DecimalValue:
        return Decimal(actual.value) == Decimal(expected.value)
    if type(actual) is StringSetValue:
        return set(actual.value) == set(expected.value)
    return actual.value == expected.value


def _known_result(value):
    return ("true", "MATCH") if value else ("false", "NO_MATCH")


def _atom(expression, context):
    if expression.op == "valid_at":
        if context.assessment_at is None:
            return "unknown", "REFERENCE_MISSING"
        return _known_result(expression.start <= context.assessment_at.value < expression.end)
    actual, problem = _field_value(expression.field, context)
    if problem:
        return "unknown", problem
    if expression.op == "exists":
        return "true", "MATCH"
    if expression.op == "in":
        if type(actual) is StringSetValue:
            if any(type(item) is not TextValue for item in expression.values):
                return "unknown", "TYPE_MISMATCH"
            return _known_result(bool(set(actual.value).intersection(item.value for item in expression.values)))
        # Validate the entire finite membership collection before determining a
        # match; an early matching item cannot hide incompatible units/scales.
        for expected in expression.values:
            problem = _compatibility(actual, expected)
            if problem:
                return "unknown", problem
        return _known_result(any(_equal(actual, expected) for expected in expression.values))
    problem = _compatibility(actual, expression.value)
    if problem:
        return "unknown", problem
    if expression.op == "eq":
        return _known_result(_equal(actual, expression.value))
    if expression.op in {"gte", "lte"}:
        if type(actual) not in {IntegerValue, DecimalValue}:
            return "unknown", "TYPE_MISMATCH"
        left = Decimal(actual.value) if type(actual) is DecimalValue else actual.value
        right = Decimal(expression.value.value) if type(actual) is DecimalValue else expression.value.value
        return _known_result(left >= right if expression.op == "gte" else left <= right)
    if expression.op == "date_before":
        if type(actual) not in {DateValue, InstantValue}:
            return "unknown", "TYPE_MISMATCH"
        return _known_result(actual.value < expression.value.value)
    raise RuleInputError()


def evaluate_expression(expression, context) -> EvaluationResult:
    """Validate the whole AST first, then calculate every bounded branch."""
    expression, context = parse_expression(expression), validate_context(context)
    trace = []

    def visit(node):
        index = len(trace)
        trace.append(None)
        children = []
        if node.op in {"all", "any"}:
            values = []
            for child in node.children:
                child_index, outcome, _reason = visit(child)
                children.append(child_index)
                values.append(outcome)
            if node.op == "all":
                truth = "false" if "false" in values else "unknown" if "unknown" in values else "true"
            else:
                truth = "true" if "true" in values else "unknown" if "unknown" in values else "false"
            reason = "UNKNOWN_CHILD" if truth == "unknown" else "MATCH" if truth == "true" else "NO_MATCH"
        elif node.op == "not":
            child_index, value, _reason = visit(node.child)
            children.append(child_index)
            truth = {"true": "false", "false": "true", "unknown": "unknown"}[value]
            reason = "UNKNOWN_CHILD" if truth == "unknown" else "MATCH" if truth == "true" else "NO_MATCH"
        else:
            truth, reason = _atom(node, context)
        trace[index] = TraceNode(op=node.op, field=node.field, outcome=truth, reason=reason,
                                 children=tuple(children))
        return index, truth, reason

    _, truth, reason = visit(expression)
    return EvaluationResult(truth=truth, reason=reason, trace=tuple(trace))


def context_from_profile(profile, *, assessment_date=None, assessment_at=None) -> EvaluationContext:
    """Project only fixed declared fields; no inferred scope or score fallback."""
    try:
        from ..profiles.schemas import ProfileSnapshot

        profile = ProfileSnapshot.model_validate(profile)
        fields = [ContextField(field=FieldRef(name="study_level"),
                               datum=TypedDatum(status="known", value=TextValue(value=profile.study_level))),
                  ContextField(field=FieldRef(name="entry_year"),
                               datum=TypedDatum(status="known", value=IntegerValue(value=profile.entry_year)))]
        for name, scope in (("residence_region", profile.residence_region),
                            ("course_system", profile.course_system),
                            ("applicant_category", profile.applicant_category),
                            ("exam_province", profile.exam_province), ("pathway", profile.pathway)):
            status = "known" if scope.status == "known" else "not_applicable" if scope.status == "not_applicable" else "missing"
            fields.append(ContextField(field=FieldRef(name=name), datum=TypedDatum(status=status,
                value=TextValue(value=scope.value) if status == "known" else None)))
        # T23 has no separate explicitly-confirmed empty subject declaration.
        fields.append(ContextField(field=FieldRef(name="subjects"), datum=TypedDatum(
            status="known" if profile.subjects else "missing",
            value=StringSetValue(value=profile.subjects) if profile.subjects else None)))
        for key in ASSESSMENT_KEYS:
            pair = profile.assessments.get(key)
            slots = (("achieved", pair.achieved if pair else None),
                     ("predicted", pair.predicted if pair else None))
            for basis, slot in slots:
                status = "missing" if slot is None else "known" if slot.status == "provided" else slot.status
                fields.append(ContextField(field=FieldRef(name="assessment", key=key, basis=basis),
                    datum=TypedDatum(status=status, value=DecimalValue(value=slot.value, unit=slot.unit,
                        scale=slot.scale) if status == "known" else None)))
        return validate_context(EvaluationContext(fields=tuple(fields),
            assessment_date=assessment_date, assessment_at=assessment_at))
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise RuleInputError() from None
