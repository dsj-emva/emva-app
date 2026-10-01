"""The Training API: whether the advertiser's data can be trained on, training the stage-by-stage
model and its Backtest inside the request (ruling 4 of the phase 1 PRD), and the latest Training
run.

Nothing trains before a person has confirmed the Mapping, which formats its data. Training is
serialised per advertiser by holding its row. A Training run is recorded in Postgres at the
injected clock's time; its model and its Backtest are kept in object storage as JSON, never
pickled, so they are readable and safe to load. Every number of a run carries the label of the
advertiser's Data source.
"""

import uuid
from contextlib import suppress
from datetime import UTC, datetime

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from emva_api import records
from emva_api.backtest import Backtest, backtest
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
from emva_api.training_runs import STORAGE_FAILED, latest_run
from emva_api.transitions import LEFT_OUT, Transition

router = APIRouter()

RESULTS_UNREADABLE = "The results of this run's Backtest could not be read from storage. Try again."


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
    data_source: str = Field(
        description="The label every number of the run carries, e.g. 'on hand-made test data'"
    )
    backtest: Backtest | None = Field(
        description="The run's Backtest; null when its results are unavailable"
    )
    results_unavailable_because: str | None = Field(
        description="Why the Backtest's results are unavailable; null when they are shown"
    )


class Training(BaseModel):
    trainable: bool
    not_trainable_because: str | None = Field(description="Why not, while it cannot train")
    rule: str = Field(description="When a Transition's model is learned")
    left_out: str = Field(description="Which leads each Transition leaves out")
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
            "description": "The mapping is not confirmed, or it marks no input",
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
    leads = records.formatted_leads(session, advertiser)
    model = train(leads, now)
    results = backtest(leads, now)
    run_id = uuid.uuid4()
    keys = f"advertisers/{advertiser.id}/training-runs/{run_id}"
    model_key, backtest_key = f"{keys}.json", f"{keys}-backtest.json"
    run = records.TrainingRun(
        id=run_id,
        advertiser_id=advertiser.id,
        trained_at=now,
        model_key=model_key,
        backtest_key=backtest_key,
    )
    try:
        store.put(model_key, model.model_dump_json(indent=2).encode())
        store.put(backtest_key, results.model_dump_json(indent=2).encode())
        session.add(run)
        session.commit()
    except (BotoCoreError, ClientError, SQLAlchemyError) as error:
        session.rollback()
        # Nothing refers to them now; delete each when storage can be reached, so failing to
        # delete one never leaves the other behind.
        for key in (model_key, backtest_key):
            with suppress(BotoCoreError, ClientError):
                store.delete(key)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The model was trained but could not be kept, so nothing was stored. Try again.",
        ) from error
    return _training(advertiser, _view(advertiser, run, model, results))


def _not_trainable_because(advertiser: records.Advertiser) -> str | None:
    mapping = advertiser.mapping
    if mapping is None or mapping.confirmed_at is None:
        return "The mapping is not confirmed yet. Nothing trains before a person confirms it."
    if not Mapping.model_validate(mapping.content).leads.inputs:
        return "The mapping marks no input to the score, so there is nothing to learn from."
    return None


def _training(advertiser: records.Advertiser, latest: TrainingRunView | None) -> Training:
    because = _not_trainable_because(advertiser)
    return Training(
        trainable=because is None,
        not_trainable_because=because,
        rule=RULE,
        left_out=LEFT_OUT,
        latest=latest,
    )


def _latest(
    session: Session, advertiser: records.Advertiser, store: ObjectStore
) -> TrainingRunView | None:
    latest = latest_run(session, advertiser, store)
    if latest is None:
        return None
    run, model = latest
    try:
        results = Backtest.model_validate_json(store.get(run.backtest_key))
    except (BotoCoreError, ClientError, MissingObject):
        return _view(advertiser, run, model, None, RESULTS_UNREADABLE)
    return _view(advertiser, run, model, results)


def _view(
    advertiser: records.Advertiser,
    run: records.TrainingRun,
    model: Model,
    results: Backtest | None,
    results_unavailable_because: str | None = None,
) -> TrainingRunView:
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
        data_source=advertiser.data_source.label,
        backtest=results,
        results_unavailable_because=results_unavailable_because,
    )
