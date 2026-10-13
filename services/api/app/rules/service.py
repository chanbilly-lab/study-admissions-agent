"""Private four-state results with actual current catalogue proofs and replay."""

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import quote
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.v2.idempotency_canonical import canonical_request_hash
from ..assessments.models import EligibilityAssessment
from ..assessments.store import AssessmentsStore, expression_document, result_fingerprint
from ..audit.context import audited
from ..auth.config import AuthFlowError
from ..profiles.service import ProfileService
from ..public_catalog.proof import AnonymousProofVerifier
from ..public_catalog.reader import _MAPPERS as CATALOG_MAPPERS
from ..public_catalog.schemas import PublicCatalogError
from ..releases.service import ReleaseService
from .adapters.schemas import AdapterPolicy, BundleQuery, RuleBundle, ScopeRequest
from .adapters.scope import scope_request_from_profile
from .adapters.selector import select_rules
from .assessment_engine import EligibilityEngineResult, evaluate_eligibility
from .deferral import DeferralBundle, DeferralPolicy, DeferralQuery, DeferralRequest, DeferralResult, evaluate_deferral
from .evaluator import context_from_profile, evaluate_expression
from .expression import EvaluationContext, InstantValue, explicit_instant, parse_expression
from .schemas import (AssessmentContextData, AssessmentData, AssessmentError, AssessmentPolicy,
                      AssessmentRequest, ENGINE_VERSION, ReplayRequest, RuleReference, UnknownDimension)

EXTRAS = ("intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")


