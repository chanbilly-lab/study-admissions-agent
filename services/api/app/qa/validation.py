"""Atomic whole-answer checks; DTO hashes alone never prove current authority."""

from ..model_gateway.schemas import StructuredAnswer
from .schemas import QAError, RetrievedBundle


def validate_claims(bundle, answer, *, current_bundle):
    """Pure content check for two trusted projections, not an authority port."""
    try:
        original = RetrievedBundle.model_validate(bundle)
        current = RetrievedBundle.model_validate(current_bundle)
        answer = StructuredAnswer.model_validate(answer)
        if original.pin_sha256 != current.pin_sha256 or original.request != current.request:
            raise ValueError()
        atoms = {item.citation_id: item for item in current.atoms}
        ids = tuple(item.citation_id for item in answer.claims)
        if len(set(ids)) != len(ids) or any(identifier not in atoms for identifier in ids):
            raise ValueError()
        if any(claim.value != atoms[claim.citation_id].value for claim in answer.claims):
            raise ValueError()
        return answer
    except Exception:
        raise QAError(409) from None


def validate_answer(retriever, bundle, answer):
    """Re-read exact current publication after model waiting, outside its TX."""
    from .retrieval import ScopedRetriever
    try:
        if type(retriever) is not ScopedRetriever:
            raise QAError()
        original = RetrievedBundle.model_validate(bundle)
        current = retriever.retrieve(original.request)
        return validate_claims(original, answer, current_bundle=current)
    except QAError:
        raise
    except Exception:
        raise QAError(409) from None
