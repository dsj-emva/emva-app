"""The Mapping: what each column of an advertiser's two files means and where each CRM stage sits
on the Canonical ladder; and the rules that decide whether a person may confirm it.

A Mapping is a draft until a person confirms it. Pure: no I/O; the time of confirmation is given.
"""

import enum
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from emva_api.csv_file import ColumnFacts
from emva_api.dates import DateOrder, is_time_zone
from emva_api.ladder import Stage, StageOrLost


class ColumnKind(enum.StrEnum):
    """How an input column is read: as a number, or as one of a set of categories."""

    NUMBER = "number"
    CATEGORY = "category"


class LeadsColumns(BaseModel):
    """Which leads-file column holds what. Every column not marked here is dropped."""

    model_config = ConfigDict(frozen=True)

    lead_id: str | None = None
    submitted_at: str | None = Field(None, description="When the lead was submitted")
    name: str | None = Field(None, description="The lead's name, to be removed")
    email: str | None = Field(None, description="The lead's email, to be scrambled")
    phone: str | None = Field(None, description="The lead's phone, to be scrambled")
    country: str | None = Field(
        None, description="The lead's country, used only to read its phone, then dropped"
    )
    currency: str | None = Field(
        None, description="The lead's currency, used only to read its phone, then dropped"
    )
    inputs: dict[str, ColumnKind] = Field(
        default_factory=dict, description="The inputs to the score, each read as its kind"
    )


class StageHistoryColumns(BaseModel):
    model_config = ConfigDict(frozen=True)

    lead_id: str | None = None
    crm_stage: str | None = None
    changed_at: str | None = Field(None, description="When the change of CRM stage happened")
    deal_value: str | None = None


class Mapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    leads: LeadsColumns = LeadsColumns()
    stage_history: StageHistoryColumns = StageHistoryColumns()
    crm_stages: dict[str, StageOrLost] = Field(
        default_factory=dict, description="Where each CRM stage name sits: a Stage, or Lost"
    )
    typical_deal_size: float | None = Field(None, allow_inf_nan=False)
    date_order: DateOrder | None = Field(None, description="The order both files write dates in")
    time_zone: str = Field("UTC", description="The zone of every time written without one")


@dataclass(frozen=True)
class Files:
    """What the uploaded files hold, as far as the Mapping is concerned."""

    leads_columns: list[str]
    stage_history_columns: list[str]
    # Every CRM stage name in the column marked as the CRM stage.
    crm_stages: list[str]
    leads_row_count: int = 0
    # What each leads-file column's values are like; a column without facts is not checked.
    leads_column_facts: dict[str, ColumnFacts] = field(default_factory=dict)


