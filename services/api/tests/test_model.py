"""The stage-by-stage model: one regularised logistic regression per Transition from Contact
attempted, learned only from at least 10 leads that made it and 10 that failed it; otherwise
"too few to learn" with its observed rate. A lead's chance of winning is the product over the
Transitions ahead of it."""

from datetime import UTC, datetime, timedelta

import pytest
from test_hand_made_upload import HAND_MADE, HAND_MADE_MAPPING

from emva_api.csv_file import read_csv
from emva_api.features import Features, NumberInput, Refused
from emva_api.formatter import FormattedLead, format_files
from emva_api.ladder import LOST, Stage, StageEvent, StageOrLost
from emva_api.mapping import ConfirmedMapping, Mapping
from emva_api.model import MIN_EACH, Learned, Model, TransitionModel, train
from emva_api.transitions import LEARNED

AS_OF = datetime(2025, 1, 1, tzinfo=UTC)
START = datetime(2024, 3, 1, tzinfo=UTC)


def lead(budget: float, *path: StageOrLost) -> FormattedLead:
    return FormattedLead(
        identifier_hash=f"{budget} {path}",
        submitted_at=START,
        email_hash=None,
        phone_hash=None,
        phone_country_found=None,
        numbers={"Budget": budget},
        categories={},
        stage_events=tuple(
            StageEvent(stage, START + timedelta(days=day)) for day, stage in enumerate(path, 1)
        ),
    )


def first_transition(made: int, failed: int) -> list[FormattedLead]:
    """Leads at the first learned Transition: bigger budgets made it."""
    return [lead(1000.0 + i, Stage.CONTACT_ATTEMPTED, Stage.ENGAGED) for i in range(made)] + [
        lead(10.0 + i, Stage.CONTACT_ATTEMPTED, LOST) for i in range(failed)
    ]


def won_leads() -> list[FormattedLead]:
    path = (Stage.CONTACT_ATTEMPTED, Stage.ENGAGED, Stage.QUALIFIED, Stage.PROPOSAL, Stage.WON)
    return [lead(2000.0, *path), lead(2000.0, *path[:2], LOST), lead(2000.0, *path[:3], LOST)]


def test_a_transition_needs_ten_leads_that_made_it_and_ten_that_failed_it_to_be_learned():
    assert MIN_EACH == 10

    learned = train(first_transition(made=10, failed=10), AS_OF).transitions[0]
    too_few_failed = train(first_transition(made=10, failed=9), AS_OF).transitions[0]
    too_few_made = train(first_transition(made=9, failed=12), AS_OF).transitions[0]

    assert learned.learned is not None
    assert (too_few_failed.learned, too_few_failed.observed_rate) == (None, 10 / 19)
    assert (too_few_made.learned, too_few_made.observed_rate) == (None, 9 / 21)


def test_each_transition_counts_the_leads_that_made_failed_or_are_unfinished_there():
    leads = [*first_transition(made=3, failed=2), lead(5.0, Stage.CONTACT_ATTEMPTED)]

    model = train(leads, AS_OF)

    first, second = model.transitions[:2]
    assert (first.made, first.failed, first.unfinished) == (3, 2, 1)
    assert (second.made, second.failed, second.unfinished) == (0, 0, 3)


def test_a_transition_too_few_to_learn_gives_every_lead_its_observed_rate():
    model = train(first_transition(made=3, failed=1), AS_OF)

    assert model.transitions[0].chance(model.features.row(lead(1.0))) == 0.75
    assert model.transitions[0].chance(model.features.row(lead(5000.0))) == 0.75


def test_a_transition_no_lead_has_made_or_failed_has_no_rate_and_refuses_a_chance():
    model = train(first_transition(made=3, failed=1), AS_OF)
    engaged = model.transitions[1]

    assert (engaged.made, engaged.failed, engaged.observed_rate) == (0, 0, None)
    with pytest.raises(Refused, match="No lead has made or failed Engaged → Qualified yet"):
        model.chance_of_winning(lead(1.0))


def test_a_learned_transition_gives_leads_like_those_that_made_it_a_higher_chance():
    model = train(first_transition(made=15, failed=15), AS_OF)

    first = model.transitions[0]
    assert first.chance(model.features.row(lead(1200.0))) > 0.5
    assert first.chance(model.features.row(lead(15.0))) < 0.5


def test_a_leads_chance_of_winning_is_the_product_over_the_four_transitions():
    features = Features(
        numbers=(NumberInput(column="Budget", mean=0.0, sd=1.0, missing_seen=False),),
        categories=(),
    )

    def rate(transition, observed: float) -> TransitionModel:
        return TransitionModel(
            from_stage=transition.from_stage,
            to_stage=transition.to_stage,
            made=1,
            failed=1,
            unfinished=0,
            observed_rate=observed,
            learned=None,
        )

    first = LEARNED[0]
    model = Model(
        as_of=AS_OF,
        features=features,
        transitions=(
            TransitionModel(
                from_stage=first.from_stage,
                to_stage=first.to_stage,
                made=10,
                failed=10,
                unfinished=0,
                observed_rate=0.5,
                # A budget of 2 gives log-odds 0, so a chance of one half.
                learned=Learned(intercept=-1.0, coefficients=(0.5,)),
            ),
            rate(LEARNED[1], 0.8),
            rate(LEARNED[2], 0.5),
            rate(LEARNED[3], 0.25),
        ),
    )

    assert model.chance_of_winning(lead(2.0)) == pytest.approx(0.5 * 0.8 * 0.5 * 0.25)


def test_the_model_is_kept_as_json_and_read_back_the_same():
    model = train(first_transition(made=12, failed=11) + won_leads(), AS_OF)

    again = Model.model_validate_json(model.model_dump_json())

    assert again == model
    assert again.transitions[0].chance(again.features.row(lead(500.0))) == model.transitions[
        0
    ].chance(model.features.row(lead(500.0)))


def test_only_leads_and_stage_events_as_of_the_time_are_learned_from():
    leads = first_transition(made=3, failed=1)

    before_any_contact = train(leads, START)

    assert [t.made + t.failed + t.unfinished for t in before_any_contact.transitions] == [0] * 4
    assert before_any_contact.as_of == START


def test_training_on_the_hand_made_dataset_learns_all_four_transitions():
    mapping = ConfirmedMapping(Mapping.model_validate(HAND_MADE_MAPPING), START)
    tables = [
        read_csv((HAND_MADE / name).read_bytes()) for name in ("leads.csv", "stage_history.csv")
    ]
    leads = format_files(*tables, mapping).leads

    model = train(leads, AS_OF.replace(year=2026))

    # The dataset was written with at least 12 made and 12 failed at each.
    assert [(t.made >= 12, t.failed >= 12) for t in model.transitions] == [(True, True)] * 4
    assert all(t.learned is not None for t in model.transitions)
