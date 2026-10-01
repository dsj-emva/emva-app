"""The Mapping API, for the review screen: the advertiser's Mapping, kept as a draft while the
person fills it in, then confirmed by them as a separate act. A confirmed Mapping is never changed,
and is read back from what it was confirmed against, never from the raw files.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert

from emva_api import mapping, records
from emva_api.csv_file import count_values
from emva_api.dependencies import (
    NOT_FOUND,
    UNREADABLE_STORED_FILE,
    ClockDep,
    Problem,
    SessionDep,
    StoreDep,
    find_advertiser,
    read_stored,
    uploaded_file,
)
from emva_api.ladder import STAGES_AND_LOST, StageOrLost, name_of
from emva_api.mapping import (
    INPUT_KINDS,
    LEADS_ROLES,
    STAGE_HISTORY_ROLES,
    ColumnKind,
    Files,
    LeadsRole,
    Mapping,
    NotConfirmable,
    StageHistoryRole,
)
from emva_api.object_store import ObjectStore
from emva_api.records import FileKind

router = APIRouter()


class CrmStage(BaseModel):
    name: str
    row_count: int


class FileShape(BaseModel):
    """What the two files hold, as far as the Mapping is concerned."""

    leads_columns: list[str]
    stage_history_columns: list[str]
    crm_stages: list[CrmStage] = Field(
        description="Every CRM stage name in the column marked as the CRM stage, most used first"
    )

    def files(self) -> Files:
        return Files(
            leads_columns=self.leads_columns,
            stage_history_columns=self.stage_history_columns,
            crm_stages=[stage.name for stage in self.crm_stages],
        )


class LeadsRoleChoice(BaseModel):
    role: LeadsRole
    label: str


class StageHistoryRoleChoice(BaseModel):
    role: StageHistoryRole
    label: str


class InputKindChoice(BaseModel):
    kind: ColumnKind
    label: str


class StageOrLostChoice(BaseModel):
    value: StageOrLost
    name: str


class MappingReview(BaseModel):
    mapping: Mapping
    confirmed_at: datetime | None = Field(description="When a person confirmed it; null in draft")
    problems: list[str] = Field(description="Why it cannot be confirmed yet; empty once it can")
    crm_stages: list[CrmStage] = Field(
        description="Every CRM stage name in the column marked as the CRM stage, most used first"
    )
    leads_roles: list[LeadsRoleChoice] = Field(description="What a leads-file column can hold")
    stage_history_roles: list[StageHistoryRoleChoice] = Field(
        description="What a stage-history column can hold"
    )
    input_kinds: list[InputKindChoice] = Field(description="How an input column can be read")
    stages_and_lost: list[StageOrLostChoice] = Field(
        description="What a CRM stage can be placed on: the Canonical ladder in order, then Lost"
    )


@router.get(
    "/advertisers/{advertiser_id}/mapping",
    operation_id="getMapping",
    responses={**NOT_FOUND, **UNREADABLE_STORED_FILE},
)
def get_mapping(advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep) -> MappingReview:
    """The mapping as last saved (an empty draft at first), with what stops it being confirmed."""
    advertiser = find_advertiser(session, advertiser_id)
    record = advertiser.mapping
    if record is not None and record.confirmed_at is not None:
        shape = FileShape.model_validate(record.confirmed_against)
        return _review(Mapping.model_validate(record.content), shape, record.confirmed_at)
    draft = Mapping.model_validate(record.content) if record else Mapping()
    shape, _ = _shape(advertiser, draft, store, record and record.crm_stages_read)
    return _review(draft, shape, None)


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
    record = advertiser.mapping
    if record is not None and record.confirmed_at is not None:
        raise _confirmed()
    shape, crm_stages_read = _shape(advertiser, draft, store, record and record.crm_stages_read)
    values = {"content": draft.model_dump(mode="json"), "crm_stages_read": crm_stages_read}
    # Confirmation holds the mapping row while it runs; a save that waited for it finds the
    # mapping confirmed and changes nothing.
    saved = session.execute(
        insert(records.AdvertiserMapping)
        .values(advertiser_id=advertiser.id, **values)
        .on_conflict_do_update(
            index_elements=[records.AdvertiserMapping.advertiser_id],
            set_=values,
            where=records.AdvertiserMapping.confirmed_at.is_(None),
        )
        .returning(records.AdvertiserMapping.advertiser_id)
    ).first()
    session.commit()
    if saved is None:
        raise _confirmed()
    return _review(draft, shape, None)


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
    # Both rows are held until the commit, so no upload or save lands between the check and it.
    advertiser = find_advertiser(session, advertiser_id, lock=True)
    record = session.get(records.AdvertiserMapping, advertiser.id, with_for_update=True)
    if record is not None and record.confirmed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The mapping is already confirmed.")
    draft = Mapping.model_validate(record.content) if record else Mapping()
    shape, _ = _shape(advertiser, draft, store, record and record.crm_stages_read)
    try:
        confirmed = mapping.confirm(draft, shape.files(), clock.now())
    except NotConfirmable as refused:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"The mapping cannot be confirmed yet: {' '.join(refused.problems)}",
        ) from refused
    assert record is not None, "an empty draft is never confirmable"
    record.content = confirmed.mapping.model_dump(mode="json")
    record.confirmed_at = confirmed.confirmed_at
    record.confirmed_against = shape.model_dump(mode="json")
    session.commit()
    return _review(confirmed.mapping, shape, confirmed.confirmed_at)


def _confirmed() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, "The mapping is confirmed and can no longer be changed."
    )


def _review(draft: Mapping, shape: FileShape, confirmed_at: datetime | None) -> MappingReview:
    return MappingReview(
        mapping=draft,
        confirmed_at=confirmed_at and confirmed_at.astimezone(UTC),
        problems=mapping.problems(draft, shape.files()),
        crm_stages=shape.crm_stages,
        leads_roles=[LeadsRoleChoice(role=r, label=LEADS_ROLES[r].label) for r in LeadsRole],
        stage_history_roles=[
            StageHistoryRoleChoice(role=r, label=STAGE_HISTORY_ROLES[r].label)
            for r in StageHistoryRole
        ],
        input_kinds=[
            InputKindChoice(kind=kind, label=label) for kind, label in INPUT_KINDS.items()
        ],
        stages_and_lost=[
            StageOrLostChoice(value=value, name=name_of(value)) for value in STAGES_AND_LOST
        ],
    )


def _shape(
    advertiser: records.Advertiser,
    draft: Mapping,
    store: ObjectStore,
    read_before: dict[str, Any] | None,
) -> tuple[FileShape, dict[str, Any] | None]:
    """What the files hold now, and the CRM stage names read for it. The stage-history file is
    read at most once, and not at all when its CRM stage names were read before from the same
    file and column."""
    leads = uploaded_file(advertiser, FileKind.LEADS)
    history = uploaded_file(advertiser, FileKind.STAGE_HISTORY)
    column = draft.stage_history.crm_stage
    crm_stages_read = None
    if column is not None and column in history.column_names:
        source = {"object_key": history.object_key, "column": column}
        if read_before is not None and {k: read_before[k] for k in source} == source:
            crm_stages_read = read_before
        else:
            counts = count_values(read_stored(history, store), column)
            crm_stages_read = {**source, "crm_stages": [list(count) for count in counts]}
    crm_stages = [
        CrmStage(name=name, row_count=count)
        for name, count in (crm_stages_read["crm_stages"] if crm_stages_read else [])
    ]
    shape = FileShape(
        leads_columns=leads.column_names,
        stage_history_columns=history.column_names,
        crm_stages=crm_stages,
    )
    return shape, crm_stages_read
