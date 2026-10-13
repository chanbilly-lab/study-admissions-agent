"""Pure, bounded classification of original rows; no model or executable rule."""

import re
from uuid import UUID

from pydantic import ValidationError

from ..ingestion.schemas import MAX_DECIMAL_LENGTH, ParsedRow, _uuid
from .schemas import Classification, DateResolutionSnapshot, FactsError, TypedPayload


_UNITS = {
    "score": {"decimal": {"unknown", "points", "percent", "fraction"}},
    "fee": {"decimal": {"unknown", "CNY", "GBP"}},
    "material": {"text": {"unknown", "text"}, "decimal": {"unknown", "item"}},
    "date": {"text": {"unknown", "ISO_DATE"}},
    "requirement": {"text": {"unknown", "text"}, "decimal": {"unknown", "points", "percent", "fraction", "item"}},
    "statistic": {"decimal": {"unknown", "points", "percent", "fraction", "people"}},
}
_CLAIMS = {
    "score": {"unknown", "minimum_requirement", "typical_offer", "historical_statistic", "information"},
    "requirement": {"unknown", "minimum_requirement", "typical_offer", "information"},
    "fee": {"unknown", "information"},
    "material": {"unknown", "minimum_requirement", "information"},
    "date": {"unknown", "minimum_requirement", "information"},
    "statistic": {"unknown", "historical_statistic", "information"},
}


def normalize_decimal(value: str) -> str:
    """Canonical lexical equality without Decimal context or rounding."""
    if (type(value) is not str or len(value) > MAX_DECIMAL_LENGTH
            or re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None):
        raise FactsError(422)
    negative = value.startswith("-")
    integer, _, fraction = value.lstrip("-").partition(".")
    fraction = fraction.rstrip("0")
    normalized = integer + ("." + fraction if fraction else "")
    return ("-" if negative and normalized != "0" else "") + normalized


def _typed_values(row, classification, *, evidence_id, date_resolution):
    """Intrinsic closed checks; SQL proof and current source policy stay in service."""
    row = ParsedRow.model_validate(row)
    classification = Classification.model_validate(classification)
    evidence_id = _uuid(evidence_id) if evidence_id is not None else None
    date_resolution = DateResolutionSnapshot.model_validate(date_resolution) if date_resolution is not None else None
    if (classification.claim_kind not in _CLAIMS[row.fact_type]
            or classification.unit_code not in _UNITS[row.fact_type].get(row.value_kind, ())):
        raise ValueError("fact, claim, value kind and normalized unit must match the closed matrix")
    if row.fact_type != "date" and (classification.date_event_id is not None or date_resolution is not None):
        raise ValueError("only date facts may contain a date resolution")
    if row.fact_type == "date":
        if (classification.date_event_id is None) != (date_resolution is None):
            raise ValueError("a date reference requires its original resolution snapshot")
        if date_resolution is not None and (
            classification.date_event_id != date_resolution.date_event_id
            or row.offering_id != date_resolution.offering_id
            or row.offering_version != date_resolution.offering_version
            or row.entry_year != date_resolution.entry_year
            or row.value_text != date_resolution.original_text
        ):
            raise ValueError("date snapshot must match the exact original row and offering version")

    normalized = row.value_text
    if row.value_text is not None and row.value_kind == "decimal":
        normalized = normalize_decimal(row.value_text)
        if normalized.startswith("-"):
            raise ValueError("supported numeric values must be nonnegative")
        integer, _, fraction = normalized.partition(".")
        if classification.unit_code == "percent" and (
            len(integer) > 3 or len(integer) == 3 and integer > "100" or integer == "100" and fraction
        ):
            raise ValueError("percent values must be between zero and one hundred")
        if classification.unit_code == "fraction" and (integer not in {"0", "1"} or integer == "1" and fraction):
            raise ValueError("fraction values must be between zero and one")
        if classification.unit_code in {"item", "people"} and fraction:
            raise ValueError("item and people values must be whole counts")

    incomplete = (row.value_text is None or evidence_id is None
        or classification.claim_kind == "unknown" or classification.unit_code == "unknown"
        or classification.period == "unknown" or row.footnote_state == "unknown")
    if classification.claim_kind == "historical_statistic" or row.fact_type == "statistic":
        incomplete = incomplete or (
            classification.statistics_basis in {"unknown", "not_applicable"}
            or any(value is None for value in (classification.statistic_population,
                classification.statistic_denominator, classification.cohort_year, classification.survey_period))
        )
    if row.fact_type == "date":
        incomplete = incomplete or date_resolution is None or date_resolution.conversion_status not in {"unique", "date_only"}
    return normalized, "draft" if incomplete else "review_required"


def type_candidate(row: ParsedRow, classification: Classification, *,
                   evidence_id: UUID | None, date_resolution: DateResolutionSnapshot | None) -> TypedPayload:
    """Revalidate all inputs and derive a candidate, without approval or inference."""
    try:
        current_row = ParsedRow.model_validate(row)
        current_classification = Classification.model_validate(classification)
        current_evidence = _uuid(evidence_id) if evidence_id is not None else None
        current_date = DateResolutionSnapshot.model_validate(date_resolution) if date_resolution is not None else None
        normalized, state = _typed_values(current_row, current_classification,
            evidence_id=current_evidence, date_resolution=current_date)
        return TypedPayload(**current_row.model_dump(), classification=current_classification,
            evidence_id=current_evidence, normalized_value=normalized, date_resolution=current_date,
            state=state, hard_rule=False, publication_eligible=False)
    except (ValidationError, ValueError, TypeError, OverflowError):
        raise FactsError(422) from None
