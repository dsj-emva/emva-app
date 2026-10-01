"""Training through the API: a Training run is recorded in Postgres at the injected clock's time
and its model kept in object storage as JSON; nothing trains, and nothing is stored, before the
Mapping is confirmed and its data formatted."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from botocore.exceptions import EndpointConnectionError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_formatting_api import confirm, confirmed_without_formatting, map_hand_made
from test_hand_made_upload import HAND_MADE_MAPPING, upload_hand_made

from emva_api.clock import FixedClock
from emva_api.main import create_app
from emva_api.object_store import ObjectStore
from emva_api.settings import Settings

# Pooled over the four Transitions: 169 made of 225 finished.
POOLED = 169 / 225


def transition(from_stage, to_stage, name, made, failed, unfinished):
    return {
        "transition": {"from_stage": from_stage, "to_stage": to_stage, "name": name},
        "made": made,
        "failed": failed,
        "unfinished": unfinished,
        "fitted": True,
        "verdict": "Learned",
        "smoothed_rate": pytest.approx((made + 2 * POOLED) / (made + failed + 2)),
    }


HAND_MADE_TRANSITIONS = [
    transition("contact_attempted", "engaged", "Contact attempted → Engaged", 67, 16, 4),
    transition("engaged", "qualified", "Engaged → Qualified", 49, 15, 3),
    transition("qualified", "proposal", "Qualified → Proposal", 35, 12, 2),
    transition("proposal", "won", "Proposal → Won", 18, 13, 4),
]

RULE = (
    "A transition's model is learned only from at least 10 leads that made it and 10 that "
    "failed it. With fewer it is too few to learn, and every lead gets its smoothed rate: its "
    "own rate pulled towards the rate across all four transitions."
)


def train(client: TestClient, advertiser: str):
    return client.post(f"/advertisers/{advertiser}/training-runs")


def training(client: TestClient, advertiser: str):
    return client.get(f"/advertisers/{advertiser}/training")


def refused_with(client: TestClient, advertiser: str, reason: str) -> None:
    """Training is refused with the reason, and the screen is told the same."""
    refused = train(client, advertiser)
    assert refused.status_code == 409
    assert refused.json()["detail"] == reason
    assert training(client, advertiser).json() == {
        "trainable": False,
        "not_trainable_because": reason,
        "rule": RULE,
        "latest": None,
    }


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
        refused_with(
            own_client,
            advertiser,
            "The mapping is not confirmed yet. Nothing trains before a person confirms it.",
        )
    assert training_runs_stored(own_settings, own_bucket) == (0, [])


def test_training_is_refused_when_the_mapping_is_confirmed_but_its_data_not_formatted(
    own_client: TestClient, own_settings: Settings, own_bucket
):
    advertiser = confirmed_without_formatting(own_client, own_settings, HAND_MADE_MAPPING)

    refused_with(
        own_client,
        advertiser,
        "The mapping is confirmed but its data is not formatted yet. Confirm again to format it.",
    )
    assert training_runs_stored(own_settings, own_bucket) == (0, [])


def test_training_is_refused_when_the_mapping_marks_no_input_to_the_score(client: TestClient):
    no_inputs = {**HAND_MADE_MAPPING, "leads": {**HAND_MADE_MAPPING["leads"], "inputs": {}}}
    advertiser = map_hand_made(client, no_inputs)
    confirm(client, advertiser)

    refused_with(
        client,
        advertiser,
        "The mapping marks no input to the score, so there is nothing to learn from.",
    )


def test_training_on_the_hand_made_dataset_learns_every_transition_and_counts_its_leads(
    client: TestClient, clock: FixedClock
):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)
    clock.set(datetime(2026, 9, 15, 8, 30, tzinfo=UTC))

    assert training(client, advertiser).json() == {
        "trainable": True,
        "not_trainable_because": None,
        "rule": RULE,
        "latest": None,
    }

    trained = train(client, advertiser)

    assert trained.status_code == 201, trained.text
    assert trained.json()["trainable"] is True
    run = trained.json()["latest"]
    assert run["trained_at"] == "2026-09-15T08:30:00Z"
    assert run["transitions"] == HAND_MADE_TRANSITIONS


def test_the_latest_training_run_reads_back_as_it_was_trained(client: TestClient):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)

    second = [train(client, advertiser).json() for _ in range(2)][-1]

    assert training(client, advertiser).json() == second


def test_of_runs_trained_at_the_same_clock_time_the_one_trained_last_is_the_latest(
    client: TestClient,
):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)

    runs = [train(client, advertiser).json()["latest"]["id"] for _ in range(3)]

    assert len(set(runs)) == 3
    assert training(client, advertiser).json()["latest"]["id"] == runs[-1]


def test_when_the_latest_model_cannot_be_read_from_storage_it_says_so(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)
    train(client, advertiser)

    def unreachable(store: ObjectStore, key: str) -> bytes:
        raise EndpointConnectionError(endpoint_url="http://object-storage")

    monkeypatch.setattr(ObjectStore, "get", unreachable)
    read = training(client, advertiser)

    assert read.status_code == 503
    assert read.json()["detail"] == (
        "The latest Training run's model could not be read from storage. Try again."
    )


def test_the_model_is_kept_in_object_storage_as_readable_json(client: TestClient, bucket):
    advertiser = map_hand_made(client)
    confirm(client, advertiser)

    run = train(client, advertiser).json()["latest"]

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
    # A value and a missing flag per number, and one per category value.
    assert len(first["regression"]["coefficients"]) == 3 * 2 + 5 + 5


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
