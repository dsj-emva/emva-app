"""Features: a lead's inputs as the model reads them. The same code serves training, the
Backtest and scoring, and its fitted parameters are kept with the model. Pure: no I/O.

- A number is standardised with the training leads' mean and standard deviation; a number the
  same for every training lead is only centred.
- A missing number stands at the training mean, and a flag input after every number says
  whether it is missing, so the model learns what a missing number means (ruling 12 of the
  phase 1 PRD). Where no training lead lacked it, the flag's weight stays near zero under the
  regularisation, so a missing number is still scored.
- A category is one-hot over the values the training leads had, most common first; a missing
  category is a value of its own. A value no training lead had is refused.
"""

import statistics
from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from emva_api.formatter import FormattedLead


class Refused(Exception):
    """The lead cannot be read by the model; the message says why."""


class NumberInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    column: str
    mean: float
    sd: float
    # False when no training lead gave it, so its mean stands for nothing.
    any_given: bool


class CategoryInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    column: str
    # The training values, most common first; None is a missing value.
    values: tuple[str | None, ...]


class Features(BaseModel):
    """The fitted parameters, in the order a lead's row lists its inputs."""

    model_config = ConfigDict(frozen=True)

    numbers: tuple[NumberInput, ...]
    categories: tuple[CategoryInput, ...]

    def typical(self) -> tuple[dict[str, float | None], dict[str, str | None]]:
        """The typical lead's inputs: every number at its training mean, given (not given when
        no training lead gave it), and every category at its most common training value."""
        return (
            {number.column: number.mean if number.any_given else None for number in self.numbers},
            {category.column: category.values[0] for category in self.categories},
        )

    def row(self, lead: FormattedLead) -> list[float]:
        """The lead's inputs as the model reads them; Refused when it cannot read them."""
        row: list[float] = []
        for number in self.numbers:
            value = lead.numbers.get(number.column)
            if value is None:
                row += [0.0, 1.0]
            else:
                row += [(value - number.mean) / number.sd, 0.0]
        for category in self.categories:
            value = lead.categories.get(category.column)
            if value not in category.values:
                raise Refused(
                    f"“{category.column}” is missing, and no training lead lacked it."
                    if value is None
                    else f"“{category.column}” is “{value}”, which no training lead had."
                )
            row += [1.0 if value == seen else 0.0 for seen in category.values]
        return row


def fit_features(leads: Sequence[FormattedLead]) -> Features:
    """The parameters fitted on the leads given; the inputs are those of the first lead."""
    first = leads[0] if leads else None
    numbers = []
    for column in first.numbers if first else ():
        given = [v for lead in leads if (v := lead.numbers.get(column)) is not None]
        sd = statistics.pstdev(given) if given else 0.0
        numbers.append(
            NumberInput(
                column=column,
                mean=statistics.fmean(given) if given else 0.0,
                sd=sd or 1.0,
                any_given=bool(given),
            )
        )
    categories = [
        CategoryInput(
            column=column,
            values=tuple(
                value
                for value, _ in Counter(lead.categories.get(column) for lead in leads).most_common()
            ),
        )
        for column in (first.categories if first else ())
    ]
    return Features(numbers=tuple(numbers), categories=tuple(categories))
