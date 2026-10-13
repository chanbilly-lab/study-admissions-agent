"""Independent synthetic citation boundaries; a hash is never current authority."""

from datetime import date, datetime, time, timezone, tzinfo
from hashlib import sha256
import json
import socket
from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest

from services.api.app.admissions_catalog.schemas import ScopeKey
from services.api.app.evidence.schemas import EvidenceLocator, EvidenceScope
from services.api.app.model_gateway.schemas import Claim, ModelScope, StructuredAnswer
from services.api.app.public_catalog.schemas import PublicDateData, PublicEvidenceData, PublicFactData
from services.api.app.qa.schemas import (QAPolicy, QAError, RequestScope, RetrievalRequest,
    CitationData, RetrievedBundle, atom_value, bundle_from_public, citation_from_public, fingerprint)
from services.api.app.qa.retrieval import ScopedRetriever
from services.api.app.qa.validation import validate_answer, validate_claims


NOW = datetime(2026, 10, 4, 4, tzinfo=timezone.utc)
DATASET = UUID("00000000-0000-4000-8000-000000000001")
OFFERING = UUID("00000000-0000-4000-8000-000000000002")
RELEASE = UUID("00000000-0000-4000-8000-000000000003")
EVIDENCE = UUID("00000000-0000-4000-8000-000000000004")
SCOPE_KEYS = ("degree", "course", "campus", "teaching_language", "progression_pathway",
    "intake", "application_cycle", "channel", "course_system", "pathway", "applicant_category",
    "province", "exam_system", "subject_scope", "batch_group")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("T38 independent unit tests must not connect or resolve hosts")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def scope(**changes):
    values = dict(dataset_id=DATASET, institution_id=uuid4(), program_id=uuid4(), country="CN",
        study_level="undergraduate", entry_year=2027,
        **{name: ScopeKey(status="known", value="DEMO_" + name) for name in SCOPE_KEYS})
    values.update(changes)
    return EvidenceScope(**values)


def request(**changes):
    values = dict(release_id=RELEASE, offering_id=OFFERING, offering_version=1, entry_year=2027,
        scope=RequestScope(**scope().model_dump(exclude={"dataset_id"})), intent="requirements", keywords=())
    values.update(changes)
    return RetrievalRequest(**values)


def public_fact(**changes):
    values = dict(fact_type="score", field_key="DEMO_minimum_score", value_kind="decimal",
        value_text="600.00", normalized_value="600", unit="DEMO_points", missing_reason=None,
        footnote_state="present", footnote_text="DEMO_仅适用于指定课程与入学年",
        claim_kind="minimum_requirement", unit_code="points", period="not_applicable",
        statistics_basis="not_applicable", statistic_population=None, statistic_denominator=None,
        cohort_year=None, survey_period=None, evidence_id=EVIDENCE, date_resolution=None)
    return PublicFactData(**{**values, **changes})


def public_evidence(selected_scope, **changes):
    quote = 'DEMO_原文：600.00 DEMO_points；仅适用于指定课程与入学年。'
    raw = quote.encode("utf-8")
    values = dict(evidence_id=EVIDENCE, release_id=RELEASE, release_version=1,
        requirements_version="a" * 64, is_synthetic=True, offering_id=OFFERING,
        offering_version=1, entry_year=2027, language="zh-Hans", quote=quote,
        document_sha256=sha256(raw).hexdigest(), snippet_sha256=sha256(raw).hexdigest(),
        locator=EvidenceLocator(byte_start=0, byte_end=len(raw), line_start=1, line_end=1,
            page=None, section=None, location_kind="utf8_byte_lines"),
        scope=selected_scope, publisher="DEMO_PUBLISHER", authority_claim="claimed_official")
    return PublicEvidenceData(**{**values, **changes})


def bundle(*, fact=None, selected_scope=None, citations=None, **changes):
    selected_scope = selected_scope or scope()
    current_request = request(scope=RequestScope(**selected_scope.model_dump(exclude={"dataset_id"})))
    references = citations if citations is not None else (
        citation_from_public(fact or public_fact(), public_evidence(selected_scope)),)
    values = dict(model_scope=ModelScope(dataset_id=DATASET, entry_year=2027, offering_id=OFFERING,
        offering_version=1), release_version=1, requirements_version="a" * 64,
        content_sha256="b" * 64, citations=references, retrieved_at=NOW, is_synthetic=True)
    values.update(changes)
    return bundle_from_public(current_request, **values)


