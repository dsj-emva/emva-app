import pytest

from emva_api.csv_file import (
    ColumnFacts,
    ColumnProfile,
    UnreadableFile,
    column_facts,
    count_values,
    profile,
    read_csv,
)


def test_column_facts_count_each_columns_distinct_non_empty_values():
    table = read_csv(b"Trip,Budget\nSafari,100\nsafari,100\nSafari,\n,200\n")

    assert column_facts(table) == {
        "Trip": ColumnFacts(distinct_values=2, looks_like_contact=False),
        "Budget": ColumnFacts(distinct_values=2, looks_like_contact=False),
    }


@pytest.mark.parametrize(
    "value",
    [
        "ada.fenwick@example.com",
        "Call Ada on ada@example.org please",
        "+44 7700 900101",
        "07700 900101",
        "ring 07700900101 after 6",
        "(0044) 7700-900-101",
    ],
)
def test_a_column_with_any_value_like_an_email_or_phone_looks_like_contact_details(value: str):
    table = read_csv(f'Notes\nSafari\n"{value}"\n'.encode())

    assert column_facts(table)["Notes"].looks_like_contact


@pytest.mark.parametrize(
    "value", ["Safari", "18500", "2024-01-04 09:12", "3 nights, 2 adults", "@home", "1 000 000"]
)
def test_ordinary_values_do_not_look_like_contact_details(value: str):
    table = read_csv(f'Notes\n"{value}"\n'.encode())

    assert not column_facts(table)["Notes"].looks_like_contact


def test_reads_the_header_and_every_row():
    table = read_csv(b"Lead ID,Budget\nL1,5000\nL2,12000\n")

    assert table.columns == ["Lead ID", "Budget"]
    assert table.row_count == 2


def test_reads_a_file_saved_with_a_byte_order_mark_and_windows_line_ends():
    table = read_csv(b"\xef\xbb\xbfLead ID,Budget\r\nL1,5000\r\n")

    assert table.columns == ["Lead ID", "Budget"]
    assert table.row_count == 1


def test_blank_lines_are_not_rows():
    assert read_csv(b"Lead ID\nL1\n\nL2\n\n").row_count == 2


def test_quoted_values_may_hold_commas_and_line_breaks():
    table = read_csv(b'Lead ID,Notes\nL1,"Big family, two rooms\nwants a pool"\n')

    assert table.row_count == 1
    assert profile(table)[1].examples == ["Big family, two rooms\nwants a pool"]


def test_profile_gives_each_column_its_first_three_distinct_non_empty_values():
    table = read_csv(b"Lead ID,Channel\nL1,\nL2,Phone\nL3,Phone\nL4,Web form\nL5,Email\nL6,Chat\n")

    assert profile(table) == [
        ColumnProfile(name="Lead ID", examples=["L1", "L2", "L3"]),
        ColumnProfile(name="Channel", examples=["Phone", "Web form", "Email"]),
    ]


def test_a_row_shorter_than_the_header_has_empty_values_for_the_missing_cells():
    table = read_csv(b"Lead ID,Channel\nL1\nL2,Phone\n")

    assert table.row_count == 2
    assert profile(table)[1].examples == ["Phone"]


def test_counts_how_many_rows_use_each_value_of_a_column_most_used_first():
    table = read_csv(
        b"Lead ID,Stage\nL1,New enquiry\nL1,Quote sent\nL2,New enquiry\nL3,New enquiry\n"
        b"L2,Closed lost\nL3,Quote sent\nL4,\n"
    )

    assert count_values(table, "Stage") == [
        ("New enquiry", 3),
        ("Quote sent", 2),
        ("Closed lost", 1),
    ]


def test_values_used_equally_often_are_counted_in_alphabetical_order():
    table = read_csv(b"Stage\nQuote sent\nClosed won\n")

    assert count_values(table, "Stage") == [("Closed won", 1), ("Quote sent", 1)]


@pytest.mark.parametrize("content", [b"", b"   \n\n", b"\xef\xbb\xbf"])
def test_an_empty_file_is_refused(content):
    with pytest.raises(UnreadableFile, match="The file is empty."):
        read_csv(content)


def test_a_header_with_no_rows_below_it_is_refused():
    with pytest.raises(UnreadableFile, match="The file has a header row but no rows below it."):
        read_csv(b"Lead ID,Budget\n")


@pytest.mark.parametrize(
    "first_line",
    [
        b"L1,Ada Lovelace,5000",  # a data row where the header should be
        b"Lead ID,,Budget",  # a column without a name
        b"Lead ID,Budget,Budget",  # two columns with the same name
    ],
)
def test_a_file_whose_first_line_is_not_a_header_row_is_refused(first_line):
    with pytest.raises(UnreadableFile, match="The file has no header row"):
        read_csv(first_line + b"\nL2,Grace Hopper,7000\n")


def test_a_file_that_is_not_text_is_refused():
    with pytest.raises(UnreadableFile, match="The file is not a readable CSV file."):
        read_csv(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe")


def test_a_file_holding_null_characters_is_refused():
    with pytest.raises(UnreadableFile, match="The file is not a readable CSV file."):
        read_csv(b"Lead ID,Budget\nL1,50\x0000\n")


def test_a_file_with_a_value_too_long_to_be_one_cell_is_refused():
    with pytest.raises(UnreadableFile, match="The file is not a readable CSV file."):
        read_csv(b"Lead ID,Notes\nL1," + b"x" * 200_000 + b"\n")
