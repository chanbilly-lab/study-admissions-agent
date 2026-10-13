"""Bounded immutable snapshots inside the caller's active PostgreSQL transaction."""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..api.v2.idempotency_canonical import canonical_request_hash
from ..rules.expression import parse_expression
from ..rules.schemas import ASSESSMENTS_HEAD, AssessmentData, AssessmentError
from .models import AssessmentsBase, EligibilityAssessment

HEADS = {"auth_alembic_version": "0006_audit_t10", "profiles_alembic_version": "0001_profiles_t23",
    "catalog_alembic_version": "0003_catalog_sources_t13", "storage_alembic_version": "0001_storage_t14",
    "imports_alembic_version": "0001_imports_t15", "evidence_alembic_version": "0001_evidence_t16",
    "facts_alembic_version": "0001_facts_t17", "reviews_alembic_version": "0001_reviews_t18",
    "releases_alembic_version": "0001_releases_t19"}


def migration_config():
    directory = Path(__file__).resolve().parents[2]
    config = Config(str(directory / "assessments_alembic.ini"))
    config.set_main_option("script_location", str(directory / "assessments_migrations"))
    return config


def migrate_assessments(engine):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
        raise AssessmentError()
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    except Exception:
        raise AssessmentError() from None


def expression_document(value):
    """Persist only fields belonging to each op, preserving the whole AST."""
    node = parse_expression(value)
    fields = {"all": ("children",), "any": ("children",), "not": ("child",),
        "exists": ("field",), "eq": ("field", "value"), "in": ("field", "values"),
        "gte": ("field", "value"), "lte": ("field", "value"),
        "date_before": ("field", "value"), "valid_at": ("start", "end")}[node.op]
    result = {"op": node.op}
    dump = node.model_dump(mode="json")
    for name in fields:
        if name == "children":
            result[name] = [expression_document(child) for child in node.children]
        elif name == "child":
            result[name] = expression_document(node.child)
        else:
            result[name] = dump[name]
    return result


def result_fingerprint(payload):
    return canonical_request_hash({key: value for key, value in payload.items()
        if key not in {"result_sha256", "current_validity", "replayed"}})


class AssessmentsStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise AssessmentError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            if not {"eligibility_assessments", "assessments_alembic_version"}.issubset(inspector.get_table_names()):
                raise AssessmentError()
            for table in AssessmentsBase.metadata.tables.values():
                if {col["name"] for col in inspector.get_columns(table.name)} != set(table.columns.keys()):
                    raise AssessmentError()
            with self.engine.connect() as connection:
                for table, head in {**HEADS, "assessments_alembic_version": ASSESSMENTS_HEAD}.items():
                    if connection.execute(text("SELECT version_num FROM " + table)).scalars().all() != [head]:
                        raise AssessmentError()
                trigger = connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid='eligibility_assessments'::regclass AND tgname='eligibility_assessments_no_update' AND NOT tgisinternal")).scalar_one_or_none()
                if trigger not in {"O", "A"}:
                    raise AssessmentError()
        except SQLAlchemyError:
            raise AssessmentError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise AssessmentError()
        try:
            for mapper in (None, EligibilityAssessment):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise AssessmentError()
            yield
        except SQLAlchemyError:
            raise AssessmentError() from None

    def get(self, session, assessment_id, owner_user_id):
        with self._work(session):
            if type(assessment_id) is not UUID or type(owner_user_id) is not UUID:
                raise AssessmentError(404)
            row = session.scalar(select(EligibilityAssessment).where(EligibilityAssessment.id == assessment_id,
                EligibilityAssessment.owner_user_id == owner_user_id).with_for_update()
                .execution_options(populate_existing=True))
            if row is None:
                raise AssessmentError(404)
            return row

    def create(self, session, *, owner, data, snapshot, audit_event_id):
        with self._work(session):
            data = AssessmentData.model_validate(data)
            payload = data.model_dump(mode="json")
            if result_fingerprint(payload) != data.result_sha256:
                raise AssessmentError()
            row = EligibilityAssessment(id=data.assessment_id, version=1, owner_user_id=owner.user_id,
                profile_id=data.profile_id, profile_version_id=data.profile_version_id,
                profile_version=data.profile_version, profile_is_synthetic=data.profile_is_synthetic,
                dataset_id=data.target.dataset_id, release_id=data.release_id, entry_year=snapshot["entry_year"],
                catalogue_is_synthetic=data.catalogue_is_synthetic, assessment_at=data.assessment_at,
                expires_at=data.expires_at, engine_version=data.engine_version, binding_mode=data.binding_mode,
                payload=payload, replay_snapshot=snapshot, result_sha256=data.result_sha256,
                snapshot_sha256=canonical_request_hash(snapshot), audit_event_id=audit_event_id)
            session.add(row)
            session.flush()
            return row

    @staticmethod
    def result(row, *, current_validity="unavailable", replayed=False):
        try:
            if (result_fingerprint(row.payload) != row.result_sha256
                or row.payload.get("result_sha256") != row.result_sha256
                or canonical_request_hash(row.replay_snapshot) != row.snapshot_sha256):
                raise AssessmentError()
            data = AssessmentData.model_validate({**row.payload, "current_validity": current_validity,
                                                  "replayed": replayed})
            if ((data.assessment_id, data.version, data.profile_id, data.profile_version_id,
                 data.profile_version, data.profile_is_synthetic, data.target.dataset_id,
                 data.release_id, data.catalogue_is_synthetic, data.engine_version, data.binding_mode,
                 data.assessment_at, data.expires_at) != (row.id, row.version, row.profile_id,
                 row.profile_version_id, row.profile_version, row.profile_is_synthetic, row.dataset_id,
                 row.release_id, row.catalogue_is_synthetic, row.engine_version, row.binding_mode,
                 row.assessment_at, row.expires_at)):
                raise AssessmentError()
            return data
        except (ValueError, TypeError, AttributeError, OverflowError):
            raise AssessmentError() from None
