"""The Canonical ladder: the fixed, ordered Stages every advertiser's sales process is expressed on.

Lost is not a Stage: it can follow any Stage. A CRM stage is placed on one Stage or on Lost.
Pure: no I/O.
"""

import enum


class Stage(enum.StrEnum):
    """A Stage of the Canonical ladder; members are in ladder order."""

    SUBMITTED = "submitted"
    CONTACT_ATTEMPTED = "contact_attempted"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    WON = "won"


class Lost(enum.StrEnum):
    LOST = "lost"


LOST = Lost.LOST

LADDER: tuple[Stage, ...] = tuple(Stage)

type Place = Stage | Lost

# Every place a CRM stage can be put, in the order a person is offered them.
PLACES: tuple[Place, ...] = (*LADDER, LOST)

_NAMES: dict[Place, str] = {
    Stage.SUBMITTED: "Submitted",
    Stage.CONTACT_ATTEMPTED: "Contact attempted",
    Stage.ENGAGED: "Engaged",
    Stage.QUALIFIED: "Qualified",
    Stage.PROPOSAL: "Proposal",
    Stage.WON: "Won",
    LOST: "Lost",
}


def place_name(place: Place) -> str:
    return _NAMES[place]
