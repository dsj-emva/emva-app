"""The Backtest's measures on small hand-made inputs with answers worked out by hand: the
calibration slope, the calibration groups, the Brier difference with its bootstrap interval,
AUC, and the Trust gate's pass/fail marks on both sides of each threshold."""

import math

import numpy as np
import pytest

from emva_api import backtest as backtest_module
from emva_api.backtest import (
    EPSILON,
    RESAMPLES,
    SEED,
    auc,
    brier_comparison,
    calibration_groups,
    calibration_slope,
    trust_gate,
)


def repeated(chance: float, won: int, lost: int) -> tuple[list[float], list[bool]]:
    return [chance] * (won + lost), [True] * won + [False] * lost


def joined(*parts: tuple[list[float], list[bool]]) -> tuple[list[float], list[bool]]:
    return [p for part in parts for p in part[0]], [w for part in parts for w in part[1]]


def test_a_slope_of_one_when_each_predicted_chance_wins_at_that_rate():
    # 1 of 5 won at 0.2 and 4 of 5 at 0.8: the fit through both groups' rates is exact.
    predicted, won = joined(repeated(0.2, 1, 4), repeated(0.8, 4, 1))

    assert calibration_slope(predicted, won).value == pytest.approx(1.0, abs=1e-9)


def test_a_slope_of_one_half_when_the_win_rates_are_half_as_far_apart_in_log_odds():
    # Predicted log-odds ±ln 4 (0.2 and 0.8); won at 1/3 and 2/3, log-odds ±ln 2.
    predicted, won = joined(repeated(0.2, 1, 2), repeated(0.8, 2, 1))

    assert calibration_slope(predicted, won).value == pytest.approx(
        math.log(2) / math.log(4), abs=1e-9
    )


def test_predictions_of_zero_and_one_are_clipped_before_their_log_odds_are_taken():
    assert EPSILON == 0.001
    # Clipped to 0.001 and 0.999, log-odds ±ln 999; won at 1/3 and 2/3, log-odds ±ln 2.
    predicted, won = joined(repeated(0.0, 1, 2), repeated(1.0, 2, 1))

    assert calibration_slope(predicted, won).value == pytest.approx(
        math.log(2) / math.log(999), abs=1e-9
    )


def no_slope_because(predicted: list[float], won: list[bool]) -> str | None:
    slope = calibration_slope(predicted, won)
    assert slope.value is None
    return slope.missing_because


def test_no_slope_when_the_predictions_are_all_alike_or_all_one_outcome_and_it_says_why():
    assert no_slope_because([], []) == "No lead was scored."
    assert no_slope_because(*repeated(0.3, 2, 3)) == (
        "Every lead scored has the same predicted chance, so no slope can be fitted."
    )
    assert no_slope_because([0.2, 0.4, 0.6], [False] * 3) == (
        "The leads scored were all won or all lost, so no slope can be fitted."
    )


SEPARATED = (
    "The fit did not converge: the predicted chances separate won from lost leads "
    "(near-)perfectly, so no finite slope fits them."
)


def test_no_slope_when_won_and_lost_leads_are_perfectly_separated():
    assert no_slope_because([0.2, 0.3, 0.6, 0.7], [False, False, True, True]) == SEPARATED


def test_no_slope_when_they_are_separated_but_for_a_tie_at_the_boundary():
    # Every lost lead at or below 0.5 and every won lead at or above it: quasi-separation.
    predicted = [0.2, 0.3, 0.5, 0.5, 0.7, 0.8]
    won = [False, False, False, True, True, True]

    assert no_slope_because(predicted, won) == SEPARATED


def test_a_slope_has_no_reason_missing():
    predicted, won = joined(repeated(0.2, 1, 4), repeated(0.8, 4, 1))

    assert calibration_slope(predicted, won).missing_because is None


def test_deciles_with_at_least_ten_leads_in_each_otherwise_fewer_groups():
    def sizes(n: int) -> list[int]:
        return [g.leads for g in calibration_groups([i / n for i in range(n)], [False] * n)]

    assert sizes(100) == [10] * 10
    assert sizes(205) == [21] * 5 + [20] * 5
    assert sizes(64) == [11] * 4 + [10] * 2
    assert sizes(0) == []


def test_fewer_than_ten_leads_make_one_group_of_them_all():
    (group,) = calibration_groups([0.1, 0.2, 0.6], [False, True, True])

    assert (group.leads, group.predicted, group.actual) == (
        3,
        pytest.approx(0.3),
        pytest.approx(2 / 3),
    )
    assert [g.leads for g in calibration_groups([0.5] * 9, [False] * 9)] == [9]


def test_leads_with_the_same_predicted_chance_keep_the_order_they_were_scored_in():
    # Twenty leads all at 0.5: the first ten scored won, the last ten lost. Ties are not
    # broken by Outcome, so the groups keep that order.
    lower, upper = calibration_groups([0.5] * 20, [True] * 10 + [False] * 10)

    assert (lower.actual, upper.actual) == (1.0, 0.0)
    flipped = calibration_groups([0.5] * 20, [False] * 10 + [True] * 10)
    assert [g.actual for g in flipped] == [0.0, 1.0]


