"""Claims and completions in a caller-owned PostgreSQL transaction."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..audit.retention import expires_after_months
from .models import IdempotencyRecord
from .schemas import IDEMPOTENCY_HEAD, MAX_TTL_SECONDS, IdempotencyError, ResourceReceipt

OPERATION_KINDS = {"catalog.import": "import", "catalog.publish": "catalog_release",
                   "profile.create": "profile", "plan.confirm": "plan"}


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2] / "idempotency_alembic.ini"))


def _auth_ready(connection):
    if connection.execute(text("SELECT version_num FROM auth_alembic_version")).scalars().all() != ["0006_audit_t10"]:
        raise IdempotencyError()


def migrate_idempotency(engine, target="head"):
    if (getattr(getattr(engine, "dialect", None), "name", None) != "postgresql"
        or target not in {"head", IDEMPOTENCY_HEAD}):
        raise IdempotencyError()
    try:
        with engine.begin() as connection:
            _auth_ready(connection)
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise IdempotencyError() from None


def utc_time(value):
    try:
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None or value.fold:
            raise ValueError()
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise IdempotencyError() from None


class IdempotencyStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise IdempotencyError()
        self.engine = engine

    def assert_schema_ready(self):
        """Readiness is inspection only, including the deferred commit barrier."""
        try:
            inspector = inspect(self.engine)
            if not {"idempotency_records", "idempotency_alembic_version"}.issubset(inspector.get_table_names()):
                raise IdempotencyError()
            if {item["name"] for item in inspector.get_columns("idempotency_records")} != set(IdempotencyRecord.__table__.columns.keys()):
                raise IdempotencyError()
            with self.engine.connect() as connection:
                _auth_ready(connection)
                if connection.execute(text("SELECT version_num FROM idempotency_alembic_version")).scalars().all() != [IDEMPOTENCY_HEAD]:
                    raise IdempotencyError()
                barrier = connection.execute(text("SELECT tgdeferrable, tginitdeferred, tgenabled FROM pg_trigger WHERE tgrelid = 'idempotency_records'::regclass AND tgname = 'idempotency_completed_at_commit' AND NOT tgisinternal")).one_or_none()
                if barrier is None or not barrier[0] or not barrier[1] or barrier[2] not in {"O", "A"}:
                    raise IdempotencyError()
        except SQLAlchemyError:
            raise IdempotencyError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise IdempotencyError()
        try:
            for mapper in (None, IdempotencyRecord):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise IdempotencyError()
            yield
        except IntegrityError:
            raise IdempotencyError(409) from None
        except SQLAlchemyError:
            raise IdempotencyError() from None

    @staticmethod
    def receipt(row):
        try:
            return ResourceReceipt(kind=row.resource_kind, resource_id=row.resource_id, version=row.resource_version)
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise IdempotencyError() from None

    @classmethod
    def _validate_row(cls, row):
        created, expiry = utc_time(row.created_at), utc_time(row.expires_at)
        if (row.operation not in OPERATION_KINDS or type(row.is_synthetic) is not bool
            or not isinstance(row.id, UUID) or not isinstance(row.actor_user_id, UUID)
            or any(type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for value in (row.key_digest, row.request_hash))
            or not created < expiry <= expires_after_months(created)):
            raise IdempotencyError()
        if row.state == "processing":
            if any(value is not None for value in (row.resource_kind, row.resource_id, row.resource_version, row.completed_at)):
                raise IdempotencyError()
        elif row.state == "completed":
            if (cls.receipt(row).kind != OPERATION_KINDS[row.operation]
                or row.completed_at is None or not created <= utc_time(row.completed_at) < expiry):
                raise IdempotencyError()
        else:
            raise IdempotencyError()

    def claim(self, session, actor_user_id, operation, key_digest, request_hash, *, is_synthetic, clock, ttl_seconds):
        """Return a locked row and replay flag; no processing claim is committed here."""
        if (not isinstance(actor_user_id, UUID) or type(operation) is not str or operation not in OPERATION_KINDS
            or type(is_synthetic) is not bool or not callable(clock)
            or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TTL_SECONDS
            or any(type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for value in (key_digest, request_hash))):
            raise IdempotencyError(422)
        with self._work(session):
            created = utc_time(clock())
            identity = uuid4()
            inserted = session.scalar(insert(IdempotencyRecord).values(id=identity, actor_user_id=actor_user_id,
                operation=operation, key_digest=key_digest, request_hash=request_hash, is_synthetic=is_synthetic,
                state="processing", created_at=created,
                expires_at=min(created + timedelta(seconds=ttl_seconds), expires_after_months(created)))
                .on_conflict_do_nothing(index_elements=["actor_user_id", "operation", "key_digest"])
                .returning(IdempotencyRecord.id))
            row = session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.actor_user_id == actor_user_id,
                IdempotencyRecord.operation == operation, IdempotencyRecord.key_digest == key_digest)
                .with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise IdempotencyError()
            self._validate_row(row)
            if row.is_synthetic != is_synthetic or (inserted is None and row.state == "processing"):
                raise IdempotencyError()
            now = utc_time(clock())  # Unique-index and row-lock waits have completed.
            if utc_time(row.created_at) > now:
                raise IdempotencyError()
            if utc_time(row.expires_at) <= now:
                # Receipt expiry does not delete, renew or authorize its old business resource.
                session.delete(row)
                session.flush()
                row = IdempotencyRecord(id=uuid4(), actor_user_id=actor_user_id, operation=operation,
                    key_digest=key_digest, request_hash=request_hash, is_synthetic=is_synthetic,
                    state="processing", created_at=now,
                    expires_at=min(now + timedelta(seconds=ttl_seconds), expires_after_months(now)))
                session.add(row)
                session.flush()
                return row, False
            if inserted is not None:
                row.created_at = now
                row.expires_at = min(now + timedelta(seconds=ttl_seconds), expires_after_months(now))
                session.flush()
                return row, False
            if row.request_hash != request_hash:
                raise IdempotencyError(409)
            return row, True

    def complete(self, session, row, receipt, *, now):
        try:
            receipt = ResourceReceipt.model_validate(receipt)
        except (ValidationError, ValueError, TypeError):
            raise IdempotencyError(422) from None
        with self._work(session):
            self._validate_row(row)
            now = utc_time(now)
            if (row.state != "processing" or receipt.kind != OPERATION_KINDS[row.operation]
                or not utc_time(row.created_at) <= now < utc_time(row.expires_at)):
                raise IdempotencyError(409)
            row.state, row.resource_kind, row.resource_id, row.resource_version = (
                "completed", receipt.kind, receipt.resource_id, receipt.version)
            row.completed_at = now
            session.flush()
            self._validate_row(row)
            return self.receipt(row)
