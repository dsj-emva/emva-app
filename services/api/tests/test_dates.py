"""Times as an advertiser's files write them, read with the date order and time zone the person
picks in the Mapping."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from emva_api.dates import DateOrder, Unreadable, is_time_zone, read_time

LONDON = ZoneInfo("Europe/London")


def utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=UTC)


@pytest.mark.parametrize(
    ("order", "read"),
    [
        (DateOrder.DAY_MONTH_YEAR, utc(2024, 1, 5)),
        (DateOrder.MONTH_DAY_YEAR, utc(2024, 5, 1)),
    ],
)
def test_05_01_2024_is_read_in_the_date_order_picked(order: DateOrder, read: datetime):
    assert read_time("05/01/2024", order, UTC) == read


def test_05_01_2024_is_unreadable_as_year_month_day():
    with pytest.raises(Unreadable):
        read_time("05/01/2024", DateOrder.YEAR_MONTH_DAY, UTC)


@pytest.mark.parametrize("order", list(DateOrder))
def test_a_date_starting_with_a_four_digit_year_is_always_year_month_day(order: DateOrder):
    assert read_time("2024-01-05 10:00", order, UTC) == utc(2024, 1, 5, 10)


@pytest.mark.parametrize(
    ("written", "read"),
    [
        ("05.01.2024", utc(2024, 1, 5)),
        ("5-1-2024", utc(2024, 1, 5)),
        ("05/01/2024 9:05", utc(2024, 1, 5, 9, 5)),
        ("05/01/2024 09:05:30", utc(2024, 1, 5, 9, 5, 30)),
        ("2024/01/05T09:05:30.250", utc(2024, 1, 5, 9, 5, 30, 250000)),
    ],
)
def test_separators_times_and_seconds_are_read(written: str, read: datetime):
    assert read_time(written, DateOrder.DAY_MONTH_YEAR, UTC) == read


def test_a_time_without_a_zone_is_read_in_the_zone_picked_through_summer_time():
    assert read_time("2024-01-05 10:00", DateOrder.YEAR_MONTH_DAY, LONDON) == utc(2024, 1, 5, 10)
    assert read_time("2024-07-05 10:00", DateOrder.YEAR_MONTH_DAY, LONDON) == utc(2024, 7, 5, 9)


@pytest.mark.parametrize(
    "written", ["2024-07-05T12:00+02:00", "2024-07-05 12:00 +0200", "2024-07-05T10:00:00Z"]
)
def test_a_time_with_its_own_zone_keeps_it(written: str):
    assert read_time(written, DateOrder.YEAR_MONTH_DAY, LONDON) == utc(2024, 7, 5, 10)


def test_every_time_read_is_in_utc():
    assert read_time("2024-07-05 10:00", DateOrder.YEAR_MONTH_DAY, LONDON).tzinfo is UTC


@pytest.mark.parametrize(
    "written",
    ["", "TBC", "not recorded", "05/01/24", "31/02/2024", "05/13/2024 10:00", "2024-01-05 25:00"],
)
def test_what_is_not_a_time_in_the_order_picked_is_unreadable(written: str):
    with pytest.raises(Unreadable):
        read_time(written, DateOrder.DAY_MONTH_YEAR, UTC)


def test_a_time_zone_is_a_name_from_the_time_zone_database():
    assert is_time_zone("Europe/London")
    assert is_time_zone("UTC")
    assert not is_time_zone("Europe/Lndon")
    assert not is_time_zone("")
    assert not is_time_zone("../etc/passwd")
