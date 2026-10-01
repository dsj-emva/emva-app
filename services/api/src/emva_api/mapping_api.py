"""The Mapping API, for the review screen: the advertiser's Mapping, kept as a draft while the
person fills it in, then confirmed by them as a separate act. Confirming runs the Formatter and
deletes the raw files. A confirmed Mapping is never changed, and is read back from what it was
confirmed against, never from the raw files.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from emva_api import mapping, records
from emva_api.csv_file import ColumnFacts, column_facts, count_values
from emva_api.dates import DATE_ORDERS, DateOrder
from emva_api.dependencies import (
    NOT_FOUND,
    UNREADABLE_STORED_FILE,
    ClockDep,
    Problem,
    SessionDep,
    StoreDep,
    find_advertiser,
    label,
    read_stored,
    uploaded_file,
)
from emva_api.formatter import Summary, format_files
from emva_api.ladder import STAGES_AND_LOST, StageOrLost, name_of
from emva_api.mapping import (
    INPUT_KINDS,
    LEADS_ROLES,
    STAGE_HISTORY_ROLES,
    ColumnKind,
    ConfirmedMapping,
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
    """What the two files hold, as far as the Mapping is concerned; never any of their values."""

    leads_columns: list[str]
    stage_history_columns: list[str]
    crm_stages: list[CrmStage] = Field(
        description="Every CRM stage name in the column marked as the CRM stage, most used first"
    )
    leads_row_count: int = 0
    leads_column_facts: dict[str, ColumnFacts] = Field(default_factory=dict)

    def files(self) -> Files:
        return Files(
            leads_columns=self.leads_columns,
            stage_history_columns=self.stage_history_columns,
            crm_stages=[stage.name for stage in self.crm_stages],
            leads_row_count=self.leads_row_count,
            leads_column_facts=self.leads_column_facts,
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


class DateOrderChoice(BaseModel):
    value: DateOrder
    label: str


class MappingReview(BaseModel):
    mapping: Mapping
    confirmed_at: datetime | None = Field(description="When a person confirmed it; null in draft")
    formatted_at: datetime | None = Field(description="When its data was formatted")
    formatting: Summary | None = Field(description="What formatting made of the files")
    still_to_do: str | None = Field(
        description="What confirming still has to do, when it was interrupted; confirming again "
        "does it. Null in draft and once confirming is done."
    )
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
    date_orders: list[DateOrderChoice] = Field(description="The orders dates can be written in")


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
        return _confirmed_review(advertiser, record)
    draft = Mapping.model_validate(record.content) if record else Mapping()
    shape, _ = _shape(advertiser, draft, store, record and record.crm_stages_read)
    return _review(draft, shape)


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
    return _review(draft, shape)


@router.post(
    "/advertisers/{advertiser_id}/mapping/confirmation",
    operation_id="confirmMapping",
    responses={
        **NOT_FOUND,
        status.HTTP_409_CONFLICT: {
            "model": Problem,
            "description": "Not confirmable yet, already confirmed, or a file cannot be read",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": Problem,
            "description": "Not confirmed, or confirmed but the raw files not all deleted yet",
        },
    },
)
def confirm_mapping(
    advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep, clock: ClockDep
) -> MappingReview:
    """Confirm the saved draft, recording when, and format both files with it in the same
    operation; refused while it has problems. The formatted data and the confirmation are saved
    together or not at all; then each raw file is deleted, and recorded as deleted, in turn.

    Confirming again finishes what was interrupted: it formats a mapping confirmed before its
    data was formatted, while the raw files are there, and deletes raw files still kept."""
    # Both rows are held until the commit, so no upload or save lands between the check and it.
    advertiser = find_advertiser(session, advertiser_id, lock=True)
    record = session.get(records.AdvertiserMapping, advertiser.id, with_for_update=True)
    if record is not None and record.confirmed_at is not None:
        if advertiser.formatting is None:
            # Confirmed before formatting existed, and never un-confirmed (ruling 9): format it
            # now if it can be, or say it never can be.
            confirmed = ConfirmedMapping(
                mapping=Mapping.model_validate(record.content), confirmed_at=record.confirmed_at
            )
            lacking = _lacking_for_formatting(record)
            if lacking:
                raise _never_formatted(lacking)
            _format(advertiser, confirmed, store, session, confirmed_before=True)
            _commit(session)
        elif not _raw_uploads(advertiser):
            raise HTTPException(status.HTTP_409_CONFLICT, "The mapping is already confirmed.")
        _delete_raw_uploads(advertiser, session, store)
        return _confirmed_review(advertiser, record)

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
    _format(advertiser, confirmed, store, session, confirmed_before=False)
    record.content = confirmed.mapping.model_dump(mode="json")
    record.confirmed_at = confirmed.confirmed_at
    record.confirmed_against = shape.model_dump(mode="json")
    _commit(session)
    _delete_raw_uploads(advertiser, session, store)
    return _confirmed_review(advertiser, record)


def _format(
    advertiser: records.Advertiser,
    confirmed: ConfirmedMapping,
    store: ObjectStore,
    session: Session,
    *,
    confirmed_before: bool,
) -> None:
    tables = []
    for kind in (FileKind.LEADS, FileKind.STAGE_HISTORY):
        file = uploaded_file(advertiser, kind)
        if not confirmed_before:
            tables.append(read_stored(file, store))
            continue
        try:
            tables.append(read_stored(file, store))
        except HTTPException as error:
            raise _never_formatted(f"the raw {label(kind)} can no longer be read") from error
    records.keep_formatted(
        session, advertiser, format_files(*tables, confirmed), confirmed.confirmed_at
    )


def _lacking_for_formatting(record: records.AdvertiserMapping) -> str | None:
    """Why a mapping confirmed before formatting existed can never be formatted, if it cannot:
    it lacks what formatting now needs (a date order, say), and it cannot be changed."""
    content = Mapping.model_validate(record.content)
    shape = FileShape.model_validate(record.confirmed_against)
    missing = mapping.problems(content, shape.files())
    return f"as confirmed it lacks what formatting needs: {' '.join(missing)}" if missing else None


def _never_formatted(why: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        f"The mapping was confirmed before its data could be formatted, and it cannot be "
        f"formatted now: {why}. A confirmed mapping cannot be changed, so start a new advertiser "
        "and upload both files again.",
    )


def _commit(session: Session) -> None:
    try:
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The mapping is not confirmed: the formatted data could not be saved. Try again.",
        ) from error


def _raw_uploads(advertiser: records.Advertiser) -> list[records.UploadedFile]:
    return [file for file in advertiser.files if file.object_key is not None]


def _delete_raw_uploads(
    advertiser: records.Advertiser, session: Session, store: ObjectStore
) -> None:
    """Delete each raw file and record it deleted before the next, so the records always say
    which raw files are still in storage."""
    for file in _raw_uploads(advertiser):
        try:
            store.delete(file.object_key)
            file.object_key = None
            session.commit()
        except (BotoCoreError, ClientError, SQLAlchemyError) as error:
            session.rollback()
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "The mapping is confirmed and the data formatted, but the raw files could not "
                "all be deleted yet. Confirm again to delete them.",
            ) from error


def _confirmed_review(
    advertiser: records.Advertiser, record: records.AdvertiserMapping
) -> MappingReview:
    formatting = advertiser.formatting
    lacking = _lacking_for_formatting(record)
    if formatting is None and lacking:
        still_to_do = _never_formatted(lacking).detail
    elif formatting is None:
        still_to_do = (
            "The mapping is confirmed but its data is not formatted yet. Confirm again to "
            "format it."
        )
    elif _raw_uploads(advertiser):
        still_to_do = (
            "The data is formatted, but the raw files are not all deleted yet. Confirm again "
            "to delete them."
        )
    else:
        still_to_do = None
    return _review(
        Mapping.model_validate(record.content),
        FileShape.model_validate(record.confirmed_against),
        confirmed_at=record.confirmed_at,
        formatting=formatting,
        still_to_do=still_to_do,
    )


def _confirmed() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, "The mapping is confirmed and can no longer be changed."
    )


def _review(
    draft: Mapping,
    shape: FileShape,
    *,
    confirmed_at: datetime | None = None,
    formatting: records.Formatting | None = None,
    still_to_do: str | None = None,
) -> MappingReview:
    return MappingReview(
        mapping=draft,
        confirmed_at=confirmed_at and confirmed_at.astimezone(UTC),
        formatted_at=formatting and formatting.formatted_at.astimezone(UTC),
        formatting=formatting and Summary.model_validate(formatting.summary),
        still_to_do=still_to_do,
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
        date_orders=[DateOrderChoice(value=o, label=text) for o, text in DATE_ORDERS.items()],
    )


def _shape(
    advertiser: records.Advertiser,
    draft: Mapping,
    store: ObjectStore,
    read_before: dict[str, Any] | None,
) -> tuple[FileShape, dict[str, Any] | None]:
    """What the files hold now, and the CRM stage names read for it. The stage-history file is
    read at most once, and not at all when its CRM stage names were read before from the same
    file and column. The leads file is read only for a file uploaded before its column facts were
    kept, and only while the draft has a category input to check."""
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
    facts: dict[str, Any] = leads.column_facts or {}
    has_category = ColumnKind.CATEGORY in draft.leads.inputs.values()
    if leads.column_facts is None and has_category:
        facts = column_facts(read_stored(leads, store))
    shape = FileShape(
        leads_columns=leads.column_names,
        stage_history_columns=history.column_names,
        crm_stages=crm_stages,
        leads_row_count=leads.row_count,
        leads_column_facts=facts,
    )
    return shape, crm_stages_read
