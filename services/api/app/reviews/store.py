"""Caller-transaction decision histories and one locked logical-key case."""

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..evidence.store import utc_time
from ..facts.models import FactCandidate, FactConflict
from ..facts.store import fingerprint
from .models import ReviewCase, ReviewDecision, ReviewConflictResolution, ReviewsBase
from .schemas import (ConflictResolution, ReviewCaseData, ReviewDecisionData, ReviewRequest,
                      ReviewsError, REVIEWS_HEAD)


_HEADS = {"auth_alembic_version": "0006_audit_t10", "catalog_alembic_version": "0003_catalog_sources_t13",
          "storage_alembic_version": "0001_storage_t14", "imports_alembic_version": "0001_imports_t15",
          "evidence_alembic_version": "0001_evidence_t16", "facts_alembic_version": "0001_facts_t17"}


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2] / "reviews_alembic.ini"))


def _parents_ready(connection):
    for table, head in _HEADS.items():
        if connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all() != [head]:
            raise ReviewsError()


def migrate_reviews(engine, target="head"):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql" or target not in {"head", REVIEWS_HEAD}:
        raise ReviewsError()
    try:
        with engine.begin() as connection:
            _parents_ready(connection)
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise ReviewsError() from None


def _input(model, value):
    try:
        return model.model_validate(value)
    except (ValidationError, ValueError, TypeError):
        raise ReviewsError(422) from None


def fact_fingerprint(fact):
    return fingerprint(fact.model_dump(mode="json"))


def conflict_fingerprint(ids):
    return fingerprint([str(identifier) for identifier in sorted(ids, key=str)])


class ReviewsStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise ReviewsError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            tables = list(ReviewsBase.metadata.tables.values())
            if not ({table.name for table in tables} | {"reviews_alembic_version"}).issubset(inspector.get_table_names()):
                raise ReviewsError()
            for table in tables:
                if {column["name"] for column in inspector.get_columns(table.name)} != set(table.columns.keys()):
                    raise ReviewsError()
            with self.engine.connect() as connection:
                _parents_ready(connection)
                if connection.execute(text("SELECT version_num FROM reviews_alembic_version")).scalars().all() != [REVIEWS_HEAD]:
                    raise ReviewsError()
                triggers = connection.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal "
                    "AND tgenabled='O' AND tgrelid IN (to_regclass('review_decisions'),to_regclass('review_conflict_resolutions'))")).scalars().all()
                if set(triggers) != {"reviews_decisions_immutable", "reviews_resolutions_immutable"}:
                    raise ReviewsError()
                pointer = connection.execute(text("SELECT condeferrable, condeferred FROM pg_constraint "
                    "WHERE conname='fk_review_case_current_decision' AND conrelid=to_regclass('review_cases')")).all()
                if pointer != [(True, True)]:
                    raise ReviewsError()
        except SQLAlchemyError:
            raise ReviewsError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise ReviewsError()
        try:
            for mapper in (None, ReviewCase, ReviewDecision, ReviewConflictResolution, FactCandidate, FactConflict):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise ReviewsError()
            yield
        except IntegrityError:
            raise ReviewsError(409) from None
        except SQLAlchemyError:
            raise ReviewsError() from None

    def get_case(self, session, logical_key_hash, *, lock=True):
        with self._work(session):
            query = select(ReviewCase).where(ReviewCase.logical_key_hash == logical_key_hash)
            return session.scalar((query.with_for_update() if lock else query).execution_options(populate_existing=True))

    def claim_case(self, session, fact_row, *, now):
        with self._work(session):
            now = utc_time(now)
            session.execute(insert(ReviewCase).values(id=uuid4(), logical_key_hash=fact_row.logical_key_hash,
                revision=0, chosen_fact_id=None, current_decision_id=None, is_synthetic=fact_row.is_synthetic,
                created_at=now, updated_at=now).on_conflict_do_nothing(index_elements=[ReviewCase.logical_key_hash]))
            row = self.get_case(session, fact_row.logical_key_hash)
            if row is None or row.is_synthetic != fact_row.is_synthetic:
                raise ReviewsError(409)
            return row

    def get_decision(self, session, decision_id):
        with self._work(session):
            if type(decision_id) is not UUID:
                raise ReviewsError(404)
            row = session.scalar(select(ReviewDecision).where(ReviewDecision.id == decision_id)
                .with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise ReviewsError(404)
            return row

    def resolutions(self, session, decision):
        with self._work(session):
            rows = session.scalars(select(ReviewConflictResolution).where(
                ReviewConflictResolution.decision_id == decision.id).order_by(ReviewConflictResolution.other_fact_id)
                .limit(201).execution_options(populate_existing=True)).all()
            if len(rows) > 200 or any((row.selected_fact_id, row.logical_key_hash) !=
                (decision.fact_id, decision.logical_key_hash) for row in rows):
                raise ReviewsError(409)
            try:
                return tuple(ConflictResolution(fact_id=row.other_fact_id, reason_code=row.reason_code) for row in rows)
            except (ValidationError, ValueError, TypeError, AttributeError):
                raise ReviewsError() from None

    def request(self, session, decision):
        try:
            return ReviewRequest(fact_id=decision.fact_id, expected_fact_version=1,
                expected_case_revision=decision.case_revision - 1, action=decision.action,
                checks=decision.checks, conflict_resolutions=self.resolutions(session, decision),
                return_reason=decision.return_reason)
        except ReviewsError:
            raise
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise ReviewsError() from None

    def record(self, session, case, request, fact, *, reviewer, audit_event_id, now):
        request = _input(ReviewRequest, request)
        with self._work(session):
            if (case.logical_key_hash != self._fact_logical(session, fact.id)
                or case.is_synthetic != fact.is_synthetic or case.revision != request.expected_case_revision
                or case.revision >= 2147483647):
                raise ReviewsError(409)
            now = utc_time(now)
            if utc_time(case.created_at) > now or utc_time(case.updated_at) > now:
                raise ReviewsError(409)
            row = ReviewDecision(id=uuid4(), case_id=case.id, case_revision=case.revision + 1,
                logical_key_hash=case.logical_key_hash, fact_id=fact.id, action=request.action,
                checks=[check.model_dump(mode="json") for check in request.checks],
                return_reason=request.return_reason, fact_sha256=fact_fingerprint(fact),
                conflicts_sha256=conflict_fingerprint(fact.conflicting_ids), reviewer_user_id=reviewer.user_id,
                audit_event_id=audit_event_id, is_synthetic=fact.is_synthetic, created_at=now)
            session.add(row)
            session.flush()
            for resolution in request.conflict_resolutions:
                session.add(ReviewConflictResolution(id=uuid4(), decision_id=row.id, selected_fact_id=fact.id,
                    other_fact_id=resolution.fact_id, logical_key_hash=case.logical_key_hash,
                    reason_code=resolution.reason_code, created_at=now))
            case.revision, case.current_decision_id, case.updated_at = row.case_revision, row.id, now
            case.chosen_fact_id = fact.id if request.action == "approve" else None
            session.flush()
            return row

    def _fact_logical(self, session, fact_id):
        value = session.scalar(select(FactCandidate.logical_key_hash).where(FactCandidate.id == fact_id))
        if value is None:
            raise ReviewsError(404)
        return value

    def decision_data(self, session, row, *, current_approved=False):
        request = self.request(session, row)
        try:
            return ReviewDecisionData(decision_id=row.id, case_id=row.case_id, case_revision=row.case_revision,
                fact_id=row.fact_id, action=request.action, checks=request.checks,
                conflict_resolutions=request.conflict_resolutions, return_reason=request.return_reason,
                reviewer_user_id=row.reviewer_user_id, created_at=utc_time(row.created_at),
                is_synthetic=row.is_synthetic, current_approved=current_approved)
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise ReviewsError() from None

    def case_data(self, row, *, logical_key_hash, is_synthetic, current_approved=False):
        try:
            return ReviewCaseData(case_id=row.id if row else None, logical_key_hash=logical_key_hash,
                case_revision=row.revision if row else 0, chosen_fact_id=row.chosen_fact_id if row else None,
                current_decision_id=row.current_decision_id if row else None,
                current_approved=current_approved, is_synthetic=is_synthetic)
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise ReviewsError() from None
