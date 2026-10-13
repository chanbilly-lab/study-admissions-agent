"""Trusted storage metadata maintenance in a caller-owned PostgreSQL transaction."""

from contextlib import contextmanager
from datetime import timezone
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .models import StorageBase, StorageObject
from .schemas import FileData, STORAGE_HEAD, StorageError, StorageNamespace


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2] / "storage_alembic.ini"))


def _parents_ready(connection):
    try:
        if (connection.scalar(text("SELECT version_num FROM auth_alembic_version")) != "0006_audit_t10"
            or connection.scalar(text("SELECT version_num FROM catalog_alembic_version")) != "0003_catalog_sources_t13"):
            raise StorageError()
    except SQLAlchemyError:
        raise StorageError() from None


def migrate_storage(engine, target="head"):
    if (getattr(getattr(engine, "dialect", None), "name", None) != "postgresql"
        or target not in {"head", STORAGE_HEAD}):
        raise StorageError()
    try:
        with engine.begin() as connection:
            _parents_ready(connection)
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise StorageError() from None


def _identifier(value):
    if not isinstance(value, UUID) or value.version != 4:
        raise StorageError(404)
    return value


class StorageStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise StorageError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            if not {"storage_objects", "storage_alembic_version"}.issubset(inspector.get_table_names()):
                raise StorageError()
            if {column["name"] for column in inspector.get_columns("storage_objects")} != set(StorageObject.__table__.columns.keys()):
                raise StorageError()
            with self.engine.connect() as connection:
                _parents_ready(connection)
                if connection.execute(text("SELECT version_num FROM storage_alembic_version")).scalars().all() != [STORAGE_HEAD]:
                    raise StorageError()
        except SQLAlchemyError:
            raise StorageError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise StorageError()
        try:
            for mapper in (None, StorageObject):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise StorageError()
            yield
        except IntegrityError:
            raise StorageError(409) from None
        except SQLAlchemyError:
            raise StorageError() from None

    @staticmethod
    def data(row):
        try:
            fields = {name: getattr(row, name) for name in FileData.model_fields}
            for name in ("created_at", "expires_at"):
                if fields[name].tzinfo is None or fields[name].utcoffset() is None:
                    raise ValueError()
                fields[name] = fields[name].astimezone(timezone.utc)
            return FileData.model_validate(fields)
        except (ValidationError, ValueError, TypeError, AttributeError, OverflowError):
            raise StorageError() from None

    def get(self, session, file_id, *, lock=True):
        identifier = _identifier(file_id)
        with self._work(session):
            query = select(StorageObject).where(StorageObject.id == identifier)
            if lock:
                query = query.with_for_update()
            row = session.execute(query.execution_options(populate_existing=True)).scalar_one_or_none()
            if row is None:
                raise StorageError(404)
            self.data(row)
            return row

    def create_private(self, session, data: FileData, resource):
        try:
            data = FileData.model_validate(data)
        except (ValidationError, ValueError, TypeError):
            raise StorageError() from None
        if (data.namespace != StorageNamespace.student_private or data.status != "quarantined"
            or data.id != resource.id or resource.resource_type != "attachment" or resource.version != 1
            or resource.is_synthetic != data.is_synthetic):
            raise StorageError()
        with self._work(session):
            row = StorageObject(**data.model_dump(), owner_user_id=resource.owner_user_id,
                owned_resource_id=resource.id, resource_version=resource.version,
                dataset_id=None, source_id=None, source_version=None)
            session.add(row)
            session.flush()
            return self.data(row)

    def create_source(self, session, data: FileData, source):
        try:
            data = FileData.model_validate(data)
        except (ValidationError, ValueError, TypeError):
            raise StorageError() from None
        if (data.namespace != StorageNamespace.source_quarantine or data.status != "quarantined"
            or data.is_synthetic != source.is_synthetic):
            raise StorageError()
        with self._work(session):
            row = StorageObject(**data.model_dump(), owner_user_id=None, owned_resource_id=None,
                resource_version=None, dataset_id=source.dataset_id, source_id=source.source_id,
                source_version=source.version)
            session.add(row)
            session.flush()
            return self.data(row)

    def mark_delete_pending(self, session, file_id):
        with self._work(session):
            row = self.get(session, file_id)
            if row.namespace != StorageNamespace.student_private:
                raise StorageError(404)
            if row.status != "deleted":
                row.status = "delete_pending"
                session.flush()
            return self.data(row)

    def confirm_deleted(self, session, file_id):
        """Internal receipt maintenance, after a committed deletion tombstone."""
        with self._work(session):
            row = self.get(session, file_id)
            if row.namespace != StorageNamespace.student_private or row.status not in {"delete_pending", "deleted"}:
                raise StorageError(409)
            row.status = "deleted"
            session.flush()
            return self.data(row)
