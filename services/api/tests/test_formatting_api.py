"""Confirming the Mapping runs the Formatter in the same operation: the hand-made dataset is
formatted, its summary returned, and the raw uploads deleted; a failure leaves nothing half-done."""

import csv
import re
from datetime import UTC, datetime

import pytest
from botocore.exceptions import EndpointConnectionError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_hand_made_upload import HAND_MADE, HAND_MADE_MAPPING, upload_hand_made

from emva_api.clock import FixedClock
from emva_api.main import create_app
from emva_api.object_store import ObjectStore
from emva_api.settings import Settings

HAND_MADE_SUMMARY = {
    "lead_count": 100,
    "won": 18,
    "lost": 58,
    "unfinished": 24,
    "never_reached_contact_attempted": 13,
    "unreadable_rows": [
        {
            "file": "leads",
            "row": 101,
            "lead": "L-1101",
            "reason": "The submission time cannot be read.",
        },
        {
            "file": "stage-history",
            "row": 128,
            "lead": "L-1031",
            "reason": "The time of the change cannot be read.",
        },
        {"file": "stage-history", "row": 218, "lead": "L-1052", "reason": "No CRM stage."},
        *(
            {
                "file": "stage-history",
                "row": row,
                "lead": "L-1101",
                "reason": "The lead's row in the leads file could not be read.",
            }
            for row in (414, 415, 416)
        ),
        {"file": "stage-history", "row": 417, "lead": None, "reason": "No lead identifier."},
        {
            "file": "stage-history",
            "row": 418,
            "lead": "L-9042",
            "reason": "The lead is not in the leads file.",
        },
    ],
}


def map_hand_made(client: TestClient) -> str:
    advertiser = upload_hand_made(client)
    saved = client.put(f"/advertisers/{advertiser}/mapping", json=HAND_MADE_MAPPING)
    assert saved.json()["problems"] == []
    return advertiser


def test_confirming_formats_the_data_and_returns_its_summary(client: TestClient, clock: FixedClock):
    advertiser = map_hand_made(client)
    assert client.get(f"/advertisers/{advertiser}/mapping").json()["formatting"] is None
    clock.set(datetime(2026, 9, 14, 11, 5, tzinfo=UTC))

    confirmed = client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["formatting"] == {
        "formatted_at": "2026-09-14T11:05:00Z",
        **HAND_MADE_SUMMARY,
    }
    again = client.get(f"/advertisers/{advertiser}/mapping").json()
    assert again["formatting"] == confirmed.json()["formatting"]


def test_once_formatted_the_raw_uploads_are_gone_and_their_columns_are_refused_cleanly(
    client: TestClient, bucket
):
    advertiser = map_hand_made(client)

    client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert list(bucket.objects.filter(Prefix=f"advertisers/{advertiser}/")) == []
    for kind in ("leads", "stage-history"):
        columns = client.get(f"/advertisers/{advertiser}/files/{kind}/columns")
        assert columns.status_code == 410
        assert columns.json()["detail"].startswith("The raw ")
    described = client.get(f"/advertisers/{advertiser}").json()
    assert described["leads_file"]["row_count"] == 101
    assert client.get(f"/advertisers/{advertiser}/mapping").status_code == 200


def test_when_formatting_cannot_be_saved_nothing_is_confirmed_and_the_raw_uploads_stay(
    client: TestClient, bucket, monkeypatch: pytest.MonkeyPatch
):
    advertiser = map_hand_made(client)
    real_commit = Session.commit

    def lost_connection(session: Session) -> None:
        raise OperationalError("COMMIT", {}, Exception("connection lost"))

    monkeypatch.setattr(Session, "commit", lost_connection)
    refused = client.post(f"/advertisers/{advertiser}/mapping/confirmation")
    monkeypatch.setattr(Session, "commit", real_commit)

    assert refused.status_code == 503
    assert "not confirmed" in refused.json()["detail"]
    review = client.get(f"/advertisers/{advertiser}/mapping").json()
    assert (review["confirmed_at"], review["formatting"]) == (None, None)
    assert len(list(bucket.objects.filter(Prefix=f"advertisers/{advertiser}/"))) == 2
    assert client.post(f"/advertisers/{advertiser}/mapping/confirmation").status_code == 200


