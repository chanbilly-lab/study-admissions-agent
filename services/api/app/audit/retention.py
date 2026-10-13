"""D06 product upper limits, independent of a deployed collector or legal hold."""

from calendar import monthrange
from datetime import datetime, timezone

LOG_MAX_DAYS = 30
AUDIT_MAX_MONTHS = 24


def expires_after_months(occurred_at: datetime, months: int = AUDIT_MAX_MONTHS):
    if (not isinstance(occurred_at, datetime) or occurred_at.tzinfo is None or occurred_at.utcoffset() is None
        or type(months) is not int or not 1 <= months <= AUDIT_MAX_MONTHS):
        raise ValueError("finite calendar retention is required")
    value = occurred_at.astimezone(timezone.utc)
    month_index = value.year * 12 + value.month - 1 + months
    year, month = divmod(month_index, 12)
    return value.replace(year=year, month=month + 1, day=min(value.day, monthrange(year, month + 1)[1]))