def answer(current, *, value=None):
    atom = current.atoms[0]
    return StructuredAnswer(status="answered", claims=(Claim(citation_id=atom.citation_id,
        value=atom.value if value is None else value),), advice_codes=())


@pytest.mark.parametrize("changes", [
    {"entry_year": True}, {"entry_year": "2027"}, {"entry_year": 2027.0},
    {"entry_year": 1999}, {"entry_year": 2101}, {"offering_version": False},
    {"offering_version": 0}, {"offering_version": "1"},
    {"release_id": UUID(int=1)}, {"offering_id": UUID(int=2)},
    {"intent": "sql"}, {"intent": ["requirements"]},
    {"keywords": ("DEMO_keyword",) * 6}, {"keywords": (0,)},
    {"owner_user_id": uuid4()}, {"dataset_id": DATASET}, {"profile": {}},
    {"grades": {"score": "750"}}, {"tools": ["fetch_url"]},
])
def test_request_is_closed_strict_and_does_not_accept_private_authority(changes):
    with pytest.raises((ValidationError, QAError)):
        request(**changes)


def test_complete_scope_cannot_be_omitted_or_silently_replaced():
    original = request()
    for field in ("province", "course", "campus", "channel", "applicant_category"):
        raw = original.model_dump()
        del raw["scope"][field]
        with pytest.raises((ValidationError, QAError)):
            RetrievalRequest.model_validate(raw)
    assert original.scope.province.value == "DEMO_province"
    assert original.scope.country == "CN" and original.entry_year == 2027


def test_literal_keyword_is_not_a_tool_or_mutation_instruction():
    value = "DEMO_ OR 1=1; DROP TABLE student_profiles; https://example.invalid"
    # Literal search data is either accepted as a bounded string or safely
    # rejected. Neither branch executes it or adds a retrieval capability.
    try:
        current = request(keywords=(value,))
    except (ValidationError, QAError):
        return
    assert current.keywords == (value,)
    assert set(RetrievalRequest.model_fields) == {
        "release_id", "offering_id", "offering_version", "entry_year", "scope", "intent", "keywords"}


def test_real_gate_cannot_be_opened_by_a_constructed_policy():
    for forged in (QAPolicy.model_construct(enabled=True, allow_test_fixture_read=True, real_qa_ready=True),
            QAPolicy().model_copy(update={"enabled": 1}),
            QAPolicy().model_copy(update={"real_qa_ready": True})):
        with pytest.raises((ValidationError, QAError)):
            QAPolicy.model_validate(forged)


def test_repeated_nested_scope_is_valid_but_cyclic_raw_data_is_not():
    shared = ScopeKey(status="known", value="DEMO_shared")
    current = bundle(selected_scope=scope(**{key: shared for key in SCOPE_KEYS}))
    assert len(current.citations) == len(current.atoms) == 1
    assert RetrievedBundle.model_validate(current) == current
    raw = request().model_dump()
    raw["scope"]["course"] = raw
    with pytest.raises((ValidationError, QAError)):
        RetrievalRequest.model_validate(raw)


@pytest.mark.parametrize("changes", [
    {"version": True}, {"release_version": True}, {"entry_year": 2028},
    {"offering_id": uuid4()}, {"offering_version": 2}, {"evidence_id": uuid4()},
    {"field_key": "DEMO_DIFFERENT_FIELD"}, {"is_synthetic": 1},
    {"content_sha256": "0" * 64}, {"id": uuid4()},
])
def test_copied_citation_cannot_break_exact_public_bindings(changes):
    current = bundle().citations[0]
    for bad in (current.model_copy(update=changes),
            CitationData.model_construct(**{**current.model_dump(), **changes})):
        with pytest.raises((ValidationError, QAError)):
            CitationData.model_validate(bad)


def test_nested_constructed_fact_scope_and_quote_are_revalidated():
    current = bundle()
    citation = current.citations[0]
    forged_fact = citation.fact.model_copy(update={"normalized_value": "750"})
    forged_scope = citation.scope.model_copy(update={"course": ScopeKey(status="unknown", value=None)})
    forged_quote = citation.evidence.model_copy(update={"quote": "DEMO_changed_quote"})
    for changes in ({"fact": forged_fact}, {"scope": forged_scope}, {"evidence": forged_quote}):
        forged = citation.model_copy(update=changes)
        with pytest.raises((ValidationError, QAError)):
            CitationData.model_validate(forged)


