"""Current source authority and bounded review derivatives; no public evidence API."""

from contextlib import contextmanager
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..admin.sources.models import CatalogSource, CatalogSourceVersion
from ..admin.sources.service import SourceService
from ..admissions_catalog.date_models import CatalogDateEvent
from ..admissions_catalog.models import (AdmissionOffering, AdmissionOfferingVersion, CatalogDataset,
                                        CatalogInstitution, CatalogProgram)
from ..admissions_catalog.store import CatalogStoreError
from ..audit.context import audited
from ..audit.models import AuditEvent
from ..auth.authorization import Authorizer, AuthorizationError
from ..auth.config import AuthFlowError
from ..auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from ..auth.service import AuthService
from ..privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from ..storage.models import StorageObject
from ..storage.schemas import FileData, StorageError, StorageNamespace
from ..storage.service import StorageService
from .locators import extract_snippet, validate_original
from .models import Document, DocumentVersion, EvidenceSnippet
from .schemas import (DocumentCreate, EvidenceError, EvidencePolicy, LocatedSnippet, MAX_ORIGINAL_BYTES,
                      OriginalData, SnippetCreate, SnippetData, VersionCreate)
from .store import EvidenceStore, _input, utc_time


class EvidenceService:
    def __init__(self, source_service: SourceService, storage_service: StorageService,
                 store: EvidenceStore, policy: EvidencePolicy = EvidencePolicy()):
        self.source_service, self.storage_service, self.store = source_service, storage_service, store
        self.auth_service = getattr(source_service, "auth_service", None)
        try:
            self.policy = EvidencePolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise EvidenceError() from None
        self._initial_policy = self.policy
        self._validate()
        self.authorizer = Authorizer(self.auth_service)

    def _validate(self):
        if (not isinstance(self.source_service, SourceService) or not isinstance(self.storage_service, StorageService)
            or not isinstance(self.store, EvidenceStore) or not isinstance(self.auth_service, AuthService)
            or self.storage_service.auth_service is not self.auth_service
            or self.storage_service.source_service is not self.source_service
            or any(service.store.engine is not self.store.engine for service in
                   (self.source_service, self.storage_service, self.auth_service))):
            raise EvidenceError()
        settings, source_policy = self.source_service._validate()
        storage_policy = self.storage_service._validate()
        try:
            policy = EvidencePolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise EvidenceError() from None
        if policy != self._initial_policy:
            raise EvidenceError()
        return settings, policy, source_policy, storage_policy

    def _guard_session(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise EvidenceError()
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                           PrivacyNoticeVersion, PrivacyAdmissionRecord, AuditEvent, CatalogDataset,
                           CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion,
                           CatalogDateEvent, CatalogSource, CatalogSourceVersion, StorageObject,
                           Document, DocumentVersion, EvidenceSnippet):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise EvidenceError()
        except EvidenceError:
            raise
        except Exception:
            raise EvidenceError() from None

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
        except (EvidenceError, AuthFlowError, CatalogStoreError, StorageError):
            raise
        except Exception:
            raise EvidenceError() from None

    def _authorize(self, session, principal, expected_policy, *, review=False):
        self._guard_session(session)
        settings, policy, _, _ = self._validate()
        if not policy.enabled:
            raise EvidenceError()
        if settings.admin_assurance_policy != expected_policy:
            raise AuthorizationError(403)
        current = self.authorizer.check_capability_in_transaction(session, principal,
            "catalog.review" if review else "catalog.import")
        if current.is_synthetic:
            if self.auth_service.runtime_settings.app_environment != "test":
                raise EvidenceError()
        elif not policy.real_evidence_ready:
            raise EvidenceError()
        return current

    def _responsible_source(self, session, principal, document, expected_policy):
        current = self._authorize(session, principal, expected_policy)
        current, source = self.storage_service._source_guard(session, current, document.source_id,
                                                            document.source_version)
        if source.dataset_id != document.dataset_id:
            raise EvidenceError(409)
        current = self._authorize(session, current, expected_policy)
        if not source.created_at <= self.auth_service._now() < source.recheck_due_at:
            raise EvidenceError(409)
        return current, source

    @staticmethod
    def _check_file(metadata, *, expected_hash=None, expected_size=None, expected_media=None):
        try:
            metadata = FileData.model_validate(metadata)
        except (ValidationError, ValueError, TypeError):
            raise EvidenceError() from None
        if metadata.media_type not in {"application/json", "text/csv"} or metadata.size_bytes > MAX_ORIGINAL_BYTES:
            raise EvidenceError(422)
        if ((expected_hash is not None and metadata.sha256 != expected_hash)
            or (expected_size is not None and metadata.size_bytes != expected_size)
            or (expected_media is not None and metadata.media_type != expected_media)):
            raise EvidenceError(409)
        return metadata

    def _responsible_file(self, session, principal, document, file_id, expected_policy, *, expected_hash=None):
        current, source = self._responsible_source(session, principal, document, expected_policy)
        metadata = self.storage_service.get_source_file_in_transaction(session, current, file_id,
            expected_dataset_id=document.dataset_id, expected_source_id=document.source_id,
            expected_source_version=document.source_version)
        metadata = self._check_file(metadata, expected_hash=expected_hash)
        if metadata.is_synthetic != source.is_synthetic or metadata.is_synthetic != current.is_synthetic:
            raise EvidenceError(409)
        current = self._authorize(session, current, expected_policy)
        now = self.auth_service._now()
        if not source.created_at <= now < source.recheck_due_at or not metadata.created_at <= now < metadata.expires_at:
            raise EvidenceError(409)
        return current, metadata

    def _review_file(self, session, principal, document, version, expected_policy):
        # This bounded derivative permission does not grant Storage.read_source.
        # Responsibility remains a current, server-configured source property;
        # no owner Principal is forged and no second account/connection is locked.
        current = self._authorize(session, principal, expected_policy, review=True)
        source = self.source_service.store.get_source_version(session, document.source_id)
        _, _, source_policy, storage_policy = self._validate()
        if not source_policy.enabled or not storage_policy.enabled or storage_policy.source_retention_days is None:
            raise EvidenceError()
        if (source.dataset_id, source.version, source.is_synthetic) != (
            document.dataset_id, document.source_version, document.is_synthetic):
            raise EvidenceError(409)
        if source.is_synthetic:
            if not current.is_synthetic or self.auth_service.runtime_settings.app_environment != "test":
                raise AuthorizationError(403)
        elif (current.is_synthetic or not source_policy.real_sources_ready or not storage_policy.real_storage_ready
              or source.responsible_user_id not in source_policy.responsible_user_ids):
            raise EvidenceError()
        now = self.auth_service._now()
        if (source.manual_import_permission != "granted" or not source.manual_import_enabled
            or source.license_basis is None or source.permission_record_reference is None
            or source.permission_reviewed_at is None or source.permission_reviewed_at > now
            or not source.created_at <= now < source.recheck_due_at):
            raise EvidenceError(409)
        row = self.storage_service.store.get(session, version.file_id)
        metadata = self._check_file(self.storage_service.store.data(row), expected_hash=version.document_sha256,
                                   expected_size=version.size_bytes, expected_media=version.media_type)
        if (row.namespace != StorageNamespace.source_quarantine or row.status != "quarantined"
            or (row.dataset_id, row.source_id, row.source_version, row.is_synthetic) !=
               (document.dataset_id, document.source_id, document.source_version, document.is_synthetic)
            or not metadata.created_at <= self.auth_service._now() < metadata.expires_at):
            raise EvidenceError(404)
        current = self._authorize(session, current, expected_policy, review=True)
        # Final authorization is another query boundary; times are checked again.
        now = self.auth_service._now()
        if not source.created_at <= now < source.recheck_due_at or not metadata.created_at <= now < metadata.expires_at:
            raise EvidenceError(409)
        return current, metadata

    def _audit(self, session, current):
        # The existing audit type whitelist has no evidence object type. Retain
        # the fixed administrator action without mislabelling another domain ID.
        self.auth_service.store.audit.success(session, "administrator.action", actor=current,
                                             now=self.auth_service._now())

    def _not_future(self, *rows):
        now = self.auth_service._now()
        if any(utc_time(row.created_at) > now for row in rows):
            raise EvidenceError(409)

    @staticmethod
    def _same_document(left, right):
        fields = ("id", "dataset_id", "source_id", "source_version", "document_reference", "language", "is_synthetic")
        if any(getattr(left, field) != getattr(right, field) for field in fields):
            raise EvidenceError(409)

    def _version_guard(self, session, principal, document, version, expected_policy, *, review=False):
        if (version.document_id != document.id or version.dataset_id != document.dataset_id
            or version.is_synthetic != document.is_synthetic or version.version > document.current_version):
            raise EvidenceError(409)
        self._not_future(document, version)
        if review:
            current, metadata = self._review_file(session, principal, document, version, expected_policy)
        else:
            current, metadata = self._responsible_file(session, principal, document, version.file_id,
                                                     expected_policy, expected_hash=version.document_sha256)
        self._check_file(metadata, expected_size=version.size_bytes, expected_media=version.media_type)
        self._not_future(document, version)
        return current, metadata

    @audited("administrator.action")
    def create_document(self, principal, data: DocumentCreate):
        data = _input(DocumentCreate, data)
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction() as session:
            current, source = self._responsible_source(session, principal, data, expected_policy)
            row = self.store.create_document(session, data, is_synthetic=source.is_synthetic, now=self.auth_service._now())
            self._audit(session, current)
            self._responsible_source(session, current, row, expected_policy)
            self._not_future(row)
            result = self.store.document_data(row)
        return result

    @audited("administrator.action")
    def create_version(self, principal, data: VersionCreate):
        data = _input(VersionCreate, data)
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction() as session:
            current = self._authorize(session, principal, expected_policy)
            hint = self.store.document_data(self.store.get_document(session, data.document_id, lock=False))
            _, metadata = self._responsible_file(session, current, hint, data.file_id, expected_policy,
                                                 expected_hash=data.file_sha256)
        content = self.storage_service.read_source(principal, data.file_id)
        original = _input(OriginalData, validate_original(content, media_type=metadata.media_type))
        if original.sha256 != data.file_sha256 or original.size_bytes != metadata.size_bytes:
            raise EvidenceError(409)
        with self._transaction() as session:
            current, _ = self._responsible_file(session, principal, hint, data.file_id, expected_policy,
                                               expected_hash=data.file_sha256)
            document = self.store.get_document(session, data.document_id)
            self._same_document(hint, document)
            row = self.store.append_version(session, data, original, now=self.auth_service._now())
            # Dedup never replaces the original file binding or renews its TTL.
            self._version_guard(session, current, document, row, expected_policy)
            self._audit(session, current)
            self._version_guard(session, current, document, row, expected_policy)
            result = self.store.version_data(row)
        return result

    @audited("administrator.action")
    def create_snippet(self, principal, data: SnippetCreate) -> SnippetData:
        data = _input(SnippetCreate, data)
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction() as session:
            current = self._authorize(session, principal, expected_policy)
            hint = self.store.document_data(self.store.get_document(session, data.document_id, lock=False))
            version_hint = self.store.get_version(session, data.document_id, data.document_version, lock=False)
            _, metadata = self._version_guard(session, current, hint, version_hint, expected_policy)
            file_id = version_hint.file_id
            version_data = self.store.version_data(version_hint)
        content = self.storage_service.read_source(principal, file_id)
        original = _input(OriginalData, validate_original(content, media_type=metadata.media_type))
        if original.sha256 != version_data.document_sha256 or original.size_bytes != version_data.size_bytes:
            raise EvidenceError(409)
        located = _input(LocatedSnippet, extract_snippet(content, media_type=metadata.media_type,
                                                       byte_start=data.byte_start, byte_end=data.byte_end))
        with self._transaction() as session:
            current, _ = self._responsible_file(session, principal, hint, file_id, expected_policy,
                                               expected_hash=version_data.document_sha256)
            document = self.store.get_document(session, data.document_id)
            self._same_document(hint, document)
            version = self.store.get_version(session, document.id, data.document_version)
            if version.file_id != file_id or self.store.version_data(version) != version_data:
                raise EvidenceError(409)
            row = self.store.create_snippet(session, data, located, now=self.auth_service._now())
            self._audit(session, current)
            result = self.store.snippet_data(session, row)
            self._version_guard(session, current, document, version, expected_policy)
            self._not_future(row)
        return result

    def _snippet(self, session, principal, identifier, expected_policy):
        current = self._authorize(session, principal, expected_policy, review=True)
        hint = self.store.get_snippet(session, identifier, lock=False)
        document_hint = self.store.document_data(self.store.get_document(session, hint.document_id, lock=False))
        version_hint = self.store.get_version(session, hint.document_id, hint.document_version, lock=False)
        current, _ = self._version_guard(session, current, document_hint, version_hint, expected_policy, review=True)
        document = self.store.get_document(session, hint.document_id)
        self._same_document(document_hint, document)
        version = self.store.get_version(session, document.id, hint.document_version)
        row = self.store.get_snippet(session, identifier)
        if (row.document_id, row.document_version, version.file_id) != (
            document.id, version.version, version_hint.file_id):
            raise EvidenceError(409)
        return current, document, version, row

    def _read_snippet(self, session, principal, identifier, expected_policy, *, expected=None):
        current, document, version, row = self._snippet(session, principal, identifier, expected_policy)
        if expected is not None and (row.offering_id, row.offering_version, row.entry_year) != expected:
            raise EvidenceError(409)
        self.store.snippet_data(session, row)
        self._audit(session, current)
        result = self.store.snippet_data(session, row)
        self._version_guard(session, current, document, version, expected_policy, review=True)
        self._not_future(row)
        return result

    @audited("administrator.action")
    def get_snippet(self, principal, snippet_id: UUID) -> SnippetData:
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction() as session:
            result = self._read_snippet(session, principal, snippet_id, expected_policy)
        return result

    @audited("administrator.action")
    def verify_in_transaction(self, session, principal, snippet_id: UUID, *, expected_offering_id,
                              expected_offering_version, expected_entry_year) -> SnippetData:
        """Caller-owned: failures must roll back; the result is not yet committed."""
        if (type(expected_offering_id) is not UUID or type(expected_offering_version) is not int
            or not 1 <= expected_offering_version <= 2147483647 or type(expected_entry_year) is not int
            or not 1 <= expected_entry_year <= 9999):
            raise EvidenceError(422)
        expected_policy = self._validate()[0].admin_assurance_policy
        with self._transaction(session) as active:
            return self._read_snippet(active, principal, snippet_id, expected_policy,
                expected=(expected_offering_id, expected_offering_version, expected_entry_year))
