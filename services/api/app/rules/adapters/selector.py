"""Finite scope matching with explicit trusted test ports, never qualification."""

from typing import Protocol

from ...admissions_catalog.schemas import ScopeKey
from .schemas import (AdapterInputError, AdapterPolicy, AdapterSelection, BundleQuery,
    MAX_BUNDLES, RuleBundle, ScopeRequest)
from .scope import DEFAULT_CONFIGURATION, canonical_province, parse_scope_configuration


class RuleProvider(Protocol):
    def __call__(self, query: BundleQuery) -> tuple[RuleBundle, ...] | list[RuleBundle]: ...


class BindingVerifier(Protocol):
    def __call__(self, query: BundleQuery, bundle: RuleBundle) -> bool: ...


def _input(model, value):
    try:
        if type(value) not in (dict, model):
            raise AdapterInputError()
        return model.model_validate(value)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise AdapterInputError() from None


def _result(reason, adapter=None, bundle=None):
    unsupported = {"UNSUPPORTED_COUNTRY", "UNSUPPORTED_COURSE", "UNSUPPORTED_APPLICANT", "UNSUPPORTED_PATHWAY"}
    return AdapterSelection(selection_status="matched" if bundle else "unsupported" if reason in unsupported else "unknown",
        reason=reason, adapter=adapter, bundle_id=bundle.bundle_id if bundle else None,
        release_id=bundle.release_id if bundle else None,
        requirements_version=bundle.requirements_version if bundle else None,
        ruleset_version=bundle.ruleset_version if bundle else None)


def _route(request, configuration):
    if request.target.country not in {"CN", "GB"}:
        return None, "UNSUPPORTED_COUNTRY"
    adapter = "CN_GAOKAO" if request.target.country == "CN" else "UK_UNDERGRADUATE"
    for scope, expected, reason in ((request.course_system, "gaokao", "UNSUPPORTED_COURSE"),
        (request.applicant_category, "cn_mainland", "UNSUPPORTED_APPLICANT"),
        (request.pathway, "gaokao" if adapter == "CN_GAOKAO" else "uk_undergraduate", "UNSUPPORTED_PATHWAY")):
        if scope.status != "known":
            return adapter, "MISSING_SCOPE"
        if scope.value != expected:
            return adapter, reason
    if adapter == "CN_GAOKAO":
        if request.exam_province.status != "known":
            return adapter, "MISSING_SCOPE"
        if canonical_province(request.exam_province.value, configuration=configuration) is None:
            return adapter, "PROVINCE_UNRECOGNIZED"
    elif request.entry_year not in configuration.uk_entry_years:
        return adapter, "UK_YEAR_UNSUPPORTED"
    if any(scope is None or scope.status == "unknown" for scope in _extra_values(request)):
        return adapter, "MISSING_SCOPE"
    return adapter, None


def _extra_values(request):
    return (request.intake, request.application_cycle, request.channel,
            request.exam_system, request.subject_scope, request.batch_group)


def _same_scope(left: ScopeKey, right: ScopeKey):
    if left.status == "unknown" or right.status == "unknown":
        return "MISSING_SCOPE"
    return None if left == right else "SCOPE_MISMATCH"


def _matching(request, bundle, adapter, configuration):
    target, scope = request.target, bundle.scope
    if ((scope.dataset_id, scope.institution_id, scope.program_id, scope.country,
         bundle.offering_id, bundle.offering_version, bundle.scope_sha256) !=
        (target.dataset_id, target.institution_id, target.program_id, target.country,
         target.offering_id, target.offering_version, target.scope_sha256)):
        return "TARGET_MISMATCH"
    if scope.entry_year != request.entry_year:
        return "YEAR_MISMATCH"
    if bundle.stage != request.stage:
        return "STAGE_MISMATCH"
    # This is the only vocabulary mapping; program course/progression are not
    # applicant course_system/pathway and are bound by the full target hash.
    if request.study_level != "bachelor" or scope.study_level != "undergraduate":
        return "SCOPE_MISMATCH"
    scope_values = (scope.degree, scope.course, scope.campus, scope.teaching_language,
        scope.progression_pathway, scope.intake, scope.application_cycle, scope.channel,
        scope.course_system, scope.pathway, scope.applicant_category, scope.province,
        scope.exam_system, scope.subject_scope, scope.batch_group)
    if any(value.status == "unknown" for value in scope_values):
        return "MISSING_SCOPE"
    for left, right in ((request.course_system, scope.course_system),
        (request.applicant_category, scope.applicant_category), (request.pathway, scope.pathway),
        *zip(_extra_values(request), (scope.intake, scope.application_cycle, scope.channel,
            scope.exam_system, scope.subject_scope, scope.batch_group), strict=True)):
        problem = _same_scope(left, right)
        if problem:
            return problem
    if not (adapter == "UK_UNDERGRADUATE" and scope.province.status == "not_applicable"):
        if request.exam_province.status != "known" or scope.province.status != "known":
            return "MISSING_SCOPE"
        actual = canonical_province(request.exam_province.value, configuration=configuration)
        required = canonical_province(scope.province.value, configuration=configuration)
        if actual is None or required is None:
            return "PROVINCE_UNRECOGNIZED"
        if actual != required:
            return "SCOPE_MISMATCH"
    if bundle.ruleset_version is None:
        return "RULESET_UNAVAILABLE"
    if not bundle.valid_from <= request.assessment_at < bundle.valid_until:
        return "BUNDLE_EXPIRED"
    return None


