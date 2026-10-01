"""The Backtest: the advertiser's past leads scored, in time order, each with a model trained
only on leads submitted before it, then compared with how they actually ended and with the
Status-quo signal. Pure: no I/O; "now" is given by the caller's injected clock.

Every rule below is fixed in advance and never tuned on results (decision 0005); the Trust gate
uses its real-data thresholds: the calibration slope within 0.8 to 1.2, and the 95% interval of
the paired Brier difference above zero. AUC is reported, not gated.
"""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, computed_field

from emva_api.features import Refused
from emva_api.formatter import FormattedLead
from emva_api.ladder import Won, progress
from emva_api.model import Model, train

FOLDS = 5
MAX_GROUPS = 10
MIN_PER_GROUP = 10
# Predictions are clipped to [EPSILON, 1 - EPSILON] before their log-odds are taken.
EPSILON = 0.001
RESAMPLES = 2000
SEED = 2026
SLOPE_LOW, SLOPE_HIGH = 0.8, 1.2
# Newton's method for the slope's regression: it has converged when no step moves a
# coefficient by more than this; otherwise, after MAX_STEPS, there is no slope.
STEP_TOLERANCE = 1e-10
MAX_STEPS = 100

RULES = (
    f"Leads are put in order of submission and cut into {FOLDS} consecutive folds of equal "
    "size. The first fold only trains and is never scored. Each later fold is scored with a "
    "model trained only on the leads submitted before its first lead, with their stage history "
    "as of that moment.",
    "Only leads whose Outcome is known now, won or lost, are compared with how they ended.",
    "The Status-quo signal gives every lead of a fold the win rate of the leads before it that "
    "had an Outcome at the fold's start: every lead sent alike.",
    f"Calibration groups: leads in order of predicted chance, cut into deciles when there are "
    f"at least {MAX_GROUPS * MIN_PER_GROUP}, otherwise into as many groups of at least "
    f"{MIN_PER_GROUP} as there are.",
    f"Calibration slope: the unpenalised logistic regression of the Outcome on the log-odds of "
    f"the predicted chance, clipped to between {EPSILON} and {1 - EPSILON}.",
    f"Brier difference: the status quo's Brier score minus Emva's, per lead, so above zero means "
    f"Emva is more accurate. Its 95% interval is a bootstrap over leads, {RESAMPLES} resamples "
    f"with the fixed seed {SEED}.",
)


class Group(BaseModel):
    """One calibration group."""

    model_config = ConfigDict(frozen=True)

    leads: int
    predicted: float = Field(description="The group's mean predicted chance of winning")
    actual: float = Field(description="The share of the group's leads that were won")


class Comparison(BaseModel):
    """Emva against the Status-quo signal, by Brier score (lower is more accurate)."""

    model_config = ConfigDict(frozen=True)

    emva_brier: float
    status_quo_brier: float
    difference: float = Field(description="Status quo's Brier score minus Emva's, per lead")
    interval_low: float
    interval_high: float


class Check(BaseModel):
    """One check of the Trust gate."""

    model_config = ConfigDict(frozen=True)

    name: str
    threshold: str
    passed: bool


