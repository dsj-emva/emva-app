from datetime import UTC, datetime

from emva_api.clock import FixedClock, SystemClock


def test_fixed_clock_tells_the_time_it_was_set_to():
    clock = FixedClock(datetime(2026, 3, 14, 9, 30, tzinfo=UTC))

    assert clock.now() == datetime(2026, 3, 14, 9, 30, tzinfo=UTC)


def test_fixed_clock_can_be_moved():
    clock = FixedClock(datetime(2026, 3, 14, 9, 30, tzinfo=UTC))

    clock.set(datetime(2026, 4, 1, 12, 0, tzinfo=UTC))

    assert clock.now() == datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


def test_system_clock_tells_an_aware_utc_time():
    assert SystemClock().now().tzinfo is UTC
