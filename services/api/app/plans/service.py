"""Owner-only, unconfirmed drafts with current source proofs in one transaction."""

from contextlib import contextmanager
from datetime import date, datetime, time
import json
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from ..audit.context import audited
from ..auth.config import AuthFlowError
from ..public_catalog.schemas import PublicCatalogError
from ..rules.adapters.schemas import RuleBundle
from ..rules.assessment_engine import evaluate_eligibility
from ..rules.deferral import DeferralBundle
from ..rules.service import EligibilityService
from .drafts import build_plan_draft
from .schemas import DraftBuildInput, PlanCreateInput, PlanError, PlanPolicy
from .store import PlansStore, assessment_reference


def _policy_snapshot(value):
    """Decode only T12 native date fields inside a stored T28 policy binding."""
    raw = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    for purpose in ("application_deadline", "supplement_deadline"):
        binding = raw[purpose]
        if binding is None:
            continue
        event = binding["date_event"]
        for key, parser in (("local_date", date.fromisoformat), ("local_time", time.fromisoformat),
                            ("calculated_utc_instant", datetime.fromisoformat), ("utc_instant", datetime.fromisoformat)):
            if event[key] is not None:
                event[key] = parser(event[key])
    result = DeferralBundle.model_validate(raw)
    if result.model_dump(mode="json") != value:
        raise PlanError()
    return result


