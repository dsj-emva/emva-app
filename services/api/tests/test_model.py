"""The stage-by-stage model: one regularised logistic regression per Transition from Contact
attempted, fitted only on at least 10 leads that made it and 10 that failed it; otherwise "too
few to learn" with its smoothed rate. A lead's chance of winning is the product over the
Transitions ahead of it."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from test_hand_made_upload import HAND_MADE, HAND_MADE_MAPPING

from emva_api import model as model_module
from emva_api.csv_file import read_csv
from emva_api.features import Features, NumberInput, Refused
from emva_api.formatter import FormattedLead, format_files
from emva_api.ladder import LOST, Stage, StageEvent, StageOrLost
from emva_api.mapping import ConfirmedMapping, Mapping
from emva_api.model import MIN_EACH, Model, Regression, TransitionModel, train
from emva_api.transitions import TRANSITIONS

AS_OF = datetime(2025, 1, 1, tzinfo=UTC)
START = datetime(2024, 3, 1, tzinfo=UTC)


def lead(
    budget: float | None,
    *path: StageOrLost,
    trip: str = "Safari",
    submitted: datetime = START,
    name: str = "",
) -> FormattedLead:
    return FormattedLead(
        identifier_hash=f"{name}{budget} {trip} {path}",
        submitted_at=submitted,
        email_hash=None,
        phone_hash=None,
        phone_country_found=None,
        numbers={"Budget": budget},
        categories={"Trip": trip},
        stage_events=tuple(
            StageEvent(stage, START + timedelta(days=day)) for day, stage in enumerate(path, 1)
        ),
    )


def first_transition(made: int, failed: int) -> list[FormattedLead]:
    """Leads at the first learned Transition: bigger budgets made it."""
    return [lead(1000.0 + i, Stage.CONTACT_ATTEMPTED, Stage.ENGAGED) for i in range(made)] + [
        lead(10.0 + i, Stage.CONTACT_ATTEMPTED, LOST) for i in range(failed)
    ]


def at_engaged(made: int, failed: int, unfinished: int = 0) -> list[FormattedLead]:
    """Leads past the first Transition, at the second: Engaged to Qualified."""
    path = (Stage.CONTACT_ATTEMPTED, Stage.ENGAGED)
    return (
        [lead(500.0 + i, *path, Stage.QUALIFIED, name="q") for i in range(made)]
        + [lead(400.0 + i, *path, LOST, name="l") for i in range(failed)]
        + [lead(300.0 + i, *path, name="u") for i in range(unfinished)]
    )


def won_leads() -> list[FormattedLead]:
    path = (Stage.CONTACT_ATTEMPTED, Stage.ENGAGED, Stage.QUALIFIED, Stage.PROPOSAL, Stage.WON)
    return [lead(2000.0, *path), lead(2000.0, *path[:2], LOST), lead(2000.0, *path[:3], LOST)]


def test_a_transition_needs_ten_leads_that_made_it_and_ten_that_failed_it_to_be_fitted():
    assert MIN_EACH == 10

    fitted = train(first_transition(made=10, failed=10), AS_OF).transitions[0]
    too_few_failed = train(first_transition(made=10, failed=9), AS_OF).transitions[0]
    too_few_made = train(first_transition(made=9, failed=12), AS_OF).transitions[0]

    assert fitted.regression is not None
    assert too_few_failed.regression is None
    assert too_few_made.regression is None


def test_each_transition_keeps_the_leads_that_made_failed_or_are_unfinished_there():
    leads = [*first_transition(made=3, failed=2), lead(5.0, Stage.CONTACT_ATTEMPTED)]

    model = train(leads, AS_OF)

    first, second = model.transitions[:2]
    assert (first.made, first.failed, first.unfinished) == (3, 2, 1)
    assert (second.made, second.failed, second.unfinished) == (0, 0, 3)
    assert [t.transition for t in model.transitions] == list(TRANSITIONS)


def test_a_transition_too_few_to_learn_gives_every_lead_its_smoothed_rate():
    model = train(first_transition(made=3, failed=1), AS_OF)

    # Pooled over all four Transitions, p = 3/4; so (3 + 2·3/4) / (4 + 2).
    first = model.transitions[0]
    assert first.smoothed_rate == pytest.approx(0.75)
    assert first.chance(model.features.row(lead(1.0))) == pytest.approx(0.75)
    assert first.chance(model.features.row(lead(5000.0))) == pytest.approx(0.75)


def test_the_smoothed_rate_pulls_a_transition_with_few_leads_towards_the_pooled_rate():
    # Contact attempted → Engaged: 17 made, 12 failed. Engaged → Qualified: 0 made, 5 failed.
    # Qualified → Proposal and Proposal → Won: 0 / 0. Pooled p = 17 / 34.
    zero_of_five = train(first_transition(made=12, failed=12) + at_engaged(0, 5), AS_OF)
    p = 17 / 34
    assert [t.smoothed_rate for t in zero_of_five.transitions[1:]] == pytest.approx(
        [2 * p / 7, p, p]
    )

    # 7 made, 3 failed; then 3 made, 4 failed. Pooled p = 10 / 17.
    leads = first_transition(made=0, failed=3) + at_engaged(made=3, failed=4)
    three_of_seven = train(leads, AS_OF)
    p = 10 / 17
    first, second = three_of_seven.transitions[:2]
    assert (first.made, first.failed, second.made, second.failed) == (7, 3, 3, 4)
    assert first.smoothed_rate == pytest.approx((7 + 2 * p) / 12)
    assert second.smoothed_rate == pytest.approx((3 + 2 * p) / 9)


def test_only_when_no_lead_finished_any_transition_is_a_chance_refused():
    model = train([lead(5.0, Stage.CONTACT_ATTEMPTED), lead(7.0)], AS_OF)

    assert [t.smoothed_rate for t in model.transitions] == [None] * 4
    with pytest.raises(Refused, match="No lead has made or failed any Transition yet"):
        model.chance_of_winning(lead(1.0))


def test_a_fitted_transition_gives_leads_like_those_that_made_it_a_higher_chance():
    model = train(first_transition(made=15, failed=15), AS_OF)

    first = model.transitions[0]
    assert first.regression is not None and first.regression.converged
    assert first.chance(model.features.row(lead(1200.0))) > 0.5
    assert first.chance(model.features.row(lead(15.0))) < 0.5


def test_a_fit_that_does_not_converge_is_recorded(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(model_module, "MAX_ITER", 1)

    first = train(first_transition(made=15, failed=15), AS_OF).transitions[0]

    assert first.regression is not None
    assert first.regression.converged is False


def test_a_leads_chance_of_winning_is_the_product_over_the_four_transitions():
    features = Features(
        numbers=(NumberInput(column="Budget", mean=0.0, sd=1.0, any_given=True),),
        categories=(),
    )

    def transition(i: int, rate: float, regression: Regression | None = None) -> TransitionModel:
        return TransitionModel(
            transition=TRANSITIONS[i],
            made=10,
            failed=10,
            unfinished=0,
            smoothed_rate=rate,
            regression=regression,
        )

    model = Model(
        as_of=AS_OF,
        features=features,
        transitions=(
            # A budget of 2, given, has log-odds 0: a chance of one half.
            transition(0, 0.9, Regression(intercept=-1.0, coefficients=(0.5, 3.0), converged=True)),
            transition(1, 0.8),
            transition(2, 0.5),
            transition(3, 0.25),
        ),
    )

    assert model.chance_of_winning(lead(2.0, trip="Safari")) == pytest.approx(
        0.5 * 0.8 * 0.5 * 0.25
    )


def test_the_model_is_kept_as_json_and_read_back_the_same():
    model = train(first_transition(made=12, failed=11) + won_leads(), AS_OF)

    again = Model.model_validate_json(model.model_dump_json())

    assert again == model
    assert again.chance_of_winning(lead(500.0)) == model.chance_of_winning(lead(500.0))


def test_nothing_after_as_of_changes_the_model():
    leads = first_transition(made=12, failed=12) + won_leads()
    after = AS_OF + timedelta(days=1)
    # Every open lead is won or lost after as_of, and a lead is submitted after it.
    later = [
        replace(open_lead, stage_events=(*open_lead.stage_events, StageEvent(outcome, after)))
        for open_lead, outcome in zip(leads, [Stage.WON, LOST] * len(leads), strict=False)
    ] + [lead(99.0, Stage.CONTACT_ATTEMPTED, LOST, trip="Cruise", submitted=after)]

    assert train(later, AS_OF) == train(leads, AS_OF)


def test_inputs_are_read_from_every_lead_submitted_as_of_the_time_not_only_finished_ones():
    unfinished = lead(None, Stage.CONTACT_ATTEMPTED, trip="Cruise")
    neglected = lead(70.0, trip="Wedding")
    model = train(first_transition(made=12, failed=12) + [unfinished, neglected], AS_OF)

    assert model.features.categories[0].values[1:] == ("Cruise", "Wedding")
    assert model.chance_of_winning(lead(None, trip="Cruise")) > 0
    assert model.chance_of_winning(lead(5.0, trip="Wedding")) > 0


def test_training_on_the_hand_made_dataset_fits_all_four_transitions():
    mapping = ConfirmedMapping(Mapping.model_validate(HAND_MADE_MAPPING), START)
    tables = [
        read_csv((HAND_MADE / name).read_bytes()) for name in ("leads.csv", "stage_history.csv")
    ]
    leads = format_files(*tables, mapping).leads

    model = train(leads, AS_OF.replace(year=2026))

    # The dataset was written with at least 12 made and 12 failed at each.
    assert [(t.made >= 12, t.failed >= 12) for t in model.transitions] == [(True, True)] * 4
    assert all(t.regression is not None and t.regression.converged for t in model.transitions)
