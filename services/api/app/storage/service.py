"""Owner-only files and source quarantine with fresh authorization around I/O.

Filesystem and database commits are not one atomic transaction. A valid backend
write receipt permits best-effort compensation; uncertain backend failures must
be cleaned by that trusted adapter, never by deleting an existing foreign key.
"""

from contextlib import contextmanager
from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..admin.sources.models import CatalogSource, CatalogSourceVersion
from ..admin.sources.service import SourceService
from ..admissions_catalog.date_models import CatalogDateEvent
from ..admissions_catalog.models import (AdmissionOffering, AdmissionOfferingVersion, CatalogDataset,
                                        CatalogInstitution, CatalogProgram)
from ..audit.context import audited
from ..audit.models import AuditEvent
from ..audit.retention import expires_after_months
from ..auth.authorization import Authorizer, AuthorizationError, Principal
from ..auth.config import AuthFlowError
from ..auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from ..auth.service import AuthService
from ..privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from ..privacy.service import PrivacyService
from .models import StorageObject
from .protocol import StorageBackend
from .schemas import (FileData, StorageError, StorageNamespace, StoragePolicy, StoredBlob, ValidatedUpload)
from .store import StorageStore
from .validation import validate_upload


class StorageService:
    def __init__(self, auth_service, privacy_service, source_service, store, backend,
                 policy: StoragePolicy = StoragePolicy()):
        self.auth_service, self.privacy_service, self.source_service = auth_service, privacy_service, source_service
        self.store, self.backend = store, backend
        try:
            self.policy = StoragePolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise StorageError() from None
        self._initial_policy = self.policy
        self._validate()
        self.authorizer = Authorizer(auth_service)

    def _validate(self):
        if (not isinstance(self.auth_service, AuthService) or not isinstance(self.privacy_service, PrivacyService)
            or not isinstance(self.source_service, SourceService) or not isinstance(self.store, StorageStore)
            or not isinstance(self.backend, StorageBackend)
            or self.privacy_service.auth_service is not self.auth_service
            or self.source_service.auth_service is not self.auth_service
            or self.source_service.store.engine is not self.store.engine
            or self.auth_service.store.engine is not self.store.engine):
            raise StorageError()
        self.auth_service._validate()
        self.privacy_service._validate()
        self.source_service._validate()
        try:
            policy = StoragePolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise StorageError() from None
        if policy != self._initial_policy:
            raise StorageError()
        return policy

    def _guard_session(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise StorageError()
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                           PrivacyNoticeVersion, PrivacyAdmissionRecord, AuditEvent, CatalogDataset,
                           CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion,
                           CatalogDateEvent, CatalogSource, CatalogSourceVersion, StorageObject):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise StorageError()
        except StorageError:
            raise
        except Exception:
            raise StorageError() from None

    @contextmanager
    def _transaction(self, supplied=None):
        self._validate()
        try:
            if supplied is None:
                with Session(self.store.engine) as session, session.begin():
                    self._guard_session(session)
                    yield session
            else:
                self._guard_session(supplied)
                yield supplied
        except (AuthFlowError, StorageError):
            raise
        except Exception:
            raise StorageError() from None

    def _policy_check(self, current, synthetic):
        policy = self._validate()
        if not policy.enabled:
            raise StorageError()
        if synthetic:
            if self.auth_service.runtime_settings.app_environment != "test" or not current.is_synthetic:
                raise AuthorizationError(403)
        elif not policy.real_storage_ready or current.is_synthetic:
            raise StorageError()
        return policy

    def _backend(self, method, *args):
        try:
            return getattr(self.backend, method)(*args)
        except StorageError:
            raise
        except Exception:
            raise StorageError() from None

    def _write(self, namespace, identifier, content, validated):
        self._backend("verify_ready")
        result = self._backend("write", namespace, identifier, content)
        try:
            result = StoredBlob.model_validate(result)
        except (ValidationError, ValueError, TypeError):
            raise StorageError() from None
        if (result.namespace != namespace or result.object_id != identifier
            or result.size_bytes != validated.size_bytes or result.sha256 != validated.sha256):
            raise StorageError()
        return result

    def _read(self, data):
        self._backend("verify_ready")
        content = self._backend("read", data.namespace, data.id, data.size_bytes, data.sha256)
        if type(content) is not bytes or len(content) != data.size_bytes or sha256(content).hexdigest() != data.sha256:
            raise StorageError()
        return content

    def _compensate(self, receipt):
        if receipt is not None:
            try:
                # True = removed; False = already absent. Both leave no usable blob.
                result = self._backend("delete", receipt.namespace, receipt.object_id)
                if type(result) is not bool:
                    raise StorageError()
            except Exception:
                pass  # Unregistered orphan remains inaccessible; no auto-repair/registration.

    def _file_data(self, identifier, namespace, current, validated, *, source=None):
        now = self.auth_service._now()
        try:
            expiry = expires_after_months(now, 24)
            if source is not None:
                policy = self._validate()
                if policy.source_retention_days is None:
                    raise StorageError()
                expiry = min(expiry, now + timedelta(days=policy.source_retention_days), source.recheck_due_at)
            return FileData(id=identifier, namespace=namespace, is_synthetic=current.is_synthetic,
                status="quarantined", **validated.model_dump(), created_at=now, expires_at=expiry)
        except StorageError:
            raise
        except (ValidationError, ValueError, TypeError, OverflowError):
            raise StorageError() from None

    def _available(self, row):
        data = self.store.data(row)
        now = self.auth_service._now()
        if data.status != "quarantined" or not data.created_at <= now < data.expires_at:
            raise StorageError(404)
        return data

    def _private(self, session, principal, file_id):
        current, resource = self.authorizer.check_owned_in_transaction(
            session, principal, "attachment", file_id, "download")
        self.privacy_service.require_purpose(session, current, "core_consultation")
        row = self.store.get(session, file_id)
        data = self._available(row)
        if (data.namespace != StorageNamespace.student_private or row.owner_user_id != current.user_id
            or row.owned_resource_id != resource.id or row.resource_version != resource.version
            or row.is_synthetic != resource.is_synthetic):
            raise StorageError(404)
        self._policy_check(current, data.is_synthetic)
        return current, resource, data

    def _source_guard(self, session, principal, source_id, expected_version, *, write=False):
        capability = "catalog.storage.write" if write else "catalog.storage.read"
        current = self.authorizer.check_capability_in_transaction(session, principal, capability)
        source = self.source_service.get_source_version(current, source_id, session=session)
        policy = self._policy_check(current, source.is_synthetic)
        if policy.source_retention_days is None:
            raise StorageError()
        if type(expected_version) is not int or source.version != expected_version:
            raise StorageError(409)
        if source.responsible_user_id != current.user_id:
            raise AuthorizationError(403)
        now = self.auth_service._now()
        if (source.manual_import_permission != "granted" or not source.manual_import_enabled
            or source.license_basis is None or source.permission_record_reference is None
            or source.permission_reviewed_at is None or source.permission_reviewed_at > now
            or not source.created_at <= now < source.recheck_due_at):
            raise StorageError(409)
        return current, source

    def _audit_private(self, session, current, resource, action):
        self.auth_service.store.audit.success(session, action, actor=current, object_type="attachment",
            object_id=resource.id, object_version=resource.version, now=self.auth_service._now())

    def _audit_source(self, session, current):
        self.auth_service.store.audit.success(session, "administrator.action", actor=current, now=self.auth_service._now())

    @audited("authorization.owned.register")
    def upload_private(self, principal, *, parent_kind, parent_resource_id, filename, content_type, data: bytes):
        if parent_kind not in {"profile", "plan"}:
            raise AuthorizationError(403)
        receipt = None
        try:
            with self._transaction() as session:
                current, parent = self.authorizer.check_owned_in_transaction(
                    session, principal, parent_kind, parent_resource_id, "read")
                self.privacy_service.require_purpose(session, current, "core_consultation")
                self._policy_check(current, parent.is_synthetic)
                validated = ValidatedUpload.model_validate(validate_upload(data, filename=filename, content_type=content_type))
                identifier = uuid4()
                receipt = self._write(StorageNamespace.student_private, identifier, data, validated)
                # File I/O can cross an absolute expiry or withdrawal boundary.
                current, _ = self.authorizer.check_owned_in_transaction(
                    session, current, parent_kind, parent_resource_id, "read")
                self.privacy_service.require_purpose(session, current, "core_consultation")
                resource = self.authorizer.register_owned(current, "attachment", resource_id=identifier,
                                                          parent_id=parent_resource_id, session=session)
                saved = self.store.create_private(session, self._file_data(identifier,
                    StorageNamespace.student_private, current, validated), resource)
                self._audit_private(session, current, resource, "authorization.owned.register")
                _, _, saved = self._private(session, current, saved.id)
            return saved  # The SQL context committed before metadata becomes visible.
        except Exception:
            self._compensate(receipt)
            raise

    @audited("administrator.action")
    def upload_source(self, principal, source_id, *, expected_source_version, filename, content_type, data: bytes):
        receipt = None
        try:
            with self._transaction() as session:
                current, source = self._source_guard(session, principal, source_id, expected_source_version, write=True)
                validated = ValidatedUpload.model_validate(validate_upload(data, filename=filename, content_type=content_type))
                identifier = uuid4()
                receipt = self._write(StorageNamespace.source_quarantine, identifier, data, validated)
                current, source = self._source_guard(session, current, source_id, expected_source_version, write=True)
                saved = self.store.create_source(session, self._file_data(identifier,
                    StorageNamespace.source_quarantine, current, validated, source=source), source)
                self._audit_source(session, current)
                current, source = self._source_guard(session, current, source_id, expected_source_version, write=True)
                saved = self._available(self.store.get(session, saved.id))
            return saved
        except Exception:
            self._compensate(receipt)
            raise

    @audited("authorization.owned.check")
    def read_private(self, principal, file_id):
        with self._transaction() as session:
            current, resource, metadata = self._private(session, principal, file_id)
            content = self._read(metadata)
            current, resource, _ = self._private(session, current, file_id)
            self._audit_private(session, current, resource, "authorization.owned.check")
            self._private(session, current, file_id)
        return content

    def _source_file(self, session, principal, file_id):
        current = self.authorizer.check_capability_in_transaction(session, principal, "catalog.storage.read")
        # Peek only immutable references; lock order remains account -> source -> file.
        hint = self.store.get(session, file_id, lock=False)
        if hint.namespace != StorageNamespace.source_quarantine:
            raise StorageError(404)
        reference = hint.dataset_id, hint.source_id, hint.source_version
        current, source = self._source_guard(session, current, hint.source_id, hint.source_version)
        row = self.store.get(session, file_id)
        if (row.namespace != StorageNamespace.source_quarantine
            or reference != (row.dataset_id, row.source_id, row.source_version)
            or source.dataset_id != row.dataset_id or source.is_synthetic != row.is_synthetic):
            raise StorageError(409)
        return current, self._available(row), reference

    @audited("administrator.action")
    def read_source(self, principal, file_id):
        with self._transaction() as session:
            current, metadata, _ = self._source_file(session, principal, file_id)
            content = self._read(metadata)
            current, _, _ = self._source_file(session, current, file_id)
            self._audit_source(session, current)
            self._source_file(session, current, file_id)
        return content

    @audited("administrator.action")
    def get_source_file_in_transaction(self, session, principal, file_id, *, expected_dataset_id=None,
                                       expected_source_id=None, expected_source_version=None):
        with self._transaction(session) as active:
            current, metadata, reference = self._source_file(active, principal, file_id)
            expected = (expected_dataset_id, expected_source_id, expected_source_version)
            if any(value is not None for value in expected):
                if (any(value is None for value in expected) or not isinstance(expected_dataset_id, UUID)
                    or not isinstance(expected_source_id, UUID) or type(expected_source_version) is not int
                    or expected != reference):
                    raise StorageError(409)
            self._audit_source(active, current)
            _, metadata, _ = self._source_file(active, current, file_id)
            return metadata

    def _delete_owner(self, session, principal, file_id):
        current, _ = self.authorizer._refresh(principal, session)
        resource = session.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == file_id,
            AuthOwnedResource.owner_user_id == current.user_id).with_for_update()
            .execution_options(populate_existing=True))
        if resource is None or resource.resource_type != "attachment":
            raise StorageError(404)
        row = self.store.get(session, file_id)
        if (row.namespace != StorageNamespace.student_private or row.owner_user_id != current.user_id
            or row.owned_resource_id != resource.id or row.is_synthetic != current.is_synthetic):
            raise StorageError(404)
        current, _ = self.authorizer._refresh(current, session)
        return current, resource, row

    @audited("authorization.owned.execute")
    def delete_private(self, principal, file_id):
        # Reduction of permissions is independent of a still-active purpose/role.
        with self._transaction() as session:
            current, resource, row = self._delete_owner(session, principal, file_id)
            if row.status == "deleted":
                return self.store.data(row)
            guard = self.auth_service.store.rights_guard
            if guard is not None:
                guard.record(session, "file_deleted", current.user_id, resource_id=row.id)
            resource.status = "deleted"
            saved = self.store.mark_delete_pending(session, file_id)
            self._audit_private(session, current, resource, "authorization.owned.execute")
            self._delete_owner(session, current, file_id)
        try:
            absent = self._backend("delete", saved.namespace, saved.id)
            if type(absent) is not bool:
                raise StorageError()
            # Internal completion receipt; no new access is granted even if the
            # initiating session expires after its committed deletion request.
            with self._transaction() as session:
                completed = self.store.confirm_deleted(session, saved.id)
            saved = completed
        except Exception:
            pass  # Tombstone is durable; physical deletion failure stays pending.
        return saved
