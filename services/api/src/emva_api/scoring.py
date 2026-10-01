"""Scoring one lead: its Submit score and its Score explanation. Pure: no I/O.

The chance of winning is the model's: the product of the lead's chances on the four Transitions
from Contact attempted to Won (decision 0002, ruling 2 of the phase 1 PRD), a Transition too few
to learn giving its smoothed rate (ruling 13). The Lead score is that chance times the
advertiser's Typical deal size (decision 0003, ruling 1); the lead states no size of its own yet.

The Score explanation starts at the typical lead (every number at its training mean, given; every
category at its most common training value) and its chance, then changes one input at a time, in
the Mapping's order, from the typical value to this lead's, recording how far each moves the
chance up or down. Each step starts where the last ended and the last ends at this lead's chance,
so the steps add up to it. A number not given is its own step, moved by its learned missing flag.
"""

from collections.abc import Sequence
from dataclasses import replace

from pydantic import BaseModel, Field, computed_field

from emva_api.formatter import FormattedLead
from emva_api.model import Model

NOT_GIVEN = "not given"


class Step(BaseModel):
    input: str = Field(description="The input's name, as the Mapping has it")
    typical: str = Field(description="The typical lead's value")
    value: str = Field(description="This lead's value; “not given” when it was left blank")
    before: float = Field(description="The chance of winning before this input changed")
    after: float = Field(description="The chance of winning once it changed to this lead's")

    @computed_field(description="How far this input moved the chance: up when above zero")
    @property
    def change(self) -> float:
        return self.after - self.before


class Explanation(BaseModel):
    typical_chance: float = Field(description="The typical lead's chance of winning")
    steps: list[Step] = Field(description="One per input, in the Mapping's order")


class Score(BaseModel):
    chance_of_winning: float
    typical_deal_size: float = Field(description="The size the Lead score used")
    lead_score: float = Field(description="The chance of winning times the deal size; not money")
    explanation: Explanation


def score(
    model: Model, lead: FormattedLead, order: Sequence[str], typical_deal_size: float
) -> Score:
    """The lead's Submit score and Score explanation, its inputs walked in the order given;
    Refused when the model cannot score it."""
    chance = model.chance_of_winning(lead)
    numbers, categories = model.features.typical()
    current = replace(lead, numbers=numbers, categories=categories)
    typical_chance = before = model.chance_of_winning(current)
    steps = []
    for column in order:
        if column in numbers:
            typical, value = numbers[column], lead.numbers[column]
            current = replace(current, numbers={**current.numbers, column: value})
        else:
            typical, value = categories[column], lead.categories[column]
            current = replace(current, categories={**current.categories, column: value})
        after = model.chance_of_winning(current)
        steps.append(
            Step(
                input=column,
                typical=value_text(typical),
                value=value_text(value),
                before=before,
                after=after,
            )
        )
        before = after
    assert current.numbers == lead.numbers and current.categories == lead.categories
    return Score(
        chance_of_winning=chance,
        typical_deal_size=typical_deal_size,
        lead_score=chance * typical_deal_size,
        explanation=Explanation(typical_chance=typical_chance, steps=steps),
    )


def value_text(value: float | str | None) -> str:
    if value is None:
        return NOT_GIVEN
    if isinstance(value, str):
        return value
    return f"{value:,.2f}".rstrip("0").rstrip(".")
