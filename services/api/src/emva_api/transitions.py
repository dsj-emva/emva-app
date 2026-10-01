"""The Transitions dataset: for each Transition the model learns, the leads that faced it and how
each fared, as of a time. Pure: no I/O.

Only the Transitions from Contact attempted onwards are learned (decision 0002, ruling 2 of the
phase 1 PRD): whether a lead is attempted is the advertiser's behaviour, so Neglected leads,
including those lost before any Contact attempt, are left out entirely. A lead's progress comes
from the Canonical ladder (`ladder.progress`) on its stage events up to the time; reaching a
later Stage counts as making every Transition before it, and a lead lost after a Stage failed
the Transition from that Stage only.
"""

import enum
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from emva_api.formatter import FormattedLead
from emva_api.ladder import LADDER, Stage, name_of, progress


@dataclass(frozen=True)
class Transition:
    """A lead moving from one Stage to the next."""

    from_stage: Stage
    to_stage: Stage

    @property
    def name(self) -> str:
        return f"{name_of(self.from_stage)} → {name_of(self.to_stage)}"


# The Transitions learned, in ladder order: from Contact attempted to Won.
LEARNED: tuple[Transition, ...] = tuple(
    Transition(LADDER[i], LADDER[i + 1])
    for i in range(LADDER.index(Stage.CONTACT_ATTEMPTED), len(LADDER) - 1)
)


class Faced(enum.StrEnum):
    """How a lead that faced a Transition fared at it."""

    MADE = "made"
    FAILED = "failed"
    # Neither made nor failed yet: left out of that Transition's learning.
    UNFINISHED = "unfinished"


type Dataset = dict[Transition, list[tuple[FormattedLead, Faced]]]


def transitions_dataset(leads: Iterable[FormattedLead], as_of: datetime) -> Dataset:
    """Each learned Transition with every lead that faced it as of the time, in the order given.

    Only leads submitted at or before the time, and only their stage events at or before it,
    count. A lead faces the Transitions in turn up to the first it did not make."""
    dataset: Dataset = {transition: [] for transition in LEARNED}
    for lead in leads:
        if lead.submitted_at > as_of:
            continue
        reached = progress(event for event in lead.stage_events if event.at <= as_of)
        if reached.neglected:
            continue
        for transition in LEARNED:
            if not reached.reached(transition.from_stage):
                break
            if reached.reached(transition.to_stage):
                fared = Faced.MADE
            elif reached.lost_after is transition.from_stage:
                fared = Faced.FAILED
            else:
                fared = Faced.UNFINISHED
            dataset[transition].append((lead, fared))
            if fared is not Faced.MADE:
                break
    return dataset
