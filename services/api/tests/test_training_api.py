"""Training through the API: a Training run is recorded in Postgres at the injected clock's time
and its model kept in object storage as JSON; nothing trains, and nothing is stored, before the
Mapping is confirmed and its data formatted."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_formatting_api import confirm, confirmed_without_formatting, map_hand_made
from test_hand_made_upload import HAND_MADE_MAPPING, upload_hand_made

from emva_api.clock import FixedClock
from emva_api.main import create_app
from emva_api.settings import Settings

HAND_MADE_TRANSITIONS = [
    {
        "from_stage": "contact_attempted",
        "to_stage": "engaged",
        "name": "Contact attempted → Engaged",
        "made": 67,
        "failed": 16,
        "unfinished": 4,
        "learned": True,
        "observed_rate": pytest.approx(67 / 83),
    },
    {
        "from_stage": "engaged",
        "to_stage": "qualified",
        "name": "Engaged → Qualified",
        "made": 49,
        "failed": 15,
        "unfinished": 3,
        "learned": True,
        "observed_rate": pytest.approx(49 / 64),
    },
    {
        "from_stage": "qualified",
        "to_stage": "proposal",
        "name": "Qualified → Proposal",
        "made": 35,
        "failed": 12,
        "unfinished": 2,
        "learned": True,
        "observed_rate": pytest.approx(35 / 47),
    },
    {
        "from_stage": "proposal",
        "to_stage": "won",
        "name": "Proposal → Won",
        "made": 18,
        "failed": 13,
        "unfinished": 4,
        "learned": True,
        "observed_rate": pytest.approx(18 / 31),
    },
]


def train(client: TestClient, advertiser: str):
    return client.post(f"/advertisers/{advertiser}/training-runs")


@pytest.fixture
def own_client(own_settings: Settings, clock: FixedClock) -> Iterator[TestClient]:
    with TestClient(create_app(own_settings, clock)) as client:
        yield client


def training_runs_stored(settings: Settings, bucket) -> tuple[int, list[str]]:
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT count(*) FROM training_run")).scalar_one()
    engine.dispose()
    return rows, [o.key for o in bucket.objects.all() if "/training-runs/" in o.key]


def test_training_is_refused_before_the_mapping_is_confirmed_and_nothing_is_stored(
    own_client: TestClient, own_settings: Settings, own_bucket
):
    no_mapping = upload_hand_made(own_client)
    draft = map_hand_made(own_client)

    for advertiser in (no_mapping, draft):
        refused = train(own_client, advertiser)

        assert refused.status_code == 409
        assert refused.json()["detail"] == (
            "The mapping is not confirmed yet. Nothing trains before a person confirms it."
        )
    assert training_runs_stored(own_settings, own_bucket) == (0, [])


def test_training_is_refused_when_the_mapping_is_confirmed_but_its_data_not_formatted(
    own_client: TestClient, own_settings: Settings, own_bucket
):
    advertiser = confirmed_without_formatting(own_client, own_settings, HAND_MADE_MAPPING)

    refused = train(own_client, advertiser)

    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "The mapping is confirmed but its data is not formatted yet. Confirm again to format it."
    )
    assert training_runs_stored(own_settings, own_bucket) == (0, [])


def test_training_is_refused_when_the_mapping_marks_no_input_to_the_score(client: TestClient):
    no_inputs = {**HAND_MADE_MAPPING, "leads": {**HAND_MADE_MAPPING["leads"], "inputs": {}}}
    advertiser = map_hand_made(client, no_inputs)
    confirm(client, advertiser)

    refused = train(client, advertiser)

    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "The mapping marks no input to the score, so there is nothing to learn from."
    )


def test_training_on_the_hand_made_dataset_learns_every_transition_and_counts_its_leads(
    client: TestClient, clock: FixedClock
):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)
    clock.set(datetime(2026, 9, 15, 8, 30, tzinfo=UTC))

    trained = train(client, advertiser)

    assert trained.status_code == 201, trained.text
    assert trained.json()["trained_at"] == "2026-09-15T08:30:00Z"
    assert trained.json()["transitions"] == HAND_MADE_TRANSITIONS


def test_the_latest_training_run_reads_back_as_it_was_trained(
    client: TestClient, clock: FixedClock
):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)
    latest = f"/advertisers/{advertiser}/training-runs/latest"
    assert client.get(latest).status_code == 404

    train(client, advertiser)
    clock.set(datetime(2026, 9, 16, tzinfo=UTC))
    second = train(client, advertiser).json()

    assert client.get(latest).json() == second


def test_the_model_is_kept_in_object_storage_as_readable_json(client: TestClient, bucket):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)

    run = train(client, advertiser).json()

    stored = bucket.Object(f"advertisers/{advertiser}/training-runs/{run['id']}.json")
    model = json.loads(stored.get()["Body"].read())
    assert model["as_of"] == "2026-09-14T10:00:00Z"
    assert [n["column"] for n in model["features"]["numbers"]] == [
        "Party Size",
        "Nights",
        "Budget (GBP)",
    ]
    first = model["transitions"][0]
    assert (first["made"], first["failed"], first["unfinished"]) == (67, 16, 4)
    assert len(first["learned"]["coefficients"]) == 3 + 1 + 5 + 5


def test_when_the_training_run_cannot_be_recorded_its_model_is_not_kept_either(
    own_client: TestClient, own_settings: Settings, own_bucket, monkeypatch: pytest.MonkeyPatch
):
    advertiser = map_hand_made(own_client)
    confirm(own_client, advertiser)

    def lost_connection(session: Session) -> None:
        raise OperationalError("COMMIT", {}, Exception("connection lost"))

    monkeypatch.setattr(Session, "commit", lost_connection)
    refused = train(own_client, advertiser)
    monkeypatch.undo()

    assert refused.status_code == 503
    assert training_runs_stored(own_settings, own_bucket) == (0, [])
