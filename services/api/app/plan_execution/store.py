"""Active same-engine storage for immutable proposals and declared completion."""

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

from ..plans.models import PlanRoot, PlanVersion, PlanTask
from ..plans.schemas import EstimateOverride, PlanDraft, plan_draft_fingerprint
from ..plans.schedule_schemas import ScheduleDraft
from ..plans.store import HEADS as PLAN_HEADS, MAPPERS as PLAN_MAPPERS
from ..profiles.store import database_time
from .models import ExecutionBase, ExecutionHead, ExecutionProposal, ExecutionConfirmation, TaskCompletion
from .schemas import (EXECUTION_HEAD, MAX_PROPOSAL_BYTES, ExecutionError, ExecutionData,
    ProposalData, ConfirmationData, CompletionData, ScheduleConfiguration, WorkspaceInput)

HEADS = {**PLAN_HEADS, "plans_alembic_version": "0001_plans_t30"}
MAPPERS = (*PLAN_MAPPERS, ExecutionHead, ExecutionProposal, ExecutionConfirmation, TaskCompletion)
IMMUTABLE_TABLES = ("plan_execution_proposals", "plan_execution_confirmations", "plan_task_completions")


def migration_config():
    directory = Path(__file__).resolve().parents[2]
    config = Config(str(directory / "execution_alembic.ini"))
    config.set_main_option("script_location", str(directory / "execution_migrations"))
    return config


def migrate_execution(engine, target="head"):
    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
        raise ExecutionError()
    if target not in {"head", EXECUTION_HEAD}:
        raise ExecutionError(422)
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise ExecutionError() from None


def bounded_payload(payload, maximum=MAX_PROPOSAL_BYTES):
    # PostgreSQL jsonb text has a space after separators. Measure before writes.
    try:
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(", ", ": ")).encode("utf-8")) > maximum:
            raise ExecutionError(422)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ExecutionError(422) from None
    return payload


def effective_draft(source, overrides):
    source = PlanDraft.model_validate(source)
    rows = tuple(EstimateOverride.model_validate(item) for item in overrides)
    if len(rows) > 100 or len({r.task_key for r in rows}) != len(rows):
        raise ExecutionError(422)
    changes = {r.task_key: r.estimated_hours for r in rows}
    if set(changes) - {t.task_key for t in source.tasks}:
        raise ExecutionError(422)
    tasks = []
    for original in source.tasks:
        values = original.model_dump()
        if original.task_key in changes:
            value = changes[original.task_key]
            values.update(estimated_hours=value, estimate_source="unknown" if value is None else "user_adjusted")
        tasks.append(type(original).model_validate(values))
    values = source.model_dump()
    values["tasks"] = tuple(tasks)
    json_value = source.model_copy(update={"tasks": tuple(tasks)}).model_dump(mode="json")
    values["draft_sha256"] = plan_draft_fingerprint(json_value)
    return PlanDraft.model_validate(values)


def _native_dates(value):
    if type(value) is list:
        return [_native_dates(v) for v in value]
    if type(value) is not dict:
        return value
    instants = {"generated_at", "expires_at", "created_at", "start_at", "end_at", "horizon_start", "horizon_end",
                "due_at", "calculated_utc_instant", "utc_instant"}
    result = {}
    for key, item in value.items():
        if item is not None and key in instants:
            item = datetime.fromisoformat(item)
        elif item is not None and key in {"local_date", "week_start"}:
            item = date.fromisoformat(item)
        elif item is not None and key == "local_time":
            item = time.fromisoformat(item)
        else:
            item = _native_dates(item)
        result[key] = item
    return result


def proposal_payload(overrides, configuration, schedule):
    return bounded_payload({"estimate_overrides": [o.model_dump(mode="json") for o in overrides],
        "schedule_configuration": configuration.model_dump(mode="json") if configuration is not None else None,
        "schedule": schedule.model_dump(mode="json") if schedule is not None else None})


