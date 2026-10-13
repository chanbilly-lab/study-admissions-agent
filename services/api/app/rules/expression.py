"""Closed T25 syntax and typed inputs, without executable source or free paths."""

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import re
from typing import Annotated, Literal, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_DEPTH = 16
MAX_NODES = 256
MAX_CHILDREN = 32
MAX_EXPRESSION_BYTES = 65536
MAX_INTEGER = 2**53 - 1
SCALAR_FIELDS = ("study_level", "entry_year", "residence_region", "course_system",
                 "applicant_category", "exam_province", "pathway", "subjects")
FieldName = Literal["study_level", "entry_year", "residence_region", "course_system",
                    "applicant_category", "exam_province", "pathway", "subjects",
                    "assessment", "assessment_date", "assessment_at"]
AssessmentKey = Literal["gaokao_total", "chinese", "math", "gaokao_english", "physics",
                        "chemistry", "biology", "politics", "history", "geography",
                        "ielts_overall", "ielts_listening", "ielts_reading", "ielts_writing",
                        "ielts_speaking"]
ASSESSMENT_KEYS = AssessmentKey.__args__
Truth = Literal["true", "false", "unknown"]
Reason = Literal["MATCH", "NO_MATCH", "MISSING", "PENDING", "NOT_APPLICABLE", "CONFLICTED",
                 "TYPE_MISMATCH", "UNIT_MISMATCH", "SCALE_MISMATCH", "PREDICTED_NOT_ACHIEVED",
                 "CALENDAR_MISMATCH", "PRECISION_MISMATCH", "REFERENCE_MISSING", "UNKNOWN_CHILD"]
Operator = Literal["all", "any", "not", "exists", "eq", "in", "gte", "lte", "date_before", "valid_at"]


class RuleInputError(ValueError):
    status_code = 422
    code = "INVALID_RULE_INPUT"

    def __init__(self):
        super().__init__("Rule input is invalid")


class RuleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always",
        hide_input_in_errors=True, validate_default=True, allow_inf_nan=False)


def bounded_text(value):
    if (type(value) is not str or len(value) > 256 or len(value.encode("utf-8")) > 1024
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError("bounded text is required")
    return value


def decimal_value(value):
    if (type(value) is not str or not 1 <= len(value) <= 64
            or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None):
        raise ValueError("an explicit bounded decimal is required")
    return value


def explicit_instant(value):
    try:
        if type(value) is str:
            match = re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(Z|[+-]\d{2}:\d{2})", value)
            if match is None or match[1] == "-00:00":
                raise ValueError()
            offset = match[1]
            if offset != "Z" and (int(offset[1:3]) > 23 or int(offset[4:6]) > 59):
                raise ValueError()
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if (type(value) is not datetime or type(value.tzinfo) not in (timezone, ZoneInfo)
                or value.utcoffset() is None
                or value.fold):
            raise ValueError()
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("an explicit instant is required") from None


class FieldRef(RuleModel):
    name: FieldName
    key: AssessmentKey | None = None
    basis: Literal["achieved", "predicted"] | None = None

    @model_validator(mode="after")
    def fixed_reference(self):
        if self.name == "assessment":
            if self.key is None or self.basis is None:
                raise ValueError("assessment reference requires its exact key and basis")
        elif self.key is not None or self.basis is not None:
            raise ValueError("scalar references cannot contain assessment selectors")
        return self


class TextValue(RuleModel):
    kind: Literal["text"] = "text"
    value: str = Field(strict=True, max_length=256)

    _bounded = field_validator("value")(bounded_text)


class IntegerValue(RuleModel):
    kind: Literal["integer"] = "integer"
    value: int = Field(strict=True, ge=-MAX_INTEGER, le=MAX_INTEGER)


class DecimalValue(RuleModel):
    kind: Literal["decimal"] = "decimal"
    value: str = Field(strict=True, min_length=1, max_length=64)
    unit: Literal["points", "band", "percent", "fraction"]
    scale: str = Field(strict=True, min_length=1, max_length=64)

    _decimal = field_validator("value", "scale")(decimal_value)

    @model_validator(mode="after")
    def exact_scale(self):
        if Decimal(self.scale) <= 0 or Decimal(self.value) > Decimal(self.scale):
            raise ValueError("decimal requires an explicit positive scale")
        return self


class StringSetValue(RuleModel):
    kind: Literal["string_set"] = "string_set"
    value: tuple[str, ...] = Field(max_length=MAX_CHILDREN)

    @field_validator("value", mode="before")
    @classmethod
    def exact_collection(cls, value):
        if type(value) not in (list, tuple) or any(type(item) is not str for item in value):
            raise ValueError("an explicit string collection is required")
        return value

    @field_validator("value")
    @classmethod
    def unique_strings(cls, value):
        for item in value:
            bounded_text(item)
        if len(set(value)) != len(value):
            raise ValueError("set values must be unique")
        return value


class DateValue(RuleModel):
    kind: Literal["date"] = "date"
    value: date = Field(strict=True)
    calendar: str = Field(strict=True, min_length=1, max_length=100)

    @field_validator("value", mode="before")
    @classmethod
    def exact_date(cls, value):
        if type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            value = date.fromisoformat(value)
        if type(value) is not date:
            raise ValueError("an explicit calendar date is required")
        return value

    @field_validator("calendar")
    @classmethod
    def calendar_domain(cls, value):
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:+-]{0,99}", value) is None:
            raise ValueError("an explicit calendar domain is required")
        return value


