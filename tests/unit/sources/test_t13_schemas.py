"""Offline declarations are synthetic examples, never evidence of legal review."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from uuid import UUID

from pydantic import ValidationError
import pytest

from services.api.app.admin.sources.schemas import (
    SourceCreateInput, SourceDefinition, SourcePolicy, SourceRevisionInput, SourceVersionData,
    validate_source_url,
)


NOW = datetime(2026, 10, 3, 12, 1, 2, 300, tzinfo=timezone.utc)


def definition(**changes):
    return {
        "publisher": "DEMO_合成发布者", "entry_url": "https://DEMO.invalid/admissions",
        "purpose": "admissions_reference", "data_type": "entry_requirements",
        "scope_note": "DEMO_原始范围描述；不自动解释为资格规则。",
        "authority_claim": "claimed_official", "manual_import_permission": "pending",
        "publication_permission": "pending", "automated_fetch_permission": "pending",
        "license_basis": None, "permission_record_reference": None,
        "recheck_days": 30, "manual_import_enabled": False, **changes,
    }


def recorded(**changes):
    return definition(manual_import_permission="granted", license_basis="DEMO_合成许可声明，未作法律核验。",
        permission_record_reference="DEMO_PERMISSION_RECORD", **changes)


def creation(**changes):
    return {"id": UUID(int=1), "dataset_id": UUID(int=2), "reference_key": "DEMO_SOURCE",
            "is_synthetic": True, "definition": definition(), **changes}


def version(values=None, **changes):
    values = definition() if values is None else values
    reviewed = NOW if any(values[field] != "pending" for field in (
        "manual_import_permission", "publication_permission", "automated_fetch_permission")) else None
    return {**values, "id": UUID(int=3), "dataset_id": UUID(int=2), "source_id": UUID(int=1),
        "version": 1, "is_synthetic": True, "responsible_user_id": UUID(int=4), "created_at": NOW,
        "permission_reviewed_at": reviewed, "recheck_due_at": NOW + timedelta(days=values["recheck_days"]),
        "auto_fetch_enabled": False, **changes}


def test_default_policy_is_closed_and_does_not_create_a_responsible_user():
    policy = SourcePolicy()
    assert policy.enabled is False and policy.real_sources_ready is False
    assert policy.responsible_user_ids == ()


def test_claimed_official_never_grants_pending_permissions_or_enables_import():
    current = SourceDefinition(**definition())
    assert current.authority_claim == "claimed_official"
    assert current.manual_import_permission == current.publication_permission == current.automated_fetch_permission == "pending"
    assert current.license_basis is None and current.permission_record_reference is None
    assert current.manual_import_enabled is False


@pytest.mark.parametrize("url", [
    "http://DEMO.invalid:8080/a%20b?year=2026&channel=synthetic",
    "https://[2001:db8::1]/catalog?example=true", "https://例子.中国/合成来源",
    "HTTPS://DEMO.invalid/非ASCII路径?example=%20",
])
def test_metadata_urls_preserve_exact_path_query_and_host_without_rewriting(url):
    assert validate_source_url(url) == url
    assert SourceDefinition(**definition(entry_url=url)).entry_url == url


@pytest.mark.parametrize("invalid", [
    ("ftp://DEMO.invalid/a", "javascript:alert(1)", "//DEMO.invalid/a", "https:///a"),
    ("https://user@DEMO.invalid/a", "https://user:secret@DEMO.invalid/a", "https://DEMO.invalid/a#"),
    ("https://DEMO.invalid/a\n", " https://DEMO.invalid/a", "https://DEMO.invalid/a\x7f", "https://DEMO.invalid\\a"),
    ("https://DEMO.invalid:0/a", "https://DEMO.invalid:65536/a", "https://DEMO.invalid:/a", "https://[broken/a"),
    ("https://bad_host.invalid/a", "https://-bad.invalid/a", "https://DEMO..invalid/a", "https://DEMO.invalid/a%xx"),
])
def test_url_validation_rejects_parser_tolerance_credentials_and_malformed_authorities(invalid):
    for url in invalid:
        with pytest.raises(ValidationError) as rejected:
            SourceDefinition(**definition(entry_url=url))
        assert url not in str(rejected.value)


@pytest.mark.parametrize("values", [
    recorded(publication_permission="denied", automated_fetch_permission="pending", manual_import_enabled=True),
    definition(publication_permission="granted", license_basis="DEMO_声明", permission_record_reference="DEMO_RECORD"),
    definition(automated_fetch_permission="granted", license_basis="DEMO_声明", permission_record_reference="DEMO_RECORD"),
])
def test_three_permissions_are_independent_and_fetch_is_always_disabled(values):
    current = SourceVersionData(**version(values))
    assert current.manual_import_permission == values["manual_import_permission"]
    assert current.publication_permission == values["publication_permission"]
    assert current.automated_fetch_permission == values["automated_fetch_permission"]
    assert current.permission_reviewed_at == NOW and current.auto_fetch_enabled is False


@pytest.mark.parametrize("changes", [
    {"manual_import_permission": "denied"}, {"publication_permission": "granted", "license_basis": "DEMO_声明"},
    {"license_basis": "DEMO_声明"}, {"permission_record_reference": "DEMO_RECORD"},
])
def test_recorded_or_pending_permission_has_exact_basis_and_reference_coupling(changes):
    with pytest.raises(ValidationError):
        SourceDefinition(**definition(**changes))


@pytest.mark.parametrize("permission", ["pending", "denied"])
def test_manual_import_cannot_be_requested_without_manual_grant(permission):
    values = definition(manual_import_enabled=True) if permission == "pending" else {
        **recorded(), "manual_import_permission": "denied", "manual_import_enabled": True}
    with pytest.raises(ValidationError):
        SourceDefinition(**values)


def test_synthetic_publisher_root_and_permission_reference_must_share_namespace():
    for changes in ({"reference_key": "demo_source"}, {"is_synthetic": False},
        {"definition": definition(publisher="真实发布者")},
        {"definition": {**recorded(), "permission_record_reference": "REAL_RECORD"}}):
        with pytest.raises(ValidationError):
            SourceCreateInput(**{**creation(), **changes})
    for publisher, record in [("demo_publisher", "REAL_RECORD"), ("真实发布者", "dEmO_record")]:
        with pytest.raises(ValidationError):
            SourceCreateInput(**{**creation(), "reference_key": "REAL_SOURCE", "is_synthetic": False,
                "definition": {**recorded(), "publisher": publisher, "permission_record_reference": record}})
    real = SourceCreateInput(**{**creation(), "reference_key": "REAL_SOURCE", "is_synthetic": False,
        "definition": definition(publisher="真实候选发布者")})
    assert real.definition.manual_import_permission == "pending"


def test_all_data_types_are_explicit_and_required_fields_do_not_guess_responsibility():
    for data_type in ("entry_requirements", "application_dates", "regional_cutoffs", "admission_observations",
        "curriculum", "outcomes", "institution_directory"):
        assert SourceDefinition(**definition(data_type=data_type)).data_type == data_type
    for field in ("license_basis", "permission_record_reference", "recheck_days", "authority_claim"):
        incomplete = definition()
        del incomplete[field]
        with pytest.raises(ValidationError):
            SourceDefinition(**incomplete)
    for field in ("owner", "responsible_user_id", "reviewed_at", "role", "auto_fetch_enabled"):
        with pytest.raises(ValidationError) as rejected:
            SourceCreateInput(**{**creation(), field: "SOURCE_PRIVATE_SENTINEL"})
        assert "SOURCE_PRIVATE_SENTINEL" not in str(rejected.value)


def test_strict_bounded_fields_and_text_keys_reject_coercion_and_empty_values():
    for field, value in [("recheck_days", 0), ("recheck_days", 731), ("recheck_days", True),
        ("recheck_days", 30.0), ("manual_import_enabled", 0), ("publisher", "x" * 201),
        ("scope_note", "x" * 1001), ("license_basis", "x" * 2001), ("publisher", "DEMO_\nname"),
        ("scope_note", "\x00"), ("permission_record_reference", "DEMO_REF\n")]:
        with pytest.raises(ValidationError):
            SourceDefinition(**definition(**{field: value}))


@pytest.mark.parametrize("forgery", ["copy", "construct"])
def test_nested_definition_is_revalidated_after_copy_or_construct(forgery):
    base = SourceDefinition(**definition())
    invalid = {**definition(), "manual_import_enabled": True}
    forged = base.model_copy(update=invalid) if forgery == "copy" else SourceDefinition.model_construct(**invalid)
    with pytest.raises(ValidationError):
        SourceCreateInput(**{**creation(), "definition": forged})
    with pytest.raises(ValidationError):
        SourceRevisionInput(source_id=UUID(int=1), definition=forged)


def test_flat_output_keeps_server_responsibility_and_no_automatic_fetch():
    data = SourceVersionData(**version(recorded()))
    assert data.responsible_user_id == UUID(int=4) and data.source_id == UUID(int=1)
    assert data.permission_reviewed_at == NOW and data.auto_fetch_enabled is False
    assert "definition" not in SourceVersionData.model_fields and "reference_key" not in SourceVersionData.model_fields
    for value in (True, 0, "false"):
        with pytest.raises(ValidationError):
            SourceVersionData(**version(auto_fetch_enabled=value))


def test_server_timestamps_are_native_aware_and_normalized_to_utc():
    local = timezone(timedelta(hours=8))
    data = SourceVersionData(**version(recorded(), created_at=NOW.astimezone(local),
        permission_reviewed_at=NOW.astimezone(local), recheck_due_at=(NOW+timedelta(days=30)).astimezone(local)))
    assert data.created_at == NOW and data.created_at.tzinfo == timezone.utc
    for value in (NOW.replace(tzinfo=None), NOW.isoformat(), 1791028862, True):
        with pytest.raises(ValidationError):
            SourceVersionData(**version(created_at=value))


def test_declaration_timestamp_and_explicit_review_interval_cannot_be_forged():
    for payload in (version(permission_reviewed_at=NOW), version(recorded(), permission_reviewed_at=None),
        version(recorded(), permission_reviewed_at=NOW-timedelta(seconds=1)),
        version(recheck_due_at=NOW+timedelta(days=31)), version(version=1.0)):
        with pytest.raises(ValidationError):
            SourceVersionData(**payload)
    leap = datetime(2028, 2, 29, 12, tzinfo=timezone.utc)
    data = SourceVersionData(**version(definition(recheck_days=730), created_at=leap,
        recheck_due_at=datetime(2030, 2, 28, 12, tzinfo=timezone.utc)))
    assert data.recheck_due_at == leap+timedelta(days=730)


def test_policy_requires_explicit_unique_responsibility_and_strict_flags():
    for payload in (dict(enabled=1), dict(real_sources_ready=True),
        dict(responsible_user_ids=(UUID(int=4), UUID(int=4))), dict(responsible_user_ids=[UUID(int=4)])):
        with pytest.raises(ValidationError):
            SourcePolicy(**payload)
    assert SourcePolicy(enabled=True, real_sources_ready=True, responsible_user_ids=(UUID(int=4),)).enabled


def test_frozen_outputs_and_model_revalidation_reject_copied_assurance():
    data = SourceVersionData(**version())
    with pytest.raises(ValidationError):
        data.auto_fetch_enabled = True
    with pytest.raises(ValidationError):
        SourceVersionData.model_validate(data.model_copy(update={"permission_reviewed_at": NOW}))
    policy = SourcePolicy().model_copy(update={"enabled": 1})
    with pytest.raises(ValidationError):
        SourcePolicy.model_validate(policy)


def test_schemas_imports_are_pure_without_auth_db_network_or_application_imports():
    completed = subprocess.run([sys.executable, "-B", "-c", r'''
import json,sys
import services.api.app.admin.sources.schemas
forbidden=("sqlalchemy", "httpx", "services.api.app.main", "services.api.app.models",
 "services.api.app.auth", "services.api.app.audit", "services.api.app.admissions_catalog.models")
print(json.dumps([name for name in sys.modules if any(name==prefix or name.startswith(prefix+".")
 for prefix in forbidden)]))
'''], cwd=Path(__file__).resolve().parents[3], capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == "" and json.loads(completed.stdout) == []
