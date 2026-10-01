"""The Formatter turns both files, read with a confirmed Mapping, into canonical leads with their
stage events, and reports every row it cannot read without repeating what it holds."""

from datetime import UTC, datetime

import pytest

from emva_api.csv_file import read_csv
from emva_api.dates import DateOrder
from emva_api.formatter import (
    Formatted,
    FormattedLead,
    Summary,
    Unreadable,
    UnreadableRows,
    format_files,
    format_lead,
)
from emva_api.ladder import Stage, StageEvent
from emva_api.mapping import ConfirmedMapping, Mapping
from emva_api.personal_data import Country, hashed_email, hashed_identifier, hashed_phone
from emva_api.records import FileKind

MAPPING = Mapping.model_validate(
    {
        "leads": {
            "lead_id": "Lead ID",
            "submitted_at": "Created",
            "name": "Name",
            "email": "Email",
            "phone": "Phone",
            "inputs": {"Trip": "category", "Budget": "number"},
        },
        "stage_history": {
            "lead_id": "Lead",
            "crm_stage": "Stage",
            "changed_at": "When",
            "deal_value": "Value",
        },
        "crm_stages": {
            "New": "submitted",
            "Called": "contact_attempted",
            "Voicemail": "contact_attempted",
            "Quote": "proposal",
            "Won": "won",
            "Lost": "lost",
        },
        "typical_deal_size": 10000.0,
        "default_country": "GB",
        "date_order": "year_month_day",
        "time_zone": "UTC",
    }
)

LEADS_HEADER = "Lead ID,Created,Name,Email,Phone,Trip,Budget,Notes"
ADA = "L1,2024-01-04 09:12,Ada Fenwick, Ada@Example.com ,07700 900101,Safari,18500,called twice"
HISTORY_HEADER = "Lead,Stage,When,Value,By"
ADA_SUBMITTED = "L1,New,2024-01-04 09:12,,system"


def run(leads: list[str], history: list[str], mapping: Mapping = MAPPING) -> Formatted:
    def table(header: str, rows: list[str]):
        return read_csv("\n".join([header, *rows]).encode())

    confirmed = ConfirmedMapping(mapping=mapping, confirmed_at=datetime(2026, 9, 14, tzinfo=UTC))
    return format_files(table(LEADS_HEADER, leads), table(HISTORY_HEADER, history), confirmed)


def when(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2024, 1, day, hour, minute, tzinfo=UTC)


def test_a_lead_keeps_hashes_of_what_identifies_it_its_submission_time_and_inputs_only():
    result = run([ADA], [ADA_SUBMITTED])

    assert result.leads == [
        FormattedLead(
            identifier_hash=hashed_identifier("L1"),
            submitted_at=when(4, 9, 12),
            email_hash=hashed_email("ada@example.com"),
            phone_hash=hashed_phone("+447700900101", Country.GB),
            numbers={"Budget": 18500.0},
            categories={"Trip": "Safari"},
            stage_events=(StageEvent(Stage.SUBMITTED, when(4, 9, 12)),),
        )
    ]
    assert result.summary.unreadable == []


def test_one_new_lead_is_formatted_by_the_same_code_from_its_values_alone():
    lead = format_lead(
        {"Lead ID": "L7", "Created": "2024-01-04 09:12", "Trip": "Safari", "Budget": "900"},
        MAPPING,
    )

    assert lead == FormattedLead(
        identifier_hash=hashed_identifier("L7"),
        submitted_at=when(4, 9, 12),
        email_hash=None,
        phone_hash=None,
        numbers={"Budget": 900.0},
        categories={"Trip": "Safari"},
    )


def test_one_new_lead_that_cannot_be_read_says_why():
    with pytest.raises(Unreadable, match="The submission time cannot be read."):
        format_lead({"Lead ID": "L7", "Created": "soon"}, MAPPING)


def test_without_email_or_phone_columns_marked_a_lead_has_no_hashes():
    unmarked = MAPPING.model_copy(
        update={"leads": MAPPING.leads.model_copy(update={"email": None, "phone": None})}
    )

    lead = run([ADA], [ADA_SUBMITTED], unmarked).leads[0]

    assert (lead.email_hash, lead.phone_hash) == (None, None)


def test_a_blank_email_phone_or_input_is_missing_not_unreadable():
    result = run(["L1,2024-01-04 09:12,Ada,,  ,,"], [ADA_SUBMITTED])

    lead = result.leads[0]
    assert (lead.email_hash, lead.phone_hash) == (None, None)
    assert (lead.numbers, lead.categories) == ({"Budget": None}, {"Trip": None})
    assert result.summary.unreadable == []


def test_a_category_is_kept_as_written_apart_from_surrounding_spaces():
    lead = run(["L1,2024-01-04 09:12,Ada,,, Family HOLIDAY ,"], [ADA_SUBMITTED]).leads[0]

    assert lead.categories["Trip"] == "Family HOLIDAY"


