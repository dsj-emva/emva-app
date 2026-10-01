"""The API for naming an advertiser and uploading its leads file and stage-history file.

Handlers are plain functions, so FastAPI runs their blocking database, object-storage and CSV
work in its threadpool; only reading the request body runs on the event loop.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from emva_api import records
from emva_api.csv_file import UnreadableFile, profile, read_csv
from emva_api.dependencies import (
    NOT_FOUND,
    UNREADABLE_STORED_FILE,
    ClockDep,
    Problem,
    SessionDep,
    StoreDep,
    find_advertiser,
    find_file,
    label,
    read_stored,
    uploaded_file,
)
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
    mapping_confirmed_at: datetime | None = Field(
        description="When the mapping was confirmed; from then on the files cannot be replaced"
    )


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
    return _describe(find_advertiser(session, advertiser_id))


@router.put(
    "/advertisers/{advertiser_id}/files/{kind}",
    operation_id="uploadFile",
    responses={
        **NOT_FOUND,
        status.HTTP_400_BAD_REQUEST: {"model": Problem, "description": "Not a readable CSV file"},
        status.HTTP_409_CONFLICT: {
            "model": Problem,
            "description": "Another upload won, or the mapping is confirmed",
        },
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
    # Locked, so the mapping cannot be confirmed between this check and the commit.
    advertiser = find_advertiser(session, advertiser_id, lock=True)
    if _confirmed_at(advertiser) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The mapping is confirmed, so the files can no longer be replaced.",
        )
    try:
        table = read_csv(content)
    except UnreadableFile as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error

    object_key = f"advertisers/{advertiser.id}/{kind.value}/{uuid.uuid4()}.csv"
    store.put(object_key, content)
    file = find_file(advertiser, kind)
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
                f"Another upload of the {label(kind)} finished first. "
                "Upload it again to replace it.",
            ) from error
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"The {label(kind)} could not be saved. Try again.",
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
    file = uploaded_file(find_advertiser(session, advertiser_id), kind)
    table = read_stored(file, store)
    return [Column(name=column.name, examples=column.examples) for column in profile(table)]


def _describe(advertiser: records.Advertiser) -> Advertiser:
    leads_file = find_file(advertiser, FileKind.LEADS)
    stage_history_file = find_file(advertiser, FileKind.STAGE_HISTORY)
    return Advertiser(
        id=advertiser.id,
        name=advertiser.name,
        data_source=advertiser.data_source,
        leads_file=leads_file and _profile(leads_file),
        stage_history_file=stage_history_file and _profile(stage_history_file),
        review_available=leads_file is not None and stage_history_file is not None,
        mapping_confirmed_at=_confirmed_at(advertiser),
    )


def _confirmed_at(advertiser: records.Advertiser) -> datetime | None:
    confirmed_at = advertiser.mapping and advertiser.mapping.confirmed_at
    return confirmed_at and confirmed_at.astimezone(UTC)


def _profile(file: records.UploadedFile) -> FileProfile:
    return FileProfile(
        kind=file.kind,
        file_name=file.file_name,
        uploaded_at=file.uploaded_at.astimezone(UTC),
        row_count=file.row_count,
        column_names=file.column_names,
    )
