"""The Canonical ladder: the fixed, ordered Stages every advertiser's sales process is expressed on.

Lost is not a Stage: it can follow any Stage. A CRM stage is placed on one Stage or on Lost.
Pure: no I/O.
"""

import enum
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
