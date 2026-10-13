"""Independent release propagation goldens; no fixture implies live approval."""

from datetime import timedelta, timezone
from decimal import localcontext
from itertools import permutations
from uuid import UUID

from pydantic import ValidationError
import pytest

from services.api.app.admissions_catalog.schemas import ScopeKey
from services.api.app.changes.comparator import compare_releases
from services.api.app.changes.schemas import (
    BusinessDiff, ChangeImpactData, ChangeImpactPage, ChangesError, ChangesPolicy,
    ReleaseSnapshot,
)
from services.api.app.rules.adapters.schemas import TargetReference
from tests.unit.changes.test_t34_comparator import (
    NOW, classification, published_member, replacement, snapshot,
)


def compare(before, members, **changes):
    after = replacement(before, members, **changes)
    # Establish both intrinsic fixed snapshots before testing comparison.
    ReleaseSnapshot.model_validate(before)
    ReleaseSnapshot.model_validate(after)
    return compare_releases(before, after, event_type="replaced")


@pytest.mark.parametrize("order", tuple(permutations(range(3))))
def test_whole_record_permutation_preserves_business_without_pairing_by_id(order):
    rows = tuple(published_member(index+1, value_text=str(600+index),
        interpretation=classification(claim_kind="minimum_requirement" if index != 1 else "typical_offer"),
        footnote_state="present", footnote_text=f"DEMO_note_{index}") for index in range(3))
    before = snapshot(rows)
    result = compare(before, tuple(rows[index] for index in order))
    assert result.semantic_business_changed is False
    assert len(result.member_diffs) == 1 and len(result.member_diffs[0].after) == 3
    assert result.member_diffs[0].changed_fields == ()
    assert result.before_release_id != result.after_release_id and result.reference_changed


@pytest.mark.parametrize("swapped", ["unit", "footnote", "classification"])
def test_equal_field_multisets_do_not_hide_changed_value_relationships(swapped):
    def make(index, position, *, rotate=False):
        associated = (position+1) % 3 if rotate else position
        return published_member(index, value_text=str(600+position),
            unit=f"DEMO_unit_{associated if swapped == 'unit' else position}",
            interpretation=classification(claim_kind=("minimum_requirement", "typical_offer", "information")[
                associated if swapped == "classification" else position]),
            footnote_state="present", footnote_text=f"DEMO_note_{associated if swapped == 'footnote' else position}")
    before = snapshot(tuple(make(index+1, index) for index in range(3)))
    result = compare(before, tuple(make(index+11, index, rotate=True) for index in range(3)))
    assert result.semantic_business_changed
    assert result.member_diffs[0].changed_fields == ("association",)
    assert len(result.member_diffs[0].before_fact_ids) == len(result.member_diffs[0].after_fact_ids) == 3


def test_multiplicity_redistribution_is_not_hidden_by_the_same_distinct_value_set():
    before = snapshot(tuple(published_member(i+1, value_text=value, offering_version=i+1)
        for i, value in enumerate(("600", "600", "650"))))
    result = compare(before, tuple(published_member(i+11, value_text=value, offering_version=i+1)
        for i, value in enumerate(("600", "650", "650"))))
    assert len(result.member_diffs) == 1
    assert result.member_diffs[0].changed_fields == ("value",)
    assert len(result.member_diffs[0].before) == len(result.member_diffs[0].after) == 3


def test_score_requirement_and_field_keys_remain_separate_even_when_numbers_agree():
    before = snapshot((published_member(1), published_member(2, fact_type="requirement"),
        published_member(3, field_key="DEMO_another_score")))
    result = compare(before, (published_member(11, value_text="601"),
        published_member(12, fact_type="requirement"), published_member(13, field_key="DEMO_another_score")))
    assert len(result.member_diffs) == 3
    changed = [group for group in result.member_diffs if group.semantic_business_changed]
    assert len(changed) == 1 and (changed[0].fact_type, changed[0].field_key) == ("score", "DEMO_score")


@pytest.mark.parametrize("scope", ["course", "campus", "channel", "applicant_category", "province"])
def test_one_exact_scope_dimension_change_is_material_without_name_matching(scope):
    before = snapshot()
    changed = published_member(2, scope_changes={scope: ScopeKey(status="known", value="DEMO_other")})
    result = compare(before, (changed,))
    assert result.member_diffs[0].changed_fields == ("scope",)
    assert result.member_diffs[0].offering_id == before.members[0].fact.offering_id


