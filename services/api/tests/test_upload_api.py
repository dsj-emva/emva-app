from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from emva_api.clock import FixedClock
from emva_api.uploads import MAX_UPLOAD_BYTES

LEADS = b"Lead ID,Budget (GBP)\nL1,8000\nL2,\nL3,12000\n"
STAGE_HISTORY = (
    b"Lead ID,Stage,Changed at\n"
    b"L1,New enquiry,2026-01-02\nL1,Quote sent,2026-01-09\nL2,New enquiry,2026-01-03\n"
)


def create_advertiser(client: TestClient, name: str = "Savanna Journeys") -> str:
    response = client.post("/advertisers", json={"name": name, "data_source": "hand_made_test"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client: TestClient, advertiser: str, kind: str, content, file_name: str):
    return client.put(
        f"/advertisers/{advertiser}/files/{kind}",
        params={"file_name": file_name},
        content=content,
        headers={"Content-Type": "text/csv"},
    )


def stored_objects(bucket, advertiser: str) -> list[bytes]:
    return [
        item.get()["Body"].read()
        for item in bucket.objects.filter(Prefix=f"advertisers/{advertiser}/")
    ]


def test_a_new_advertiser_has_no_files_and_its_review_is_unavailable(client: TestClient):
    response = client.post(
        "/advertisers", json={"name": "Savanna Journeys", "data_source": "hand_made_test"}
    )

    assert response.status_code == 201
    advertiser = client.get(f"/advertisers/{response.json()['id']}").json()
    assert advertiser["name"] == "Savanna Journeys"
    assert advertiser["data_source"] == "hand_made_test"
    assert advertiser["data_source_label"] == "on hand-made test data"
    assert advertiser["leads_file"] is None
    assert advertiser["stage_history_file"] is None
    assert advertiser["review_available"] is False


def test_the_data_sources_to_pick_from_are_listed_with_their_labels(client: TestClient):
    response = client.get("/data-sources")

    assert response.status_code == 200
    assert response.json() == [
        {"value": "hand_made_test", "label": "on hand-made test data"},
        {"value": "simulated", "label": "on simulated data"},
        {"value": "public", "label": "on public data"},
        {"value": "private", "label": "on the advertiser's private export"},
    ]


def test_an_advertiser_needs_a_name(client: TestClient):
    response = client.post("/advertisers", json={"name": "  ", "data_source": "simulated"})

    assert response.status_code == 422


def test_an_unknown_advertiser_is_not_found(client: TestClient):
    response = client.get("/advertisers/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_the_upload_time_comes_from_the_clock(client: TestClient, clock: FixedClock):
    advertiser = create_advertiser(client)
    clock.set(datetime(2026, 9, 15, 8, 45, tzinfo=UTC))

    response = upload(client, advertiser, "leads", b"Lead ID\nL1\n", "leads.csv")

    assert response.status_code == 200, response.text
    assert response.json()["uploaded_at"] == "2026-09-15T08:45:00Z"
    leads_file = client.get(f"/advertisers/{advertiser}").json()["leads_file"]
    assert leads_file["uploaded_at"] == "2026-09-15T08:45:00Z"


def test_an_uploaded_file_shows_its_name_row_count_and_column_names(client: TestClient):
    advertiser = create_advertiser(client)

    response = upload(client, advertiser, "leads", LEADS, "crm-export.csv")

    assert response.status_code == 200
    leads_file = client.get(f"/advertisers/{advertiser}").json()["leads_file"]
    assert leads_file["file_name"] == "crm-export.csv"
    assert leads_file["row_count"] == 3
    assert leads_file["column_names"] == ["Lead ID", "Budget (GBP)"]


def test_each_column_comes_with_example_values_read_from_the_file(client: TestClient):
    advertiser = create_advertiser(client)
    upload(client, advertiser, "leads", LEADS, "crm-export.csv")

    response = client.get(f"/advertisers/{advertiser}/files/leads/columns")

    assert response.status_code == 200
    assert response.json() == [
        {"name": "Lead ID", "examples": ["L1", "L2", "L3"]},
        {"name": "Budget (GBP)", "examples": ["8000", "12000"]},
    ]


def test_columns_need_the_file_uploaded(client: TestClient):
    advertiser = create_advertiser(client)

    response = client.get(f"/advertisers/{advertiser}/files/stage-history/columns")

    assert response.status_code == 404
    assert response.json() == {"detail": "The stage-history file is not uploaded."}


def test_the_review_is_available_only_once_both_files_are_uploaded(client: TestClient):
    advertiser = create_advertiser(client)

    upload(client, advertiser, "stage-history", STAGE_HISTORY, "history.csv")
    assert client.get(f"/advertisers/{advertiser}").json()["review_available"] is False

    upload(client, advertiser, "leads", LEADS, "leads.csv")
    assert client.get(f"/advertisers/{advertiser}").json()["review_available"] is True


def test_uploading_a_file_again_replaces_it(client: TestClient, bucket, clock: FixedClock):
    advertiser = create_advertiser(client)
    upload(client, advertiser, "leads", LEADS, "wrong-export.csv")
    clock.set(datetime(2026, 9, 16, 9, 0, tzinfo=UTC))

    response = upload(client, advertiser, "leads", b"Lead ID\nL7\n", "right-export.csv")

    assert response.status_code == 200, response.text
    leads_file = client.get(f"/advertisers/{advertiser}").json()["leads_file"]
    assert leads_file["file_name"] == "right-export.csv"
    assert leads_file["row_count"] == 1
    assert leads_file["uploaded_at"] == "2026-09-16T09:00:00Z"
    assert stored_objects(bucket, advertiser) == [b"Lead ID\nL7\n"]


def test_an_unreadable_file_is_refused_with_the_reason_and_not_kept(client: TestClient, bucket):
    advertiser = create_advertiser(client)

    response = upload(client, advertiser, "leads", b"", "leads.csv")

    assert response.status_code == 400
    assert response.json() == {"detail": "The file is empty."}
    assert client.get(f"/advertisers/{advertiser}").json()["leads_file"] is None
    assert stored_objects(bucket, advertiser) == []


def test_a_file_needs_a_name(client: TestClient):
    advertiser = create_advertiser(client)

    assert upload(client, advertiser, "leads", LEADS, " ").status_code == 422


def too_big() -> bytes:
    header = b"Lead ID,Notes\n"
    return header + b"x" * (MAX_UPLOAD_BYTES + 1 - len(header))


def test_a_file_over_the_size_limit_is_refused(client: TestClient, bucket):
    advertiser = create_advertiser(client)

    response = upload(client, advertiser, "leads", too_big(), "huge.csv")

    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than 20 MB."}
    assert stored_objects(bucket, advertiser) == []


def test_a_file_over_the_size_limit_is_refused_when_sent_without_its_length(
    client: TestClient,
):
    advertiser = create_advertiser(client)
    content = too_big()
    chunks = (content[start : start + (1 << 20)] for start in range(0, len(content), 1 << 20))

    response = upload(client, advertiser, "leads", chunks, "huge.csv")

    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than 20 MB."}


def test_a_file_of_exactly_the_size_limit_is_taken(client: TestClient):
    advertiser = create_advertiser(client)
    header, row = b"Lead ID\n", b"L-1001\n"
    rows, rest = divmod(MAX_UPLOAD_BYTES - len(header), len(row))
    content = header + row * rows + b"x" * (rest - 1) + b"\n"
    assert len(content) == MAX_UPLOAD_BYTES

    assert upload(client, advertiser, "leads", content, "big.csv").status_code == 200


@pytest.mark.parametrize(
    ("failure", "status", "detail"),
    [
        (
            IntegrityError("INSERT", {}, Exception("duplicate key")),
            409,
            "Another upload of the leads file finished first. Upload it again to replace it.",
        ),
        (
            OperationalError("COMMIT", {}, Exception("connection lost")),
            503,
            "The leads file could not be saved. Try again.",
        ),
    ],
)
def test_an_upload_whose_record_cannot_be_saved_leaves_no_file_behind(
    client: TestClient, bucket, monkeypatch: pytest.MonkeyPatch, failure, status, detail
):
    advertiser = create_advertiser(client)

    def fail(session: Session) -> None:
        raise failure

    monkeypatch.setattr(Session, "commit", fail)
    response = upload(client, advertiser, "leads", LEADS, "leads.csv")
    monkeypatch.undo()

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert client.get(f"/advertisers/{advertiser}").json()["leads_file"] is None
    assert stored_objects(bucket, advertiser) == []


def test_a_replacement_that_cannot_be_saved_keeps_the_earlier_file(
    client: TestClient, bucket, monkeypatch: pytest.MonkeyPatch
):
    advertiser = create_advertiser(client)
    upload(client, advertiser, "leads", LEADS, "leads.csv")

    def fail(session: Session) -> None:
        raise OperationalError("COMMIT", {}, Exception("connection lost"))

    monkeypatch.setattr(Session, "commit", fail)
    response = upload(client, advertiser, "leads", b"Lead ID\nL7\n", "other.csv")
    monkeypatch.undo()

    assert response.status_code == 503
    assert client.get(f"/advertisers/{advertiser}").json()["leads_file"]["file_name"] == "leads.csv"
    assert stored_objects(bucket, advertiser) == [LEADS]


def test_a_stored_file_that_can_no_longer_be_read_is_reported(client: TestClient, bucket):
    advertiser = create_advertiser(client)
    upload(client, advertiser, "stage-history", STAGE_HISTORY, "history.csv")
    [stored] = bucket.objects.filter(Prefix=f"advertisers/{advertiser}/")
    bucket.put_object(Key=stored.key, Body=b"")

    response = client.get(f"/advertisers/{advertiser}/files/stage-history/columns")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The stored stage-history file can no longer be read. Upload it again."
    }
