"""Exact public projections and atomic typed claim checks, wholly offline."""

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from pydantic import ValidationError
import pytest

from services.api.app.evidence.schemas import EvidenceLocator, EvidenceScope
from services.api.app.admissions_catalog.schemas import ScopeKey
from services.api.app.model_gateway.schemas import Claim, ModelScope, StructuredAnswer
from services.api.app.public_catalog.schemas import PublicEvidenceData, PublicFactData
from services.api.app.qa import (QAError, QAPolicy, RequestScope, RetrievalRequest, RetrievedBundle,
    atom_value, bundle_from_public, citation_from_public, validate_claims)
from services.api.app.qa.retrieval import ScopedRetriever
from services.api.app.qa.schemas import ProjectionLimit

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def fixture_bundle(*, field_key="total_threshold", value_text="600.00", normalized_value="600", unit="points"):
    scope = EvidenceScope(dataset_id=uuid4(), institution_id=uuid4(), program_id=uuid4(), country="CN",
        study_level="undergraduate", entry_year=2026, **{name: ScopeKey(status="known", value="DEMO_" + name)
        for name in RequestScope.model_fields if name not in {"institution_id", "program_id", "country", "study_level", "entry_year"}})
    request = RetrievalRequest(release_id=uuid4(), offering_id=uuid4(), offering_version=1, entry_year=2026,
        scope=RequestScope.model_validate(scope.model_dump(exclude={"dataset_id"})), intent="requirements")
    evidence_id = uuid4()
    fact = PublicFactData(fact_type="score", field_key=field_key, value_kind="decimal", value_text=value_text,
        normalized_value=normalized_value, unit=unit, missing_reason=None, footnote_state="present",
        footnote_text="DEMO_original footnote", claim_kind="minimum_requirement", unit_code="points",
        period="not_applicable", statistics_basis="not_applicable", statistic_population=None,
        statistic_denominator=None, cohort_year=None, survey_period=None, evidence_id=evidence_id, date_resolution=None)
    quote = "DEMO_original source 600.00"
    evidence = PublicEvidenceData(evidence_id=evidence_id, release_id=request.release_id, release_version=1,
        requirements_version="a" * 64, is_synthetic=True, offering_id=request.offering_id, offering_version=1,
        entry_year=2026, language="en", quote=quote, document_sha256="b" * 64,
        snippet_sha256=sha256(quote.encode()).hexdigest(), locator=EvidenceLocator(location_kind="utf8_byte_lines", byte_start=0,
        byte_end=len(quote.encode()), line_start=1, line_end=1, page=None, section=None), scope=scope,
        publisher="DEMO_publisher", authority_claim="claimed_official")
    citation = citation_from_public(fact, evidence)
    bundle = bundle_from_public(request, model_scope=ModelScope(dataset_id=scope.dataset_id,
        offering_id=request.offering_id, offering_version=1, entry_year=2026), release_version=1,
        requirements_version="a" * 64, content_sha256="c" * 64, citations=(citation,),
        retrieved_at=NOW, is_synthetic=True)
    return bundle


def answered(bundle):
    return StructuredAnswer(status="answered", claims=(Claim(citation_id=bundle.atoms[0].citation_id,
        value=bundle.atoms[0].value),), advice_codes=())


def test_projection_preserves_original_number_unit_footnote_and_independent_reference():
    bundle = fixture_bundle()
    citation = bundle.citations[0]
    assert citation.id.version == 4 and citation.version == 1 and citation.id != citation.evidence_id
    assert citation.fact.value_text == "600.00" and citation.fact.normalized_value == "600"
    assert '"unit":"points"' in bundle.atoms[0].value
    assert '"footnote_text":"DEMO_original footnote"' in bundle.atoms[0].value
    assert 'evidence_id' not in bundle.atoms[0].value
    assert validate_claims(bundle, answered(bundle), current_bundle=bundle) == answered(bundle)


def test_canonical_projection_is_stable_and_same_evidence_two_fields_has_two_ids():
    bundle = fixture_bundle()
    first = bundle.citations[0]
    same = citation_from_public(first.fact, first.evidence)
    other = citation_from_public(first.fact.model_copy(update={"field_key": "math_threshold"}), first.evidence)
    assert same.id == first.id and same.content_sha256 == first.content_sha256
    assert other.evidence_id == first.evidence_id and other.id != first.id
    combined = bundle_from_public(bundle.request, model_scope=bundle.model_scope, release_version=1,
        requirements_version=bundle.requirements_version, content_sha256=bundle.content_sha256,
        citations=(first, other), retrieved_at=NOW, is_synthetic=True)
    assert len(combined.atoms) == 2


@pytest.mark.parametrize("changes", [{"owner_user_id": uuid4()}, {"tools": ()}, {"entry_year": True},
    {"offering_version": 0}, {"entry_year": 2027}, {"keywords": ("x",) * 6}, {"keywords": ("x", "x")}])
def test_request_is_closed_and_does_not_coerce_scope(changes):
    request = fixture_bundle().request
    with pytest.raises(ValidationError):
        RetrievalRequest.model_validate(request.model_copy(update=changes))


