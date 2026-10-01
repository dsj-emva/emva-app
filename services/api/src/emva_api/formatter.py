"""The Formatter: turns an advertiser's leads file and stage-history file, read with a confirmed
Mapping, into Emva's canonical leads and their stage events, outcome included.

Personal data never comes out (decision 0010): names are dropped; the lead identifier, email
and phone are hashed (the files are joined on the identifier's hash); the lead's country and
currency only read its phone and are dropped; every column the Mapping does not mark is dropped.
A row it cannot read is reported by its row number and a reason only, never by its lead or
anything it holds. Pure: no I/O.
"""

import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from pydantic import BaseModel, Field

from emva_api.csv_file import Table
from emva_api.dates import Unreadable as UnreadableTime
from emva_api.dates import read_time, time_zone
from emva_api.ladder import Lost, StageEvent, Won, progress
from emva_api.mapping import ColumnKind, ConfirmedMapping, Mapping
from emva_api.personal_data import hashed_email, hashed_identifier, hashed_phone, phone_region
from emva_api.records import FileKind

# How many row numbers an unreadable-rows report lists for each reason.
FIRST_ROWS = 10


@dataclass(frozen=True)
class FormattedLead:
    identifier_hash: str
    submitted_at: datetime
    email_hash: str | None
    phone_hash: str | None
    # False when the phone's country was not found, so its digits as written were hashed; None
    # without a phone.
    phone_country_found: bool | None
    numbers: dict[str, float | None]
    categories: dict[str, str | None]
    stage_events: tuple[StageEvent, ...] = ()


class UnreadableRows(BaseModel):
    """The rows of one file that could not be read for one reason, and so were not kept."""

    file: FileKind
    reason: str
    count: int
    first_rows: list[int] = Field(
        description=f"The first {FIRST_ROWS} of them, by place in the file from 1 below the header"
    )


class Summary(BaseModel):
    """What the Formatter made of the two files."""

    lead_count: int
    won: int
    lost: int
    no_outcome_yet: int = Field(description="Leads neither won nor lost yet")
    neglected: int = Field(description="Neglected leads: never attempted to contact")
    phones_without_country: int = Field(
        description="Leads whose phone's country was not found, so its digits as written were "
        "hashed; to be resolved later"
    )
    unreadable: list[UnreadableRows]


@dataclass(frozen=True)
class Formatted:
    leads: list[FormattedLead]
    summary: Summary


class Unreadable(Exception):
    """The row cannot be read; the message says why without repeating what it holds."""


def format_lead(cells: dict[str, str], mapping: Mapping) -> FormattedLead:
    """One lead from its leads-file values by column name; a column missing is empty."""
    columns = mapping.leads
    cell = _reader(cells)
    identifier_hash = hashed_identifier(cell(columns.lead_id))
    if identifier_hash is None:
        raise Unreadable("No lead identifier.")
    submitted_at = _time(cell(columns.submitted_at), mapping, "The submission time cannot be read.")
    numbers: dict[str, float | None] = {}
    categories: dict[str, str | None] = {}
    for column, kind in columns.inputs.items():
        if kind is ColumnKind.NUMBER:
            numbers[column] = _number(cell(column), f"“{column}” is not a number.")
        else:
            categories[column] = cell(column) or None
    # The lead's country and currency only read its phone; neither is kept.
    region = phone_region(cell(columns.country), cell(columns.currency))
    phone = hashed_phone(cell(columns.phone), region)
    return FormattedLead(
        identifier_hash=identifier_hash,
        submitted_at=submitted_at,
        email_hash=hashed_email(cell(columns.email)),
        phone_hash=phone and phone.hash,
        phone_country_found=phone and phone.country_found,
        numbers=numbers,
        categories=categories,
    )


def format_stage_event(cells: dict[str, str], mapping: Mapping) -> tuple[str, StageEvent]:
    """One stage-history row: the hash of its lead's identifier, and its stage event."""
    columns = mapping.stage_history
    cell = _reader(cells)
    identifier_hash = hashed_identifier(cell(columns.lead_id))
    if identifier_hash is None:
        raise Unreadable("No lead identifier.")
    crm_stage = cell(columns.crm_stage)
    if not crm_stage:
        raise Unreadable("No CRM stage.")
    at = _time(cell(columns.changed_at), mapping, "The time of the change cannot be read.")
    deal_value = _number(cell(columns.deal_value), "The deal value is not a number.")
    return identifier_hash, StageEvent(mapping.crm_stages[crm_stage], at, deal_value)


