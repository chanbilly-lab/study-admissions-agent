"""Same-engine batch staging; callers own commit and rollback boundaries."""

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ...admissions_catalog.models import AdmissionOffering, AdmissionOfferingVersion
from ...idempotency.store import utc_time
from ...ingestion.schemas import (ImportRequest, ImportResult, ImportServiceError, ParsedImport, ParsedRow,
                                  PARSER_SCHEMA_VERSION, ROW_FIELDS, RowError)
from .models import ImportBatch, ImportCandidateRow, ImportRowError

IMPORTS_HEAD = "0001_imports_t15"
_HEADS = {"auth_alembic_version": "0006_audit_t10", "catalog_alembic_version": "0003_catalog_sources_t13",
          "storage_alembic_version": "0001_storage_t14", "idempotency_alembic_version": "0001_idempotency_t49"}


def migration_config():
    return Config(str(Path(__file__).resolve().parents[3] / "imports_alembic.ini"))


def _parents_ready(connection):
    for table, head in _HEADS.items():
        if connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all() != [head]:
            raise ImportServiceError()


def migrate_imports(engine, target="head"):
    if (getattr(getattr(engine, "dialect", None), "name", None) != "postgresql"
        or target not in {"head", IMPORTS_HEAD}):
        raise ImportServiceError()
    try:
        with engine.begin() as connection:
            _parents_ready(connection)
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise ImportServiceError() from None


def _input(model, value):
    try:
        return model.model_validate(value)
    except (ValidationError, ValueError, TypeError):
        raise ImportServiceError(422) from None


class ImportsStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise ImportServiceError()
        self.engine = engine

    def assert_schema_ready(self):
        from .models import ImportsBase
        try:
            inspector = inspect(self.engine)
            tables = list(ImportsBase.metadata.tables.values())
            if not ({table.name for table in tables} | {"imports_alembic_version"}).issubset(inspector.get_table_names()):
                raise ImportServiceError()
            for table in tables:
                if {column["name"] for column in inspector.get_columns(table.name)} != set(table.columns.keys()):
                    raise ImportServiceError()
            with self.engine.connect() as connection:
                _parents_ready(connection)
                if connection.execute(text("SELECT version_num FROM imports_alembic_version")).scalars().all() != [IMPORTS_HEAD]:
                    raise ImportServiceError()
        except SQLAlchemyError:
            raise ImportServiceError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise ImportServiceError()
        try:
            for mapper in (None, ImportBatch, ImportCandidateRow, ImportRowError,
                           AdmissionOffering, AdmissionOfferingVersion):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise ImportServiceError()
            yield
        except IntegrityError:
            raise ImportServiceError(409) from None
        except SQLAlchemyError:
            raise ImportServiceError() from None

    def get(self, session, import_id, *, lock=True):
        if type(import_id) is not UUID:
            raise ImportServiceError(404)
        with self._work(session):
            query = select(ImportBatch).where(ImportBatch.id == import_id)
            if lock:
                query = query.with_for_update()
            row = session.scalar(query.execution_options(populate_existing=True))
            if row is None or row.status == "deleted":
                raise ImportServiceError(404)
            return row

    def natural(self, session, request):
        request = _input(ImportRequest, request)
        with self._work(session):
            return session.scalar(select(ImportBatch).where(ImportBatch.dataset_id == request.dataset_id,
                ImportBatch.source_id == request.source_id, ImportBatch.source_version == request.source_version,
                ImportBatch.file_sha256 == request.file_sha256, ImportBatch.format == request.format,
                ImportBatch.parser_schema_version == PARSER_SCHEMA_VERSION).with_for_update()
                .execution_options(populate_existing=True))

    def scope_errors(self, session, parsed, *, dataset_id, is_synthetic):
        parsed = _input(ParsedImport, parsed)
        errors = list(parsed.errors)
        with self._work(session):
            # Every scoped offering/version is locked in a deterministic order.
            for row in sorted(parsed.rows, key=lambda item: (str(item.offering_id), item.offering_version, item.row_number)):
                try:
                    row.validate_namespace(is_synthetic)
                except (ValueError, TypeError):
                    errors.append(RowError(row_number=row.row_number, field="source_record_reference", code="NAMESPACE_MISMATCH"))
                parent = session.scalar(select(AdmissionOffering).where(AdmissionOffering.id == row.offering_id,
                    AdmissionOffering.dataset_id == dataset_id).with_for_update()
                    .execution_options(populate_existing=True))
                version = session.scalar(select(AdmissionOfferingVersion).where(
                    AdmissionOfferingVersion.dataset_id == dataset_id, AdmissionOfferingVersion.offering_id == row.offering_id,
                    AdmissionOfferingVersion.version == row.offering_version).with_for_update()
                    .execution_options(populate_existing=True))
                field = ("offering_id" if parent is None or parent.is_synthetic != is_synthetic else
                         "offering_version" if version is None or version.is_synthetic != is_synthetic else
                         "entry_year" if parent.entry_year != row.entry_year else None)
                if field is not None:
                    errors.append(RowError(row_number=row.row_number, field=field, code="SCOPE_MISMATCH"))
        unique = {(error.row_number, error.field, error.code): error for error in errors}
        return tuple(unique[key] for key in sorted(unique))

    def create(self, session, request, file_data, parsed, errors, *, actor_user_id, now):
        request, parsed = _input(ImportRequest, request), _input(ParsedImport, parsed)
        errors = tuple(_input(RowError, error) for error in errors)
        with self._work(session):
            row = ImportBatch(id=uuid4(), dataset_id=request.dataset_id, source_id=request.source_id,
                source_version=request.source_version, file_id=request.file_id, file_sha256=request.file_sha256,
                file_size=file_data.size_bytes, format=request.format, parser_schema_version=PARSER_SCHEMA_VERSION,
                status="rejected" if errors else "staged", version=1, total_rows=parsed.total_rows,
                staged_rows=0 if errors else len(parsed.rows), error_count=len(errors), actor_user_id=actor_user_id,
                is_synthetic=file_data.is_synthetic, created_at=utc_time(now))
            session.add(row)
            session.flush()
            if errors:
                session.add_all(ImportRowError(import_id=row.id, **error.model_dump()) for error in errors)
            else:
                session.add_all(ImportCandidateRow(id=uuid4(), import_id=row.id, dataset_id=request.dataset_id,
                    is_synthetic=file_data.is_synthetic, **candidate.model_dump(), review_state="draft",
                    evidence_state="unresolved") for candidate in parsed.rows)
            session.flush()
            self.result(session, row)
            return row

    def result(self, session, row, *, replayed=False):
        with self._work(session):
            if row.status == "deleted":
                raise ImportServiceError(404)
            try:
                errors = tuple(RowError(row_number=error.row_number, field=error.field, code=error.code)
                    for error in session.scalars(select(ImportRowError).where(ImportRowError.import_id == row.id)
                        .order_by(ImportRowError.row_number, ImportRowError.field, ImportRowError.code)).all())
                candidates = session.scalars(select(ImportCandidateRow).where(ImportCandidateRow.import_id == row.id)
                    .order_by(ImportCandidateRow.row_number).with_for_update()
                    .execution_options(populate_existing=True)).all()
                if (row.version != 1 or row.parser_schema_version != PARSER_SCHEMA_VERSION
                    or len(candidates) != row.staged_rows or any(candidate.review_state != "draft"
                        or candidate.evidence_state != "unresolved" for candidate in candidates)):
                    raise ImportServiceError()
                staged_rows = []
                for candidate in candidates:
                    staged = ParsedRow(**{name: getattr(candidate, name) for name in (*ROW_FIELDS, "row_number")})
                    if candidate.dataset_id != row.dataset_id or candidate.is_synthetic != row.is_synthetic:
                        raise ImportServiceError()
                    staged_rows.append(staged)
                if staged_rows:
                    start = 1 if row.format == "json" else 2
                    if tuple(item.row_number for item in staged_rows) != tuple(range(start, start + len(staged_rows))):
                        raise ImportServiceError()
                    scoped = ParsedImport(rows=tuple(staged_rows), errors=(), total_rows=row.total_rows)
                    if self.scope_errors(session, scoped, dataset_id=row.dataset_id, is_synthetic=row.is_synthetic):
                        raise ImportServiceError()
                return ImportResult(id=row.id, status=row.status, total_rows=row.total_rows,
                    staged_rows=row.staged_rows, error_count=row.error_count, errors=errors, replayed=replayed)
            except (ValidationError, ValueError, TypeError, AttributeError):
                raise ImportServiceError() from None
