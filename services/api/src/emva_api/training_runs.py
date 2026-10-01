"""Reading an advertiser's latest Training run and its model, as the Training and Scoring APIs
both need it. The run is recorded in Postgres; its model is kept in object storage as JSON."""

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from emva_api import records
from emva_api.dependencies import Problem
from emva_api.model import Model
from emva_api.object_store import MissingObject, ObjectStore

STORAGE_FAILED = {status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Problem}}


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
