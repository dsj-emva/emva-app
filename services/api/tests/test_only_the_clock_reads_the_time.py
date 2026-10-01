"""Decision 0006: nothing but the clock module reads the system clock."""

import re
from pathlib import Path

import emva_api

READS_THE_SYSTEM_CLOCK = re.compile(
    r"\b(datetime\.(now|utcnow|today)|date\.today|time\.(time|time_ns|monotonic|localtime|gmtime))\b"
    r"|\bfunc\.now\b|\bserver_default\s*=\s*func\."
)


def test_no_module_but_the_clock_reads_the_system_clock():
    package = Path(emva_api.__file__).parent
    offenders = [
        f"{path.relative_to(package)}:{number}: {line.strip()}"
        for path in package.rglob("*.py")
        if path.name != "clock.py"
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if READS_THE_SYSTEM_CLOCK.search(line)
    ]

    assert offenders == []
