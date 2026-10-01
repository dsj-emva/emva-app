"""The API for the review screen: the advertiser's Mapping, kept as a draft while the person fills
it in, then confirmed by them as a separate act. A confirmed Mapping is never changed.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert

from emva_api import mapping, records
from emva_api.csv_file import count_values
from emva_api.dependencies import (
    NOT_FOUND,
    ClockDep,
    Problem,
    SessionDep,
    StoreDep,
    find_advertiser,
    read_stored,
    uploaded_file,
)
from emva_api.ladder import PLACES, Place, place_name
from emva_api.mapping import Files, Mapping, NotConfirmable
from emva_api.object_store import ObjectStore
from emva_api.records import FileKind

router = APIRouter()


class CrmStage(BaseModel):
    name: str
    row_count: int


class LadderPlace(BaseModel):
    place: Place
    name: str


class MappingReview(BaseModel):
    mapping: Mapping
    confirmed_at: datetime | None = Field(description="When a person confirmed it; null in draft")
    problems: list[str] = Field(description="Why it cannot be confirmed yet; empty once it can")
    crm_stages: list[CrmStage] = Field(
        description="Every CRM stage name in the column marked as the CRM stage, most used first"
    )
    places: list[LadderPlace] = Field(
        description="Where a CRM stage can be placed: the Canonical ladder in order, then Lost"
    )


@router.get(
    "/advertisers/{advertiser_id}/mapping",
    operation_id="getMapping",
    responses={
        **NOT_FOUND,
        status.HTTP_409_CONFLICT: {"model": Problem, "description": "Stored file unreadable"},
    },
)
def get_mapping(advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep) -> MappingReview:
    """The mapping as last saved (an empty draft at first), with what stops it being confirmed."""
    advertiser = find_advertiser(session, advertiser_id)
    record = advertiser.mapping
    draft = Mapping.model_validate(record.content) if record else Mapping()
    return _review(advertiser, draft, record and record.confirmed_at, store)


@router.put(
    "/advertisers/{advertiser_id}/mapping",
    operation_id="saveMapping",
    responses={
        **NOT_FOUND,
        status.HTTP_409_CONFLICT: {
            "model": Problem,
            "description": "Already confirmed, or a stored file is unreadable",
        },
    },
)
def save_mapping(
    advertiser_id: uuid.UUID, draft: Mapping, session: SessionDep, store: StoreDep
) -> MappingReview:
    """Keep the draft as it stands; refused once the mapping is confirmed."""
    advertiser = find_advertiser(session, advertiser_id)
    review = _review(advertiser, draft, None, store)
    content = draft.model_dump(mode="json")
    saved = session.execute(
        insert(records.AdvertiserMapping)
        .values(advertiser_id=advertiser.id, content=content)
        .on_conflict_do_update(
            index_elements=[records.AdvertiserMapping.advertiser_id],
            set_={"content": content},
            where=records.AdvertiserMapping.confirmed_at.is_(None),
        )
        .returning(records.AdvertiserMapping.advertiser_id)
    ).first()
    session.commit()
    if saved is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The mapping is confirmed and can no longer be changed."
        )
    return review


@router.post(
    "/advertisers/{advertiser_id}/mapping/confirmation",
    operation_id="confirmMapping",
    responses={
        **NOT_FOUND,
        status.HTTP_409_CONFLICT: {
            "model": Problem,
            "description": "Not confirmable yet, already confirmed, or a stored file unreadable",
        },
    },
)
def confirm_mapping(
    advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep, clock: ClockDep
) -> MappingReview:
    """Confirm the saved draft, recording when; refused while it has problems."""
    advertiser = find_advertiser(session, advertiser_id)
    record = session.get(records.AdvertiserMapping, advertiser.id, with_for_update=True)
    if record is not None and record.confirmed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The mapping is already confirmed.")
    draft = Mapping.model_validate(record.content) if record else Mapping()
    files, _ = _files(advertiser, draft, store)
    try:
        confirmed = mapping.confirm(draft, files, clock.now())
    except NotConfirmable as refused:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"The mapping cannot be confirmed yet: {' '.join(refused.problems)}",
        ) from refused
    if record is None:
        record = records.AdvertiserMapping(advertiser_id=advertiser.id)
        session.add(record)
    record.content = confirmed.mapping.model_dump(mode="json")
    record.confirmed_at = confirmed.confirmed_at
    session.commit()
    return _review(advertiser, confirmed.mapping, confirmed.confirmed_at, store)


def _review(
    advertiser: records.Advertiser,
    draft: Mapping,
    confirmed_at: datetime | None,
    store: ObjectStore,
) -> MappingReview:
    files, crm_stages = _files(advertiser, draft, store)
    return MappingReview(
        mapping=draft,
        confirmed_at=confirmed_at and confirmed_at.astimezone(UTC),
        problems=mapping.problems(draft, files),
        crm_stages=crm_stages,
        places=[LadderPlace(place=place, name=place_name(place)) for place in PLACES],
    )


def _files(
    advertiser: records.Advertiser, draft: Mapping, store: ObjectStore
) -> tuple[Files, list[CrmStage]]:
    """What the files hold; the stage-history file is read only for its CRM stage names."""
    leads = uploaded_file(advertiser, FileKind.LEADS)
    history = uploaded_file(advertiser, FileKind.STAGE_HISTORY)
    column = draft.stage_history.crm_stage
    crm_stages: list[CrmStage] = []
    if column is not None and column in history.column_names:
        counts = count_values(read_stored(history, store), column)
        crm_stages = [CrmStage(name=name, row_count=count) for name, count in counts]
    files = Files(
        leads_columns=leads.column_names,
        stage_history_columns=history.column_names,
        crm_stages=[stage.name for stage in crm_stages],
    )
    return files, crm_stages
