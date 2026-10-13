"""Same-transaction append-only request batches, never a collector or publisher."""

from hashlib import sha256

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db import require_maintenance
from .models import AnnualSourceCycle, AnnualSourceUpdateRequest
from .planner import scheduled_instant
from .schemas import AnnualPlan, ScheduleConfig, canonical, config_digest, utc


def _payload(model, limit):
    value = model.model_dump(mode="json")
    if len(canonical(value)) > limit:
        raise ValueError("ANNUAL_PAYLOAD_LIMIT_EXCEEDED")
    return value


def _bound_plan(plan, config):
    current_config = ScheduleConfig.model_validate(config.model_dump())
    current_plan = AnnualPlan.model_validate(plan.model_dump())
    if not current_config.enabled:
        raise ValueError("ANNUAL_SCHEDULE_DISABLED")
    if (current_plan.schedule_id != current_config.schedule_id
            or current_plan.config_revision != current_config.revision
            or current_plan.config_sha256 != config_digest(current_config)
            or current_plan.cycle_year < current_config.start_cycle_year
            or current_plan.scheduled_at != scheduled_instant(current_config, current_plan.cycle_year)):
        raise ValueError("ANNUAL_PLAN_CONFIGURATION_MISMATCH")
    targets = {target.reference_key: target.model_dump(mode="json") for target in current_config.targets}
    requests = {request.target_ref: request for request in current_plan.requests}
    if set(targets) != set(requests) or any(request.scope.model_dump(mode="json") != targets[ref]
                                          for ref, request in requests.items()):
        raise ValueError("ANNUAL_PLAN_TARGET_MISMATCH")
    return current_plan, current_config


def _saved_cycle(connection, row):
    saved_config = ScheduleConfig.model_validate(row["config_snapshot"])
    saved_plan = AnnualPlan.model_validate(row["plan_payload"])
    saved_plan, saved_config = _bound_plan(saved_plan, saved_config)
    if (row["id"] != saved_plan.cycle_id or row["schedule_id"] != saved_plan.schedule_id
            or row["cycle_year"] != saved_plan.cycle_year or row["config_revision"] != saved_plan.config_revision
            or row["config_sha256"] != saved_plan.config_sha256
            or row["config_snapshot"] != saved_config.model_dump(mode="json")
            or row["plan_payload"] != saved_plan.model_dump(mode="json")
            or utc(row["scheduled_at"]) != saved_plan.scheduled_at
            or utc(row["created_at"]) != saved_plan.planned_at
            or row["request_count"] != len(saved_plan.requests)):
        raise ValueError("ANNUAL_PERSISTED_CYCLE_INTEGRITY_MISMATCH")
    rows = connection.execute(select(AnnualSourceUpdateRequest.__table__).where(
        AnnualSourceUpdateRequest.__table__.c.cycle_id == row["id"])).mappings().all()
    expected = {request.target_ref: request for request in saved_plan.requests}
    if len(rows) != len(expected) or {request["target_ref"] for request in rows} != set(expected):
        raise ValueError("ANNUAL_PERSISTED_REQUEST_INTEGRITY_MISMATCH")
    for request in rows:
        wanted = expected[request["target_ref"]]
        payload = wanted.model_dump(mode="json")
        if (request["id"] != wanted.id or request["cycle_id"] != saved_plan.cycle_id
                or request["kind"] != wanted.dataset_type or request["exam_year"] != wanted.exam_year
                or request["entry_year"] != wanted.entry_year or request["payload"] != payload
                or request["payload_sha256"] != sha256(canonical(payload)).hexdigest()):
            raise ValueError("ANNUAL_PERSISTED_REQUEST_INTEGRITY_MISMATCH")
    return saved_plan, saved_config


def _result(status, plan):
    return {"status": status, "cycle_id": str(plan.cycle_id), "cycle_year": plan.cycle_year,
            "request_count": len(plan.requests), "network_requested": False,
            "facts_updated": False, "published": False}


def persist_plan(connection, plan: AnnualPlan, config: ScheduleConfig) -> dict:
    """Caller commits only after success; a savepoint protects a failed batch.

    The annual natural key excludes the current execution timestamp and config
    revision. A changed configuration never overwrites or silently recreates an
    already recorded cycle. Returning does not confirm the outer commit succeeded.
    """
    try:
        # Disabled or invalid configuration is rejected before any SQL read.
        current_plan, current_config = _bound_plan(plan, config)
        config_payload = _payload(current_config, 65536)
        plan_payload = _payload(current_plan, 131072)
        request_values = []
        for request in current_plan.requests:
            payload = _payload(request, 16384)
            request_values.append({"id": request.id, "cycle_id": current_plan.cycle_id,
                "target_ref": request.target_ref, "kind": request.dataset_type,
                "exam_year": request.exam_year, "entry_year": request.entry_year,
                "payload": payload, "payload_sha256": sha256(canonical(payload)).hexdigest()})
        require_maintenance(connection)
        with connection.begin_nested():
            created = connection.execute(pg_insert(AnnualSourceCycle.__table__).values(
                id=current_plan.cycle_id, schedule_id=current_plan.schedule_id,
                cycle_year=current_plan.cycle_year, config_revision=current_plan.config_revision,
                config_sha256=current_plan.config_sha256, config_snapshot=config_payload,
                plan_payload=plan_payload, scheduled_at=current_plan.scheduled_at,
                created_at=current_plan.planned_at, request_count=len(request_values)
            ).on_conflict_do_nothing(index_elements=["schedule_id", "cycle_year"])
              .returning(AnnualSourceCycle.__table__.c.id)).scalar_one_or_none()
            if created is not None:
                connection.execute(insert(AnnualSourceUpdateRequest.__table__), request_values)
            row = connection.execute(select(AnnualSourceCycle.__table__).where(
                AnnualSourceCycle.__table__.c.schedule_id == current_plan.schedule_id,
                AnnualSourceCycle.__table__.c.cycle_year == current_plan.cycle_year)).mappings().one()
            saved_plan, _ = _saved_cycle(connection, row)
            if created is not None:
                if saved_plan != current_plan:
                    raise ValueError("ANNUAL_NEW_CYCLE_INTEGRITY_MISMATCH")
                result = _result("requests_created", saved_plan)
            elif saved_plan.config_sha256 != current_plan.config_sha256:
                result = _result("configuration_conflict", saved_plan)
            else:
                # planned_at may legitimately differ on a subsequent tick.
                result = _result("already_requested", saved_plan)
        return result
    except Exception:
        # Never leak DSNs, SQL, driver messages, input values, or server paths.
        raise ValueError("ANNUAL_REQUEST_PERSISTENCE_FAILED") from None
