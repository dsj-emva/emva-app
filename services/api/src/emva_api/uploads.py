"""The API for naming an advertiser and uploading its leads file and stage-history file."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from emva_api import records
from emva_api.clock import Clock
from emva_api.csv_file import Table, UnreadableFile, count_values, profile, read_csv
from emva_api.object_store import ObjectStore
from emva_api.records import DataSource, FileKind

router = APIRouter()

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
FileName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class NewAdvertiser(BaseModel):
    name: Name
    data_source: DataSource


class Column(BaseModel):
    name: str
    examples: list[str] = Field(description="The column's first few distinct non-empty values")


class FileProfile(BaseModel):
    kind: FileKind
    file_name: str
    uploaded_at: datetime
    row_count: int
    columns: list[Column]


class Advertiser(BaseModel):
    id: uuid.UUID
    name: str
    data_source: DataSource
    leads_file: FileProfile | None
    stage_history_file: FileProfile | None
    review_available: bool = Field(description="True once both files are uploaded")


class CrmStage(BaseModel):
    name: str
    row_count: int


class Problem(BaseModel):
    detail: str


def _session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


def _store(request: Request) -> ObjectStore:
    return request.app.state.store


def _clock(request: Request) -> Clock:
    return request.app.state.clock


SessionDep = Annotated[Session, Depends(_session)]
StoreDep = Annotated[ObjectStore, Depends(_store)]
ClockDep = Annotated[Clock, Depends(_clock)]
NOT_FOUND = {status.HTTP_404_NOT_FOUND: {"model": Problem}}


@router.post(
    "/advertisers",
    operation_id="createAdvertiser",
    status_code=status.HTTP_201_CREATED,
)
def create_advertiser(
    new: NewAdvertiser, session: SessionDep, store: StoreDep, clock: ClockDep
) -> Advertiser:
    advertiser = records.Advertiser(
        name=new.name, data_source=new.data_source, created_at=clock.now()
    )
    session.add(advertiser)
    session.commit()
    return _describe(advertiser, store)


@router.get("/advertisers/{advertiser_id}", operation_id="getAdvertiser", responses=NOT_FOUND)
def get_advertiser(advertiser_id: uuid.UUID, session: SessionDep, store: StoreDep) -> Advertiser:
    return _describe(_find_advertiser(session, advertiser_id), store)


@router.put(
    "/advertisers/{advertiser_id}/files/{kind}",
    operation_id="uploadFile",
    responses={
        **NOT_FOUND,
        status.HTTP_400_BAD_REQUEST: {"model": Problem, "description": "Not a readable CSV file"},
        status.HTTP_409_CONFLICT: {"model": Problem, "description": "Already uploaded"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload_file(
    advertiser_id: uuid.UUID,
    kind: FileKind,
    file_name: Annotated[FileName, Query()],
    request: Request,
    session: SessionDep,
    store: StoreDep,
    clock: ClockDep,
) -> FileProfile:
    advertiser = _find_advertiser(session, advertiser_id)
    if any(file.kind == kind for file in advertiser.files):
        raise HTTPException(status.HTTP_409_CONFLICT, f"The {_label(kind)} is already uploaded.")
    content = await request.body()
    try:
        table = read_csv(content)
    except UnreadableFile as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error

    file_id = uuid.uuid4()
    object_key = f"advertisers/{advertiser.id}/{kind.value}/{file_id}.csv"
    store.put(object_key, content)
    file = records.UploadedFile(
        id=file_id,
        advertiser=advertiser,
        kind=kind,
        file_name=file_name,
        object_key=object_key,
        uploaded_at=clock.now(),
    )
    session.add(file)
    session.commit()
    return _profile(file, table)


@router.get(
    "/advertisers/{advertiser_id}/files/stage-history/crm-stages",
    operation_id="getCrmStages",
    responses={
        **NOT_FOUND,
        status.HTTP_400_BAD_REQUEST: {"model": Problem, "description": "No such column"},
    },
)
def get_crm_stages(
    advertiser_id: uuid.UUID,
    column: Annotated[str, Query(description="The stage-history column holding the CRM stage")],
    session: SessionDep,
    store: StoreDep,
) -> list[CrmStage]:
    """Every distinct CRM stage name in the column, with how many rows use it."""
    file = _find_file(_find_advertiser(session, advertiser_id), FileKind.STAGE_HISTORY)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The stage-history file is not uploaded.")
    table = read_csv(store.get(file.object_key))
    if column not in table.columns:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"The stage-history file has no column {column!r}."
        )
    return [CrmStage(name=name, row_count=count) for name, count in count_values(table, column)]


def _find_advertiser(session: Session, advertiser_id: uuid.UUID) -> records.Advertiser:
    advertiser = session.get(records.Advertiser, advertiser_id)
    if advertiser is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such advertiser.")
    return advertiser


def _find_file(advertiser: records.Advertiser, kind: FileKind) -> records.UploadedFile | None:
    return next((file for file in advertiser.files if file.kind == kind), None)


def _describe(advertiser: records.Advertiser, store: ObjectStore) -> Advertiser:
    def profile_of(kind: FileKind) -> FileProfile | None:
        file = _find_file(advertiser, kind)
        return None if file is None else _profile(file, read_csv(store.get(file.object_key)))

    leads_file = profile_of(FileKind.LEADS)
    stage_history_file = profile_of(FileKind.STAGE_HISTORY)
    return Advertiser(
        id=advertiser.id,
        name=advertiser.name,
        data_source=advertiser.data_source,
        leads_file=leads_file,
        stage_history_file=stage_history_file,
        review_available=leads_file is not None and stage_history_file is not None,
    )


def _profile(file: records.UploadedFile, table: Table) -> FileProfile:
    return FileProfile(
        kind=file.kind,
        file_name=file.file_name,
        uploaded_at=file.uploaded_at.astimezone(UTC),
        row_count=table.row_count,
        columns=[Column(name=column.name, examples=column.examples) for column in profile(table)],
    )


def _label(kind: FileKind) -> str:
    return {FileKind.LEADS: "leads file", FileKind.STAGE_HISTORY: "stage-history file"}[kind]
