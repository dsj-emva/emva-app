"""Confirming the Mapping runs the Formatter in the same operation: the hand-made dataset is
formatted, its summary returned, and the raw uploads deleted; a failure leaves nothing half-done
and the records always match what is in storage."""

import csv
import io
import json
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
from emva_api.object_store import MissingObject, ObjectStore
from emva_api.settings import Settings

HAND_MADE_SUMMARY = {
    "lead_count": 100,
    "won": 18,
    "lost": 58,
    "no_outcome_yet": 24,
    "neglected": 13,
    "phones_without_country": 0,
    "unreadable": [
        {
            "file": "leads",
            "reason": "The submission time cannot be read.",
            "count": 1,
            "first_rows": [101],
        },
        {
            "file": "stage-history",
            "reason": "The time of the change cannot be read.",
            "count": 1,
            "first_rows": [128],
        },
        {"file": "stage-history", "reason": "No CRM stage.", "count": 1, "first_rows": [218]},
        {
            "file": "stage-history",
            "reason": "The lead's row in the leads file could not be read.",
            "count": 3,
            "first_rows": [414, 415, 416],
        },
        {"file": "stage-history", "reason": "No lead identifier.", "count": 1, "first_rows": [417]},
        {
            "file": "stage-history",
            "reason": "The lead is not in the leads file.",
            "count": 1,
            "first_rows": [418],
        },
    ],
}


def map_hand_made(client: TestClient, mapping: dict = HAND_MADE_MAPPING) -> str:
    advertiser = upload_hand_made(client)
    saved = client.put(f"/advertisers/{advertiser}/mapping", json=mapping)
    assert saved.json()["problems"] == []
    return advertiser


def confirm(client: TestClient, advertiser: str):
    return client.post(f"/advertisers/{advertiser}/mapping/confirmation")


def raw_files(bucket, advertiser: str) -> list[str]:
    return sorted(
        o.key.split("/")[2] for o in bucket.objects.filter(Prefix=f"advertisers/{advertiser}/")
    )


def raw_kept(client: TestClient, advertiser: str) -> list[str]:
    described = client.get(f"/advertisers/{advertiser}").json()
    return sorted(
        file["kind"]
        for file in (described["leads_file"], described["stage_history_file"])
        if file["raw_kept"]
    )


def test_confirming_formats_the_data_and_returns_its_summary(client: TestClient, clock: FixedClock):
    advertiser = map_hand_made(client)
    assert client.get(f"/advertisers/{advertiser}/mapping").json()["formatting"] is None
    clock.set(datetime(2026, 9, 14, 11, 5, tzinfo=UTC))

    confirmed = confirm(client, advertiser)

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["formatting"] == HAND_MADE_SUMMARY
    assert confirmed.json()["formatted_at"] == "2026-09-14T11:05:00Z"
    assert confirmed.json()["still_to_do"] is None
    again = client.get(f"/advertisers/{advertiser}/mapping").json()
    assert again["formatting"] == confirmed.json()["formatting"]


def test_once_formatted_the_raw_uploads_are_gone_and_their_columns_are_refused_cleanly(
    client: TestClient, bucket
):
    advertiser = map_hand_made(client)

    confirm(client, advertiser)

    assert raw_files(bucket, advertiser) == []
    assert raw_kept(client, advertiser) == []
    for kind in ("leads", "stage-history"):
        columns = client.get(f"/advertisers/{advertiser}/files/{kind}/columns")
        assert columns.status_code == 410
        assert columns.json()["detail"].startswith("The raw ")
    described = client.get(f"/advertisers/{advertiser}").json()
    assert described["leads_file"]["row_count"] == 101


def test_when_formatting_cannot_be_saved_nothing_is_confirmed_and_the_raw_uploads_stay(
    client: TestClient, bucket, monkeypatch: pytest.MonkeyPatch
):
    advertiser = map_hand_made(client)
    real_commit = Session.commit

    def lost_connection(session: Session) -> None:
        raise OperationalError("COMMIT", {}, Exception("connection lost"))

    monkeypatch.setattr(Session, "commit", lost_connection)
    refused = confirm(client, advertiser)
    monkeypatch.setattr(Session, "commit", real_commit)

    assert refused.status_code == 503
    assert "not confirmed" in refused.json()["detail"]
    review = client.get(f"/advertisers/{advertiser}/mapping").json()
    assert (review["confirmed_at"], review["formatting"]) == (None, None)
    assert raw_files(bucket, advertiser) == ["leads", "stage-history"]
    assert confirm(client, advertiser).status_code == 200


