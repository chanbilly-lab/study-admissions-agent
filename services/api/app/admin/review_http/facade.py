"""Trusted same-transaction composition, without borrowing a source owner."""

import base64
import json
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import func, select

from ...admissions_catalog.schemas import ScopeKey
from ...audit.context import audited
from ...auth.assurance import check_admin_assurance
from ...auth.authorization import AuthorizationError, Role
from ...auth.config import AuthFlowError
from ...auth.models import AuthSession, AuthUserRole
from ...evidence.schemas import DocumentCreate, SnippetCreate, VersionCreate
from ...evidence.store import utc_time
from ...facts.models import FactCandidate
from ...facts.schemas import FactCreate
from ...facts.store import fingerprint
from ...ingestion.schemas import ParsedRow, ROW_FIELDS
from ...releases.schemas import PublishMember, PublishRequest, ReleasesError, WithdrawalRequest
from ...reviews.schemas import ReviewRequest
from ..imports.models import ImportCandidateRow
from .schemas import (CurrentReleaseData, ImportRowData, ImportRowsData, PublishPrecheckData,
    ReleaseHeadData, ReviewCandidateRef, ReviewCandidatesData, ReviewConflictData, ReviewContextData,
    ReviewDetailData)


def _native(model, value):
    """Strip only the separately validated explicit-confirmation field."""
    type(value).model_validate(value)
    return model.model_validate({name: getattr(value, name) for name in model.model_fields})


def _cursor(value, binding):
    if value is None:
        return None
    try:
        if type(value) is not str or not 1 <= len(value) <= 1024 or not value.isascii():
            raise ValueError
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        data = json.loads(decoded)
        if type(data) is not dict or set(data) != {"binding", "last"} or data["binding"] != fingerprint(binding):
            raise ValueError
        return data["last"]
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ReleasesError(409) from None


def _next(binding, last):
    return base64.urlsafe_b64encode(json.dumps({"binding": fingerprint(binding), "last": last},
        sort_keys=True, separators=(",", ":")).encode("ascii")).decode("ascii").rstrip("=")


