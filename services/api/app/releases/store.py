"""Caller-owned atomic release history, CAS visibility and pending outbox rows."""

from contextlib import contextmanager
from datetime import date, datetime, time
import re
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..admin.sources.models import CatalogSourceVersion
from ..admissions_catalog.models import AdmissionOfferingVersion, CatalogDataset
from ..admissions_catalog.schemas import DatasetData, MAX_VERSION
from ..auth.authorization import Principal
from ..evidence.models import EvidenceSnippet
from ..evidence.schemas import SnippetData
from ..evidence.store import scope_hash, utc_time
from ..facts.models import FactCandidate
from ..facts.schemas import TypedCandidate
from ..facts.store import fingerprint
from ..reviews.models import ReviewDecision
from ..storage.models import StorageObject
from .models import (CatalogRelease, CatalogReleaseMember, CatalogReleaseState, ChangeEvent,
                     OutboxEvent, ReleasesBase)
from .schemas import (MAX_MEMBERS, PublishRequest, ReleaseData, ReleaseMemberData,
                      RELEASES_HEAD, ReleasesError, WithdrawalRequest)
from .validation import release_content_hash, requirements_snapshot_hash, validate_release


_HEADS = {"auth_alembic_version": "0006_audit_t10", "catalog_alembic_version": "0003_catalog_sources_t13",
          "storage_alembic_version": "0001_storage_t14", "imports_alembic_version": "0001_imports_t15",
          "evidence_alembic_version": "0001_evidence_t16", "facts_alembic_version": "0001_facts_t17",
          "reviews_alembic_version": "0001_reviews_t18", "idempotency_alembic_version": "0001_idempotency_t49"}
_HASH = re.compile(r"[0-9a-f]{64}")


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2] / "releases_alembic.ini"))


def _parents_ready(connection):
    for table, head in _HEADS.items():
        if connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all() != [head]:
            raise ReleasesError()


def migrate_releases(engine, target="head"):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql" or target not in {"head", RELEASES_HEAD}:
        raise ReleasesError()
    try:
        with engine.begin() as connection:
            _parents_ready(connection)
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise ReleasesError() from None


def _input(model, value):
    try:
        return model.model_validate(value)
    except (ValidationError, ValueError, TypeError, OverflowError):
        raise ReleasesError(422) from None


def _timestamp(value):
    if type(value) is not str or len(value) > 64:
        raise ValueError("a captured canonical timestamp is required")
    return datetime.fromisoformat(value)


def _captured_snapshot(raw):
    """Decode only known captured native date fields, then compare canonical JSON."""
    if type(raw) is not dict or set(raw) != {"fact", "evidence"}:
        raise ValueError("an exact captured fact and evidence snapshot is required")
    if type(raw["fact"]) is not dict or type(raw["evidence"]) is not dict:
        raise ValueError("bounded captured objects are required")
    fields = dict(raw["fact"])
    fields["created_at"] = _timestamp(fields.get("created_at"))
    if fields.get("date_resolution") is not None:
        original = fields["date_resolution"]
        if type(original) is not dict:
            raise ValueError("a captured date snapshot is required")
        native = dict(original)
        if native.get("local_date") is not None:
            if type(native["local_date"]) is not str or len(native["local_date"]) > 10:
                raise ValueError("a captured canonical local date is required")
            native["local_date"] = date.fromisoformat(native["local_date"])
        if native.get("local_time") is not None:
            if type(native["local_time"]) is not str or len(native["local_time"]) > 32:
                raise ValueError("a captured canonical local time is required")
            native["local_time"] = time.fromisoformat(native["local_time"])
        if native.get("calculated_utc_instant") is not None:
            native["calculated_utc_instant"] = _timestamp(native["calculated_utc_instant"])
        fields["date_resolution"] = native
    fact = TypedCandidate.model_validate(fields)
    evidence_fields = dict(raw["evidence"])
    evidence_fields["created_at"] = _timestamp(evidence_fields.get("created_at"))
    evidence = SnippetData.model_validate(evidence_fields)
    if fact.model_dump(mode="json") != raw["fact"] or evidence.model_dump(mode="json") != raw["evidence"]:
        raise ValueError("captured snapshots must use the exact canonical serialized DTO")
    return fact, evidence