def test_when_a_stored_file_cannot_be_read_nothing_is_confirmed(client: TestClient, bucket):
    advertiser = map_hand_made(client)
    leads_key = next(
        o.key for o in bucket.objects.filter(Prefix=f"advertisers/{advertiser}/leads/")
    )
    bucket.put_object(Key=leads_key, Body=b"\x00\x01")

    refused = confirm(client, advertiser)

    assert refused.status_code == 409
    review = client.get(f"/advertisers/{advertiser}/mapping").json()
    assert (review["confirmed_at"], review["formatting"]) == (None, None)


def test_when_a_stored_file_is_missing_it_is_said_cleanly(client: TestClient, bucket):
    advertiser = map_hand_made(client)
    for stored in bucket.objects.filter(Prefix=f"advertisers/{advertiser}/leads/"):
        stored.delete()

    columns = client.get(f"/advertisers/{advertiser}/files/leads/columns")
    refused = confirm(client, advertiser)

    assert columns.status_code == 409
    assert refused.status_code == 409
    assert (
        refused.json()["detail"] == "The stored leads file can no longer be read. Upload it again."
    )


def test_the_object_store_reads_a_missing_object_as_missing_and_deletes_it_as_done(settings):
    store = ObjectStore(settings)

    with pytest.raises(MissingObject):
        store.get("advertisers/nobody/leads/never-stored.csv")
    store.delete("advertisers/nobody/leads/never-stored.csv")


def test_when_one_raw_file_cannot_be_deleted_the_records_say_which_is_still_kept(
    client: TestClient, bucket, monkeypatch: pytest.MonkeyPatch
):
    advertiser = map_hand_made(client)
    real_delete = ObjectStore.delete
    deletes = 0

    def second_unreachable(store: ObjectStore, key: str) -> None:
        nonlocal deletes
        deletes += 1
        if deletes == 2:
            raise EndpointConnectionError(endpoint_url="http://object-storage")
        real_delete(store, key)

    monkeypatch.setattr(ObjectStore, "delete", second_unreachable)
    first = confirm(client, advertiser)
    monkeypatch.setattr(ObjectStore, "delete", real_delete)

    assert first.status_code == 503
    assert "Confirm again" in first.json()["detail"]
    assert raw_kept(client, advertiser) == raw_files(bucket, advertiser) == ["stage-history"]
    review = client.get(f"/advertisers/{advertiser}/mapping").json()
    assert review["formatting"]["lead_count"] == 100
    assert review["still_to_do"] == (
        "The data is formatted, but the raw files are not all deleted yet. Confirm again to "
        "delete them."
    )
    again = confirm(client, advertiser)
    assert again.status_code == 200, again.text
    assert again.json()["still_to_do"] is None
    assert raw_kept(client, advertiser) == raw_files(bucket, advertiser) == []
    assert confirm(client, advertiser).status_code == 409


# A mapping confirmed before formatting existed (#15), with no formatting: never a 500, and its
# raw files are never deleted unformatted.


def confirmed_without_formatting(client: TestClient, settings: Settings, mapping: dict) -> str:
    advertiser = upload_hand_made(client)
    review = client.put(f"/advertisers/{advertiser}/mapping", json=mapping).json()
    described = client.get(f"/advertisers/{advertiser}").json()
    shape = {
        "leads_columns": described["leads_file"]["column_names"],
        "stage_history_columns": described["stage_history_file"]["column_names"],
        "crm_stages": review["crm_stages"],
    }
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE mapping SET confirmed_at = '2026-09-01T10:00:00Z', "
                "confirmed_against = CAST(:shape AS json) WHERE advertiser_id = :id"
            ),
            {"shape": json.dumps(shape), "id": advertiser},
        )
    engine.dispose()
    return advertiser


