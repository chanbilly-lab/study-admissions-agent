"""Offline business comparison goldens; these fixtures do not publish facts."""

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

from pydantic import ValidationError
import pytest

from services.api.app.admissions_catalog.date_schemas import DateEventData, DateEventInput
from services.api.app.admissions_catalog.dates import normalize_date_event
from services.api.app.admissions_catalog.schemas import ScopeKey
from services.api.app.changes.comparator import business_projection, compare_releases, target_member_diffs
from services.api.app.changes.schemas import (
    BusinessDiff, ChangesError, ChangesPolicy, PublishedMember, ReleaseSnapshot, fingerprint,
)
from services.api.app.evidence.schemas import EvidenceLocator, EvidenceScope, SnippetData
from services.api.app.facts.schemas import Classification, DateResolutionSnapshot, TypedCandidate
from services.api.app.facts.typing import type_candidate
from services.api.app.ingestion.schemas import ParsedRow
from services.api.app.releases.schemas import PublishMember, PublishRequest, ReleaseData, ReleaseMemberData
from services.api.app.releases.validation import release_content_hash, requirements_snapshot_hash


NOW = datetime(2026, 10, 4, 4, tzinfo=timezone.utc)
DATASET, OFFERING = UUID(int=10_000), UUID(int=20_000)
SCOPE_FIELDS = ("degree", "course", "campus", "teaching_language", "progression_pathway",
    "intake", "application_cycle", "channel", "course_system", "pathway", "applicant_category",
    "province", "exam_system", "subject_scope", "batch_group")


def classification(**changes):
    fields = dict(claim_kind="minimum_requirement", unit_code="points", period="not_applicable",
        statistics_basis="not_applicable", statistic_population=None, statistic_denominator=None,
        cohort_year=None, survey_period=None, date_event_id=None)
    return Classification(**{**fields, **changes})


def date_snapshot(**changes):
    fields = dict(id=UUID(int=30_000), dataset_id=DATASET, offering_id=OFFERING, offering_version=1,
        entry_year=2027, reference_key="DEMO_T34_date", is_synthetic=True,
        event_type="application_deadline", original_text="DEMO_2027 deadline", precision="date",
        local_date=date(2027, 1, 15), local_time=None, timezone="Europe/London",
        source_alignment="pending", evidence_reference=None)
    original = DateEventInput(**{**fields, **changes})
    resolution = normalize_date_event(original)
    return DateResolutionSnapshot.from_date_event(DateEventData(**original.model_dump(),
        **resolution.model_dump(), utc_instant=None, review_state="draft", evidence_state="unresolved"))


def fact(index=1, *, interpretation=None, date_resolution=None, **changes):
    fields = dict(offering_id=OFFERING, offering_version=1, entry_year=2027,
        source_record_reference="DEMO_T34_record", fact_type="score", field_key="DEMO_score",
        value_kind="decimal", value_text="600.00", unit="DEMO_points", missing_reason=None,
        footnote_state="none", footnote_text=None, locator=None, row_number=1)
    row = ParsedRow(**{**fields, **changes})
    payload = type_candidate(row, interpretation or classification(), evidence_id=UUID(int=40_000 + index),
        date_resolution=date_resolution)
    return TypedCandidate(**payload.model_dump(), id=UUID(int=index), version=1,
        import_id=UUID(int=50_000 + index), import_row_id=UUID(int=60_000 + index), dataset_id=DATASET,
        is_synthetic=True, created_at=NOW, conflicting_ids=())


