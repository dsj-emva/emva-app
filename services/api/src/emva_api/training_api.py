"""The Training API: train the stage-by-stage model on the advertiser's formatted data, inside the
request (ruling 4 of the phase 1 PRD), and read the latest Training run back.

Nothing trains before a person has confirmed the Mapping and its data is formatted. A Training
run is recorded in Postgres at the injected clock's time; its model is kept in object storage as
JSON, never pickled, so it is readable and safe to load.
"""

import uuid
from contextlib import suppress
from datetime import UTC, datetime

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from emva_api import records
from emva_api.dependencies import (
    NOT_FOUND,
    ClockDep,
    Problem,
    SessionDep,
    StoreDep,
    find_advertiser,
)
from emva_api.ladder import Stage
from emva_api.mapping import Mapping
from emva_api.model import Model, train

router = APIRouter()


class TransitionResult(BaseModel):
    from_stage: Stage
    to_stage: Stage
    name: str
    made: int = Field(description="Leads that made it")
    failed: int = Field(description="Leads lost at it")
    unfinished: int = Field(
        description="Leads that faced it but neither made nor failed it yet; left out"
    )
    learned: bool = Field(description="False when too few to learn: fewer than 10 made or failed")
    observed_rate: float | None = Field(
        description="made / (made + failed), the chance used when too few to learn; null when "
        "no lead has made or failed it yet"
    )


class TrainingRunView(BaseModel):
    id: uuid.UUID
    trained_at: datetime
    transitions: list[TransitionResult] = Field(
        description="Each Transition from Contact attempted to Won, in ladder order"
    )


@router.post(
    "/advertisers/{advertiser_id}/training-runs",
    operation_id="train",
    status_code=status.HTTP_201_CREATED,
    responses={
        **NOT_FOUND,
        status.HTTP_409_CONFLICT: {
            "model": Problem,
            "description": "The mapping is not confirmed, its data not formatted, or it marks "
            "no input",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": Problem,
            "description": "The Training run could not be kept",
        },
    },
)
def train_model(
    advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep, clock: ClockDep
) -> TrainingRunView:
    """Train on every formatted lead and stage event as of now, and keep the Training run."""
    advertiser = find_advertiser(session, advertiser_id)
    mapping = advertiser.mapping
    if mapping is None or mapping.confirmed_at is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The mapping is not confirmed yet. Nothing trains before a person confirms it.",
        )
    if advertiser.formatting is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The mapping is confirmed but its data is not formatted yet. Confirm again to "
            "format it.",
        )
    if not Mapping.model_validate(mapping.content).leads.inputs:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The mapping marks no input to the score, so there is nothing to learn from.",
        )
    now = clock.now()
    model = train(records.formatted_leads(session, advertiser), now)
    run_id = uuid.uuid4()
    run = records.TrainingRun(
        id=run_id,
        advertiser_id=advertiser.id,
        trained_at=now,
        model_key=f"advertisers/{advertiser.id}/training-runs/{run_id}.json",
    )
    try:
        store.put(run.model_key, model.model_dump_json(indent=2).encode())
        session.add(run)
        session.commit()
    except (BotoCoreError, ClientError, SQLAlchemyError) as error:
        session.rollback()
        # Nothing refers to the model now; delete it when storage can be reached.
        with suppress(BotoCoreError, ClientError):
            store.delete(run.model_key)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The model was trained but could not be kept, so nothing was stored. Try again.",
        ) from error
    return _view(run, model)


@router.get(
    "/advertisers/{advertiser_id}/training-runs/latest",
    operation_id="getLatestTrainingRun",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": Problem,
            "description": "No such advertiser, or not trained yet",
        }
    },
)
def latest_training_run(
    advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep
) -> TrainingRunView:
    advertiser = find_advertiser(session, advertiser_id)
    run = session.scalars(
        select(records.TrainingRun)
        .where(records.TrainingRun.advertiser_id == advertiser.id)
        .order_by(records.TrainingRun.trained_at.desc())
        .limit(1)
    ).first()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The model has not been trained yet.")
    return _view(run, Model.model_validate_json(store.get(run.model_key)))


def _view(run: records.TrainingRun, model: Model) -> TrainingRunView:
    return TrainingRunView(
        id=run.id,
        trained_at=run.trained_at.astimezone(UTC),
        transitions=[
            TransitionResult(
                from_stage=t.from_stage,
                to_stage=t.to_stage,
                name=t.transition.name,
                made=t.made,
                failed=t.failed,
                unfinished=t.unfinished,
                learned=t.learned is not None,
                observed_rate=t.observed_rate,
            )
            for t in model.transitions
        ],
    )
