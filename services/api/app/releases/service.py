"""Atomic facts-only snapshots; no public reader, rules compiler or consumer."""

from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..admissions_catalog.store import CatalogStoreError
from ..audit.context import audited
from ..auth.assurance import check_admin_assurance
from ..auth.authorization import Authorizer, AuthorizationError, Role
from ..auth.config import AuthFlowError
from ..auth.models import AuthSession, AuthUserRole
from ..evidence.schemas import EvidenceError
from ..evidence.store import scope_hash, utc_time
from ..facts.schemas import FactsError
from ..facts.store import fingerprint
from ..idempotency.schemas import IdempotencyError, ResourceReceipt
from ..idempotency.service import IdempotencyService
from ..ingestion.schemas import ImportServiceError
from ..reviews.schemas import ReviewsError
from ..reviews.service import ReviewService
from ..storage.schemas import StorageError, StorageNamespace
from .models import CatalogRelease, CatalogReleaseMember, CatalogReleaseState, ChangeEvent, OutboxEvent
from .schemas import PublishRequest, ReleaseMemberData, ReleasePolicy, ReleasesError, WithdrawalRequest
from .store import ReleasesStore
from .validation import release_content_hash, validate_release


_DOMAIN_ERRORS = (ReleasesError, ReviewsError, FactsError, EvidenceError, CatalogStoreError,
                  StorageError, ImportServiceError)


def _input(model, value):
    try:
        return model.model_validate(value)
    except (ValidationError, ValueError, TypeError, OverflowError):
        raise ReleasesError(422) from None


@dataclass(frozen=True)
class _MemberProof:
    member: ReleaseMemberData
    snapshot: dict
    source: object
    file: object
    created_times: tuple