def _snapshot_matches(member, raw, *, dataset_id, is_synthetic, published_at):
    fact, evidence = _captured_snapshot(raw)
    if ((fact.id, fact.dataset_id, fact.offering_id, fact.offering_version, fact.entry_year, fact.is_synthetic, fact.evidence_id) !=
        (member.fact_id, dataset_id, member.offering_id, member.offering_version, member.entry_year, is_synthetic, member.evidence_id)
        or (evidence.id, evidence.offering_id, evidence.offering_version, evidence.entry_year, evidence.is_synthetic) !=
           (member.evidence_id, member.offering_id, member.offering_version, member.entry_year, is_synthetic)
        or evidence.scope.dataset_id != dataset_id or evidence.document_sha256 != member.file_sha256
        or fingerprint(fact.model_dump(mode="json")) != member.fact_sha256
        or fingerprint(evidence.model_dump(mode="json")) != member.evidence_sha256
        or scope_hash(evidence.scope) != member.scope_sha256
        or fact.created_at > published_at or evidence.created_at > published_at):
        raise ValueError("captured metadata must match the exact immutable member")
    # Re-serialization gives SQLAlchemy an owned bounded copy, not caller dicts.
    return {"fact": fact.model_dump(mode="json"), "evidence": evidence.model_dump(mode="json")}


class ReleasesStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise ReleasesError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            tables = list(ReleasesBase.metadata.tables.values())
            if not ({table.name for table in tables} | {"releases_alembic_version"}).issubset(inspector.get_table_names()):
                raise ReleasesError()
            for table in tables:
                if {column["name"] for column in inspector.get_columns(table.name)} != set(table.columns.keys()):
                    raise ReleasesError()
            with self.engine.connect() as connection:
                _parents_ready(connection)
                if connection.execute(text("SELECT version_num FROM releases_alembic_version")).scalars().all() != [RELEASES_HEAD]:
                    raise ReleasesError()
                triggers = connection.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgenabled='O' "
                    "AND tgrelid IN (to_regclass('catalog_releases'),to_regclass('catalog_release_members'),"
                    "to_regclass('catalog_change_events'))")).scalars().all()
                if set(triggers) != {"releases_root_immutable", "releases_members_immutable", "releases_events_immutable"}:
                    raise ReleasesError()
                published_index = connection.execute(text("SELECT i.indisunique, i.indisvalid, i.indisready, "
                    "pg_get_indexdef(i.indexrelid), pg_get_expr(i.indpred,i.indrelid) FROM pg_index i "
                    "WHERE i.indexrelid=to_regclass('uq_release_current_published') "
                    "AND i.indrelid=to_regclass('catalog_release_states')")).all()
                if (len(published_index) != 1 or published_index[0][:3] != (True, True, True)
                    or "(dataset_id, entry_year)" not in published_index[0][3]
                    or published_index[0][4] != "((status)::text = 'published'::text)"):
                    raise ReleasesError()
        except SQLAlchemyError:
            raise ReleasesError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise ReleasesError()
        try:
            for mapper in (None, CatalogRelease, CatalogReleaseMember, CatalogReleaseState, ChangeEvent, OutboxEvent,
                CatalogDataset, AdmissionOfferingVersion, FactCandidate, ReviewDecision, CatalogSourceVersion,
                EvidenceSnippet, StorageObject):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise ReleasesError()
            yield
        except IntegrityError as error:
            # Explicit CAS checks handle ordinary conflicts. A required event,
            # outbox or FK write failure is an unavailable transaction, not a
            # misleading user conflict; only the two genuine unique-head races
            # have the conflict meaning.
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            sqlstate = getattr(error.orig, "sqlstate", None)
            if sqlstate == "23505" and constraint in {"uq_release_content", "uq_release_current_published"}:
                raise ReleasesError(409) from None
            raise ReleasesError() from None
        except SQLAlchemyError:
            raise ReleasesError() from None

    def dataset(self, session, dataset_id):
        if type(dataset_id) is not UUID:
            raise ReleasesError(404)
        with self._work(session):
            row = session.scalar(select(CatalogDataset).where(CatalogDataset.id == dataset_id)
                .with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise ReleasesError(404)
            try:
                DatasetData.model_validate({name: getattr(row, name) for name in DatasetData.model_fields})
            except (ValidationError, ValueError, TypeError, AttributeError):
                raise ReleasesError() from None
            return row

    def get(self, session, release_id, *, lock=True):
        if type(release_id) is not UUID:
            raise ReleasesError(404)
        with self._work(session):
            query = select(CatalogRelease).where(CatalogRelease.id == release_id)
            row = session.scalar((query.with_for_update() if lock else query).execution_options(populate_existing=True))
            if row is None:
                raise ReleasesError(404)
            return row

    def state(self, session, release_id):
        if type(release_id) is not UUID:
            raise ReleasesError(404)
        with self._work(session):
            row = session.scalar(select(CatalogReleaseState).where(CatalogReleaseState.release_id == release_id)
                .with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise ReleasesError()
            return row

    def members(self, session, release_id):
        if type(release_id) is not UUID:
            raise ReleasesError(404)
        with self._work(session):
            rows = tuple(session.scalars(select(CatalogReleaseMember).where(CatalogReleaseMember.release_id == release_id)
                .order_by(CatalogReleaseMember.fact_id).limit(MAX_MEMBERS + 1).with_for_update()
                .execution_options(populate_existing=True)).all())
            if not 1 <= len(rows) <= MAX_MEMBERS:
                raise ReleasesError()
            return rows

    def natural(self, session, content_hash):
        if type(content_hash) is not str or _HASH.fullmatch(content_hash) is None:
            raise ReleasesError(422)
        with self._work(session):
            return session.scalar(select(CatalogRelease).where(CatalogRelease.content_sha256 == content_hash)
                .with_for_update().execution_options(populate_existing=True))

    def current(self, session, dataset_id, entry_year):
        if type(dataset_id) is not UUID or type(entry_year) is not int or not 1 <= entry_year <= 9999:
            raise ReleasesError(422)
        with self._work(session):
            rows = session.scalars(select(CatalogReleaseState).where(CatalogReleaseState.dataset_id == dataset_id,
                CatalogReleaseState.entry_year == entry_year, CatalogReleaseState.status == "published")
                .limit(2).with_for_update().execution_options(populate_existing=True)).all()
            if len(rows) > 1:
                raise ReleasesError()
            return rows[0] if rows else None

    def _event(self, session, root, state, *, actor, audit_event_id, now, related_release_id=None, reason_code=None):
        event = ChangeEvent(id=uuid4(), release_id=root.id, dataset_id=root.dataset_id,
            entry_year=root.entry_year, is_synthetic=root.is_synthetic, event_type=state.status,
            state_revision=state.revision, related_release_id=related_release_id, reason_code=reason_code,
            actor_user_id=actor.user_id, audit_event_id=audit_event_id, created_at=now)
        session.add(event)
        session.flush()
        session.add(OutboxEvent(id=uuid4(), event_id=event.id, status="pending", created_at=now))
        session.flush()

    def create(self, session, request, members, *, snapshots, actor, audit_event_id, now):
        request, actor = _input(PublishRequest, request), _input(Principal, actor)
        with self._work(session):
            dataset = self.dataset(session, request.dataset_id)
            if (dataset.revision != request.expected_dataset_revision or dataset.revision >= MAX_VERSION
                or dataset.is_synthetic != actor.is_synthetic):
                raise ReleasesError(409)
            members = validate_release(request, members, is_synthetic=dataset.is_synthetic)
            now = utc_time(now)
            if type(audit_event_id) is not UUID or type(snapshots) is not tuple or len(snapshots) != len(members):
                raise ReleasesError(422)
            captured = []
            try:
                for member, raw in zip(members, snapshots):
                    if (type(raw) is not dict or set(raw) != {"fact", "evidence", "file_id", "file_metadata_sha256"}
                        or type(raw["file_id"]) is not UUID or raw["file_id"].version != 4
                        or type(raw["file_metadata_sha256"]) is not str or _HASH.fullmatch(raw["file_metadata_sha256"]) is None):
                        raise ValueError()
                    body = _snapshot_matches(member, {"fact": raw["fact"], "evidence": raw["evidence"]},
                        dataset_id=dataset.id, is_synthetic=dataset.is_synthetic, published_at=now)
                    captured.append((body, raw["file_id"], raw["file_metadata_sha256"]))
            except (ValidationError, ValueError, TypeError, OverflowError, AttributeError):
                raise ReleasesError(422) from None
            old_state = self.current(session, dataset.id, request.entry_year)
            previous = None
            if request.replaces_release_id is None:
                if old_state is not None:
                    raise ReleasesError(409)
            else:
                previous = self.get(session, request.replaces_release_id)
                if (old_state is None or old_state.release_id != previous.id
                    or (previous.dataset_id, previous.entry_year, previous.is_synthetic) !=
                       (dataset.id, request.entry_year, dataset.is_synthetic)
                    or old_state.revision != request.expected_replaced_state_revision or old_state.revision >= MAX_VERSION
                    or utc_time(previous.published_at) > now or utc_time(old_state.updated_at) > now):
                    raise ReleasesError(409)
            root = CatalogRelease(id=uuid4(), version=1, dataset_id=dataset.id, entry_year=request.entry_year,
                kind=request.kind, is_synthetic=dataset.is_synthetic, valid_from=request.valid_from,
                valid_until=request.valid_until, content_sha256=release_content_hash(request, members),
                requirements_version=requirements_snapshot_hash(members), ruleset_version=None,
                replaces_release_id=request.replaces_release_id, publisher_user_id=actor.user_id,
                audit_event_id=audit_event_id, published_at=now)
            session.add(root)
            session.flush()
            # The successor root must exist for the immediate FK; remove the
            # old published state before inserting the new partial-unique head.
            if previous is not None:
                old_state.status, old_state.revision = "replaced", old_state.revision + 1
                old_state.replaced_by_release_id, old_state.updated_at = root.id, now
                session.flush()
            state = CatalogReleaseState(release_id=root.id, dataset_id=dataset.id, entry_year=request.entry_year,
                is_synthetic=dataset.is_synthetic, status="published", revision=1,
                replaced_by_release_id=None, updated_at=now)
            session.add(state)
            for member, (body, file_id, metadata_hash) in zip(members, captured):
                session.add(CatalogReleaseMember(id=uuid4(), release_id=root.id, dataset_id=dataset.id,
                    is_synthetic=dataset.is_synthetic, **member.model_dump(), file_id=file_id,
                    file_metadata_sha256=metadata_hash, snapshot=body))
            dataset.revision += 1
            session.flush()
            if previous is not None:
                self._event(session, previous, old_state, actor=actor, audit_event_id=audit_event_id,
                    now=now, related_release_id=root.id)
            self._event(session, root, state, actor=actor, audit_event_id=audit_event_id, now=now)
            return root

    def withdraw(self, session, root, request, *, actor, audit_event_id, now):
        request, actor = _input(WithdrawalRequest, request), _input(Principal, actor)
        with self._work(session):
            if root.id != request.release_id or type(audit_event_id) is not UUID:
                raise ReleasesError(422)
            dataset = self.dataset(session, root.dataset_id)
            root = self.get(session, root.id)
            state = self.state(session, root.id)
            now = utc_time(now)
            if (root.is_synthetic != actor.is_synthetic or dataset.is_synthetic != root.is_synthetic
                or state.dataset_id != root.dataset_id or state.entry_year != root.entry_year
                or state.is_synthetic != root.is_synthetic or state.status != "published"
                or state.revision != request.expected_state_revision or state.revision >= MAX_VERSION
                or dataset.revision >= MAX_VERSION or utc_time(root.published_at) > now or utc_time(state.updated_at) > now):
                raise ReleasesError(409)
            state.status, state.revision, state.updated_at = "withdrawn", state.revision + 1, now
            state.replaced_by_release_id = None
            dataset.revision += 1
            session.flush()
            self._event(session, root, state, actor=actor, audit_event_id=audit_event_id,
                        now=now, reason_code=request.reason_code)
            return state

    def result(self, session, root, *, replayed=False):
        with self._work(session):
            state, rows = self.state(session, root.id), self.members(session, root.id)
            try:
                if (state.dataset_id, state.entry_year, state.is_synthetic) != (root.dataset_id, root.entry_year, root.is_synthetic):
                    raise ValueError()
                members = []
                for row in rows:
                    if (row.release_id, row.dataset_id, row.entry_year, row.is_synthetic) != (
                        root.id, root.dataset_id, root.entry_year, root.is_synthetic):
                        raise ValueError()
                    member = ReleaseMemberData.model_validate({name: getattr(row, name) for name in ReleaseMemberData.model_fields})
                    if (type(row.file_id) is not UUID or row.file_id.version != 4
                        or type(row.file_metadata_sha256) is not str or _HASH.fullmatch(row.file_metadata_sha256) is None):
                        raise ValueError()
                    _snapshot_matches(member, row.snapshot, dataset_id=root.dataset_id,
                        is_synthetic=root.is_synthetic, published_at=utc_time(root.published_at))
                    members.append(member)
                if utc_time(state.updated_at) < utc_time(root.published_at):
                    raise ValueError()
                return ReleaseData(release_id=root.id, version=root.version, dataset_id=root.dataset_id,
                    entry_year=root.entry_year, kind=root.kind, is_synthetic=root.is_synthetic,
                    valid_from=utc_time(root.valid_from), valid_until=utc_time(root.valid_until),
                    content_sha256=root.content_sha256, requirements_version=root.requirements_version,
                    ruleset_version=root.ruleset_version, members=tuple(members), state=state.status,
                    state_revision=state.revision, published_at=utc_time(root.published_at),
                    publisher_user_id=root.publisher_user_id, replaces_release_id=root.replaces_release_id,
                    replaced_by_release_id=state.replaced_by_release_id, replayed=replayed)
            except (ValidationError, ValueError, TypeError, OverflowError, AttributeError):
                raise ReleasesError() from None