class InstantValue(RuleModel):
    kind: Literal["instant"] = "instant"
    value: datetime = Field(strict=True)
    precision: Literal["minute", "second"]

    _instant = field_validator("value", mode="before")(explicit_instant)

    @model_validator(mode="after")
    def exact_precision(self):
        if self.value.microsecond or self.precision == "minute" and self.value.second:
            raise ValueError("instant must retain its declared precision")
        return self


TypedValue = Annotated[Union[TextValue, IntegerValue, DecimalValue, StringSetValue,
                            DateValue, InstantValue], Field(discriminator="kind")]


class TypedDatum(RuleModel):
    status: Literal["known", "missing", "pending", "not_applicable", "conflicted"]
    value: TypedValue | None

    @model_validator(mode="after")
    def unknown_is_null(self):
        if (self.status == "known") != (self.value is not None):
            raise ValueError("only known values may contain a typed value")
        return self


class ContextField(RuleModel):
    field: FieldRef
    datum: TypedDatum

    @model_validator(mode="after")
    def reference_fields_are_separate(self):
        if self.field.name in {"assessment_date", "assessment_at"}:
            raise ValueError("reference dates must be explicit context values")
        return self


class EvaluationContext(RuleModel):
    fields: tuple[ContextField, ...] = Field(default=(), max_length=40)
    assessment_date: DateValue | None = None
    assessment_at: InstantValue | None = None

    @model_validator(mode="after")
    def unique_fields(self):
        keys = [(item.field.name, item.field.key, item.field.basis) for item in self.fields]
        if len(set(keys)) != len(keys):
            raise ValueError("context fields must be unique")
        return self


class Expr(RuleModel):
    op: Operator
    children: tuple["Expr", ...] = Field(default=(), max_length=MAX_CHILDREN)
    child: "Expr | None" = None
    field: FieldRef | None = None
    value: TypedValue | None = None
    values: tuple[TypedValue, ...] = Field(default=(), max_length=MAX_CHILDREN)
    start: datetime | None = Field(default=None, strict=True)
    end: datetime | None = Field(default=None, strict=True)

    _window = field_validator("start", "end", mode="before")(
        lambda value: explicit_instant(value) if value is not None else None)

    @model_validator(mode="after")
    def operator_shape(self):
        allowed = {"all": {"children"}, "any": {"children"}, "not": {"child"},
            "exists": {"field"}, "eq": {"field", "value"}, "in": {"field", "values"},
            "gte": {"field", "value"}, "lte": {"field", "value"},
            "date_before": {"field", "value"}, "valid_at": {"start", "end"}}[self.op]
        if self.model_fields_set - allowed - {"op"}:
            raise ValueError("operator contains unrelated fields")
        if self.op in {"all", "any"} and not self.children:
            raise ValueError("logical groups must not be empty")
        if self.op == "not" and self.child is None:
            raise ValueError("not requires one child")
        if "field" in allowed and self.field is None:
            raise ValueError("an exact field is required")
        if "value" in allowed and self.value is None:
            raise ValueError("a typed literal is required")
        if self.op == "in" and (not self.values or any(type(v) is not type(self.values[0]) for v in self.values)):
            raise ValueError("in requires a nonempty homogeneous literal collection")
        if self.op == "valid_at" and (self.start is None or self.end is None or self.start >= self.end):
            raise ValueError("an explicit increasing window is required")
        return self


class TraceNode(RuleModel):
    op: Operator
    field: FieldRef | None
    outcome: Truth
    reason: Reason
    children: tuple[int, ...] = Field(max_length=MAX_CHILDREN)

    @field_validator("children")
    @classmethod
    def bounded_indices(cls, value):
        if any(type(item) is not int or not 0 <= item < MAX_NODES for item in value):
            raise ValueError("bounded trace indices are required")
        return value


