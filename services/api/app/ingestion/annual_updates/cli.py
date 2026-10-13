"""Explicit preview/tick/worker commands; never start with FastAPI or migrate."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
from threading import Event
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from .db import annual_database_url
from .planner import build_due_plan, scheduled_instant
from .schemas import ScheduleConfig, utc
from .store import persist_plan


class OperationError(Exception):
    def __init__(self, code: str):
        self.code = code


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate configuration field")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("Non-finite configuration value")


def load_config(path: Path) -> ScheduleConfig:
    try:
        with path.open("rb") as handle:
            body = handle.read(32769)
        if not 1 <= len(body) <= 32768:
            raise ValueError()
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
        return ScheduleConfig.model_validate(value)
    except Exception:
        raise OperationError("CONFIGURATION_INVALID") from None


def result(status: str, **values) -> dict:
    return {"schema_version": "annual.source.result.1", "status": status,
            "network_requested": False, "facts_updated": False, "published": False, **values}


def next_trigger(config: ScheduleConfig, now: datetime) -> datetime:
    year = max(now.astimezone(ZoneInfo(config.timezone)).year, config.start_cycle_year)
    candidate = scheduled_instant(config, year)
    if candidate <= now:
        if year >= 9998:
            raise ValueError("No further cycle in the supported range")
        candidate = scheduled_instant(config, year + 1)
    return candidate


def tick(config: ScheduleConfig, now: datetime, *, apply: bool = False) -> dict:
    # No database environment, connection, HTTP, or model is touched for disabled/dry-run.
    try:
        config = ScheduleConfig.model_validate(config.model_dump())
        now = utc(now)
        if not config.enabled:
            return result("disabled", request_count=0)
        plan = build_due_plan(config, now)
        if plan is None:
            return result("not_due", request_count=0, next_due_at=next_trigger(config, now).isoformat())
        if not apply:
            return result("dry_run", persisted=False, plan=plan.model_dump(mode="json"))
    except Exception:
        raise OperationError("SCHEDULE_INVALID") from None
    engine = None
    try:
        url = annual_database_url(os.environ.get("ANNUAL_UPDATES_DATABASE_URL"))
        engine = create_engine(url, hide_parameters=True, echo=False, poolclass=NullPool,
                               connect_args={"connect_timeout": 5})
        with engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
            connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
            saved = persist_plan(connection, plan, config)
        # This return occurs only after the transaction has committed successfully.
        return result(saved.pop("status"), **saved)
    except Exception:
        raise OperationError("SCHEDULE_DATABASE_UNAVAILABLE") from None
    finally:
        if engine is not None:
            engine.dispose()


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True), flush=True)


def run_worker(path: Path) -> int:
    stop = Event()
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda _signum, _frame: stop.set())
    failures = 0
    last_message = None
    while not stop.is_set():
        # Re-read to honour a pause; an invalid config fails closed, never uses the old one.
        config = load_config(path)
        if not config.enabled:
            emit(result("disabled", request_count=0))
            return 0
        now = datetime.now(timezone.utc)
        try:
            saved = tick(config, now, apply=True)
            failures = 0
            signature = json.dumps(saved, sort_keys=True)
            if signature != last_message:
                emit(saved)
                last_message = signature
            if saved["status"] == "configuration_conflict":
                # Existing cycle remains intact. A maintainer must resolve this change.
                return 1
            delay = min(config.poll_interval_seconds,
                        max(1.0, (next_trigger(config, datetime.now(timezone.utc))
                                  - datetime.now(timezone.utc)).total_seconds()))
        except OperationError as error:
            failures += 1
            emit(result("retrying" if failures < config.max_consecutive_failures else "failed",
                        error=error.code, consecutive_failures=failures))
            if failures >= config.max_consecutive_failures:
                return 1
            delay = min(config.poll_interval_seconds, 60 * 2 ** (failures - 1))
        # Event.wait is interruptible; no thread, timer, or worker is installed on import.
        stop.wait(delay)
    emit(result("stopped"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Internal annual collection requests; no fact refresh or publication")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "tick", "run"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name != "plan":
            command.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "run":
            if not args.apply:
                raise OperationError("APPLY_REQUIRED")
            return run_worker(args.config)
        config = load_config(args.config)
        saved = tick(config, datetime.now(timezone.utc), apply=args.command == "tick" and args.apply)
        emit(saved)
        return 1 if saved["status"] == "configuration_conflict" else 0
    except OperationError as error:
        emit(result("failed", error=error.code))
        return 1
    except Exception:
        # Never print SQL URLs, filenames, raw config, input values, or tracebacks.
        emit(result("failed", error="ANNUAL_SCHEDULE_OPERATION_FAILED"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
