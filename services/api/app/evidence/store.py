"""Caller-owned PostgreSQL work and exact immutable evidence references."""

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..admissions_catalog.models import (AdmissionOffering, AdmissionOfferingVersion, CatalogInstitution,
                                        CatalogProgram, OFFERING_SCOPE_FIELDS, PROGRAM_SCOPE_FIELDS)
from ..admissions_catalog.schemas import MAX_VERSION, ScopeKey
from .models import Document, DocumentVersion, EvidenceBase, EvidenceSnippet
from .schemas import (DocumentCreate, DocumentData, EVIDENCE_HEAD, EvidenceError, EvidenceLocator,
                      EvidenceScope, LocatedSnippet, OriginalData, SnippetCreate, SnippetData,
                      VersionCreate, VersionData)

_HEADS = {"auth_alembic_version": "0006_audit_t10", "catalog_alembic_version": "0003_catalog_sources_t13",
          "storage_alembic_version": "0001_storage_t14"}


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2] / "evidence_alembic.ini"))


def _parents_ready(connection):
    for table, head in _HEADS.items():
        if connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all() != [head]:
            raise EvidenceError()


def migrate_evidence(engine, target="head"):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql" or target not in {"head", EVIDENCE_HEAD}:
        raise EvidenceError()
    try:
        with engine.begin() as connection:
            _parents_ready(connection)
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise EvidenceError() from None


def _input(model, value):
    try:
        return model.model_validate(value)
    except (ValidationError, ValueError, TypeError):
        raise EvidenceError(422) from None


def utc_time(value):
    try:
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None or value.fold:
            raise ValueError()
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise EvidenceError() from None


