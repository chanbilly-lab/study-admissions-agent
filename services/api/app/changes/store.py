"""Same-session change receipts and metadata-only impact relationships."""

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..assessments.models import EligibilityAssessment
from ..plan_execution.store import HEADS as EXECUTION_HEADS, MAPPERS as EXECUTION_MAPPERS
from ..plans.models import PlanRoot, PlanVersion, PlanSourceAssessment
from ..profiles.store import database_time
from ..releases.models import CatalogRelease, CatalogReleaseMember, CatalogReleaseState, ChangeEvent, OutboxEvent
from ..releases.schemas import ReleaseData, ReleaseMemberData
from ..releases.store import _captured_snapshot, _snapshot_matches
from .models import ChangesBase, ChangeEventReceipt, AssessmentChangeImpact, PlanChangeImpact
from .schemas import (CHANGES_HEAD, ChangesError, ChangeImpactData, ChangeProcessingData,
                      PublishedMember, ReleaseSnapshot, fingerprint)

HEADS = {**EXECUTION_HEADS, "execution_alembic_version": "0001_execution_t32"}
MAPPERS = (*EXECUTION_MAPPERS, CatalogRelease, CatalogReleaseMember, CatalogReleaseState,
           ChangeEvent, OutboxEvent, ChangeEventReceipt, AssessmentChangeImpact, PlanChangeImpact)
RELATION_INDEXES = {"ix_assessment_release_target": ("eligibility_assessments", "(release_id, dataset_id, entry_year)"),
                    "ix_plan_source_assessment": ("plan_draft_assessments", "(assessment_id, version_id, plan_id)")}


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2] / "changes_alembic.ini"))


def migrate_changes(engine, target="head"):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql" or target not in {"head", CHANGES_HEAD}:
        raise ChangesError()
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise ChangesError() from None


def bounded_json(value, maximum=262144):
    try:
        if type(value) is not dict or len(json.dumps(value, ensure_ascii=False, allow_nan=False,
                separators=(", ", ": ")).encode("utf-8")) > maximum:
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ChangesError(422) from None


def event_fingerprint(event):
    values = {column.name: getattr(event, column.name) for column in ChangeEvent.__table__.columns}
    for key, value in values.items():
        if type(value) is UUID:
            values[key] = str(value)
        elif type(value) is datetime:
            values[key] = database_time(value).isoformat()
    return fingerprint(values)


def impact_data(row, *, plan_id=None):
    try:
        if fingerprint(row.payload) != row.payload_sha256:
            raise ValueError()
        values = dict(row.payload)
        values["created_at"] = datetime.fromisoformat(values["created_at"])
        result = ChangeImpactData.model_validate(values)
        if (result.event_id != row.event_id or result.assessment_id != row.assessment_id
            or result.needs_review != row.needs_review or result.created_at != database_time(row.created_at)
            or result.model_dump(mode="json") != row.payload):
            raise ValueError()
        if isinstance(row, PlanChangeImpact) and result.plan_id != row.plan_id:
            raise ValueError()
        if isinstance(row, AssessmentChangeImpact) and result.plan_id is not None:
            raise ValueError()
        if plan_id is not None:
            values["plan_id"] = plan_id
            result = ChangeImpactData.model_validate(values)
        return result
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ChangesError() from None


class ChangesStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise ChangesError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            if not {"changes_alembic_version", *ChangesBase.metadata.tables}.issubset(inspector.get_table_names()):
                raise ChangesError()
            for table in ChangesBase.metadata.tables.values():
                if set(table.columns.keys()) != {column["name"] for column in inspector.get_columns(table.name)}:
                    raise ChangesError()
            with self.engine.connect() as connection:
                for table, head in {**HEADS, "changes_alembic_version": CHANGES_HEAD}.items():
                    if connection.execute(text("SELECT version_num FROM " + table)).scalars().all() != [head]:
                        raise ChangesError()
                for table in ChangesBase.metadata.tables:
                    enabled = connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid=CAST(:name AS regclass) AND tgname=:trigger AND NOT tgisinternal"),
                        {"name": table, "trigger": table + "_no_update"}).scalar_one_or_none()
                    if enabled not in {"O", "A"}:
                        raise ChangesError()
                for index, (table, fields) in RELATION_INDEXES.items():
                    result = connection.execute(text("SELECT i.indisvalid, i.indisready, pg_get_indexdef(i.indexrelid) FROM pg_index i WHERE i.indexrelid=to_regclass(:name) AND i.indrelid=to_regclass(:table)"),
                        {"name": index, "table": table}).one_or_none()
                    if result is None or result[:2] != (True, True) or fields not in result[2]:
                        raise ChangesError()
        except SQLAlchemyError:
            raise ChangesError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise ChangesError()
        try:
            for mapper in (None, *MAPPERS):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise ChangesError()
            yield
        except SQLAlchemyError:
            raise ChangesError() from None

    def event(self, session, event_id):
        with self._work(session):
            row = session.scalar(select(ChangeEvent).where(ChangeEvent.id == event_id).with_for_update()
                .execution_options(populate_existing=True))
            if row is None:
                raise ChangesError(404)
            return row

    def snapshot(self, session, release_id):
        # Roots/members are immutable. Read states without taking source locks:
        # processing a committed historical event does not authorize publication.
        with self._work(session):
            root = session.get(CatalogRelease, release_id, populate_existing=True)
            state = session.get(CatalogReleaseState, release_id, populate_existing=True)
            if root is None or state is None:
                raise ChangesError()
            rows = tuple(session.scalars(select(CatalogReleaseMember).where(CatalogReleaseMember.release_id == release_id)
                .order_by(CatalogReleaseMember.fact_id).limit(51)).all())
            if not 1 <= len(rows) <= 50:
                raise ChangesError()
            try:
                if (state.dataset_id, state.entry_year, state.is_synthetic) != (root.dataset_id, root.entry_year, root.is_synthetic):
                    raise ValueError()
                members, published = [], []
                for row in rows:
                    if (row.release_id, row.dataset_id, row.entry_year, row.is_synthetic) != (root.id, root.dataset_id, root.entry_year, root.is_synthetic):
                        raise ValueError()
                    member = ReleaseMemberData.model_validate({name: getattr(row, name) for name in ReleaseMemberData.model_fields})
                    _snapshot_matches(member, row.snapshot, dataset_id=root.dataset_id,
                        is_synthetic=root.is_synthetic, published_at=database_time(root.published_at))
                    fact, evidence = _captured_snapshot(row.snapshot)
                    members.append(member)
                    published.append(PublishedMember(release_member=member, fact=fact, evidence=evidence))
                release = ReleaseData(release_id=root.id, version=root.version, dataset_id=root.dataset_id,
                    entry_year=root.entry_year, kind=root.kind, is_synthetic=root.is_synthetic,
                    valid_from=database_time(root.valid_from), valid_until=database_time(root.valid_until),
                    content_sha256=root.content_sha256, requirements_version=root.requirements_version,
                    ruleset_version=root.ruleset_version, members=tuple(members), state=state.status,
                    state_revision=state.revision, published_at=database_time(root.published_at),
                    publisher_user_id=root.publisher_user_id, replaces_release_id=root.replaces_release_id,
                    replaced_by_release_id=state.replaced_by_release_id, replayed=False)
                return root, state, ReleaseSnapshot(release=release, members=tuple(published))
            except (ValueError, TypeError, AttributeError, OverflowError):
                raise ChangesError() from None

    def receipt(self, session, event_id):
        with self._work(session):
            return session.get(ChangeEventReceipt, event_id, populate_existing=True)

    def processing_data(self, session, receipt, *, event_sha256, payload, replayed, erased_counts=(0, 0)):
        with self._work(session):
            if (type(erased_counts) is not tuple or len(erased_counts) != 2
                or any(type(value) is not int or value < 0 for value in erased_counts)):
                raise ChangesError(409)
            if (receipt.event_sha256 != event_sha256 or fingerprint(receipt.payload) != receipt.payload_sha256
                or receipt.payload != payload or receipt.event_type != payload["event_type"]
                or str(receipt.dataset_id) != payload["dataset_id"] or receipt.entry_year != payload["entry_year"]
                or receipt.is_synthetic != payload["is_synthetic"]
                or (str(receipt.before_release_id) if receipt.before_release_id is not None else None) != payload["before_release_id"]
                or (str(receipt.after_release_id) if receipt.after_release_id is not None else None) != payload["after_release_id"]):
                raise ChangesError(409)
            for model, count, erased in ((AssessmentChangeImpact, receipt.assessment_count, erased_counts[0]), (PlanChangeImpact, receipt.plan_count, erased_counts[1])):
                if session.scalar(select(func.count()).select_from(model).where(model.event_id == receipt.event_id)) + erased != count:
                    raise ChangesError(409)
            return ChangeProcessingData(event_id=receipt.event_id, event_type=receipt.event_type,
                payload_sha256=receipt.payload_sha256, processed_at=database_time(receipt.processed_at),
                assessment_count=receipt.assessment_count, plan_count=receipt.plan_count, replayed=replayed)

    def assessments(self, session, release_id, dataset_id, entry_year, *, blocked_owners=frozenset()):
        with self._work(session):
            # Do not load the ORM entity: payload evaluation contains grades and
            # replay_snapshot is private. Only public target/immutable IDs leave SQL.
            query = select(EligibilityAssessment.id, EligibilityAssessment.owner_user_id,
                EligibilityAssessment.profile_id, EligibilityAssessment.profile_version_id,
                EligibilityAssessment.profile_is_synthetic, EligibilityAssessment.catalogue_is_synthetic,
                EligibilityAssessment.dataset_id, EligibilityAssessment.release_id, EligibilityAssessment.entry_year,
                EligibilityAssessment.payload["target"].label("target"))
            query = query.where(EligibilityAssessment.release_id == release_id,
                EligibilityAssessment.dataset_id == dataset_id, EligibilityAssessment.entry_year == entry_year).order_by(EligibilityAssessment.id)
            if blocked_owners:
                if type(blocked_owners) is not frozenset or any(type(value) is not UUID for value in blocked_owners):
                    raise ChangesError()
                query = query.where(EligibilityAssessment.owner_user_id.not_in(blocked_owners))
            # No LIMIT. A completed receipt covers every existing matching row.
            yield from session.execute(query.execution_options(yield_per=100)).mappings()

    def plans(self, session, assessment_id):
        with self._work(session):
            query = select(PlanSourceAssessment.version_id, PlanSourceAssessment.assessment_id,
                PlanSourceAssessment.plan_id, PlanRoot.owner_user_id, PlanRoot.is_synthetic)
            query = query.join(PlanRoot, PlanRoot.id == PlanSourceAssessment.plan_id).where(
                PlanSourceAssessment.assessment_id == assessment_id).order_by(PlanSourceAssessment.version_id)
            yield from session.execute(query.execution_options(yield_per=100)).mappings()

    def insert_assessment(self, session, current, data):
        with self._work(session):
            payload = bounded_json(data.model_dump(mode="json"), 65536)
            row = AssessmentChangeImpact(event_id=data.event_id, assessment_id=data.assessment_id,
                owner_user_id=current["owner_user_id"], is_synthetic=current["profile_is_synthetic"],
                needs_review=data.needs_review, payload=payload, payload_sha256=fingerprint(payload), created_at=data.created_at)
            session.add(row)
            session.flush()
            return row

    def insert_plan(self, session, association, data):
        with self._work(session):
            values = data.model_dump()
            values["plan_id"] = association["plan_id"]
            value = ChangeImpactData.model_validate(values)
            payload = bounded_json(value.model_dump(mode="json"), 65536)
            session.add(PlanChangeImpact(event_id=data.event_id, assessment_id=data.assessment_id,
                plan_version_id=association["version_id"], plan_id=association["plan_id"],
                owner_user_id=association["owner_user_id"], is_synthetic=association["is_synthetic"],
                needs_review=data.needs_review, payload=payload, payload_sha256=fingerprint(payload), created_at=data.created_at))
            session.flush()

    def insert_receipt(self, session, event, diff, payload, counts, now):
        with self._work(session):
            payload = bounded_json(payload)
            row = ChangeEventReceipt(event_id=event.id, dataset_id=event.dataset_id, entry_year=event.entry_year,
                is_synthetic=event.is_synthetic, event_type=event.event_type,
                before_release_id=diff.before_release_id, after_release_id=diff.after_release_id,
                event_sha256=event_fingerprint(event), payload_sha256=fingerprint(payload), payload=payload,
                assessment_count=counts[0], plan_count=counts[1], processed_at=now, audit_event_id=event.audit_event_id)
            session.add(row)
            session.flush()
            return row

    def assessment_impacts(self, session, assessment_id, owner_id):
        with self._work(session):
            rows = tuple(session.scalars(select(AssessmentChangeImpact).where(
                AssessmentChangeImpact.assessment_id == assessment_id, AssessmentChangeImpact.owner_user_id == owner_id)
                .order_by(AssessmentChangeImpact.created_at, AssessmentChangeImpact.event_id).limit(101)).all())
            if len(rows) > 100:
                raise ChangesError(409)
            return rows

    def plan_impacts(self, session, plan_id, owner_id):
        with self._work(session):
            # Dynamic inheritance includes historical verification plans created
            # after processing. Durable plan impacts remain immutable evidence.
            query = select(AssessmentChangeImpact).join(PlanSourceAssessment,
                PlanSourceAssessment.assessment_id == AssessmentChangeImpact.assessment_id)
            rows = tuple(session.scalars(query.where(PlanSourceAssessment.plan_id == plan_id,
                AssessmentChangeImpact.owner_user_id == owner_id).distinct()
                .order_by(AssessmentChangeImpact.created_at, AssessmentChangeImpact.event_id, AssessmentChangeImpact.assessment_id)
                .limit(101)).all())
            if len(rows) > 100:
                raise ChangesError(409)
            return rows