def format_files(leads: Table, stage_history: Table, confirmed: ConfirmedMapping) -> Formatted:
    """Both files formatted with the confirmed Mapping; only a confirmed one can be given."""
    mapping = confirmed.mapping
    unreadable: list[tuple[FileKind, int, str]] = []

    by_identifier: dict[str, FormattedLead] = {}
    unreadable_leads: set[str] = set()
    for number, cells in _rows(leads, _leads_columns(mapping)):
        try:
            lead = format_lead(cells, mapping)
            if lead.identifier_hash in by_identifier:
                raise Unreadable("Another row has the same lead identifier.")
        except Unreadable as problem:
            unreadable.append((FileKind.LEADS, number, str(problem)))
            identifier_hash = hashed_identifier(cells.get(mapping.leads.lead_id or "", ""))
            if identifier_hash is not None and identifier_hash not in by_identifier:
                unreadable_leads.add(identifier_hash)
            continue
        by_identifier[lead.identifier_hash] = lead

    events: dict[str, list[StageEvent]] = {identifier: [] for identifier in by_identifier}
    for number, cells in _rows(stage_history, _stage_history_columns(mapping)):
        try:
            identifier_hash, event = format_stage_event(cells, mapping)
            if identifier_hash not in events:
                raise Unreadable(
                    "The lead's row in the leads file could not be read."
                    if identifier_hash in unreadable_leads
                    else "The lead is not in the leads file."
                )
        except Unreadable as problem:
            unreadable.append((FileKind.STAGE_HISTORY, number, str(problem)))
            continue
        events[identifier_hash].append(event)

    formatted = [
        replace(lead, stage_events=tuple(sorted(events[key], key=lambda event: event.at)))
        for key, lead in by_identifier.items()
    ]
    return Formatted(leads=formatted, summary=_summary(formatted, unreadable))


def _summary(leads: list[FormattedLead], unreadable: list[tuple[FileKind, int, str]]) -> Summary:
    progresses = [progress(lead.stage_events) for lead in leads]
    outcomes = Counter(type(lead.outcome) for lead in progresses)
    grouped: dict[tuple[FileKind, str], list[int]] = {}
    counts: Counter[tuple[FileKind, str]] = Counter()
    for file, row, reason in unreadable:
        counts[file, reason] += 1
        rows = grouped.setdefault((file, reason), [])
        if len(rows) < FIRST_ROWS:
            rows.append(row)
    return Summary(
        lead_count=len(leads),
        won=outcomes[Won],
        lost=outcomes[Lost],
        no_outcome_yet=outcomes[type(None)],
        neglected=sum(lead.neglected for lead in progresses),
        phones_without_country=sum(lead.phone_country_found is False for lead in leads),
        unreadable=[
            UnreadableRows(file=file, reason=reason, count=counts[file, reason], first_rows=rows)
            for (file, reason), rows in grouped.items()
        ],
    )


def _leads_columns(mapping: Mapping) -> list[str | None]:
    leads = mapping.leads
    return [
        leads.lead_id,
        leads.submitted_at,
        leads.email,
        leads.phone,
        leads.country,
        leads.currency,
        *leads.inputs,
    ]


def _stage_history_columns(mapping: Mapping) -> list[str | None]:
    history = mapping.stage_history
    return [history.lead_id, history.crm_stage, history.changed_at, history.deal_value]


def _rows(table: Table, wanted: list[str | None]):
    """Each row's place (from 1) and its values in the wanted columns, found once by name."""
    index = {name: table.columns.index(name) for name in wanted if name is not None}
    for number, row in enumerate(table.rows, start=1):
        yield number, {name: row[i] for name, i in index.items()}


def _reader(cells: dict[str, str]) -> Callable[[str | None], str]:
    def cell(column: str | None) -> str:
        return cells.get(column, "").strip() if column is not None else ""

    return cell


def _time(text: str, mapping: Mapping, problem: str) -> datetime:
    assert mapping.date_order is not None, "a confirmed Mapping has a date order"
    try:
        return read_time(text, mapping.date_order, time_zone(mapping.time_zone))
    except UnreadableTime as error:
        raise Unreadable(problem) from error


def _number(text: str, problem: str) -> float | None:
    if not text:
        return None
    try:
        number = float(text)
    except ValueError as error:
        raise Unreadable(problem) from error
    if not math.isfinite(number):
        raise Unreadable(problem)
    return number
