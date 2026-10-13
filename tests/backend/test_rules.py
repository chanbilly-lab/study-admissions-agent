from copy import deepcopy
from datetime import date

import pytest
from sqlalchemy.orm import Session

from services.api.app.catalog import read_offering
from services.api.app.eligibility import evaluate
from services.api.app.models import EvidenceRecord, OfferingRecord
from services.api.app.schemas import Profile, Rule


def load(session, profile_input, identifier="DEMO_GB_DEFERRED"):
    profile = Profile(**deepcopy(profile_input), id="DEMO_TEST_PROFILE", version=1, owner_id="demo_alice")
    offering = read_offering(session, session.get(OfferingRecord, identifier))
    return profile, offering


def language_rule(offering):
    return next(rule for rule in offering.rules if rule.field == "assessments.english_language")


@pytest.mark.parametrize("mutation", ["missing", "predicted", "wrong_scale", "wrong_unit"])
def test_missing_or_unusable_score_never_becomes_eligible(app, settings, profile_input, mutation):
    if mutation == "missing":
        del profile_input["assessments"]["english_language"]
    else:
        score = profile_input["assessments"]["english_language"]
        if mutation == "predicted":
            score["kind"] = "predicted"
        elif mutation == "wrong_scale":
            score["scale"] = 10
        else:
            score["unit"] = "points"
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input, "DEMO_GB_NO_DEFERRAL")
        result = evaluate(session, profile, offering, settings)
        assert result.status == "unknown"
        assert not result.conditions


@pytest.mark.parametrize("field", ["math", "gaokao_total"])
def test_missing_domestic_score_unknown_not_deferrable(app, settings, profile_input, field):
    del profile_input["assessments"][field]
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input, "DEMO_CN_MATH")
        result = evaluate(session, profile, offering, settings)
        assert result.status == "unknown" and not result.conditions


def test_reviewed_hard_failure_wins_over_an_unknown_atom(app, settings, profile_input):
    profile_input["assessments"]["gaokao_total"]["value"] = 400
    del profile_input["assessments"]["english_language"]
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input, "DEMO_GB_NO_DEFERRAL")
        result = evaluate(session, profile, offering, settings)
        assert result.status == "ineligible"
        assert {item.outcome for item in result.reasons} == {"false", "unknown"}


@pytest.mark.parametrize("change", ["missing_policy", "missing_deadline_evidence", "wrong_year", "conflicted", "review_required", "expired", "hash_tamper", "excerpt_tamper", "version_tamper", "cross_offering_policy", "cross_offering_deadline", "deadline_mismatch"])
def test_invalid_deferral_never_returns_conditional(app, settings, profile_input, change):
    del profile_input["assessments"]["english_language"]
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input)
        rule = language_rule(offering)
        if change == "missing_policy":
            rule.deferral.evidence_id = "DEMO_MISSING"
        elif change == "missing_deadline_evidence":
            rule.deferral.deadline_evidence_id = "DEMO_MISSING"
        elif change == "cross_offering_policy":
            rule.deferral.evidence_id = "DEMO_EVIDENCE_GB_NO_DEFERRAL"
        elif change == "cross_offering_deadline":
            rule.deferral.deadline_evidence_id = "DEMO_EVIDENCE_GB_MISSING_DEADLINE"
        elif change == "deadline_mismatch":
            rule.deferral.deadline = "2027-08-21"
        else:
            record = session.get(EvidenceRecord, rule.deferral.evidence_id)
            payload = deepcopy(record.payload)
            if change == "wrong_year":
                payload["entry_year"] = 2026
            elif change in ("conflicted", "review_required", "expired"):
                payload["review_status"] = change
            elif change == "hash_tamper":
                record.raw_document += "篡改内容"
            elif change == "excerpt_tamper":
                payload["excerpt"] = "并不存在于原文的片段"
            elif change == "version_tamper":
                payload["document_version_id"] = "DEMO_OTHER_VERSION"
            record.payload = payload
        result = evaluate(session, profile, offering, settings)
        assert result.status == "unknown", result.model_dump()
        assert not result.conditions


def test_expired_deferral_on_explicit_assessment_date_unknown(app, settings, profile_input):
    del profile_input["assessments"]["english_language"]
    settings.assessment_date = date(2027, 8, 21)
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input)
        result = evaluate(session, profile, offering, settings)
        assert result.status == "unknown" and any("已经过去" in item.message for item in result.reasons)


def test_deferral_date_boundary_is_date_only(app, settings, profile_input):
    del profile_input["assessments"]["english_language"]
    settings.assessment_date = date(2027, 8, 20)
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input)
        assert evaluate(session, profile, offering, settings).status == "conditional"


@pytest.mark.parametrize("change", ["wrong_year", "wrong_province", "wrong_category", "wrong_course", "wrong_pathway"])
def test_cross_scope_unknown_not_ineligible(app, settings, profile_input, change):
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input, "DEMO_CN_MATH")
        if change == "wrong_year":
            offering.entry_year = 2026
        elif change == "wrong_province":
            offering.province = "广东"
        elif change == "wrong_category":
            offering.applicant_category = "other"
        elif change == "wrong_course":
            offering.course_system = "alevel"
        else:
            offering.pathway = "uk_undergraduate"
        assert evaluate(session, profile, offering, settings).status == "unknown"


@pytest.mark.parametrize("change", ["unreviewed_rule", "missing_evidence", "cross_offering_evidence", "wrong_rule_offering", "no_rules"])
def test_unavailable_rules_never_eligible(app, settings, profile_input, change):
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input)
        rule = language_rule(offering)
        if change == "unreviewed_rule":
            rule.review_status = "review_required"
        elif change == "missing_evidence":
            rule.evidence_id = "DEMO_MISSING"
        elif change == "cross_offering_evidence":
            rule.evidence_id = "DEMO_EVIDENCE_GB_NO_DEFERRAL"
        elif change == "wrong_rule_offering":
            rule.offering_id = "DEMO_GB_NO_DEFERRAL"
        else:
            offering.rules = []
        assert evaluate(session, profile, offering, settings).status == "unknown"


@pytest.mark.parametrize("field,value", [("value", "6.5"), ("scale", None), ("unit", None), ("scale", -1), ("value", 99), ("op", "eq"), ("field", "__class__")])
def test_bad_score_dsl_is_unknown_before_missing_deferral(app, settings, profile_input, field, value):
    del profile_input["assessments"]["english_language"]
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input)
        rule = language_rule(offering)
        setattr(rule, field, value)
        result = evaluate(session, profile, offering, settings)
        assert result.status == "unknown" and not result.conditions


@pytest.mark.parametrize("field,op,value", [("province", "eq", 12), ("course_system", "gte", 2), ("entry_year", "eq", "2027"), ("entry_year", "in", ["2027"]), ("subjects", "eq", "physics"), ("subjects", "in", [])])
def test_typed_profile_dsl_errors_are_unknown_not_false(app, settings, profile_input, field, op, value):
    with Session(app.state.engine) as session:
        profile, offering = load(session, profile_input, "DEMO_CN_MATH")
        rule = next(rule for rule in offering.rules if rule.field == "subjects")
        rule.field, rule.op, rule.value = field, op, value
        result = evaluate(session, profile, offering, settings)
        assert result.status == "unknown" and any(item.outcome == "unknown" for item in result.reasons)


def test_no_eval_exec_model_or_network_in_rule_module():
    import ast
    from pathlib import Path
    import services.api.app.eligibility as module
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    calls = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    assert not ({"eval", "exec", "compile", "__import__"} & set(calls))
    imported = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any("provider" in name or "http" in name for name in imported)
