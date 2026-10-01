"""The Scoring API: the form for one new lead, and its Submit score with its Score explanation.

The form holds exactly the confirmed Mapping's inputs, with the categories seen in the latest
Training run. An entered lead is formatted by the Formatter's `format_lead`, as training's leads
were, and scored by `scoring.score` with that run's model and the advertiser's Typical deal size.
Nothing about it is stored. It carries no personal data: the form has no such column.
"""

import uuid
from datetime import datetime
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
from emva_api.model import Model
from emva_api.object_store import ObjectStore
from emva_api.records import DataSource
from emva_api.scoring import NOT_GIVEN, Explanation, score, value_text
from emva_api.training_api import STORAGE_FAILED, latest_run

router = APIRouter()

NO_TRAINING_RUN = "No Training run yet. Train the model before scoring a lead."
# Stands in for the entered lead's identifier, which the Formatter requires; never kept.
ENTERED_LEAD = "entered on the scoring screen"

REFUSED = {
    status.HTTP_400_BAD_REQUEST: {
        "model": Problem,
        "description": "The lead cannot be scored: an input missing, unreadable or unseen in "
        "training, or no chance known",
    },
    status.HTTP_409_CONFLICT: {"model": Problem, "description": "No Training run yet"},
}


class Choice(BaseModel):
    value: str = Field(description="What to send; empty for a category not given")
    label: str


class ScoringInput(BaseModel):
    column: str = Field(description="The input's name, as the Mapping has it")
    kind: ColumnKind
    typical: str = Field(description="The typical lead's value: the training mean or most common")
    choices: list[Choice] | None = Field(
        description="A category's values seen in training, most common first; null for a number"
    )


class ScoringForm(BaseModel):
    training_run_id: uuid.UUID
    trained_at: datetime
    data_source: DataSource
    typical_deal_size: float
    inputs: list[ScoringInput] = Field(description="The Mapping's inputs, in its order")


class EnteredLead(BaseModel):
    inputs: dict[str, str] = Field(
        description="Every input by its column, as a file would write it; a number may be empty"
    )


class ScoredLead(BaseModel):
    training_run_id: uuid.UUID
    data_source: DataSource
    chance_of_winning: float
    typical_deal_size: float = Field(description="The size the Lead score used")
    lead_score: float = Field(description="The chance of winning times the deal size; not money")
    explanation: Explanation


@router.get(
    "/advertisers/{advertiser_id}/scoring-form",
    operation_id="getScoringForm",
    responses={**NOT_FOUND, **STORAGE_FAILED, status.HTTP_409_CONFLICT: REFUSED[409]},
)
def get_scoring_form(advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep) -> ScoringForm:
    """The inputs a person enters to score one new lead."""
    advertiser, run, model, mapping = _latest(session, advertiser_id, store)
    numbers, categories = model.features.typical()
    values = {category.column: category.values for category in model.features.categories}
    inputs = []
    for column, kind in mapping.leads.inputs.items():
        if kind is ColumnKind.NUMBER:
            typical, choices = numbers[column], None
        else:
            typical = categories[column]
            choices = [
                Choice(value=value or "", label=value or NOT_GIVEN) for value in values[column]
            ]
        inputs.append(
            ScoringInput(column=column, kind=kind, typical=value_text(typical), choices=choices)
        )
    return ScoringForm(
        training_run_id=run.id,
        trained_at=run.trained_at,
        data_source=advertiser.data_source,
        typical_deal_size=_typical_deal_size(mapping),
        inputs=inputs,
    )


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
    advertiser, run, model, mapping = _latest(session, advertiser_id, store)
    inputs = mapping.leads
    for column in entered.inputs:
        if column not in inputs.inputs:
            _refuse(f"“{column}” is not an input to the score.")
    for column in inputs.inputs:
        if column not in entered.inputs:
            _refuse(f"Enter every input; “{column}” is missing.")
    assert inputs.lead_id is not None and inputs.submitted_at is not None, "confirmed Mapping"
    cells = {
        **entered.inputs,
        inputs.lead_id: ENTERED_LEAD,
        inputs.submitted_at: clock.now().isoformat(),
    }
    try:
        lead = format_lead(cells, mapping)
        scored = score(model, lead, list(inputs.inputs), _typical_deal_size(mapping))
    except (Unreadable, Refused) as problem:
        _refuse(str(problem))
    return ScoredLead(
        training_run_id=run.id,
        data_source=advertiser.data_source,
        chance_of_winning=scored.chance_of_winning,
        typical_deal_size=scored.typical_deal_size,
        lead_score=scored.lead_score,
        explanation=scored.explanation,
    )


def _latest(
    session: Session, advertiser_id: uuid.UUID, store: ObjectStore
) -> tuple[records.Advertiser, records.TrainingRun, Model, Mapping]:
    advertiser = find_advertiser(session, advertiser_id)
    latest = latest_run(session, advertiser, store)
    # A Training run is made only from a confirmed Mapping, which never changes after.
    if latest is None or advertiser.mapping is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NO_TRAINING_RUN)
    run, model = latest
    return advertiser, run, model, Mapping.model_validate(advertiser.mapping.content)


def _typical_deal_size(mapping: Mapping) -> float:
    assert mapping.typical_deal_size is not None, "a confirmed Mapping has a Typical deal size"
    return mapping.typical_deal_size


def _refuse(detail: str) -> NoReturn:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail)
