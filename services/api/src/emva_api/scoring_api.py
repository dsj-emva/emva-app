"""The Scoring API: the form for one new lead, and its Submit score with its Score explanation.

The form holds exactly the confirmed Mapping's inputs, with the categories seen in the latest
Training run. An entered lead is formatted by the Formatter's `format_lead`, as training's leads
were, and scored by `scoring.score` with that run's model and the advertiser's Typical deal size.
Nothing about it is stored. It carries no personal data: the form has no such column.

A refusal about the lead (an input missing, unreadable or unseen in training) is a bad request;
one about the advertiser's state (no Training run, one from which no chance can be known, or a
Mapping whose inputs are not the ones the latest Training run learned from) is a conflict,
whatever the lead.
"""

import uuid
from typing import NoReturn

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from emva_api import records
from emva_api.dependencies import (
    NOT_FOUND,
    ClockDep,
    Problem,
    SessionDep,
    StoreDep,
    find_advertiser,
)
from emva_api.features import Refused
from emva_api.formatter import Unreadable, format_lead
from emva_api.mapping import ColumnKind, Mapping
from emva_api.model import Model, NoChance
from emva_api.object_store import ObjectStore
from emva_api.records import DataSource
from emva_api.scoring import NOT_GIVEN, NotLearned, Score, check_inputs, score, value_text
from emva_api.training_runs import STORAGE_FAILED, latest_run

router = APIRouter()

NO_TRAINING_RUN = "No Training run yet. Train the model before scoring a lead."
# Stands in for the entered lead's identifier, which the Formatter requires; never kept.
ENTERED_LEAD = "entered on the scoring screen"

NOT_SCORABLE = {
    status.HTTP_409_CONFLICT: {
        "model": Problem,
        "description": "No Training run yet, none from which a chance can be known, or a "
        "Mapping whose inputs are not the ones it learned from",
    }
}
REFUSED = {
    status.HTTP_400_BAD_REQUEST: {
        "model": Problem,
        "description": "The lead cannot be scored: an input missing, unreadable or unseen in "
        "training",
    },
    **NOT_SCORABLE,
}


class Choice(BaseModel):
    value: str = Field(description="What to send; empty for a category not given")
    label: str


class ScoringInput(BaseModel):
    column: str = Field(description="The input's name, as the Mapping has it")
    kind: ColumnKind
    typical: str = Field(description="The typical lead's value: the training mean or most common")
    typical_choice: str | None = Field(
        description="The value of the typical lead's choice, for a category; null for a number"
    )
    choices: list[Choice] | None = Field(
        description="A category's values seen in training, most common first; null for a number"
    )


class ScoringForm(BaseModel):
    inputs: list[ScoringInput] = Field(description="The Mapping's inputs, in its order")


class EnteredLead(BaseModel):
    inputs: dict[str, str] = Field(
        description="Every input by its column, as a file would write it; a number may be empty"
    )


class ScoredLead(Score):
    data_source: DataSource = Field(description="Where the data the model learned from came from")


@router.get(
    "/advertisers/{advertiser_id}/scoring-form",
    operation_id="getScoringForm",
    responses={**NOT_FOUND, **STORAGE_FAILED, **NOT_SCORABLE},
)
def get_scoring_form(advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep) -> ScoringForm:
    """The inputs a person enters to score one new lead."""
    _, model, mapping = _latest(session, advertiser_id, store)
    numbers, categories = model.features.typical()
    values = {category.column: category.values for category in model.features.categories}
    inputs = []
    for column, kind in mapping.leads.inputs.items():
        if kind is ColumnKind.NUMBER:
            inputs.append(
                ScoringInput(
                    column=column,
                    kind=kind,
                    typical=value_text(numbers[column]),
                    typical_choice=None,
                    choices=None,
                )
            )
        else:
            inputs.append(
                ScoringInput(
                    column=column,
                    kind=kind,
                    typical=value_text(categories[column]),
                    typical_choice=categories[column] or "",
                    choices=[
                        Choice(value=value or "", label=value or NOT_GIVEN)
                        for value in values[column]
                    ],
                )
            )
    return ScoringForm(inputs=inputs)


@router.post(
    "/advertisers/{advertiser_id}/scores",
    operation_id="scoreLead",
    responses={**NOT_FOUND, **STORAGE_FAILED, **REFUSED},
)
def score_lead(
    advertiser_id: uuid.UUID,
    entered: EnteredLead,
    session: SessionDep,
    store: StoreDep,
    clock: ClockDep,
) -> ScoredLead:
    """The entered lead's Submit score and Score explanation, from the latest Training run."""
    advertiser, model, mapping = _latest(session, advertiser_id, store)
    columns = mapping.leads
    for column in entered.inputs:
        if column not in columns.inputs:
            _refuse(f"“{column}” is not an input to the score.")
    for column in columns.inputs:
        if column not in entered.inputs:
            _refuse(f"Enter every input; “{column}” is missing.")
    # Never so for a confirmed Mapping, which every Training run has.
    if columns.lead_id is None or columns.submitted_at is None or not mapping.typical_deal_size:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The Mapping marks no lead identifier, submission time or Typical deal size, so no "
            "lead can be scored.",
        )
    cells = {
        **entered.inputs,
        columns.lead_id: ENTERED_LEAD,
        columns.submitted_at: clock.now().isoformat(),
    }
    try:
        lead = format_lead(cells, mapping)
        scored = score(model, lead, columns.inputs, mapping.typical_deal_size)
    except NoChance as problem:
        raise HTTPException(status.HTTP_409_CONFLICT, str(problem)) from problem
    except (Unreadable, Refused) as problem:
        _refuse(str(problem))
    return ScoredLead(**dict(scored), data_source=advertiser.data_source)


def _latest(
    session: Session, advertiser_id: uuid.UUID, store: ObjectStore
) -> tuple[records.Advertiser, Model, Mapping]:
    advertiser = find_advertiser(session, advertiser_id)
    latest = latest_run(session, advertiser, store)
    # A Training run is made only from a confirmed Mapping, which never changes after.
    if latest is None or advertiser.mapping is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NO_TRAINING_RUN)
    _, model = latest
    mapping = Mapping.model_validate(advertiser.mapping.content)
    try:
        check_inputs(model, mapping.leads.inputs)
    except NotLearned as problem:
        raise HTTPException(status.HTTP_409_CONFLICT, str(problem)) from problem
    return advertiser, model, mapping


def _refuse(detail: str) -> NoReturn:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail)