def published_member(index=1, *, candidate=None, scope_changes=None, evidence_changes=None,
                     member_changes=None, **fact_changes):
    candidate = candidate or fact(index, **fact_changes)
    raw = json.dumps({"value_text": candidate.value_text, "unit": candidate.unit,
        "footnote": candidate.footnote_text}, ensure_ascii=False).encode("utf-8")
    scope = EvidenceScope(dataset_id=candidate.dataset_id, program_id=UUID(int=70_000),
        institution_id=UUID(int=80_000), country="CN", study_level="undergraduate", entry_year=candidate.entry_year,
        **{**{field: ScopeKey(status="known", value="DEMO_" + field) for field in SCOPE_FIELDS}, **(scope_changes or {})})
    evidence = SnippetData(text=raw.decode("utf-8"), snippet_sha256=sha256(raw).hexdigest(),
        locator=EvidenceLocator(byte_start=0, byte_end=len(raw), line_start=1, line_end=1,
            page=None, section=None, location_kind="utf8_byte_lines"),
        id=candidate.evidence_id, document_id=UUID(int=90_000 + index), document_version=1,
        offering_id=candidate.offering_id, offering_version=candidate.offering_version,
        entry_year=candidate.entry_year, language="und", document_sha256=sha256(raw).hexdigest(),
        is_synthetic=True, created_at=NOW, scope=scope)
    if evidence_changes:
        evidence = SnippetData.model_validate({**evidence.model_dump(), **evidence_changes})
    metadata = dict(fact_id=candidate.id, logical_key_hash=fingerprint({"index": index}),
        decision_id=UUID(int=100_000 + index), case_revision=1, offering_id=candidate.offering_id,
        offering_version=candidate.offering_version, entry_year=candidate.entry_year,
        source_id=UUID(int=110_000), source_version=1, evidence_id=evidence.id,
        fact_sha256=fingerprint(candidate.model_dump(mode="json")), scope_sha256=fingerprint(scope.model_dump(mode="json")),
        evidence_sha256=fingerprint(evidence.model_dump(mode="json")), source_sha256="1" * 64,
        file_sha256=evidence.document_sha256, public_evidence=False)
    return PublishedMember(release_member=ReleaseMemberData(**{**metadata, **(member_changes or {})}),
        fact=candidate, evidence=evidence)


def snapshot(members=None, *, release_id=UUID(int=120_000), replaces_release_id=None, **changes):
    members = (published_member(),) if members is None else members
    references = tuple(member.release_member for member in members)
    first = members[0].fact
    request = PublishRequest(dataset_id=first.dataset_id, expected_dataset_revision=1, entry_year=first.entry_year,
        kind="test_fixture", valid_from=NOW - timedelta(hours=1), valid_until=NOW + timedelta(days=1),
        members=tuple(PublishMember(fact_id=member.fact_id, expected_case_revision=member.case_revision,
            expected_decision_id=member.decision_id, public_evidence=member.public_evidence) for member in references),
        replaces_release_id=replaces_release_id, expected_replaced_state_revision=1 if replaces_release_id else None)
    if changes:
        request = PublishRequest.model_validate({**request.model_dump(), **changes})
    release = ReleaseData(release_id=release_id, version=1, dataset_id=request.dataset_id,
        entry_year=request.entry_year, kind=request.kind, is_synthetic=True,
        valid_from=request.valid_from, valid_until=request.valid_until,
        content_sha256=release_content_hash(request, references), requirements_version=requirements_snapshot_hash(references),
        ruleset_version=None, members=references, state="published", state_revision=1, published_at=NOW,
        publisher_user_id=UUID(int=130_000), replaces_release_id=replaces_release_id,
        replaced_by_release_id=None, replayed=False)
    return ReleaseSnapshot(release=release, members=members)


def replacement(before, members=None, **changes):
    return snapshot(members or before.members, release_id=UUID(int=before.release.release_id.int + 1),
        replaces_release_id=before.release.release_id, **changes)


def test_same_business_has_separate_reference_trace_and_keeps_original_decimal():
    before = snapshot()
    after = replacement(before, (published_member(2, value_text="600.0", offering_version=2,
        member_changes={"source_version": 2, "source_sha256": "2" * 64}),))
    result = compare_releases(before, after, event_type="replaced")
    assert result.semantic_business_changed is False and result.reference_changed is True
    group = result.member_diffs[0]
    assert group.kind == "unchanged" and group.reference_changed and group.changed_fields == ()
    assert group.before[0].value_text == "600.00" and group.after[0].value_text == "600.0"
    assert group.before[0].normalized_value == group.after[0].normalized_value == "600"
    assert group.after_references[0].source_version == 2


