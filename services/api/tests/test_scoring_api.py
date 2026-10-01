"""Scoring one lead through the API: the form is the Mapping's inputs with the categories seen in
training; the entered lead goes through the same Formatter and Features as training, then the
latest Training run's model. Nothing about the lead is stored."""

import math

import pytest
from fastapi.testclient import TestClient
from test_formatting_api import confirm, map_hand_made
from test_training_api import train

NOT_GIVEN = {"value": "", "label": "not given"}
A_LEAD = {
    "Enquiry Channel": "Phone",
    "Trip Type": "Safari",
    "Party Size": "2",
    "Nights": "12",
    "Budget (GBP)": "18500",
}


@pytest.fixture
def trained(client: TestClient) -> str:
    advertiser = map_hand_made(client)
    confirm(client, advertiser)
    assert train(client, advertiser).status_code == 201
    return advertiser


def scoring_form(client: TestClient, advertiser: str):
    return client.get(f"/advertisers/{advertiser}/scoring-form")


def score(client: TestClient, advertiser: str, inputs: dict[str, str]):
    return client.post(f"/advertisers/{advertiser}/scores", json={"inputs": inputs})


def test_the_form_is_the_mappings_inputs_with_the_categories_seen_in_training(
    client: TestClient, trained: str
):
    form = scoring_form(client, trained)

    assert form.status_code == 200, form.text
    body = form.json()
    assert body["typical_deal_size"] == 12000.0
    assert body["data_source"] == "hand_made_test"
    training_run = client.get(f"/advertisers/{trained}/training").json()["latest"]["id"]
    assert body["training_run_id"] == training_run
    inputs = body["inputs"]
    assert [(i["column"], i["kind"]) for i in inputs] == [
        ("Enquiry Channel", "category"),
        ("Trip Type", "category"),
        ("Party Size", "number"),
        ("Nights", "number"),
        ("Budget (GBP)", "number"),
    ]
    # Most common first, as the typical lead has them.
    assert [c["label"] for c in inputs[0]["choices"]] == [
        "Web form",
        "Instagram ad",
        "Email",
        "Phone",
        "Partner agent",
    ]
    assert inputs[0]["typical"] == "Web form"
    assert inputs[2]["choices"] is None
    assert all(NOT_GIVEN not in i["choices"] for i in inputs[:2])


def test_a_lead_is_scored_with_its_chance_lead_score_and_explanation(
    client: TestClient, trained: str
):
    scored = score(client, trained, A_LEAD)

    assert scored.status_code == 200, scored.text
    body = scored.json()
    chance = body["chance_of_winning"]
    assert 0 < chance < 1
    assert body["typical_deal_size"] == 12000.0
    assert body["lead_score"] == pytest.approx(chance * 12000.0)
    assert body["data_source"] == "hand_made_test"
    steps = body["explanation"]["steps"]
    assert [(s["input"], s["value"]) for s in steps] == [
        ("Enquiry Channel", "Phone"),
        ("Trip Type", "Safari"),
        ("Party Size", "2"),
        ("Nights", "12"),
        ("Budget (GBP)", "18,500"),
    ]
    assert steps[-1]["after"] == chance
    assert math.fsum(
        [body["explanation"]["typical_chance"], *(s["change"] for s in steps)]
    ) == pytest.approx(chance, abs=1e-12)


def test_a_blank_number_is_scored_as_not_given(client: TestClient, trained: str):
    scored = score(client, trained, {**A_LEAD, "Budget (GBP)": ""})

    assert scored.status_code == 200, scored.text
    budget = scored.json()["explanation"]["steps"][-1]
    assert (budget["input"], budget["value"]) == ("Budget (GBP)", "not given")


def refused(client: TestClient, advertiser: str, inputs: dict[str, str], status: int, detail: str):
    answer = score(client, advertiser, inputs)
    assert answer.status_code == status, answer.text
    assert answer.json()["detail"] == detail


def test_a_category_unseen_in_training_is_refused(client: TestClient, trained: str):
    refused(
        client,
        trained,
        {**A_LEAD, "Trip Type": "Cruise"},
        400,
        "“Trip Type” is “Cruise”, which no training lead had.",
    )


def test_a_category_left_blank_that_no_training_lead_lacked_is_refused(
    client: TestClient, trained: str
):
    refused(
        client,
        trained,
        {**A_LEAD, "Trip Type": ""},
        400,
        "“Trip Type” is missing, and no training lead lacked it.",
    )


def test_a_missing_input_or_one_the_mapping_does_not_have_is_refused(
    client: TestClient, trained: str
):
    without_nights = {k: v for k, v in A_LEAD.items() if k != "Nights"}
    refused(client, trained, without_nights, 400, "Enter every input; “Nights” is missing.")
    refused(
        client,
        trained,
        {**A_LEAD, "Email": "someone@example.com"},
        400,
        "“Email” is not an input to the score.",
    )


def test_a_number_that_is_not_a_number_is_refused(client: TestClient, trained: str):
    refused(client, trained, {**A_LEAD, "Nights": "twelve"}, 400, "“Nights” is not a number.")


def test_scoring_is_refused_before_a_training_run(client: TestClient):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)
    because = "No Training run yet. Train the model before scoring a lead."

    form = scoring_form(client, advertiser)
    assert (form.status_code, form.json()["detail"]) == (409, because)
    refused(client, advertiser, A_LEAD, 409, because)