def test_sixty_four_character_numbers_survive_a_low_ambient_decimal_context():
    old_value = "1234567890" * 5 + "12345678.12345"
    assert len(old_value) == 64
    with localcontext() as context:
        context.prec = 2
        before = snapshot((published_member(value_text=old_value),))
        result = compare(before, (published_member(2, value_text=old_value[:-1]+"6"),))
    assert result.member_diffs[0].changed_fields == ("value",)
    assert result.member_diffs[0].before[0].normalized_value == old_value
    assert result.member_diffs[0].after[0].normalized_value == old_value[:-1]+"6"


def test_zero_is_business_data_and_not_an_unpublished_or_pending_value():
    before = snapshot((published_member(value_text="0.0000"),))
    result = compare(before, (published_member(2, value_text=None, missing_reason="not_published"),))
    group = result.member_diffs[0]
    assert group.before[0].normalized_value == "0" and group.before[0].missing_reason is None
    assert group.after[0].normalized_value is None and group.after[0].missing_reason == "not_published"
    assert group.semantic_business_changed and "missing_reason" in group.changed_fields


def test_equivalent_explicit_utc_offsets_do_not_create_a_release_window_change():
    before = snapshot()
    offset = timezone(timedelta(hours=8))
    result = compare(before, before.members,
        valid_from=before.release.valid_from.astimezone(offset),
        valid_until=before.release.valid_until.astimezone(offset))
    assert result.release_changed_fields == () and not result.semantic_business_changed


def test_full_hundred_group_union_preserves_both_sides_and_original_identity():
    before = snapshot(tuple(published_member(i+1, offering_id=UUID(int=200_000+i)) for i in range(50)))
    result = compare(before, tuple(published_member(i+101, offering_id=UUID(int=300_000+i)) for i in range(50)))
    assert len(result.member_diffs) == 100
    assert sum(group.kind == "added" for group in result.member_diffs) == 50
    assert sum(group.kind == "removed" for group in result.member_diffs) == 50
    assert {group.offering_id for group in result.member_diffs} == {
        *(UUID(int=200_000+i) for i in range(50)), *(UUID(int=300_000+i) for i in range(50))}


@pytest.mark.parametrize("member_field", ["fact_id", "evidence_id", "offering_id", "entry_year",
    "offering_version", "fact_sha256", "scope_sha256", "evidence_sha256", "file_sha256"])
def test_an_unverified_individual_reference_cannot_enter_comparison(member_field):
    good = snapshot()
    assert compare_releases(None, good, event_type="published").semantic_business_changed
    member = good.members[0]
    old = getattr(member.release_member, member_field)
    new = UUID(int=999_999) if isinstance(old, UUID) else old+1 if type(old) is int else "f"*64
    forged_member = member.model_copy(update={"release_member":member.release_member.model_copy(update={member_field:new})})
    bad = good.model_copy(update={"members":(forged_member,)})
    with pytest.raises(ChangesError) as failure:
        compare_releases(None, bad, event_type="published")
    assert failure.value.status_code == 422 and str(failure.value) == "INVALID_CHANGE_INPUT"


@pytest.mark.parametrize("bad", [True, 1, 0, "false", None])
def test_real_processing_is_not_enabled_by_forged_false_literals(bad):
    with pytest.raises(ValidationError):
        ChangesPolicy.model_validate(ChangesPolicy().model_copy(update={"real_changes_ready":bad}))


def impact(**changes):
    values = dict(event_id=UUID(int=1), assessment_id=UUID(int=2), plan_id=UUID(int=3),
        before_release_id=UUID(int=4), after_release_id=UUID(int=5), offering_id=UUID(int=6),
        entry_year=2027, needs_review=False, reasons=("REFERENCE_REPLACED",), created_at=NOW)
    return ChangeImpactData(**{**values, **changes})


@pytest.mark.parametrize("reason", ["MEMBER_ADDED", "MEMBER_REMOVED", "BUSINESS_CHANGED",
    "RELEASE_WINDOW_CHANGED", "RULESET_CHANGED", "RELEASE_WITHDRAWN"])
def test_only_reference_replacement_can_have_no_business_review_flag(reason):
    trace = impact()
    assert not trace.needs_review
    changed = impact(needs_review=True, reasons=("REFERENCE_REPLACED", reason))
    assert changed.needs_review
    with pytest.raises(ValidationError):
        ChangeImpactData.model_validate(changed.model_copy(update={"needs_review":False}))


@pytest.mark.parametrize("changes", [{"reasons":("REFERENCE_REPLACED", "REFERENCE_REPLACED")},
    {"reasons":("DEMO_PRIVATE_VALUE_SENTINEL",)}, {"needs_review":1},
    {"entry_year":True}, {"before_release_id":None, "after_release_id":None},
    {"value_text":"DEMO_PRIVATE_VALUE_SENTINEL"}, {"owner_user_id":UUID(int=7)}])
