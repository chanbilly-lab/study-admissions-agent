"""Pure candidate contracts: no school facts, persistence, HTTP or providers."""

import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

from pydantic import ValidationError
import pytest

from services.api.app.admissions_catalog.schemas import (
    DatasetData, DatasetInput, InstitutionData, InstitutionInput, MAX_VERSION,
    OfferingData, OfferingInput, OfferingVersionData, OfferingVersionRef,
    ProgramData, ProgramInput, ScopeKey,
)


DATASET = UUID("00000000-0000-0000-0000-000000000001")
INSTITUTION = UUID("00000000-0000-0000-0000-000000000002")
PROGRAM = UUID("00000000-0000-0000-0000-000000000003")
OFFERING = UUID("00000000-0000-0000-0000-000000000004")
VERSION = UUID("00000000-0000-0000-0000-000000000005")
PROGRAM_SCOPES = ("degree", "course", "campus", "teaching_language", "progression_pathway")
OFFERING_SCOPES = ("intake", "application_cycle", "channel", "course_system", "pathway",
    "applicant_category", "province", "exam_system", "subject_scope", "batch_group")


def unknown():
    return ScopeKey(status="unknown", value=None)


def dataset(**changes):
    return dict(id=DATASET, reference_key="DEMO_DATASET", data_mode="demo", is_synthetic=True, **changes)


def institution():
    return dict(id=INSTITUTION, dataset_id=DATASET, reference_key="DEMO_INSTITUTION",
        name="DEMO_合成机构", country="CN", is_synthetic=True)


def program():
    return dict(id=PROGRAM, dataset_id=DATASET, institution_id=INSTITUTION,
        reference_key="DEMO_PROGRAM", name="DEMO_合成项目", study_level="undergraduate",
        is_synthetic=True, **{field: unknown() for field in PROGRAM_SCOPES})


def offering():
    return dict(id=OFFERING, dataset_id=DATASET, program_id=PROGRAM,
        reference_key="DEMO_OFFERING", is_synthetic=True, entry_year=2026,
        **{field: unknown() for field in OFFERING_SCOPES})


def version_reference():
    return dict(dataset_id=DATASET, offering_id=OFFERING, version=1)


def test_explicit_valid_identities_and_exact_version_reference_are_frozen_internal_data():
    cases = [(DatasetInput, dataset()), (DatasetData, dataset(revision=1)),
        (InstitutionInput, institution()), (InstitutionData, institution()),
        (ProgramInput, program()), (ProgramData, program()),
        (OfferingInput, offering()), (OfferingData, {**offering(), "current_version": 1}),
        (OfferingVersionRef, version_reference()),
        (OfferingVersionData, {**version_reference(), "id": VERSION, "is_synthetic": True})]
    for model, payload in cases:
        value = model.model_validate(payload)
        assert model.model_validate(value) == value
        assert model.model_config["frozen"] is True
        assert model.model_config["revalidate_instances"] == "always"
        assert model.model_json_schema()["additionalProperties"] is False
    assert DatasetInput(**dataset()).visibility == "private"
    assert InstitutionInput(**institution()).name == "DEMO_合成机构"
    assert OfferingVersionRef(**version_reference()).model_dump() == version_reference()


@pytest.mark.parametrize("year", [True, False, "2026", 2026.0, 0, -1, 10000, None])
def test_entry_year_is_explicit_strict_bounded_integer(year):
    with pytest.raises(ValidationError):
        OfferingInput(**{**offering(), "entry_year": year})


@pytest.mark.parametrize("year", [1, 9999])
def test_year_numeric_bounds_do_not_guess_current_admissions_year(year):
    assert OfferingInput(**{**offering(), "entry_year": year}).entry_year == year


@pytest.mark.parametrize("model,field,payload", [
    (DatasetData, "revision", dataset()), (OfferingVersionRef, "version", version_reference())])
@pytest.mark.parametrize("invalid", [True, "1", 0, MAX_VERSION + 1])
def test_revision_and_version_are_positive_strict_pg_sized_integers(model, field, payload, invalid):
    with pytest.raises(ValidationError):
        model(**{**payload, field: invalid})


