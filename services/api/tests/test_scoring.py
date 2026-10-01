"""Scoring one lead: its chance of winning over the four Transitions, its Lead score (the chance
times the advertiser's Typical deal size, decision 0003), and its Score explanation, which walks
from the typical lead to this one an input at a time."""

import math
from datetime import UTC, datetime

import pytest

from emva_api.features import CategoryInput, Features, NumberInput, Refused
from emva_api.formatter import FormattedLead
from emva_api.model import Model, Regression, TransitionModel
from emva_api.scoring import score
from emva_api.transitions import TRANSITIONS

AS_OF = datetime(2025, 1, 1, tzinfo=UTC)
# The Mapping's inputs, in its order: a category first, then two numbers.
ORDER = ("Trip", "Budget", "Nights")
FEATURES = Features(
    numbers=(
        NumberInput(column="Budget", mean=4000.0, sd=2000.0),
        NumberInput(column="Nights", mean=7.5, sd=2.5),
    ),
    # Safari is the most common trip.
    categories=(CategoryInput(column="Trip", values=("Safari", "Honeymoon", None)),),
)


def lead(budget: float | None, nights: float | None, trip: str | None) -> FormattedLead:
    return FormattedLead(
        identifier_hash="x",
        submitted_at=AS_OF,
        email_hash=None,
        phone_hash=None,
        phone_country_found=None,
        numbers={"Budget": budget, "Nights": nights},
        categories={"Trip": trip},
    )


TYPICAL = lead(4000.0, 7.5, "Safari")


def transition(i: int, rate: float | None, regression: Regression | None = None):
    return TransitionModel(
        transition=TRANSITIONS[i],
        made=10,
        failed=10,
        unfinished=0,
        smoothed_rate=rate,
        regression=regression,
    )


def model(*transitions: TransitionModel) -> Model:
    return Model(as_of=AS_OF, features=FEATURES, transitions=transitions)


# Row: Budget, Budget missing, Nights, Nights missing, Safari, Honeymoon, Trip not given.
LEARNED = model(
    transition(
        0,
        0.5,
        Regression(
            intercept=0.2,
            coefficients=(0.8, -0.6, 0.3, -0.2, 0.1, -0.4, -0.5),
            converged=True,
        ),
    ),
    transition(
        1, 0.8, Regression(intercept=1.0, coefficients=(0.4, 0.0) + (0.0,) * 5, converged=True)
    ),
    transition(2, 0.6),
    transition(3, 0.5),
)


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def test_the_lead_score_is_the_chance_of_winning_times_the_typical_deal_size():
    rates = model(transition(0, 0.5), transition(1, 0.8), transition(2, 0.5), transition(3, 0.25))

    scored = score(rates, TYPICAL, ORDER, typical_deal_size=6000.0)

    assert scored.chance_of_winning == pytest.approx(0.05)
    assert scored.typical_deal_size == 6000.0
    assert scored.lead_score == pytest.approx(300.0)


def test_the_chance_of_winning_is_the_product_of_the_four_transitions_learned_or_not():
    # Budget 6000 is one sd above the mean; the other inputs are typical.
    scored = score(LEARNED, lead(6000.0, 7.5, "Safari"), ORDER, typical_deal_size=1000.0)

    first = sigmoid(0.2 + 0.8 + 0.1)
    second = sigmoid(1.0 + 0.4)
    assert scored.chance_of_winning == pytest.approx(first * second * 0.6 * 0.5)
    assert scored.lead_score == pytest.approx(first * second * 0.6 * 0.5 * 1000.0)


def test_a_transition_too_few_to_learn_scores_every_lead_with_its_smoothed_rate():
    smoothed = model(transition(0, 0.9), transition(1, 0.7), transition(2, 0.4), transition(3, 0.3))

    low = score(smoothed, lead(100.0, 1.0, "Honeymoon"), ORDER, typical_deal_size=1.0)
    high = score(smoothed, lead(9000.0, 20.0, "Safari"), ORDER, typical_deal_size=1.0)

    assert low.chance_of_winning == pytest.approx(0.9 * 0.7 * 0.4 * 0.3)
    assert high.chance_of_winning == low.chance_of_winning


def test_the_explanation_starts_at_the_typical_lead_and_its_steps_add_up_to_the_leads_chance():
    entered = lead(6000.0, 10.0, "Honeymoon")

    scored = score(LEARNED, entered, ORDER, typical_deal_size=2000.0)
    explanation = scored.explanation

    assert explanation.typical_chance == pytest.approx(
        sigmoid(0.2 + 0.1) * sigmoid(1.0) * 0.6 * 0.5
    )
    assert [step.input for step in explanation.steps] == ["Trip", "Budget", "Nights"]
    # Each step starts where the last one ended, and the last ends exactly at the lead's chance.
    assert explanation.steps[0].before == explanation.typical_chance
    for earlier, later in zip(explanation.steps, explanation.steps[1:], strict=False):
        assert later.before == earlier.after
    assert explanation.steps[-1].after == scored.chance_of_winning
    assert math.fsum(
        [explanation.typical_chance, *(step.change for step in explanation.steps)]
    ) == pytest.approx(scored.chance_of_winning, abs=1e-15)
    # Honeymoon (-0.4 instead of Safari's +0.1) pulls the chance down; a bigger budget and more
    # nights push it up.
    assert [step.change < 0 for step in explanation.steps] == [True, False, False]


def test_each_step_names_its_input_the_typical_value_and_this_leads_value():
    scored = score(LEARNED, lead(6000.0, 10.0, "Honeymoon"), ORDER, typical_deal_size=1.0)

    assert [(s.input, s.typical, s.value) for s in scored.explanation.steps] == [
        ("Trip", "Safari", "Honeymoon"),
        ("Budget", "4,000", "6,000"),
        ("Nights", "7.5", "10"),
    ]


def test_a_lead_equal_to_the_typical_lead_has_no_movement():
    scored = score(LEARNED, TYPICAL, ORDER, typical_deal_size=1.0)

    assert [step.change for step in scored.explanation.steps] == [0.0, 0.0, 0.0]
    assert scored.explanation.typical_chance == scored.chance_of_winning


def test_a_blank_number_is_its_own_step_not_given_moved_by_its_learned_flag():
    scored = score(LEARNED, lead(None, 7.5, "Safari"), ORDER, typical_deal_size=1.0)

    budget = scored.explanation.steps[1]
    assert (budget.input, budget.typical, budget.value) == ("Budget", "4,000", "not given")
    # The missing flag's weight is -0.6 on the first Transition.
    assert budget.after == pytest.approx(sigmoid(0.2 - 0.6 + 0.1) * sigmoid(1.0) * 0.6 * 0.5)
    assert budget.change < 0
    assert scored.chance_of_winning == budget.after


def test_a_category_not_given_is_named_so():
    scored = score(LEARNED, lead(4000.0, 7.5, None), ORDER, typical_deal_size=1.0)

    assert scored.explanation.steps[0].value == "not given"


def test_a_category_no_training_lead_had_is_refused():
    with pytest.raises(Refused, match="“Trip” is “Cruise”, which no training lead had."):
        score(LEARNED, lead(4000.0, 7.5, "Cruise"), ORDER, typical_deal_size=1.0)


def test_a_chance_is_refused_when_no_lead_finished_any_transition():
    no_history = model(*(transition(i, None) for i in range(4)))

    with pytest.raises(Refused, match="No lead has made or failed any Transition yet"):
        score(no_history, TYPICAL, ORDER, typical_deal_size=1.0)
