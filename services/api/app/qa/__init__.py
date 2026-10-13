"""Typed public retrieval; database access is explicit and models stay disabled."""

from .schemas import (CitationData, QAError, QAPolicy, RequestScope, RetrievalRequest, RetrievedBundle,
                      atom_value, bundle_from_public, citation_from_public, fingerprint)
from .validation import validate_answer, validate_claims


def __getattr__(name):
    if name == "ScopedRetriever":
        from .retrieval import ScopedRetriever
        return ScopedRetriever
    raise AttributeError(name)
