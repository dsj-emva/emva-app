"""What the API's handlers share: the database session, object store and clock each is given,
and finding the advertiser and the uploaded files a request names."""

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from emva_api import records
from emva_api.clock import Clock
from emva_api.csv_file import Table, UnreadableFile, read_csv
from emva_api.object_store import ObjectStore
from emva_api.records import FileKind


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
UNREADABLE_STORED_FILE = {
    status.HTTP_409_CONFLICT: {"model": Problem, "description": "Stored file unreadable"}
}


def find_advertiser(
    session: Session, advertiser_id: uuid.UUID, *, lock: bool = False
) -> records.Advertiser:
    """The advertiser; with lock, its row is held until the transaction ends, so changes that
    must not interleave (uploading a file, confirming the mapping) take turns."""
    advertiser = session.get(records.Advertiser, advertiser_id, with_for_update=lock)
    if advertiser is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such advertiser.")
    return advertiser


def find_file(advertiser: records.Advertiser, kind: FileKind) -> records.UploadedFile | None:
    return next((file for file in advertiser.files if file.kind == kind), None)


def uploaded_file(advertiser: records.Advertiser, kind: FileKind) -> records.UploadedFile:
    file = find_file(advertiser, kind)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"The {label(kind)} is not uploaded.")
    return file


def read_stored(file: records.UploadedFile, store: ObjectStore) -> Table:
    try:
        return read_csv(store.get(file.object_key))
    except UnreadableFile as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"The stored {label(file.kind)} can no longer be read. Upload it again.",
        ) from error


def label(kind: FileKind) -> str:
    return {FileKind.LEADS: "leads file", FileKind.STAGE_HISTORY: "stage-history file"}[kind]