def _json(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if type(value) is datetime:
        return explicit_instant(value).isoformat()
    if type(value) is UUID:
        return str(value)
    if type(value) is dict:
        return {key: _json(item) for key, item in value.items()}
    if type(value) in (tuple, list):
        return [_json(item) for item in value]
    return value


def _bundle_snapshot(bundle):
    result = bundle.model_dump(mode="json")
    result["expression"] = expression_document(bundle.expression)
    return result


def rule_descriptor(bundle):
    """A precise TEST descriptor, never an automatic conversion of facts to DSL."""
    bundle = RuleBundle.model_validate(bundle)
    nodes = []
    def visit(node):
        index = len(nodes)
        parts = [str(index), node.op]
        if node.field is not None:
            parts += [node.field.name, node.field.key or "-", node.field.basis or "-"]
        for name in ("value", "values", "start", "end"):
            value = getattr(node, name)
            if value is None or name == "values" and not value:
                continue
            items = value if name == "values" else (value,)
            for item in items:
                raw = _json(item)
                if type(raw) is dict:
                    parts.append(name + "=" + ",".join(key + ":" + quote(str(raw[key]), safe="") for key in sorted(raw)))
                else:
                    parts.append(name + "=" + quote(str(raw), safe=""))
        nodes.append("|".join(parts))
        if node.op in {"all", "any"}:
            for child in node.children:
                visit(child)
        elif node.op == "not":
            visit(node.child)
    visit(bundle.expression)
    binding = dict(reference=bundle.reference_key, stage=bundle.stage,
        valid_from=bundle.valid_from.isoformat(), valid_until=bundle.valid_until.isoformat(),
        ruleset=bundle.ruleset_version, scope=bundle.scope_sha256,
        offering=str(bundle.offering_id), offering_version=str(bundle.offering_version))
    return ("DEMO_T28_RULE " + bundle.expression_sha256 + " "
        + ";".join(key+"="+quote(str(binding[key]), safe="") for key in sorted(binding))
        + " " + ";".join(nodes))


def deferral_descriptor(bundle):
    """The approved synthetic text must declare every policy/deadline binding."""
    bundle = DeferralBundle.model_validate(bundle)
    values = {"keys": ",".join(bundle.assessment_keys), "states": ",".join(bundle.allowed_missing_states),
        "stage": bundle.stage, "policy_id": str(bundle.policy_id), "policy_version": bundle.policy_version,
        "scope": bundle.scope_sha256, "application_required": str(bundle.application_deadline_required).lower(),
        "reference": bundle.reference_key, "ruleset": bundle.ruleset_version,
        "valid_from": bundle.valid_from.isoformat(), "valid_until": bundle.valid_until.isoformat(),
        "offering": str(bundle.offering_id), "offering_version": str(bundle.offering_version)}
    for name in ("application_deadline", "supplement_deadline"):
        binding = getattr(bundle, name)
        values[name] = "null" if binding is None else (str(binding.date_event.id) + ":"
            + canonical_request_hash(binding.date_event.model_dump(mode="json")) + ":"
            + (binding.reference_calendar or "unknown"))
    return "DEMO_T28_DEFERRAL " + ";".join(key + "=" + values[key] for key in sorted(values))


class EligibilityService:
    def __init__(self, profile_service, release_service, store,
                 policy=AssessmentPolicy(), *, rule_binding_reader=None, deferral_reader=None):
        try:
            if not isinstance(profile_service, ProfileService) or not isinstance(release_service, ReleaseService) or not isinstance(store, AssessmentsStore):
                raise ValueError()
            self.profile_service, self.release_service, self.store = profile_service, release_service, store
            self.auth_service = profile_service.auth_service
            self.policy = AssessmentPolicy.model_validate(policy)
            self.rule_binding_reader, self.deferral_reader = rule_binding_reader, deferral_reader
            self.proof = AnonymousProofVerifier(release_service)
            self._initial = (profile_service, release_service, store, self.auth_service,
                self.auth_service.clock, self.auth_service.runtime_settings, self.policy,
                rule_binding_reader, deferral_reader)
            self._validate()
        except Exception:
            raise AssessmentError() from None

    def _validate(self):
        try:
            profile, release, store, auth, clock, runtime, policy, reader, deferrals = self._initial
            current = AssessmentPolicy.model_validate(self.policy)
            if (self.profile_service is not profile or self.release_service is not release or self.store is not store
                or self.auth_service is not auth or auth.clock is not clock or auth.runtime_settings != runtime
                or self.rule_binding_reader is not reader or self.deferral_reader is not deferrals or current != policy
                or profile.auth_service is not auth or release.auth_service is not auth
                or store.engine is not auth.store.engine or release.store.engine is not store.engine):
                raise ValueError()
            profile._validate()
            release._validate()
            self.proof.validate_configuration()
            if current.allow_test_bindings and runtime.app_environment != "test":
                raise ValueError()
            if (reader is not None and not callable(reader)) or (deferrals is not None and not callable(deferrals)):
                raise ValueError()
            return current
        except Exception:
            raise AssessmentError() from None

    def _guard_session(self, session):
        self.profile_service._guard_session(session)
        for mapper in (*CATALOG_MAPPERS, EligibilityAssessment):
            bind = session.get_bind(mapper=mapper)
            if getattr(bind, "engine", bind) is not self.store.engine:
                raise AssessmentError()

    @contextmanager
    def _transaction(self, supplied=None):
        try:
            self._validate()
            if supplied is None:
                self.store.assert_schema_ready()
                with Session(self.store.engine) as session, session.begin():
                    self._guard_session(session)
                    yield session
            else:
                self._guard_session(supplied)
                yield supplied
        except Exception as error:
            self.profile_service._abort(supplied)
            if isinstance(error, (AssessmentError, AuthFlowError)):
                raise
            status = getattr(error, "status_code", None)
            if type(status) is int and status in {401, 403, 404, 409}:
                raise error
            raise AssessmentError() from None

    @staticmethod
    def _input(model, value):
        try:
            return model.model_validate(value)
        except (ValueError, TypeError, OverflowError):
            raise AssessmentError(422) from None

    def _authorize(self, session, principal):
        current = self.profile_service._authorize(session, principal)
        if not self._validate().enabled:
            raise AssessmentError()
        return current

    def preflight(self, principal):
        with self._transaction() as session:
            current = self._authorize(session, principal)
            proof = self.profile_service._proof(session, current)
            self.profile_service._final(session, current, proof)
            self._validate()

    def context(self, principal, *, session=None):
        with self._transaction(session) as same:
            current, _ = self.profile_service.authorizer._refresh(principal, same)
            policy = self._validate()
            if not policy.enabled:
                return AssessmentContextData(schema_version="v2.t28", can_evaluate=False, can_read=False, can_replay=False,
                    reason="processing_disabled", is_synthetic=current.is_synthetic)
            current = self._authorize(same, current)
            proof = self.profile_service._proof(same, current)
            self.profile_service._final(same, current, proof)
            self._validate()
            return AssessmentContextData(schema_version="v2.t28", can_evaluate=True, can_read=True, can_replay=True,
                reason="ready" if policy.allow_test_bindings and self.rule_binding_reader is not None else "ruleset_unavailable",
                is_synthetic=current.is_synthetic)

    def _release(self, session, request, profile):
        # Dataset first, as in publication/withdrawal; no reverse root->dataset lock.
        dataset = self.release_service.store.dataset(session, request.target.dataset_id)
        root = self.release_service.store.get(session, request.release_id)
        state = self.release_service.store.state(session, root.id)
        if (root.dataset_id != dataset.id or root.entry_year != profile.entry_year
            or dataset.is_synthetic != root.is_synthetic or state.status != "published"):
            raise AssessmentError(409)
        if root.is_synthetic:
            if (self.auth_service.runtime_settings.app_environment != "test" or root.kind != "test_fixture"
                or dataset.data_mode != "demo"):
                raise AssessmentError()
        elif root.kind != "formal" or dataset.data_mode != "verified":
            raise AssessmentError()
        data = self.release_service.store.result(session, root)
        members = tuple(member for member in self.release_service.store.members(session, root.id)
            if (member.offering_id, member.offering_version) == (request.target.offering_id, request.target.offering_version))
        if not members:
            raise AssessmentError(409)
        proofs = tuple(self.proof.member(session, root, member) for member in members)
        for item in proofs:
            scope = item.evidence.scope
            if ((scope.dataset_id, scope.institution_id, scope.program_id, item.institution.country,
                 item.member.scope_sha256) != (request.target.dataset_id, request.target.institution_id,
                 request.target.program_id, request.target.country, request.target.scope_sha256)):
                raise AssessmentError(409)
        return root, state, data, proofs

    @staticmethod
    def _bounded(model, raw):
        if type(raw) not in (tuple, list) or len(raw) > 32:
            raise AssessmentError()
        try:
            return tuple(model.model_validate(value) for value in raw)
        except (ValueError, TypeError, OverflowError):
            raise AssessmentError() from None

    @staticmethod
    def _rule_verified(bundle, root, proofs):
        by_fact = {proof.fact.id: proof for proof in proofs}
        if (bundle.release_id != root.id or bundle.release_version != root.version
            or bundle.requirements_version != root.requirements_version or not bundle.is_synthetic
            or not root.is_synthetic or bundle.ruleset_version is None
            or set(bundle.fact_ids) - set(by_fact)):
            return False
        selected = tuple(by_fact[identifier] for identifier in bundle.fact_ids)
        text = rule_descriptor(bundle)
        return (len(text.encode("utf-8")) <= 4096 and set(bundle.evidence_ids) == {item.evidence.id for item in selected}
            and any(item.fact.classification.claim_kind == "minimum_requirement" and item.fact.value_text == text
                    and item.fact.missing_reason is None for item in selected)
            and all(item.member.scope_sha256 == bundle.scope_sha256 for item in selected))

    @staticmethod
    def _deferral_verified(bundle, root, proofs):
        if (bundle.release_id != root.id or bundle.release_version != root.version
            or bundle.requirements_version != root.requirements_version or not bundle.is_synthetic):
            return False
        by_evidence = {item.evidence.id: item for item in proofs}
        if set(bundle.policy_evidence_ids) - set(by_evidence):
            return False
        text = deferral_descriptor(bundle)
        if (len(text.encode("utf-8")) > 4096 or not any(
            by_evidence[identifier].fact.classification.claim_kind == "information"
            and by_evidence[identifier].fact.value_text == text for identifier in bundle.policy_evidence_ids)):
            return False
        for name in ("application_deadline", "supplement_deadline"):
            deadline = getattr(bundle, name)
            if deadline is None:
                continue
            expected = deadline.date_event.model_dump(mode="json")
            if set(deadline.evidence_ids) - set(by_evidence):
                return False
            if not any(by_evidence[identifier].fact.date_resolution is not None
                and _date_event(by_evidence[identifier].fact.date_resolution).model_dump(mode="json") == expected
                for identifier in deadline.evidence_ids):
                return False
        return True

    def _rules(self, session, request, profile, root, proofs, at):
        scope = scope_request_from_profile(profile, target=request.target, stage=request.stage,
            assessment_at=at, **{name: getattr(request, name) for name in EXTRAS})
        query = BundleQuery(target=request.target, entry_year=profile.entry_year, stage=request.stage)
        policy = self._validate()
        if not (policy.allow_test_bindings and root.is_synthetic and self.rule_binding_reader is not None):
            return None, "RULESET_UNAVAILABLE", scope
        raw = self.rule_binding_reader(session, query)
        bundles = self._bounded(RuleBundle, raw)
        snapshots = [_bundle_snapshot(bundle) for bundle in bundles]
        selection = select_rules(scope, provider=lambda query: bundles, policy=AdapterPolicy(enabled=True,
            allow_test_bundles=True, app_environment="test", data_mode="demo"),
            verifier=lambda q, bundle: self._rule_verified(bundle, root, proofs))
        if snapshots != [_bundle_snapshot(RuleBundle.model_validate(bundle)) for bundle in bundles]:
            raise AssessmentError()
        self._validate()
        if selection.selection_status != "matched":
            return None, "SCOPE_UNAVAILABLE" if selection.reason in {"MISSING_SCOPE", "SCOPE_MISMATCH", "TARGET_MISMATCH", "YEAR_MISMATCH", "STAGE_MISMATCH"} else "BINDING_UNAVAILABLE", scope
        selected = next(bundle for bundle in bundles if bundle.bundle_id == selection.bundle_id)
        return selected, None, scope

    def _deferrals(self, session, scope, bundle, context, root, proofs, *, required_keys=None):
        result, snapshots, selected = {}, [], []
        if self.deferral_reader is None:
            return result, snapshots, selected
        keys = sorted({field.field.key for field in context.fields if field.field.name == "assessment"
            and field.field.basis == "achieved" and field.datum.status in {"missing", "pending"}})
        if required_keys is not None:
            keys = [key for key in keys if key in required_keys]
        for key in keys:
            state = next(field.datum.status for field in context.fields
                if field.field.name == "assessment" and field.field.key == key and field.field.basis == "achieved")
            request = DeferralRequest(target=scope.target, entry_year=scope.entry_year, stage=scope.stage,
                release_id=bundle.release_id, release_version=bundle.release_version,
                requirements_version=bundle.requirements_version, ruleset_version=bundle.ruleset_version,
                assessment_key=key, basis="achieved", missing_state=state, assessment_at=scope.assessment_at)
            query = DeferralQuery.model_validate({name: getattr(request, name) for name in DeferralQuery.model_fields})
            policies = self._bounded(DeferralBundle, self.deferral_reader(session, query))
            before = [policy.model_dump(mode="json") for policy in policies]
            permission = evaluate_deferral(request, bundles=policies, policy=DeferralPolicy(enabled=True,
                allow_test_bundles=True, app_environment="test", data_mode="demo"),
                verifier=lambda q, policy: self._deferral_verified(policy, root, proofs))
            if before != [DeferralBundle.model_validate(policy).model_dump(mode="json") for policy in policies]:
                raise AssessmentError()
            result[key] = permission
            snapshots.append({"assessment_key": key, "bundles": before})
            if permission.deferral_status == "allowed":
                selected.append(next(policy for policy in policies if policy.bundle_id == permission.bundle_id))
        return result, snapshots, selected

    @staticmethod
    def _context(profile, expression, at):
        # Precision is explicit: a microsecond instant is not a fabricated second.
        instant = InstantValue(value=at, precision="second") if at.microsecond == 0 else None
        complete = context_from_profile(profile, assessment_at=instant)
        refs = set()
        def visit(node):
            if node.field is not None:
                refs.add((node.field.name, node.field.key, node.field.basis))
            for child in node.children:
                visit(child)
            if node.child is not None:
                visit(node.child)
        visit(expression)
        return EvaluationContext(fields=tuple(field for field in complete.fields
            if (field.field.name, field.field.key, field.field.basis) in refs), assessment_date=None,
            assessment_at=complete.assessment_at if ("assessment_at", None, None) in refs or any(node.op == "valid_at" for node in _nodes(expression)) else None)

    def _final(self, session, current, privacy_proof, profile_root, profile_row,
               *, release=None, proofs=(), bundle=None, policies=(), assessment=None, historical=False):
        # This profile final guard performs the LAST SQL and yields one fresh time.
        now = self.profile_service._final(session, current, privacy_proof, (profile_row,), (profile_root,))
        self._validate()
        if not self.policy.enabled or (assessment is not None and not assessment.assessment_at <= now < assessment.expires_at):
            raise AssessmentError(409)
        if not historical:
            self.proof.final_deadlines(proofs, (release,), now)
            if bundle is not None and not bundle.valid_from <= now < bundle.valid_until:
                raise AssessmentError(409)
            for policy, key, missing_state in policies:
                if not policy.valid_from <= now < policy.valid_until:
                    raise AssessmentError(409)
                # Reuse the pure deadline calculation at the final time, without SQL.
                if not self._permission_at(policy, key, missing_state, proofs, now):
                    raise AssessmentError(409)
        return now

    @staticmethod
    def _permission_at(policy, key, missing_state, proofs, now):
        request = DeferralRequest(target=_target(policy, proofs), entry_year=policy.scope.entry_year,
            stage=policy.stage, release_id=policy.release_id, release_version=policy.release_version,
            requirements_version=policy.requirements_version, ruleset_version=policy.ruleset_version,
            assessment_key=key, basis="achieved", missing_state=missing_state, assessment_at=now)
        return evaluate_deferral(request, bundles=(policy,), policy=DeferralPolicy(enabled=True,
            allow_test_bundles=True, app_environment="test", data_mode="demo"),
            verifier=lambda q, p: True).deferral_status == "allowed"

    @staticmethod
    def _necessary(outcome, policies, context):
        result = []
        for obligation in outcome.obligations:
            policy = next((policy for policy in policies if policy.bundle_id == obligation.deferral.bundle_id), None)
            if policy is None:
                raise AssessmentError(409)
            missing = next(field.datum.status for field in context.fields if field.field.name == "assessment"
                and field.field.key == obligation.assessment_key and field.field.basis == "achieved")
            result.append((policy, obligation.assessment_key, missing))
        return tuple(result)

    @audited("authorization.owned.execute")
    def evaluate(self, principal, request, *, session=None):
        with self._transaction(session) as same:
            request = self._input(AssessmentRequest, request)
            current = self._authorize(same, principal)
            current, profile_root, profile_row, privacy, profile = self.profile_service._read(same, current,
                request.profile_id, version_id=request.profile_version_id)
            if profile_root.current_version_id != profile_row.id:
                raise AssessmentError(409)
            release_root, state, release, proofs = self._release(same, request, profile.profile)
            at = self.auth_service._now()
            bundle, unavailable, scope = self._rules(same, request, profile.profile, release_root, proofs, at)
            context = EvaluationContext()
            deferrals, policy_snapshots, policies = {}, [], []
            if bundle is None:
                outcome = EligibilityEngineResult(status="unknown", reason=unavailable, evaluation=None, obligations=())
            else:
                context = self._context(profile.profile, bundle.expression, at)
                if evaluate_expression(bundle.expression, context).truth == "unknown":
                    deferrals, policy_snapshots, policies = self._deferrals(same, scope, bundle, context, release_root, proofs)
                outcome = evaluate_eligibility(bundle.expression, context, deferrals=deferrals)
            values = _json(dict(assessment_id=uuid4(), version=1, profile_id=profile.profile_id,
                profile_version_id=profile.version_id, profile_version=profile.version, profile_sha256=profile.profile_sha256,
                target=request.target, release_id=release.release_id, requirements_version=release.requirements_version,
                ruleset_version=bundle.ruleset_version if bundle else None, stage=request.stage, assessment_at=at,
                expires_at=profile.expires_at, engine_version=ENGINE_VERSION,
                binding_mode="test_fixture" if bundle else "unavailable", profile_is_synthetic=current.is_synthetic,
                catalogue_is_synthetic=release.is_synthetic, eligibility=outcome,
                competition_context=UnknownDimension(status="unknown", reason="DATA_UNAVAILABLE"),
                preference_fit=UnknownDimension(status="unknown", reason="DATA_UNAVAILABLE"),
                data_quality=UnknownDimension(status="unknown", reason="DATA_UNAVAILABLE"),
                rule_refs=(RuleReference(bundle_id=bundle.bundle_id, expression_sha256=bundle.expression_sha256,
                    fact_ids=bundle.fact_ids, evidence_ids=bundle.evidence_ids),) if bundle else (),
                current_validity="current" if bundle else "unavailable", replayed=False))
            # Hash the validated canonical wire representation, including UTC
            # serialization, rather than an earlier native/ISO intermediate.
            values["result_sha256"] = "0" * 64
            canonical = AssessmentData.model_validate(values).model_dump(mode="json")
            canonical["result_sha256"] = result_fingerprint(canonical)
            data = AssessmentData.model_validate(canonical)
            snapshot = dict(request=request.model_dump(mode="json"), entry_year=profile.profile.entry_year,
                context=context.model_dump(mode="json"), expression=expression_document(bundle.expression) if bundle else None,
                deferrals={key: value.model_dump(mode="json") for key, value in deferrals.items()},
                bundle=_bundle_snapshot(bundle) if bundle else None, policies=policy_snapshots,
                release_content_sha256=release.content_sha256)
            audit = self.auth_service.store.audit.success(same, "authorization.owned.execute", actor=current,
                object_type="profile", object_id=profile.profile_id, object_version=profile.version, now=at)
            row = self.store.create(same, owner=current, data=data, snapshot=snapshot, audit_event_id=audit.id)
            result = self.store.result(row, current_validity=data.current_validity)
            final_now = self._final(same, current, privacy, profile_root, profile_row, release=(release_root, state),
                proofs=proofs, bundle=bundle, policies=self._necessary(outcome, policies, context), assessment=result)
            if bundle is not None:
                final_outcome = evaluate_eligibility(bundle.expression,
                    self._context(profile.profile, bundle.expression, final_now), deferrals=deferrals)
                if (final_outcome.status, final_outcome.obligations) != (outcome.status, outcome.obligations):
                    raise AssessmentError(409)
        return result

    def _historical(self, session, row, data, profile):
        request = AssessmentRequest.model_validate(row.replay_snapshot["request"])
        dataset = self.release_service.store.dataset(session, data.target.dataset_id)
        root = self.release_service.store.get(session, data.release_id)
        state = self.release_service.store.state(session, root.id)
        if root.content_sha256 != row.replay_snapshot["release_content_sha256"] or dataset.id != root.dataset_id:
            raise AssessmentError()
        if state.status in {"withdrawn", "replaced"}:
            return state.status, None
        try:
            root, state, release, proofs = self._release(session, request, profile.profile)
            bundle, missing, scope = self._rules(session, request, profile.profile, root, proofs, self.auth_service._now())
            if data.binding_mode == "unavailable":
                return "unavailable", (root, state, proofs, None, (), {})
            if bundle is None or _bundle_snapshot(bundle) != row.replay_snapshot["bundle"]:
                return "needs_review", None
            context = EvaluationContext.model_validate(row.replay_snapshot["context"])
            keys = {obligation.assessment_key for obligation in data.eligibility.obligations}
            if data.eligibility.status in {"eligible", "ineligible"}:
                return "current", (root, state, proofs, bundle, (), {})
            permissions, snapshots, policies = self._deferrals(session, scope, bundle, context, root, proofs,
                required_keys=keys if data.eligibility.status == "conditional" else None)
            expected = [snapshot for snapshot in row.replay_snapshot["policies"]
                if data.eligibility.status != "conditional" or snapshot["assessment_key"] in keys]
            if snapshots != expected:
                return "needs_review", None
            for obligation in data.eligibility.obligations:
                actual = permissions.get(obligation.assessment_key)
                if (actual is None or actual.deferral_status != "allowed"
                    or actual != obligation.deferral):
                    return "needs_review", None
            return "current", (root, state, proofs, bundle, self._necessary(data.eligibility, policies, context), permissions)
        except Exception as error:
            if getattr(error, "status_code", None) in {404, 409}:
                return "needs_review", None
            raise

    @audited("authorization.owned.execute")
    def get_assessment(self, principal, assessment_id, *, session=None, _replayed=False):
        with self._transaction(session) as same:
            current = self._authorize(same, principal)
            row = self.store.get(same, assessment_id, current.user_id)
            data = self.store.result(row)
            current, root, version, privacy, profile = self.profile_service._read(same, current,
                row.profile_id, version_id=row.profile_version_id)
            if data.profile_sha256 != profile.profile_sha256:
                raise AssessmentError()
            snapshot = row.replay_snapshot
            if snapshot["expression"] is not None:
                expression = parse_expression(snapshot["expression"])
                context = EvaluationContext.model_validate(snapshot["context"])
                expected = self._context(profile.profile, expression, data.assessment_at)
                if context != expected:
                    raise AssessmentError()
                recomputed = evaluate_eligibility(expression, context,
                    deferrals={key: DeferralResult.model_validate(value) for key, value in snapshot["deferrals"].items()})
                if recomputed != data.eligibility:
                    raise AssessmentError()
            elif data.eligibility.evaluation is not None or snapshot["context"] != EvaluationContext().model_dump(mode="json"):
                raise AssessmentError()
            validity, current_proof = self._historical(same, row, data, profile)
            if root.current_version_id != version.id and validity in {"current", "unavailable"}:
                validity = "needs_review"
            self.auth_service.store.audit.success(same, "authorization.owned.execute", actor=current,
                object_type="profile", object_id=profile.profile_id, object_version=profile.version,
                now=self.auth_service._now())
            result = self.store.result(row, current_validity=validity, replayed=_replayed)
            now = self._final(same, current, privacy, root, version, assessment=result, historical=True)
            if current_proof is not None:
                release_root, state, proofs, bundle, policies, permissions = current_proof
                try:
                    self.proof.final_deadlines(proofs, ((release_root, state),), now)
                    if bundle is not None and not bundle.valid_from <= now < bundle.valid_until:
                        raise PublicCatalogError(409)
                    if any(not policy.valid_from <= now < policy.valid_until
                        or not self._permission_at(policy, key, missing, proofs, now)
                        for policy, key, missing in policies):
                        raise PublicCatalogError(409)
                    if bundle is not None:
                        fresh = evaluate_eligibility(bundle.expression,
                            self._context(profile.profile, bundle.expression, now), deferrals=permissions)
                        if (fresh.status, fresh.obligations) != (data.eligibility.status, data.eligibility.obligations):
                            raise PublicCatalogError(409)
                except PublicCatalogError:
                    result = self.store.result(row, current_validity="needs_review", replayed=_replayed)
        return result

    @audited("authorization.owned.execute")
    def replay(self, principal, assessment_id, request, *, session=None):
        with self._transaction(session) as same:
            self._input(ReplayRequest, request)
            result = self.get_assessment(principal, assessment_id, session=same, _replayed=True)
        return result


def _nodes(expression):
    yield expression
    for child in expression.children:
        yield from _nodes(child)
    if expression.child is not None:
        yield from _nodes(expression.child)


def _target(policy, proofs):
    from .adapters.schemas import TargetReference
    proof = proofs[0]
    scope = policy.scope
    return TargetReference(dataset_id=scope.dataset_id, institution_id=scope.institution_id,
        program_id=scope.program_id, offering_id=policy.offering_id, offering_version=policy.offering_version,
        country=proof.institution.country, scope_sha256=policy.scope_sha256)


def _date_event(snapshot):
    from ..admissions_catalog.date_schemas import DateEventData
    raw = snapshot.model_dump()
    raw["id"] = raw.pop("date_event_id")
    raw.update(review_state="draft", evidence_state="unresolved")
    return DateEventData.model_validate(raw)