class ExecutionStore:
    def __init__(self, engine):
        if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
            raise ExecutionError()
        self.engine = engine

    def assert_schema_ready(self):
        try:
            inspector = inspect(self.engine)
            if not {"execution_alembic_version", *ExecutionBase.metadata.tables}.issubset(inspector.get_table_names()):
                raise ExecutionError()
            for table in ExecutionBase.metadata.tables.values():
                if set(table.columns.keys()) != {c["name"] for c in inspector.get_columns(table.name)}:
                    raise ExecutionError()
            with self.engine.connect() as connection:
                for table, head in {**HEADS, "execution_alembic_version": EXECUTION_HEAD}.items():
                    if connection.execute(text("SELECT version_num FROM " + table)).scalars().all() != [head]:
                        raise ExecutionError()
                for table in IMMUTABLE_TABLES:
                    enabled = connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid=CAST(:name AS regclass) AND tgname=:trigger AND NOT tgisinternal"),
                        {"name": table, "trigger": table + "_no_update"}).scalar_one_or_none()
                    if enabled not in {"O", "A"}:
                        raise ExecutionError()
        except SQLAlchemyError:
            raise ExecutionError() from None

    @contextmanager
    def _work(self, session):
        try:
            if (not isinstance(session, Session) or not session.in_transaction() or not session.is_active
                or not session.get_transaction().is_active):
                raise ExecutionError()
            for mapper in (None, *MAPPERS):
                bind = session.get_bind(mapper=mapper)
                if getattr(bind, "engine", bind) is not self.engine:
                    raise ExecutionError()
            yield
        except SQLAlchemyError:
            raise ExecutionError() from None

    def get(self, session, plan_id, owner_user_id):
        with self._work(session):
            row = session.scalar(select(ExecutionHead).where(ExecutionHead.plan_id == plan_id,
                ExecutionHead.owner_user_id == owner_user_id).with_for_update().execution_options(populate_existing=True))
            if row is None:
                raise ExecutionError(404)
            return row

    @staticmethod
    def next_version(head, expected):
        if head.state_version != expected or expected >= 2_147_483_647:
            raise ExecutionError(409)
        return expected + 1

    def create(self, session, current, source, *, audit_event_id):
        with self._work(session):
            proposal_id = uuid4()
            head = ExecutionHead(plan_id=source.plan_id, source_version_id=source.version_id,
                owner_user_id=current.user_id, is_synthetic=current.is_synthetic, state_version=1, state="draft",
                current_proposal_id=proposal_id, confirmation_id=None, created_at=source.created_at, expires_at=source.expires_at)
            session.add(head)
            session.flush()
            session.add(ExecutionProposal(id=proposal_id, plan_id=head.plan_id, source_version_id=head.source_version_id,
                owner_user_id=head.owner_user_id, is_synthetic=head.is_synthetic, state_version=1,
                payload=proposal_payload((),None,None), draft_sha256=source.draft.draft_sha256, schedule_sha256=None,
                created_at=head.created_at, expires_at=head.expires_at, audit_event_id=audit_event_id))
            session.flush()
            return head

    def append_proposal(self, session, head, request, draft, schedule, *, now, audit_event_id):
        with self._work(session):
            if head.state != "draft":
                raise ExecutionError(409)
            version = self.next_version(head, request.expected_version)
            row = ExecutionProposal(id=uuid4(),plan_id=head.plan_id,source_version_id=head.source_version_id,
                owner_user_id=head.owner_user_id,is_synthetic=head.is_synthetic,state_version=version,
                payload=proposal_payload(request.estimate_overrides,request.schedule,schedule),draft_sha256=draft.draft_sha256,
                schedule_sha256=schedule.schedule_sha256 if schedule is not None else None,created_at=now,
                expires_at=head.expires_at,audit_event_id=audit_event_id)
            session.add(row)
            session.flush()
            head.current_proposal_id, head.state_version = row.id, version
            session.flush()

    def confirm(self, session, head, request_sha256, *, expected_version, now, audit_event_id):
        with self._work(session):
            if head.state != "draft":
                raise ExecutionError(409)
            version = self.next_version(head, expected_version)
            row = ExecutionConfirmation(id=uuid4(),plan_id=head.plan_id,source_version_id=head.source_version_id,
                owner_user_id=head.owner_user_id,is_synthetic=head.is_synthetic,proposal_id=head.current_proposal_id,
                confirmed_state_version=version,request_sha256=request_sha256,acknowledge_unverified_deadlines=True,
                confirmed_at=now,expires_at=head.expires_at,audit_event_id=audit_event_id)
            session.add(row)
            session.flush()
            head.state, head.confirmation_id, head.state_version = "confirmed", row.id, version
            session.flush()

    def complete(self, session, head, task_key, request_sha256, *, expected_version, now, audit_event_id):
        with self._work(session):
            if head.state != "confirmed":
                raise ExecutionError(409)
            existing = session.scalar(select(TaskCompletion).where(TaskCompletion.confirmation_id==head.confirmation_id,
                TaskCompletion.task_key==task_key).with_for_update().execution_options(populate_existing=True))
            if existing is not None:
                if existing.request_sha256 != request_sha256:
                    raise ExecutionError(409)
                return True
            version = self.next_version(head, expected_version)
            session.add(TaskCompletion(id=uuid4(),plan_id=head.plan_id,source_version_id=head.source_version_id,
                owner_user_id=head.owner_user_id,is_synthetic=head.is_synthetic,confirmation_id=head.confirmation_id,
                task_key=task_key,state_version=version,request_sha256=request_sha256,source="student_declared",
                completed_at=now,expires_at=head.expires_at,audit_event_id=audit_event_id))
            session.flush()
            head.state_version = version
            session.flush()
            return False

    def result(self, session, head, source, *, state_version=None):
        with self._work(session):
            try:
                version = head.state_version if state_version is None else state_version
                if type(version) is not int or not 1 <= version <= head.state_version:
                    raise ExecutionError(404)
                if (head.plan_id,head.source_version_id,head.owner_user_id,head.is_synthetic,head.created_at,head.expires_at) != (
                    source.plan_id,source.version_id,head.owner_user_id,source.draft.is_synthetic,source.created_at,source.expires_at):
                    raise ExecutionError()
                proposal = session.scalar(select(ExecutionProposal).where(ExecutionProposal.plan_id==head.plan_id,
                    ExecutionProposal.state_version<=version).order_by(ExecutionProposal.state_version.desc()).limit(1)
                    .with_for_update().execution_options(populate_existing=True))
                if proposal is None:
                    raise ExecutionError()
                payload = proposal.payload
                bounded_payload(payload)
                if type(payload) is not dict or set(payload) != {"estimate_overrides","schedule_configuration","schedule"}:
                    raise ExecutionError()
                configuration = None if payload["schedule_configuration"] is None else ScheduleConfiguration.model_validate(_native_dates(payload["schedule_configuration"]))
                schedule = None if payload["schedule"] is None else ScheduleDraft.model_validate(_native_dates(payload["schedule"]))
                estimates = WorkspaceInput(expected_version=proposal.state_version,estimate_overrides=payload["estimate_overrides"],schedule=configuration).estimate_overrides
                draft = effective_draft(source.draft,estimates)
                if proposal_payload(estimates,configuration,schedule) != payload or proposal.draft_sha256 != draft.draft_sha256 or proposal.schedule_sha256 != (schedule.schedule_sha256 if schedule is not None else None):
                    raise ExecutionError()
                for row in (proposal,):
                    if (row.source_version_id,row.owner_user_id,row.is_synthetic,row.expires_at) != (head.source_version_id,head.owner_user_id,head.is_synthetic,head.expires_at):
                        raise ExecutionError()
                confirmation = session.scalar(select(ExecutionConfirmation).where(ExecutionConfirmation.plan_id==head.plan_id,
                    ExecutionConfirmation.confirmed_state_version<=version).with_for_update().execution_options(populate_existing=True))
                completions = session.scalars(select(TaskCompletion).where(TaskCompletion.plan_id==head.plan_id,
                    TaskCompletion.state_version<=version).order_by(TaskCompletion.state_version).limit(101)
                    .with_for_update().execution_options(populate_existing=True)).all()
                for row in ([confirmation] if confirmation is not None else []) + completions:
                    if (row.source_version_id,row.owner_user_id,row.is_synthetic,row.expires_at) != (head.source_version_id,head.owner_user_id,head.is_synthetic,head.expires_at):
                        raise ExecutionError()
                if confirmation is not None and (confirmation.proposal_id != proposal.id or confirmation.acknowledge_unverified_deadlines is not True):
                    raise ExecutionError()
                if any(confirmation is None or row.confirmation_id != confirmation.id for row in completions):
                    raise ExecutionError()
                if version == head.state_version and (head.current_proposal_id != proposal.id or head.confirmation_id != (confirmation.id if confirmation is not None else None)
                    or head.state != ("confirmed" if confirmation is not None else "draft")):
                    raise ExecutionError()
                return ExecutionData(schema_version="v2.t32",plan_id=head.plan_id,source_plan_version_id=head.source_version_id,
                    source_draft_sha256=source.draft.draft_sha256,state_version=version,state="confirmed" if confirmation is not None else "draft",
                    proposal=ProposalData(id=proposal.id,state_version=proposal.state_version,estimate_overrides=estimates,effective_draft=draft,
                        schedule_configuration=configuration,schedule=schedule,created_at=database_time(proposal.created_at)),
                    confirmation=None if confirmation is None else ConfirmationData(id=confirmation.id,proposal_id=confirmation.proposal_id,
                        confirmed_state_version=confirmation.confirmed_state_version,confirmed_at=database_time(confirmation.confirmed_at),acknowledge_unverified_deadlines=True),
                    completed_tasks=tuple(CompletionData(task_key=r.task_key,completed_state_version=r.state_version,
                        completed_at=database_time(r.completed_at),source=r.source) for r in completions),
                    created_at=database_time(head.created_at),expires_at=database_time(head.expires_at),is_synthetic=head.is_synthetic)
            except ExecutionError:
                raise
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                raise ExecutionError() from None
