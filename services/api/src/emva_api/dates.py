"""Reading a time as an advertiser's files write it, in the date order and time zone the person
picked in the Mapping. Pure: no I/O, and never the wall clock.
"""

import enum
import re
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, available_timezones


class DateOrder(enum.StrEnum):
    YEAR_MONTH_DAY = "year_month_day"
    DAY_MONTH_YEAR = "day_month_year"
    MONTH_DAY_YEAR = "month_day_year"


DATE_ORDERS: dict[DateOrder, str] = {
    DateOrder.YEAR_MONTH_DAY: "Year-month-day (2024-01-05)",
    DateOrder.DAY_MONTH_YEAR: "Day-month-year (05/01/2024)",
    DateOrder.MONTH_DAY_YEAR: "Month-day-year (01/05/2024)",
}


class Unreadable(ValueError):
    """Not a time in the order picked; the message never repeats the text."""

    def __init__(self) -> None:
        super().__init__("The time cannot be read.")


_TIME = re.compile(
    r"(?P<a>\d{1,4})[-/.](?P<b>\d{1,2})[-/.](?P<c>\d{1,4})"
    r"(?:[ T](?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2})(?:\.(?P<fraction>\d{1,6}))?)?)?"
    r"\s*(?P<zone>Z|[+-]\d{2}:?\d{2})?"
)


def read_time(text: str, order: DateOrder, zone: tzinfo) -> datetime:
    """The time in UTC. A date starting with a four-digit year is read year-month-day whatever
    the order; any other date must have a four-digit year where the order puts it. A time
    without a zone of its own is read in the given zone."""
    found = _TIME.fullmatch(text.strip())
    if found is None:
        raise Unreadable()
    a, b, c = found["a"], found["b"], found["c"]
    if len(a) == 4 and len(c) <= 2:
        year, month, day = a, b, c
    elif order == DateOrder.YEAR_MONTH_DAY or len(c) != 4 or len(a) > 2:
        raise Unreadable()
    elif order == DateOrder.DAY_MONTH_YEAR:
        day, month, year = a, b, c
    else:
        month, day, year = a, b, c
    try:
        local = datetime(
            int(year),
            int(month),
            int(day),
            int(found["hour"] or 0),
            int(found["minute"] or 0),
            int(found["second"] or 0),
            int((found["fraction"] or "0").ljust(6, "0")),
            tzinfo=_zone(found["zone"]) or zone,
        )
    except ValueError as error:
        raise Unreadable() from error
    return local.astimezone(UTC)


def is_time_zone(name: str) -> bool:
    return name in _TIME_ZONES


def time_zone(name: str) -> tzinfo:
    return ZoneInfo(name)


_TIME_ZONES = frozenset(available_timezones()) | {"UTC"}


def _zone(written: str | None) -> tzinfo | None:
    if written is None:
        return None
    if written == "Z":
        return UTC
    sign = -1 if written[0] == "-" else 1
    digits = written[1:].replace(":", "")
    return timezone(sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:])))