def test_numeric_atom_retains_raw_unit_classification_context_and_footnote():
    current = bundle()
    payload = json.loads(current.atoms[0].value)
    assert payload["value_text"] == "600.00" and payload["normalized_value"] == "600"
    assert payload["unit"] == "DEMO_points" and payload["unit_code"] == "points"
    assert payload["claim_kind"] == "minimum_requirement"
    assert payload["footnote_state"] == "present" and payload["footnote_text"] == current.citations[0].fact.footnote_text
    assert current.citations[0].evidence.authority_claim == "claimed_official"
    assert current.citations[0].is_synthetic is True
    assert current.citations[0].id != current.citations[0].evidence_id
    assert current.citations[0].id.version == 4
    assert validate_claims(current, answer(current), current_bundle=current) == answer(current)


@pytest.mark.parametrize("mutator", [
    lambda raw: {**raw, "value_text": "601.00", "normalized_value": "601"},
    lambda raw: {**raw, "unit": "DEMO_band", "unit_code": "band"},
    lambda raw: {**raw, "claim_kind": "minimum_requirement", "cohort_year": 2026},
    lambda raw: {**raw, "footnote_state": "none", "footnote_text": None},
    lambda raw: {**raw, "value_text": "NaN"},
    lambda raw: {**raw, "normalized_value": "1e999"},
])
def test_numeric_or_context_invention_rejects_the_entire_model_answer(mutator):
    current = bundle()
    value = json.dumps(mutator(json.loads(current.atoms[0].value)), ensure_ascii=False,
        sort_keys=True, separators=(",", ":"))
    with pytest.raises(QAError) as caught:
        validate_claims(current, answer(current, value=value), current_bundle=current)
    assert caught.value.status_code == 409


def test_date_only_atom_keeps_precision_and_unknown_official_utc():
    original = PublicDateData(event_type="application_deadline", original_text="DEMO_2027-01-15",
        precision="date", local_date=date(2027, 1, 15), local_time=None, timezone="Europe/London",
        source_alignment="pending", conversion_status="date_only", calculated_utc_instant=None,
        utc_instant=None, tzdata_version="2026.4")
    current = bundle(fact=public_fact(fact_type="date", value_kind="text", value_text=original.original_text,
        normalized_value=None, unit=None, unit_code="ISO_DATE", claim_kind="information",
        date_resolution=original), unknown_reasons=("DATE_UNRESOLVED",))
    payload = json.loads(current.atoms[0].value)
    projected = payload["date_resolution"]
    assert projected["precision"] == "date" and projected["local_time"] is None
    assert projected["utc_instant"] is projected["calculated_utc_instant"] is None
    assert projected["timezone"] == "Europe/London"
    assert validate_claims(current, answer(current), current_bundle=current).status == "answered"
    for changes in ({"local_time": "23:59:00"}, {"utc_instant": "2027-01-15T23:59:00Z"},
            {"local_date": "2027-01-16"}):
        changed = {**payload, "date_resolution": {**projected, **changes}}
        with pytest.raises(QAError):
            validate_claims(current, answer(current, value=json.dumps(changed, ensure_ascii=False,
                sort_keys=True, separators=(",", ":"))), current_bundle=current)


@pytest.mark.parametrize("claim_kind,intent,expected", [
    ("historical_statistic", "requirements", False), ("typical_offer", "requirements", False),
    ("historical_statistic", "background", True), ("typical_offer", "background", True),
    ("minimum_requirement", "requirements", True),
])
def test_original_classification_determines_intent_without_hard_requirement_promotion(claim_kind, intent, expected):
    assert ScopedRetriever._matches_intent(public_fact(claim_kind=claim_kind), intent) is expected


def test_duplicate_or_mixed_good_bad_claims_never_return_a_partial_answer():
    current = bundle()
    good = answer(current).claims[0]
    for claims in ((good, good), (good, Claim(citation_id=uuid4(), value=good.value)),
            (good, Claim(citation_id=good.citation_id, value="DEMO_bad_value"))):
        forged = StructuredAnswer.model_construct(status="answered", claims=claims, advice_codes=())
        with pytest.raises(QAError) as caught:
            validate_claims(current, forged, current_bundle=current)
        assert caught.value.code == "CITATION_CONFLICT"


