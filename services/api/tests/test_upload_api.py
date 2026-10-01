from datetime import UTC, datetime

from fastapi.testclient import TestClient

from emva_api.clock import FixedClock


def create_advertiser(client: TestClient, name: str = "Savanna Journeys") -> str:
    response = client.post("/advertisers", json={"name": name, "data_source": "hand_made_test"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_a_new_advertiser_has_no_files_and_its_review_is_unavailable(client: TestClient):
    response = client.post(
        "/advertisers", json={"name": "Savanna Journeys", "data_source": "hand_made_test"}
    )

    assert response.status_code == 201
    advertiser = client.get(f"/advertisers/{response.json()['id']}").json()
    assert advertiser["name"] == "Savanna Journeys"
    assert advertiser["data_source"] == "hand_made_test"
    assert advertiser["leads_file"] is None
    assert advertiser["stage_history_file"] is None
    assert advertiser["review_available"] is False


def test_an_advertiser_needs_a_name(client: TestClient):
    response = client.post("/advertisers", json={"name": "  ", "data_source": "simulated"})

    assert response.status_code == 422


def test_an_unknown_advertiser_is_not_found(client: TestClient):
    response = client.get("/advertisers/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_the_upload_time_comes_from_the_clock(client: TestClient, clock: FixedClock):
    advertiser = create_advertiser(client)
    clock.set(datetime(2026, 9, 15, 8, 45, tzinfo=UTC))

    response = client.put(
        f"/advertisers/{advertiser}/files/leads",
        params={"file_name": "leads.csv"},
        content=b"Lead ID\nL1\n",
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["uploaded_at"] == "2026-09-15T08:45:00Z"
    assert (
        client.get(f"/advertisers/{advertiser}").json()["leads_file"]["uploaded_at"]
        == "2026-09-15T08:45:00Z"
    )


def upload(client: TestClient, advertiser: str, kind: str, content: bytes, file_name: str):
    return client.put(
        f"/advertisers/{advertiser}/files/{kind}",
        params={"file_name": file_name},
        content=content,
        headers={"Content-Type": "text/csv"},
    )


LEADS = b"Lead ID,Budget (GBP)\nL1,8000\nL2,\nL3,12000\n"
STAGE_HISTORY = (
    b"Lead ID,Stage,Changed at\n"
    b"L1,New enquiry,2026-01-02\nL1,Quote sent,2026-01-09\nL2,New enquiry,2026-01-03\n"
)


def test_an_uploaded_file_shows_its_name_row_count_and_columns_with_example_values(
    client: TestClient,
):
    advertiser = create_advertiser(client)

    response = upload(client, advertiser, "leads", LEADS, "crm-export.csv")

    assert response.status_code == 200
    leads_file = client.get(f"/advertisers/{advertiser}").json()["leads_file"]
    assert leads_file["file_name"] == "crm-export.csv"
    assert leads_file["row_count"] == 3
    assert leads_file["columns"] == [
        {"name": "Lead ID", "examples": ["L1", "L2", "L3"]},
        {"name": "Budget (GBP)", "examples": ["8000", "12000"]},
    ]


def test_the_review_is_available_only_once_both_files_are_uploaded(client: TestClient):
    advertiser = create_advertiser(client)

    upload(client, advertiser, "stage-history", STAGE_HISTORY, "history.csv")
    assert client.get(f"/advertisers/{advertiser}").json()["review_available"] is False

    upload(client, advertiser, "leads", LEADS, "leads.csv")
    assert client.get(f"/advertisers/{advertiser}").json()["review_available"] is True


def test_a_file_already_uploaded_is_not_replaced(client: TestClient):
    advertiser = create_advertiser(client)
    upload(client, advertiser, "leads", LEADS, "leads.csv")

    response = upload(client, advertiser, "leads", b"Other\nx\n", "other.csv")

    assert response.status_code == 409
    assert response.json() == {"detail": "The leads file is already uploaded."}
    leads_file = client.get(f"/advertisers/{advertiser}").json()["leads_file"]
    assert leads_file["file_name"] == "leads.csv"


def test_an_unreadable_file_is_refused_with_the_reason_and_not_kept(client: TestClient):
    advertiser = create_advertiser(client)

    response = upload(client, advertiser, "leads", b"", "leads.csv")

    assert response.status_code == 400
    assert response.json() == {"detail": "The file is empty."}
    assert client.get(f"/advertisers/{advertiser}").json()["leads_file"] is None


def test_a_file_needs_a_name(client: TestClient):
    advertiser = create_advertiser(client)

    assert upload(client, advertiser, "leads", LEADS, " ").status_code == 422


def test_lists_every_crm_stage_name_in_the_chosen_column_with_its_row_count(client: TestClient):
    advertiser = create_advertiser(client)
    upload(client, advertiser, "stage-history", STAGE_HISTORY, "history.csv")

    response = client.get(
        f"/advertisers/{advertiser}/files/stage-history/crm-stages", params={"column": "Stage"}
    )

    assert response.status_code == 200
    assert response.json() == [
        {"name": "New enquiry", "row_count": 2},
        {"name": "Quote sent", "row_count": 1},
    ]


def test_crm_stages_need_a_column_the_stage_history_file_has(client: TestClient):
    advertiser = create_advertiser(client)
    upload(client, advertiser, "stage-history", STAGE_HISTORY, "history.csv")

    response = client.get(
        f"/advertisers/{advertiser}/files/stage-history/crm-stages", params={"column": "Status"}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The stage-history file has no column 'Status'."}


def test_crm_stages_need_the_stage_history_file(client: TestClient):
    advertiser = create_advertiser(client)

    response = client.get(
        f"/advertisers/{advertiser}/files/stage-history/crm-stages", params={"column": "Stage"}
    )

    assert response.status_code == 404
