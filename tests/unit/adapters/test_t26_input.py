"""Configuration and trusted-port consistency checks for the pure adapter."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from services.api.app.evidence.schemas import EvidenceScope
from services.api.app.rules.adapters import (
    AdapterInputError, AdapterPolicy, DEFAULT_CONFIGURATION, RuleBundle, ScopeRequest,
    expression_fingerprint, parse_scope_configuration, scope_fingerprint, select_rules,
)


NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[3]
EXTRA = ("intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")


def fixture_values():
    known = lambda value: {"status": "known", "value": value}
    identities = {name: UUID(int=n) for n, name in enumerate(
        ("dataset_id", "institution_id", "program_id", "offering_id"), start=1)}
    scope = EvidenceScope(**{name: value for name, value in identities.items() if name != "offering_id"},
        country="CN", study_level="undergraduate", entry_year=2027,
        **{name: known("DEMO_" + name) for name in
            ("degree", "course", "campus", "teaching_language", "progression_pathway", *EXTRA)},
        course_system=known("gaokao"), pathway=known("gaokao"),
        applicant_category=known("cn_mainland"), province=known("Zhejiang"))
    expression = {"op": "exists", "field": {"name": "entry_year"}}
    request = ScopeRequest(entry_year=2027, study_level="bachelor", residence_region=known("HK"),
        course_system=scope.course_system, applicant_category=scope.applicant_category,
        exam_province=known("zhejiang"), pathway=scope.pathway,
        target={**identities, "offering_version": 1, "country": "CN", "scope_sha256": scope_fingerprint(scope)},
        stage="application", assessment_at=NOW, **{name: getattr(scope, name) for name in EXTRA})
    bundle = RuleBundle(bundle_id=UUID(int=5), reference_key="DEMO_T26_INPUT",
        release_id=UUID(int=6), release_version=1, requirements_version="a" * 64,
        ruleset_version="b" * 64, is_synthetic=True, scope=scope, scope_sha256=scope_fingerprint(scope),
        offering_id=identities["offering_id"], offering_version=1, stage="application",
        valid_from=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=1),
        expression=expression, expression_sha256=expression_fingerprint(expression),
        fact_ids=(UUID(int=7),), evidence_ids=(UUID(int=8),))
    policy = AdapterPolicy(enabled=True, allow_test_bundles=True, app_environment="test", data_mode="demo")
    return request, bundle, policy


def test_explicit_json_configuration_matches_the_pure_default():
    loaded = json.loads((ROOT / "config/scopes/undergraduate.json").read_text(encoding="utf-8"))
    assert parse_scope_configuration(loaded) == DEFAULT_CONFIGURATION
    aliases = [value for entry in DEFAULT_CONFIGURATION.provinces for value in (entry.canonical, *entry.aliases)]
    assert len(aliases) == len(set(aliases)) == 63
    assert DEFAULT_CONFIGURATION.real_rules_ready is False


@pytest.mark.parametrize("change", ["collision", "new_year", "real_ready"])
def test_configuration_cannot_silently_add_aliases_years_or_real_readiness(change):
    raw = DEFAULT_CONFIGURATION.model_dump()
    if change == "collision":
        raw["provinces"][0]["aliases"] = ("tianjin",)
    elif change == "new_year":
        raw["uk_entry_years"] = (2028,)
    else:
        raw["real_rules_ready"] = True
    with pytest.raises(AdapterInputError):
        parse_scope_configuration(raw)


@pytest.mark.parametrize("country", ["US", "cn", "CN\n"])
def test_target_country_has_only_the_frozen_routes(country):
    request, _, _ = fixture_values()
    target = request.target.model_copy(update={"country": country})
    with pytest.raises(AdapterInputError):
        select_rules(request.model_copy(update={"target": target}))


@pytest.mark.parametrize("bad_hash", ["a" * 64 + "\n", "a" * 65, "A" * 64])
def test_target_hash_is_exact_and_bounded(bad_hash):
    request, _, _ = fixture_values()
    with pytest.raises(AdapterInputError):
        select_rules(request.model_copy(update={"target": request.target.model_copy(update={"scope_sha256": bad_hash})}))


@pytest.mark.parametrize("failure", ["no_ruleset", "expired"])
def test_bad_current_binding_cannot_hide_behind_a_good_member_in_either_order(failure):
    request, good, policy = fixture_values()
    raw = good.model_dump()
    raw["expression"] = good.expression
    raw["bundle_id"] = UUID(int=9)
    if failure == "no_ruleset":
        raw["ruleset_version"] = None
    else:
        raw["valid_until"] = NOW
    bad = RuleBundle.model_validate(raw)
    expected = "RULESET_UNAVAILABLE" if failure == "no_ruleset" else "BUNDLE_EXPIRED"
    for ordered in ((bad, good), (good, bad)):
        visits = []
        result = select_rules(request, policy=policy, provider=lambda query: ordered,
            verifier=lambda query, bundle: visits.append(bundle.bundle_id) or True)
        assert result.selection_status == "unknown" and result.reason == expected
        assert visits == []


def test_unrelated_historical_year_does_not_poison_the_current_binding():
    request, good, policy = fixture_values()
    raw = good.model_dump()
    raw["expression"] = good.expression
    raw["scope"]["entry_year"] = 2026
    raw["scope_sha256"] = scope_fingerprint(raw["scope"])
    raw["ruleset_version"] = None
    raw["valid_until"] = NOW
    old = RuleBundle.model_validate(raw)
    result = select_rules(request, policy=policy, provider=lambda query: (old, good),
        verifier=lambda query, bundle: True)
    assert result.selection_status == "matched"
    assert result.bundle_id == good.bundle_id


def test_later_verifier_cannot_replace_an_earlier_verified_snapshot():
    request, first, policy = fixture_values()
    raw = first.model_dump()
    raw["expression"] = first.expression
    raw["bundle_id"] = UUID(int=10)
    second = RuleBundle.model_validate(raw)
    retained = []
    def verifier(query, bundle):
        if retained:
            object.__setattr__(retained[0], "bundle_id", bundle.bundle_id)
        retained.append(bundle)
        return True
    result = select_rules(request, policy=policy, provider=lambda query: (first, second), verifier=verifier)
    assert len(retained) == 2
    assert result.selection_status == "unknown" and result.reason == "BINDING_UNVERIFIED"


def test_matched_is_only_scope_selection_and_never_evaluates_the_expression():
    request, bundle, policy = fixture_values()
    # This could be false for a separate rules context. Selection cannot decide
    # eligibility and has no student's achieved or predicted measurements.
    expression = {"op": "eq", "field": {"name": "entry_year"}, "value": {"kind": "integer", "value": 2026}}
    raw = bundle.model_dump()
    raw.update(expression=expression, expression_sha256=expression_fingerprint(expression))
    bundle = RuleBundle.model_validate(raw)
    result = select_rules(request, policy=policy, provider=lambda query: (bundle,), verifier=lambda query, bound: True)
    assert result.selection_status == "matched"
    assert set(result.model_dump()) == {"selection_status", "reason", "adapter", "bundle_id", "release_id",
        "requirements_version", "ruleset_version"}
    assert not {"eligible", "truth", "profile", "expression"}.intersection(result.model_dump())
