"""Features: a lead's inputs as the model reads them, with parameters fitted on the training
leads and kept with the model; the same code for training, the backtest and scoring."""

from datetime import UTC, datetime

import pytest

from emva_api.features import Features, Refused, fit_features
from emva_api.formatter import FormattedLead


def lead(numbers: dict[str, float | None], categories: dict[str, str | None]) -> FormattedLead:
    return FormattedLead(
        identifier_hash="x",
        submitted_at=datetime(2024, 3, 1, tzinfo=UTC),
        email_hash=None,
        phone_hash=None,
        phone_country_found=None,
        numbers=numbers,
        categories=categories,
    )


def test_a_number_is_standardised_with_the_training_mean_and_sd_then_flagged_given():
    features = fit_features([lead({"Nights": n}, {}) for n in (2.0, 4.0, 6.0, 8.0)])

    # Mean 5, standard deviation sqrt(5); the flag after it says the number is given.
    assert features.row(lead({"Nights": 10.0}, {})) == pytest.approx([5 / 5**0.5, 0.0])
    assert features.row(lead({"Nights": 5.0}, {})) == [0.0, 0.0]


def test_a_number_the_same_for_every_training_lead_is_only_centred():
    features = fit_features([lead({"Nights": 3.0}, {}) for _ in range(3)])

    assert features.row(lead({"Nights": 5.0}, {})) == [2.0, 0.0]


def test_a_missing_number_is_the_training_mean_and_flagged_as_missing():
    features = fit_features([lead({"Budget": b}, {}) for b in (1000.0, 3000.0, None)])

    # The mean of the numbers given (2000) stands in for a missing one, and a flag says so.
    assert features.row(lead({"Budget": None}, {})) == [0.0, 1.0]
    assert features.row(lead({"Budget": 3000.0}, {})) == [1.0, 0.0]


def test_a_number_never_missing_in_training_is_still_read_when_missing():
    features = fit_features([lead({"Budget": b}, {}) for b in (1000.0, 3000.0)])

    assert features.row(lead({"Budget": None}, {})) == [0.0, 1.0]


def test_a_category_is_one_hot_over_the_training_values_most_common_first():
    trips = ["Safari", "Honeymoon", "Safari", "City break", "Honeymoon", "Safari"]
    features = fit_features([lead({}, {"Trip": trip}) for trip in trips])

    assert features.categories[0].values == ("Safari", "Honeymoon", "City break")
    assert features.row(lead({}, {"Trip": "Honeymoon"})) == [0.0, 1.0, 0.0]


def test_a_category_unseen_in_training_is_refused():
    features = fit_features([lead({}, {"Trip": "Safari"})])

    with pytest.raises(Refused, match="“Trip” is “Cruise”, which no training lead had."):
        features.row(lead({}, {"Trip": "Cruise"}))


def test_a_missing_category_is_a_value_of_its_own():
    features = fit_features([lead({}, {"Trip": trip}) for trip in ("Safari", None, "Safari")])

    assert features.row(lead({}, {"Trip": None})) == [0.0, 1.0]
    features = fit_features([lead({}, {"Trip": "Safari"})])
    with pytest.raises(Refused, match="“Trip” is missing, and no training lead lacked it."):
        features.row(lead({}, {"Trip": None}))


def test_numbers_come_before_categories_each_in_the_order_of_the_inputs():
    leads = [
        lead({"Nights": 2.0, "Party": 1.0}, {"Trip": "Safari", "Channel": "Phone"}),
        lead({"Nights": 4.0, "Party": 3.0}, {"Trip": "Safari", "Channel": "Web"}),
    ]
    features = fit_features(leads)

    row = lead({"Nights": 4.0, "Party": 1.0}, {"Trip": "Safari", "Channel": "Web"})
    assert features.row(row) == [1.0, 0.0, -1.0, 0.0, 1.0, 0.0, 1.0]


def test_the_typical_lead_has_every_number_at_its_mean_and_every_category_at_its_most_common():
    leads = [
        lead({"Nights": n}, {"Trip": t})
        for n, t in ((2.0, "Honeymoon"), (None, "Safari"), (6.0, "Safari"))
    ]

    assert fit_features(leads).typical() == ({"Nights": 4.0}, {"Trip": "Safari"})


def test_a_number_no_training_lead_gave_is_not_given_in_the_typical_lead():
    features = fit_features([lead({"Budget": None}, {}) for _ in range(3)])

    assert features.numbers[0].any_given is False
    assert features.typical() == ({"Budget": None}, {})


def test_the_fitted_parameters_are_kept_as_json_and_read_back_the_same():
    leads = [lead({"Budget": b}, {"Trip": t}) for b, t in ((1.0, "Safari"), (None, "Honeymoon"))]
    features = fit_features(leads)

    again = Features.model_validate_json(features.model_dump_json())

    assert again == features
    assert again.row(leads[1]) == features.row(leads[1])
