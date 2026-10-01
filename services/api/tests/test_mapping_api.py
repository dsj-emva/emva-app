"""The review screen's API: the draft Mapping is kept as the person works, then confirmed."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from emva_api.clock import FixedClock

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

PLACES = [
    {"place": "submitted", "name": "Submitted"},
    {"place": "contact_attempted", "name": "Contact attempted"},
    {"place": "engaged", "name": "Engaged"},
    {"place": "qualified", "name": "Qualified"},
    {"place": "proposal", "name": "Proposal"},
    {"place": "won", "name": "Won"},
    {"place": "lost", "name": "Lost"},
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
    assert review["places"] == PLACES
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
        "“Email” is marked as the lead's email, so it cannot be an input to the score.",
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
    save(client, advertiser, COMPLETE)
    stored = [
        item for item in bucket.objects.filter(Prefix=f"advertisers/{advertiser}/stage-history/")
    ]
    bucket.put_object(Key=stored[0].key, Body=b"")

    response = client.get(f"/advertisers/{advertiser}/mapping")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The stored stage-history file can no longer be read. Upload it again."
    }