def test_a_group_shows_its_mean_predicted_chance_and_its_actual_win_rate():
    predicted = [0.1] * 5 + [0.3] * 5 + [0.5] * 5 + [0.9] * 5
    won = [i < 2 for i in range(5)] * 2 + [True] * 10
    # 20 leads: two groups of ten, the lower ten and the upper ten by predicted chance.
    lower, upper = calibration_groups(predicted, won)

    assert (lower.leads, lower.predicted, lower.actual) == (10, pytest.approx(0.2), 0.4)
    assert (upper.leads, upper.predicted, upper.actual) == (10, pytest.approx(0.7), 1.0)


def test_the_brier_difference_is_the_status_quo_brier_minus_emvas():
    # Emva: (0.8 - 1)² = 0.04 and (0.4 - 0)² = 0.16. Status quo 0.5 each: 0.25 and 0.25.
    comparison = brier_comparison([0.8, 0.4], [0.5, 0.5], [True, False])

    assert comparison.emva_brier == pytest.approx(0.10)
    assert comparison.status_quo_brier == pytest.approx(0.25)
    assert comparison.difference == pytest.approx(0.15)


def test_when_every_lead_differs_by_the_same_amount_the_interval_is_that_amount():
    # Each lead: status quo (0.5 - 1)² = 0.25 or (0.5 - 0)² = 0.25; Emva 0.04 either way.
    won = [True, False] * 5
    emva = [0.8 if w else 0.2 for w in won]
    comparison = brier_comparison(emva, [0.5] * 10, won)

    assert comparison.interval_low == pytest.approx(0.21)
    assert comparison.interval_high == pytest.approx(0.21)


def test_the_interval_is_a_fixed_seed_bootstrap_over_leads_and_reproduces():
    assert (SEED, RESAMPLES) == (2026, 2000)
    emva = [0.9, 0.2, 0.6, 0.4, 0.7, 0.1, 0.5, 0.3]
    won = [True, False, True, False, False, False, True, True]

    first = brier_comparison(emva, [0.5] * 8, won)
    again = brier_comparison(emva, [0.5] * 8, won)

    assert first == again
    assert first.interval_low < first.difference < first.interval_high
    # Resampling eight leads cannot give a mean beyond the best and worst single lead's.
    differences = [0.25 - (p - w) ** 2 for p, w in zip(emva, won, strict=True)]
    assert min(differences) <= first.interval_low
    assert first.interval_high <= max(differences)


def test_the_interval_is_the_same_however_many_resamples_are_drawn_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
):
    # Resamples are drawn in chunks to bound memory; the stream of draws, and so the interval,
    # must be exactly that of drawing all RESAMPLES at once.
    rng = np.random.default_rng(7)
    won = list(rng.random(37) < 0.4)
    emva = list(rng.random(37))
    y = np.asarray(won, dtype=float)
    differences = (0.4 - y) ** 2 - (np.asarray(emva) - y) ** 2
    at_once = np.random.default_rng(SEED).integers(0, 37, size=(RESAMPLES, 37))
    low, high = np.quantile(differences[at_once].mean(axis=1), [0.025, 0.975])

    for elements in (37, 37 * 3 + 5, 10**6):
        monkeypatch.setattr(backtest_module, "CHUNK_ELEMENTS", elements)
        comparison = brier_comparison(emva, [0.4] * 37, won)
        assert (comparison.interval_low, comparison.interval_high) == (low, high)


def test_auc_counts_the_pairs_of_a_won_and_a_lost_lead_ranked_the_right_way_ties_half():
    # Won 0.8 and 0.4; lost 0.4 and 0.2. Pairs: (0.8, 0.4) 1, (0.8, 0.2) 1, (0.4, 0.4) ½,
    # (0.4, 0.2) 1: 3.5 of 4.
    assert auc([0.8, 0.4, 0.4, 0.2], [True, True, False, False]) == pytest.approx(0.875)
    assert auc([0.3, 0.6], [True, True]) is None


def test_auc_by_ranks_equals_counting_every_pair():
    def by_pairs(predicted: list[float], won: list[bool]) -> float:
        wins = [p for p, w in zip(predicted, won, strict=True) if w]
        losses = [p for p, w in zip(predicted, won, strict=True) if not w]
        right = sum((w > lost) + 0.5 * (w == lost) for w in wins for lost in losses)
        return right / (len(wins) * len(losses))

    rng = np.random.default_rng(3)
    for n in (2, 5, 40, 301):
        # Rounded so that many predictions tie.
        predicted = [float(p) for p in np.round(rng.random(n), 1)]
        won = [bool(w) for w in rng.random(n) < 0.3]
        won[0], won[1] = True, False

        assert auc(predicted, won) == by_pairs(predicted, won)


@pytest.mark.parametrize(
    ("slope", "passed"),
    [(0.79, False), (0.8, True), (1.0, True), (1.2, True), (1.21, False), (None, False)],
)
def test_the_calibration_check_passes_only_with_a_slope_within_0_8_to_1_2(slope, passed):
    calibration, _ = trust_gate(slope, 0.01)

    assert calibration.passed is passed
    assert calibration.threshold == "Calibration slope within 0.8 to 1.2"


@pytest.mark.parametrize(
    ("interval_low", "passed"), [(0.001, True), (0.0, False), (-0.02, False), (None, False)]
)
def test_the_comparison_check_passes_only_with_its_interval_above_zero(interval_low, passed):
    _, comparison = trust_gate(1.0, interval_low)

    assert comparison.passed is passed
    assert comparison.threshold == (
        "The 95% interval of the Brier difference (status quo minus Emva) is above zero"
    )