def test_an_old_confirmed_mapping_reads_without_error_and_says_formatting_is_still_to_do(
    client: TestClient, settings: Settings, bucket
):
    advertiser = confirmed_without_formatting(client, settings, HAND_MADE_MAPPING)

    review = client.get(f"/advertisers/{advertiser}/mapping")

    assert review.status_code == 200
    assert review.json()["formatting"] is None
    assert review.json()["still_to_do"] == (
        "The mapping is confirmed but its data is not formatted yet. Confirm again to format it."
    )
    assert raw_files(bucket, advertiser) == ["leads", "stage-history"]


def test_confirming_an_old_confirmed_mapping_again_formats_it_while_its_raw_files_are_there(
    client: TestClient, settings: Settings, bucket
):
    advertiser = confirmed_without_formatting(client, settings, HAND_MADE_MAPPING)

    again = confirm(client, advertiser)

    assert again.status_code == 200, again.text
    assert again.json()["formatting"] == HAND_MADE_SUMMARY
    assert again.json()["confirmed_at"] == "2026-09-01T10:00:00Z"
    assert raw_files(bucket, advertiser) == []


def test_formatting_on_confirming_again_is_dated_by_the_clock_not_by_the_confirmation(
    client: TestClient, settings: Settings, clock: FixedClock
):
    advertiser = confirmed_without_formatting(client, settings, HAND_MADE_MAPPING)
    clock.set(datetime(2026, 9, 14, 11, 30, tzinfo=UTC))

    again = confirm(client, advertiser).json()

    assert again["confirmed_at"] == "2026-09-01T10:00:00Z"
    assert again["formatted_at"] == "2026-09-14T11:30:00Z"


def test_an_old_confirmed_mapping_whose_raw_file_is_gone_says_to_start_a_new_advertiser(
    client: TestClient, settings: Settings, bucket
):
    advertiser = confirmed_without_formatting(client, settings, HAND_MADE_MAPPING)
    for stored in bucket.objects.filter(Prefix=f"advertisers/{advertiser}/leads/"):
        stored.delete()

    refused = confirm(client, advertiser)

    assert refused.status_code == 409
    assert (
        "cannot be formatted now: the raw leads file can no longer be read"
        in (refused.json()["detail"])
    )
    assert "start a new advertiser" in refused.json()["detail"]
    assert raw_files(bucket, advertiser) == ["stage-history"]
    assert client.get(f"/advertisers/{advertiser}/mapping").json()["formatting"] is None


def test_an_old_confirmed_mapping_without_a_date_order_cannot_be_formatted_and_keeps_its_files(
    client: TestClient, settings: Settings, bucket
):
    old = {key: value for key, value in HAND_MADE_MAPPING.items() if key != "date_order"}
    advertiser = confirmed_without_formatting(client, settings, old)

    still_to_do = client.get(f"/advertisers/{advertiser}/mapping").json()["still_to_do"]
    refused = confirm(client, advertiser)

    assert "Confirm again" not in still_to_do
    assert "start a new advertiser" in still_to_do
    assert still_to_do == refused.json()["detail"]

    assert refused.status_code == 409
    assert "Pick the order the files write dates in." in refused.json()["detail"]
    assert "start a new advertiser" in refused.json()["detail"]
    assert raw_files(bucket, advertiser) == ["leads", "stage-history"]


# Done when: no name, raw email or raw phone number from the hand-made dataset is found anywhere
# in Postgres or object storage after formatting, training and scoring a lead, and the raw uploads
# are gone.


def personal_data(leads_csv: str) -> set[str]:
    found: set[str] = set()
    for row in csv.DictReader(io.StringIO(leads_csv)):
        phone = row["Phone"]
        digits = re.sub(r"\D", "", phone)
        found |= {row["Full Name"], row["Email"], row["Email"].lower(), phone}
        found |= {digits, "+" + digits, "0" + digits[2:]}
        if "Notes" in row:
            found.add(row["Notes"])
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