def test_approval_hash_document_layout_and_locator_do_not_become_business():
    before = snapshot()
    original = before.members[0]
    loc = original.evidence.locator.model_dump()
    loc.update(byte_start=10, byte_end=loc["byte_end"] + 10, line_start=2, line_end=2)
    changed = published_member(1, evidence_changes={"locator": EvidenceLocator(**loc),
        "document_id": UUID(int=999), "document_version": 2, "document_sha256": "a" * 64},
        member_changes={"decision_id": UUID(int=888), "case_revision": 2})
    result = compare_releases(before, replacement(before, (changed,)), event_type="replaced")
    assert not result.semantic_business_changed and result.member_diffs[0].reference_changed


@pytest.mark.parametrize("changes,field", [
    ({"value_text": "601"}, "value"), ({"unit": "DEMO_new_points"}, "unit"),
    ({"footnote_state": "present", "footnote_text": "DEMO_仅部分专业"}, "footnote"),
    ({"value_text": None, "missing_reason": "not_published"}, "missing_reason"),
    ({"interpretation": classification(claim_kind="typical_offer")}, "classification"),
])
def test_material_value_unit_claim_footnote_and_missing_changes(changes, field):
    before = snapshot()
    after = replacement(before, (published_member(2, **changes),))
    result = compare_releases(before, after, event_type="replaced")
    assert result.semantic_business_changed and field in result.member_diffs[0].changed_fields


def test_text_is_not_trimmed_normalized_or_treated_as_natural_language_equivalent():
    before = snapshot((published_member(1, fact_type="requirement", value_kind="text", value_text="DEMO_原要求",
        interpretation=classification(unit_code="text")),))
    after = replacement(before, (published_member(2, fact_type="requirement", value_kind="text", value_text="DEMO_原要求 ",
        interpretation=classification(unit_code="text")),))
    assert "value" in compare_releases(before, after, event_type="replaced").member_diffs[0].changed_fields


def test_full_scope_is_material_and_unknown_does_not_match_known():
    before = snapshot()
    changed = published_member(2, scope_changes={"province": ScopeKey(status="unknown", value=None),
        "degree": ScopeKey(status="known", value="DEMO_degree_new")})
    result = compare_releases(before, replacement(before, (changed,)), event_type="replaced")
    assert result.member_diffs[0].changed_fields == ("scope",)
    assert result.member_diffs[0].before[0].scope.province.status == "known"
    assert result.member_diffs[0].after[0].scope.province.status == "unknown"


def test_same_field_multiple_classifications_are_compared_without_arbitrary_pairing():
    low = published_member(1, value_text="600", interpretation=classification(claim_kind="minimum_requirement"))
    typical = published_member(2, value_text="650", interpretation=classification(claim_kind="typical_offer"))
    before = snapshot((low, typical))
    after = replacement(before, (typical, low))
    result = compare_releases(before, after, event_type="replaced")
    assert len(result.member_diffs) == 1 and not result.semantic_business_changed
    assert len(result.member_diffs[0].before) == len(result.member_diffs[0].after) == 2


def test_multiset_count_is_preserved_for_same_business_across_versions():
    before = snapshot()
    after = replacement(before, (before.members[0], published_member(2, offering_version=2)))
    group = compare_releases(before, after, event_type="replaced").member_diffs[0]
    assert group.semantic_business_changed and len(group.before) == 1 and len(group.after) == 2


def test_association_change_is_not_hidden_by_equal_marginal_field_sets():
    def member(index, value, claim, footnote):
        return published_member(index, value_text=value, interpretation=classification(claim_kind=claim),
            footnote_state="present", footnote_text=footnote)
    before = snapshot((member(1, "600", "minimum_requirement", "DEMO_A"),
                       member(2, "650", "typical_offer", "DEMO_B")))
    after = replacement(before, (member(3, "600", "minimum_requirement", "DEMO_B"),
                                 member(4, "650", "typical_offer", "DEMO_A")))
    group = compare_releases(before, after, event_type="replaced").member_diffs[0]
    assert group.changed_fields == ("association",) and group.semantic_business_changed


