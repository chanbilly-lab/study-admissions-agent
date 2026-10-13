"""Bounded parsing outside the atomic receipt and candidate-staging transaction."""

from contextlib import contextmanager
from hashlib import sha256
from uuid import UUID

from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...admissions_catalog.date_models import CatalogDateEvent
from ...admissions_catalog.models import (AdmissionOffering, AdmissionOfferingVersion, CatalogDataset,
                                         CatalogInstitution, CatalogProgram)
from ...admissions_catalog.store import CatalogStoreError
from ...audit.context import audited
from ...audit.models import AuditEvent
from ...auth.authorization import Authorizer, AuthorizationError, Role
from ...auth.assurance import check_admin_assurance
from ...auth.config import AuthFlowError
from ...auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from ...auth.service import AuthService
from ...idempotency.models import IdempotencyRecord
from ...idempotency.schemas import IdempotencyError, ResourceReceipt
from ...idempotency.service import IdempotencyService
from ...idempotency.store import utc_time
from ...ingestion.schemas import (ImportRequest, ImportResult, ImportsPolicy, ImportServiceError,
                                  MAX_IMPORT_BYTES, PARSER_SCHEMA_VERSION, ParsedImport)
from ...ingestion.structured import parse_structured_import
from ...privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from ...storage.models import StorageObject
from ...storage.schemas import FileData, StorageError
from ...storage.service import StorageService
from ..sources.models import CatalogSource, CatalogSourceVersion
from ..sources.service import SourceService
from .models import ImportBatch, ImportCandidateRow, ImportRowError
from .store import ImportsStore, _input


