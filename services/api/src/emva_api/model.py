"""The stage-by-stage model (decision 0002) with the simple model only (decision 0009): for each
Transition from Contact attempted to Won, a regularised logistic regression on the lead's
Features. A lead's chance of winning is the product of its chances on the Transitions ahead of
it; for a Submit score, all of them.

A Transition's regression is fitted only on at least MIN_EACH leads that made it and MIN_EACH
that failed it (ruling 8 of the phase 1 PRD). Otherwise it is too few to learn, and every lead
gets its smoothed rate, (made + 2·p) / (made + failed + 2), where p is the pooled rate of made
over made-plus-failed across all the Transitions of the same Training run (ruling 13). Only
when no lead has made or failed any Transition is a chance refused.

The Features are fitted on every lead submitted as of the time, finished or not, so an input
value seen only on an unfinished or Neglected lead is still read when scoring.

The model is plain data (coefficients, intercepts, the Features' parameters, the counts and
rates), kept as JSON and read back without scikit-learn. Pure: no I/O.
"""

import math
import warnings
from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from emva_api.features import Features, Refused, fit_features
from emva_api.formatter import FormattedLead
from emva_api.transitions import Faced, Transition, transitions_dataset

MIN_EACH = 10
# The L2 penalty's inverse strength, fixed in advance and never tuned on results: scikit-learn's
# default, a moderate pull towards zero on standardised inputs.
C = 1.0
# Far more iterations than a fit on standardised inputs needs; a fit that still stops short is
# recorded as not converged.
MAX_ITER = 10_000

RULE = (
    f"A transition's model is learned only from at least {MIN_EACH} leads that made it and "
    f"{MIN_EACH} that failed it. With fewer it is too few to learn, and every lead gets its "
    "smoothed rate: its own rate pulled towards the rate across all four transitions."
)


class Regression(BaseModel):
    """A fitted logistic regression."""

    model_config = ConfigDict(frozen=True)

    intercept: float
    # One per input of the Features' row, in its order.
    coefficients: tuple[float, ...]
    # False when the fit stopped at MAX_ITER before it converged.
    converged: bool


class TransitionModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    transition: Transition
    made: int
    failed: int
    unfinished: int
    # (made + 2·p) / (made + failed + 2); None only when no lead finished any Transition.
    smoothed_rate: float | None = Field(allow_inf_nan=False)
    # None when too few to learn.
    regression: Regression | None

    @computed_field
    @property
    def verdict(self) -> str:
        """What the screen says of it."""
        if self.regression is None:
            return "Too few to learn"
        if not self.regression.converged:
            return "Learned, but its fit did not converge"
        return "Learned"

    def chance(self, row: list[float]) -> float:
        """The chance a lead with this Features row makes it; Refused when there is no rate."""
        if self.regression is not None:
            score = self.regression.intercept + math.fsum(
                c * x for c, x in zip(self.regression.coefficients, row, strict=True)
            )
            return 1 / (1 + math.exp(-score))
        if self.smoothed_rate is None:
            raise Refused("No lead has made or failed any Transition yet, so no chance is known.")
        return self.smoothed_rate


class Model(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Trained on leads submitted, and stage events recorded, at or before this time.
    as_of: datetime
    features: Features
    # Every Transition, in ladder order.
    transitions: tuple[TransitionModel, ...]

    def chance_of_winning(self, lead: FormattedLead) -> float:
        """The chance of making every Transition from Contact attempted to Won, as a Submit
        score uses it; Refused when the lead's inputs or the Transitions cannot give one."""
        row = self.features.row(lead)
        return math.prod(transition.chance(row) for transition in self.transitions)


def train(leads: Sequence[FormattedLead], as_of: datetime) -> Model:
    """The model trained on the leads as of the time."""
    dataset = transitions_dataset(leads, as_of)
    features = fit_features([lead for lead in leads if lead.submitted_at <= as_of])
    finished = {
        transition: [
            (lead, fared is Faced.MADE) for lead, fared in facing if fared is not Faced.UNFINISHED
        ]
        for transition, facing in dataset.items()
    }
    all_finished = [made for outcomes in finished.values() for _, made in outcomes]
    pooled = sum(all_finished) / len(all_finished) if all_finished else None
    transitions = []
    for transition, outcomes in finished.items():
        made = sum(made for _, made in outcomes)
        failed = len(outcomes) - made
        transitions.append(
            TransitionModel(
                transition=transition,
                made=made,
                failed=failed,
                unfinished=len(dataset[transition]) - len(outcomes),
                smoothed_rate=None if pooled is None else (made + 2 * pooled) / (made + failed + 2),
                regression=_fit(features, outcomes) if min(made, failed) >= MIN_EACH else None,
            )
        )
    return Model(as_of=as_of, features=features, transitions=tuple(transitions))


def _fit(features: Features, outcomes: list[tuple[FormattedLead, bool]]) -> Regression:
    rows = [features.row(lead) for lead, _ in outcomes]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        fitted = LogisticRegression(C=C, max_iter=MAX_ITER).fit(
            rows, [made for _, made in outcomes]
        )
    return Regression(
        intercept=float(fitted.intercept_[0]),
        coefficients=tuple(float(c) for c in fitted.coef_[0]),
        converged=not any(issubclass(w.category, ConvergenceWarning) for w in caught),
    )
