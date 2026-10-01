"""The Mapping API: the draft Mapping is kept as the person works, then confirmed."""

import threading
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from emva_api.clock import FixedClock
from emva_api.object_store import ObjectStore
from emva_api.settings import Settings

LEADS = b"Lead ID,Created,Email,Budget\nL1,2026-01-02,ada@example.com,8000\nL2,2026-01-03,,\n"
STAGE_HISTORY = (
    b"Lead ID,Stage,Changed At,Deal Value\n"
    b"L1,New enquiry,2026-01-02,\nL1,Closed won,2026-01-09,9000\nL2,New enquiry,2026-01-03,\n"
)

COMPLETE = {
    "leads": {
        "lead_id": "Lead ID",
        "submitted_at": "Created",
        "name": None,
        "email": "Email",
        "phone": None,
        "inputs": {"Budget": "number"},
    },
    "stage_history": {
        "lead_id": "Lead ID",
        "crm_stage": "Stage",
        "changed_at": "Changed At",
        "deal_value": "Deal Value",
    },
    "crm_stages": {"New enquiry": "submitted", "Closed won": "won"},
    "typical_deal_size": 8000.0,
}

STAGES_AND_LOST = [
    {"value": "submitted", "name": "Submitted"},
    {"value": "contact_attempted", "name": "Contact attempted"},
    {"value": "engaged", "name": "Engaged"},
    {"value": "qualified", "name": "Qualified"},
    {"value": "proposal", "name": "Proposal"},
    {"value": "won", "name": "Won"},
    {"value": "lost", "name": "Lost"},
]


def advertiser_with_both_files(client: TestClient, stage_history: bytes = STAGE_HISTORY) -> str:
    advertiser = client.post(
        "/advertisers", json={"name": "Savanna Journeys", "data_source": "hand_made_test"}
    ).json()["id"]
    for kind, content in [("leads", LEADS), ("stage-history", stage_history)]:
        response = upload(client, advertiser, kind, content)
        assert response.status_code == 200, response.text
    return advertiser


def upload(client: TestClient, advertiser: str, kind: str, content: bytes):
    return client.put(
        f"/advertisers/{advertiser}/files/{kind}",
        params={"file_name": f"{kind}.csv"},
        content=content,
        headers={"Content-Type": "text/csv"},
    )


def save(client: TestClient, advertiser: str, mapping: dict):
    return client.put(f"/advertisers/{advertiser}/mapping", json=mapping)


def test_a_new_mapping_is_an_empty_draft_with_everything_still_to_do(client: TestClient):
    advertiser = advertiser_with_both_files(client)

    response = client.get(f"/advertisers/{advertiser}/mapping")

    assert response.status_code == 200, response.text
    review = response.json()
    assert review["mapping"] == {
        "leads": {
            "lead_id": None,
            "submitted_at": None,
            "name": None,
            "email": None,
            "phone": None,
            "inputs": {},
        },
        "stage_history": {
            "lead_id": None,
            "crm_stage": None,
            "changed_at": None,
            "deal_value": None,
        },
        "crm_stages": {},
        "typical_deal_size": None,
    }
    assert review["confirmed_at"] is None
    assert review["crm_stages"] == []
    assert review["stages_and_lost"] == STAGES_AND_LOST


def test_the_draft_comes_with_what_each_column_can_hold(client: TestClient):
    advertiser = advertiser_with_both_files(client)

    review = client.get(f"/advertisers/{advertiser}/mapping").json()

    assert review["leads_roles"] == [
        {"role": "lead_id", "label": "Lead identifier"},
        {"role": "submitted_at", "label": "Submission time"},
        {"role": "name", "label": "Name (removed)"},
        {"role": "email", "label": "Email (scrambled)"},
        {"role": "phone", "label": "Phone (scrambled)"},
    ]
    assert review["stage_history_roles"] == [
        {"role": "lead_id", "label": "Lead identifier"},
        {"role": "crm_stage", "label": "CRM stage"},
        {"role": "changed_at", "label": "When the change happened"},
        {"role": "deal_value", "label": "Deal value"},
    ]
    assert review["input_kinds"] == [
        {"kind": "number", "label": "Number"},
        {"kind": "category", "label": "Category"},
    ]
    assert "Enter the typical deal size." in review["problems"]


def test_the_mapping_needs_both_files(client: TestClient):
    advertiser = client.post(
        "/advertisers", json={"name": "Savanna Journeys", "data_source": "hand_made_test"}
    ).json()["id"]
    upload(client, advertiser, "leads", LEADS)

    response = client.get(f"/advertisers/{advertiser}/mapping")

    assert response.status_code == 404
    assert response.json() == {"detail": "The stage-history file is not uploaded."}