class ReleaseService:
    def __init__(self, review_service: ReviewService, idempotency_service: IdempotencyService,
                 store: ReleasesStore, policy: ReleasePolicy = ReleasePolicy()):
        self.review_service, self.idempotency_service, self.store = review_service, idempotency_service, store
        self.auth_service = getattr(review_service, "auth_service", None)
        try:
            self.policy = ReleasePolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise ReleasesError() from None
        self._initial_policy = self.policy
        self._validate()
        self.authorizer = Authorizer(self.auth_service)

    def _validate(self):
        if (not isinstance(self.review_service, ReviewService)
            or not isinstance(self.idempotency_service, IdempotencyService)
            or not isinstance(self.store, ReleasesStore)
            or self.auth_service is not self.review_service.auth_service
            or self.idempotency_service.auth_service is not self.auth_service
            or self.review_service.store.engine is not self.store.engine
            or self.idempotency_service.store.engine is not self.store.engine):
            raise ReleasesError()
        settings = self.auth_service._validate()
        self.review_service._validate()
        self.idempotency_service._validate()
        try:
            policy = ReleasePolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise ReleasesError() from None
        if policy != self._initial_policy:
            raise ReleasesError()
        return settings, policy

    def _guard_session(self, session):
        self.review_service._guard_session(session)
        self.idempotency_service._guard_session(session)
        try:
            for mapper in (CatalogRelease, CatalogReleaseMember, CatalogReleaseState, ChangeEvent, OutboxEvent):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise ReleasesError()
        except ReleasesError:
            raise
        except Exception:
            raise ReleasesError() from None

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
        except (*_DOMAIN_ERRORS, AuthFlowError, IdempotencyError):
            self._rollback_supplied(supplied)
            raise
        except Exception:
            self._rollback_supplied(supplied)
            raise ReleasesError() from None

    def _authorize(self, session, principal, expected_policy, capability):
        self._guard_session(session)
        settings, policy = self._validate()
        if not policy.enabled:
            raise ReleasesError()
        if settings.admin_assurance_policy != expected_policy:
            raise AuthorizationError(403)
        current = self.authorizer.check_capability_in_transaction(session, principal, capability)
        runtime = self.auth_service.runtime_settings
        if current.is_synthetic:
            if runtime.app_environment != "test" or not policy.allow_test_releases:
                raise ReleasesError()
        elif not policy.real_releases_ready:
            raise ReleasesError()
        return current

    def _mode(self, current, dataset, kind):
        _, policy = self._validate()
        if dataset.is_synthetic != current.is_synthetic:
            raise ReleasesError()
        if kind == "test_fixture":
            if (not dataset.is_synthetic or dataset.data_mode != "demo"
                or not dataset.reference_key.startswith("DEMO_")
                or self.auth_service.runtime_settings.app_environment != "test"
                or not policy.allow_test_releases):
                raise ReleasesError()
        elif kind == "formal":
            if dataset.is_synthetic or current.is_synthetic or dataset.reference_key.upper().startswith("DEMO_"):
                raise ReleasesError(422)
            if dataset.data_mode != "verified" or not policy.real_releases_ready:
                raise ReleasesError()
        else:
            raise ReleasesError(422)

    def _audit(self, session, current, action, root=None):
        return self.auth_service.store.audit.success(session, action, actor=current,
            object_type="catalog_release" if root is not None else None,
            object_id=root.id if root is not None else None,
            object_version=1 if root is not None else None, now=self.auth_service._now())

    def _member_proof(self, session, current, requested, request, expected_policy):
        reviews = self.review_service
        decision = reviews.approval_in_transaction(session, current, requested.fact_id,
            expected_case_revision=requested.expected_case_revision,
            expected_decision_id=requested.expected_decision_id)
        facts = reviews.fact_service
        fact = facts._read(session, current, requested.fact_id, expected_policy)
        fact_row = facts.store.get(session, fact.id)
        batch = facts.import_service.store.get(session, fact.import_id)
        if (fact.dataset_id != request.dataset_id or fact.entry_year != request.entry_year
            or fact.is_synthetic != current.is_synthetic or fact.evidence_id is None
            or not decision.current_approved):
            raise ReleasesError(409)
        evidence = facts.evidence_service.verify_in_transaction(session, current, fact.evidence_id,
            expected_offering_id=fact.offering_id, expected_offering_version=fact.offering_version,
            expected_entry_year=fact.entry_year)
        document = facts.evidence_service.store.get_document(session, evidence.document_id)
        document_version = facts.evidence_service.store.get_version(session, document.id, evidence.document_version)
        source = facts.import_service.source_service.store.get_source_version(session, batch.source_id)
        file_row = facts.import_service.storage_service.store.get(session, batch.file_id)
        file = facts.import_service.storage_service.store.data(file_row)
        if ((batch.dataset_id, batch.source_id, batch.source_version, batch.is_synthetic) !=
            (request.dataset_id, source.source_id, source.version, current.is_synthetic)
            or (document.dataset_id, document.source_id, document.source_version, document.is_synthetic) !=
            (batch.dataset_id, batch.source_id, batch.source_version, batch.is_synthetic)
            or (document_version.file_id, document_version.document_sha256, document_version.size_bytes) !=
            (batch.file_id, batch.file_sha256, batch.file_size)
            or (file_row.dataset_id, file_row.source_id, file_row.source_version, file.is_synthetic) !=
            (batch.dataset_id, batch.source_id, batch.source_version, batch.is_synthetic)
            or file.namespace != StorageNamespace.source_quarantine or file.status != "quarantined"
            or file.sha256 != batch.file_sha256 or file.size_bytes != batch.file_size
            or evidence.document_sha256 != batch.file_sha256):
            raise ReleasesError(409)
        if (source.publication_permission != "granted" or source.license_basis is None
            or source.permission_record_reference is None or source.permission_reviewed_at is None):
            raise ReleasesError(409)
        case = reviews.store.get_case(session, fact_row.logical_key_hash)
        raw_decision = reviews.store.get_decision(session, decision.decision_id)
        if case is None:
            raise ReleasesError(409)
        member = ReleaseMemberData(fact_id=fact.id, logical_key_hash=fact_row.logical_key_hash,
            decision_id=decision.decision_id, case_revision=decision.case_revision,
            offering_id=fact.offering_id, offering_version=fact.offering_version, entry_year=fact.entry_year,
            source_id=source.source_id, source_version=source.version, evidence_id=evidence.id,
            fact_sha256=fingerprint(fact.model_dump(mode="json")), scope_sha256=scope_hash(evidence.scope),
            evidence_sha256=fingerprint(evidence.model_dump(mode="json")),
            source_sha256=fingerprint(source.model_dump(mode="json")), file_sha256=file.sha256,
            public_evidence=requested.public_evidence)
        proof = _MemberProof(member=member, source=source, file=file,
            snapshot={"fact": fact.model_dump(mode="json"), "evidence": evidence.model_dump(mode="json"),
                      "file_id": file.id, "file_metadata_sha256": fingerprint(file.model_dump(mode="json"))},
            created_times=(batch.created_at, fact.created_at, document.created_at, document_version.created_at,
                           evidence.created_at, case.created_at, case.updated_at, raw_decision.created_at))
        self._deadline((proof,), request)
        return proof

    def _proofs(self, session, current, request, expected_policy):
        proofs = tuple(self._member_proof(session, current, member, request, expected_policy)
                       for member in request.members)
        validate_release(request, tuple(proof.member for proof in proofs), is_synthetic=current.is_synthetic)
        return proofs

    def _final_authority(self, session, current, expected_policy, capability):
        self._authorize(session, current, expected_policy, capability)
        # Keep strong references to the locked rows while the last refresh reads
        # them again. Its SQL is the final I/O boundary for this operation.
        role = session.scalar(select(AuthUserRole).where(AuthUserRole.user_id == current.user_id,
            AuthUserRole.role == "data_admin").with_for_update().execution_options(populate_existing=True))
        session_row = session.get(AuthSession, current.session_id)
        fresh, stored = self.authorizer._refresh(current, session)
        settings, policy = self._validate()
        now = self.auth_service._now()
        if (session_row is None or session_row.revoked_at is not None
            or not utc_time(session_row.created_at) <= now < stored.expires_at):
            raise AuthorizationError(401)
        if (not policy.enabled or settings.admin_assurance_policy != expected_policy
            or Role.data_admin not in fresh.roles or role is None or role.revoked_at is not None
            or utc_time(role.granted_at) > now
            or (role.expires_at is not None and utc_time(role.expires_at) <= now)
            or stored.verified_issuer != settings.provider.issuer
            or stored.verified_client_id != settings.provider.client_id):
            raise AuthorizationError(403)
        check_admin_assurance(stored.assurance, issuer=stored.verified_issuer,
            client_id=stored.verified_client_id, policy=expected_policy, now=now)
        return now

    def _deadline(self, proofs, request=None, root=None, state=None, *, now=None):
        # All involved SQL locks and the last authorization query have completed.
        # One fresh clock applies to EVERY member; no SQL follows this boundary.
        now = self.auth_service._now() if now is None else now
        if request is not None and not request.valid_from <= now < request.valid_until:
            raise ReleasesError(409)
        for proof in proofs:
            if (not proof.source.created_at <= now < proof.source.recheck_due_at
                or proof.source.permission_reviewed_at is None or proof.source.permission_reviewed_at > now
                or not proof.file.created_at <= now < proof.file.expires_at
                or any(utc_time(time) > now for time in proof.created_times)):
                raise ReleasesError(409)
        if ((root is not None and utc_time(root.published_at) > now)
            or (state is not None and utc_time(state.updated_at) > now)):
            raise ReleasesError(409)

    def _replacement_replay(self, session, root, request):
        if root.replaces_release_id != request.replaces_release_id:
            raise ReleasesError(409)
        if request.replaces_release_id is not None:
            previous = self.store.get(session, request.replaces_release_id)
            state = self.store.state(session, previous.id)
            if ((previous.dataset_id, previous.entry_year, previous.is_synthetic) !=
                (root.dataset_id, root.entry_year, root.is_synthetic)
                or state.status != "replaced" or state.replaced_by_release_id != root.id
                or state.revision != request.expected_replaced_state_revision + 1):
                raise ReleasesError(409)

    def _verify_release(self, session, current, root, request, expected_policy):
        dataset = self.store.dataset(session, request.dataset_id)
        self._mode(current, dataset, request.kind)
        state = self.store.state(session, root.id)
        result = self.store.result(session, root)
        if ((root.dataset_id, root.entry_year, root.kind, root.is_synthetic) !=
            (request.dataset_id, request.entry_year, request.kind, current.is_synthetic)
            or state.status != "published"):
            raise ReleasesError(409)
        self._replacement_replay(session, root, request)
        proofs = self._proofs(session, current, request, expected_policy)
        if (result.members != tuple(proof.member for proof in proofs)
            or root.content_sha256 != release_content_hash(request, result.members)):
            raise ReleasesError(409)
        stored_members = self.store.members(session, root.id)
        for stored, proof in zip(stored_members, proofs):
            if (stored.file_id != proof.file.id
                or stored.file_metadata_sha256 != proof.snapshot["file_metadata_sha256"]
                or stored.snapshot != {"fact": proof.snapshot["fact"], "evidence": proof.snapshot["evidence"]}):
                raise ReleasesError(409)
        return proofs, state

    @audited("catalog.publish")
    def publish(self, principal, request: PublishRequest, key: SecretStr, *, session=None):
        with self._transaction(session) as active:
            request = _input(PublishRequest, request)
            expected_policy = self._validate()[0].admin_assurance_policy
            current = self._authorize(active, principal, expected_policy, "catalog.publish")
            dataset = self.store.dataset(active, request.dataset_id)
            self._mode(current, dataset, request.kind)
            slot = {"error": None, "natural_replay": False}

            def protected(callback):
                def run(*args):
                    try:
                        return callback(*args)
                    except _DOMAIN_ERRORS as error:
                        slot["error"] = error
                        raise
                return run

            @protected
            def perform(work, actor):
                proofs = self._proofs(work, actor, request, expected_policy)
                members = tuple(proof.member for proof in proofs)
                content = release_content_hash(request, members)
                existing = self.store.natural(work, content)
                if existing is not None:
                    self._verify_release(work, actor, existing, request, expected_policy)
                    slot["natural_replay"] = True
                    return ResourceReceipt(kind="catalog_release", resource_id=existing.id, version=1)
                audit = self._audit(work, actor, "catalog.publish")
                root = self.store.create(work, request, members,
                    snapshots=tuple(proof.snapshot for proof in proofs), actor=actor,
                    audit_event_id=audit.id, now=self.auth_service._now())
                return ResourceReceipt(kind="catalog_release", resource_id=root.id, version=1)

            @protected
            def verify(work, actor, receipt):
                root = self.store.get(work, receipt.resource_id)
                self._verify_release(work, actor, root, request, expected_policy)
                return True

            try:
                receipt = self.idempotency_service.execute(current, "catalog.publish", key,
                    request.model_dump(mode="json"), perform=perform, verify_resource=verify, session=active)
            except (AuthFlowError, IdempotencyError):
                if slot["error"] is not None:
                    raise slot["error"] from None
                raise
            root = self.store.get(active, receipt.resource.resource_id)
            proofs, state = self._verify_release(active, current, root, request, expected_policy)
            result = self.store.result(active, root, replayed=receipt.replayed or slot["natural_replay"])
            now = self._final_authority(active, current, expected_policy, "catalog.publish")
            self._deadline(proofs, request, root, state, now=now)
        return result

    @audited("catalog.withdraw")
    def withdraw(self, principal, request: WithdrawalRequest, *, session=None):
        with self._transaction(session) as active:
            request = _input(WithdrawalRequest, request)
            expected_policy = self._validate()[0].admin_assurance_policy
            current = self._authorize(active, principal, expected_policy, "catalog.withdraw")
            hint = self.store.get(active, request.release_id, lock=False)
            dataset = self.store.dataset(active, hint.dataset_id)
            self._mode(current, dataset, hint.kind)
            root = self.store.get(active, hint.id)
            audit = self._audit(active, current, "catalog.withdraw", root)
            state = self.store.withdraw(active, root, request, actor=current,
                audit_event_id=audit.id, now=self.auth_service._now())
            result = self.store.result(active, root)
            now = self._final_authority(active, current, expected_policy, "catalog.withdraw")
            self._deadline((), root=root, state=state, now=now)
        return result

    @audited("catalog.review")
    def get_release(self, principal, release_id: UUID, *, session=None):
        with self._transaction(session) as active:
            if type(release_id) is not UUID:
                raise ReleasesError(404)
            expected_policy = self._validate()[0].admin_assurance_policy
            current = self._authorize(active, principal, expected_policy, "catalog.review")
            hint = self.store.get(active, release_id, lock=False)
            dataset = self.store.dataset(active, hint.dataset_id)
            self._mode(current, dataset, hint.kind)
            root = self.store.get(active, hint.id)
            state = self.store.state(active, root.id)
            result = self.store.result(active, root)
            self._audit(active, current, "catalog.review", root)
            now = self._final_authority(active, current, expected_policy, "catalog.review")
            self._deadline((), root=root, state=state, now=now)
        return result