class ImportService:
    def __init__(self, source_service: SourceService, storage_service: StorageService,
                 idempotency_service: IdempotencyService, store: ImportsStore,
                 policy: ImportsPolicy = ImportsPolicy()):
        self.source_service, self.storage_service = source_service, storage_service
        self.idempotency_service, self.store = idempotency_service, store
        self.auth_service = getattr(source_service, "auth_service", None)
        try:
            self.policy = ImportsPolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise ImportServiceError() from None
        self._initial_policy = self.policy
        self._validate()
        self.authorizer = Authorizer(self.auth_service)

    def _validate(self):
        if (not isinstance(self.source_service, SourceService) or not isinstance(self.storage_service, StorageService)
            or not isinstance(self.idempotency_service, IdempotencyService) or not isinstance(self.store, ImportsStore)
            or not isinstance(self.auth_service, AuthService)
            or self.storage_service.auth_service is not self.auth_service
            or self.idempotency_service.auth_service is not self.auth_service
            or self.storage_service.source_service is not self.source_service
            or any(service.store.engine is not self.store.engine for service in
                   (self.source_service, self.storage_service, self.idempotency_service, self.auth_service))):
            raise ImportServiceError()
        settings, _ = self.source_service._validate()
        self.storage_service._validate()
        self.idempotency_service._validate()
        try:
            policy = ImportsPolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise ImportServiceError() from None
        if policy != self._initial_policy:
            raise ImportServiceError()
        return settings, policy

    def _guard_session(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise ImportServiceError()
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                           PrivacyNoticeVersion, PrivacyAdmissionRecord, AuditEvent, CatalogDataset,
                           CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion,
                           CatalogDateEvent, CatalogSource, CatalogSourceVersion, StorageObject,
                           IdempotencyRecord, ImportBatch, ImportCandidateRow, ImportRowError):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise ImportServiceError()
        except ImportServiceError:
            raise
        except Exception:
            raise ImportServiceError() from None

    @contextmanager
    def _transaction(self):
        try:
            self._validate()
            with Session(self.store.engine) as session, session.begin():
                self._guard_session(session)
                yield session
        except (AuthFlowError, CatalogStoreError, StorageError, IdempotencyError, ImportServiceError):
            raise
        except Exception:
            raise ImportServiceError() from None

    def _authorize(self, session, principal, expected_policy):
        self._guard_session(session)
        settings, policy = self._validate()
        if not policy.enabled:
            raise ImportServiceError()
        if settings.admin_assurance_policy != expected_policy:
            raise AuthorizationError(403)
        current = self.authorizer.check_capability_in_transaction(session, principal, "catalog.import")
        if current.is_synthetic:
            if self.auth_service.runtime_settings.app_environment != "test":
                raise ImportServiceError()
        elif not policy.real_imports_ready:
            raise ImportServiceError()
        return current

    def _current_file(self, session, principal, request, expected_policy, *, additional_files=()):
        current = self._authorize(session, principal, expected_policy)
        metadata = self.storage_service.get_source_file_in_transaction(session, current, request.file_id,
            expected_dataset_id=request.dataset_id, expected_source_id=request.source_id,
            expected_source_version=request.source_version)
        try:
            metadata = FileData.model_validate(metadata)
        except (ValidationError, ValueError, TypeError):
            raise ImportServiceError() from None
        if metadata.sha256 != request.file_sha256:
            raise ImportServiceError(409)
        if metadata.media_type != {"json": "application/json", "csv": "text/csv"}[request.format]:
            raise ImportServiceError(422)
        # Storage permits 10 MiB; this synchronous parser permits only 1 MiB.
        # Reject before file I/O/T49 rather than inventing a durable oversized batch.
        if metadata.size_bytes > MAX_IMPORT_BYTES:
            raise ImportServiceError(422)
        if metadata.is_synthetic != current.is_synthetic:
            raise ImportServiceError()
        # Retain locked source/file proof through the LAST authorization query.
        # No SQL follows the fresh clock: a role/session/MFA or source/file can
        # expire while that query waits even though it was valid on entry.
        source = self.source_service.get_source_version(current, request.source_id, session=session)
        if source.version != request.source_version or source.responsible_user_id != current.user_id:
            raise ImportServiceError(409)
        role = session.scalar(select(AuthUserRole).where(AuthUserRole.user_id == current.user_id,
            AuthUserRole.role == "data_admin").with_for_update().execution_options(populate_existing=True))
        session_row = session.get(AuthSession, current.session_id)
        current, stored = self.authorizer._refresh(current, session)
        settings, _ = self._validate()
        now = self.auth_service._now()
        if (session_row is None or session_row.revoked_at is not None
            or not utc_time(session_row.created_at) <= now < stored.expires_at):
            raise AuthorizationError(401)
        if (settings.admin_assurance_policy != expected_policy or Role.data_admin not in current.roles
            or role is None or role.revoked_at is not None or utc_time(role.granted_at) > now
            or (role.expires_at is not None and utc_time(role.expires_at) <= now)
            or stored.verified_issuer != settings.provider.issuer
            or stored.verified_client_id != settings.provider.client_id):
            raise AuthorizationError(403)
        check_admin_assurance(stored.assurance, issuer=stored.verified_issuer,
            client_id=stored.verified_client_id, policy=expected_policy, now=now)
        if (source.manual_import_permission != "granted" or not source.manual_import_enabled
            or source.license_basis is None or source.permission_record_reference is None
            or source.permission_reviewed_at is None or source.permission_reviewed_at > now
            or not source.created_at <= now < source.recheck_due_at
            or any(not file.created_at <= now < file.expires_at for file in (metadata, *additional_files))):
            raise ImportServiceError(409)
        return current, metadata

    @staticmethod
    def _request_for_batch(row):
        try:
            return ImportRequest(dataset_id=row.dataset_id, source_id=row.source_id,
                source_version=row.source_version, file_id=row.file_id,
                file_sha256=row.file_sha256, format=row.format)
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise ImportServiceError() from None

    def _verify_batch(self, session, principal, row, request, expected_policy, *, replayed=False,
                      additional_files=()):
        if (row.status == "deleted" or row.version != 1 or row.parser_schema_version != PARSER_SCHEMA_VERSION
            or type(row.actor_user_id) is not UUID or row.is_synthetic != principal.is_synthetic
            or (row.dataset_id, row.source_id, row.source_version, row.file_sha256, row.format) !=
               (request.dataset_id, request.source_id, request.source_version, request.file_sha256, request.format)
            or utc_time(row.created_at) > self.auth_service._now()):
            raise ImportServiceError(404)
        original_request = self._request_for_batch(row)
        current, original_file = self._current_file(session, principal, original_request, expected_policy)
        if original_file.size_bytes != row.file_size:
            raise ImportServiceError()
        result = self.store.result(session, row, replayed=replayed)
        # Offering locks and audit flushes can wait. Check the exact original file,
        # current source permission and current administrator again afterwards.
        current, _ = self._current_file(session, current, original_request, expected_policy,
                                        additional_files=additional_files)
        return result

    @audited("catalog.import")
    def import_file(self, principal, request: ImportRequest, key: SecretStr) -> ImportResult:
        """Own-TX only: return the minimal verified snapshot after T49 COMMIT."""
        request = _input(ImportRequest, request)
        self.idempotency_service._key_digest(key)
        settings, _ = self._validate()
        expected_policy = settings.admin_assurance_policy
        with self._transaction() as session:
            _, metadata = self._current_file(session, principal, request, expected_policy)
        # The source reader owns its own transaction and verifies actual bytes.
        content = self.storage_service.read_source(principal, request.file_id)
        if (type(content) is not bytes or len(content) != metadata.size_bytes
            or sha256(content).hexdigest() != request.file_sha256):
            raise ImportServiceError(409)
        try:
            parsed = ParsedImport.model_validate(parse_structured_import(content, format=request.format))
        except Exception:
            raise ImportServiceError() from None
        payload = request.model_dump(mode="json")
        final = {}
        callback_failure = []

        def perform(active, current):
            current, file_data = self._current_file(active, current, request, expected_policy)
            row = self.store.natural(active, request)
            if row is None:
                errors = self.store.scope_errors(active, parsed, dataset_id=request.dataset_id,
                                                 is_synthetic=current.is_synthetic)
                row = self.store.create(active, request, file_data, parsed, errors,
                                        actor_user_id=current.user_id, now=self.auth_service._now())
                final["natural_replayed"] = False
            else:
                self._verify_batch(active, current, row, request, expected_policy)
                final["natural_replayed"] = True
            return ResourceReceipt(kind="import", resource_id=row.id, version=row.version)

        def verify(active, current, receipt):
            current, _ = self._current_file(active, current, request, expected_policy)
            row = self.store.get(active, receipt.resource_id)
            if receipt.kind != "import" or receipt.version != row.version:
                raise ImportServiceError()
            final["snapshot"] = self._verify_batch(active, current, row, request, expected_policy)
            return True

        def protected(callback):
            def run(*args):
                try:
                    return callback(*args)
                except (CatalogStoreError, StorageError, ImportServiceError) as error:
                    # T49 intentionally wraps unknown local callback exceptions.
                    # Retain only these fixed domain errors until its own-TX has
                    # fully rolled back; never unwrap a raw parser/SQL exception.
                    callback_failure.append(error)
                    raise
            return run

        try:
            with self._transaction() as active:
                completed = self.idempotency_service.execute(principal, "catalog.import", key, payload,
                    perform=protected(perform), verify_resource=protected(verify), session=active)
                row = self.store.get(active, completed.resource.resource_id)
                if completed.resource.kind != "import" or completed.resource.version != row.version:
                    raise ImportServiceError()
                current, requested_file = self._current_file(active, principal, request, expected_policy)
                snapshot = self._verify_batch(active, current, row, request, expected_policy,
                                               additional_files=(requested_file,))
                result = _input(ImportResult, snapshot.model_copy(update={
                    "replayed": completed.replayed or final.get("natural_replayed", False)}))
        except IdempotencyError:
            if callback_failure:
                raise callback_failure[-1] from None
            raise
        except (AuthFlowError, CatalogStoreError, StorageError, ImportServiceError):
            raise
        except Exception:
            raise ImportServiceError() from None
        return result  # The outer import transaction committed BEFORE release.

    @audited("administrator.action")
    def get_import(self, principal, import_id: UUID) -> ImportResult:
        settings, _ = self._validate()
        expected_policy = settings.admin_assurance_policy
        with self._transaction() as session:
            current = self._authorize(session, principal, expected_policy)
            # Immutable references are only a hint; source/file locks precede the
            # batch lock, matching the import path. Re-read all refs under lock.
            hint = self.store.get(session, import_id, lock=False)
            request = self._request_for_batch(hint)
            current, _ = self._current_file(session, current, request, expected_policy)
            row = self.store.get(session, import_id)
            if self._request_for_batch(row) != request:
                raise ImportServiceError(409)
            self._verify_batch(session, current, row, request, expected_policy)
            self.auth_service.store.audit.success(session, "administrator.action", actor=current,
                object_type="import", object_id=row.id, object_version=row.version, now=self.auth_service._now())
            result = self._verify_batch(session, current, row, request, expected_policy)
        return result