def test_exact_high_precision_adjacent_decimal_values_do_not_round_together():
    value = "1234567890" * 5 + "12345678.12345"
    assert len(value) == 64
    before = snapshot((published_member(value_text=value),))
    after = replacement(before, (published_member(2, value_text=value[:-1] + "6"),))
    assert compare_releases(before, after, event_type="replaced").member_diffs[0].changed_fields == ("value",)


def test_statistical_population_denominator_period_and_cohort_are_business():
    def interpretation(**changes):
        return classification(claim_kind="historical_statistic", unit_code="people", period="survey_period",
            statistics_basis="employment", statistic_population="DEMO_毕业生", statistic_denominator="DEMO_全部毕业生",
            cohort_year=2025, survey_period="DEMO_半年", **changes)
    before = snapshot((published_member(fact_type="statistic", value_text="10", interpretation=interpretation()),))
    changed = classification(**{**interpretation().model_dump(), "cohort_year": 2026, "statistic_denominator": "DEMO_已回应毕业生"})
    after = replacement(before, (published_member(2, fact_type="statistic", value_text="10", interpretation=changed),))
    assert compare_releases(before, after, event_type="replaced").member_diffs[0].changed_fields == ("classification",)


def date_member(index=1, **date_changes):
    resolution = date_snapshot(**date_changes)
    candidate = fact(index, fact_type="date", field_key="DEMO_deadline", value_kind="text",
        value_text=resolution.original_text, unit="DEMO_ISO_DATE", date_resolution=resolution,
        interpretation=classification(unit_code="ISO_DATE", date_event_id=resolution.date_event_id))
    return published_member(index, candidate=candidate)


@pytest.mark.parametrize("changes", [
    {"local_date": date(2027, 1, 16)},
    {"precision": "minute", "local_time": time(12, 30)},
    {"event_type": "score_supplement"},
    {"timezone": "Asia/Hong_Kong"},
    {"source_alignment": "conflict"},
])
def test_original_date_precision_calendar_event_and_candidate_state_are_material(changes):
    before = snapshot((date_member(),))
    after = replacement(before, (date_member(2, **changes),))
    group = compare_releases(before, after, event_type="replaced").member_diffs[0]
    assert group.changed_fields == ("date",) and group.after[0].date_resolution.utc_instant is None
    assert group.after[0].date_resolution.tzdata_version == "2026.4"


def test_public_permission_and_release_window_are_independent_material_dimensions():
    before = snapshot()
    after = replacement(before, (published_member(2, member_changes={"public_evidence": True}),),
        valid_until=NOW + timedelta(days=2))
    result = compare_releases(before, after, event_type="replaced")
    assert result.release_changed_fields == ("validity",)
    assert result.member_diffs[0].changed_fields == ("public_evidence",)


def test_added_removed_targets_and_withdrawal_keep_exact_references():
    before = snapshot()
    other = published_member(2, offering_id=UUID(int=20_001))
    after = replacement(before, (other,))
    changed = compare_releases(before, after, event_type="replaced")
    assert {group.kind for group in changed.member_diffs} == {"added", "removed"}
    withdrawn = compare_releases(before, None, event_type="withdrawn")
    assert withdrawn.release_changed_fields == ("availability",) and withdrawn.after_release_id is None
    assert withdrawn.member_diffs[0].before_fact_ids == (before.members[0].fact.id,)
    assert withdrawn.member_diffs[0].after == () and withdrawn.semantic_business_changed


def test_first_publication_has_no_old_reference_and_preserves_new_year():
    new = snapshot((published_member(entry_year=2028),))
    result = compare_releases(None, new, event_type="published")
    assert result.entry_year == 2028 and result.before_release_id is None
    assert result.member_diffs[0].kind == "added"
    # This projection alone does not authorize impacts against an older year's assessment.


