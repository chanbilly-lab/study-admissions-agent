"""Exact repeated target identities stay consistent with the original scope."""

from uuid import UUID

from services.api.app.changes.comparator import compare_releases
from services.api.app.changes.service import ChangesService
from services.api.app.rules.adapters.schemas import TargetReference
from tests.unit.changes.test_t34_comparator import snapshot, replacement, published_member


def binding():
    before=snapshot()
    diff=compare_releases(before,replacement(before,(published_member(2,value_text="601"),)),event_type="replaced")
    original=before.members[0]
    scope=original.evidence.scope
    target=TargetReference(dataset_id=scope.dataset_id,institution_id=scope.institution_id,program_id=scope.program_id,
        offering_id=original.fact.offering_id,offering_version=original.fact.offering_version,
        country=scope.country,scope_sha256=original.release_member.scope_sha256)
    source=dict(target=target.model_dump(mode="json"),dataset_id=scope.dataset_id,
        release_id=before.release.release_id,entry_year=scope.entry_year,
        catalogue_is_synthetic=True,profile_is_synthetic=True)
    return source,diff,target


def test_matching_identity_has_actual_business_change():
    source,diff,target=binding()
    actual,reasons=ChangesService._assessment_reasons(source,diff)
    assert actual==target and reasons==("BUSINESS_CHANGED","REFERENCE_REPLACED")


def test_other_program_institution_or_country_is_not_an_affected_target():
    source,diff,target=binding()
    for field,value in (("institution_id",UUID(int=234567)),("program_id",UUID(int=345678)),("country","GB")):
        different=target.model_copy(update={field:value})
        actual,reasons=ChangesService._assessment_reasons({**source,"target":different.model_dump(mode="json")},diff)
        assert actual==different and reasons==()
