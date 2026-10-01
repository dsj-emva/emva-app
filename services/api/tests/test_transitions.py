"""The Transitions dataset: for each Transition from Contact attempted onwards, the leads that
faced it, and whether each made it, failed it or is unfinished there, as of a time."""

from datetime import UTC, datetime

from emva_api.formatter import FormattedLead
from emva_api.ladder import LOST, Stage, StageEvent, StageOrLost
from emva_api.transitions import TRANSITIONS, Faced, Transition, transitions_dataset

AS_OF = datetime(2024, 6, 1, tzinfo=UTC)


def at(day: int) -> datetime:
    return datetime(2024, 3, day, 9, tzinfo=UTC)


def lead(name: str, *path: StageOrLost, submitted: datetime | None = None) -> FormattedLead:
    """A lead whose stage events follow the path, one a day from the 2nd of March."""
    return FormattedLead(
        identifier_hash=name,
        submitted_at=submitted or at(1),
        email_hash=None,
        phone_hash=None,
        phone_country_found=None,
        numbers={},
        categories={},
        stage_events=tuple(StageEvent(stage, at(day)) for day, stage in enumerate(path, start=2)),
    )


def faced(leads: list[FormattedLead], as_of: datetime = AS_OF) -> dict[str, list[tuple]]:
    """Each Transition by name, with each lead that faced it by name and how."""
    return {
        transition.name: [(lead.identifier_hash, how) for lead, how in facing]
        for transition, facing in transitions_dataset(leads, as_of).items()
    }


CONTACT, ENGAGED, QUALIFIED, PROPOSAL = (
    "Contact attempted → Engaged",
    "Engaged → Qualified",
    "Qualified → Proposal",
    "Proposal → Won",
)


def test_the_transitions_modelled_run_from_contact_attempted_to_won():
    assert [transition.name for transition in TRANSITIONS] == [
        "Contact attempted → Engaged",
        "Engaged → Qualified",
        "Qualified → Proposal",
        "Proposal → Won",
    ]
    assert TRANSITIONS[0] == Transition(from_stage=Stage.CONTACT_ATTEMPTED, to_stage=Stage.ENGAGED)


def test_a_won_lead_made_every_transition():
    path = (Stage.CONTACT_ATTEMPTED, Stage.ENGAGED, Stage.QUALIFIED, Stage.PROPOSAL, Stage.WON)
    dataset = faced([lead("a", *path)])

    assert dataset == {name: [("a", Faced.MADE)] for name in dataset}


def test_skipped_stages_count_as_made():
    dataset = faced([lead("a", Stage.CONTACT_ATTEMPTED, Stage.PROPOSAL)])

    assert dataset == {
        CONTACT: [("a", Faced.MADE)],
        ENGAGED: [("a", Faced.MADE)],
        QUALIFIED: [("a", Faced.MADE)],
        PROPOSAL: [("a", Faced.UNFINISHED)],
    }


def test_lost_counts_as_failed_at_the_next_transition_only():
    dataset = faced([lead("a", Stage.CONTACT_ATTEMPTED, Stage.ENGAGED, LOST)])

    assert dataset == {
        CONTACT: [("a", Faced.MADE)],
        ENGAGED: [("a", Faced.FAILED)],
        QUALIFIED: [],
        PROPOSAL: [],
    }


def test_a_lead_with_no_outcome_yet_is_unfinished_at_the_transition_it_stands_before():
    dataset = faced([lead("a", Stage.CONTACT_ATTEMPTED)])

    assert dataset == {CONTACT: [("a", Faced.UNFINISHED)], ENGAGED: [], QUALIFIED: [], PROPOSAL: []}


def test_neglected_leads_are_left_out_entirely_even_when_lost_before_any_contact():
    dataset = faced(
        [
            lead("never touched"),
            lead("only submitted", Stage.SUBMITTED),
            lead("lost before contact", Stage.SUBMITTED, LOST),
        ]
    )

    assert dataset == {CONTACT: [], ENGAGED: [], QUALIFIED: [], PROPOSAL: []}


def test_stage_events_after_as_of_are_ignored():
    # Contact attempted on the 2nd, Engaged on the 3rd, lost on the 4th.
    a = lead("a", Stage.CONTACT_ATTEMPTED, Stage.ENGAGED, LOST)

    assert faced([a], as_of=at(2))[CONTACT] == [("a", Faced.UNFINISHED)]
    assert faced([a], as_of=at(3))[ENGAGED] == [("a", Faced.UNFINISHED)]
    assert faced([a], as_of=at(4))[ENGAGED] == [("a", Faced.FAILED)]


def test_a_lead_not_contacted_by_as_of_is_neglected_then_and_left_out():
    a = lead("a", Stage.CONTACT_ATTEMPTED, Stage.ENGAGED)

    assert faced([a], as_of=at(1))[CONTACT] == []


def test_leads_submitted_after_as_of_are_left_out():
    a = lead("a", Stage.CONTACT_ATTEMPTED, submitted=at(1))
    later = lead("later", Stage.CONTACT_ATTEMPTED, submitted=at(5))

    assert faced([a, later], as_of=at(3))[CONTACT] == [("a", Faced.UNFINISHED)]
    assert [name for name, _ in faced([a, later], as_of=at(5))[CONTACT]] == ["a", "later"]
