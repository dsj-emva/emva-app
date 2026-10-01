"""The Formatter: turns an advertiser's leads file and stage-history file, read with a confirmed
Mapping, into Emva's canonical leads and their stage events, outcome included.

Personal data never comes out (decision 0010): names are dropped, email and phone are hashed,
and every column the Mapping does not mark is dropped. A row it cannot read is reported with a
reason that names its lead but never repeats what the row holds. Pure: no I/O.
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from emva_api.csv_file import Table
from emva_api.ladder import Lost, Stage, StageEvent, Unfinished, Won, progress
from emva_api.mapping import ColumnKind, ConfirmedMapping
from emva_api.personal_data import hashed_email, hashed_phone
from emva_api.records import FileKind

type InputValue = float | str | None


@dataclass(frozen=True)
class FormattedLead:
    identifier: str
    submitted_at: datetime
    email_hash: str | None
    phone_hash: str | None
    inputs: dict[str, InputValue]
    stage_events: list[StageEvent] = field(default_factory=list)


@dataclass(frozen=True)
class UnreadableRow:
    file: FileKind
    row: int  # the row's place in its file, counting from 1 below the header
    lead: str | None  # the row's lead identifier, when it has one
    reason: str


@dataclass(frozen=True)
class Summary:
    lead_count: int
    won: int
    lost: int
    unfinished: int
    never_reached_contact_attempted: int


@dataclass(frozen=True)
class Formatted:
    leads: list[FormattedLead]
    unreadable: list[UnreadableRow]

    def summary(self) -> Summary:
        progresses = [progress(lead.stage_events) for lead in self.leads]
        outcomes = Counter(type(lead.outcome) for lead in progresses)
        return Summary(
            lead_count=len(self.leads),
            won=outcomes[Won],
            lost=outcomes[Lost],
            unfinished=outcomes[Unfinished],
            never_reached_contact_attempted=sum(
                not lead.reached(Stage.CONTACT_ATTEMPTED) for lead in progresses
            ),
        )


class _Unreadable(Exception):
    pass


def format_files(leads: Table, stage_history: Table, confirmed: ConfirmedMapping) -> Formatted:
    """Both files formatted with the confirmed Mapping; only a confirmed one can be given."""
    mapping = confirmed.mapping
    unreadable: list[UnreadableRow] = []

    columns = mapping.leads
    by_identifier: dict[str, FormattedLead] = {}
    unreadable_leads: set[str] = set()
    for number, row in enumerate(leads.rows, start=1):
        cell = _cells(leads, row)
        identifier = cell(columns.lead_id)
        try:
            if not identifier:
                raise _Unreadable("No lead identifier.")
            if identifier in by_identifier or identifier in unreadable_leads:
                raise _Unreadable("Another row has the same lead identifier.")
            submitted_at = _time(cell(columns.submitted_at), "The submission time cannot be read.")
            inputs = {
                column: _input(cell(column), column, kind)
                for column, kind in columns.inputs.items()
            }
        except _Unreadable as problem:
            unreadable.append(
                UnreadableRow(FileKind.LEADS, number, identifier or None, str(problem))
            )
            if identifier and identifier not in by_identifier:
                unreadable_leads.add(identifier)
            continue
        by_identifier[identifier] = FormattedLead(
            identifier=identifier,
            submitted_at=submitted_at,
            email_hash=hashed_email(cell(columns.email)),
            phone_hash=hashed_phone(cell(columns.phone)),
            inputs=inputs,
        )

    history = mapping.stage_history
    for number, row in enumerate(stage_history.rows, start=1):
        cell = _cells(stage_history, row)
        identifier = cell(history.lead_id)
        try:
            if not identifier:
                raise _Unreadable("No lead identifier.")
            crm_stage = cell(history.crm_stage)
            if not crm_stage:
                raise _Unreadable("No CRM stage.")
            at = _time(cell(history.changed_at), "The time of the change cannot be read.")
            deal_value = _number(cell(history.deal_value), "The deal value is not a number.")
            lead = by_identifier.get(identifier)
            if lead is None:
                raise _Unreadable(
                    "The lead's row in the leads file could not be read."
                    if identifier in unreadable_leads
                    else "The lead is not in the leads file."
                )
        except _Unreadable as problem:
            unreadable.append(
                UnreadableRow(FileKind.STAGE_HISTORY, number, identifier or None, str(problem))
            )
            continue
        lead.stage_events.append(StageEvent(mapping.crm_stages[crm_stage], at, deal_value))

    for lead in by_identifier.values():
        lead.stage_events.sort(key=lambda event: event.at)
    return Formatted(leads=list(by_identifier.values()), unreadable=unreadable)


def _cells(table: Table, row: list[str]):
    """The row's value in a named column, trimmed; empty when no column is named."""

    def cell(column: str | None) -> str:
        return row[table.columns.index(column)].strip() if column is not None else ""

    return cell


def _time(text: str, problem: str) -> datetime:
    """An ISO 8601 date or time; one written without a zone is read as UTC."""
    try:
        read = datetime.fromisoformat(text)
    except ValueError as error:
        raise _Unreadable(problem) from error
    return read.replace(tzinfo=UTC) if read.tzinfo is None else read.astimezone(UTC)


def _number(text: str, problem: str) -> float | None:
    if not text:
        return None
    try:
        number = float(text)
    except ValueError as error:
        raise _Unreadable(problem) from error
    if not math.isfinite(number):
        raise _Unreadable(problem)
    return number


def _input(text: str, column: str, kind: ColumnKind) -> InputValue:
    if kind is ColumnKind.NUMBER:
        return _number(text, f"“{column}” is not a number.")
    return text or None
