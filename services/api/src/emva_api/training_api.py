"""The Training API: whether the advertiser's data can be trained on, training the stage-by-stage
model inside the request (ruling 4 of the phase 1 PRD), and the latest Training run.

Nothing trains before a person has confirmed the Mapping and its data is formatted. Training is
serialised per advertiser by holding its row. A Training run is recorded in Postgres at the
injected clock's time; its model is kept in object storage as JSON, never pickled, so it is
readable and safe to load.
"""

import uuid
from contextlib import suppress
from datetime import UTC, datetime

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
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
from emva_api.mapping import Mapping
from emva_api.model import RULE, Model, train
from emva_api.object_store import MissingObject, ObjectStore
from emva_api.transitions import Transition

router = APIRouter()

STORAGE_FAILED = {status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Problem}}


class TransitionResult(BaseModel):
    transition: Transition
    made: int = Field(description="Leads that made it")
    failed: int = Field(description="Leads lost at it")
    unfinished: int = Field(
        description="Leads that faced it but neither made nor failed it yet; left out"
    )
    fitted: bool = Field(description="Whether its logistic regression was fitted")
    verdict: str = Field(description="What to say of it: learned, or too few to learn")
    smoothed_rate: float | None = Field(
        description="(made + 2p) / (made + failed + 2), p pooled across the run's Transitions: "
        "every lead's chance when too few to learn. Null only when no lead finished any."
    )


class TrainingRunView(BaseModel):
    id: uuid.UUID
    trained_at: datetime
    transitions: list[TransitionResult] = Field(
        description="Each Transition from Contact attempted to Won, in ladder order"
    )


class Training(BaseModel):
    trainable: bool
    not_trainable_because: str | None = Field(description="Why not, while it cannot train")
    rule: str = Field(description="When a Transition's model is learned")
    latest: TrainingRunView | None = Field(description="The latest Training run; null before one")


@router.get(
    "/advertisers/{advertiser_id}/training",
    operation_id="getTraining",
    responses={**NOT_FOUND, **STORAGE_FAILED},
)
def get_training(advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep) -> Training:
    """Whether training can run now, and the latest Training run."""
    advertiser = find_advertiser(session, advertiser_id)
    return _training(advertiser, _latest(session, advertiser, store))


@router.post(
    "/advertisers/{advertiser_id}/training-runs",
    operation_id="train",
    status_code=status.HTTP_201_CREATED,
    responses={
        **NOT_FOUND,
        **STORAGE_FAILED,
        status.HTTP_409_CONFLICT: {
            "model": Problem,
            "description": "The mapping is not confirmed, its data not formatted, or it marks "
            "no input",
        },
    },
)
def train_model(
    advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep, clock: ClockDep
) -> Training:
    """Train on every formatted lead and stage event as of now, and keep the Training run."""
    # Held until the commit, so training runs for one advertiser take turns.
    advertiser = find_advertiser(session, advertiser_id, lock=True)
    refusal = _not_trainable_because(advertiser)
    if refusal is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, refusal)
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
    return _training(advertiser, _view(run, model))


def _not_trainable_because(advertiser: records.Advertiser) -> str | None:
    mapping = advertiser.mapping
    if mapping is None or mapping.confirmed_at is None:
        return "The mapping is not confirmed yet. Nothing trains before a person confirms it."
    if advertiser.formatting is None:
        return (
            "The mapping is confirmed but its data is not formatted yet. Confirm again to "
            "format it."
        )
    if not Mapping.model_validate(mapping.content).leads.inputs:
        return "The mapping marks no input to the score, so there is nothing to learn from."
    return None


def _training(advertiser: records.Advertiser, latest: TrainingRunView | None) -> Training:
    because = _not_trainable_because(advertiser)
    return Training(
        trainable=because is None, not_trainable_because=because, rule=RULE, latest=latest
    )


def _latest(
    session: Session, advertiser: records.Advertiser, store: ObjectStore
) -> TrainingRunView | None:
    latest = latest_run(session, advertiser, store)
    return None if latest is None else _view(*latest)


def latest_run(
    session: Session, advertiser: records.Advertiser, store: ObjectStore
) -> tuple[records.TrainingRun, Model] | None:
    """The advertiser's latest Training run and its model; None before the first."""
    run = session.scalars(
        select(records.TrainingRun)
        .where(records.TrainingRun.advertiser_id == advertiser.id)
        .order_by(records.TrainingRun.number.desc())
        .limit(1)
    ).first()
    if run is None:
        return None
    try:
        stored = store.get(run.model_key)
    except (BotoCoreError, ClientError, MissingObject) as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The latest Training run's model could not be read from storage. Try again.",
        ) from error
    return run, Model.model_validate_json(stored)


def _view(run: records.TrainingRun, model: Model) -> TrainingRunView:
    return TrainingRunView(
        id=run.id,
        trained_at=run.trained_at.astimezone(UTC),
        transitions=[
            TransitionResult(
                transition=t.transition,
                made=t.made,
                failed=t.failed,
                unfinished=t.unfinished,
                fitted=t.regression is not None,
                verdict=t.verdict,
                smoothed_rate=t.smoothed_rate,
            )
            for t in model.transitions
        ],
    )