def test_all_version_projections_accept_bound_and_reject_unbounded_current_version():
    assert DatasetData(**dataset(revision=MAX_VERSION)).revision == MAX_VERSION
    assert OfferingData(**{**offering(), "current_version": MAX_VERSION}).current_version == MAX_VERSION
    assert OfferingVersionData(**{**version_reference(), "version": MAX_VERSION,
        "id": VERSION, "is_synthetic": True}).version == MAX_VERSION
    with pytest.raises(ValidationError):
        OfferingData(**{**offering(), "current_version": MAX_VERSION + 1})


@pytest.mark.parametrize("marker", [1, 0, "true", None])
def test_synthetic_marker_is_never_coerced_from_caller_claims(marker):
    for model, payload in [(DatasetInput, dataset()), (OfferingInput, offering()),
        (OfferingVersionData, {**version_reference(), "id": VERSION, "is_synthetic": True})]:
        with pytest.raises(ValidationError):
            model(**{**payload, "is_synthetic": marker})


@pytest.mark.parametrize("changes", [
    dict(data_mode="verified"),
    dict(data_mode="demo", is_synthetic=False, reference_key="candidate_dataset"),
    dict(data_mode="verified", is_synthetic=False, reference_key="DEMO_DATASET"),
    dict(data_mode="verified", is_synthetic=False, reference_key="demo_dataset"),
    dict(reference_key="demo_dataset"), dict(visibility="public"), dict(data_mode="reviewed")])
def test_dataset_mode_private_visibility_and_demo_namespace_are_distinct(changes):
    with pytest.raises(ValidationError):
        DatasetInput(**{**dataset(), **changes})


def test_verified_candidate_namespace_is_private_and_does_not_claim_review_or_publication():
    candidate = DatasetInput(**{**dataset(), "data_mode": "verified", "is_synthetic": False,
        "reference_key": "candidate_namespace"})
    assert candidate.visibility == "private"
    assert "reviewed" not in candidate.model_dump() and "release_id" not in candidate.model_dump()


@pytest.mark.parametrize("changes", [
    dict(is_synthetic=False, reference_key="candidate_institution", name="demo_candidate"),
    dict(is_synthetic=False, reference_key="candidate_institution", name="dEmO_candidate"),
    dict(name="合成机构"), dict(name="demo_合成机构"), dict(reference_key="DEMO_BAD\n")])
def test_reference_and_display_names_cannot_hide_demo_as_real_or_unmarked_synthetic(changes):
    with pytest.raises(ValidationError):
        InstitutionInput(**{**institution(), **changes})


@pytest.mark.parametrize("country", ["cn", "C", "CHN", " CN", None])
def test_country_is_explicit_uppercase_code_and_not_inferred_from_scope(country):
    with pytest.raises(ValidationError):
        InstitutionInput(**{**institution(), "country": country})


def test_display_names_allow_bounded_human_text_without_serving_as_identity_keys():
    maximum = "DEMO_" + "学" * 195
    assert ProgramInput(**{**program(), "name": maximum}).name == maximum
    with pytest.raises(ValidationError):
        ProgramInput(**{**program(), "name": maximum + "学"})
    with pytest.raises(ValidationError):
        InstitutionInput(**{**institution(), "name": "DEMO_私有\x00文本"})


def test_canonical_scopes_preserve_case_and_distinguish_missing_from_actual_values():
    scopes = [ScopeKey(status="unknown", value=None), ScopeKey(status="not_applicable", value=None),
        ScopeKey(status="known", value="unknown"), ScopeKey(status="known", value="not_applicable"),
        ScopeKey(status="known", value="DEMO_SCOPE"), ScopeKey(status="known", value="demo_scope")]
    keys = [scope.canonical_key() for scope in scopes]
    assert len(set(keys)) == len(scopes)
    for scope in scopes:
        assert ScopeKey.from_canonical_key(scope.canonical_key()) == scope
    maximum = ScopeKey(status="known", value="A" * 100)
    assert len(maximum.canonical_key().encode("utf-8")) == 106


@pytest.mark.parametrize("payload", [
    dict(status="known", value=None), dict(status="unknown", value="DEMO_SCOPE"),
    dict(status="not_applicable", value="DEMO_SCOPE"), dict(status="missing", value=None),
    dict(status="known", value=""), dict(status="known", value="A" * 101),
    dict(status="known", value=" DEMO_SCOPE"), dict(status="known", value="DEMO_SCOPE\n"),
    dict(status="known", value="DEMO\x00SCOPE"), dict(status="known", value=123),
    dict(status="known", value="海南"), dict(status="known", value="DEMO_😀")])
