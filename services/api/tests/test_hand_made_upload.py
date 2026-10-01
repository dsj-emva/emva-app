"""The hand-made dataset (tests/hand_made/, written by hand) uploaded as a person would.

What it holds, for the slices that use it (a planned-hospitality advertiser's CRM export):
- leads.csv: 101 leads submitted from January 2024 to July 2025; L-1101's submission time is
  unreadable ("TBC"); some budgets are blank.
- stage_history.csv: one row per stage change, in the CRM's own stage names. On the ladder:
  New enquiry is Submitted; Call attempted and Left voicemail are Contact attempted; Discovery call
  is Engaged; Brief agreed is Qualified; Quote sent and Itinerary revised are Proposal; Closed won
  is Won (with its Deal value); Closed lost and Closed Lost are Lost.
- From Contact attempted onwards each transition has at least 12 leads that made it and 12 that
  failed it; some leads skip stages, some are unfinished at every stage, some were never
  contacted (only New enquiry, or no rows at all) and two were lost before any contact.
- Unreadable rows: one without a lead, one without a stage, one without a readable time, and one
  for a lead (L-9042) that is not in the leads file.
- Bigger budgets, Safari and Honeymoon trips, and Phone or Partner agent enquiries win more.
"""

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from emva_api.clock import FixedClock

HAND_MADE = Path(__file__).parent / "hand_made"


def upload_hand_made(client: TestClient) -> str:
    advertiser = client.post(
        "/advertisers", json={"name": "Savanna Journeys", "data_source": "hand_made_test"}
    ).json()["id"]
    for kind, file_name in [("leads", "leads.csv"), ("stage-history", "stage_history.csv")]:
        response = client.put(
            f"/advertisers/{advertiser}/files/{kind}",
            params={"file_name": file_name},
            content=(HAND_MADE / file_name).read_bytes(),
            headers={"Content-Type": "text/csv"},
        )
        assert response.status_code == 200, response.text
    return advertiser


def test_both_hand_made_files_show_their_row_counts_and_columns(client: TestClient):
    advertiser_id = upload_hand_made(client)
    advertiser = client.get(f"/advertisers/{advertiser_id}").json()
    leads_columns = client.get(f"/advertisers/{advertiser_id}/files/leads/columns").json()
    history_columns = client.get(f"/advertisers/{advertiser_id}/files/stage-history/columns").json()

    leads, history = advertiser["leads_file"], advertiser["stage_history_file"]
    assert advertiser["review_available"] is True
    assert leads["row_count"] == 101
    assert leads["column_names"] == [
        "Lead ID",
        "Created Date",
        "Full Name",
        "Email",
        "Phone",
        "Enquiry Channel",
        "Trip Type",
        "Party Size",
        "Nights",
        "Budget (GBP)",
    ]
    assert leads_columns[6]["examples"] == ["Safari", "Family holiday", "Corporate retreat"]
    assert history["row_count"] == 418
    assert history_columns[1] == {
        "name": "Stage",
        "examples": ["New enquiry", "Call attempted", "Discovery call"],
    }


def test_the_hand_made_stage_history_uses_the_crms_own_stage_names(client: TestClient):
    advertiser = upload_hand_made(client)

    review = client.put(
        f"/advertisers/{advertiser}/mapping", json={"stage_history": {"crm_stage": "Stage"}}
    ).json()

    assert review["crm_stages"] == [
        {"name": "New enquiry", "row_count": 98},
        {"name": "Call attempted", "row_count": 82},
        {"name": "Discovery call", "row_count": 67},
        {"name": "Closed lost", "row_count": 57},
        {"name": "Brief agreed", "row_count": 44},
        {"name": "Quote sent", "row_count": 35},
        {"name": "Closed won", "row_count": 19},
        {"name": "Left voicemail", "row_count": 10},
        {"name": "Itinerary revised", "row_count": 3},
        {"name": "Closed Lost", "row_count": 2},
    ]


HAND_MADE_MAPPING = {
    "leads": {
        "lead_id": "Lead ID",
        "submitted_at": "Created Date",
        "name": "Full Name",
        "email": "Email",
        "phone": "Phone",
        "inputs": {
            "Enquiry Channel": "category",
            "Trip Type": "category",
            "Party Size": "number",
            "Nights": "number",
            "Budget (GBP)": "number",
        },
    },
    "stage_history": {
        "lead_id": "Lead ID",
        "crm_stage": "Stage",
        "changed_at": "Changed At",
        "deal_value": "Deal Value",
    },
    "crm_stages": {
        "New enquiry": "submitted",
        "Call attempted": "contact_attempted",
        "Left voicemail": "contact_attempted",
        "Discovery call": "engaged",
        "Brief agreed": "qualified",
        "Quote sent": "proposal",
        "Itinerary revised": "proposal",
        "Closed won": "won",
        "Closed lost": "lost",
        "Closed Lost": "lost",
    },
    "typical_deal_size": 12000.0,
}


def test_every_column_and_crm_stage_of_the_hand_made_files_can_be_mapped_and_confirmed(
    client: TestClient, clock: FixedClock
):
    advertiser = upload_hand_made(client)
    saved = client.put(f"/advertisers/{advertiser}/mapping", json=HAND_MADE_MAPPING).json()
    assert saved["problems"] == []
    clock.set(datetime(2026, 9, 14, 11, 5, tzinfo=UTC))

    confirmed = client.post(f"/advertisers/{advertiser}/mapping/confirmation")

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["confirmed_at"] == "2026-09-14T11:05:00Z"
    assert confirmed.json()["mapping"] == HAND_MADE_MAPPING