@pytest.mark.parametrize("change", ["requirements", "content", "full_scope", "version", "year"])
def test_current_self_consistent_changed_bundle_still_invalidates_original_answer(change):
    original = bundle()
    citation = original.citations[0]
    request_values = original.request.model_dump()
    evidence_values = citation.evidence.model_dump()
    model_values = original.model_scope.model_dump()
    if change == "requirements":
        evidence_values["requirements_version"] = "c" * 64
    elif change == "content":
        pass
    elif change == "full_scope":
        changed_scope = citation.scope.model_copy(update={"campus": ScopeKey(status="known", value="DEMO_OTHER_CAMPUS")})
        evidence_values["scope"] = changed_scope
        request_values["scope"] = changed_scope.model_dump(exclude={"dataset_id"})
    elif change == "version":
        evidence_values["offering_version"] = model_values["offering_version"] = request_values["offering_version"] = 2
    else:
        changed_scope = citation.scope.model_copy(update={"entry_year": 2028})
        evidence_values.update(entry_year=2028, scope=changed_scope)
        request_values.update(entry_year=2028, scope=changed_scope.model_dump(exclude={"dataset_id"}))
        model_values["entry_year"] = 2028
    changed_citation = citation_from_public(citation.fact, PublicEvidenceData(**evidence_values))
    changed = bundle_from_public(RetrievalRequest(**request_values), model_scope=ModelScope(**model_values),
        release_version=1, requirements_version=evidence_values["requirements_version"],
        content_sha256="d" * 64 if change == "content" else original.content_sha256,
        citations=(changed_citation,), retrieved_at=NOW, is_synthetic=True)
    assert RetrievedBundle.model_validate(changed) == changed
    with pytest.raises(QAError):
        validate_claims(original, answer(original), current_bundle=changed)


def test_self_hash_or_arbitrary_retrieval_callable_is_not_an_authority_port():
    current = bundle()
    invoked = []
    class FakeRetriever:
        def retrieve(self, value):
            invoked.append(value)
            return current
    for port in (FakeRetriever(), lambda value: current, {"reviewed": True, "bundle": current}):
        with pytest.raises(QAError) as caught:
            validate_answer(port, current, answer(current))
        assert caught.value.status_code == 503
    assert invoked == []


def test_unknown_bundle_cannot_acquire_answered_claims_or_inferred_citations():
    original = request()
    unknown = bundle_from_public(original, retrieved_at=NOW, unknown_reasons=("SCOPE_UNKNOWN",))
    empty = StructuredAnswer(status="unknown", claims=(), advice_codes=("REVIEW_SOURCE",))
    assert validate_claims(unknown, empty, current_bundle=unknown) == empty
    with pytest.raises(QAError):
        validate_claims(unknown, answer(bundle()), current_bundle=unknown)


def test_native_timezone_and_container_subclasses_are_rejected_without_callbacks():
    callbacks = []
    class EvilZone(tzinfo):
        def utcoffset(self, dt):
            callbacks.append("offset")
            return None
    class EvilDict(dict):
        def items(self):
            callbacks.append("items")
            return super().items()
    current = bundle()
    for raw in (EvilDict(current.model_dump()),
            current.model_copy(update={"retrieved_at": datetime(2026, 10, 4, tzinfo=EvilZone())})):
        with pytest.raises((ValidationError, QAError)):
            RetrievedBundle.model_validate(raw)
    assert callbacks == []


def test_large_atom_is_not_silently_truncated_and_duplicate_fields_have_distinct_citations():
    with pytest.raises((ValueError, QAError)):
        atom_value(public_fact(value_text="DEMO_" + "文" * 2000, normalized_value=None, value_kind="text"))
    current = scope()
    first = citation_from_public(public_fact(), public_evidence(current))
    second = citation_from_public(public_fact(field_key="DEMO_other_score"), public_evidence(current))
    assert first.evidence_id == second.evidence_id and first.id != second.id
    assert len(bundle(selected_scope=current, citations=(first, second)).atoms) == 2