def test_both_files_are_read_with_the_date_order_and_time_zone_picked():
    british = MAPPING.model_copy(
        update={"date_order": DateOrder.DAY_MONTH_YEAR, "time_zone": "Europe/London"}
    )

    lead = run(
        ["L1,05/07/2024 10:00,Ada,,,Safari,1"], ["L1,Called,06/07/2024 09:30,,AK"], british
    ).leads[0]

    assert lead.submitted_at == datetime(2024, 7, 5, 9, 0, tzinfo=UTC)
    assert lead.stage_events == (
        StageEvent(Stage.CONTACT_ATTEMPTED, datetime(2024, 7, 6, 8, 30, tzinfo=UTC)),
    )


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (",2024-01-05 10:00,Bo,,,Safari,1", "No lead identifier."),
        ("L2,TBC,Bo,,,Safari,1", "The submission time cannot be read."),
        ("L2,,Bo,,,Safari,1", "The submission time cannot be read."),
        ("L2,05/01/2024,Bo,,,Safari,1", "The submission time cannot be read."),
        ("L2,2024-01-05 10:00,Bo,,,Safari,lots", "“Budget” is not a number."),
        ("L2,2024-01-05 10:00,Bo,,,Safari,nan", "“Budget” is not a number."),
        (" L1 ,2024-01-05 10:00,Bo,,,Safari,1", "Another row has the same lead identifier."),
    ],
)
def test_a_leads_row_that_cannot_be_read_is_reported_by_row_and_reason_and_not_kept(
    row: str, reason: str
):
    result = run([ADA, row], [ADA_SUBMITTED])

    assert [lead.identifier_hash for lead in result.leads] == [hashed_identifier("L1")]
    assert result.summary.unreadable == [
        UnreadableRows(file=FileKind.LEADS, reason=reason, count=1, first_rows=[2])
    ]


def test_an_unreadable_row_never_names_its_lead_or_repeats_what_it_holds():
    result = run([ADA, "ada@example.com,ada@example.com,Bo,,,Safari,1"], [ADA_SUBMITTED])

    reported = result.summary.model_dump_json()
    assert "ada@example.com" not in reported
    assert "L1" not in reported


def test_stage_events_are_placed_on_the_ladder_through_the_mapping_with_their_deal_values():
    result = run(
        [ADA],
        [
            "L1,Quote,2024-01-09 10:00,,AK",
            ADA_SUBMITTED,
            "L1,Called,2024-01-05 10:00,,AK",
            "L1,Won,2024-01-20 16:30,19250,AK",
        ],
    )

    assert result.leads[0].stage_events == (
        StageEvent(Stage.SUBMITTED, when(4, 9, 12)),
        StageEvent(Stage.CONTACT_ATTEMPTED, when(5, 10)),
        StageEvent(Stage.PROPOSAL, when(9, 10)),
        StageEvent(Stage.WON, when(20, 16, 30), deal_value=19250.0),
    )


def test_two_crm_stages_on_one_ladder_stage_both_count_for_the_same_lead():
    result = run([ADA], ["L1,Called,2024-01-05 10:00,,AK", "L1,Voicemail,2024-01-06 11:00,,AK"])

    assert result.leads[0].stage_events == (
        StageEvent(Stage.CONTACT_ATTEMPTED, when(5, 10)),
        StageEvent(Stage.CONTACT_ATTEMPTED, when(6, 11)),
    )
    assert result.summary.neglected == 0


def test_the_files_are_joined_on_the_trimmed_identifier():
    result = run([ADA], [" L1 ,Called,2024-01-05 10:00,,AK"])

    assert result.leads[0].stage_events == (StageEvent(Stage.CONTACT_ATTEMPTED, when(5, 10)),)


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (",Quote,2024-01-09 10:00,,AK", "No lead identifier."),
        ("L1,,2024-01-09 10:00,,AK", "No CRM stage."),
        ("L1,Quote,not recorded,,AK", "The time of the change cannot be read."),
        ("L1,Won,2024-01-09 10:00,about 9k,AK", "The deal value is not a number."),
        ("L9,Won,2024-01-09 10:00,9000,AK", "The lead is not in the leads file."),
        ("L2,Quote,2024-01-09 10:00,,AK", "The lead's row in the leads file could not be read."),
    ],
)
def test_a_stage_history_row_that_cannot_be_read_is_reported_and_not_kept(row: str, reason: str):
    result = run([ADA, "L2,TBC,Bo,,,Safari,1"], [ADA_SUBMITTED, row])

    assert result.leads[0].stage_events == (StageEvent(Stage.SUBMITTED, when(4, 9, 12)),)
    assert (
        UnreadableRows(file=FileKind.STAGE_HISTORY, reason=reason, count=1, first_rows=[2])
        in result.summary.unreadable
    )


def test_unreadable_rows_are_counted_by_reason_with_only_their_first_ten_row_numbers():
    unknown = ["L9,Won,2024-01-09 10:00,,AK" for _ in range(12)]
    result = run([ADA], [ADA_SUBMITTED, *unknown, "L1,,2024-01-09 10:00,,AK"])

    assert result.summary.unreadable == [
        UnreadableRows(
            file=FileKind.STAGE_HISTORY,
            reason="The lead is not in the leads file.",
            count=12,
            first_rows=[2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        ),
        UnreadableRows(
            file=FileKind.STAGE_HISTORY, reason="No CRM stage.", count=1, first_rows=[14]
        ),
    ]


def test_the_summary_counts_leads_by_outcome_and_the_neglected_leads():
    result = run(
        [
            ADA,
            "L2,2024-01-05 10:00,Bo,,,Safari,1",
            "L3,2024-01-06 10:00,Cy,,,Safari,1",
            "L4,2024-01-07 10:00,Di,,,Safari,1",
            "L5,2024-01-08 10:00,Ed,,,Safari,1",
            "L6,TBC,Fi,,,Safari,1",
        ],
        [
            "L1,Called,2024-01-05 10:00,,AK",
            "L1,Won,2024-01-20 10:00,,AK",
            "L2,Quote,2024-01-09 10:00,,AK",
            "L2,Lost,2024-01-12 10:00,,AK",
            "L3,Called,2024-01-07 10:00,,AK",
            "L4,Lost,2024-01-07 12:00,,AK",
            "L9,Won,2024-01-20 10:00,,AK",
        ],
    )

    assert result.summary.model_dump(exclude={"unreadable"}) == Summary(
        lead_count=5, won=1, lost=2, no_outcome_yet=2, neglected=2, unreadable=[]
    ).model_dump(exclude={"unreadable"})
