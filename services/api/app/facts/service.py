"""Strong-admin typed derivatives; no raw reads, approval or executable rules."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..admin.imports.models import ImportBatch, ImportCandidateRow, ImportRowError
from ..admin.imports.service import ImportService
from ..admin.sources.models import CatalogSource, CatalogSourceVersion
from ..admissions_catalog.date_models import CatalogDateEvent
from ..admissions_catalog.date_store import DateEventStore
from ..admissions_catalog.models import (AdmissionOffering, AdmissionOfferingVersion, CatalogDataset,
                                        CatalogInstitution, CatalogProgram)
from ..admissions_catalog.store import CatalogStoreError
from ..audit.context import audited
from ..audit.models import AuditEvent
from ..auth.authorization import Authorizer, AuthorizationError
from ..auth.config import AuthFlowError
from ..auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from ..auth.service import AuthService
from ..evidence.models import Document, DocumentVersion, EvidenceSnippet
from ..evidence.schemas import EvidenceError
from ..evidence.service import EvidenceService
from ..evidence.store import scope_hash, utc_time
from ..idempotency.models import IdempotencyRecord
from ..idempotency.schemas import IdempotencyError
from ..ingestion.schemas import ImportServiceError, ParsedRow, PARSER_SCHEMA_VERSION, ROW_FIELDS
from ..privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from ..storage.models import StorageObject
from ..storage.schemas import StorageError
from .models import FactCandidate, FactConflict
from .schemas import (DateResolutionSnapshot, FactCreate, FactPolicy, FactsError, TypedCandidate)
from .store import FactsStore, _input, fingerprint
from .typing import type_candidate


class FactService:
    def __init__(self, import_service: ImportService, evidence_service: EvidenceService,
                 store: FactsStore, policy: FactPolicy = FactPolicy()):
        self.import_service, self.evidence_service, self.store = import_service, evidence_service, store
        self.auth_service = getattr(import_service, "auth_service", None)
        try:
            self.policy = FactPolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise FactsError() from None
        self._initial_policy = self.policy
        self._validate()
        self.authorizer = Authorizer(self.auth_service)
        self.date_store = DateEventStore(store.engine)

    def _validate(self):
        if (not isinstance(self.import_service, ImportService) or not isinstance(self.evidence_service, EvidenceService)
            or not isinstance(self.store, FactsStore) or not isinstance(self.auth_service, AuthService)
            or self.evidence_service.auth_service is not self.auth_service
            or self.evidence_service.source_service is not self.import_service.source_service
            or self.evidence_service.storage_service is not self.import_service.storage_service
            or any(service.store.engine is not self.store.engine for service in
                   (self.import_service, self.evidence_service, self.auth_service))):
            raise FactsError()
        settings, imports_policy = self.import_service._validate()
        self.evidence_service._validate()
        try:
            policy = FactPolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise FactsError() from None
        if policy != self._initial_policy:
            raise FactsError()
        return settings, policy, imports_policy

    def _guard_session(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise FactsError()
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                           PrivacyNoticeVersion, PrivacyAdmissionRecord, AuditEvent, CatalogDataset,
                           CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion,
                           CatalogDateEvent, CatalogSource, CatalogSourceVersion, StorageObject,
                           IdempotencyRecord, ImportBatch, ImportCandidateRow, ImportRowError,
                           Document, DocumentVersion, EvidenceSnippet, FactCandidate, FactConflict):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise FactsError()
        except FactsError:
            raise
        except Exception:
            raise FactsError() from None

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
        except (FactsError, AuthFlowError, CatalogStoreError, StorageError, ImportServiceError,
                EvidenceError, IdempotencyError):
            self._rollback_supplied(supplied)
            raise
        except Exception:
            self._rollback_supplied(supplied)
            raise FactsError() from None

    def _rollback_supplied(self, session):
        # Only the explicitly supplied session on this engine is ours to abort.
        # Never roll back an unrelated engine or mask the original safe error.
        try:
            if isinstance(session, Session) and session.in_transaction():
                bind = session.get_bind()
                if getattr(bind, "engine", bind) is self.store.engine:
                    session.rollback()
        except Exception:
            pass

    def _authorize(self, session, principal, expected_policy, *, review):
        self._guard_session(session)
        settings, policy, imports_policy = self._validate()
        if not policy.enabled or not imports_policy.enabled:
            raise FactsError()
        if settings.admin_assurance_policy != expected_policy:
            raise AuthorizationError(403)
        current = self.authorizer.check_capability_in_transaction(session, principal,
            "catalog.review" if review else "catalog.import")
        if current.is_synthetic:
            if self.auth_service.runtime_settings.app_environment != "test":
                raise FactsError()
        elif not policy.real_facts_ready or not imports_policy.real_imports_ready:
            raise FactsError()
        return current

    def _batch(self, session, principal, import_id, expected_policy, *, review):
        current = self._authorize(session, principal, expected_policy, review=review)
        hint = self.import_service.store.get(session, import_id, lock=False)
        request = self.import_service._request_for_batch(hint)
        if review:
            # Trusted import references describe only the bounded derivative.
            # This is not an owner Principal or permission to read full bytes.
            description = SimpleNamespace(dataset_id=hint.dataset_id, source_id=hint.source_id,
                source_version=hint.source_version, is_synthetic=hint.is_synthetic)
            version = SimpleNamespace(file_id=hint.file_id, document_sha256=hint.file_sha256,
                size_bytes=hint.file_size, media_type={"json": "application/json", "csv": "text/csv"}.get(hint.format))
            current, _ = self.evidence_service._review_file(session, current, description, version, expected_policy)
        else:
            current, _ = self.import_service._current_file(session, current, request, expected_policy)
        batch = self.import_service.store.get(session, import_id)
        if self.import_service._request_for_batch(batch) != request:
            raise FactsError(409)
        if (batch.status != "staged" or batch.version != 1 or batch.parser_schema_version != PARSER_SCHEMA_VERSION
            or batch.is_synthetic != current.is_synthetic or utc_time(batch.created_at) > self.auth_service._now()):
            raise FactsError(409)
        if review:
            self.import_service.store.result(session, batch)
        else:
            self.import_service._verify_batch(session, current, batch, request, expected_policy)
        return current, batch

    def _resolve(self, session, principal, data, expected_policy, *, review):
        current, batch = self._batch(session, principal, data.import_id, expected_policy, review=review)
        raw = session.scalar(select(ImportCandidateRow).where(ImportCandidateRow.id == data.import_row_id,
            ImportCandidateRow.import_id == batch.id).with_for_update().execution_options(populate_existing=True))
        if raw is None:
            raise FactsError(404)
        if raw.dataset_id != batch.dataset_id or raw.is_synthetic != batch.is_synthetic:
            raise FactsError(409)
        try:
            original = ParsedRow(**{name: getattr(raw, name) for name in (*ROW_FIELDS, "row_number")})
            original.validate_namespace(batch.is_synthetic)
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise FactsError() from None
        scope = self.evidence_service.store.scope(session, dataset_id=batch.dataset_id,
            offering_id=original.offering_id, offering_version=original.offering_version,
            entry_year=original.entry_year, is_synthetic=batch.is_synthetic)
        date, date_hash = None, None
        if data.classification.date_event_id is not None:
            row = session.scalar(select(CatalogDateEvent).where(CatalogDateEvent.id == data.classification.date_event_id)
                .with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise FactsError(404)
            date_data = self.date_store.get_date_event(session, row.id)
            if ((date_data.dataset_id, date_data.offering_id, date_data.offering_version, date_data.entry_year,
                 date_data.is_synthetic, date_data.original_text) != (batch.dataset_id, original.offering_id,
                 original.offering_version, original.entry_year, batch.is_synthetic, original.value_text)):
                raise FactsError(409)
            date = DateResolutionSnapshot.from_date_event(date_data)
            date_hash = fingerprint(date_data.model_dump(mode="json"))
        evidence_hash = None
        if data.evidence_id is not None:
            snippet = self.evidence_service.verify_in_transaction(session, current, data.evidence_id,
                expected_offering_id=original.offering_id, expected_offering_version=original.offering_version,
                expected_entry_year=original.entry_year)
            document = self.evidence_service.store.get_document(session, snippet.document_id)
            version = self.evidence_service.store.get_version(session, document.id, snippet.document_version)
            if ((document.dataset_id, document.source_id, document.source_version, document.is_synthetic,
                 version.file_id, version.document_sha256, version.size_bytes) != (batch.dataset_id,
                 batch.source_id, batch.source_version, batch.is_synthetic, batch.file_id, batch.file_sha256, batch.file_size)):
                raise FactsError(409)
            evidence_hash = fingerprint(snippet.model_dump(mode="json"))
        payload = type_candidate(original, data.classification, evidence_id=data.evidence_id, date_resolution=date)
        hashes = {"row_sha256": fingerprint(original.model_dump(mode="json")), "scope_sha256": scope_hash(scope),
                  "date_sha256": date_hash, "evidence_sha256": evidence_hash}
        return current, batch, raw, payload, hashes

    def _audit(self, session, current):
        # The closed audit whitelist has no fact object type. No arbitrary IDs
        # are mislabelled as another existing domain's object.
        self.auth_service.store.audit.success(session, "administrator.action", actor=current,
                                             now=self.auth_service._now())

    def _final_guard(self, session, current, batch, row, result, expected_policy, *, review):
        source = session.scalar(select(CatalogSourceVersion).where(
            CatalogSourceVersion.source_id == batch.source_id, CatalogSourceVersion.version == batch.source_version)
            .with_for_update().execution_options(populate_existing=True))
        file = session.scalar(select(StorageObject).where(StorageObject.id == batch.file_id)
            .with_for_update().execution_options(populate_existing=True))
        edges = session.scalars(select(FactConflict).where(or_(FactConflict.left_id == row.id,
            FactConflict.right_id == row.id)).limit(201).execution_options(populate_existing=True)).all()
        self._authorize(session, current, expected_policy, review=review)
        now = self.auth_service._now()
        if (source is None or file is None or not utc_time(source.created_at) <= now < utc_time(source.recheck_due_at)
            or not utc_time(file.created_at) <= now < utc_time(file.expires_at)
            or utc_time(batch.created_at) > now or utc_time(row.created_at) > now
            or len(edges) > 200 or any(utc_time(edge.created_at) > now for edge in edges)):
            raise FactsError(409)
        ids = tuple(sorted((edge.right_id if edge.left_id == row.id else edge.left_id for edge in edges), key=str))
        if ids != result.conflicting_ids:
            raise FactsError(409)

    def _verify_fact(self, session, principal, row, expected_policy, *, review, expected=None):
        data = FactCreate(import_id=row.import_id, import_row_id=row.import_row_id,
                          classification=self.store.classification(row), evidence_id=row.evidence_id)
        current, batch, raw, payload, hashes = self._resolve(session, principal, data, expected_policy, review=review)
        if (row.import_id != batch.id or row.import_row_id != raw.id or row.dataset_id != batch.dataset_id
            or row.is_synthetic != batch.is_synthetic or row.date_event_id != data.classification.date_event_id):
            raise FactsError(409)
        if expected is not None and (row.offering_id, row.offering_version, row.entry_year) != expected:
            raise FactsError(409)
        result = self.store.data(session, row, payload, **hashes, now=self.auth_service._now())
        # Re-lock/re-read all proof inputs after the last fact/conflict query.
        final_current, final_batch, final_raw, final_payload, final_hashes = self._resolve(
            session, current, data, expected_policy, review=review)
        if (batch.id != final_batch.id or raw.id != final_raw.id or payload != final_payload or hashes != final_hashes):
            raise FactsError(409)
        self._final_guard(session, final_current, final_batch, row, result, expected_policy, review=review)
        return result

    @audited("administrator.action")
    def create_fact(self, principal, data: FactCreate) -> TypedCandidate:
        data = _input(FactCreate, data)
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction() as session:
            current, batch, raw, payload, hashes = self._resolve(session, principal, data, expected_policy, review=False)
            row = self.store.create(session, batch=batch, import_row=raw, payload=payload,
                                    **hashes, now=self.auth_service._now())
            self._audit(session, current)
            result = self._verify_fact(session, current, row, expected_policy, review=False)
        return result

    def _read(self, session, principal, fact_id, expected_policy, *, expected=None):
        current = self._authorize(session, principal, expected_policy, review=True)
        hint = self.store.get(session, fact_id, lock=False)
        data = FactCreate(import_id=hint.import_id, import_row_id=hint.import_row_id,
                          classification=self.store.classification(hint), evidence_id=hint.evidence_id)
        self._resolve(session, current, data, expected_policy, review=True)
        row = self.store.get(session, fact_id)
        if (row.import_id, row.import_row_id, row.evidence_id) != (data.import_id, data.import_row_id, data.evidence_id):
            raise FactsError(409)
        self._audit(session, current)
        return self._verify_fact(session, current, row, expected_policy, review=True, expected=expected)

    @audited("administrator.action")
    def get_fact(self, principal, fact_id: UUID) -> TypedCandidate:
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction() as session:
            result = self._read(session, principal, fact_id, expected_policy)
        return result

    @audited("administrator.action")
    def verify_in_transaction(self, session, principal, fact_id: UUID, *, expected_offering_id,
                              expected_offering_version, expected_entry_year) -> TypedCandidate:
        """Caller owns commit; errors abort its transaction, results are provisional."""
        with self._transaction(session) as active:
            if (type(expected_offering_id) is not UUID or type(expected_offering_version) is not int
                or not 1 <= expected_offering_version <= 2147483647 or type(expected_entry_year) is not int
                or not 1 <= expected_entry_year <= 9999):
                raise FactsError(422)
            expected_policy = self._validate()[0].admin_assurance_policy
            return self._read(active, principal, fact_id, expected_policy,
                expected=(expected_offering_id, expected_offering_version, expected_entry_year))
