"""The Canonical ladder: the fixed, ordered Stages every advertiser's sales process is expressed on.

Lost is not a Stage: it can follow any Stage. A CRM stage is placed on one Stage or on Lost.
Pure: no I/O.
"""

import enum
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal


class Stage(enum.StrEnum):
    """A Stage of the Canonical ladder; members are in ladder order."""

    SUBMITTED = "submitted"
    CONTACT_ATTEMPTED = "contact_attempted"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    WON = "won"


LOST: Final = "lost"

LADDER: tuple[Stage, ...] = tuple(Stage)

type StageOrLost = Stage | Literal["lost"]

# What a CRM stage can be placed on, in the order a person is offered them.
STAGES_AND_LOST: tuple[StageOrLost, ...] = (*LADDER, LOST)

_NAMES: dict[StageOrLost, str] = {
    Stage.SUBMITTED: "Submitted",
    Stage.CONTACT_ATTEMPTED: "Contact attempted",
    Stage.ENGAGED: "Engaged",
    Stage.QUALIFIED: "Qualified",
    Stage.PROPOSAL: "Proposal",
    Stage.WON: "Won",
    LOST: "Lost",
}


def name_of(stage_or_lost: StageOrLost) -> str:
    return _NAMES[stage_or_lost]


@dataclass(frozen=True)
class StageEvent:
    """A lead reaching a Stage, or being lost, at a time; a Deal value when the CRM records one."""

    stage: StageOrLost
    at: datetime
    deal_value: float | None = None


@dataclass(frozen=True)
class Won:
    at: datetime
    deal_value: float | None


@dataclass(frozen=True)
class Lost:
    at: datetime


@dataclass(frozen=True)
class Unfinished:
    """Neither won nor lost (yet); never counted as lost."""


UNFINISHED: Final = Unfinished()

type Outcome = Won | Lost | Unfinished


@dataclass(frozen=True)
class Progress:
    furthest: Stage
    lost_after: Stage | None
    outcome: Outcome

    def reached(self, stage: Stage) -> bool:
        """Reaching a Stage counts as reaching every Stage before it."""
        return LADDER.index(stage) <= LADDER.index(self.furthest)


def progress(events: Iterable[StageEvent]) -> Progress:
    """How far a lead got and how it ended, from its stage events in any order.

    Every lead is at least Submitted. Won is final: the lead was won when first won, with that
    event's Deal value. Otherwise the latest event decides: a lead whose latest event is Lost was
    lost after the furthest Stage it reached; a later Stage reopens a lost lead. Lost recorded at
    the same moment as a Stage is read as after it.
    """
    in_time_order = sorted(events, key=lambda event: (event.at, event.stage == LOST))
    furthest = max(
        (LADDER.index(event.stage) for event in in_time_order if event.stage != LOST), default=0
    )
    first_won = next((event for event in in_time_order if event.stage is Stage.WON), None)
    if first_won is not None:
        return Progress(Stage.WON, None, Won(at=first_won.at, deal_value=first_won.deal_value))
    if in_time_order and in_time_order[-1].stage == LOST:
        return Progress(LADDER[furthest], LADDER[furthest], Lost(at=in_time_order[-1].at))
    return Progress(LADDER[furthest], None, UNFINISHED)
