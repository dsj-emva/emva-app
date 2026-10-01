"""Decision 0006: nothing but the clock module reads the system clock."""

import ast
from pathlib import Path

import pytest

import emva_api

CLOCK_READS = {"now", "utcnow", "today", "fromtimestamp", "utcfromtimestamp"}
CLOCK_MODULES = {"time", "calendar"}


def system_clock_reads(source: str) -> list[str]:
    """Every place the code could read the system clock, however datetime or time is imported."""
    tree = ast.parse(source)
    datetime_modules: set[str] = set()  # names bound to the datetime module
    datetime_classes: set[str] = set()  # names bound to datetime.datetime or datetime.date
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "datetime":
                    datetime_modules.add(alias.asname or alias.name)
                if alias.name.split(".")[0] in CLOCK_MODULES:
                    found.append(f"line {node.lineno}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "datetime":
                for alias in node.names:
                    if alias.name in {"datetime", "date"}:
                        datetime_classes.add(alias.asname or alias.name)
            if node.module and node.module.split(".")[0] in CLOCK_MODULES:
                found.append(f"line {node.lineno}: imports from {node.module}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            base = node.value
            reads_datetime = node.attr in CLOCK_READS and (
                (isinstance(base, ast.Name) and base.id in datetime_classes)
                or (
                    isinstance(base, ast.Attribute)
                    and base.attr in {"datetime", "date"}
                    and isinstance(base.value, ast.Name)
                    and base.value.id in datetime_modules
                )
            )
            database_now = node.attr == "now" and isinstance(base, ast.Name) and base.id == "func"
            if reads_datetime or database_now:
                found.append(f"line {node.lineno}: {ast.unparse(node)}")
    return found


@pytest.mark.parametrize(
    "source",
    [
        "from datetime import datetime\ndatetime.now()",
        "from datetime import datetime as dt\ndt.now(UTC)",
        "from datetime import date as d\nd.today()",
        "import datetime\ndatetime.datetime.utcnow()",
        "import datetime as when\nwhen.date.today()",
        "import datetime as when\nstamp = when.datetime.now",
        "import time",
        "import time as t",
        "from time import monotonic",
        "from sqlalchemy import func\nfunc.now()",
    ],
)
def test_the_guard_catches_a_read_of_the_system_clock(source: str):
    assert system_clock_reads(source) != []


@pytest.mark.parametrize(
    "source",
    [
        "from datetime import UTC, datetime\nx: datetime = datetime(2026, 1, 1, tzinfo=UTC)",
        "def f(clock):\n    return clock.now()",
        "from datetime import datetime\ndatetime.fromisoformat('2026-01-01')",
    ],
)
def test_the_guard_allows_code_that_takes_time_from_the_clock(source: str):
    assert system_clock_reads(source) == []


def test_no_module_but_the_clock_reads_the_system_clock():
    package = Path(emva_api.__file__).parent
    offenders = [
        f"{path.relative_to(package)} {read}"
        for path in package.rglob("*.py")
        if path.name != "clock.py"
        for read in system_clock_reads(path.read_text())
    ]

    assert offenders == []
