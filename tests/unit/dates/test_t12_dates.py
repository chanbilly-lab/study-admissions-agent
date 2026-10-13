"""Synthetic candidate dates only; no external source, database or HTTP calls."""

import json
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from services.api.app.admissions_catalog.date_schemas import (
    DateEventData, DateEventInput, DateResolution,
)
from services.api.app.admissions_catalog.dates import normalize_date_event


def candidate(**changes):
    return {
        "id": UUID(int=1), "dataset_id": UUID(int=2), "offering_id": UUID(int=3),
        "offering_version": 1, "entry_year": 2026, "reference_key": "DEMO_DATE",
        "is_synthetic": True, "event_type": "application_deadline",
        "original_text": "DEMO_ synthetic deadline text; pending human comparison.",
        "local_date": date(2026, 1, 15), "local_time": time(18, 0),
        "timezone": "Europe/London", "precision": "minute",
        "source_alignment": "pending", "evidence_reference": None,
        **changes,
    }


def output(payload):
    current = DateEventInput(**payload)
    resolved = normalize_date_event(current)
    return {**current.model_dump(), **resolved.model_dump(), "utc_instant": None,
            "review_state": "draft", "evidence_state": "unresolved"}


@pytest.mark.parametrize("local_date,local_time,zone,expected", [
    (date(2026, 1, 15), time(18), "Europe/London", datetime(2026, 1, 15, 18, tzinfo=timezone.utc)),
    (date(2026, 7, 15), time(18), "Europe/London", datetime(2026, 7, 15, 17, tzinfo=timezone.utc)),
    (date(2026, 7, 15), time(1), "Asia/Hong_Kong", datetime(2026, 7, 14, 17, tzinfo=timezone.utc)),
    (date(2026, 7, 15), time(18, 2, 3), "UTC", datetime(2026, 7, 15, 18, 2, 3, tzinfo=timezone.utc)),
])
def test_unique_roundtrip_candidate_preserves_region_and_is_never_an_approved_instant(
    local_date, local_time, zone, expected,
):
    current = DateEventData(**output(candidate(local_date=local_date, local_time=local_time,
        timezone=zone, precision="second" if local_time.second else "minute")))
    assert current.conversion_status == "unique" and current.calculated_utc_instant == expected
    assert current.timezone == zone and current.tzdata_version == "2026.4"
    assert current.utc_instant is None and current.review_state == "draft"
    assert current.evidence_state == "unresolved" and current.evidence_reference is None
    assert current.source_alignment == "pending"


@pytest.mark.parametrize("local_date,local_time,zone,status", [
    (date(2026, 10, 25), time(1, 30), "Europe/London", "ambiguous"),
    (date(2026, 3, 29), time(1, 30), "Europe/London", "nonexistent"),
    # Half-hour changes and a skipped whole day exercise roundtrip, not offset heuristics.
    (date(2026, 4, 5), time(1, 45), "Australia/Lord_Howe", "ambiguous"),
    (date(2026, 10, 4), time(2, 15), "Australia/Lord_Howe", "nonexistent"),
    (date(2011, 12, 30), time(12), "Pacific/Apia", "nonexistent"),
])
def test_both_folds_are_validated_and_ambiguous_or_nonexistent_times_are_not_selected(
    local_date, local_time, zone, status,
):
    resolved = normalize_date_event(DateEventInput(**candidate(
        local_date=local_date, local_time=local_time, timezone=zone)))
    assert resolved.conversion_status == status and resolved.calculated_utc_instant is None


@pytest.mark.parametrize("changes,status", [
    ({"precision": "date", "local_time": None, "timezone": None}, "date_only"),
    ({"precision": "date", "local_time": None}, "date_only"),
    ({"precision": "unknown", "local_date": None, "local_time": None, "timezone": None}, "unknown"),
    ({"timezone": None}, "missing_timezone"),
    ({"source_alignment": "conflict"}, "source_conflict"),
    ({"local_date": date.min, "local_time": time(0), "timezone": "Asia/Tokyo"}, "out_of_range"),
    ({"local_date": date.max, "local_time": time(23, 59), "timezone": "America/New_York"}, "out_of_range"),
])
def test_missing_precision_or_conflict_never_invents_a_time_or_final_utc(changes, status):
    data = DateEventData(**output(candidate(**changes)))
    assert data.conversion_status == status
    assert data.calculated_utc_instant is None and data.utc_instant is None
    for field, expected in changes.items():
        assert getattr(data, field) == expected