def test_when_a_stored_file_cannot_be_read_nothing_is_confirmed(client: TestClient, bucket):
    advertiser = map_hand_made(client)
    leads_key = next(
        o.key for o in bucket.objects.filter(Prefix=f"advertisers/{advertiser}/leads/")
    )
    bucket.put_object(Key=leads_key, Body=b"\x00\x01")

    refused = client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert refused.status_code == 409
    review = client.get(f"/advertisers/{advertiser}/mapping").json()
    assert (review["confirmed_at"], review["formatting"]) == (None, None)


def test_when_the_raw_uploads_cannot_be_deleted_confirming_again_finishes_the_deletion(
    client: TestClient, bucket, monkeypatch: pytest.MonkeyPatch
):
    advertiser = map_hand_made(client)
    real_delete = ObjectStore.delete

    def unreachable(store: ObjectStore, key: str) -> None:
        raise EndpointConnectionError(endpoint_url="http://object-storage")

    monkeypatch.setattr(ObjectStore, "delete", unreachable)
    first = client.post(f"/advertisers/{advertiser}/mapping/confirmation")
    monkeypatch.setattr(ObjectStore, "delete", real_delete)

    assert first.status_code == 503
    assert "Confirm again" in first.json()["detail"]
    assert client.get(f"/advertisers/{advertiser}/mapping").json()["formatting"] is not None
    again = client.post(f"/advertisers/{advertiser}/mapping/confirmation")
    assert again.status_code == 200, again.text
    assert again.json()["formatting"]["lead_count"] == 100
    assert list(bucket.objects.filter(Prefix=f"advertisers/{advertiser}/")) == []
    finished = client.post(f"/advertisers/{advertiser}/mapping/confirmation")
    assert finished.status_code == 409


# Done when: no name, raw email or raw phone number from the hand-made dataset is found anywhere
# in Postgres or object storage after formatting, and the raw uploads are gone.


def personal_data_of_the_hand_made_dataset() -> set[str]:
    with (HAND_MADE / "leads.csv").open(newline="") as leads:
        rows = list(csv.DictReader(leads))
    found: set[str] = set()
    for row in rows:
        phone = row["Phone"]
        digits = re.sub(r"\D", "", phone)
        found |= {row["Full Name"], row["Email"], row["Email"].lower(), phone}
        found |= {digits, "+" + digits, "0" + digits[2:]}
    return {value for value in found if value}


def everything_in_postgres(settings: Settings) -> str:
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        tables = inspect(connection).get_table_names()
        assert {"lead", "stage_event", "formatting", "mapping", "uploaded_file"} <= set(tables)
        dumped = [
            connection.execute(
                text(f"SELECT coalesce(json_agg(t)::text, '') FROM \"{table}\" t")
            ).scalar_one()
            for table in tables
        ]
    engine.dispose()
    return "\n".join(dumped)


def everything_in_object_storage(bucket) -> str:
    return "\n".join(o.get()["Body"].read().decode(errors="replace") for o in bucket.objects.all())


def test_after_formatting_no_personal_data_is_stored_anywhere(own_settings: Settings, own_bucket):
    personal = personal_data_of_the_hand_made_dataset()
    assert {"Ada Fenwick", "ada.fenwick@example.com", "+447700900101"} <= personal
    with TestClient(create_app(own_settings, FixedClock(datetime(2026, 9, 14, tzinfo=UTC)))) as c:
        advertiser = map_hand_made(c)
        assert "Ada Fenwick" in everything_in_object_storage(own_bucket), "the scan sees uploads"
        confirmed = c.post(f"/advertisers/{advertiser}/mapping/confirmation")
    assert confirmed.status_code == 200, confirmed.text

    stored = everything_in_postgres(own_settings)
    assert "L-1001" in stored, "the scan sees the formatted leads"
    assert sorted(value for value in personal if value in stored) == []
    assert list(own_bucket.objects.all()) == [], "the raw uploads are gone"
    assert sorted(v for v in personal if v in everything_in_object_storage(own_bucket)) == []
