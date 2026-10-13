"""Thin current-authority HTTP orchestration over the existing domain services."""

from contextlib import contextmanager

from pydantic import ValidationError

from ...audit.context import audited
from ...auth.authorization import Authorizer
from ...auth.config import AuthFlowError
from ...settings import V2RuntimeSettings
from ..sources.schemas import SourceRevisionInput, SourceVersionData
from .schemas import AdminContextData, AdminSourceData


class AdminFacade:
    def __init__(self, identity_service, source_service, storage_service, import_service, settings):
        self.auth_service = identity_service
        self.source_service, self.storage_service, self.import_service = source_service, storage_service, import_service
        self.settings = V2RuntimeSettings.model_validate(settings)
        self._initial_settings = self.settings
        self._validate()
        self.authorizer = Authorizer(identity_service)

    def _validate(self):
        from ...auth.service import AuthService
        from ...storage.service import StorageService
        from ..imports.service import ImportService
        from ..sources.service import SourceService
        try:
            runtime = V2RuntimeSettings.model_validate(self.settings)
            if (runtime != self._initial_settings or not isinstance(self.auth_service, AuthService)
                or not isinstance(self.source_service, SourceService)
                or not isinstance(self.storage_service, StorageService)
                or not isinstance(self.import_service, ImportService)
                or self.auth_service.runtime_settings != runtime
                or self.source_service.auth_service is not self.auth_service
                or self.storage_service.auth_service is not self.auth_service
                or self.import_service.auth_service is not self.auth_service
                or self.storage_service.source_service is not self.source_service
                or self.import_service.source_service is not self.source_service
                or self.import_service.storage_service is not self.storage_service):
                raise ValueError
            self.source_service._validate()
            self.storage_service._validate()
            self.import_service._validate()
        except Exception:
            raise AuthFlowError(503, "SERVICE_UNAVAILABLE") from None

    @contextmanager
    def _transaction(self):
        self._validate()
        with self.source_service._transaction() as session:
            self.import_service._guard_session(session)
            yield session

    def preflight(self, principal, capability):
        """Reject weak/foreign identities before buffering an upload request."""
        with self._transaction() as session:
            return self.authorizer.check_capability_in_transaction(session, principal, capability)

    @audited("administrator.action")
    def context(self, principal):
        with self._transaction() as session:
            current = self.authorizer.check_capability_in_transaction(session, principal, "catalog.source.read")
            source_ready = self.source_service.policy.enabled and (
                (current.is_synthetic and self.settings.app_environment == "test")
                or (not current.is_synthetic and self.source_service.policy.real_sources_ready
                    and current.user_id in self.source_service.policy.responsible_user_ids))
            import_ready = (source_ready and self.storage_service.policy.enabled
                and self.storage_service.policy.source_retention_days is not None
                and self.import_service.policy.enabled and self.import_service.idempotency_service.policy.enabled
                and (current.is_synthetic or (self.storage_service.policy.real_storage_ready
                    and self.import_service.policy.real_imports_ready
                    and self.import_service.idempotency_service.policy.real_idempotency_ready)))
            self.auth_service.store.audit.success(session, "administrator.action", actor=current,
                now=self.auth_service._now())
            current = self.authorizer.check_capability_in_transaction(session, current, "catalog.source.read")
            result = AdminContextData(schema_version="v2.t21", can_manage_sources=source_ready,
                can_import=import_ready, is_synthetic=current.is_synthetic)
        return result

    def _source_output(self, session, current, source, *, modifying=False):
        source = SourceVersionData.model_validate(source)
        dataset = self.source_service.store.get_dataset(session, source.dataset_id)
        revision = dataset.revision
        # The dataset read is in the existing source transaction. The last
        # domain check follows this SQL before the facade commits its output.
        checked = self.source_service.get_source_version(current, source.source_id, source.version, session=session)
        if modifying:
            now = self.auth_service._now()
            if not checked.created_at <= now < checked.recheck_due_at:
                from ...admissions_catalog.store import CatalogStoreError
                raise CatalogStoreError(409, "SOURCE_RECHECK_REQUIRED")
        values = checked.model_dump(exclude={"responsible_user_id"})
        return AdminSourceData(**values, dataset_revision=revision)

    @audited("administrator.action")
    def register(self, principal, request):
        with self._transaction() as session:
            saved = self.source_service.register_source(principal, request.source,
                expected_dataset_revision=request.expected_dataset_revision, session=session)
            result = self._source_output(session, principal, saved, modifying=True)
        return result

    @audited("administrator.action")
    def revise(self, principal, source_id, request):
        with self._transaction() as session:
            saved = self.source_service.revise_source(principal,
                SourceRevisionInput(source_id=source_id, definition=request.definition),
                expected_dataset_revision=request.expected_dataset_revision,
                expected_source_version=request.expected_source_version, session=session)
            result = self._source_output(session, principal, saved, modifying=True)
        return result

    @audited("administrator.action")
    def get_source(self, principal, source_id, version=None):
        with self._transaction() as session:
            saved = self.source_service.get_source_version(principal, source_id, version, session=session)
            result = self._source_output(session, principal, saved)
        return result

    def upload(self, principal, request):
        self._validate()
        return self.storage_service.upload_source(principal, request.source_id,
            expected_source_version=request.source_version, filename=request.filename,
            content_type=request.content_type, data=request.content_utf8.encode("utf-8"))

    def import_file(self, principal, request, key):
        from ...ingestion.schemas import ImportRequest
        self._validate()
        return self.import_service.import_file(principal,
            ImportRequest.model_validate(request.model_dump(exclude={"confirmed"})), key)

    def get_import(self, principal, import_id):
        self._validate()
        return self.import_service.get_import(principal, import_id)