def test_dataset_is_server_derived_and_unknown_scope_is_explicit():
    bundle = fixture_bundle()
    with pytest.raises(ValidationError):
        RequestScope.model_validate({**bundle.request.scope.model_dump(), "dataset_id": uuid4()})
    scope = bundle.request.scope.model_copy(update={"province": ScopeKey(status="unknown", value=None)})
    request = bundle.request.model_copy(update={"scope": scope})
    unknown = bundle_from_public(request, retrieved_at=NOW, unknown_reasons=("SCOPE_UNKNOWN",))
    assert unknown.model_scope is None and not unknown.atoms and unknown.is_synthetic is None
    answer = StructuredAnswer(status="unknown", claims=(), advice_codes=("MISSING_EVIDENCE",))
    assert validate_claims(unknown, answer, current_bundle=unknown) == answer


@pytest.mark.parametrize("value", ["600", "600.00 points", "750", "2026-10-04T23:59:00Z"])
def test_answer_cannot_drop_unit_context_or_invent_a_number_or_date(value):
    bundle = fixture_bundle()
    answer = StructuredAnswer(status="answered", claims=(Claim(citation_id=bundle.atoms[0].citation_id,
        value=value),), advice_codes=())
    with pytest.raises(QAError) as caught:
        validate_claims(bundle, answer, current_bundle=bundle)
    assert caught.value.code == "CITATION_CONFLICT"


def test_new_timestamp_does_not_change_content_pin_but_changed_current_content_does():
    bundle = fixture_bundle()
    refreshed = bundle.model_copy(update={"retrieved_at": datetime(2026, 10, 4, 1, tzinfo=timezone.utc)})
    assert RetrievedBundle.model_validate(refreshed).pin_sha256 == bundle.pin_sha256
    assert validate_claims(bundle, answered(bundle), current_bundle=refreshed)
    with pytest.raises(QAError):
        validate_claims(bundle, answered(bundle), current_bundle=fixture_bundle())


def test_duplicate_claim_rejects_entire_answer_and_unknown_has_no_invented_facts():
    bundle = fixture_bundle()
    claim = answered(bundle).claims[0]
    with pytest.raises(QAError):
        validate_claims(bundle, StructuredAnswer(status="answered", claims=(claim, claim), advice_codes=()),
                        current_bundle=bundle)
    unknown = StructuredAnswer(status="unknown", claims=(), advice_codes=("REVIEW_SOURCE",))
    assert validate_claims(bundle, unknown, current_bundle=bundle) == unknown


def test_atom_budget_is_explicit_and_real_processing_is_exactly_closed():
    bundle = fixture_bundle()
    with pytest.raises(ProjectionLimit):
        atom_value(bundle.citations[0].fact.model_copy(update={"footnote_text": "DEMO_" + "x" * 1999}))
    for value in (True, 0, "false"):
        with pytest.raises(ValidationError):
            QAPolicy(real_qa_ready=value)


def test_invalid_public_field_is_rejected_instead_of_being_reported_as_a_limit():
    bundle = fixture_bundle()
    invalid = bundle.citations[0].fact.model_copy(update={"value_text": True})
    with pytest.raises(ValidationError):
        atom_value(invalid)
    with pytest.raises(ValidationError):
        ScopedRetriever._bounded_bundle(bundle.request, model_scope=bundle.model_scope,
            release_version=1, requirements_version=bundle.requirements_version,
            content_sha256=bundle.content_sha256, citations=(), retrieved_at=NOW,
            is_synthetic="true", unknown_reasons=("NO_MATCHING_FACTS",))


def test_whole_projection_budget_returns_no_partial_citations_and_keeps_exact_release_pins():
    bundle = fixture_bundle()
    first = bundle.citations[0]
    scope = first.scope.model_copy(update={name: ScopeKey(status="known", value="DEMO_" + "x" * 95)
        for name in RequestScope.model_fields if name not in {"institution_id", "program_id", "country", "study_level", "entry_year"}})
    request = bundle.request.model_copy(update={"scope": RequestScope.model_validate(scope.model_dump(exclude={"dataset_id"}))})
    quote = "DEMO_" + "x" * 4091
    evidence = first.evidence.model_copy(update={"scope": scope, "quote": quote,
        "snippet_sha256": sha256(quote.encode()).hexdigest(), "locator": EvidenceLocator(
            location_kind="utf8_byte_lines", byte_start=0, byte_end=len(quote), line_start=1, line_end=1,
            page=None, section=None)})
    fact = first.fact.model_copy(update={"footnote_text": "DEMO_" + "x" * 1300})
    citations = tuple(citation_from_public(fact.model_copy(update={"field_key": "DEMO_" + str(index) + "x" * 80}), evidence)
                      for index in range(20))
    values = dict(model_scope=bundle.model_scope, release_version=1, requirements_version=bundle.requirements_version,
        content_sha256=bundle.content_sha256, citations=citations, retrieved_at=NOW, is_synthetic=True)
    with pytest.raises(ProjectionLimit):
        bundle_from_public(request, **values)
    result = ScopedRetriever._bounded_bundle(request, **values)
    assert result.unknown_reasons == ("LIMIT_EXCEEDED",) and result.citations == result.atoms == ()
    assert result.requirements_version == bundle.requirements_version and result.content_sha256 == bundle.content_sha256
