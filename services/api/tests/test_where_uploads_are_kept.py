"""Raw files go to object storage and records to Postgres; nothing is written to local disk."""

import builtins
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from emva_api import records
from emva_api.settings import Settings

LEADS = b"Lead ID,Budget (GBP)\nL1,8000\nL2,12000\n"


def upload_leads(client: TestClient, content: bytes):
    advertiser = client.post(
        "/advertisers", json={"name": "Savanna Journeys", "data_source": "hand_made_test"}
    ).json()["id"]
    response = client.put(
        f"/advertisers/{advertiser}/files/leads",
        params={"file_name": "leads.csv"},
        content=content,
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    return advertiser


def test_the_raw_file_is_in_object_storage_and_its_record_in_postgres(
    client: TestClient, settings: Settings, bucket
):
    advertiser = upload_leads(client, LEADS)

    with Session(create_engine(settings.database_url)) as session:
        file = session.scalars(
            select(records.UploadedFile).where(
                records.UploadedFile.advertiser_id == advertiser,
                records.UploadedFile.kind == records.FileKind.LEADS,
            )
        ).one()
    stored = bucket.Object(file.object_key).get()
    assert file.file_name == "leads.csv"
    assert stored["Body"].read() == LEADS


def test_uploading_a_large_file_writes_nothing_to_local_disk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    writes: list[str] = []
    real_open, real_os_open = builtins.open, os.open

    def watched_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            writes.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    def watched_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            writes.append(str(path))
        return real_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", watched_open)
    monkeypatch.setattr(os, "open", watched_os_open)
    big = b"Lead ID,Notes\n" + b"".join(b"L%d,%s\n" % (n, b"x" * 200) for n in range(20_000))

    upload_leads(client, big)

    assert writes == []
