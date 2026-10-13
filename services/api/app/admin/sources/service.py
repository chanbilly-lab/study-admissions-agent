"""Current administrator authorization, declarations and required same-TX auditing."""

from contextlib import contextmanager
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...admissions_catalog.date_models import CatalogDateEvent
from ...admissions_catalog.models import (AdmissionOffering, AdmissionOfferingVersion, CatalogDataset,
                                         CatalogInstitution, CatalogProgram)
from ...admissions_catalog.store import CatalogStoreError, _input
from ...audit.context import audited
from ...audit.models import AuditEvent
from ...auth.authorization import Authorizer, AuthorizationError, Principal
from ...auth.models import AuthSession, AuthUser, AuthUserRole
from ...auth.service import AuthService
from .models import CatalogSource, CatalogSourceVersion
from .schemas import SourceCreateInput, SourcePolicy, SourceRevisionInput, SourceVersionData
from .store import SourceStore


class SourceService:
    def __init__(self, auth_service: AuthService, store: SourceStore, policy: SourcePolicy = SourcePolicy()):
        self.auth_service, self.store = auth_service, store
        try:
            self.policy = SourcePolicy.model_validate(policy)
        except (ValidationError, ValueError, TypeError):
            raise CatalogStoreError() from None
        self._initial_policy = self.policy
        self._validate()
        self.authorizer = Authorizer(self.auth_service)

    def _validate(self):
        if not isinstance(self.auth_service, AuthService) or not isinstance(self.store, SourceStore):
            raise CatalogStoreError()
        settings = self.auth_service._validate()
        if self.store.engine is not self.auth_service.store.engine:
            raise CatalogStoreError()
        try:
            policy = SourcePolicy.model_validate(self.policy)
        except (ValidationError, ValueError, TypeError):
            raise CatalogStoreError() from None
        if policy != self._initial_policy:
            raise CatalogStoreError()
        return settings, policy

    def _guard_session(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise CatalogStoreError()
        try:
            for mapper in (None, AuthUser, AuthSession, AuthUserRole, AuditEvent, CatalogDataset,
                           CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion,
                           CatalogDateEvent, CatalogSource, CatalogSourceVersion):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.store.engine:
                    raise CatalogStoreError()
        except CatalogStoreError:
            raise
        except Exception:
            raise CatalogStoreError() from None

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
        except SQLAlchemyError:
            raise CatalogStoreError() from None

    def _policy_check(self, current, is_synthetic):
        _, policy = self._validate()
        if not policy.enabled:
            raise CatalogStoreError()
        if is_synthetic:
            if self.auth_service.runtime_settings.app_environment != "test" or not current.is_synthetic:
                raise AuthorizationError(403)
        elif (not policy.real_sources_ready or not policy.responsible_user_ids
              or current.is_synthetic or current.user_id not in policy.responsible_user_ids):
            raise CatalogStoreError()

    def _finish(self, session, current, data, capability, *, modifying, original_settings):
        # An audit flush is another lock/I/O boundary. Permission and time must
        # be refreshed after it, while all account and catalog locks remain held.
        self.auth_service.store.audit.success(session, "administrator.action", actor=current,
                                             now=self.auth_service._now())
        fresh = self.authorizer.check_capability_in_transaction(session, current, capability)
        settings, _ = self._validate()
        if settings.admin_assurance_policy != original_settings.admin_assurance_policy:
            raise AuthorizationError(403)
        self._policy_check(fresh, data.is_synthetic)
        checked = SourceVersionData.model_validate(data)
        now = self.auth_service._now()
        if modifying and (now < checked.created_at or now >= checked.recheck_due_at
            or (checked.permission_reviewed_at is not None and checked.permission_reviewed_at > now)):
            raise CatalogStoreError(409, "SOURCE_RECHECK_REQUIRED")
        return checked

    @audited("administrator.action")
    def register_source(self, principal: Principal, data: SourceCreateInput, *,
                        expected_dataset_revision: int, session: Session | None = None) -> SourceVersionData:
        data = _input(SourceCreateInput, data)
        with self._transaction(session) as active:
            current = self.authorizer.check_capability_in_transaction(active, principal, "catalog.source.register")
            settings, _ = self._validate()
            self._policy_check(current, data.is_synthetic)
            saved = self.store.create_source(active, data, version_id=uuid4(), responsible_user_id=current.user_id,
                now=self.auth_service._now(), expected_dataset_revision=expected_dataset_revision)
            return self._finish(active, current, saved, "catalog.source.register", modifying=True,
                                original_settings=settings)

    @audited("administrator.action")
    def revise_source(self, principal: Principal, data: SourceRevisionInput, *, expected_dataset_revision: int,
                      expected_source_version: int, session: Session | None = None) -> SourceVersionData:
        data = _input(SourceRevisionInput, data)
        with self._transaction(session) as active:
            current = self.authorizer.check_capability_in_transaction(active, principal, "catalog.source.register")
            settings, _ = self._validate()
            old = self.store.get_source_version(active, data.source_id)
            self._policy_check(current, old.is_synthetic)
            if old.responsible_user_id != current.user_id:
                raise AuthorizationError(403)
            saved = self.store.append_source_version(active, data, version_id=uuid4(),
                responsible_user_id=current.user_id, now=self.auth_service._now(),
                expected_dataset_revision=expected_dataset_revision, expected_source_version=expected_source_version)
            return self._finish(active, current, saved, "catalog.source.register", modifying=True,
                                original_settings=settings)

    @audited("administrator.action")
    def get_source_version(self, principal: Principal, source_id: UUID, version: int | None = None, *,
                           session: Session | None = None) -> SourceVersionData:
        with self._transaction(session) as active:
            current = self.authorizer.check_capability_in_transaction(active, principal, "catalog.source.read")
            settings, _ = self._validate()
            data = self.store.get_source_version(active, source_id, version)
            self._policy_check(current, data.is_synthetic)
            return self._finish(active, current, data, "catalog.source.read", modifying=False,
                                original_settings=settings)
