"""Explicit strong-reviewer decisions, with current same-transaction proof."""

from contextlib import contextmanager
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..admissions_catalog.store import CatalogStoreError
from ..audit.context import audited
from ..auth.authorization import AuthorizationError
from ..auth.config import AuthFlowError
from ..evidence.schemas import EvidenceError
from ..evidence.store import utc_time
from ..facts.schemas import FactsError
from ..facts.service import FactService
from ..idempotency.schemas import IdempotencyError
from ..ingestion.schemas import ImportServiceError
from ..storage.schemas import StorageError
from .models import ReviewCase, ReviewDecision, ReviewConflictResolution
from .schemas import ReviewPolicy, ReviewRequest, ReviewsError
from .store import ReviewsStore, _input, fact_fingerprint, conflict_fingerprint
from .validation import validate_review


class ReviewService:
    def __init__(self, fact_service: FactService, store: ReviewsStore,
                 policy: ReviewPolicy = ReviewPolicy()):
        self.fact_service, self.store = fact_service, store
        self.auth_service = getattr(fact_service, "auth_service", None)
        try:
            self.policy = ReviewPolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise ReviewsError() from None
        self._initial_policy = self.policy
        self._validate()

    def _validate(self):
        if (not isinstance(self.fact_service, FactService) or not isinstance(self.store, ReviewsStore)
            or self.auth_service is not self.fact_service.auth_service
            or self.store.engine is not self.fact_service.store.engine):
            raise ReviewsError()
        settings, facts_policy, imports_policy = self.fact_service._validate()
        try:
            policy = ReviewPolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise ReviewsError() from None
        if policy != self._initial_policy:
            raise ReviewsError()
        return settings, policy, facts_policy, imports_policy

    def _guard_session(self, session):
        self.fact_service._guard_session(session)
        try:
            for mapper in (ReviewCase, ReviewDecision, ReviewConflictResolution):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise ReviewsError()
        except ReviewsError:
            raise
        except Exception:
            raise ReviewsError() from None

    def _rollback_supplied(self, session):
        try:
            if isinstance(session, Session) and session.in_transaction():
                bind = session.get_bind()
                if getattr(bind, "engine", bind) is self.store.engine:
                    session.rollback()
        except Exception:
            pass

    @contextmanager
    def _transaction(self, supplied=None):
        try:
            self._validate()
            if supplied is None:
                with Session(self.store.engine) as session, session.begin():
                    self._guard_session(session)
                    yield session
            else:
                self._guard_session(supplied)
                yield supplied
        except (ReviewsError, FactsError, AuthFlowError, CatalogStoreError, StorageError,
                ImportServiceError, EvidenceError, IdempotencyError):
            self._rollback_supplied(supplied)
            raise
        except Exception:
            self._rollback_supplied(supplied)
            raise ReviewsError() from None

    def _authorize(self, session, principal, expected_policy):
        self._guard_session(session)
        settings, policy, facts_policy, imports_policy = self._validate()
        if not policy.enabled or not facts_policy.enabled or not imports_policy.enabled:
            raise ReviewsError()
        if settings.admin_assurance_policy != expected_policy:
            raise AuthorizationError(403)
        current = self.fact_service._authorize(session, principal, expected_policy, review=True)
        if current.is_synthetic:
            if self.auth_service.runtime_settings.app_environment != "test":
                raise ReviewsError()
        elif not policy.real_reviews_ready:
            raise ReviewsError()
        return current

    def _fact(self, session, principal, fact_id, expected_policy):
        current = self._authorize(session, principal, expected_policy)
        if type(fact_id) is not UUID:
            raise ReviewsError(404)
        hint = self.fact_service.store.get(session, fact_id, lock=False)
        if hint.is_synthetic != current.is_synthetic:
            raise ReviewsError()
        result = self.fact_service._read(session, current, fact_id, expected_policy,
            expected=(hint.offering_id, hint.offering_version, hint.entry_year))
        row = self.fact_service.store.get(session, fact_id)
        batch = self.fact_service.import_service.store.get(session, row.import_id)
        return current, row, batch, result

    def _snippet(self, session, current, fact):
        if fact.evidence_id is None:
            return None
        return self.fact_service.evidence_service.verify_in_transaction(session, current, fact.evidence_id,
            expected_offering_id=fact.offering_id, expected_offering_version=fact.offering_version,
            expected_entry_year=fact.entry_year)

    def _audit(self, session, current):
        # The ID is an audit trace, not a permission or retention-blocking FK.
        return self.auth_service.store.audit.success(session, "catalog.review", actor=current,
                                                    now=self.auth_service._now())

    def _check_case(self, case, row, decision=None):
        if (case.logical_key_hash != row.logical_key_hash or case.is_synthetic != row.is_synthetic
            or type(case.revision) is not int or not 0 <= case.revision <= 2147483647):
            raise ReviewsError(409)
        if decision is not None and ((decision.case_id, decision.case_revision, decision.logical_key_hash,
            decision.is_synthetic, decision.id) != (case.id, case.revision, case.logical_key_hash,
            case.is_synthetic, case.current_decision_id)):
            raise ReviewsError(409)

    def _final(self, session, current, row, fact, expected_policy, *, case=None, decision=None):
        # This is the last SQL/authorization boundary. T17 re-locks/recomputes
        # raw row, scope, date, evidence, original file and current conflict set,
        # then checks source/file/identity deadlines at one fresh local time.
        final = self.fact_service._verify_fact(session, current, row, expected_policy, review=True,
            expected=(fact.offering_id, fact.offering_version, fact.entry_year))
        settings, policy, _, _ = self._validate()
        if not policy.enabled or settings.admin_assurance_policy != expected_policy:
            raise ReviewsError()
        if fact_fingerprint(final) != fact_fingerprint(fact):
            raise ReviewsError(409)
        now = self.auth_service._now()
        if (case is not None and (utc_time(case.created_at) > now or utc_time(case.updated_at) > now)
            or decision is not None and utc_time(decision.created_at) > now):
            raise ReviewsError(409)
        return final

    def _matches_approval(self, session, case, decision, fact, batch, evidence):
        if (decision.action != "approve" or case.chosen_fact_id != fact.id
            or decision.fact_id != fact.id or decision.reviewer_user_id == batch.actor_user_id
            or decision.fact_sha256 != fact_fingerprint(fact)
            or decision.conflicts_sha256 != conflict_fingerprint(fact.conflicting_ids)):
            return False
        request = self.store.request(session, decision)
        try:
            validate_review(request, fact, evidence)
        except ReviewsError as error:
            if error.status_code in {409, 422}:
                return False
            raise
        return True

    def _history_projection(self, session, current, row, case, expected_policy):
        """Expired proof exposes only an already-bound case, never derivative data."""
        self._check_case(case, row)
        decision = self.store.get_decision(session, case.current_decision_id)
        self._check_case(case, row, decision)
        result = self.store.case_data(case, logical_key_hash=row.logical_key_hash,
                                     is_synthetic=row.is_synthetic, current_approved=False)
        self._audit(session, current)
        self._authorize(session, current, expected_policy)
        now = self.auth_service._now()
        if (utc_time(case.created_at) > now or utc_time(case.updated_at) > now
            or utc_time(decision.created_at) > now):
            raise ReviewsError(409)
        return result

    @audited("catalog.review")
    def decide(self, principal, request: ReviewRequest):
        request = _input(ReviewRequest, request)
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction() as session:
            current, row, batch, fact = self._fact(session, principal, request.fact_id, expected_policy)
            if current.user_id == batch.actor_user_id:
                raise AuthorizationError(403)
            case = self.store.claim_case(session, row, now=self.auth_service._now())
            self._check_case(case, row)
            if case.revision != request.expected_case_revision or fact.version != request.expected_fact_version:
                raise ReviewsError(409)
            evidence = self._snippet(session, current, fact) if request.action == "approve" else None
            validate_review(request, fact, evidence)
            audit = self._audit(session, current)
            decision = self.store.record(session, case, request, fact, reviewer=current,
                                         audit_event_id=audit.id, now=self.auth_service._now())
            self._check_case(case, row, decision)
            result = self.store.decision_data(session, decision, current_approved=request.action == "approve")
            self._final(session, current, row, fact, expected_policy, case=case, decision=decision)
        return result

    @audited("catalog.review")
    def get_case(self, principal, fact_id: UUID):
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction() as session:
            current = self._authorize(session, principal, expected_policy)
            if type(fact_id) is not UUID:
                raise ReviewsError(404)
            hint = self.fact_service.store.get(session, fact_id, lock=False)
            if hint.is_synthetic != current.is_synthetic:
                raise ReviewsError()
            case_hint = self.store.get_case(session, hint.logical_key_hash, lock=False)
            try:
                current, row, batch, fact = self._fact(session, current, fact_id, expected_policy)
            except (FactsError, EvidenceError, StorageError, ImportServiceError, CatalogStoreError) as error:
                if error.status_code != 409 or case_hint is None:
                    raise
                if not session.is_active or not session.in_transaction():
                    raise ReviewsError() from None
                case = self.store.get_case(session, hint.logical_key_hash)
                if case is None:
                    raise ReviewsError(409)
                return self._history_projection(session, current, hint, case, expected_policy)
            case = self.store.get_case(session, row.logical_key_hash)
            approved, decision = False, None
            final_row, final_fact = row, fact
            if case is not None:
                decision = self.store.get_decision(session, case.current_decision_id)
                self._check_case(case, row, decision)
                if case.chosen_fact_id is not None:
                    try:
                        current, final_row, final_batch, final_fact = self._fact(
                            session, current, case.chosen_fact_id, expected_policy)
                    except (FactsError, EvidenceError, StorageError, ImportServiceError, CatalogStoreError) as error:
                        if error.status_code != 409:
                            raise
                        if not session.is_active or not session.in_transaction():
                            raise ReviewsError() from None
                        return self._history_projection(session, current, row, case, expected_policy)
                    if final_row.logical_key_hash != case.logical_key_hash:
                        raise ReviewsError(409)
                    evidence = self._snippet(session, current, final_fact)
                    approved = self._matches_approval(session, case, decision, final_fact, final_batch, evidence)
            result = self.store.case_data(case, logical_key_hash=row.logical_key_hash,
                                         is_synthetic=row.is_synthetic, current_approved=approved)
            self._audit(session, current)
            try:
                self._final(session, current, final_row, final_fact, expected_policy, case=case, decision=decision)
            except (FactsError, EvidenceError, StorageError, ImportServiceError, CatalogStoreError) as error:
                if error.status_code != 409 or case is None:
                    raise
                if not session.is_active or not session.in_transaction():
                    raise ReviewsError() from None
                return self._history_projection(session, current, row, case, expected_policy)
        return result

    @audited("catalog.review")
    def approval_in_transaction(self, session, principal, fact_id: UUID, *,
                                expected_case_revision, expected_decision_id):
        """T19 consumer seam: current proof only; results precede caller commit."""
        with self._transaction(session) as active:
            if (type(fact_id) is not UUID or type(expected_decision_id) is not UUID
                or type(expected_case_revision) is not int or not 1 <= expected_case_revision <= 2147483647):
                raise ReviewsError(422)
            expected_policy = self._validate()[0].admin_assurance_policy
            current, row, batch, fact = self._fact(active, principal, fact_id, expected_policy)
            case = self.store.get_case(active, row.logical_key_hash)
            if (case is None or case.revision != expected_case_revision
                or case.current_decision_id != expected_decision_id or case.chosen_fact_id != fact.id):
                raise ReviewsError(409)
            decision = self.store.get_decision(active, case.current_decision_id)
            self._check_case(case, row, decision)
            evidence = self._snippet(active, current, fact)
            if not self._matches_approval(active, case, decision, fact, batch, evidence):
                raise ReviewsError(409)
            result = self.store.decision_data(active, decision, current_approved=True)
            self._audit(active, current)
            self._final(active, current, row, fact, expected_policy, case=case, decision=decision)
            return result
