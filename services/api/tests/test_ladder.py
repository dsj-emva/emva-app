from datetime import UTC, datetime

import pytest

from emva_api.ladder import (
    LADDER,
    LOST,
    STAGES_AND_LOST,
    Lost,
    Progress,
    Stage,
    StageEvent,
    Won,
    name_of,
    progress,
)


def test_the_canonical_ladder_runs_from_submitted_to_won_in_order():
    assert [name_of(stage) for stage in LADDER] == [
        "Submitted",
        "Contact attempted",
        "Engaged",
        "Qualified",
        "Proposal",
        "Won",
    ]
    assert LADDER[0] is Stage.SUBMITTED
    assert LADDER[-1] is Stage.WON


def test_lost_is_not_a_stage_on_the_ladder():
    assert LOST not in LADDER
    assert name_of(LOST) == "Lost"


def test_a_crm_stage_can_be_placed_on_any_stage_or_on_lost():
    assert [name_of(stage_or_lost) for stage_or_lost in STAGES_AND_LOST] == [
        "Submitted",
        "Contact attempted",
        "Engaged",
        "Qualified",
        "Proposal",
        "Won",
        "Lost",
    ]


# A lead's progress up the ladder, from its stage events.


def at(day: int, hour: int = 9) -> datetime:
    return datetime(2024, 3, day, hour, tzinfo=UTC)


def test_a_lead_with_no_stage_events_is_submitted_with_no_outcome_yet():
    assert progress([]) == Progress(Stage.SUBMITTED, lost_after=None, outcome=None)


def test_a_lead_that_reached_a_stage_and_stopped_has_no_outcome_yet_and_is_never_lost():
    lead = progress([StageEvent(Stage.SUBMITTED, at(1)), StageEvent(Stage.ENGAGED, at(3))])

    assert lead == Progress(Stage.ENGAGED, lost_after=None, outcome=None)


def test_reaching_a_later_stage_counts_as_reaching_every_stage_before_it():
    lead = progress([StageEvent(Stage.PROPOSAL, at(4))])

    assert lead.furthest is Stage.PROPOSAL
    assert lead.reached(Stage.CONTACT_ATTEMPTED)
    assert lead.reached(Stage.QUALIFIED)
    assert lead.reached(Stage.PROPOSAL)
    assert not lead.reached(Stage.WON)


def test_several_events_on_one_stage_count_once():
    lead = progress(
        [
            StageEvent(Stage.CONTACT_ATTEMPTED, at(1)),
            StageEvent(Stage.CONTACT_ATTEMPTED, at(2)),
            StageEvent(Stage.CONTACT_ATTEMPTED, at(3)),
        ]
    )

    assert lead == Progress(Stage.CONTACT_ATTEMPTED, lost_after=None, outcome=None)


def test_a_won_lead_keeps_when_it_was_won_and_its_deal_value():
    lead = progress(
        [
            StageEvent(Stage.SUBMITTED, at(1)),
            StageEvent(Stage.PROPOSAL, at(5)),
            StageEvent(Stage.WON, at(9, 15), deal_value=18250.0),
        ]
    )

    assert lead == Progress(
        Stage.WON, lost_after=None, outcome=Won(at=at(9, 15), deal_value=18250.0)
    )


def test_a_won_lead_may_have_no_deal_value():
    assert progress([StageEvent(Stage.WON, at(9))]).outcome == Won(at=at(9), deal_value=None)


@pytest.mark.parametrize("stage", [stage for stage in LADDER if stage is not Stage.WON])
def test_a_lead_lost_after_any_stage_is_lost_after_the_furthest_stage_it_reached(stage: Stage):
    lead = progress([StageEvent(stage, at(2)), StageEvent(LOST, at(6))])

    assert lead == Progress(stage, lost_after=stage, outcome=Lost(at=at(6)))


def test_a_lead_lost_before_any_contact_attempt_is_lost_and_neglected():
    lead = progress([StageEvent(Stage.SUBMITTED, at(1)), StageEvent(LOST, at(2))])

    assert lead == Progress(Stage.SUBMITTED, lost_after=Stage.SUBMITTED, outcome=Lost(at=at(2)))
    assert lead.neglected


@pytest.mark.parametrize(
    ("events", "neglected"),
    [
        ([], True),
        ([StageEvent(Stage.SUBMITTED, at(1))], True),
        ([StageEvent(Stage.CONTACT_ATTEMPTED, at(2))], False),
        ([StageEvent(Stage.QUALIFIED, at(2)), StageEvent(LOST, at(3))], False),
    ],
)
def test_a_lead_never_attempted_is_neglected(events: list[StageEvent], neglected: bool):
    assert progress(events).neglected is neglected


def test_stage_events_out_of_time_order_are_read_in_time_order():
    in_order = [
        StageEvent(Stage.SUBMITTED, at(1)),
        StageEvent(Stage.QUALIFIED, at(3)),
        StageEvent(LOST, at(8)),
    ]

    assert progress(list(reversed(in_order))) == progress(in_order)
    assert progress(in_order).lost_after is Stage.QUALIFIED


def test_a_lead_reopened_after_it_was_lost_is_decided_by_its_latest_event():
    reopened = progress(
        [
            StageEvent(LOST, at(4)),
            StageEvent(Stage.ENGAGED, at(2)),
            StageEvent(Stage.QUALIFIED, at(7)),
        ]
    )

    assert reopened == Progress(Stage.QUALIFIED, lost_after=None, outcome=None)


def test_a_lead_lost_again_after_it_was_reopened_is_lost_after_its_furthest_stage():
    lead = progress(
        [
            StageEvent(Stage.ENGAGED, at(2)),
            StageEvent(LOST, at(4)),
            StageEvent(Stage.PROPOSAL, at(7)),
            StageEvent(LOST, at(9)),
        ]
    )

    assert lead == Progress(Stage.PROPOSAL, lost_after=Stage.PROPOSAL, outcome=Lost(at=at(9)))


def test_lost_at_the_same_moment_as_a_stage_is_read_as_after_it():
    lead = progress([StageEvent(LOST, at(4)), StageEvent(Stage.ENGAGED, at(4))])

    assert lead == Progress(Stage.ENGAGED, lost_after=Stage.ENGAGED, outcome=Lost(at=at(4)))


def test_won_is_final_even_when_lost_is_recorded_after_it():
    lead = progress([StageEvent(Stage.WON, at(5), deal_value=9000.0), StageEvent(LOST, at(8))])

    assert lead == Progress(Stage.WON, lost_after=None, outcome=Won(at=at(5), deal_value=9000.0))


def test_a_lead_won_twice_was_won_when_first_won():
    lead = progress(
        [
            StageEvent(Stage.WON, at(9), deal_value=7000.0),
            StageEvent(Stage.WON, at(5), deal_value=6500.0),
        ]
    )

    assert lead.outcome == Won(at=at(5), deal_value=6500.0)