class PlansService:
    def __init__(self, eligibility_service, store, policy=PlanPolicy()):
        try:
            if not isinstance(eligibility_service, EligibilityService) or not isinstance(store, PlansStore):
                raise ValueError()
            self.eligibility_service, self.store = eligibility_service, store
            self.auth_service = eligibility_service.auth_service
            self.policy = PlanPolicy.model_validate(policy)
            self._initial = (eligibility_service, store, self.auth_service, self.auth_service.clock,
                             self.auth_service.runtime_settings, self.policy)
            self._validate()
        except Exception:
            raise PlanError() from None

    def _validate(self):
        try:
            eligibility, store, auth, clock, runtime, policy = self._initial
            current = PlanPolicy.model_validate(self.policy)
            if (self.eligibility_service is not eligibility or self.store is not store or self.auth_service is not auth
                or auth.clock is not clock or auth.runtime_settings != runtime or current != policy
                or eligibility.auth_service is not auth or eligibility.store.engine is not store.engine
                or auth.store.engine is not store.engine or current.allow_test_drafts and runtime.app_environment != "test"):
                raise ValueError()
            eligibility._validate()
            return current
        except Exception:
            raise PlanError() from None

    def _guard_session(self, session):
        # All mapper guards run before the first SQL, including supplied bind overrides.
        self.eligibility_service._guard_session(session)
        with self.store._work(session):
            pass

    @contextmanager
    def _transaction(self, supplied=None):
        try:
            self._validate()
            if supplied is None:
                self.store.assert_schema_ready()
                with Session(self.store.engine) as same, same.begin():
                    self._guard_session(same)
                    yield same
            else:
                self._guard_session(supplied)
                yield supplied
        except (PlanError, AuthFlowError):
            self.eligibility_service.profile_service._abort(supplied)
            raise
        except Exception as error:
            self.eligibility_service.profile_service._abort(supplied)
            status = getattr(error, "status_code", 503)
            raise PlanError(status if status in {422, 404, 409, 503} else 503) from None

    def _authorize(self, session, principal):
        current = self.eligibility_service._authorize(session, principal)
        policy = self._validate()
        if (not policy.enabled or not policy.allow_test_drafts or not current.is_synthetic
            or self.auth_service.runtime_settings.app_environment != "test"):
            raise PlanError()
        return current

    def _sources(self, session, current, ids):
        results, rows = [], []
        for identifier in ids:
            data = self.eligibility_service.get_assessment(current, identifier, session=session)
            row = self.eligibility_service.store.get(session, identifier, current.user_id)
            if not data.profile_is_synthetic or not data.catalogue_is_synthetic:
                raise PlanError()
            results.append(data)
            rows.append(row)
        if results:
            _, root, version, _, _ = self.eligibility_service.profile_service._read(session,current,
                results[0].profile_id,version_id=results[0].profile_version_id)
            if root.current_version_id != version.id:
                raise PlanError(409)
        return tuple(results), tuple(rows)

    @staticmethod
    def _snapshots(assessments, rows):
        rules, policies = {}, {}
        for assessment, row in zip(assessments, rows, strict=True):
            snapshot = row.replay_snapshot
            raw = snapshot["bundle"]
            if raw is not None:
                bundle = RuleBundle.model_validate(raw)
                # Expr dumps contain explicit optional fields; compare the canonical
                # op-specific snapshot rather than a generic full model dump.
                from ..rules.service import _bundle_snapshot
                if _bundle_snapshot(bundle) != raw:
                    raise PlanError()
                old = rules.get(bundle.bundle_id)
                if old is not None and old != bundle:
                    raise PlanError()
                rules[bundle.bundle_id] = bundle
            necessary = {o.deferral.bundle_id for o in assessment.eligibility.obligations}
            if assessment.current_validity == "current":
                for group in snapshot["policies"]:
                    for raw in group["bundles"]:
                        if UUID(raw["bundle_id"]) not in necessary:
                            continue
                        policy = _policy_snapshot(raw)
                        old = policies.get(policy.bundle_id)
                        if old is not None and old != policy:
                            raise PlanError()
                        policies[policy.bundle_id] = policy
        return tuple(rules.values()), tuple(policies.values())

    def _final(self, session, current, assessments, *, created_at, expires_at):
        # Re-read original ownership/purpose and current evidence after every write
        # and audit flush. A current -> historical change must abort the new draft.
        fresh, rows = self._sources(session, current, tuple(a.assessment_id for a in assessments))
        if fresh != assessments:
            raise PlanError(409)
        profiles = self.eligibility_service.profile_service
        current, root, version, privacy, profile = profiles._read(session, current,
            fresh[0].profile_id, version_id=fresh[0].profile_version_id)
        if root.current_version_id != version.id:
            raise PlanError(409)
        proofs = []
        for data, row in zip(fresh, rows, strict=True):
            validity, proof = self.eligibility_service._historical(session, row, data, profile)
            if root.current_version_id != version.id and validity in {"current", "unavailable"}:
                validity = "needs_review"
            if validity != data.current_validity:
                raise PlanError(409)
            proofs.append(proof)
        # Profile final performs the LAST SQL. All following checks share this time.
        now = profiles._final(session, current, privacy, (version,), (root,))
        self._validate()
        if not created_at <= now < expires_at or any(not a.assessment_at <= now < a.expires_at for a in fresh):
            raise PlanError(409)
        for data, proof in zip(fresh, proofs, strict=True):
            if proof is None:
                continue
            release_root, state, members, bundle, policies, permissions = proof
            try:
                self.eligibility_service.proof.final_deadlines(members, ((release_root, state),), now)
                if bundle is not None and not bundle.valid_from <= now < bundle.valid_until:
                    raise PublicCatalogError(409)
                if any(not p.valid_from <= now < p.valid_until or not self.eligibility_service._permission_at(p,k,m,members,now)
                       for p,k,m in policies):
                    raise PublicCatalogError(409)
                if bundle is not None:
                    outcome = evaluate_eligibility(bundle.expression,
                        self.eligibility_service._context(profile.profile, bundle.expression, now), deferrals=permissions)
                    if (outcome.status, outcome.obligations) != (data.eligibility.status, data.eligibility.obligations):
                        raise PublicCatalogError(409)
            except PublicCatalogError:
                raise PlanError(409) from None

    @audited("authorization.owned.execute")
    def create_draft(self, principal, request, *, session=None):
        with self._transaction(session) as same:
            try:
                request = PlanCreateInput.model_validate(request)
            except (ValueError, TypeError):
                raise PlanError(422) from None
            current = self._authorize(same, principal)
            assessments, rows = self._sources(same, current, request.assessment_ids)
            rules, policies = self._snapshots(assessments, rows)
            now = self.auth_service._now()
            draft = build_plan_draft(DraftBuildInput(assessments=assessments, confirmed=request.confirmed,
                generated_at=now, study_goals=request.study_goals, estimate_overrides=request.estimate_overrides,
                rule_bundles=rules, deadline_bundles=policies))
            plan_id = uuid4()
            self.eligibility_service.profile_service.authorizer.register_owned(current, "plan", resource_id=plan_id, session=same)
            audit = self.auth_service.store.audit.success(same,"authorization.owned.execute",actor=current,
                object_type="plan",object_id=plan_id,object_version=1,now=now)
            root = self.store.create(same,current,draft,plan_id=plan_id,audit_event_id=audit.id,now=now)
            result = self.store.result(same,root)
            self.auth_service.store.audit.success(same,"authorization.owned.execute",actor=current,
                object_type="plan",object_id=plan_id,object_version=1,now=self.auth_service._now())
            self._final(same,current,assessments,created_at=result.created_at,expires_at=result.expires_at)
        return result

    @audited("authorization.owned.execute")
    def get_draft(self, principal, plan_id, *, session=None):
        with self._transaction(session) as same:
            current = self._authorize(same,principal)
            current,owned = self.eligibility_service.profile_service.authorizer.check_owned_in_transaction(same,current,"plan",plan_id,"read")
            root = self.store.get(same,plan_id,current.user_id)
            if (owned.parent_id is not None or owned.version != root.current_version
                or owned.is_synthetic != root.is_synthetic or root.is_synthetic != current.is_synthetic):
                raise PlanError()
            result = self.store.result(same,root)
            assessments, _ = self._sources(same,current,tuple(ref.assessment_id for ref in result.draft.assessment_refs))
            expected = {ref.assessment_id:ref for ref in result.draft.assessment_refs}
            if any(a.current_validity != expected[a.assessment_id].current_validity for a in assessments):
                raise PlanError(409)
            if any(assessment_reference(a) != expected[a.assessment_id]
                or (a.profile_id,a.profile_version_id,a.profile_sha256,a.profile_is_synthetic) !=
                   (result.draft.profile_id,result.draft.profile_version_id,result.draft.profile_sha256,result.draft.is_synthetic)
                or not a.assessment_at <= result.created_at < result.expires_at <= a.expires_at for a in assessments):
                raise PlanError()
            self.auth_service.store.audit.success(same,"authorization.owned.execute",actor=current,
                object_type="plan",object_id=plan_id,object_version=result.version,now=self.auth_service._now())
            self._final(same,current,assessments,created_at=result.created_at,expires_at=result.expires_at)
        return result
