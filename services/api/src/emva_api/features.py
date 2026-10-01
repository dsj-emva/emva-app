"""Features: a lead's inputs as the model reads them. The same code serves training, the
Backtest and scoring, and its fitted parameters are kept with the model. Pure: no I/O.

- A number is standardised with the training leads' mean and standard deviation; a number the
  same for every training lead is only centred.
- A number missing in training stands at the training mean, and a flag input after it says it
  is missing, so the model learns what a missing number means. A number missing at scoring is
  refused when no training lead lacked it, since the model never learned what that means.
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
    # Whether a training lead lacked it, and so whether a flag input says it is missing.
    missing_seen: bool


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

    def row(self, lead: FormattedLead) -> list[float]:
        """The lead's inputs as the model reads them; Refused when it cannot read them."""
        row: list[float] = []
        for number in self.numbers:
            value = lead.numbers.get(number.column)
            if value is None and not number.missing_seen:
                raise Refused(f"“{number.column}” is missing, and no training lead lacked it.")
            row.append(0.0 if value is None else (value - number.mean) / number.sd)
            if number.missing_seen:
                row.append(1.0 if value is None else 0.0)
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
    """The parameters fitted on the training leads; the inputs are those of the first lead."""
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
                missing_seen=len(given) < len(leads),
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