def test_trace_cannot_add_private_values_or_unbounded_caller_conclusions(changes):
    legal = impact()
    with pytest.raises(ValidationError):
        ChangeImpactData.model_validate(legal.model_copy(update=changes))
    assert set(legal.model_dump()) == {"event_id", "assessment_id", "plan_id", "before_release_id",
        "after_release_id", "needs_review", "reasons", "offering_id", "entry_year", "created_at"}


def test_output_is_frozen_and_page_budget_rejects_native_oversize_before_iteration():
    legal = impact()
    with pytest.raises(ValidationError):
        legal.needs_review = True
    assert len(ChangeImpactPage(items=(legal,)*100).items) == 100
    for value in ((legal,)*101, iter((legal,)), {"items":legal}):
        with pytest.raises(ValidationError):
            ChangeImpactPage(items=value)
    result = compare_releases(None, snapshot(), event_type="published")
    with pytest.raises(ValidationError):
        BusinessDiff.model_validate(result.model_copy(update={"member_diffs":(*result.member_diffs,)*101}))


def test_consistent_copied_flags_cannot_hide_the_business_projection_difference():
    before = snapshot()
    result = compare(before, (published_member(2, value_text="601"),))
    assert result.member_diffs[0].changed_fields == ("value",)
    forged = result.member_diffs[0].model_copy(update={"kind":"unchanged", "changed_fields":(),
        "semantic_business_changed":False})
    with pytest.raises(ValidationError):
        BusinessDiff.model_validate(result.model_copy(update={"member_diffs":(forged,),
            "semantic_business_changed":False}))


def target_for(member):
    scope, reference = member.evidence.scope, member.release_member
    return TargetReference(dataset_id=scope.dataset_id, institution_id=scope.institution_id,
        program_id=scope.program_id, country=scope.country, offering_id=reference.offering_id,
        offering_version=reference.offering_version, scope_sha256=reference.scope_sha256)


def selected_groups(result, member):
    from services.api.app.changes.comparator import target_member_diffs
    target = target_for(member)
    return target_member_diffs(result, offering_id=target.offering_id,
        offering_version=target.offering_version, scope_sha256=target.scope_sha256)


def test_new_condition_in_the_original_full_scope_is_not_limited_to_old_rule_fields():
    before = snapshot()
    retained = before.members[0]
    extra = published_member(2, fact_type="requirement", field_key="DEMO_new_requirement",
        value_kind="text", value_text="DEMO_additional_material", interpretation=classification(unit_code="text"))
    result = compare(before, (retained, extra))
    groups = selected_groups(result, retained)
    assert {(group.fact_type, group.field_key) for group in groups} == {
        ("score", "DEMO_score"), ("requirement", "DEMO_new_requirement")}
    added = next(group for group in groups if group.field_key == "DEMO_new_requirement")
    assert added.kind == "added" and added.semantic_business_changed


def test_other_province_change_is_excluded_even_in_the_same_offering_and_field_group():
    original = published_member(1)
    other = published_member(2, offering_version=2,
        scope_changes={"province":ScopeKey(status="known", value="DEMO_other_province")})
    before = snapshot((original, other))
    changed_other = published_member(3, value_text="601", offering_version=2,
        scope_changes={"province":ScopeKey(status="known", value="DEMO_other_province")})
    result = compare(before, (original, changed_other))
    assert result.semantic_business_changed  # The release did change for the other province.
    groups = selected_groups(result, original)
    assert len(groups) == 1 and groups[0].kind == "unchanged"
    assert groups[0].changed_fields == () and not groups[0].semantic_business_changed
    assert groups[0].before_fact_ids == groups[0].after_fact_ids == (original.fact.id,)


def test_removal_of_the_original_scope_is_not_hidden_by_a_same_named_other_scope():
    before = snapshot()
    other = published_member(2, offering_version=2,
        scope_changes={"province":ScopeKey(status="known", value="DEMO_other_province")})
    result = compare(before, (other,))
    groups = selected_groups(result, before.members[0])
    assert len(groups) == 1 and groups[0].kind == "removed"
    assert groups[0].semantic_business_changed and groups[0].after == ()


def test_a_changed_current_offering_version_in_the_same_scope_still_changes_the_old_target():
    before = snapshot()
    current = published_member(2, offering_version=2, value_text="601")
    result = compare(before, (current,))
    groups = selected_groups(result, before.members[0])
    assert len(groups) == 1 and groups[0].changed_fields == ("value",)
    assert groups[0].before_references[0].offering_version == 1
    assert groups[0].after_references[0].offering_version == 2