def most_categories(row_count: int) -> int:
    """The most distinct values a category input may have: more and it is not a category."""
    return max(20, row_count // 4)


@dataclass(frozen=True)
class ConfirmedMapping:
    mapping: Mapping
    confirmed_at: datetime


class NotConfirmable(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


class LeadsRole(enum.StrEnum):
    """What a leads-file column can hold besides an input; each is a field of LeadsColumns."""

    LEAD_ID = "lead_id"
    SUBMITTED_AT = "submitted_at"
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    COUNTRY = "country"
    CURRENCY = "currency"


class StageHistoryRole(enum.StrEnum):
    """What a stage-history column can hold; each is a field of StageHistoryColumns."""

    LEAD_ID = "lead_id"
    CRM_STAGE = "crm_stage"
    CHANGED_AT = "changed_at"
    DEAL_VALUE = "deal_value"


@dataclass(frozen=True)
class Role:
    label: str  # as the screen names it
    holds: str  # as a sentence names it
    required: bool = False


LEADS_ROLES: dict[LeadsRole, Role] = {
    LeadsRole.LEAD_ID: Role("Lead identifier", "the lead identifier", required=True),
    LeadsRole.SUBMITTED_AT: Role("Submission time", "the submission time", required=True),
    LeadsRole.NAME: Role("Name (removed)", "the lead's name"),
    LeadsRole.EMAIL: Role("Email (scrambled)", "the lead's email"),
    LeadsRole.PHONE: Role("Phone (scrambled)", "the lead's phone"),
    LeadsRole.COUNTRY: Role("Country (reads the phone)", "the lead's country"),
    LeadsRole.CURRENCY: Role("Currency (reads the phone)", "the lead's currency"),
}
STAGE_HISTORY_ROLES: dict[StageHistoryRole, Role] = {
    StageHistoryRole.LEAD_ID: Role("Lead identifier", "the lead identifier", required=True),
    StageHistoryRole.CRM_STAGE: Role("CRM stage", "the CRM stage", required=True),
    StageHistoryRole.CHANGED_AT: Role(
        "When the change happened", "when the change happened", required=True
    ),
    StageHistoryRole.DEAL_VALUE: Role("Deal value", "the deal value"),
}
INPUT_KINDS: dict[ColumnKind, str] = {ColumnKind.NUMBER: "Number", ColumnKind.CATEGORY: "Category"}
_AN_INPUT = "an input to the score"


def problems(mapping: Mapping, files: Files) -> list[str]:
    """Every reason the mapping cannot be confirmed yet, in the order the screen shows them."""
    leads, history = mapping.leads, mapping.stage_history
    leads_marks = [(getattr(leads, role), LEADS_ROLES[role]) for role in LeadsRole]
    history_marks = [
        (getattr(history, role), STAGE_HISTORY_ROLES[role]) for role in StageHistoryRole
    ]
    leads_holds = [(column, role.holds) for column, role in leads_marks] + [
        (column, _AN_INPUT) for column in leads.inputs
    ]
    history_holds = [(column, role.holds) for column, role in history_marks]

    found = [
        *_unmarked("leads file", leads_marks),
        *_not_in_file("leads file", leads_holds, files.leads_columns),
        *_unmarked("stage-history file", history_marks),
        *_not_in_file("stage-history file", history_holds, files.stage_history_columns),
        *_several_roles("leads file", leads_holds),
        *_several_roles("stage-history file", history_holds),
    ]

    if history.crm_stage in files.stage_history_columns:
        for name in files.crm_stages:
            if name not in mapping.crm_stages:
                found.append(f"Place the CRM stage “{name}” on the canonical ladder or on Lost.")
        if not any(mapping.crm_stages.get(name) is Stage.WON for name in files.crm_stages):
            found.append("Place at least one CRM stage on Won.")

    found += _category_problems(leads.inputs, files)

    if mapping.date_order is None:
        found.append("Pick the order the files write dates in.")
    if not is_time_zone(mapping.time_zone):
        found.append(
            f"“{mapping.time_zone}” is not a time zone; use a name such as Europe/London or UTC."
        )

    if mapping.typical_deal_size is None:
        found.append("Enter the typical deal size.")
    elif mapping.typical_deal_size <= 0:
        found.append("The typical deal size must be more than zero.")
    return found


def confirm(mapping: Mapping, files: Files, at: datetime) -> ConfirmedMapping:
    """The mapping confirmed at the given time, keeping only the CRM stages the file uses."""
    refusals = problems(mapping, files)
    if refusals:
        raise NotConfirmable(refusals)
    used = {name: on for name, on in mapping.crm_stages.items() if name in files.crm_stages}
    confirmed = mapping.model_copy(update={"crm_stages": used})
    return ConfirmedMapping(mapping=confirmed, confirmed_at=at)


def _category_problems(inputs: dict[str, ColumnKind], files: Files) -> list[str]:
    """A category input can carry neither contact details nor free text (decision 0010)."""
    found = []
    most = most_categories(files.leads_row_count)
    for column, kind in inputs.items():
        facts = files.leads_column_facts.get(column)
        if kind is not ColumnKind.CATEGORY or facts is None:
            continue
        if facts.looks_like_contact:
            found.append(
                f"“{column}” cannot be a category input: some of its values look like email "
                "addresses or phone numbers."
            )
        elif facts.distinct_values > most:
            found.append(
                f"“{column}” cannot be a category input: it has {facts.distinct_values} "
                f"different values, more than the {most} a category may have in this file."
            )
    return found


def _unmarked(file: str, marks: list[tuple[str | None, Role]]) -> list[str]:
    return [
        f"Mark the {file}'s column holding {role.holds}."
        for column, role in marks
        if role.required and column is None
    ]


def _not_in_file(file: str, holds: list[tuple[str | None, str]], columns: list[str]) -> list[str]:
    return [
        f"The {file} has no column “{column}”."
        for column, _ in holds
        if column is not None and column not in columns
    ]


def _several_roles(file: str, holds: list[tuple[str | None, str]]) -> list[str]:
    """One reason for each column marked as holding more than one thing."""
    roles: dict[str, list[str]] = {}
    for column, what in holds:
        if column is not None:
            roles.setdefault(column, []).append(what)
    return [
        f"The {file}'s column “{column}” is marked as {_listed(several)}; mark it as one only."
        for column, several in roles.items()
        if len(several) > 1
    ]


def _listed(items: list[str]) -> str:
    return f"{', '.join(items[:-1])} and {items[-1]}"