class EvaluationResult(RuleModel):
    truth: Truth
    reason: Reason
    trace: tuple[TraceNode, ...] = Field(min_length=1, max_length=MAX_NODES)

    @model_validator(mode="after")
    def root_matches(self):
        if self.trace[0].outcome != self.truth or self.trace[0].reason != self.reason:
            raise ValueError("trace root must match the result")
        return self

    def __bool__(self):
        raise TypeError("Rule truth requires an explicit three-valued comparison")


_MODELS = (FieldRef, TextValue, IntegerValue, DecimalValue, StringSetValue, DateValue,
           InstantValue, TypedDatum, ContextField, EvaluationContext, Expr)


def _charge(budget, size):
    budget[1] += size
    if budget[1] > MAX_EXPRESSION_BYTES:
        raise RuleInputError()


def _charge_string(budget, value):
    # Check code-point length first, so encoding cannot allocate an unbounded
    # temporary. Count JSON escaping without serializing unvalidated input.
    if len(value) > MAX_EXPRESSION_BYTES - budget[1]:
        raise RuleInputError()
    size = len(value.encode("utf-8")) + 2
    size += sum(1 if c in '\\"\\\\\b\f\n\r\t' else 5 if ord(c) < 32 else 0 for c in value)
    _charge(budget, size)


def _native(value, depth=0, ancestors=None, budget=None):
    """Bound and copy native/model input before Pydantic or JSON serialization."""
    ancestors = set() if ancestors is None else ancestors
    budget = [0, 0] if budget is None else budget
    budget[0] += 1
    if depth > 64 or budget[0] > 20000:
        raise RuleInputError()
    kind = type(value)
    if kind is str:
        _charge_string(budget, value)
        return value
    if kind is int:
        if not -MAX_INTEGER <= value <= MAX_INTEGER:
            raise RuleInputError()
        _charge(budget, len(str(value)))
        return value
    if kind in (bool, type(None)):
        _charge(budget, (4 if value else 5) if kind is bool else 4)
        return value
    if kind in (date, datetime):
        if kind is datetime and (type(value.tzinfo) not in (timezone, ZoneInfo) or value.fold):
            raise RuleInputError()
        _charge_string(budget, value.isoformat())
        return value
    if kind not in (dict, tuple, list) + _MODELS:
        raise RuleInputError()
    if id(value) in ancestors:
        raise RuleInputError()
    ancestors.add(id(value))
    try:
        if kind in _MODELS:
            source = value.__dict__
            if kind is Expr:
                source = {key: item for key, item in source.items() if key in value.model_fields_set
                    or key == "op" or item is not None and not (type(item) is tuple and not item)}
            return _native(source, depth + 1, ancestors, budget)
        if kind is dict:
            if any(type(key) is not str for key in value):
                raise RuleInputError()
            _charge(budget, 2 + len(value) * 2 + max(0, len(value) - 1) * 2)
            copied = {}
            for key, item in value.items():
                _charge_string(budget, key)
                copied[key] = _native(item, depth + 1, ancestors, budget)
            return copied
        _charge(budget, 2 + max(0, len(value) - 1) * 2)
        return [_native(item, depth + 1, ancestors, budget) for item in value]
    finally:
        ancestors.remove(id(value))


def _json_default(value):
    if type(value) in (date, datetime):
        return value.isoformat()
    raise RuleInputError()


def _tree_limits(raw):
    stack, count = [(raw, 1)], 0
    while stack:
        current, depth = stack.pop()
        count += 1
        if type(current) is not dict or depth > MAX_DEPTH or count > MAX_NODES:
            raise RuleInputError()
        if current.get("op") in {"all", "any"}:
            children = current.get("children")
            if type(children) is not list or not 1 <= len(children) <= MAX_CHILDREN:
                raise RuleInputError()
            stack.extend((child, depth + 1) for child in children)
        elif current.get("op") == "not":
            stack.append((current.get("child"), depth + 1))


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise RuleInputError()
        result[key] = value
    return result


def _invalid_number(_value):
    raise RuleInputError()


def parse_expression(value) -> Expr:
    try:
        if type(value) in (str, bytes):
            if len(value) > MAX_EXPRESSION_BYTES:
                raise RuleInputError()
            encoded = value.encode("utf-8") if type(value) is str else value
            if len(encoded) > MAX_EXPRESSION_BYTES:
                raise RuleInputError()
            value = json.loads(encoded.decode("utf-8"), object_pairs_hook=_pairs,
                parse_float=_invalid_number, parse_constant=_invalid_number)
        raw = _native(value)
        if len(json.dumps(raw, ensure_ascii=False, default=_json_default).encode("utf-8")) > MAX_EXPRESSION_BYTES:
            raise RuleInputError()
        _tree_limits(raw)
        return Expr.model_validate(raw)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise RuleInputError() from None


def validate_context(value) -> EvaluationContext:
    try:
        return EvaluationContext.model_validate(_native(value))
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise RuleInputError() from None