def upload(client: TestClient, advertiser: str, kind: str, content: str) -> None:
    response = client.put(
        f"/advertisers/{advertiser}/files/{kind}",
        params={"file_name": f"{kind}.csv"},
        content=content.encode(),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text


def emails_as_identifiers_and_free_text_notes() -> tuple[str, str]:
    """The hand-made files as a CRM that uses each lead's email as its identifier, with a
    free-text notes column naming the lead and their phone."""
    leads = list(csv.DictReader(io.StringIO((HAND_MADE / "leads.csv").read_text())))
    email_of = {row["Lead ID"]: row["Email"] for row in leads}

    def written(rows: list[dict[str, str]], columns: list[str]) -> str:
        out = io.StringIO()
        writer = csv.DictWriter(out, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return out.getvalue()

    for row in leads:
        row["Notes"] = f"{row['Full Name']} asked us to ring {row['Phone']} after six"
        row["Lead ID"] = email_of[row["Lead ID"]]
    history = list(csv.DictReader(io.StringIO((HAND_MADE / "stage_history.csv").read_text())))
    for row in history:
        row["Lead ID"] = email_of.get(row["Lead ID"], row["Lead ID"])
    return (
        written(leads, [*leads[0].keys()]),
        written(history, [*history[0].keys()]),
    )


@pytest.mark.parametrize("crm", ["hand_made", "emails_as_identifiers_and_free_text_notes"])
def test_after_formatting_no_personal_data_is_stored_anywhere(
    own_settings: Settings, own_bucket, crm: str
):
    if crm == "hand_made":
        leads, history = (
            (HAND_MADE / "leads.csv").read_text(),
            (HAND_MADE / "stage_history.csv").read_text(),
        )
    else:
        leads, history = emails_as_identifiers_and_free_text_notes()
    personal = personal_data(leads)
    assert {"Ada Fenwick", "ada.fenwick@example.com", "+447700900101"} <= personal

    with TestClient(create_app(own_settings, FixedClock(datetime(2026, 9, 14, tzinfo=UTC)))) as c:
        advertiser = c.post(
            "/advertisers", json={"name": "Savanna Journeys", "data_source": "hand_made_test"}
        ).json()["id"]
        upload(c, advertiser, "leads", leads)
        upload(c, advertiser, "stage-history", history)
        assert "Ada Fenwick" in everything_in_object_storage(own_bucket), "the scan sees uploads"
        if crm != "hand_made":
            notes_as_input = {
                **HAND_MADE_MAPPING,
                "leads": {
                    **HAND_MADE_MAPPING["leads"],
                    "inputs": {**HAND_MADE_MAPPING["leads"]["inputs"], "Notes": "category"},
                },
            }
            refused = c.put(f"/advertisers/{advertiser}/mapping", json=notes_as_input).json()
            assert any(
                p.startswith("“Notes” cannot be a category input") for p in refused["problems"]
            )
        saved = c.put(f"/advertisers/{advertiser}/mapping", json=HAND_MADE_MAPPING).json()
        assert saved["problems"] == []
        confirmed = c.post(f"/advertisers/{advertiser}/mapping/confirmation")
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["formatting"]["lead_count"] == 100
        assert list(own_bucket.objects.all()) == [], "the raw uploads are gone"
        trained = c.post(f"/advertisers/{advertiser}/training-runs")
        assert trained.status_code == 201, trained.text
        first = next(csv.DictReader(io.StringIO(leads)))
        inputs = {column: first[column] for column in HAND_MADE_MAPPING["leads"]["inputs"]}
        scored = c.post(f"/advertisers/{advertiser}/scores", json={"inputs": inputs})
        assert scored.status_code == 200, scored.text

    stored = everything_in_postgres(own_settings)
    assert '"identifier_hash"' in stored, "the scan sees the formatted leads"
    assert '"model_key"' in stored, "the scan sees the Training run"
    assert sorted(value for value in personal if value in stored) == []
    kept = sorted(o.key.rsplit("/", 1)[1] for o in own_bucket.objects.all())
    run = trained.json()["latest"]["id"]
    assert kept == [f"{run}-backtest.json", f"{run}.json"], "only the model and its Backtest"
    in_storage = everything_in_object_storage(own_bucket)
    assert '"transitions"' in in_storage and '"calibration"' in in_storage, "the scan reads both"
    assert sorted(v for v in personal if v in in_storage) == []
