"""Scoring one lead through the API: the form is the Mapping's inputs with the categories seen in
training; the entered lead goes through the same Formatter and Features as training, then the
latest Training run's model. Nothing about the lead is stored."""

import csv
import io
import math
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from test_formatting_api import confirm, map_hand_made, upload
from test_hand_made_upload import HAND_MADE, HAND_MADE_MAPPING
from test_training_api import train

from emva_api.clock import FixedClock
from emva_api.csv_file import read_csv
from emva_api.formatter import format_files
from emva_api.main import create_app
from emva_api.mapping import ConfirmedMapping, Mapping
from emva_api.model import Model
from emva_api.personal_data import hashed_identifier
from emva_api.settings import Settings

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
    inputs = form.json()["inputs"]
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
    assert (inputs[0]["typical"], inputs[0]["typical_choice"]) == ("Web form", "Web form")
    assert (inputs[2]["choices"], inputs[2]["typical_choice"]) == (None, None)
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
    assert body["data_source"] == "on hand-made test data"
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


def test_a_mapping_the_latest_training_run_did_not_learn_from_is_a_conflict_on_form_and_score(
    client: TestClient, settings: Settings, trained: str
):
    """A mismatch between the Mapping and the model is the advertiser's state, not the lead's."""
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE mapping SET content = jsonb_set(content::jsonb, "
                "'{leads,inputs,Trip Type}', '\"number\"')::json WHERE advertiser_id = :id"
            ),
            {"id": trained},
        )
    engine.dispose()
    because = (
        "“Trip Type” is not an input the latest Training run learned from as a number. Train again."
    )

    form = scoring_form(client, trained)
    assert (form.status_code, form.json()["detail"]) == (409, because)
    refused(client, trained, {**A_LEAD, "Trip Type": "3"}, 409, because)


def hand_made_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO((HAND_MADE / "leads.csv").read_text())))


def test_an_entered_lead_gets_exactly_the_chance_training_gives_the_same_lead(
    client: TestClient, trained: str, bucket
):
    run = client.get(f"/advertisers/{trained}/training").json()["latest"]["id"]
    model = Model.model_validate_json(
        bucket.Object(f"advertisers/{trained}/training-runs/{run}.json").get()["Body"].read()
    )
    mapping = ConfirmedMapping(Mapping.model_validate(HAND_MADE_MAPPING), model.as_of)
    tables = [read_csv((HAND_MADE / n).read_bytes()) for n in ("leads.csv", "stage_history.csv")]
    formatted = {lead.identifier_hash: lead for lead in format_files(*tables, mapping).leads}

    # One with every number given and one without a budget.
    for row in [r for r in hand_made_rows() if r["Lead ID"] in ("L-1001", "L-1008")]:
        inputs = {column: row[column] for column in HAND_MADE_MAPPING["leads"]["inputs"]}
        scored = score(client, trained, inputs)

        assert scored.status_code == 200, scored.text
        trained_lead = formatted[hashed_identifier(row["Lead ID"])]
        assert scored.json()["chance_of_winning"] == model.chance_of_winning(trained_lead)


@pytest.fixture
def own_client(own_settings: Settings, clock: FixedClock) -> Iterator[TestClient]:
    with TestClient(create_app(own_settings, clock)) as client:
        yield client


def everything_stored(settings: Settings, bucket) -> tuple[dict[str, int], list[str]]:
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        counts = {
            table: connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
            for table in inspect(connection).get_table_names()
        }
    engine.dispose()
    return counts, sorted(o.key for o in bucket.objects.all())


def test_scoring_a_lead_stores_nothing(own_client: TestClient, own_settings: Settings, own_bucket):
    advertiser = map_hand_made(own_client)
    confirm(own_client, advertiser)
    train(own_client, advertiser)
    before = everything_stored(own_settings, own_bucket)

    assert score(own_client, advertiser, A_LEAD).status_code == 200
    assert score(own_client, advertiser, {**A_LEAD, "Trip Type": "Cruise"}).status_code == 400

    assert everything_stored(own_settings, own_bucket) == before


def test_a_category_some_training_leads_did_not_give_can_be_scored_as_not_given(
    client: TestClient,
):
    rows = hand_made_rows()
    for row in rows[1:8]:
        row["Enquiry Channel"] = ""
    leads = io.StringIO()
    writer = csv.DictWriter(leads, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    advertiser = client.post(
        "/advertisers", json={"name": "Blank channels", "data_source": "hand_made_test"}
    ).json()["id"]
    upload(client, advertiser, "leads", leads.getvalue())
    upload(client, advertiser, "stage-history", (HAND_MADE / "stage_history.csv").read_text())
    assert (
        client.put(f"/advertisers/{advertiser}/mapping", json=HAND_MADE_MAPPING).json()["problems"]
        == []
    )
    confirm(client, advertiser)
    assert train(client, advertiser).status_code == 201

    [channel] = [
        i
        for i in scoring_form(client, advertiser).json()["inputs"]
        if i["column"] == "Enquiry Channel"
    ]
    assert NOT_GIVEN in channel["choices"]
    scored = score(client, advertiser, {**A_LEAD, "Enquiry Channel": ""})

    assert scored.status_code == 200, scored.text
    step = scored.json()["explanation"]["steps"][0]
    assert (step["input"], step["value"]) == ("Enquiry Channel", "not given")


def test_scoring_is_refused_when_no_lead_finished_any_transition(client: TestClient):
    """Ruling 13's one refusal: about the Training run, not the lead, so a conflict like having
    no Training run."""
    rows = hand_made_rows()
    history = ["Lead ID,Stage,Changed At,Deal Value,Changed By"]
    history += [f"{r['Lead ID']},New enquiry,2024-01-04 09:12,,system" for r in rows[:20]]
    # The only win belongs to a lead the leads file does not have, so it is not kept.
    history.append("L-9999,Closed won,2024-02-01 10:00,9000,AK")
    advertiser = client.post(
        "/advertisers", json={"name": "No history", "data_source": "hand_made_test"}
    ).json()["id"]
    upload(client, advertiser, "leads", (HAND_MADE / "leads.csv").read_text())
    upload(client, advertiser, "stage-history", "\n".join(history) + "\n")
    assert (
        client.put(f"/advertisers/{advertiser}/mapping", json=HAND_MADE_MAPPING).json()["problems"]
        == []
    )
    confirm(client, advertiser)
    assert train(client, advertiser).status_code == 201

    refused(
        client,
        advertiser,
        A_LEAD,
        409,
        "No lead has made or failed any Transition yet, so no chance is known.",
    )
