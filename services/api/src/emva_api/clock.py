"""The injected clock (decision 0006): the only place in Emva that reads the wall clock.

Everything that needs "now" takes a Clock, so the same code runs in real time, on a simulated clock and in
tests on a fixed one.
"""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """A clock that stays where it is put; for tests."""

    def __init__(self, at: datetime) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = at