def test_different_year_dataset_and_inexact_replacement_are_rejected_safely():
    before = snapshot()
    wrong_year = replacement(before, (published_member(2, entry_year=2028),))
    wrong_target = snapshot(release_id=UUID(int=120_001), replaces_release_id=UUID(int=777))
    other_fact = TypedCandidate.model_validate({**fact(2).model_dump(), "dataset_id": UUID(int=555)})
    wrong_dataset = replacement(before, (published_member(2, candidate=other_fact),))
    for after in (wrong_year, wrong_dataset, wrong_target, before):
        with pytest.raises(ChangesError) as error:
            compare_releases(before, after, event_type="replaced")
        assert error.value.status_code == 422 and str(error.value) == "INVALID_CHANGE_INPUT"


def test_input_members_are_bounded_before_walk_and_maximum_group_is_preserved():
    members = tuple(published_member(index, offering_version=index) for index in range(1, 51))
    maximum = snapshot(members)
    result = compare_releases(None, maximum, event_type="published")
    assert len(result.member_diffs[0].after) == 50
    duplicated_group = result.member_diffs[0].model_copy(update={"field_key": "DEMO_extra_field"})
    with pytest.raises(ValidationError):
        BusinessDiff.model_validate(result.model_copy(update={"member_diffs": (*result.member_diffs, duplicated_group)}))
    bad = maximum.model_copy(update={"members": (*members, members[0])})
    with pytest.raises(ChangesError):
        compare_releases(None, bad, event_type="published")
    for sequence in (iter(members), {members[0].fact.id}, ()):
        with pytest.raises(ValidationError):
            ReleaseSnapshot.model_validate({"release": maximum.release, "members": sequence})


def test_target_comparison_includes_new_fields_not_referenced_by_the_original_rule():
    before = snapshot()
    new_field = published_member(3, fact_type="requirement", field_key="DEMO_new_requirement", value_kind="text",
        value_text="DEMO_new explicit requirement", interpretation=classification(unit_code="text"))
    after = replacement(before, (before.members[0], new_field))
    diff = compare_releases(before, after, event_type="replaced")
    target = before.members[0].release_member
    result = target_member_diffs(diff, offering_id=target.offering_id, offering_version=target.offering_version,
        scope_sha256=target.scope_sha256)
    assert [(item.field_key, item.kind) for item in result] == [("DEMO_new_requirement", "added"), ("DEMO_score", "unchanged")]
    assert result[0].semantic_business_changed and result[0].before == ()


def test_target_comparison_excludes_other_province_and_tracks_removal_of_original_scope():
    before = snapshot()
    same_scope = published_member(2, offering_version=2)
    other_scope = published_member(3, offering_version=3, value_text="999",
        scope_changes={"province": ScopeKey(status="known", value="DEMO_other_province")})
    target = before.members[0].release_member
    for new_members, expected in (((same_scope, other_scope), "unchanged"), ((other_scope,), "removed")):
        diff = compare_releases(before, replacement(before, new_members), event_type="replaced")
        result = target_member_diffs(diff, offering_id=target.offering_id, offering_version=target.offering_version,
            scope_sha256=target.scope_sha256)
        assert len(result) == 1 and result[0].kind == expected
        assert result[0].semantic_business_changed == (expected == "removed")
        assert result[0].reference_changed
        assert all(projection.scope.province.value != "DEMO_other_province" for projection in result[0].after)


def test_target_requires_old_exact_version_scope_and_validates_copied_projection_bindings():
    before = snapshot()
    diff = compare_releases(before, replacement(before, (published_member(2, value_text="601", offering_version=2),)), event_type="replaced")
    target = before.members[0].release_member
    assert target_member_diffs(diff, offering_id=target.offering_id, offering_version=target.offering_version,
        scope_sha256=target.scope_sha256)[0].semantic_business_changed
    assert target_member_diffs(diff, offering_id=target.offering_id, offering_version=2, scope_sha256=target.scope_sha256) == ()
    assert target_member_diffs(diff, offering_id=target.offering_id, offering_version=1, scope_sha256="0" * 64) == ()
    for version, scope_hash in ((True, target.scope_sha256), (0, target.scope_sha256), (1, "SENTINEL")):
        with pytest.raises(ChangesError):
            target_member_diffs(diff, offering_id=target.offering_id, offering_version=version, scope_sha256=scope_hash)
    group = diff.member_diffs[0]
    forged = group.model_copy(update={"after_references": (group.after_references[0].model_copy(update={"scope_sha256": "0" * 64}),)})
    with pytest.raises(ChangesError):
        target_member_diffs(diff.model_copy(update={"member_diffs": (forged,)}),
            offering_id=target.offering_id, offering_version=1, scope_sha256=target.scope_sha256)