def scope_hash(scope):
    scope = _input(EvidenceScope, scope)
    encoded = json.dumps(scope.model_dump(mode="json"), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


class EvidenceStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise EvidenceError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            tables = list(EvidenceBase.metadata.tables.values())
            if not ({table.name for table in tables} | {"evidence_alembic_version"}).issubset(inspector.get_table_names()):
                raise EvidenceError()
            for table in tables:
                if {column["name"] for column in inspector.get_columns(table.name)} != set(table.columns.keys()):
                    raise EvidenceError()
            with self.engine.connect() as connection:
                _parents_ready(connection)
                if connection.execute(text("SELECT version_num FROM evidence_alembic_version")).scalars().all() != [EVIDENCE_HEAD]:
                    raise EvidenceError()
                triggers = connection.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal "
                    "AND tgenabled='O' AND tgrelid IN (to_regclass('evidence_document_versions'),to_regclass('evidence_snippets'))")).scalars().all()
                if set(triggers) != {"evidence_versions_immutable", "evidence_snippets_immutable"}:
                    raise EvidenceError()
        except SQLAlchemyError:
            raise EvidenceError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise EvidenceError()
        try:
            for mapper in (None, Document, DocumentVersion, EvidenceSnippet, AdmissionOffering,
                           AdmissionOfferingVersion, CatalogProgram, CatalogInstitution):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise EvidenceError()
            yield
        except IntegrityError:
            raise EvidenceError(409) from None
        except SQLAlchemyError:
            raise EvidenceError() from None

    @staticmethod
    def document_data(row):
        try:
            fields = {name: getattr(row, name) for name in DocumentData.model_fields}
            fields["created_at"] = utc_time(fields["created_at"])
            return DocumentData.model_validate(fields)
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise EvidenceError() from None

    @staticmethod
    def version_data(row):
        try:
            fields = {name: getattr(row, name) for name in VersionData.model_fields}
            fields["created_at"] = utc_time(fields["created_at"])
            return VersionData.model_validate(fields)
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise EvidenceError() from None

    def get_document(self, session, identifier, *, lock=True):
        if type(identifier) is not UUID:
            raise EvidenceError(404)
        with self._work(session):
            query = select(Document).where(Document.id == identifier)
            row = session.scalar((query.with_for_update() if lock else query).execution_options(populate_existing=True))
            if row is None:
                raise EvidenceError(404)
            self.document_data(row)
            return row

    def get_version(self, session, document_id, version, *, lock=True):
        if type(document_id) is not UUID or type(version) is not int or not 1 <= version <= MAX_VERSION:
            raise EvidenceError(404)
        with self._work(session):
            query = select(DocumentVersion).where(DocumentVersion.document_id == document_id, DocumentVersion.version == version)
            row = session.scalar((query.with_for_update() if lock else query).execution_options(populate_existing=True))
            if row is None:
                raise EvidenceError(404)
            self.version_data(row)
            return row

    def get_snippet(self, session, identifier, *, lock=True):
        if type(identifier) is not UUID:
            raise EvidenceError(404)
        with self._work(session):
            query = select(EvidenceSnippet).where(EvidenceSnippet.id == identifier)
            row = session.scalar((query.with_for_update() if lock else query).execution_options(populate_existing=True))
            if row is None:
                raise EvidenceError(404)
            return row

    def create_document(self, session, data, *, is_synthetic, now):
        data = _input(DocumentCreate, data)
        try:
            data.validate_namespace(is_synthetic)
        except (ValueError, TypeError):
            raise EvidenceError(422) from None
        with self._work(session):
            row = session.scalar(select(Document).where(Document.dataset_id == data.dataset_id,
                Document.source_id == data.source_id, Document.source_version == data.source_version,
                Document.document_reference == data.document_reference).with_for_update()
                .execution_options(populate_existing=True))
            if row is not None:
                if row.language != data.language or row.is_synthetic != is_synthetic:
                    raise EvidenceError(409)
                return row
            row = Document(**data.model_dump(), id=uuid4(), is_synthetic=is_synthetic,
                           current_version=0, created_at=utc_time(now))
            session.add(row)
            session.flush()
            self.document_data(row)
            return row

    def append_version(self, session, data, original, *, now):
        data, original = _input(VersionCreate, data), _input(OriginalData, original)
        with self._work(session):
            root = self.get_document(session, data.document_id)
            if root.current_version != data.expected_current_version or original.sha256 != data.file_sha256:
                raise EvidenceError(409)
            existing = session.scalar(select(DocumentVersion).where(DocumentVersion.document_id == root.id,
                DocumentVersion.document_sha256 == original.sha256).with_for_update()
                .execution_options(populate_existing=True))
            if existing is not None:
                if existing.size_bytes != original.size_bytes or existing.media_type != original.media_type:
                    raise EvidenceError(409)
                return existing
            if root.current_version >= MAX_VERSION:
                raise EvidenceError(409)
            root.current_version += 1
            row = DocumentVersion(id=uuid4(), document_id=root.id, dataset_id=root.dataset_id,
                version=root.current_version, file_id=data.file_id, document_sha256=original.sha256,
                size_bytes=original.size_bytes, media_type=original.media_type, is_synthetic=root.is_synthetic,
                created_at=utc_time(now))
            session.add(row)
            session.flush()
            self.version_data(row)
            return row

    def scope(self, session, *, dataset_id, offering_id, offering_version, entry_year, is_synthetic):
        with self._work(session):
            offering = session.scalar(select(AdmissionOffering).where(AdmissionOffering.id == offering_id,
                AdmissionOffering.dataset_id == dataset_id).with_for_update().execution_options(populate_existing=True))
            version = session.scalar(select(AdmissionOfferingVersion).where(AdmissionOfferingVersion.dataset_id == dataset_id,
                AdmissionOfferingVersion.offering_id == offering_id, AdmissionOfferingVersion.version == offering_version)
                .with_for_update().execution_options(populate_existing=True))
            if (offering is None or version is None or offering.is_synthetic != is_synthetic
                or version.is_synthetic != is_synthetic or offering.entry_year != entry_year):
                raise EvidenceError(409)
            program = session.scalar(select(CatalogProgram).where(CatalogProgram.id == offering.program_id,
                CatalogProgram.dataset_id == dataset_id, CatalogProgram.is_synthetic == is_synthetic)
                .with_for_update().execution_options(populate_existing=True))
            if program is None:
                raise EvidenceError(409)
            institution = session.scalar(select(CatalogInstitution).where(CatalogInstitution.id == program.institution_id,
                CatalogInstitution.dataset_id == dataset_id, CatalogInstitution.is_synthetic == is_synthetic)
                .with_for_update().execution_options(populate_existing=True))
            if institution is None:
                raise EvidenceError(409)
            try:
                fields = {field: ScopeKey.from_canonical_key(getattr(program, field + "_key")) for field in PROGRAM_SCOPE_FIELDS}
                fields.update({field: ScopeKey.from_canonical_key(getattr(offering, field + "_key")) for field in OFFERING_SCOPE_FIELDS})
                return EvidenceScope(dataset_id=dataset_id, institution_id=institution.id, program_id=program.id,
                    country=institution.country, study_level=program.study_level, entry_year=offering.entry_year, **fields)
            except (ValidationError, ValueError, TypeError):
                raise EvidenceError() from None

    def create_snippet(self, session, data, located, *, now):
        data, located = _input(SnippetCreate, data), _input(LocatedSnippet, located)
        if (located.locator.byte_start, located.locator.byte_end) != (data.byte_start, data.byte_end):
            raise EvidenceError(409)
        with self._work(session):
            document = self.get_document(session, data.document_id)
            version = self.get_version(session, document.id, data.document_version)
            if located.locator.byte_end > version.size_bytes:
                raise EvidenceError(422)
            scope = self.scope(session, dataset_id=document.dataset_id, offering_id=data.offering_id,
                offering_version=data.offering_version, entry_year=data.entry_year, is_synthetic=document.is_synthetic)
            row = session.scalar(select(EvidenceSnippet).where(EvidenceSnippet.document_id == document.id,
                EvidenceSnippet.document_version == version.version, EvidenceSnippet.offering_id == data.offering_id,
                EvidenceSnippet.offering_version == data.offering_version, EvidenceSnippet.byte_start == data.byte_start,
                EvidenceSnippet.byte_end == data.byte_end).with_for_update().execution_options(populate_existing=True))
            if row is not None:
                if row.scope_sha256 != scope_hash(scope) or row.snippet_sha256 != located.snippet_sha256 or row.text != located.text:
                    raise EvidenceError(409)
                return row
            row = EvidenceSnippet(id=uuid4(), **data.model_dump(), dataset_id=document.dataset_id,
                language=document.language, line_start=located.locator.line_start, line_end=located.locator.line_end,
                text=located.text, snippet_sha256=located.snippet_sha256, scope_sha256=scope_hash(scope),
                is_synthetic=document.is_synthetic, created_at=utc_time(now))
            session.add(row)
            session.flush()
            return row

    def snippet_data(self, session, row):
        with self._work(session):
            document = self.get_document(session, row.document_id)
            version = self.get_version(session, row.document_id, row.document_version)
            scope = self.scope(session, dataset_id=row.dataset_id, offering_id=row.offering_id,
                offering_version=row.offering_version, entry_year=row.entry_year, is_synthetic=row.is_synthetic)
            if (row.scope_sha256 != scope_hash(scope) or document.dataset_id != row.dataset_id
                or version.dataset_id != row.dataset_id or row.is_synthetic != document.is_synthetic
                or version.is_synthetic != row.is_synthetic or row.language != document.language
                or row.byte_end > version.size_bytes):
                raise EvidenceError(409)
            try:
                return SnippetData(id=row.id, document_id=row.document_id, document_version=row.document_version,
                    offering_id=row.offering_id, offering_version=row.offering_version, entry_year=row.entry_year,
                    language=row.language, document_sha256=version.document_sha256, snippet_sha256=row.snippet_sha256,
                    text=row.text, is_synthetic=row.is_synthetic, created_at=utc_time(row.created_at), scope=scope,
                    locator=EvidenceLocator(byte_start=row.byte_start, byte_end=row.byte_end, line_start=row.line_start,
                        line_end=row.line_end, page=None, section=None, location_kind="utf8_byte_lines"))
            except (ValidationError, ValueError, TypeError, AttributeError):
                raise EvidenceError() from None
