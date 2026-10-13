"""Trusted append-only source writes in an explicitly supplied catalog transaction."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...admissions_catalog.date_models import CatalogDateEvent
from ...admissions_catalog.models import CatalogDataset
from ...admissions_catalog.schemas import MAX_VERSION
from ...admissions_catalog.store import CATALOG_HEAD, CatalogStore, CatalogStoreError, _input, _uuid, _version
from ...audit.retention import expires_after_months
from .models import CatalogSource, CatalogSourceVersion
from .schemas import SourceCreateInput, SourceRevisionInput, SourceVersionData


def utc_time(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CatalogStoreError(422, "INVALID_INPUT")
    return value.astimezone(timezone.utc)


class SourceStore(CatalogStore):
    def assert_schema_ready(self, required_head: str = CATALOG_HEAD) -> None:
        if required_head != "0003_catalog_sources_t13":
            raise CatalogStoreError()
        super().assert_schema_ready(required_head=required_head)

    @contextmanager
    def _work(self, session):
        with super()._work(session):
            for model in (CatalogDateEvent, CatalogSource, CatalogSourceVersion):
                bind = session.get_bind(mapper=model)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise CatalogStoreError()
            yield

    @staticmethod
    def _version_output(row):
        fields = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        try:
            for field in ("created_at", "permission_reviewed_at", "recheck_due_at"):
                if fields[field] is not None:
                    fields[field] = utc_time(fields[field])
            return SourceVersionData.model_validate(fields)
        except (ValidationError, ValueError, TypeError, OverflowError):
            raise CatalogStoreError() from None

    def _source(self, session, source_id):
        # Read the immutable dataset reference, then acquire locks in dataset/root order.
        dataset_id = session.execute(select(CatalogSource.dataset_id).where(
            CatalogSource.id == _uuid(source_id))).scalar_one_or_none()
        if dataset_id is None:
            raise CatalogStoreError(404, "NOT_FOUND")
        return dataset_id

    def _root(self, session, source_id, dataset_id, synthetic):
        root = self._parent(session, CatalogSource, source_id, dataset_id, synthetic)
        _version(root.current_version)
        return root

    @staticmethod
    def _new_version(definition, *, identifier, root, responsible_user_id, now):
        now = utc_time(now)
        permissions = (definition.manual_import_permission, definition.publication_permission,
                       definition.automated_fetch_permission)
        try:
            definition.validate_namespace(root.is_synthetic)
            fields = dict(id=_uuid(identifier), dataset_id=root.dataset_id, source_id=root.id,
                version=root.current_version, is_synthetic=root.is_synthetic,
                **definition.model_dump(), responsible_user_id=_uuid(responsible_user_id),
                created_at=now, permission_reviewed_at=now if any(p != "pending" for p in permissions) else None,
                recheck_due_at=min(now + timedelta(days=definition.recheck_days), expires_after_months(now, 24)),
                auto_fetch_enabled=False)
            data = SourceVersionData.model_validate(fields)
            return CatalogSourceVersion(**data.model_dump())
        except (ValidationError, ValueError, TypeError, OverflowError):
            raise CatalogStoreError(422, "INVALID_INPUT") from None

    def create_source(self, session: Session, data: SourceCreateInput, *, version_id: UUID,
                      responsible_user_id: UUID, now: datetime, expected_dataset_revision: int) -> SourceVersionData:
        data = _input(SourceCreateInput, data)
        with self._work(session):
            dataset = self._dataset(session, data.dataset_id, expected_revision=expected_dataset_revision)
            self._matching_mode(dataset, data)
            self._advance(dataset)
            root = CatalogSource(id=data.id, dataset_id=data.dataset_id, reference_key=data.reference_key,
                                 is_synthetic=data.is_synthetic, current_version=1)
            session.add(root)
            session.flush()
            row = self._new_version(data.definition, identifier=version_id, root=root,
                                    responsible_user_id=responsible_user_id, now=now)
            session.add(row)
            session.flush()
            return self._version_output(row)

    def append_source_version(self, session: Session, data: SourceRevisionInput, *, version_id: UUID,
                              responsible_user_id: UUID, now: datetime, expected_dataset_revision: int,
                              expected_source_version: int) -> SourceVersionData:
        data = _input(SourceRevisionInput, data)
        expected_source_version = _version(expected_source_version)
        with self._work(session):
            dataset_id = self._source(session, data.source_id)
            dataset = self._dataset(session, dataset_id, expected_revision=expected_dataset_revision)
            root = self._root(session, data.source_id, dataset_id, dataset.is_synthetic)
            if root.current_version != expected_source_version or root.current_version >= MAX_VERSION:
                raise CatalogStoreError(409, "CATALOG_CONFLICT")
            old = self.get_source_version(session, root.id, root.current_version)
            if old.responsible_user_id != _uuid(responsible_user_id):
                raise CatalogStoreError(403, "FORBIDDEN")
            self._advance(dataset)
            root.current_version += 1
            row = self._new_version(data.definition, identifier=version_id, root=root,
                                    responsible_user_id=responsible_user_id, now=now)
            session.add(row)
            session.flush()
            return self._version_output(row)

    def get_source_version(self, session: Session, source_id: UUID,
                           version: int | None = None) -> SourceVersionData:
        if version is not None:
            version = _version(version)
        with self._work(session):
            dataset_id = self._source(session, source_id)
            # No expected revision on a read, but the same dataset-before-source order is required.
            dataset = session.execute(select(CatalogDataset).where(CatalogDataset.id == dataset_id)
                .with_for_update().execution_options(populate_existing=True)).scalar_one()
            self.get_dataset(session, dataset_id)
            root = self._root(session, source_id, dataset_id, dataset.is_synthetic)
            selected_version = root.current_version if version is None else version
            row = session.execute(select(CatalogSourceVersion).where(
                CatalogSourceVersion.dataset_id == dataset_id, CatalogSourceVersion.source_id == root.id,
                CatalogSourceVersion.version == selected_version, CatalogSourceVersion.is_synthetic == root.is_synthetic)
                .with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
            if row is None:
                raise CatalogStoreError(404, "NOT_FOUND")
            return self._version_output(row)
