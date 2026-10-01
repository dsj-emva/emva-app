"""Scoring one lead: its Submit score and its Score explanation. Pure: no I/O.

The chance of winning is the model's: the product of the lead's chances on the four Transitions
from Contact attempted to Won (decision 0002, ruling 2 of the phase 1 PRD), a Transition too few
to learn giving its smoothed rate (ruling 13). The Lead score is that chance times the
advertiser's Typical deal size (decision 0003, ruling 1); the lead states no size of its own yet.

The Score explanation starts at the typical lead (every number at its training mean, given, or
not given when no training lead gave it; every category at its most common training value) and
its chance, then changes one input at a time, in
the Mapping's order, from the typical value to this lead's, recording how far each moves the
chance up or down. Each step starts where the last ended and the last ends at this lead's chance,
so the steps add up to it. A number not given is its own step, moved by its learned missing flag.
"""

from collections.abc import Mapping
from dataclasses import replace

from pydantic import BaseModel, Field, computed_field

from emva_api.features import Refused
from emva_api.formatter import FormattedLead
from emva_api.mapping import ColumnKind
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
    model: Model,
    lead: FormattedLead,
    inputs: Mapping[str, ColumnKind],
    typical_deal_size: float,
) -> Score:
    """The lead's Submit score and Score explanation, its inputs walked in the Mapping's order
    and read as the kinds it gives them; Refused when the model cannot score it."""
    numbers, categories = model.features.typical()
    _check_inputs(inputs, numbers, categories)
    chance = model.chance_of_winning(lead)
    current = replace(lead, numbers=numbers, categories=categories)
    typical_chance = before = model.chance_of_winning(current)
    steps = []
    for column, kind in inputs.items():
        if kind is ColumnKind.NUMBER:
            typical, value = numbers[column], lead.numbers.get(column)
            current = replace(current, numbers={**current.numbers, column: value})
        else:
            typical, value = categories[column], lead.categories.get(column)
            current = replace(current, categories={**current.categories, column: value})
        # The inputs are exactly the model's, so once the last has changed the walk is at this
        # lead, and the last step ends at its chance.
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
    return Score(
        chance_of_winning=chance,
        typical_deal_size=typical_deal_size,
        lead_score=chance * typical_deal_size,
        explanation=Explanation(typical_chance=typical_chance, steps=steps),
    )


def _check_inputs(
    inputs: Mapping[str, ColumnKind],
    numbers: Mapping[str, object],
    categories: Mapping[str, object],
) -> None:
    """The Mapping's inputs are exactly the model's, each of the same kind."""
    learned = {column: ColumnKind.NUMBER for column in numbers} | {
        column: ColumnKind.CATEGORY for column in categories
    }
    for column, kind in inputs.items():
        if learned.get(column) is not kind:
            raise Refused(
                f"“{column}” is not an input the latest Training run learned from as a {kind}. "
                "Train again."
            )
    for column in learned:
        if column not in inputs:
            raise Refused(
                f"“{column}” is an input of the latest Training run but not of the Mapping. "
                "Train again."
            )


def value_text(value: float | str | None) -> str:
    if value is None:
        return NOT_GIVEN
    if isinstance(value, str):
        return value
    return f"{value:,.2f}".rstrip("0").rstrip(".")
