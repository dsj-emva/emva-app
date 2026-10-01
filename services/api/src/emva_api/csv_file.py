"""Reading a CSV file as a CRM exports it, and describing what is in it.

Pure: takes the file's bytes, never a path.
"""

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

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


class ColumnFacts(BaseModel):
    """What a column's values are like, without any of them: kept to check the Mapping."""

    model_config = ConfigDict(frozen=True)

    distinct_values: int = Field(description="How many distinct non-empty values it holds")
    looks_like_contact: bool = Field(description="Whether any value looks like an email or phone")


_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
# A number starting with "+" or "0", as phones are written, of digits in groups.
_PHONE = re.compile(r"(?<!\w)\(?(?:\+|0)[\d\s().-]*\d(?![\d:])")
_PHONE_DIGITS = range(9, 16)


def column_facts(table: Table) -> dict[str, ColumnFacts]:
    facts = {}
    for index, name in enumerate(table.columns):
        values = {row[index].strip() for row in table.rows} - {""}
        facts[name] = ColumnFacts(
            distinct_values=len(values),
            looks_like_contact=any(_looks_like_contact(value) for value in values),
        )
    return facts


def _looks_like_contact(value: str) -> bool:
    if _EMAIL.search(value):
        return True
    return any(
        sum(c.isdigit() for c in found.group()) in _PHONE_DIGITS for found in _PHONE.finditer(value)
    )


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
