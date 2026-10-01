"""The Mapping: what each column of an advertiser's two files means and where each CRM stage sits
on the Canonical ladder; and the rules that decide whether a person may confirm it.

A Mapping is a draft until a person confirms it. Pure: no I/O; the time of confirmation is given.
"""

import enum
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from emva_api.ladder import Place, Stage


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
    crm_stages: dict[str, Place] = Field(
        default_factory=dict, description="Where each CRM stage name sits: a Stage, or Lost"
    )
    typical_deal_size: float | None = Field(None, allow_inf_nan=False)


@dataclass(frozen=True)
class Files:
    """What the uploaded files hold, as far as the Mapping is concerned."""

    leads_columns: list[str]
    stage_history_columns: list[str]
    # Every CRM stage name in the column marked as the CRM stage.
    crm_stages: list[str]


@dataclass(frozen=True)
class ConfirmedMapping:
    mapping: Mapping
    confirmed_at: datetime


class NotConfirmable(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


_LEADS_ROLES = {
    "lead_id": "the lead identifier",
    "submitted_at": "the submission time",
    "name": "the lead's name",
    "email": "the lead's email",
    "phone": "the lead's phone",
}
_REQUIRED_LEADS_ROLES = ("lead_id", "submitted_at")
_PERSONAL_DATA_ROLES = ("name", "email", "phone")
_STAGE_HISTORY_ROLES = {
    "lead_id": "the lead identifier",
    "crm_stage": "the CRM stage",
    "changed_at": "when the change happened",
    "deal_value": "the deal value",
}


def problems(mapping: Mapping, files: Files) -> list[str]:
    """Every reason the mapping cannot be confirmed yet, in the order the screen shows them."""
    leads, history = mapping.leads, mapping.stage_history
    found: list[str] = []

    for role in _REQUIRED_LEADS_ROLES:
        if getattr(leads, role) is None:
            found.append(f"Mark the leads file's column holding {_LEADS_ROLES[role]}.")
    marked_leads = [getattr(leads, role) for role in _LEADS_ROLES] + list(leads.inputs)
    found += _not_in_file("leads file", marked_leads, files.leads_columns)

    for role, holds in _STAGE_HISTORY_ROLES.items():
        if getattr(history, role) is None:
            found.append(f"Mark the stage-history file's column holding {holds}.")
    marked_history = [getattr(history, role) for role in _STAGE_HISTORY_ROLES]
    found += _not_in_file("stage-history file", marked_history, files.stage_history_columns)

    for role in _PERSONAL_DATA_ROLES:
        column = getattr(leads, role)
        if column is not None and column in leads.inputs:
            found.append(
                f"“{column}” is marked as the lead's {role}, so it cannot be an input to the score."
            )

    if history.crm_stage in files.stage_history_columns:
        for name in files.crm_stages:
            if name not in mapping.crm_stages:
                found.append(f"Place the CRM stage “{name}” on the canonical ladder or on Lost.")
        if not any(mapping.crm_stages.get(name) is Stage.WON for name in files.crm_stages):
            found.append("Place at least one CRM stage on Won.")

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
    used = {name: place for name, place in mapping.crm_stages.items() if name in files.crm_stages}
    confirmed = mapping.model_copy(update={"crm_stages": used})
    return ConfirmedMapping(mapping=confirmed, confirmed_at=at)


def _not_in_file(file: str, marked: list[str | None], columns: list[str]) -> list[str]:
    return [
        f"The {file} has no column “{column}”."
        for column in marked
        if column is not None and column not in columns
    ]
