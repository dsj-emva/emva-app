"""Raw files go to object storage and records to Postgres; nothing is written to local disk."""

import builtins
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from emva_api import records
from emva_api.object_store import ObjectStore
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


def test_postgres_keeps_the_files_shape_but_none_of_its_values(
    client: TestClient, settings: Settings
):
    advertiser = upload_leads(client, b"Lead ID,Email\nL-4242,ada@example.com\n")

    with create_engine(settings.database_url).connect() as connection:
        record = connection.execute(
            text("SELECT row_to_json(f)::text FROM uploaded_file f WHERE advertiser_id = :id"),
            {"id": advertiser},
        ).scalar_one()
    assert '"row_count":1' in record
    assert '"column_names":["Lead ID", "Email"]' in record
    assert "L-4242" not in record
    assert "ada@example.com" not in record


def test_the_advertiser_is_described_without_reading_its_files(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    advertiser = upload_leads(client, LEADS)

    def refuse(store, key: str) -> bytes:
        raise AssertionError(f"read {key}")

    monkeypatch.setattr(ObjectStore, "get", refuse)
    response = client.get(f"/advertisers/{advertiser}")

    assert response.status_code == 200
    assert response.json()["leads_file"]["row_count"] == 2


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
