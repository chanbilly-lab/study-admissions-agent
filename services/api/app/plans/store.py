"""Bounded immutable plan storage; the caller owns authorization and commit."""

from contextlib import contextmanager
from datetime import date, datetime, time
import json
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..api.v2.idempotency_canonical import canonical_request_hash
from ..assessments.models import EligibilityAssessment
from ..assessments.store import AssessmentsStore
from ..auth.models import AuthOwnedResource
from ..profiles.models import ProfileRoot, ProfileVersion
from ..profiles.store import database_time
from .models import PlansBase, PlanRoot, PlanVersion, PlanTask, PlanSourceAssessment, PlanTaskDependency
from .schemas import MAX_TASKS, PLANS_HEAD, PlanAssessmentRef, PlanData, PlanDraft, PlanError

HEADS = {"auth_alembic_version": "0006_audit_t10", "idempotency_alembic_version": "0001_idempotency_t49",
    "catalog_alembic_version": "0003_catalog_sources_t13", "storage_alembic_version": "0001_storage_t14",
    "imports_alembic_version": "0001_imports_t15", "evidence_alembic_version": "0001_evidence_t16",
    "facts_alembic_version": "0001_facts_t17", "reviews_alembic_version": "0001_reviews_t18",
    "releases_alembic_version": "0001_releases_t19", "profiles_alembic_version": "0001_profiles_t23",
    "assessments_alembic_version": "0001_assessments_t28"}
MAPPERS = (PlanRoot, PlanVersion, PlanTask, PlanSourceAssessment, PlanTaskDependency,
           AuthOwnedResource, ProfileRoot, ProfileVersion, EligibilityAssessment)


def assessment_reference(data):
    """Exact finite projection of a validated T28 source, never a client binding."""
    return PlanAssessmentRef(assessment_id=data.assessment_id,result_sha256=data.result_sha256,
        target=data.target,release_id=data.release_id,requirements_version=data.requirements_version,
        ruleset_version=data.ruleset_version,stage=data.stage,eligibility_status=data.eligibility.status,
        current_validity=data.current_validity,rule_refs=data.rule_refs)


def migration_config():
    directory = Path(__file__).resolve().parents[2]
    config = Config(str(directory / "plans_alembic.ini"))
    config.set_main_option("script_location", str(directory / "plans_migrations"))
    return config


def migrate_plans(engine, target="head"):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
        raise PlanError()
    if target not in {"head", PLANS_HEAD}:
        raise PlanError(422)
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise PlanError() from None


def _draft(payload):
    """Decode only the known native timestamp/date fields of a server snapshot."""
    try:
        raw = json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
        for key in ("generated_at", "expires_at"):
            raw[key] = datetime.fromisoformat(raw[key])
        for ref in raw["deadline_refs"]:
            event = ref["date_event"]
            if event is None:
                continue
            for key, parser in (("local_date", date.fromisoformat), ("local_time", time.fromisoformat),
                                ("calculated_utc_instant", datetime.fromisoformat), ("utc_instant", datetime.fromisoformat)):
                if event[key] is not None:
                    event[key] = parser(event[key])
        value = PlanDraft.model_validate(raw)
        if value.model_dump(mode="json") != payload:
            raise ValueError()
        return value
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise PlanError() from None


class PlansStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise PlanError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            if not {"plans_alembic_version", *PlansBase.metadata.tables}.issubset(inspector.get_table_names()):
                raise PlanError()
            for table in PlansBase.metadata.tables.values():
                if set(table.columns.keys()) != {col["name"] for col in inspector.get_columns(table.name)}:
                    raise PlanError()
            with self.engine.connect() as connection:
                for table, head in {**HEADS, "plans_alembic_version": PLANS_HEAD}.items():
                    if connection.execute(text("SELECT version_num FROM " + table)).scalars().all() != [head]:
                        raise PlanError()
                for table in PlansBase.metadata.tables:
                    enabled = connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid=CAST(:name AS regclass) AND tgname=:trigger AND NOT tgisinternal"),
                        {"name": table, "trigger": table + "_no_update"}).scalar_one_or_none()
                    if enabled not in {"O", "A"}:
                        raise PlanError()
        except SQLAlchemyError:
            raise PlanError() from None

    @contextmanager
    def _work(self, session):
        if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
            or not session.get_transaction().is_active):
            raise PlanError()
        try:
            for mapper in (None, *MAPPERS):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise PlanError()
            yield
        except SQLAlchemyError:
            raise PlanError() from None

    def create(self, session, current, draft, *, plan_id, audit_event_id, now):
        with self._work(session):
            try:
                draft = PlanDraft.model_validate(draft)
                if type(plan_id) is not UUID or type(audit_event_id) is not UUID or now != draft.generated_at or current.is_synthetic != draft.is_synthetic:
                    raise ValueError()
            except (ValueError, TypeError):
                raise PlanError(422) from None
            profile = session.scalar(select(ProfileVersion).where(ProfileVersion.id == draft.profile_version_id,
                ProfileVersion.profile_id == draft.profile_id, ProfileVersion.owner_user_id == current.user_id)
                .with_for_update().execution_options(populate_existing=True))
            if profile is None or profile.payload_sha256 != draft.profile_sha256 or profile.is_synthetic != draft.is_synthetic:
                raise PlanError(409)
            if not profile.confirmed_at <= now < draft.expires_at <= profile.expires_at:
                raise PlanError(409)
            version_id = uuid4()
            registry = session.scalar(select(AuthOwnedResource).where(AuthOwnedResource.id == plan_id,
                AuthOwnedResource.owner_user_id == current.user_id, AuthOwnedResource.resource_type == "plan",
                AuthOwnedResource.status == "active", AuthOwnedResource.parent_id.is_(None))
                .with_for_update().execution_options(populate_existing=True))
            if registry is None or registry.is_synthetic != draft.is_synthetic or registry.version != 1:
                raise PlanError(409)
            root = PlanRoot(id=plan_id, owner_user_id=current.user_id, is_synthetic=draft.is_synthetic,
                profile_id=draft.profile_id, profile_version_id=draft.profile_version_id, profile_version=profile.version,
                profile_sha256=draft.profile_sha256, current_version=1, current_version_id=version_id, created_at=now)
            return self._insert(session, root, draft, audit_event_id)

    def _insert(self, session, root, draft, audit_event_id):
        # Called only after the service provides a matching durable owner registry.
        session.add(root)
        session.flush()
        payload = draft.model_dump(mode="json")
        row = PlanVersion(id=root.current_version_id, plan_id=root.id, owner_user_id=root.owner_user_id,
            is_synthetic=root.is_synthetic, version=1, payload=payload, draft_sha256=draft.draft_sha256,
            created_at=draft.generated_at, expires_at=draft.expires_at, audit_event_id=audit_event_id)
        session.add(row)
        session.flush()
        for ordinal, task in enumerate(draft.tasks, 1):
            value = task.model_dump(mode="json")
            session.add(PlanTask(version_id=row.id, plan_id=root.id, task_key=task.task_key,
                ordinal=ordinal, payload=value, payload_sha256=canonical_request_hash(value)))
        session.flush()
        for ref in draft.assessment_refs:
            source = session.scalar(select(EligibilityAssessment).where(EligibilityAssessment.id == ref.assessment_id,
                EligibilityAssessment.owner_user_id == root.owner_user_id).with_for_update().execution_options(populate_existing=True))
            if (source is None or source.result_sha256 != ref.result_sha256
                or source.profile_version_id != root.profile_version_id or not source.assessment_at <= row.created_at < row.expires_at <= source.expires_at):
                raise PlanError(409)
            actual=assessment_reference(AssessmentsStore.result(source))
            if actual.model_dump(exclude={"current_validity"}) != ref.model_dump(exclude={"current_validity"}):
                raise PlanError(409)
            session.add(PlanSourceAssessment(version_id=row.id, plan_id=root.id, assessment_id=ref.assessment_id,
                result_sha256=ref.result_sha256))
        for task in draft.tasks:
            for dependency in task.dependency_keys:
                session.add(PlanTaskDependency(version_id=row.id, plan_id=root.id, task_key=task.task_key, dependency_key=dependency))
        session.flush()
        return root

    def get(self, session, plan_id, owner_user_id):
        with self._work(session):
            if type(plan_id) is not UUID or type(owner_user_id) is not UUID:
                raise PlanError(404)
            root = session.scalar(select(PlanRoot).where(PlanRoot.id == plan_id, PlanRoot.owner_user_id == owner_user_id)
                .with_for_update().execution_options(populate_existing=True))
            if root is None:
                raise PlanError(404)
            return root

    def result(self, session, root):
        with self._work(session):
            try:
                row = session.scalar(select(PlanVersion).where(PlanVersion.id == root.current_version_id,
                    PlanVersion.plan_id == root.id, PlanVersion.version == root.current_version)
                    .with_for_update().execution_options(populate_existing=True))
                if row is None or (row.owner_user_id, row.is_synthetic, row.created_at) != (root.owner_user_id, root.is_synthetic, root.created_at):
                    raise ValueError()
                draft = _draft(row.payload)
                if (draft.draft_sha256 != row.draft_sha256 or (draft.profile_id, draft.profile_version_id,
                    draft.profile_sha256, draft.is_synthetic, draft.generated_at, draft.expires_at) !=
                    (root.profile_id, root.profile_version_id, root.profile_sha256, root.is_synthetic, row.created_at, row.expires_at)):
                    raise ValueError()
                tasks = session.scalars(select(PlanTask).where(PlanTask.version_id == row.id).order_by(PlanTask.ordinal)
                    .limit(MAX_TASKS+1).with_for_update().execution_options(populate_existing=True)).all()
                if len(tasks) != len(draft.tasks):
                    raise ValueError()
                for ordinal, (task, expected) in enumerate(zip(tasks, draft.tasks, strict=True), 1):
                    if (task.plan_id != root.id or task.ordinal != ordinal or task.task_key != expected.task_key
                        or task.payload != expected.model_dump(mode="json") or task.payload_sha256 != canonical_request_hash(task.payload)):
                        raise ValueError()
                sources = session.scalars(select(PlanSourceAssessment).where(PlanSourceAssessment.version_id == row.id)
                    .limit(5).with_for_update().execution_options(populate_existing=True)).all()
                if ({(s.assessment_id,s.result_sha256) for s in sources} != {(s.assessment_id,s.result_sha256) for s in draft.assessment_refs}
                    or len(sources) != len(draft.assessment_refs) or any(s.plan_id != root.id for s in sources)):
                    raise ValueError()
                edges = session.scalars(select(PlanTaskDependency).where(PlanTaskDependency.version_id == row.id)
                    .limit(MAX_TASKS*60+1).with_for_update().execution_options(populate_existing=True)).all()
                expected_edges = {(task.task_key, key) for task in draft.tasks for key in task.dependency_keys}
                if {(edge.task_key,edge.dependency_key) for edge in edges} != expected_edges or any(edge.plan_id != root.id for edge in edges):
                    raise ValueError()
                return PlanData(plan_id=root.id,version_id=row.id,version=row.version,draft=draft,
                    audit_event_id=row.audit_event_id,created_at=database_time(row.created_at),expires_at=database_time(row.expires_at))
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                raise PlanError() from None
