"""Caller-owned immutable candidate storage and bounded conflict discovery."""

from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import func, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..admin.imports.models import ImportBatch, ImportCandidateRow
from ..admissions_catalog.models import AdmissionOffering
from ..evidence.store import utc_time
from .models import FactCandidate, FactConflict, FactsBase
from .schemas import Classification, FACTS_HEAD, FactsError, TypedCandidate, TypedPayload


_HEADS = {"auth_alembic_version": "0006_audit_t10", "catalog_alembic_version": "0003_catalog_sources_t13",
          "storage_alembic_version": "0001_storage_t14", "imports_alembic_version": "0001_imports_t15",
          "evidence_alembic_version": "0001_evidence_t16"}
MAX_CONFLICTS = 200


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2] / "facts_alembic.ini"))


def _parents_ready(connection):
    for table, head in _HEADS.items():
        if connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all() != [head]:
            raise FactsError()


def migrate_facts(engine, target="head"):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql" or target not in {"head", FACTS_HEAD}:
        raise FactsError()
    try:
        with engine.begin() as connection:
            _parents_ready(connection)
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise FactsError() from None


def _input(model, value):
    try:
        return model.model_validate(value)
    except (ValidationError, ValueError, TypeError):
        raise FactsError(422) from None


def fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def identities(import_row_id, payload, *, dataset_id):
    payload = _input(TypedPayload, payload)
    classification = payload.classification.model_dump(mode="json")
    natural = fingerprint({"row": str(import_row_id), "classification": classification,
                           "evidence_id": str(payload.evidence_id) if payload.evidence_id else None})
    date_context = None
    if payload.date_resolution is not None:
        date_context = {field: getattr(payload.date_resolution, field)
                        for field in ("event_type", "precision", "timezone")}
    logical = fingerprint({"dataset_id": str(dataset_id), "offering_id": str(payload.offering_id),
        "offering_version": payload.offering_version, "field_key": payload.field_key,
        "fact_type": payload.fact_type, "classification": {key: value for key, value in classification.items()
            if key != "date_event_id"}, "date_context": date_context})
    values = {"value": payload.normalized_value, "value_kind": payload.value_kind, "missing_reason": payload.missing_reason,
              "unit_original": payload.unit, "footnote_state": payload.footnote_state,
              "footnote_text": payload.footnote_text}
    if payload.date_resolution is not None:
        values["date_values"] = {key: value for key, value in payload.date_resolution.model_dump(mode="json").items()
            if key in {"local_date", "local_time", "calculated_utc_instant", "utc_instant", "source_alignment"}}
    return fingerprint(classification), natural, logical, fingerprint(values)


class FactsStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise FactsError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            tables = list(FactsBase.metadata.tables.values())
            if not ({table.name for table in tables} | {"facts_alembic_version"}).issubset(inspector.get_table_names()):
                raise FactsError()
            for table in tables:
                if {column["name"] for column in inspector.get_columns(table.name)} != set(table.columns.keys()):
                    raise FactsError()
            with self.engine.connect() as connection:
                _parents_ready(connection)
                if connection.execute(text("SELECT version_num FROM facts_alembic_version")).scalars().all() != [FACTS_HEAD]:
                    raise FactsError()
                triggers = connection.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal "
                    "AND tgenabled='O' AND tgrelid IN (to_regclass('fact_candidates'),to_regclass('fact_conflicts'))")).scalars().all()
                if set(triggers) != {"facts_candidates_immutable", "facts_conflicts_immutable"}:
                    raise FactsError()
        except SQLAlchemyError:
            raise FactsError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise FactsError()
        try:
            for mapper in (None, FactCandidate, FactConflict, ImportBatch, ImportCandidateRow, AdmissionOffering):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise FactsError()
            yield
        except IntegrityError:
            raise FactsError(409) from None
        except SQLAlchemyError:
            raise FactsError() from None

    def get(self, session, fact_id, *, lock=True):
        if type(fact_id) is not UUID:
            raise FactsError(404)
        with self._work(session):
            query = select(FactCandidate).where(FactCandidate.id == fact_id)
            row = session.scalar((query.with_for_update() if lock else query).execution_options(populate_existing=True))
            if row is None:
                raise FactsError(404)
            return row

    def classification(self, row):
        try:
            return Classification.model_validate(row.payload["classification"])
        except (ValidationError, ValueError, TypeError, KeyError, AttributeError):
            raise FactsError() from None

    def conflicts(self, session, fact_id, *, now=None):
        with self._work(session):
            pairs = session.scalars(select(FactConflict).where(
                or_(FactConflict.left_id == fact_id, FactConflict.right_id == fact_id))
                .order_by(FactConflict.left_id, FactConflict.right_id).limit(MAX_CONFLICTS + 1)
                .execution_options(populate_existing=True)).all()
            if len(pairs) > MAX_CONFLICTS:
                raise FactsError()
            if now is not None and any(utc_time(pair.created_at) > utc_time(now) for pair in pairs):
                raise FactsError(409)
            return tuple(sorted((pair.right_id if pair.left_id == fact_id else pair.left_id for pair in pairs), key=str))

    def create(self, session, *, batch, import_row, payload, row_sha256, scope_sha256,
               date_sha256, evidence_sha256, now):
        payload = _input(TypedPayload, payload)
        classification_hash, natural, logical, value_hash = identities(import_row.id, payload, dataset_id=batch.dataset_id)
        with self._work(session):
            # All candidates for one exact offering share this lock, including
            # different batches and source-responsible actors. No lost edges.
            parent = session.scalar(select(AdmissionOffering).where(AdmissionOffering.id == payload.offering_id,
                AdmissionOffering.dataset_id == batch.dataset_id).with_for_update().execution_options(populate_existing=True))
            if parent is None or parent.is_synthetic != batch.is_synthetic or parent.entry_year != payload.entry_year:
                raise FactsError(409)
            existing = session.scalar(select(FactCandidate).where(FactCandidate.natural_key_hash == natural)
                .with_for_update().execution_options(populate_existing=True))
            if existing is not None:
                self.data(session, existing, payload, row_sha256=row_sha256, scope_sha256=scope_sha256,
                          date_sha256=date_sha256, evidence_sha256=evidence_sha256)
                return existing
            differing = session.scalars(select(FactCandidate).where(FactCandidate.logical_key_hash == logical,
                FactCandidate.value_hash != value_hash).order_by(FactCandidate.id).limit(MAX_CONFLICTS + 1)
                .with_for_update().execution_options(populate_existing=True)).all()
            if len(differing) > MAX_CONFLICTS:
                raise FactsError(409)
            for peer in differing:
                if len(self.conflicts(session, peer.id)) >= MAX_CONFLICTS:
                    raise FactsError(409)
            row = FactCandidate(id=uuid4(), version=1, import_id=batch.id, import_row_id=import_row.id,
                dataset_id=batch.dataset_id, offering_id=payload.offering_id, offering_version=payload.offering_version,
                entry_year=payload.entry_year, evidence_id=payload.evidence_id,
                date_event_id=payload.classification.date_event_id, payload=payload.model_dump(mode="json"),
                classification_hash=classification_hash, natural_key_hash=natural, logical_key_hash=logical,
                value_hash=value_hash, row_sha256=row_sha256, scope_sha256=scope_sha256,
                date_sha256=date_sha256, evidence_sha256=evidence_sha256, is_synthetic=batch.is_synthetic,
                created_at=utc_time(now))
            session.add(row)
            session.flush()
            for peer in differing:
                left, right = sorted((row.id, peer.id), key=str)
                session.add(FactConflict(id=uuid4(), left_id=left, right_id=right,
                    logical_key_hash=logical, created_at=utc_time(now)))
            session.flush()
            return row

    def data(self, session, row, payload, *, row_sha256, scope_sha256, date_sha256, evidence_sha256, now=None):
        payload = _input(TypedPayload, payload)
        calculated = identities(row.import_row_id, payload, dataset_id=row.dataset_id)
        if (row.version != 1 or row.payload != payload.model_dump(mode="json")
            or (row.classification_hash, row.natural_key_hash, row.logical_key_hash, row.value_hash) != calculated
            or (row.row_sha256, row.scope_sha256, row.date_sha256, row.evidence_sha256) !=
               (row_sha256, scope_sha256, date_sha256, evidence_sha256)
            or (row.offering_id, row.offering_version, row.entry_year, row.evidence_id, row.date_event_id) !=
               (payload.offering_id, payload.offering_version, payload.entry_year,
                payload.evidence_id, payload.classification.date_event_id)):
            raise FactsError(409)
        try:
            if now is not None and utc_time(row.created_at) > utc_time(now):
                raise FactsError(409)
            conflicting_ids = self.conflicts(session, row.id, now=now)
            fields = payload.model_dump()
            fields["state"] = "conflicted" if conflicting_ids else payload.state
            return TypedCandidate(**fields, id=row.id, version=row.version, import_id=row.import_id,
                import_row_id=row.import_row_id, dataset_id=row.dataset_id, is_synthetic=row.is_synthetic,
                created_at=utc_time(row.created_at), conflicting_ids=conflicting_ids)
        except FactsError:
            raise
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise FactsError() from None
