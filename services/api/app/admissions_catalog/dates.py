"""Bounded candidate conversion using pinned tzdata, without source review."""

import re
from datetime import datetime, timezone
from importlib.resources import files
from zoneinfo import ZoneInfo

import tzdata

from .date_schemas import DateEventInput, DateResolution


TZDATA_VERSION = "2026.4"
_REGIONS = frozenset({
    "Africa", "America", "Antarctica", "Arctic", "Asia", "Atlantic",
    "Australia", "Europe", "Indian", "Pacific",
})


def _load_timezone(key: str) -> ZoneInfo:
    # Region paths and exact UTC are explicit source keys, not timezone guesses.
    # Component checks also prevent resource traversal before opening any file.
    if type(key) is not str or len(key) > 100:
        raise ValueError("an explicit supported IANA region key or UTC is required")
    parts = key.split("/")
    if key != "UTC" and (
        len(parts) < 2 or parts[0] not in _REGIONS
        or any(re.fullmatch(r"[A-Za-z0-9_+-]+", part) is None for part in parts)
    ):
        raise ValueError("an explicit supported IANA region key or UTC is required")
    if tzdata.__version__ != TZDATA_VERSION:
        raise ValueError("the pinned timezone database is unavailable")
    try:
        resource = files("tzdata.zoneinfo").joinpath(*parts)
        with resource.open("rb") as stream:
            return ZoneInfo.from_file(stream, key=key)
    except (OSError, ValueError, ImportError):
        raise ValueError("the timezone key is unavailable in the pinned database") from None


def normalize_date_event(value: DateEventInput) -> DateResolution:
    """Revalidate a candidate and resolve both folds; never approve a deadline."""
    current = DateEventInput.model_validate(value)

    def resolution(status, instant=None):
        return DateResolution(conversion_status=status, calculated_utc_instant=instant,
                              tzdata_version=TZDATA_VERSION)

    if current.source_alignment == "conflict":
        return resolution("source_conflict")
    if current.precision == "unknown":
        return resolution("unknown")
    if current.precision == "date":
        return resolution("date_only")
    if current.timezone is None:
        return resolution("missing_timezone")

    zone = _load_timezone(current.timezone)
    local = datetime.combine(current.local_date, current.local_time)
    candidates = set()
    try:
        for fold in (0, 1):
            instant = local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
            returned = instant.astimezone(zone).replace(tzinfo=None, fold=0)
            if returned == local:
                candidates.add(instant)
    except (OverflowError, ValueError):
        return resolution("out_of_range")
    if len(candidates) == 1:
        return resolution("unique", candidates.pop())
    return resolution("ambiguous" if candidates else "nonexistent")
