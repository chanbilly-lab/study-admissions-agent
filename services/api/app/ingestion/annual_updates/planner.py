"""Pure annual due calculation with one latest-cycle catch-up, without I/O."""

from datetime import datetime, timezone
from uuid import uuid5
from zoneinfo import ZoneInfo

from .schemas import AnnualPlan, RequestPlan, ScheduleConfig, config_digest, cycle_identity, utc


def scheduled_instant(config: ScheduleConfig, year: int) -> datetime:
    local = datetime(year, config.month, config.day, config.hour, config.minute)
    zone = ZoneInfo(config.timezone)
    candidates = set()
    for fold in (0, 1):
        candidate = local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) == local:
            candidates.add(candidate)
    if len(candidates) != 1:
        raise ValueError("The configured local trigger must identify exactly one instant")
    return candidates.pop()


def build_due_plan(config: ScheduleConfig, now: datetime) -> AnnualPlan | None:
    config = ScheduleConfig.model_validate(config.model_dump())
    current = utc(now)
    if not config.enabled:
        return None
    year = current.astimezone(ZoneInfo(config.timezone)).year
    due_year = year if current >= scheduled_instant(config, year) else year - 1
    if due_year < config.start_cycle_year:
        return None
    if not 2000 <= due_year <= 9998:
        raise ValueError("The requested annual cycle is outside the supported range")
    cycle_id = cycle_identity(config.schedule_id, due_year)
    requests = []
    for target in sorted(config.targets, key=lambda item: item.reference_key):
        target_year = due_year + target.target_year_offset
        if not 1 <= target_year <= 9999:
            raise ValueError("The requested data year is outside the supported range")
        requests.append(RequestPlan(id=uuid5(cycle_id, target.reference_key), target_ref=target.reference_key,
                                    dataset_type=target.dataset_type, scope=target,
                                    entry_year=target_year if target.dataset_type == "entry_requirements" else None,
                                    exam_year=target_year if target.dataset_type != "entry_requirements" else None))
    return AnnualPlan(cycle_id=cycle_id, schedule_id=config.schedule_id, config_revision=config.revision,
                      config_sha256=config_digest(config), cycle_year=due_year,
                      scheduled_at=scheduled_instant(config, due_year), planned_at=current,
                      requests=tuple(requests))
