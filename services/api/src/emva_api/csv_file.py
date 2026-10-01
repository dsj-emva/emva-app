"""Reading a CSV file as a CRM exports it, and describing what is in it.

Pure: takes the file's bytes, never a path.
"""

import csv
import io
from collections import Counter
from dataclasses import dataclass

EXAMPLES_PER_COLUMN = 3


class UnreadableFile(Exception):
    """The file cannot be read as a CSV file with a header row; the message says why."""


@dataclass(frozen=True)
class Table:
    columns: list[str]
    rows: list[list[str]]

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    examples: list[str]


def read_csv(content: bytes) -> Table:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise UnreadableFile("The file is not a readable CSV file.") from error
    if "\x00" in text:
        raise UnreadableFile("The file is not a readable CSV file.")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        lines = [line for line in reader if any(cell.strip() for cell in line)]
    except csv.Error as error:
        raise UnreadableFile("The file is not a readable CSV file.") from error

    if not lines:
        raise UnreadableFile("The file is empty.")
    header, *rows = lines
    columns = [name.strip() for name in header]
    if not _is_header(columns):
        raise UnreadableFile(
            "The file has no header row: its first line must name every column, each name once."
        )
    if not rows:
        raise UnreadableFile("The file has a header row but no rows below it.")
    width = len(columns)
    return Table(columns=columns, rows=[(row + [""] * width)[:width] for row in rows])


def profile(table: Table) -> list[ColumnProfile]:
    return [
        ColumnProfile(name=name, examples=_first_distinct_values(table, index))
        for index, name in enumerate(table.columns)
    ]


def count_values(table: Table, column: str) -> list[tuple[str, int]]:
    """How many rows use each non-empty value of the column, most used first."""
    index = table.columns.index(column)
    counts = Counter(row[index].strip() for row in table.rows if row[index].strip())
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _is_header(columns: list[str]) -> bool:
    return (
        all(columns)
        and len(set(columns)) == len(columns)
        and not any(_is_number(name) for name in columns)
    )


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _first_distinct_values(table: Table, index: int) -> list[str]:
    examples: list[str] = []
    for row in table.rows:
        value = row[index].strip()
        if value and value not in examples:
            examples.append(value)
            if len(examples) == EXAMPLES_PER_COLUMN:
                break
    return examples