class Refusals(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason: str
    leads: int


class FoldResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: datetime = Field(description="When its first lead was submitted")
    leads: int
    trained_on: int = Field(description="Leads submitted before its start")
    status_quo_rate: float | None = Field(
        description="The win rate of the leads before it with an Outcome at its start"
    )


class Counts(BaseModel):
    model_config = ConfigDict(frozen=True)

    leads: int
    training_only: int = Field(description="Leads of the first fold: trained on, never scored")
    no_outcome_yet: int = Field(description="Leads neither won nor lost yet: left out")
    refused: list[Refusals] = Field(description="Leads that could not be scored, by reason")
    scored: int


class Backtest(BaseModel):
    model_config = ConfigDict(frozen=True)

    as_of: datetime = Field(description="When the Outcomes compared with were read")
    rules: tuple[str, ...]
    counts: Counts
    folds: tuple[FoldResult, ...]
    groups: tuple[Group, ...]
    slope: float | None = Field(description="Null when it cannot be fitted on the leads scored")
    comparison: Comparison | None = Field(description="Null when no lead was scored")
    auc: float | None = Field(description="Null unless both won and lost leads were scored")
    checks: tuple[Check, Check]

    @computed_field(description="Whether every check of the Trust gate passed")
    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


@dataclass(frozen=True)
class Fold:
    start: datetime
    leads: list[FormattedLead]
    # Trained only on the leads submitted before start, with their stage events up to it.
    model: Model
    status_quo_rate: float | None
    trained_on: int


def scored_folds(leads: Sequence[FormattedLead]) -> list[Fold]:
    """Every fold after the first, each with the model it is scored with."""
    in_order = sorted(leads, key=lambda lead: lead.submitted_at)
    parts = [list(part) for part in _split(in_order, FOLDS) if part]
    folds = []
    for part in parts[1:]:
        start = part[0].submitted_at
        before = [lead for lead in in_order if lead.submitted_at < start]
        outcomes = [_outcome(lead, start) for lead in before]
        known = [outcome for outcome in outcomes if outcome is not None]
        folds.append(
            Fold(
                start=start,
                leads=part,
                model=train(before, start),
                status_quo_rate=sum(known) / len(known) if known else None,
                trained_on=len(before),
            )
        )
    return folds


def backtest(leads: Sequence[FormattedLead], now: datetime) -> Backtest:
    """The Backtest of the leads, compared with their Outcomes as known now."""
    folds = scored_folds(leads)
    predicted: list[float] = []
    status_quo: list[float] = []
    won: list[bool] = []
    no_outcome = 0
    refused: Counter[str] = Counter()
    for fold in folds:
        for lead in fold.leads:
            outcome = _outcome(lead, now)
            if outcome is None:
                no_outcome += 1
                continue
            if fold.status_quo_rate is None:
                refused[
                    "No earlier lead had an Outcome, so the Status-quo signal has no rate."
                ] += 1
                continue
            try:
                chance = fold.model.chance_of_winning(lead)
            except Refused as refusal:
                refused[str(refusal)] += 1
                continue
            predicted.append(chance)
            status_quo.append(fold.status_quo_rate)
            won.append(outcome)
    slope = calibration_slope(predicted, won)
    comparison = brier_comparison(predicted, status_quo, won) if won else None
    return Backtest(
        as_of=now,
        rules=RULES,
        counts=Counts(
            leads=len(leads),
            training_only=len(leads) - sum(len(fold.leads) for fold in folds),
            no_outcome_yet=no_outcome,
            refused=[Refusals(reason=r, leads=n) for r, n in refused.most_common()],
            scored=len(won),
        ),
        folds=tuple(
            FoldResult(
                start=fold.start,
                leads=len(fold.leads),
                trained_on=fold.trained_on,
                status_quo_rate=fold.status_quo_rate,
            )
            for fold in folds
        ),
        groups=tuple(calibration_groups(predicted, won)),
        slope=slope,
        comparison=comparison,
        auc=auc(predicted, won),
        checks=trust_gate(slope, comparison.interval_low if comparison else None),
    )


def trust_gate(slope: float | None, interval_low: float | None) -> tuple[Check, Check]:
    """The Trust gate's real-data checks, fixed before any result is seen (decision 0005)."""
    return (
        Check(
            name="Calibration",
            threshold=f"Calibration slope within {SLOPE_LOW} to {SLOPE_HIGH}",
            passed=slope is not None and SLOPE_LOW <= slope <= SLOPE_HIGH,
        ),
        Check(
            name="Better than the Status-quo signal",
            threshold="The 95% interval of the Brier difference (status quo minus Emva) is "
            "above zero",
            passed=interval_low is not None and interval_low > 0,
        ),
    )


def calibration_groups(predicted: Sequence[float], won: Sequence[bool]) -> list[Group]:
    """Leads in order of predicted chance, cut into deciles when there are enough for ten in
    each, otherwise into as many groups of at least MIN_PER_GROUP as there are."""
    if not predicted:
        return []
    count = max(1, min(MAX_GROUPS, len(predicted) // MIN_PER_GROUP))
    ranked = sorted(zip(predicted, won, strict=True), key=lambda pair: pair[0])
    return [
        Group(
            leads=len(group),
            predicted=math.fsum(p for p, _ in group) / len(group),
            actual=sum(w for _, w in group) / len(group),
        )
        for group in _split(ranked, count)
    ]


def calibration_slope(predicted: Sequence[float], won: Sequence[bool]) -> float | None:
    """The coefficient of the unpenalised logistic regression of the Outcome on the log-odds of
    the clipped predicted chance; None when it has no finite fit (predictions all alike, one
    Outcome only, or Outcomes perfectly separated by the prediction)."""
    if len(set(predicted)) < 2 or len(set(won)) < 2:
        return None
    clipped = np.clip(np.asarray(predicted, dtype=float), EPSILON, 1 - EPSILON)
    x = np.column_stack([np.ones(len(clipped)), np.log(clipped / (1 - clipped))])
    y = np.asarray(won, dtype=float)
    beta = np.zeros(2)
    for _ in range(MAX_STEPS):
        mu = 1 / (1 + np.exp(-np.clip(x @ beta, -500, 500)))
        hessian = x.T @ (x * (mu * (1 - mu))[:, None])
        try:
            step = np.linalg.solve(hessian, x.T @ (y - mu))
        except np.linalg.LinAlgError:
            return None
        if not np.all(np.isfinite(step)):
            return None
        beta = beta + step
        if np.max(np.abs(step)) < STEP_TOLERANCE:
            return float(beta[1])
    return None


def brier_comparison(
    predicted: Sequence[float], status_quo: Sequence[float], won: Sequence[bool]
) -> Comparison:
    """Mean Brier scores and their paired per-lead difference, status quo minus Emva, with a
    95% bootstrap interval over leads (RESAMPLES resamples, seed SEED)."""
    y = np.asarray(won, dtype=float)
    emva = (np.asarray(predicted, dtype=float) - y) ** 2
    usual = (np.asarray(status_quo, dtype=float) - y) ** 2
    differences = usual - emva
    resampled = np.random.default_rng(SEED).integers(0, len(y), size=(RESAMPLES, len(y)))
    low, high = np.quantile(differences[resampled].mean(axis=1), [0.025, 0.975])
    return Comparison(
        emva_brier=float(emva.mean()),
        status_quo_brier=float(usual.mean()),
        difference=float(differences.mean()),
        interval_low=float(low),
        interval_high=float(high),
    )


def auc(predicted: Sequence[float], won: Sequence[bool]) -> float | None:
    """The share of pairs of a won and a lost lead in which the won lead has the higher
    predicted chance, a tie counting half; None without both."""
    wins = [p for p, w in zip(predicted, won, strict=True) if w]
    losses = [p for p, w in zip(predicted, won, strict=True) if not w]
    if not wins or not losses:
        return None
    right = sum((w > lost) + 0.5 * (w == lost) for w in wins for lost in losses)
    return right / (len(wins) * len(losses))


def _outcome(lead: FormattedLead, at: datetime) -> bool | None:
    """Whether the lead was won, as known at the time; None while it has no Outcome."""
    outcome = progress(event for event in lead.stage_events if event.at <= at).outcome
    return None if outcome is None else isinstance(outcome, Won)


def _split[T](items: Sequence[T], parts: int) -> list[Sequence[T]]:
    """Consecutive parts whose sizes differ by at most one, the larger first."""
    size, extra = divmod(len(items), parts)
    cuts = [0]
    for i in range(parts):
        cuts.append(cuts[-1] + size + (i < extra))
    return [items[a:b] for a, b in zip(cuts, cuts[1:], strict=False)]