def select_rules(request, *, policy=None, provider: RuleProvider | None = None,
        verifier: BindingVerifier | None = None, configuration=DEFAULT_CONFIGURATION) -> AdapterSelection:
    """Select one exact synthetic binding; callers must separately authorize.

    Ports are trusted local, side-effect-free code, not a Python sandbox. The
    selector passes no personal fields and never performs database/network I/O.
    """
    request = _input(ScopeRequest, request)
    policy = _input(AdapterPolicy, AdapterPolicy() if policy is None else policy)
    configuration = parse_scope_configuration(configuration)
    initial_policy = policy.model_dump(mode="json")
    initial_configuration = configuration.model_dump(mode="json")
    if not policy.enabled:
        return _result("POLICY_DISABLED")
    adapter, problem = _route(request, configuration)
    if problem:
        return _result(problem, adapter)
    if not (policy.allow_test_bundles and policy.app_environment == "test" and policy.data_mode == "demo"):
        return _result("REAL_RULES_UNAVAILABLE", adapter)
    if provider is None:
        return _result("RULESET_UNAVAILABLE", adapter)
    query = BundleQuery(target=request.target, entry_year=request.entry_year, stage=request.stage)
    initial_query = query.model_dump(mode="json")
    try:
        supplied = provider(query)
        if type(supplied) not in (tuple, list) or len(supplied) > MAX_BUNDLES:
            return _result("PROVIDER_UNAVAILABLE", adapter)
        # Validate every element before filtering. A matching first entry cannot
        # hide another malformed AST, forged hash, or unbounded input object.
        bundles = tuple(_input(RuleBundle, item) for item in supplied)
        if _input(BundleQuery, query).model_dump(mode="json") != initial_query:
            return _result("BINDING_UNVERIFIED", adapter)
    except Exception:
        return _result("PROVIDER_UNAVAILABLE", adapter)
    if not bundles:
        return _result("RULESET_UNAVAILABLE", adapter)
    if any(not bundle.is_synthetic for bundle in bundles):
        return _result("SYNTHETIC_BOUNDARY", adapter)
    matches, problems, binding_problems = [], [], []
    for bundle in bundles:
        problem = _matching(request, bundle, adapter, configuration)
        if problem:
            problems.append(problem)
            # Only a genuinely different target, year, or stage is outside the
            # requested binding group. A stale/unfinished member of the exact
            # group must not disappear behind another positive member.
            if problem not in {"TARGET_MISMATCH", "YEAR_MISMATCH", "STAGE_MISMATCH"}:
                binding_problems.append(problem)
        else:
            matches.append(bundle)
    if binding_problems or not matches:
        applicable_problems = binding_problems or problems
        for reason in ("RULESET_UNAVAILABLE", "MISSING_SCOPE", "PROVINCE_UNRECOGNIZED",
                       "BUNDLE_EXPIRED", "SCOPE_MISMATCH", "STAGE_MISMATCH", "YEAR_MISMATCH", "TARGET_MISMATCH"):
            if reason in applicable_problems:
                return _result(reason, adapter)
        return _result("RULESET_UNAVAILABLE", adapter)
    if verifier is None:
        return _result("VERIFIER_UNAVAILABLE", adapter)
    # Every otherwise applicable binding must verify. Revoked/invalid entries
    # cannot be ignored merely because another entry is positive.
    snapshots = tuple(bundle.model_dump(mode="json") for bundle in matches)
    try:
        for bundle, snapshot in zip(matches, snapshots, strict=True):
            verified = verifier(query, bundle)
            if type(verified) is not bool or not verified:
                return _result("BINDING_UNVERIFIED", adapter)
            if _input(RuleBundle, bundle).model_dump(mode="json") != snapshot:
                return _result("BINDING_UNVERIFIED", adapter)
        if _input(BundleQuery, query).model_dump(mode="json") != initial_query:
            return _result("BINDING_UNVERIFIED", adapter)
        if (_input(AdapterPolicy, policy).model_dump(mode="json") != initial_policy
            or parse_scope_configuration(configuration).model_dump(mode="json") != initial_configuration):
            return _result("BINDING_UNVERIFIED", adapter)
        # A later trusted callback may have retained and changed an earlier
        # value. Recheck the entire original set after all callbacks finish.
        if any(_input(RuleBundle, bundle).model_dump(mode="json") != snapshot
            for bundle, snapshot in zip(matches, snapshots, strict=True)):
            return _result("BINDING_UNVERIFIED", adapter)
    except Exception:
        return _result("VERIFIER_UNAVAILABLE", adapter)
    if any(bundle.model_dump(mode="json") != matches[0].model_dump(mode="json") for bundle in matches[1:]):
        return _result("AMBIGUOUS_RULESETS", adapter)
    return _result("MATCHED", adapter, matches[0])
