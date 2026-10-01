"""The API for naming an advertiser and uploading its leads file and stage-history file.

Handlers are plain functions, so FastAPI runs their blocking database, object-storage and CSV
work in its threadpool; only reading the request body runs on the event loop.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from emva_api import records
from emva_api.clock import Clock
from emva_api.csv_file import Table, UnreadableFile, count_values, profile, read_csv
from emva_api.object_store import ObjectStore
from emva_api.records import DataSource, FileKind

router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

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
    column_names: list[str]


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


async def _csv_body(request: Request) -> bytes:
    """The request body, refused as soon as it is known to be over the limit."""
    too_large = HTTPException(
        status.HTTP_413_CONTENT_TOO_LARGE,
        f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
    )
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise too_large
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise too_large
        chunks.append(chunk)
    return b"".join(chunks)


SessionDep = Annotated[Session, Depends(_session)]
StoreDep = Annotated[ObjectStore, Depends(_store)]
ClockDep = Annotated[Clock, Depends(_clock)]
NOT_FOUND = {status.HTTP_404_NOT_FOUND: {"model": Problem}}
UNREADABLE_STORED_FILE = {
    status.HTTP_409_CONFLICT: {"model": Problem, "description": "Stored file unreadable"}
}


@router.post(
    "/advertisers",
    operation_id="createAdvertiser",
    status_code=status.HTTP_201_CREATED,
)
def create_advertiser(new: NewAdvertiser, session: SessionDep, clock: ClockDep) -> Advertiser:
    advertiser = records.Advertiser(
        name=new.name, data_source=new.data_source, created_at=clock.now()
    )
    session.add(advertiser)
    session.commit()
    return _describe(advertiser)


@router.get("/advertisers/{advertiser_id}", operation_id="getAdvertiser", responses=NOT_FOUND)
def get_advertiser(advertiser_id: uuid.UUID, session: SessionDep) -> Advertiser:
    return _describe(_find_advertiser(session, advertiser_id))


@router.put(
    "/advertisers/{advertiser_id}/files/{kind}",
    operation_id="uploadFile",
    responses={
        **NOT_FOUND,
        status.HTTP_400_BAD_REQUEST: {"model": Problem, "description": "Not a readable CSV file"},
        status.HTTP_409_CONFLICT: {"model": Problem, "description": "Another upload won"},
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": Problem, "description": "Over 20 MB"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Problem, "description": "Not saved"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def upload_file(
    advertiser_id: uuid.UUID,
    kind: FileKind,
    file_name: Annotated[FileName, Query()],
    content: Annotated[bytes, Depends(_csv_body)],
    session: SessionDep,
    store: StoreDep,
    clock: ClockDep,
) -> FileProfile:
    """Upload the file, replacing any earlier upload of the same kind."""
    advertiser = _find_advertiser(session, advertiser_id)
    try:
        table = read_csv(content)
    except UnreadableFile as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error

    object_key = f"advertisers/{advertiser.id}/{kind.value}/{uuid.uuid4()}.csv"
    store.put(object_key, content)
    file = _find_file(advertiser, kind)
    earlier_key = file.object_key if file else None
    if file is None:
        file = records.UploadedFile(advertiser=advertiser, kind=kind)
        session.add(file)
    file.file_name = file_name
    file.object_key = object_key
    file.uploaded_at = clock.now()
    file.row_count = table.row_count
    file.column_names = table.columns
    try:
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        store.delete(object_key)
        if isinstance(error, IntegrityError):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Another upload of the {_label(kind)} finished first. "
                "Upload it again to replace it.",
            ) from error
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"The {_label(kind)} could not be saved. Try again.",
        ) from error
    if earlier_key is not None:
        store.delete(earlier_key)
    return _profile(file)


@router.get(
    "/advertisers/{advertiser_id}/files/{kind}/columns",
    operation_id="getColumns",
    responses={**NOT_FOUND, **UNREADABLE_STORED_FILE},
)
def get_columns(
    advertiser_id: uuid.UUID, kind: FileKind, session: SessionDep, store: StoreDep
) -> list[Column]:
    """Each column of the file with its first few values, read from the file itself."""
    table = _read_stored(_uploaded_file(session, advertiser_id, kind), store)
    return [Column(name=column.name, examples=column.examples) for column in profile(table)]


@router.get(
    "/advertisers/{advertiser_id}/files/stage-history/crm-stages",
    operation_id="getCrmStages",
    responses={
        **NOT_FOUND,
        **UNREADABLE_STORED_FILE,
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
    file = _uploaded_file(session, advertiser_id, FileKind.STAGE_HISTORY)
    table = _read_stored(file, store)
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


def _uploaded_file(
    session: Session, advertiser_id: uuid.UUID, kind: FileKind
) -> records.UploadedFile:
    file = _find_file(_find_advertiser(session, advertiser_id), kind)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"The {_label(kind)} is not uploaded.")
    return file


def _read_stored(file: records.UploadedFile, store: ObjectStore) -> Table:
    try:
        return read_csv(store.get(file.object_key))
    except UnreadableFile as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"The stored {_label(file.kind)} can no longer be read. Upload it again.",
        ) from error


def _describe(advertiser: records.Advertiser) -> Advertiser:
    leads_file = _find_file(advertiser, FileKind.LEADS)
    stage_history_file = _find_file(advertiser, FileKind.STAGE_HISTORY)
    return Advertiser(
        id=advertiser.id,
        name=advertiser.name,
        data_source=advertiser.data_source,
        leads_file=leads_file and _profile(leads_file),
        stage_history_file=stage_history_file and _profile(stage_history_file),
        review_available=leads_file is not None and stage_history_file is not None,
    )


def _profile(file: records.UploadedFile) -> FileProfile:
    return FileProfile(
        kind=file.kind,
        file_name=file.file_name,
        uploaded_at=file.uploaded_at.astimezone(UTC),
        row_count=file.row_count,
        column_names=file.column_names,
    )


def _label(kind: FileKind) -> str:
    return {FileKind.LEADS: "leads file", FileKind.STAGE_HISTORY: "stage-history file"}[kind]
