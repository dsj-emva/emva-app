"""The time-ordered Backtest: leads in order of submission, cut into five folds; the first only
trains; each later fold is scored by a model that never saw a lead submitted, or a stage event
dated, after the fold's start. Only leads with an Outcome known now are compared."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from test_hand_made_upload import HAND_MADE, HAND_MADE_MAPPING

from emva_api.backtest import FOLDS, backtest, scored_folds
from emva_api.csv_file import read_csv
from emva_api.formatter import FormattedLead, format_files
from emva_api.ladder import LOST, Stage, StageEvent, StageOrLost
from emva_api.mapping import ConfirmedMapping, Mapping
from emva_api.model import train

DAY_ONE = datetime(2024, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def lead(day: int, *path: tuple[int, StageOrLost], trip: str = "Safari") -> FormattedLead:
    """A lead submitted on the day, reaching each Stage on the day given."""
    return FormattedLead(
        identifier_hash=f"lead {day}",
        submitted_at=DAY_ONE + timedelta(days=day),
        email_hash=None,
        phone_hash=None,
        phone_country_found=None,
        numbers={"Budget": float(day % 7)},
        categories={"Trip": trip},
        stage_events=tuple(StageEvent(stage, DAY_ONE + timedelta(days=d)) for d, stage in path),
    )


def won_on(day: int, at: int) -> FormattedLead:
    return lead(
        day, (day, Stage.CONTACT_ATTEMPTED), (day + 1, Stage.ENGAGED), (day + 2, Stage.QUALIFIED),
        (day + 3, Stage.PROPOSAL), (at, Stage.WON),
    )  # fmt: skip


def lost_on(day: int, at: int) -> FormattedLead:
    return lead(day, (day, Stage.CONTACT_ATTEMPTED), (at, LOST))


def history(leads: int = 50) -> list[FormattedLead]:
    """One lead a day; every third won, the rest lost, each ten days after submission."""
    return [
        won_on(day, day + 10) if day % 3 == 0 else lost_on(day, day + 10) for day in range(leads)
    ]


def test_leads_are_cut_in_submission_order_into_five_folds_and_the_first_is_never_scored():
    assert FOLDS == 5
    leads = list(reversed(history(52)))

    folds = scored_folds(leads)

    # 52 leads: sizes 11, 11, 10, 10, 10; the first fold of 11 only trains.
    assert [len(fold.leads) for fold in folds] == [11, 10, 10, 10]
    assert [fold.start for fold in folds] == [DAY_ONE + timedelta(days=d) for d in (11, 22, 32, 42)]
    assert [fold.trained_on for fold in folds] == [11, 22, 32, 42]
    for fold in folds:
        assert all(lead.submitted_at >= fold.start for lead in fold.leads)


def test_a_folds_model_never_sees_leads_submitted_or_stage_events_dated_after_its_start():
    leads = history(60)
    folds = scored_folds(leads)

    def after_the_start_changed(lead: FormattedLead, start: datetime) -> FormattedLead:
        """Leads submitted from the start on made unlike any before (a trip never seen), and
        every lead's stage events after the start replaced by a win."""
        if lead.submitted_at >= start:
            lead = replace(lead, categories={"Trip": "Cruise"}, numbers={"Budget": 99.0})
        kept = tuple(event for event in lead.stage_events if event.at <= start)
        return replace(
            lead, stage_events=(*kept, StageEvent(Stage.WON, start + timedelta(hours=1)))
        )

    for i, fold in enumerate(folds):
        changed = [after_the_start_changed(lead, fold.start) for lead in leads]

        assert scored_folds(changed)[i].model == fold.model
        assert fold.model.as_of == fold.start
        assert fold.model.features.categories[0].values == ("Safari",)


def test_a_fold_is_scored_by_the_model_trained_on_the_leads_before_it_as_of_its_start():
    leads = history(60)
    fold = scored_folds(leads)[2]

    before = [lead for lead in leads if lead.submitted_at < fold.start]
    assert fold.model == train(before, fold.start)


