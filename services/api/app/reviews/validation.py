"""Intrinsic review gates; literal comparison never determines factual truth."""

import string

from pydantic import ValidationError

from ..evidence.schemas import SnippetData
from ..facts.schemas import TypedCandidate
from ..facts.typing import type_candidate
from ..ingestion.schemas import ParsedRow
from .schemas import ReviewRequest, ReviewsError


SCOPE_FIELDS = (
    "degree", "course", "campus", "teaching_language", "progression_pathway",
    "intake", "application_cycle", "channel", "course_system", "pathway",
    "applicant_category", "province", "exam_system", "subject_scope", "batch_group",
)
_WORD = frozenset(string.ascii_letters + string.digits + "_")
_NUMBER = _WORD | frozenset(".+-−＋－")


def _word_character(value) -> bool:
    return value is not None and (value.isalnum() or value == "_")


def _literal_present(text: str, value: str, *, decimal=False, unit=False) -> bool:
    """Exact text only, with Unicode word and conservative decimal boundaries."""
    start = 0
    while True:
        position = text.find(value, start)
        if position < 0:
            return False
        end = position + len(value)
        left = text[position - 1] if position else None
        right = text[end] if end < len(text) else None
        if decimal:
            valid = (left is None or left not in _NUMBER and not left.isdecimal()) and (
                right is None or right not in _NUMBER and not right.isdecimal())
        else:
            numeric_unit_prefix = unit and left is not None and left.isdecimal()
            valid = (not _word_character(value[0]) or not _word_character(left) or numeric_unit_prefix) and (
                not _word_character(value[-1]) or not _word_character(right))
        if valid:
            return True
        start = position + 1


def validate_review(request: ReviewRequest, fact: TypedCandidate, evidence: SnippetData | None) -> None:
    """Revalidate bounded inputs; authorization, revision and SQL proof stay outside."""
    try:
        current = ReviewRequest.model_validate(request)
        candidate = TypedCandidate.model_validate(fact)
        snippet = SnippetData.model_validate(evidence) if evidence is not None else None
        if current.fact_id != candidate.id or current.expected_fact_version != candidate.version:
            raise ReviewsError(409)
        if current.action == "return":
            return
        requested = {item.fact_id for item in current.conflict_resolutions}
        if requested != set(candidate.conflicting_ids):
            raise ReviewsError(409)
        original = ParsedRow.model_validate({name: getattr(candidate, name) for name in ParsedRow.model_fields})
        base = type_candidate(original, candidate.classification,
            evidence_id=candidate.evidence_id, date_resolution=candidate.date_resolution)
        if base.state != "review_required" or snippet is None:
            raise ReviewsError(422)
        if (snippet.id != candidate.evidence_id or snippet.scope.dataset_id != candidate.dataset_id
            or (snippet.offering_id, snippet.offering_version, snippet.entry_year, snippet.is_synthetic) !=
               (candidate.offering_id, candidate.offering_version, candidate.entry_year, candidate.is_synthetic)):
            raise ReviewsError(422)
        if any(getattr(snippet.scope, field).status == "unknown" for field in SCOPE_FIELDS):
            raise ReviewsError(422)
        checks = {check.field: check.status for check in current.checks}
        statistics_applies = candidate.fact_type == "statistic" or candidate.classification.claim_kind == "historical_statistic"
        if checks["statistics_context"] != ("accepted" if statistics_applies else "not_applicable"):
            raise ReviewsError(422)
        if checks["date_context"] != ("accepted" if candidate.fact_type == "date" else "not_applicable"):
            raise ReviewsError(422)
        comparisons = [(candidate.value_text, candidate.value_kind == "decimal", False)]
        if candidate.unit is not None:
            comparisons.append((candidate.unit, False, True))
        if candidate.footnote_state == "present":
            comparisons.append((candidate.footnote_text, False, False))
        if any(value is None or not _literal_present(snippet.text, value, decimal=decimal, unit=unit)
               for value, decimal, unit in comparisons):
            raise ReviewsError(422)
    except ReviewsError:
        raise
    except (ValidationError, ValueError, TypeError, OverflowError, AttributeError):
        raise ReviewsError(422) from None