def test_event_types_remain_independent_labels_without_late_application_policy():
    for event_type in ("application_open", "application_deadline", "equal_consideration", "materials_deadline",
        "language_supplement", "score_supplement", "offer_acceptance", "scholarship_deadline", "enrollment"):
        data = DateEventData(**output(candidate(event_type=event_type)))
        assert data.event_type == event_type
        assert "can_apply" not in DateEventData.model_fields and "expired" not in DateEventData.model_fields


def test_internal_date_and_time_values_are_strict_native_objects():
    for field, value in [("local_date", "2026-01-15"), ("local_date", 1768435200), ("local_date", True),
        ("local_date", datetime(2026, 1, 15)), ("local_time", "18:00"), ("local_time", 64800),
        ("local_time", False), ("local_time", time(18, tzinfo=timezone.utc)),
        ("local_time", time(18, fold=1)), ("local_time", time(18, microsecond=1))]:
        with pytest.raises(ValidationError):
            DateEventInput(**candidate(**{field: value}))


@pytest.mark.parametrize("changes", [
    {"precision": "minute", "local_time": time(18, 0, 1)},
    {"precision": "second", "local_time": time(18, microsecond=1)},
    {"precision": "date"}, {"precision": "date", "local_date": None, "local_time": None},
    {"precision": "unknown"}, {"local_date": None}, {"local_time": None},
])
def test_precision_requires_exact_nullable_field_coupling(changes):
    with pytest.raises(ValidationError):
        DateEventInput(**candidate(**changes))


def test_timezone_is_an_explicit_packaged_region_or_exact_utc_not_an_offset_or_path():
    for zone in ("GMT", "BST", "EST", "+08:00", "Etc/GMT+8", "Europe/NoSuchCity",
        "../Europe/London", "Europe/../London", "Europe\\London", "Europe/London\n", ""):
        with pytest.raises(ValidationError):
            DateEventInput(**candidate(timezone=zone))


def test_package_loader_does_not_use_system_zoneinfo_constructor_path_or_global_cache(monkeypatch):
    import services.api.app.admissions_catalog.dates as dates
    import zoneinfo
    previous_path = zoneinfo.TZPATH
    original_class = dates.ZoneInfo

    class OnlyPackaged:
        def __new__(cls, *args, **kwargs):
            raise AssertionError("host ZoneInfo constructor must not be used")

        @classmethod
        def from_file(cls, stream, *, key):
            assert stream.read(4) == b"TZif"
            stream.seek(0)
            return original_class.from_file(stream, key=key)

    monkeypatch.setattr(dates, "ZoneInfo", OnlyPackaged)
    monkeypatch.setattr(zoneinfo, "reset_tzpath", lambda *args: pytest.fail("no global TZPATH mutation"))
    assert normalize_date_event(DateEventInput(**candidate())).conversion_status == "unique"
    assert zoneinfo.TZPATH == previous_path


@pytest.mark.parametrize("failure", ["wrong_version", "missing_resource"])
def test_unavailable_pinned_database_rejects_instead_of_falling_back(monkeypatch, failure):
    import services.api.app.admissions_catalog.dates as dates
    if failure == "wrong_version":
        monkeypatch.setattr(dates.tzdata, "__version__", "UNTRUSTED_TZ_SENTINEL")
    else:
        monkeypatch.setattr(dates, "files", lambda *args: (_ for _ in ()).throw(
            FileNotFoundError("UNTRUSTED_TZ_SENTINEL")))
    with pytest.raises(ValidationError) as rejected:
        DateEventInput(**candidate())
    assert "UNTRUSTED_TZ_SENTINEL" not in str(rejected.value)


def test_bounded_identity_version_and_unverified_source_contract():
    for field, value in [("entry_year", True), ("entry_year", "2026"), ("entry_year", 10000),
        ("offering_version", 1.0), ("offering_version", 0), ("is_synthetic", 1),
        ("reference_key", "demo_date"), ("is_synthetic", False), ("event_type", "deadline"),
        ("source_alignment", "verified"), ("original_text", "x" * 4001),
        ("evidence_reference", "unresolved text")]:
        with pytest.raises(ValidationError):
            DateEventInput(**candidate(**{field: value}))


