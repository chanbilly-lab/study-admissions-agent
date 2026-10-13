"""Trusted candidate maintenance in a caller-owned transaction.

This store is not an authorization endpoint. Callers own commit/rollback and
must propagate failures out of their transaction. It offers no update/delete
interface for identities or old versions; privileged SQL remains outside that
service-level boundary.
"""

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .models import (AdmissionOffering, AdmissionOfferingVersion, CatalogBase,
                     CatalogDataset, CatalogInstitution, CatalogProgram,
                     OFFERING_SCOPE_FIELDS, PROGRAM_SCOPE_FIELDS)
from .schemas import (DatasetData, DatasetInput, InstitutionData, InstitutionInput,
                      MAX_VERSION, OfferingData, OfferingInput, OfferingVersionData,
                      OfferingVersionRef, ProgramData, ProgramInput, ScopeKey)


CATALOG_HEAD = "0003_catalog_sources_t13"
CATALOG_HEADS = {"0001_catalog_t11", "0002_catalog_dates_t12", CATALOG_HEAD}


class CatalogStoreError(ValueError):
    def __init__(self, status_code: int = 503, code: str = "CATALOG_UNAVAILABLE"):
        self.status_code = status_code
        self.code = code
        super().__init__(code)


def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[2] / "catalog_alembic.ini"))


def migrate_catalog(engine, target: str = "head") -> None:
    """Explicit PostgreSQL migration; never called by an application factory."""
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
        raise CatalogStoreError()
    if target not in {"head", *CATALOG_HEADS}:
        raise CatalogStoreError(422, "INVALID_INPUT")
    try:
        config = migration_config()
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise CatalogStoreError() from None


def _uuid(value) -> UUID:
    if not isinstance(value, UUID):
        raise CatalogStoreError(422, "INVALID_INPUT")
    return value


def _version(value) -> int:
    if type(value) is not int or not 1 <= value <= MAX_VERSION:
        raise CatalogStoreError(422, "INVALID_INPUT")
    return value


def _input(model, value):
    try:
        return model.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        raise CatalogStoreError(422, "INVALID_INPUT") from None


def _output(model, row, scope_fields=()):
    try:
        fields = {column.name: getattr(row, column.name) for column in row.__table__.columns
                  if not column.name.endswith("_key") or column.name == "reference_key"}
        for field in scope_fields:
            fields[field] = ScopeKey.from_canonical_key(getattr(row, f"{field}_key"))
        return model.model_validate(fields)
    except (ValidationError, TypeError, ValueError):
        raise CatalogStoreError() from None


class CatalogStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise CatalogStoreError()
        self.engine = engine

    def assert_schema_ready(self, required_head: str = CATALOG_HEAD) -> None:
        """Inspect only; missing or mismatched schema is never repaired here."""
        if required_head not in CATALOG_HEADS:
            raise CatalogStoreError()
        tables = list(CatalogBase.metadata.tables.values())
        if required_head != "0001_catalog_t11":
            from .date_models import DatesBase
            tables.extend(DatesBase.metadata.tables.values())
        if required_head == CATALOG_HEAD:
            from ..admin.sources.models import SourceBase
            tables.extend(SourceBase.metadata.tables.values())
        try:
            inspector = inspect(self.engine)
            required = {table.name for table in tables} | {"catalog_alembic_version"}
            if not required.issubset(inspector.get_table_names()):
                raise CatalogStoreError()
            for table in tables:
                if set(table.columns.keys()) != {column["name"] for column in inspector.get_columns(table.name)}:
                    raise CatalogStoreError()
            with self.engine.connect() as connection:
                heads = connection.execute(text("SELECT version_num FROM catalog_alembic_version")).scalars().all()
                if heads != [required_head]:
                    raise CatalogStoreError()
        except SQLAlchemyError:
            raise CatalogStoreError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction()
                or not session.is_active or not session.get_transaction().is_active):
            raise CatalogStoreError()
        try:
            # A default bind alone does not cover Session.binds overrides.
            for mapper in (None, CatalogDataset, CatalogInstitution, CatalogProgram,
                           AdmissionOffering, AdmissionOfferingVersion):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise CatalogStoreError()
            yield
        except IntegrityError:
            raise CatalogStoreError(409, "CATALOG_CONFLICT") from None
        except SQLAlchemyError:
            raise CatalogStoreError() from None

    def _dataset(self, session, identifier, *, expected_revision=None):
        query = select(CatalogDataset).where(CatalogDataset.id == _uuid(identifier))
        if expected_revision is not None:
            _version(expected_revision)
            query = query.with_for_update()
        row = session.execute(query.execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            raise CatalogStoreError(404, "NOT_FOUND")
        _output(DatasetData, row)
        if expected_revision is not None and row.revision != expected_revision:
            raise CatalogStoreError(409, "CATALOG_CONFLICT")
        return row

    @staticmethod
    def _advance(dataset):
        if dataset.revision >= MAX_VERSION:
            raise CatalogStoreError(409, "CATALOG_CONFLICT")
        dataset.revision += 1

    @staticmethod
    def _parent(session, model, identifier, dataset_id, is_synthetic):
        row = session.execute(select(model).where(model.id == identifier).with_for_update()
                              .execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            raise CatalogStoreError(404, "NOT_FOUND")
        if row.dataset_id != dataset_id or row.is_synthetic != is_synthetic:
            raise CatalogStoreError(409, "CATALOG_CONFLICT")
        return row

    @staticmethod
    def _matching_mode(dataset, data):
        if dataset.is_synthetic != data.is_synthetic:
            raise CatalogStoreError(409, "CATALOG_CONFLICT")

    def create_dataset(self, session: Session, data: DatasetInput) -> DatasetData:
        data = _input(DatasetInput, data)
        with self._work(session):
            row = CatalogDataset(**data.model_dump(), revision=1)
            session.add(row)
            session.flush()
            return _output(DatasetData, row)

    def create_institution(self, session: Session, data: InstitutionInput, *, expected_dataset_revision: int) -> InstitutionData:
        data = _input(InstitutionInput, data)
        with self._work(session):
            dataset = self._dataset(session, data.dataset_id, expected_revision=expected_dataset_revision)
            self._matching_mode(dataset, data)
            self._advance(dataset)
            row = CatalogInstitution(**data.model_dump())
            session.add(row)
            session.flush()
            return _output(InstitutionData, row)

    def create_program(self, session: Session, data: ProgramInput, *, expected_dataset_revision: int) -> ProgramData:
        data = _input(ProgramInput, data)
        with self._work(session):
            dataset = self._dataset(session, data.dataset_id, expected_revision=expected_dataset_revision)
            self._matching_mode(dataset, data)
            self._parent(session, CatalogInstitution, data.institution_id, data.dataset_id, data.is_synthetic)
            self._advance(dataset)
            fields = data.model_dump(exclude=set(PROGRAM_SCOPE_FIELDS))
            fields.update({f"{field}_key": getattr(data, field).canonical_key() for field in PROGRAM_SCOPE_FIELDS})
            row = CatalogProgram(**fields)
            session.add(row)
            session.flush()
            return _output(ProgramData, row, PROGRAM_SCOPE_FIELDS)

    def create_offering(self, session: Session, data: OfferingInput, *, expected_dataset_revision: int,
                        version_id: UUID) -> OfferingData:
        data = _input(OfferingInput, data)
        version_id = _uuid(version_id)
        with self._work(session):
            dataset = self._dataset(session, data.dataset_id, expected_revision=expected_dataset_revision)
            self._matching_mode(dataset, data)
            self._parent(session, CatalogProgram, data.program_id, data.dataset_id, data.is_synthetic)
            self._advance(dataset)
            fields = data.model_dump(exclude=set(OFFERING_SCOPE_FIELDS))
            fields.update({f"{field}_key": getattr(data, field).canonical_key() for field in OFFERING_SCOPE_FIELDS})
            row = AdmissionOffering(**fields, current_version=1)
            session.add(row)
            session.flush()
            session.add(AdmissionOfferingVersion(id=version_id, dataset_id=data.dataset_id, offering_id=data.id,
                                                version=1, is_synthetic=data.is_synthetic))
            session.flush()
            return _output(OfferingData, row, OFFERING_SCOPE_FIELDS)

    def append_offering_version(self, session: Session, offering_id: UUID, *, version_id: UUID,
                                expected_dataset_revision: int, expected_version: int) -> OfferingVersionData:
        offering_id, version_id = _uuid(offering_id), _uuid(version_id)
        expected_version = _version(expected_version)
        with self._work(session):
            dataset_id = session.execute(select(AdmissionOffering.dataset_id)
                                         .where(AdmissionOffering.id == offering_id)).scalar_one_or_none()
            if dataset_id is None:
                raise CatalogStoreError(404, "NOT_FOUND")
            dataset = self._dataset(session, dataset_id, expected_revision=expected_dataset_revision)
            offering = self._parent(session, AdmissionOffering, offering_id, dataset_id, dataset.is_synthetic)
            if offering.current_version != expected_version or expected_version >= MAX_VERSION:
                raise CatalogStoreError(409, "CATALOG_CONFLICT")
            _output(OfferingData, offering, OFFERING_SCOPE_FIELDS)
            self.get_offering_version(session, OfferingVersionRef(dataset_id=dataset_id, offering_id=offering_id,
                                                                  version=expected_version))
            self._advance(dataset)
            offering.current_version += 1
            row = AdmissionOfferingVersion(id=version_id, dataset_id=dataset_id, offering_id=offering_id,
                                           version=offering.current_version, is_synthetic=offering.is_synthetic)
            session.add(row)
            session.flush()
            return _output(OfferingVersionData, row)

    def get_dataset(self, session: Session, identifier: UUID) -> DatasetData:
        with self._work(session):
            return _output(DatasetData, self._dataset(session, identifier))

    def get_offering(self, session: Session, identifier: UUID) -> OfferingData:
        identifier = _uuid(identifier)
        with self._work(session):
            row = session.execute(select(AdmissionOffering).where(AdmissionOffering.id == identifier)
                                  .execution_options(populate_existing=True)).scalar_one_or_none()
            if row is None:
                raise CatalogStoreError(404, "NOT_FOUND")
            return _output(OfferingData, row, OFFERING_SCOPE_FIELDS)

    def get_offering_version(self, session: Session, reference: OfferingVersionRef) -> OfferingVersionData:
        reference = _input(OfferingVersionRef, reference)
        with self._work(session):
            row = session.execute(select(AdmissionOfferingVersion).where(
                AdmissionOfferingVersion.dataset_id == reference.dataset_id,
                AdmissionOfferingVersion.offering_id == reference.offering_id,
                AdmissionOfferingVersion.version == reference.version)
                .execution_options(populate_existing=True)).scalar_one_or_none()
            if row is None:
                raise CatalogStoreError(404, "NOT_FOUND")
            return _output(OfferingVersionData, row)
