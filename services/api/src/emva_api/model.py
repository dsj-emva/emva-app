"""The stage-by-stage model (decision 0002) with the simple model only (decision 0009): for each
Transition from Contact attempted to Won, a regularised logistic regression on the lead's
Features. A lead's chance of winning is the product of its chances on the Transitions ahead of
it; for a Submit score, all of them.

A Transition is learned only from at least MIN_EACH leads that made it and MIN_EACH that failed
it (ruling 8 of the phase 1 PRD). Otherwise it is "too few to learn" and every lead gets its
observed rate, made / (made + failed). When no lead has made or failed it yet it has no rate,
and a chance of winning that needs it is refused rather than guessed.

The model is plain data (coefficients, intercepts, the Features' parameters, the counts and
rates), kept as JSON and read back without scikit-learn. Pure: no I/O.
"""

import math
from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sklearn.linear_model import LogisticRegression

from emva_api.features import Features, Refused, fit_features
from emva_api.formatter import FormattedLead
from emva_api.ladder import Stage
from emva_api.transitions import Faced, Transition, transitions_dataset

MIN_EACH = 10
# The L2 penalty's inverse strength, fixed in advance and never tuned on results: scikit-learn's
# default, a moderate pull towards zero on standardised inputs.
C = 1.0


class Learned(BaseModel):
    model_config = ConfigDict(frozen=True)

    intercept: float
    # One per input of the Features' row, in its order.
    coefficients: tuple[float, ...]


class TransitionModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_stage: Stage
    to_stage: Stage
    made: int
    failed: int
    unfinished: int
    # made / (made + failed); None while no lead has made or failed it.
    observed_rate: float | None
    # None when too few to learn.
    learned: Learned | None

    @property
    def transition(self) -> Transition:
        return Transition(self.from_stage, self.to_stage)

    def chance(self, row: list[float]) -> float:
        """The chance a lead with these Features makes it; Refused when it has no rate."""
        if self.learned is not None:
            score = self.learned.intercept + math.fsum(
                c * x for c, x in zip(self.learned.coefficients, row, strict=True)
            )
            return 1 / (1 + math.exp(-score))
        if self.observed_rate is None:
            raise Refused(
                f"No lead has made or failed {self.transition.name} yet, so its chance is unknown."
            )
        return self.observed_rate


class Model(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Learned from leads submitted, and stage events recorded, at or before this time.
    as_of: datetime
    features: Features
    # The learned Transitions, in ladder order.
    transitions: tuple[TransitionModel, ...]

    def chance_of_winning(self, lead: FormattedLead) -> float:
        """The chance of making every Transition from Contact attempted to Won, as a Submit
        score uses it; Refused when the lead's inputs or a Transition cannot give one."""
        row = self.features.row(lead)
        return math.prod(transition.chance(row) for transition in self.transitions)


def train(leads: Sequence[FormattedLead], as_of: datetime) -> Model:
    """The model learned from the leads as of the time."""
    dataset = transitions_dataset(leads, as_of)
    learned_from = {
        lead.identifier_hash: lead
        for facing in dataset.values()
        for lead, fared in facing
        if fared is not Faced.UNFINISHED
    }
    features = fit_features(list(learned_from.values()))
    transitions = []
    for transition, facing in dataset.items():
        finished = [
            (lead, fared is Faced.MADE) for lead, fared in facing if fared is not Faced.UNFINISHED
        ]
        made = sum(made for _, made in finished)
        failed = len(finished) - made
        transitions.append(
            TransitionModel(
                from_stage=transition.from_stage,
                to_stage=transition.to_stage,
                made=made,
                failed=failed,
                unfinished=len(facing) - len(finished),
                observed_rate=made / len(finished) if finished else None,
                learned=_fit(features, finished) if min(made, failed) >= MIN_EACH else None,
            )
        )
    return Model(as_of=as_of, features=features, transitions=tuple(transitions))


def _fit(features: Features, finished: list[tuple[FormattedLead, bool]]) -> Learned:
    rows = [features.row(lead) for lead, _ in finished]
    fitted = LogisticRegression(C=C, max_iter=1000).fit(rows, [made for _, made in finished])
    return Learned(
        intercept=float(fitted.intercept_[0]),
        coefficients=tuple(float(c) for c in fitted.coef_[0]),
    )