def test_an_unknown_advertiser_has_no_mapping(client: TestClient):
    response = client.get("/advertisers/00000000-0000-0000-0000-000000000000/mapping")

    assert response.status_code == 404


def test_the_draft_is_kept_between_visits(client: TestClient):
    advertiser = advertiser_with_both_files(client)
    draft = {**COMPLETE, "typical_deal_size": None}

    saved = save(client, advertiser, draft)

    assert saved.status_code == 200, saved.text
    assert saved.json()["mapping"] == draft
    assert client.get(f"/advertisers/{advertiser}/mapping").json()["mapping"] == draft


def test_marking_the_crm_stage_column_lists_every_name_it_uses_with_its_row_count(
    client: TestClient,
):
    advertiser = advertiser_with_both_files(client)
    marked = {"stage_history": {"crm_stage": "Stage"}}

    review = save(client, advertiser, marked).json()

    assert review["crm_stages"] == [
        {"name": "New enquiry", "row_count": 2},
        {"name": "Closed won", "row_count": 1},
    ]
    assert (
        "Place the CRM stage “Closed won” on the canonical ladder or on Lost."
        in (review["problems"])
    )


def test_the_reasons_it_cannot_be_confirmed_come_with_the_draft(client: TestClient):
    advertiser = advertiser_with_both_files(client)
    draft = {
        **COMPLETE,
        "leads": {**COMPLETE["leads"], "inputs": {"Email": "category"}},
        "crm_stages": {"New enquiry": "submitted"},
        "typical_deal_size": -5,
    }

    review = save(client, advertiser, draft).json()

    assert review["problems"] == [
        "The leads file's column “Email” is marked as the lead's email "
        "and an input to the score; mark it as one only.",
        "Place the CRM stage “Closed won” on the canonical ladder or on Lost.",
        "Place at least one CRM stage on Won.",
        "The typical deal size must be more than zero.",
    ]


def test_a_complete_draft_has_no_problems(client: TestClient):
    advertiser = advertiser_with_both_files(client)

    assert save(client, advertiser, COMPLETE).json()["problems"] == []


def test_a_crm_stage_is_placed_only_on_the_ladder_or_on_lost(client: TestClient):
    advertiser = advertiser_with_both_files(client)

    response = save(client, advertiser, {"crm_stages": {"New enquiry": "nurture"}})

    assert response.status_code == 422


def test_confirming_records_the_time_from_the_clock(client: TestClient, clock: FixedClock):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    clock.set(datetime(2026, 9, 20, 16, 30, tzinfo=UTC))

    response = client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert response.status_code == 200, response.text
    assert response.json()["confirmed_at"] == "2026-09-20T16:30:00Z"
    review = client.get(f"/advertisers/{advertiser}/mapping").json()
    assert review["confirmed_at"] == "2026-09-20T16:30:00Z"
    assert review["mapping"] == COMPLETE


def test_confirming_keeps_only_the_crm_stages_the_file_uses(client: TestClient):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, {**COMPLETE, "crm_stages": {**COMPLETE["crm_stages"], "Old": "lost"}})

    confirmed = client.post(f"/advertisers/{advertiser}/mapping/confirmation").json()

    assert confirmed["mapping"]["crm_stages"] == COMPLETE["crm_stages"]


def test_a_mapping_with_problems_is_not_confirmed(client: TestClient):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, {**COMPLETE, "typical_deal_size": 0})

    response = client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The mapping cannot be confirmed yet: "
        "The typical deal size must be more than zero."
    }
    assert client.get(f"/advertisers/{advertiser}/mapping").json()["confirmed_at"] is None


def test_a_confirmed_mapping_cannot_be_changed(client: TestClient):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    response = save(client, advertiser, {**COMPLETE, "typical_deal_size": 1})

    assert response.status_code == 409
    assert response.json() == {"detail": "The mapping is confirmed and can no longer be changed."}
    assert client.get(f"/advertisers/{advertiser}/mapping").json()["mapping"] == COMPLETE


def test_a_confirmed_mapping_is_not_confirmed_again(client: TestClient, clock: FixedClock):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    clock.set(datetime(2026, 9, 14, 10, 0, tzinfo=UTC))
    client.post(f"/advertisers/{advertiser}/mapping/confirmation")
    clock.set(datetime(2026, 9, 21, 9, 0, tzinfo=UTC))

    response = client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert response.status_code == 409
    assert client.get(f"/advertisers/{advertiser}/mapping").json()["confirmed_at"] == (
        "2026-09-14T10:00:00Z"
    )