def test_scope_state_value_and_ascii_code_budget_are_enforced(payload):
    with pytest.raises(ValidationError):
        ScopeKey(**payload)


@pytest.mark.parametrize("key", ["", "KNOWN:DEMO_SCOPE", "known:", "unknown:DEMO_SCOPE",
    "unknown\n", " unknown", "known:DEMO_SCOPE ", None, b"unknown"])
def test_decoding_canonical_keys_does_not_normalize_malformed_or_missing_input(key):
    with pytest.raises((ValidationError, ValueError)):
        ScopeKey.from_canonical_key(key)


@pytest.mark.parametrize("forgery", ["copy", "construct"])
@pytest.mark.parametrize("case", ["dataset", "scope", "nested_scope"])
def test_boundary_revalidation_rejects_forged_outer_and_nested_instances(forgery, case):
    if case == "dataset":
        original = DatasetInput(**dataset())
        changes = dict(visibility="public")
        model = DatasetInput
    elif case == "scope":
        original = unknown()
        changes = dict(status="known")
        model = ScopeKey
    else:
        bad_scope = unknown().model_copy(update={"status": "known"})
        original = OfferingInput(**offering())
        changes = dict(province=bad_scope)
        model = OfferingInput
    forged = original.model_copy(update=changes) if forgery == "copy" else model.model_construct(
        **{**original.model_dump(), **changes})
    with pytest.raises(ValidationError):
        model.model_validate(forged)


@pytest.mark.parametrize("forgery", ["copy", "construct"])
def test_key_encoder_itself_revalidates_bypassed_instances(forgery):
    source = unknown()
    forged = source.model_copy(update={"status": "known"}) if forgery == "copy" else ScopeKey.model_construct(
        status="known", value=None)
    with pytest.raises(ValidationError):
        forged.canonical_key()


def test_required_scope_and_year_fields_have_no_country_province_or_cycle_defaults():
    for model, payload, fields in [(ProgramInput, program(), ("degree", "campus")),
        (OfferingInput, offering(), ("entry_year", "province", "application_cycle")),
        (ScopeKey, dict(status="unknown", value=None), ("value",))]:
        for field in fields:
            missing = {key: value for key, value in payload.items() if key != field}
            with pytest.raises(ValidationError):
                model(**missing)
    # An explicit not_applicable value is accepted, never guessed from GB.
    scoped = OfferingInput(**{**offering(), "province": ScopeKey(status="not_applicable", value=None)})
    assert scoped.province.canonical_key() == "not_applicable"


@pytest.mark.parametrize("extra", ["release_id", "published_at", "payload", "rules"])
def test_catalog_identities_do_not_accept_future_date_fact_or_release_payload(extra):
    with pytest.raises(ValidationError) as rejected:
        OfferingInput(**{**offering(), extra: "T11_UNTRUSTED_PRIVATE_SENTINEL"})
    assert "T11_UNTRUSTED_PRIVATE_SENTINEL" not in str(rejected.value)


def test_frozen_instances_and_uuid_identity_are_not_freeform_mutable_labels():
    for instance, field, value in [(unknown(), "status", "not_applicable"),
        (DatasetInput(**dataset()), "is_synthetic", False), (OfferingInput(**offering()), "entry_year", 2027)]:
        with pytest.raises(ValidationError):
            setattr(instance, field, value)
    with pytest.raises(ValidationError):
        DatasetInput(**{**dataset(), "id": "DEMO_DATASET"})


def test_pure_schema_import_does_not_load_m0_db_providers_or_catalog_storage():
    completed = subprocess.run([sys.executable, "-B", "-c", r'''
import json
import sys
import services.api.app.admissions_catalog.schemas
forbidden = ("sqlalchemy", "services.api.app.main", "services.api.app.models",
    "services.api.app.admissions_catalog.models", "services.api.app.admissions_catalog.store",
    "services.api.app.auth", "services.api.app.providers")
print(json.dumps([name for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)]))
'''], cwd=Path(__file__).resolve().parents[3], capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == "" and json.loads(completed.stdout) == []