class ReviewFacade:
    def __init__(self, admin_facade, evidence_service, fact_service, review_service, release_service):
        self.admin = admin_facade
        self.auth = admin_facade.auth_service
        self.evidence, self.facts, self.reviews, self.releases = (
            evidence_service, fact_service, review_service, release_service)
        self._chain = (admin_facade, self.auth, self.evidence, self.facts, self.reviews, self.releases)
        self._validate()

    def _validate(self):
        from ...evidence.service import EvidenceService
        from ...facts.service import FactService
        from ...reviews.service import ReviewService
        from ...releases.service import ReleaseService
        try:
            self.admin._validate()
            if (self._chain != (self.admin, self.auth, self.evidence, self.facts, self.reviews, self.releases)
                or not isinstance(self.evidence, EvidenceService) or not isinstance(self.facts, FactService)
                or not isinstance(self.reviews, ReviewService) or not isinstance(self.releases, ReleaseService)
                or self.evidence.source_service is not self.admin.source_service
                or self.evidence.storage_service is not self.admin.storage_service
                or self.facts.import_service is not self.admin.import_service
                or self.facts.evidence_service is not self.evidence
                or self.reviews.fact_service is not self.facts or self.releases.review_service is not self.reviews
                or self.releases.idempotency_service is not self.admin.import_service.idempotency_service
                or any(service.auth_service is not self.auth or service.store.engine is not self.auth.store.engine
                    for service in (self.evidence, self.facts, self.reviews, self.releases))):
                raise ValueError
            self.releases._validate()
        except Exception:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    def _policy(self):
        self._validate()
        return self.auth.settings.admin_assurance_policy

    def _audit(self, session, current):
        self.auth.store.audit.success(session, "administrator.action", actor=current, now=self.auth._now())

    def _ready(self, current, capability):
        synthetic = current.is_synthetic and self.admin.settings.app_environment == "test"
        release = self.releases.policy
        if capability == "catalog.withdraw":
            available = release.enabled and ((synthetic and release.allow_test_releases)
                or (not current.is_synthetic and release.real_releases_ready))
        else:
            source, storage = self.admin.source_service.policy, self.admin.storage_service.policy
            imports, evidence, facts, reviews = (self.admin.import_service.policy, self.evidence.policy,
                self.facts.policy, self.reviews.policy)
            available = all(item.enabled for item in (source, storage, imports, evidence, facts, reviews)) and (
                synthetic or (not current.is_synthetic and source.real_sources_ready
                    and bool(source.responsible_user_ids) and storage.real_storage_ready and imports.real_imports_ready
                    and evidence.real_evidence_ready and facts.real_facts_ready and reviews.real_reviews_ready))
            if capability == "catalog.publish":
                idem = self.releases.idempotency_service.policy
                available = available and release.enabled and idem.enabled and (
                    synthetic and release.allow_test_releases or not current.is_synthetic
                    and release.real_releases_ready and idem.real_idempotency_ready)
        if not available:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE")

    def _final(self, session, principal, policy, capability, proofs=(), *, request=None, root=None,
               state=None, check_readiness=True):
        """The last SQL is refresh; all identities and deadlines share one now."""
        current = self.admin.authorizer.check_capability_in_transaction(session, principal, capability)
        role = session.scalar(select(AuthUserRole).where(AuthUserRole.user_id == current.user_id,
            AuthUserRole.role == "data_admin").with_for_update().execution_options(populate_existing=True))
        row = session.get(AuthSession, current.session_id)
        fresh, stored = self.admin.authorizer._refresh(current, session)
        self._validate()
        settings = self.auth._validate()
        now = self.auth._now()
        if row is None or row.revoked_at is not None or not utc_time(row.created_at) <= now < stored.expires_at:
            raise AuthorizationError(401)
        if (settings.admin_assurance_policy != policy or Role.data_admin not in fresh.roles
            or role is None or role.revoked_at is not None or utc_time(role.granted_at) > now
            or role.expires_at is not None and utc_time(role.expires_at) <= now
            or stored.verified_issuer != settings.provider.issuer or stored.verified_client_id != settings.provider.client_id):
            raise AuthorizationError(403)
        check_admin_assurance(stored.assurance, issuer=stored.verified_issuer, client_id=stored.verified_client_id,
                              policy=policy, now=now)
        if check_readiness:
            self._ready(fresh, capability)
        self.releases._deadline(proofs, request, root, state, now=now)
        return now

    def _proof(self, session, fact):
        batch = self.admin.import_service.store.get(session, fact.import_id)
        source = self.admin.source_service.store.get_source_version(session, batch.source_id)
        file_row = self.admin.storage_service.store.get(session, batch.file_id)
        file = self.admin.storage_service.store.data(file_row)
        if (source.version != batch.source_version or source.dataset_id != batch.dataset_id
            or file.sha256 != batch.file_sha256 or file.status != "quarantined"):
            raise ReleasesError(409)
        times = [batch.created_at, fact.created_at]
        if fact.evidence_id is not None:
            snippet = self.evidence.store.get_snippet(session, fact.evidence_id)
            document = self.evidence.store.get_document(session, snippet.document_id)
            version = self.evidence.store.get_version(session, document.id, snippet.document_version)
            times.extend((snippet.created_at, document.created_at, version.created_at))
        # T12 has no creation timestamp. T17 already revalidates its locked
        # native date, exact scope and fingerprint; do not invent such a field.
        return SimpleNamespace(source=source, file=file, created_times=tuple(times))

    @audited("administrator.action")
    def context(self, principal):
        policy = self._policy()
        with self.releases._transaction() as session:
            current = self.admin.authorizer.check_capability_in_transaction(session, principal, "catalog.review")
            synthetic = current.is_synthetic and self.admin.settings.app_environment == "test"
            source = self.admin.source_service.policy
            storage = self.admin.storage_service.policy
            imports = self.admin.import_service.policy
            idem = self.admin.import_service.idempotency_service.policy
            base = (source.enabled and storage.enabled and storage.source_retention_days is not None
                and imports.enabled and idem.enabled and (synthetic or (not current.is_synthetic
                    and source.real_sources_ready and bool(source.responsible_user_ids) and storage.real_storage_ready
                    and imports.real_imports_ready and idem.real_idempotency_ready)))
            prepared = bool(base and self.evidence.policy.enabled and self.facts.policy.enabled
                and (synthetic or self.evidence.policy.real_evidence_ready and self.facts.policy.real_facts_ready))
            review = bool(prepared and self.reviews.policy.enabled and (synthetic or self.reviews.policy.real_reviews_ready))
            release = bool(self.releases.policy.enabled and (synthetic and self.releases.policy.allow_test_releases
                or not current.is_synthetic and self.releases.policy.real_releases_ready))
            own_prepare = prepared and (synthetic or current.user_id in source.responsible_user_ids)
            self._audit(session, current)
            self._final(session, current, policy, "catalog.review", check_readiness=False)
            result = ReviewContextData(schema_version="v2.t22", can_prepare=bool(own_prepare), can_review=review,
                can_publish=bool(review and release), can_withdraw=release, is_synthetic=current.is_synthetic)
        return result

    @audited("catalog.import")
    def import_rows(self, principal, import_id, limit=20, cursor=None):
        if type(import_id) is not UUID or type(limit) is not int or not 1 <= limit <= 20:
            raise ReleasesError(422)
        policy = self._policy()
        imports = self.admin.import_service
        with self.releases._transaction() as session:
            current = imports._authorize(session, principal, policy)
            hint = imports.store.get(session, import_id, lock=False)
            request = imports._request_for_batch(hint)
            current, _ = imports._current_file(session, current, request, policy)
            batch = imports.store.get(session, import_id)
            if batch.status != "staged" or imports._request_for_batch(batch) != request:
                raise ReleasesError(409)
            binding = {"actor": str(current.user_id), "import": str(batch.id), "hash": batch.file_sha256,
                       "limit": limit, "version": batch.version}
            last = _cursor(cursor, binding)
            if last is not None and (type(last) is not int or not 0 < last <= 201):
                raise ReleasesError(409)
            query = select(ImportCandidateRow).where(ImportCandidateRow.import_id == batch.id)
            if last is not None:
                query = query.where(ImportCandidateRow.row_number > last)
            raw = session.scalars(query.order_by(ImportCandidateRow.row_number).limit(limit + 1)
                .with_for_update().execution_options(populate_existing=True)).all()
            rows = tuple(ImportRowData(row_id=row.id,
                row=ParsedRow(**{name: getattr(row, name) for name in (*ROW_FIELDS, "row_number")})) for row in raw[:limit])
            result = ImportRowsData(import_id=batch.id, dataset_id=batch.dataset_id, source_id=batch.source_id,
                source_version=batch.source_version, file_id=batch.file_id, file_sha256=batch.file_sha256,
                format=batch.format, is_synthetic=batch.is_synthetic, total_rows=batch.total_rows, rows=rows,
                next_cursor=_next(binding, rows[-1].row.row_number) if len(raw) > limit else None)
            self._audit(session, current)
            imports._verify_batch(session, current, batch, request, policy)
        return result

    def create_document(self, principal, request):
        self._validate()
        return self.evidence.create_document(principal, _native(DocumentCreate, request))

    def create_version(self, principal, request):
        self._validate()
        return self.evidence.create_version(principal, _native(VersionCreate, request))

    def create_snippet(self, principal, request):
        self._validate()
        return self.evidence.create_snippet(principal, _native(SnippetCreate, request))

    def create_fact(self, principal, request):
        self._validate()
        return self.facts.create_fact(principal, _native(FactCreate, request))

    def decide(self, principal, request):
        self._validate()
        return self.reviews.decide(principal, _native(ReviewRequest, request))

    @audited("catalog.review")
    def candidates(self, principal, dataset_id, entry_year, limit=20, cursor=None):
        if (type(dataset_id) is not UUID or type(entry_year) is not int or not 1 <= entry_year <= 9999
            or type(limit) is not int or not 1 <= limit <= 100):
            raise ReleasesError(422)
        policy = self._policy()
        with self.releases._transaction() as session:
            current = self.reviews._authorize(session, principal, policy)
            dataset = self.releases.store.dataset(session, dataset_id)
            if dataset.is_synthetic != current.is_synthetic:
                raise ReleasesError(409)
            filters = (FactCandidate.dataset_id == dataset_id, FactCandidate.entry_year == entry_year)
            count = session.scalar(select(func.count()).select_from(FactCandidate).where(*filters))
            binding = {"actor": str(current.user_id), "dataset": str(dataset_id), "year": entry_year,
                       "revision": dataset.revision, "count": count, "limit": limit}
            last = _cursor(cursor, binding)
            if last is not None:
                try:
                    identifier = UUID(last)
                    if str(identifier) != last:
                        raise ValueError
                except (ValueError, TypeError, AttributeError):
                    raise ReleasesError(409) from None
            query = select(FactCandidate.id).where(*filters)
            if last is not None:
                query = query.where(FactCandidate.id > identifier)
            ids = session.scalars(query.order_by(FactCandidate.id).limit(limit + 1)).all()
            facts = tuple(self.facts._read(session, current, identifier, policy) for identifier in ids[:limit])
            proofs = tuple(self._proof(session, fact) for fact in facts)
            result = ReviewCandidatesData(dataset_id=dataset_id, entry_year=entry_year,
                dataset_revision=dataset.revision, items=tuple(ReviewCandidateRef(fact_id=fact.id, version=fact.version,
                    dataset_id=fact.dataset_id, offering_id=fact.offering_id, offering_version=fact.offering_version,
                    entry_year=fact.entry_year, state=fact.state, is_synthetic=fact.is_synthetic,
                    created_at=fact.created_at) for fact in facts),
                next_cursor=_next(binding, str(facts[-1].id)) if len(ids) > limit else None)
            self._audit(session, current)
            self._final(session, current, policy, "catalog.review", proofs)
        return result

    @audited("catalog.review")
    def detail(self, principal, fact_id):
        policy = self._policy()
        with self.releases._transaction() as session:
            current, row, batch, fact = self.reviews._fact(session, principal, fact_id, policy)
            evidence = self.reviews._snippet(session, current, fact)
            scope = self.evidence.store.scope(session, dataset_id=fact.dataset_id, offering_id=fact.offering_id,
                offering_version=fact.offering_version, entry_year=fact.entry_year, is_synthetic=fact.is_synthetic)
            prepared = {fact.id: (row, batch, fact, evidence)}
            for identifier in fact.conflicting_ids:
                _, peer, peer_batch, peer_fact = self.reviews._fact(session, current, identifier, policy)
                if peer.logical_key_hash != row.logical_key_hash:
                    raise ReleasesError(409)
                prepared[identifier] = (peer, peer_batch, peer_fact, self.reviews._snippet(session, current, peer_fact))
            case = self.reviews.store.get_case(session, row.logical_key_hash)
            approved, decision = False, None
            if case is not None:
                decision = self.reviews.store.get_decision(session, case.current_decision_id)
                self.reviews._check_case(case, row, decision)
                if case.chosen_fact_id is not None:
                    if case.chosen_fact_id not in prepared:
                        _, selected, selected_batch, selected_fact = self.reviews._fact(session, current, case.chosen_fact_id, policy)
                        if selected.logical_key_hash != row.logical_key_hash:
                            raise ReleasesError(409)
                        prepared[selected_fact.id] = (selected, selected_batch, selected_fact,
                            self.reviews._snippet(session, current, selected_fact))
                    _, chosen_batch, chosen, chosen_snippet = prepared[case.chosen_fact_id]
                    approved = self.reviews._matches_approval(session, case, decision, chosen, chosen_batch, chosen_snippet)
            case_data = self.reviews.store.case_data(case, logical_key_hash=row.logical_key_hash,
                is_synthetic=row.is_synthetic, current_approved=approved)
            gaps = []
            if evidence is None:
                gaps.append("MISSING_EVIDENCE")
            if any(isinstance(getattr(scope, name), ScopeKey) and getattr(scope, name).status == "unknown"
                for name in type(scope).model_fields):
                gaps.append("INCOMPLETE_SCOPE")
            if fact.footnote_state == "unknown":
                gaps.append("UNKNOWN_FOOTNOTE")
            if fact.value_text is None:
                gaps.append("MISSING_VALUE")
            if fact.fact_type == "statistic" and row.payload["state"] == "draft":
                gaps.append("INCOMPLETE_STATISTICS")
            if fact.fact_type == "date" and (fact.date_resolution is None
                or fact.date_resolution.conversion_status not in {"unique", "date_only"}):
                gaps.append("UNRESOLVED_DATE")
            if evidence is None:
                gaps.append("UNRESOLVED_LOCATOR")
            if row.payload["state"] == "draft":
                gaps.append("BASE_DRAFT")
            if fact.conflicting_ids:
                gaps.append("CURRENT_CONFLICTS")
            if current.user_id == batch.actor_user_id:
                gaps.append("SELF_REVIEW_FORBIDDEN")
            summaries = tuple(ReviewConflictData(fact_id=prepared[identifier][2].id,
                version=prepared[identifier][2].version, value_kind=prepared[identifier][2].value_kind,
                value_text=prepared[identifier][2].value_text, normalized_value=prepared[identifier][2].normalized_value,
                unit_text=prepared[identifier][2].unit, footnote_state=prepared[identifier][2].footnote_state,
                footnote_text=prepared[identifier][2].footnote_text, classification=prepared[identifier][2].classification,
                evidence_id=prepared[identifier][2].evidence_id, state=prepared[identifier][2].state)
                for identifier in fact.conflicting_ids)
            result = ReviewDetailData(fact=fact, case=case_data, evidence=evidence, scope=scope,
                                      gaps=tuple(gaps), conflicts=summaries)
            proofs = [self._proof(session, item[2]) for item in prepared.values()]
            if case is not None:
                proofs.append(SimpleNamespace(source=proofs[0].source, file=proofs[0].file,
                    created_times=(case.created_at, case.updated_at, decision.created_at)))
            self._audit(session, current)
            self._final(session, current, policy, "catalog.review", tuple(proofs))
        return result

    @audited("catalog.publish")
    def precheck(self, principal, request):
        request = _native(PublishRequest, request)
        policy = self._policy()
        with self.releases._transaction() as session:
            current = self.releases._authorize(session, principal, policy, "catalog.publish")
            dataset = self.releases.store.dataset(session, request.dataset_id)
            self.releases._mode(current, dataset, request.kind)
            if dataset.revision != request.expected_dataset_revision:
                raise ReleasesError(409)
            state = self.releases.store.current(session, dataset.id, request.entry_year)
            if request.replaces_release_id is None:
                if state is not None:
                    raise ReleasesError(409)
            elif (state is None or state.release_id != request.replaces_release_id
                or state.revision != request.expected_replaced_state_revision):
                raise ReleasesError(409)
            proofs = self.releases._proofs(session, current, request, policy)
            self._audit(session, current)
            now = self._final(session, current, policy, "catalog.publish", proofs, request=request)
            result = PublishPrecheckData(status="precheck_passed", request_sha256=fingerprint(request.model_dump(mode="json")),
                dataset_revision=dataset.revision, member_count=len(proofs), checked_at=now, is_synthetic=current.is_synthetic)
        return result

    def publish(self, principal, request, key):
        self._validate()
        return self.releases.publish(principal, _native(PublishRequest, request), key)

    @audited("catalog.withdraw")
    def current_release(self, principal, dataset_id, entry_year):
        if type(dataset_id) is not UUID or type(entry_year) is not int or not 1 <= entry_year <= 9999:
            raise ReleasesError(422)
        policy = self._policy()
        with self.releases._transaction() as session:
            current = self.releases._authorize(session, principal, policy, "catalog.withdraw")
            dataset = self.releases.store.dataset(session, dataset_id)
            state = self.releases.store.current(session, dataset_id, entry_year)
            root, head = None, None
            if state is not None:
                root = self.releases.store.get(session, state.release_id)
                self.releases._mode(current, dataset, root.kind)
                head = ReleaseHeadData(release_id=root.id, version=root.version, state=state.status,
                    state_revision=state.revision, kind=root.kind, is_synthetic=root.is_synthetic,
                    valid_from=utc_time(root.valid_from), valid_until=utc_time(root.valid_until),
                    content_sha256=root.content_sha256, requirements_version=root.requirements_version,
                    member_count=len(self.releases.store.members(session, root.id)),
                    replaces_release_id=root.replaces_release_id, replaced_by_release_id=state.replaced_by_release_id)
            elif dataset.is_synthetic != current.is_synthetic:
                raise ReleasesError(409)
            result = CurrentReleaseData(dataset_id=dataset_id, entry_year=entry_year,
                                        dataset_revision=dataset.revision, release=head)
            self._audit(session, current)
            self._final(session, current, policy, "catalog.withdraw", root=root, state=state)
        return result

    @audited("catalog.review")
    def get_release(self, principal, release_id):
        policy = self._policy()
        with self.releases._transaction() as session:
            current = self.releases._authorize(session, principal, policy, "catalog.review")
            hint = self.releases.store.get(session, release_id, lock=False)
            dataset = self.releases.store.dataset(session, hint.dataset_id)
            root = self.releases.store.get(session, release_id)
            result = self.releases.store.result(session, root)
            previous_revision = None
            if result.replaces_release_id is not None:
                previous_revision = self.releases.store.state(session, result.replaces_release_id).revision - 1
            request = PublishRequest(dataset_id=result.dataset_id, expected_dataset_revision=dataset.revision,
                entry_year=result.entry_year, kind=result.kind, valid_from=result.valid_from, valid_until=result.valid_until,
                members=tuple(PublishMember(fact_id=member.fact_id, expected_case_revision=member.case_revision,
                    expected_decision_id=member.decision_id, public_evidence=member.public_evidence) for member in result.members),
                replaces_release_id=result.replaces_release_id, expected_replaced_state_revision=previous_revision)
            proofs, state = self.releases._verify_release(session, current, root, request, policy)
            self._audit(session, current)
            self._final(session, current, policy, "catalog.review", proofs, request=request, root=root, state=state)
        return result

    def withdraw(self, principal, release_id, request):
        self._validate()
        type(request).model_validate(request)
        return self.releases.withdraw(principal, WithdrawalRequest(release_id=release_id,
            expected_state_revision=request.expected_state_revision, reason_code=request.reason_code))
