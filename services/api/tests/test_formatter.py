"""The Formatter turns both files, read with a confirmed Mapping, into canonical leads with their
stage events, and reports every row it cannot read."""

from datetime import UTC, datetime

import pytest

from emva_api.csv_file import read_csv
from emva_api.formatter import Formatted, FormattedLead, Summary, UnreadableRow, format_files
from emva_api.ladder import Stage, StageEvent
from emva_api.mapping import ConfirmedMapping, Mapping
from emva_api.personal_data import hashed_email, hashed_phone
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
    }
)
CONFIRMED = ConfirmedMapping(mapping=MAPPING, confirmed_at=datetime(2026, 9, 14, tzinfo=UTC))

LEADS_HEADER = "Lead ID,Created,Name,Email,Phone,Trip,Budget,Notes"
ADA = "L1,2024-01-04 09:12,Ada Fenwick, Ada@Example.com ,+44 7700 900101,Safari,18500,called twice"
HISTORY_HEADER = "Lead,Stage,When,Value,By"
ADA_SUBMITTED = "L1,New,2024-01-04 09:12,,system"


def run(leads: list[str], history: list[str], mapping: Mapping = MAPPING) -> Formatted:
    def table(header: str, rows: list[str]):
        return read_csv("\n".join([header, *rows]).encode())

    return format_files(
        table(LEADS_HEADER, leads),
        table(HISTORY_HEADER, history),
        ConfirmedMapping(mapping=mapping, confirmed_at=CONFIRMED.confirmed_at),
    )


def when(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2024, 1, day, hour, minute, tzinfo=UTC)


def test_a_lead_keeps_its_identifier_submission_time_hashes_and_inputs_and_nothing_else():
    result = run([ADA], [ADA_SUBMITTED])

    assert result.leads == [
        FormattedLead(
            identifier="L1",
            submitted_at=when(4, 9, 12),
            email_hash=hashed_email("ada@example.com"),
            phone_hash=hashed_phone("+447700900101"),
            inputs={"Trip": "Safari", "Budget": 18500.0},
            stage_events=[StageEvent(Stage.SUBMITTED, when(4, 9, 12))],
        )
    ]
    assert result.unreadable == []


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
    assert lead.inputs == {"Trip": None, "Budget": None}
    assert result.unreadable == []


def test_a_category_is_kept_as_written_apart_from_surrounding_spaces():
    lead = run(["L1,2024-01-04 09:12,Ada,,, Family HOLIDAY ,"], [ADA_SUBMITTED]).leads[0]

    assert lead.inputs["Trip"] == "Family HOLIDAY"


@pytest.mark.parametrize(
    ("written", "read"),
    [
        ("2024-01-04 09:12", when(4, 9, 12)),
        ("2024-01-04T09:12:30", when(4, 9, 12).replace(second=30)),
        ("2024-01-04T10:12+01:00", when(4, 9, 12)),
        ("2024-01-04T09:12:00Z", when(4, 9, 12)),
        ("2024-01-04", when(4, 0)),
    ],
)
def test_a_time_without_a_zone_is_read_as_utc_and_one_with_a_zone_is_converted(
    written: str, read: datetime
):
    lead = run([f"L1,{written},Ada,,,Safari,1"], [ADA_SUBMITTED]).leads[0]

    assert lead.submitted_at == read
    assert lead.submitted_at.tzinfo is UTC


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (",2024-01-05 10:00,Bo,,,Safari,1", "No lead identifier."),
        ("L2,TBC,Bo,,,Safari,1", "The submission time cannot be read."),
        ("L2,,Bo,,,Safari,1", "The submission time cannot be read."),
        ("L2,05/01/2024,Bo,,,Safari,1", "The submission time cannot be read."),
        ("L2,2024-01-05 10:00,Bo,,,Safari,lots", "“Budget” is not a number."),
        ("L2,2024-01-05 10:00,Bo,,,Safari,nan", "“Budget” is not a number."),
        ("L1,2024-01-05 10:00,Bo,,,Safari,1", "Another row has the same lead identifier."),
    ],
)
def test_a_leads_row_that_cannot_be_read_is_reported_with_its_reason_and_not_kept(
    row: str, reason: str
):
    result = run([ADA, row], [ADA_SUBMITTED])

    assert [lead.identifier for lead in result.leads] == ["L1"]
    assert [(r.file, r.row, r.reason) for r in result.unreadable] == [(FileKind.LEADS, 2, reason)]


def test_an_unreadable_row_names_its_lead_but_never_repeats_what_it_holds():
    result = run([ADA, "L2,ada@example.com,Bo,,,Safari,1"], [ADA_SUBMITTED])

    assert result.unreadable == [
        UnreadableRow(FileKind.LEADS, 2, "L2", "The submission time cannot be read.")
    ]


def test_stage_events_are_placed_on_the_ladder_through_the_mapping_with_their_deal_values():
    result = run(
        [ADA],
        [
            "L1,Quote,2024-01-09 10:00,,AK",
            ADA_SUBMITTED,
            "L1,Voicemail,2024-01-05 10:00,,AK",
            "L1,Won,2024-01-20 16:30,19250,AK",
        ],
    )

    assert result.leads[0].stage_events == [
        StageEvent(Stage.SUBMITTED, when(4, 9, 12)),
        StageEvent(Stage.CONTACT_ATTEMPTED, when(5, 10)),
        StageEvent(Stage.PROPOSAL, when(9, 10)),
        StageEvent(Stage.WON, when(20, 16, 30), deal_value=19250.0),
    ]


@pytest.mark.parametrize(
    ("row", "lead", "reason"),
    [
        (",Quote,2024-01-09 10:00,,AK", None, "No lead identifier."),
        ("L1,,2024-01-09 10:00,,AK", "L1", "No CRM stage."),
        ("L1,Quote,not recorded,,AK", "L1", "The time of the change cannot be read."),
        ("L1,Won,2024-01-09 10:00,about 9k,AK", "L1", "The deal value is not a number."),
        ("L9,Won,2024-01-09 10:00,9000,AK", "L9", "The lead is not in the leads file."),
        (
            "L2,Quote,2024-01-09 10:00,,AK",
            "L2",
            "The lead's row in the leads file could not be read.",
        ),
    ],
)
def test_a_stage_history_row_that_cannot_be_read_is_reported_with_its_reason_and_not_kept(
    row: str, lead: str | None, reason: str
):
    result = run([ADA, "L2,TBC,Bo,,,Safari,1"], [ADA_SUBMITTED, row])

    assert result.leads[0].stage_events == [StageEvent(Stage.SUBMITTED, when(4, 9, 12))]
    assert UnreadableRow(FileKind.STAGE_HISTORY, 2, lead, reason) in result.unreadable


def test_the_summary_counts_leads_by_outcome_and_those_never_attempted():
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

    assert result.summary() == Summary(
        lead_count=5, won=1, lost=2, unfinished=2, never_reached_contact_attempted=2
    )