def test_files_cannot_be_replaced_once_the_mapping_is_confirmed(client: TestClient):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    response = upload(client, advertiser, "leads", b"Lead ID\nL9\n")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The mapping is confirmed, so the files can no longer be replaced."
    }


def test_a_file_uploaded_again_with_other_columns_shows_in_the_problems(client: TestClient):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)

    upload(client, advertiser, "leads", b"Lead ID,Created,Email\nL1,2026-01-02,ada@example.com\n")

    assert client.get(f"/advertisers/{advertiser}/mapping").json()["problems"] == [
        "The leads file has no column “Budget”."
    ]


def test_a_stored_stage_history_file_that_can_no_longer_be_read_is_reported(
    client: TestClient, bucket
):
    advertiser = advertiser_with_both_files(client)
    stored = [
        item for item in bucket.objects.filter(Prefix=f"advertisers/{advertiser}/stage-history/")
    ]
    bucket.put_object(Key=stored[0].key, Body=b"")

    response = save(client, advertiser, COMPLETE)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The stored stage-history file can no longer be read. Upload it again."
    }


def test_a_confirmed_mapping_reads_without_the_raw_files(client: TestClient, bucket):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    confirmed = client.post(f"/advertisers/{advertiser}/mapping/confirmation").json()

    bucket.objects.filter(Prefix=f"advertisers/{advertiser}/").delete()
    response = client.get(f"/advertisers/{advertiser}/mapping")

    assert response.status_code == 200, response.text
    assert response.json() == confirmed
    assert response.json()["crm_stages"] == [
        {"name": "New enquiry", "row_count": 2},
        {"name": "Closed won", "row_count": 1},
    ]


def test_the_advertiser_says_when_its_mapping_was_confirmed(client: TestClient, clock: FixedClock):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    assert client.get(f"/advertisers/{advertiser}").json()["mapping_confirmed_at"] is None
    clock.set(datetime(2026, 9, 20, 16, 30, tzinfo=UTC))

    client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert client.get(f"/advertisers/{advertiser}").json()["mapping_confirmed_at"] == (
        "2026-09-20T16:30:00Z"
    )


def test_saving_again_with_the_same_crm_stage_column_does_not_read_the_file_again(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    reads: list[str] = []
    get = ObjectStore.get
    monkeypatch.setattr(ObjectStore, "get", lambda store, key: reads.append(key) or get(store, key))

    review = save(client, advertiser, {**COMPLETE, "typical_deal_size": 9000}).json()
    client.get(f"/advertisers/{advertiser}/mapping")

    assert reads == []
    assert [stage["name"] for stage in review["crm_stages"]] == ["New enquiry", "Closed won"]


def test_a_new_crm_stage_column_or_a_new_file_is_read_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    reads: list[str] = []
    get = ObjectStore.get
    monkeypatch.setattr(ObjectStore, "get", lambda store, key: reads.append(key) or get(store, key))

    other_column = {
        **COMPLETE,
        "stage_history": {**COMPLETE["stage_history"], "crm_stage": "Deal Value"},
    }
    assert save(client, advertiser, other_column).json()["crm_stages"] == [
        {"name": "9000", "row_count": 1}
    ]
    upload(client, advertiser, "stage-history", STAGE_HISTORY)
    client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert len(reads) == 2


def test_an_upload_waits_while_the_mapping_is_being_confirmed(
    client: TestClient, settings: Settings
):
    # Confirmation holds the advertiser's row; an upload arriving meanwhile waits for it, then
    # finds the mapping confirmed, so no file can change between confirmation's check and commit.
    advertiser = advertiser_with_both_files(client)
    save(client, advertiser, COMPLETE)
    responses = []
    engine = create_engine(settings.database_url)
    with engine.connect() as confirming:
        confirming.execute(
            text("SELECT id FROM advertiser WHERE id = :id FOR UPDATE"), {"id": advertiser}
        )
        uploading = threading.Thread(
            target=lambda: responses.append(upload(client, advertiser, "leads", b"Lead ID\nL9\n"))
        )
        uploading.start()
        time.sleep(0.5)
        assert uploading.is_alive()
        confirming.execute(
            text("UPDATE mapping SET confirmed_at = now() WHERE advertiser_id = :id"),
            {"id": advertiser},
        )
        confirming.commit()
    uploading.join(timeout=10)
    engine.dispose()

    assert responses[0].status_code == 409
