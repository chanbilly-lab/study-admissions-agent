"""Trusted committed-event processing and original-purpose owner trace reads."""

from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.context import audited
from ..auth.config import AuthFlowError
from ..auth.authorization import AuthorizationError
from ..assessments.models import EligibilityAssessment
from ..plans.models import PlanRoot, PlanVersion
from ..plan_execution.service import ExecutionService
from ..profiles.store import database_time
from ..releases.models import ChangeEvent, OutboxEvent
from ..rules.adapters.schemas import TargetReference
from ..rules.service import EligibilityService
from .comparator import compare_releases, target_member_diffs
from .schemas import (ChangesPolicy, ChangesError, ChangeImpactData, ChangeImpactPage)
from .store import ChangesStore, bounded_json, event_fingerprint, impact_data
from .schemas import fingerprint


def _uuid(value):
    if type(value) is not UUID or value.version != 4:
        raise ChangesError(422)
    return value


def _diff_trace(diff):
    """Keep references/fields, never copy original text or student inputs."""
    result = diff.model_dump(mode="json")
    for group in result["member_diffs"]:
        del group["before"]
        del group["after"]
    return bounded_json(result)


class ChangesService:
    def __init__(self, eligibility_service, execution_service, store, policy=ChangesPolicy()):
        try:
            if (not isinstance(eligibility_service, EligibilityService) or not isinstance(execution_service, ExecutionService)
                or not isinstance(store, ChangesStore)):
                raise ValueError()
            self.eligibility_service, self.execution_service, self.store = eligibility_service, execution_service, store
            self.auth_service = eligibility_service.auth_service
            self.profile_service = eligibility_service.profile_service
            self.policy = ChangesPolicy.model_validate(policy)
            self._initial = (eligibility_service, execution_service, store, self.auth_service,
                self.auth_service.clock, self.auth_service.runtime_settings, self.policy)
            self._validate()
        except Exception:
            raise ChangesError() from None

    def _validate(self):
        try:
            eligibility, execution, store, auth, clock, runtime, policy = self._initial
            current = ChangesPolicy.model_validate(self.policy)
            if (self.eligibility_service is not eligibility or self.execution_service is not execution
                or self.store is not store or self.auth_service is not auth or auth.clock is not clock
                or auth.runtime_settings != runtime or current != policy
                or self.profile_service is not eligibility.profile_service
                or execution.plans_service.eligibility_service is not eligibility
                or eligibility.store.engine is not store.engine or execution.store.engine is not store.engine
                or auth.store.engine is not store.engine):
                raise ValueError()
            eligibility._validate()
            execution._validate()
            return current
        except Exception:
            raise ChangesError() from None

    def _ready(self):
        policy = self._validate()
        if (not policy.enabled or not policy.allow_test_changes
            or self.auth_service.runtime_settings.app_environment != "test"):
            raise ChangesError()

    def _guard_session(self, session):
        self.eligibility_service._guard_session(session)
        self.execution_service._guard_session(session)
        with self.store._work(session):
            pass

    def _preflight(self, session):
        try:
            self._ready()
            if session is not None:
                self._guard_session(session)
        except Exception as error:
            self.profile_service._abort(session)
            if isinstance(error,ChangesError):
                raise
            raise ChangesError() from None

    @contextmanager
    def _transaction(self, supplied=None):
        try:
            self._ready()  # Closed/malformed configuration never connects.
            if supplied is None:
                self.store.assert_schema_ready()
                with Session(self.store.engine) as same, same.begin():
                    self._guard_session(same)
                    yield same
            else:
                self._guard_session(supplied)
                yield supplied
        except Exception as error:
            self.profile_service._abort(supplied)
            if isinstance(error, (ChangesError, AuthFlowError, AuthorizationError)):
                raise
            status = getattr(error, "status_code", None)
            if type(status) is int and status in {401,403,404,409,422}:
                raise ChangesError(status if status in {404,409,422} else 503) from None
            raise ChangesError() from None

    def _event_snapshots(self, session, event):
        root, state, before = self.store.snapshot(session, event.release_id)
        if (event.dataset_id, event.entry_year, event.is_synthetic) != (root.dataset_id, root.entry_year, root.is_synthetic):
            raise ChangesError(409)
        if not event.is_synthetic or root.kind != "test_fixture" or state.revision < event.state_revision:
            raise ChangesError()
        outbox = session.execute(select(OutboxEvent.status, OutboxEvent.created_at).where(OutboxEvent.event_id == event.id)).one_or_none()
        history = tuple(session.scalars(select(ChangeEvent).where(ChangeEvent.release_id == event.release_id)
            .order_by(ChangeEvent.state_revision)).all())
        if (outbox is None or outbox.status != "pending" or not history or len(history) > 2
            or tuple(row.state_revision for row in history) != tuple(range(1, state.revision + 1))
            or history[0].event_type != "published" or history[0].created_at != root.published_at
            or history[0].audit_event_id != root.audit_event_id or history[0].actor_user_id != root.publisher_user_id
            or database_time(state.updated_at) < database_time(root.published_at)):
            raise ChangesError(409)
        times = [database_time(event.created_at), database_time(root.published_at),
                 database_time(state.updated_at), database_time(outbox.created_at)]
        if event.event_type == "published":
            if event.state_revision != 1 or event.related_release_id is not None or event.reason_code is not None:
                raise ChangesError(409)
            return None, before, tuple(times)
        if event.event_type == "withdrawn":
            if (event.state_revision != 2 or event.related_release_id is not None or state.status != "withdrawn"
                or event.reason_code not in {"INCORRECT_FACT","RIGHTS_REVOKED","SOURCE_UNAVAILABLE","ADMIN_REQUEST"}):
                raise ChangesError(409)
            return before, None, tuple(times)
        if event.event_type != "replaced" or event.state_revision != 2 or event.related_release_id is None or event.reason_code is not None:
            raise ChangesError(409)
        other, other_state, after = self.store.snapshot(session, event.related_release_id)
        paired = session.scalar(select(ChangeEvent).where(ChangeEvent.release_id == other.id, ChangeEvent.state_revision == 1))
        if (state.status != "replaced" or state.replaced_by_release_id != other.id or other.replaces_release_id != root.id
            or (other.dataset_id, other.entry_year, other.is_synthetic, other.kind) != (root.dataset_id, root.entry_year, root.is_synthetic, root.kind)
            or paired is None or paired.event_type != "published" or paired.created_at != event.created_at
            or paired.audit_event_id != event.audit_event_id or paired.actor_user_id != event.actor_user_id):
            raise ChangesError(409)
        times += [database_time(other.published_at), database_time(other_state.updated_at)]
        return before, after, tuple(times)

    @staticmethod
    def _assessment_reasons(source, diff):
        try:
            target = TargetReference.model_validate(source["target"])
            if (target.dataset_id != source["dataset_id"] or source["release_id"] != diff.before_release_id
                or source["entry_year"] != diff.entry_year or source["catalogue_is_synthetic"] != diff.is_synthetic
                or source["profile_is_synthetic"] != diff.is_synthetic):
                raise ValueError()
            groups = target_member_diffs(diff,offering_id=target.offering_id,
                offering_version=target.offering_version,scope_sha256=target.scope_sha256)
            if not groups:
                return target, ()
            # The target repeats public identities alongside its scope pin.
            # An unavailable/unknown request can legally name another program;
            # it is not an affected target merely because its offering ID agrees.
            identities = (target.institution_id,target.program_id,target.country)
            if any((value.scope.institution_id,value.scope.program_id,value.scope.country) != identities
                   for group in groups for value in group.before):
                return target, ()
            reasons = set()
            if diff.event_type == "withdrawn":
                reasons.add("RELEASE_WITHDRAWN")
            else:
                if "validity" in diff.release_changed_fields:
                    reasons.add("RELEASE_WINDOW_CHANGED")
                if "ruleset" in diff.release_changed_fields:
                    reasons.add("RULESET_CHANGED")
                for group in groups:
                    if group.kind == "added":
                        reasons.add("MEMBER_ADDED")
                    elif group.kind == "removed":
                        reasons.add("MEMBER_REMOVED")
                    elif group.semantic_business_changed:
                        reasons.add("BUSINESS_CHANGED")
                if diff.reference_changed:
                    reasons.add("REFERENCE_REPLACED")
            return target, tuple(sorted(reasons))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ChangesError(409) from None

    def process_event(self, event_id, *, session=None):
        # The only input is a stored UUID. This port has no caller identity,
        # client review flag, publication permission, or student payload.
        with self._transaction(session) as same:
            rights_guard = self.auth_service.store.rights_guard
            blocked_owners = rights_guard.blocked_owners(same) if rights_guard is not None else frozenset()
            event = self.store.event(same, _uuid(event_id))
            before, after, times = self._event_snapshots(same, event)
            diff = compare_releases(before, after, event_type=event.event_type)
            trace = _diff_trace(diff)
            event_sha = event_fingerprint(event)
            receipt = self.store.receipt(same, event.id)
            if receipt is None:
                created = self.auth_service._now()
                counts = [0,0]
                if diff.before_release_id is not None:
                    for source in self.store.assessments(same, diff.before_release_id, diff.dataset_id, diff.entry_year, blocked_owners=blocked_owners):
                        target, reasons = self._assessment_reasons(source, diff)
                        if not reasons:
                            continue
                        value = ChangeImpactData(event_id=event.id, assessment_id=source["id"], plan_id=None,
                            before_release_id=diff.before_release_id, after_release_id=diff.after_release_id,
                            needs_review=any(reason != "REFERENCE_REPLACED" for reason in reasons), reasons=reasons,
                            offering_id=target.offering_id, entry_year=diff.entry_year, created_at=created)
                        self.store.insert_assessment(same,source,value)
                        counts[0] += 1
                        for association in self.store.plans(same,source["id"]):
                            if (association["owner_user_id"] != source["owner_user_id"]
                                or association["is_synthetic"] != source["profile_is_synthetic"]):
                                raise ChangesError(409)
                            self.store.insert_plan(same,association,value)
                            counts[1] += 1
                receipt = self.store.insert_receipt(same,event,diff,trace,counts,created)
                replayed = False
            else:
                replayed = True
            erased_counts = rights_guard.erased_counts(same, event.id) if rights_guard is not None else (0, 0)
            result = self.store.processing_data(same,receipt,event_sha256=event_sha,payload=trace,replayed=replayed,erased_counts=erased_counts)
            # No SQL after this single fresh time. An old published event can
            # legitimately be processed after replacement/withdrawal/expiry.
            now = self.auth_service._now()
            self._ready()
            if any(value > now for value in (*times,result.processed_at)) or result.processed_at < database_time(event.created_at):
                raise ChangesError(409)
        return result

    def _assessment_owner(self, session, current, assessment_id):
        # A minimal scalar projection: no eligibility result or replay payload.
        row = session.execute(select(EligibilityAssessment.id, EligibilityAssessment.owner_user_id,
            EligibilityAssessment.profile_id, EligibilityAssessment.profile_version_id, EligibilityAssessment.profile_is_synthetic,
            EligibilityAssessment.profile_version, EligibilityAssessment.assessment_at, EligibilityAssessment.expires_at,
            EligibilityAssessment.payload["profile_sha256"].label("profile_sha256"),
            EligibilityAssessment.payload["target"].label("target"), EligibilityAssessment.entry_year,
            EligibilityAssessment.release_id).where(
                EligibilityAssessment.id == assessment_id, EligibilityAssessment.owner_user_id == current.user_id)
            .with_for_update()).mappings().one_or_none()
        if row is None:
            raise ChangesError(404)
        if row["profile_is_synthetic"] != current.is_synthetic:
            raise ChangesError(409)
        return row

    def _profile(self, session, current, row):
        values = self.profile_service._read(session,current,row["profile_id"],version_id=row["profile_version_id"])
        if "profile_sha256" in row and (values[2].payload_sha256 != row["profile_sha256"]
            or values[2].version != row["profile_version"]):
            raise ChangesError(409)
        return values

    def _final_read(self, session, current, proof, version, root, values, lifetimes):
        now = self.profile_service._final(session,current,proof,(version,),(root,))
        self._ready()
        if any(not start <= now < end for start,end in lifetimes) or any(value.created_at > now for value in values):
            raise ChangesError(409)

    def _impact_receipts(self, session, values):
        for identifier in sorted({value.event_id for value in values}):
            event = session.get(ChangeEvent,identifier,populate_existing=True)
            receipt = self.store.receipt(session,identifier)
            if (event is None or receipt is None or receipt.event_sha256 != event_fingerprint(event)
                or receipt.payload_sha256 != fingerprint(receipt.payload)
                or receipt.audit_event_id != event.audit_event_id):
                raise ChangesError(409)
            for value in values:
                if value.event_id == identifier and (value.before_release_id != receipt.before_release_id
                    or value.after_release_id != receipt.after_release_id or value.entry_year != receipt.entry_year
                    or value.created_at != database_time(receipt.processed_at)
                    or database_time(event.created_at) > value.created_at):
                    raise ChangesError(409)

    def get_assessment_impacts(self, principal, assessment_id, *, session=None):
        self._preflight(session)
        return self._get_assessment_impacts(principal,assessment_id,session=session)

    @audited("authorization.owned.check")
    def _get_assessment_impacts(self, principal, assessment_id, *, session=None):
        with self._transaction(session) as same:
            current = self.profile_service._authorize(same,principal)
            row = self._assessment_owner(same,current,_uuid(assessment_id))
            current, root, version, proof, _ = self._profile(same,current,row)
            rows = self.store.assessment_impacts(same,row["id"],current.user_id)
            values = tuple(impact_data(value) for value in rows)
            target = TargetReference.model_validate(row["target"])
            if any((value.offering_id,value.entry_year,value.before_release_id) !=
                   (target.offering_id,row["entry_year"],row["release_id"]) for value in values):
                raise ChangesError(409)
            if any(value.is_synthetic != current.is_synthetic for value in rows):
                raise ChangesError(409)
            self._impact_receipts(same,values)
            self.auth_service.store.audit.success(same,"authorization.owned.check",actor=current,
                object_type="profile",object_id=root.id,object_version=version.version,now=self.auth_service._now())
            result = ChangeImpactPage(items=values)
            self._final_read(same,current,proof,version,root,values,
                ((database_time(row["assessment_at"]),database_time(row["expires_at"])),))
        return result

    def get_plan_impacts(self, principal, plan_id, *, session=None):
        self._preflight(session)
        return self._get_plan_impacts(principal,plan_id,session=session)

    @audited("authorization.owned.check")
    def _get_plan_impacts(self, principal, plan_id, *, session=None):
        with self._transaction(session) as same:
            current = self.profile_service._authorize(same,principal)
            plan_id = _uuid(plan_id)
            current, owned = self.profile_service.authorizer.check_owned_in_transaction(same,current,"plan",plan_id,"read")
            root = same.scalar(select(PlanRoot).where(PlanRoot.id == plan_id,PlanRoot.owner_user_id == current.user_id)
                .with_for_update().execution_options(populate_existing=True))
            if (root is None or root.is_synthetic != current.is_synthetic or owned.version != root.current_version
                or owned.parent_id is not None or root.current_version != 1):
                raise ChangesError(404)
            version_lifetime = same.execute(select(PlanVersion.created_at,PlanVersion.expires_at).where(
                PlanVersion.id == root.current_version_id,PlanVersion.plan_id == root.id,PlanVersion.owner_user_id == current.user_id)).one_or_none()
            if version_lifetime is None:
                raise ChangesError(409)
            current, profile_root, profile_version, proof, _ = self._profile(same,current,
                {"profile_id":root.profile_id,"profile_version_id":root.profile_version_id})
            rows = self.store.plan_impacts(same,plan_id,current.user_id)
            values = tuple(impact_data(value,plan_id=plan_id) for value in rows)
            if any(value.is_synthetic != current.is_synthetic for value in rows):
                raise ChangesError(409)
            self._impact_receipts(same,values)
            # Validate durable plan impact hashes as well as inherited references.
            from .models import PlanChangeImpact
            durable = tuple(same.scalars(select(PlanChangeImpact).where(PlanChangeImpact.plan_id == plan_id,
                PlanChangeImpact.owner_user_id == current.user_id)).all())
            actual = {(value.event_id,value.assessment_id):value for value in values}
            for value in durable:
                captured = impact_data(value)
                if actual.get((captured.event_id,captured.assessment_id)) != captured:
                    raise ChangesError(409)
            lifetimes = [(database_time(root.created_at),database_time(version_lifetime.expires_at)),
                (database_time(version_lifetime.created_at),database_time(version_lifetime.expires_at))]
            for assessment_id in sorted({value.assessment_id for value in values}):
                original = self._assessment_owner(same,current,assessment_id)
                if (original["profile_id"],original["profile_version_id"]) != (root.profile_id,root.profile_version_id):
                    raise ChangesError(409)
                lifetimes.append((database_time(original["assessment_at"]),database_time(original["expires_at"])))
            self.auth_service.store.audit.success(same,"authorization.owned.check",actor=current,
                object_type="plan",object_id=root.id,object_version=root.current_version,now=self.auth_service._now())
            result = ChangeImpactPage(items=values)
            self._final_read(same,current,proof,profile_version,profile_root,values,tuple(lifetimes))
        return result