def test_the_status_quo_rate_is_the_win_rate_of_earlier_leads_with_an_outcome_at_the_start():
    # Leads 0 to 9 train. At the start, day 10, leads 0 to 9 are open until day 10 + their
    # day; only those finished by day 10 count: lead 0, won on day 10.
    leads = [won_on(0, 10), *(lost_on(d, d + 11) for d in range(1, 10))] + history(50)[10:]

    first = scored_folds(leads)[0]

    assert first.start == DAY_ONE + timedelta(days=10)
    assert first.status_quo_rate == 1.0


def test_only_leads_with_an_outcome_now_are_compared_and_every_lead_is_counted():
    leads = history(50)
    # Two scored leads still open now; one with a trip no earlier lead had.
    open_leads = [
        replace(lead(d, (d, Stage.CONTACT_ATTEMPTED)), identifier_hash=f"open {d}")
        for d in (30, 40)
    ]
    unseen = replace(lost_on(45, 46), categories={"Trip": "Wedding"}, identifier_hash="unseen")
    result = backtest([*leads, *open_leads, unseen], NOW)

    counts = result.counts
    assert counts.leads == 53
    assert counts.training_only == 11
    assert counts.no_outcome_yet == 2
    assert [(r.reason, r.leads) for r in counts.refused] == [
        ("“Trip” is “Wedding”, which no training lead had.", 1)
    ]
    assert counts.scored == 53 - 11 - 2 - 1
    assert sum(g.leads for g in result.groups) == counts.scored


def test_outcomes_after_now_are_not_known_yet():
    leads = history(50)

    result = backtest(leads, DAY_ONE + timedelta(days=45))

    # Leads submitted from day 35 on end on day 45 or later: lead 35 ends exactly now.
    assert result.counts.no_outcome_yet == 50 - 36
    assert result.as_of == DAY_ONE + timedelta(days=45)


def test_with_too_few_leads_nothing_is_scored_and_both_checks_fail():
    result = backtest(history(4), NOW)

    assert result.counts.scored == 0
    assert (result.slope, result.comparison, result.auc) == (None, None, None)
    assert result.slope_missing_because == "No lead was scored."
    assert [c.passed for c in result.checks] == [False, False]
    assert not result.passed


def test_the_backtest_on_the_hand_made_dataset_reports_its_result_whatever_it_is():
    mapping = ConfirmedMapping(Mapping.model_validate(HAND_MADE_MAPPING), DAY_ONE)
    tables = [
        read_csv((HAND_MADE / name).read_bytes()) for name in ("leads.csv", "stage_history.csv")
    ]
    leads = format_files(*tables, mapping).leads

    result = backtest(leads, NOW)

    counts = result.counts
    assert counts.leads == 100
    assert counts.training_only == 20
    assert counts.scored + counts.no_outcome_yet + sum(r.leads for r in counts.refused) == 80
    assert result.comparison is not None
    assert backtest(leads, NOW) == result


def test_the_hand_made_result_already_seen_stays_exactly_as_it_was():
    """The hand-made result was seen when this Backtest was first built (PR #21); every later
    change must leave it bit for bit as it was, or it would be tuning."""
    mapping = ConfirmedMapping(Mapping.model_validate(HAND_MADE_MAPPING), DAY_ONE)
    tables = [
        read_csv((HAND_MADE / name).read_bytes()) for name in ("leads.csv", "stage_history.csv")
    ]
    leads = format_files(*tables, mapping).leads

    result = backtest(leads, datetime(2026, 9, 14, tzinfo=UTC))

    assert result.slope == 1.218257002071192
    assert result.comparison is not None
    assert result.comparison.difference == 0.021831717979490708
    assert result.comparison.interval_low == -0.00959169631846889
    assert result.comparison.interval_high == 0.05593456387736267
    assert result.auc == 0.7175324675324676
    assert [(g.leads, g.predicted, g.actual) for g in result.groups] == [
        (12, 0.07622443184822557, 0.08333333333333333),
        (12, 0.26868678502035964, 0.25),
        (12, 0.29705090434732245, 0.16666666666666666),
        (11, 0.3487562586805556, 0.18181818181818182),
        (11, 0.4321467915120867, 0.5454545454545454),
    ]
    assert [c.passed for c in result.checks] == [False, False]