def test_pending_evidence_reference_cannot_mix_demo_and_verified_namespaces():
    for changes in ({"evidence_reference": "REAL_PENDING_SOURCE"},
        {"is_synthetic": False, "reference_key": "REAL_DATE", "evidence_reference": "demo_pending_source"}):
        with pytest.raises(ValidationError):
            DateEventInput(**candidate(**changes))
    real = DateEventInput(**candidate(is_synthetic=False, reference_key="REAL_DATE",
                                      evidence_reference="REAL_PENDING_SOURCE"))
    assert real.evidence_reference == "REAL_PENDING_SOURCE"


def test_nullable_fields_must_be_explicit_and_no_server_assurance_can_be_supplied():
    for field in ("local_date", "local_time", "timezone", "evidence_reference"):
        payload = candidate()
        del payload[field]
        with pytest.raises(ValidationError):
            DateEventInput(**payload)
    for field in ("utc_instant", "calculated_utc_instant", "review_state", "conversion_status", "tzdata_version"):
        with pytest.raises(ValidationError) as rejected:
            DateEventInput(**candidate(**{field: "UNTRUSTED_DATE_SENTINEL"}))
        assert "UNTRUSTED_DATE_SENTINEL" not in str(rejected.value)


@pytest.mark.parametrize("forgery", ["copy", "construct"])
def test_normalization_revalidates_forged_input_and_never_uses_supplied_fold(forgery):
    source = DateEventInput(**candidate())
    invalid = {**candidate(), "local_time": time(1, 30, fold=1)}
    forged = source.model_copy(update=invalid) if forgery == "copy" else DateEventInput.model_construct(**invalid)
    with pytest.raises(ValidationError):
        normalize_date_event(forged)


@pytest.mark.parametrize("changes", [
    {"calculated_utc_instant": datetime(2026, 1, 16, 18, tzinfo=timezone.utc)},
    {"conversion_status": "date_only", "calculated_utc_instant": None},
    {"utc_instant": datetime(2026, 1, 15, 18, tzinfo=timezone.utc)},
    {"review_state": "reviewed"}, {"evidence_state": "verified"}, {"tzdata_version": "system"},
])
def test_persisted_data_recomputes_candidates_and_cannot_claim_final_review(changes):
    with pytest.raises(ValidationError):
        DateEventData(**{**output(candidate()), **changes})


def test_conflict_preserves_original_metadata_without_attempting_to_validate_natural_language():
    payload = candidate(original_text="DEMO_ unparsed text says a different date.\nKeep original text.",
                        source_alignment="conflict", evidence_reference="DEMO_PENDING_SOURCE")
    data = DateEventData(**output(payload))
    assert data.original_text == payload["original_text"] and data.evidence_reference == "DEMO_PENDING_SOURCE"
    assert data.conversion_status == "source_conflict" and data.calculated_utc_instant is None
    # Merely pending never claims an automatic or human comparison happened.
    pending = DateEventData(**output({**payload, "source_alignment": "pending"}))
    assert pending.source_alignment == "pending" and pending.review_state == "draft"


def test_outputs_are_frozen_and_resolution_enforces_unique_utc_coupling():
    data = DateEventData(**output(candidate()))
    with pytest.raises(ValidationError):
        data.utc_instant = data.calculated_utc_instant
    for status, instant in [("unique", None), ("ambiguous", data.calculated_utc_instant),
        ("unique", datetime(2026, 1, 15, 18)),
        ("unique", datetime(2026, 1, 15, 18, tzinfo=timezone(timedelta(hours=1))))]:
        with pytest.raises(ValidationError):
            DateResolution(conversion_status=status, calculated_utc_instant=instant, tzdata_version="2026.4")


def test_import_and_conversion_remain_pure_without_db_auth_or_application_imports():
    completed = subprocess.run([sys.executable, "-B", "-c", r'''
import json,sys
from services.api.app.admissions_catalog.dates import normalize_date_event
forbidden=("sqlalchemy", "services.api.app.main", "services.api.app.models",
 "services.api.app.admissions_catalog.models", "services.api.app.admissions_catalog.store",
 "services.api.app.auth", "services.api.app.providers")
print(json.dumps([name for name in sys.modules if any(name==prefix or name.startswith(prefix+".")
 for prefix in forbidden)]))
'''], cwd=Path(__file__).resolve().parents[3], capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == "" and json.loads(completed.stdout) == []