def test_copy_construct_cannot_forge_normalized_value_fullscope_hash_or_official_utc():
    original = snapshot()
    member = original.members[0]
    forged_facts = (member.fact.model_copy(update={"normalized_value": "999"}),
        member.fact.model_copy(update={"hard_rule": True}),
        TypedCandidate.model_construct(**{**member.fact.model_dump(), "entry_year": True}))
    forged_members = tuple(member.model_copy(update={"fact": fact}) for fact in forged_facts)
    forged_members += (member.model_copy(update={"release_member": member.release_member.model_copy(update={"scope_sha256": "f" * 64})}),)
    for forged in forged_members:
        with pytest.raises(ChangesError):
            compare_releases(None, original.model_copy(update={"members": (forged,)}), event_type="published")
    dated = snapshot((date_member(),))
    fact_value = dated.members[0].fact
    bad_date = fact_value.date_resolution.model_copy(update={"utc_instant": NOW})
    forged = dated.members[0].model_copy(update={"fact": fact_value.model_copy(update={"date_resolution": bad_date})})
    with pytest.raises(ChangesError):
        compare_releases(None, dated.model_copy(update={"members": (forged,)}), event_type="published")


def test_naive_string_and_custom_timezone_are_rejected_without_callback_or_echo():
    calls = []
    class UntrustedZone(tzinfo):
        def utcoffset(self, value):
            calls.append(value)
            raise RuntimeError("SENTINEL_private")
    original = snapshot()
    for bad in (NOW.isoformat(), NOW.replace(tzinfo=None), NOW.replace(fold=1), NOW.replace(tzinfo=UntrustedZone())):
        release = original.release.model_copy(update={"valid_until": bad})
        with pytest.raises(ChangesError) as error:
            compare_releases(None, original.model_copy(update={"release": release}), event_type="published")
        assert str(error.value) == "INVALID_CHANGE_INPUT"
    assert calls == []


def test_missing_fields_unknown_event_and_output_copy_flags_fail_closed():
    original = snapshot()
    for before, after, event in ((original, original, "published"), (None, None, "withdrawn"),
        (None, original, "SENTINEL_event"), (None, {"secret": "SENTINEL"}, "published")):
        with pytest.raises(ChangesError) as error:
            compare_releases(before, after, event_type=event)
        assert str(error.value) == "INVALID_CHANGE_INPUT"
    result = compare_releases(None, original, event_type="published")
    with pytest.raises(ValidationError):
        BusinessDiff.model_validate(result.model_copy(update={"semantic_business_changed": False}))
    group = result.member_diffs[0].model_copy(update={"kind": "unchanged", "semantic_business_changed": False, "changed_fields": ()})
    with pytest.raises(ValidationError):
        BusinessDiff.model_validate(result.model_copy(update={"member_diffs": (group,)}))
    with pytest.raises(ValidationError):
        ChangesPolicy.model_validate(ChangesPolicy().model_copy(update={"real_changes_ready": 0}))
    assert ChangesPolicy().enabled is False


def test_comparison_does_not_mutate_inputs_and_fresh_import_has_no_database_or_provider():
    before = snapshot()
    after = replacement(before)
    original = (before.model_dump(), after.model_dump())
    compare_releases(before, after, event_type="replaced")
    assert (before.model_dump(), after.model_dump()) == original
    root = Path(__file__).resolve().parents[3]
    code = """
import sys
from services.api.app.changes.comparator import compare_releases
for name in ('sqlalchemy', 'httpx', 'httpcore', 'jose', 'services.api.app.db', 'services.api.app.main'):
    assert name not in sys.modules, name
print('PURE_IMPORT_OK')
"""
    run = subprocess.run([sys.executable, "-B", "-c", code], cwd=root,
        capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "PURE_IMPORT_OK"
