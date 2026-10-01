"""Email and phone are normalised, then SHA-256 hashed (decision 0010); so is the lead
identifier. Expected hashes are the SHA-256 of the normalised text, worked out by hand with
`printf %s ... | shasum -a 256`.

A phone is resolved to E.164 (ruling 10): as written when it starts with "+" or "00"; otherwise
from the lead's own country, or failing that a currency of exactly one country; otherwise its
digits as written are hashed and flagged as having no country found.
"""

import pytest

from emva_api.personal_data import (
    HashedPhone,
    hashed_email,
    hashed_identifier,
    hashed_phone,
    phone_region,
)

ADA = "e2c10c5fecf966a1ec3d1429830ec4b04572085147fd88e7317967a95d7c5081"
UK = "b1e7c34f8f2731a143d8b4fdfdaf3a5c07eeae72a9ff3fee323da77936ff2d01"  # +447700900101
KENYAN = "7e68ed1fbff891757a23ef26f54dd9de094c47613a21f736deb30c14b70e8127"  # +254712345678
UK_AS_WRITTEN = "fb7c11e305716cb59aa97f4402039d4fdc9951dcc564f845e0213730560a056e"  # 07700900101
L1001 = "541a70f003a49f0a862aa789732360b74e7f75f6377ccdaa183696b13146c042"  # L-1001


@pytest.mark.parametrize(
    "written",
    [
        "ada.fenwick@example.com",
        "Ada.Fenwick@Example.COM",
        "  ada.fenwick@example.com\t",
        " ADA.FENWICK@EXAMPLE.COM ",
    ],
)
def test_an_email_is_trimmed_and_lower_cased_before_it_is_hashed(written: str):
    assert hashed_email(written) == ADA


@pytest.mark.parametrize("missing", ["", "   ", "\t"])
def test_a_missing_email_has_no_hash(missing: str):
    assert hashed_email(missing) is None


@pytest.mark.parametrize("written", ["L-1001", " L-1001 ", "L-1001\t"])
def test_a_lead_identifier_is_trimmed_and_hashed_but_keeps_its_case(written: str):
    assert hashed_identifier(written) == L1001
    assert hashed_identifier("l-1001") != L1001


# 1. A phone written with "+" or "00" is read as written, whatever else is known.


@pytest.mark.parametrize(
    "written",
    [
        "+447700900101",
        "+44 7700 900101",
        "+44-7700-900-101",
        "+44 (0) 7700 900101",
        "+44 (0)7700 900101",
        "+44 0 7700 900101",
        "0044 7700 900101",
        "00 44 (0) 7700 900101",
        " +44.7700.900101 ",
    ],
)
def test_a_phone_with_an_international_prefix_is_read_as_written(written: str):
    assert hashed_phone(written, None) == HashedPhone(hash=UK, country_found=True)
    assert hashed_phone(written, "KE") == HashedPhone(hash=UK, country_found=True)


# 2. Otherwise the lead's region, from its country or its currency.


def test_a_phone_without_an_international_prefix_is_read_in_the_leads_region():
    assert hashed_phone("07700 900101", "GB") == HashedPhone(hash=UK, country_found=True)
    assert hashed_phone("0712 345678", "KE") == HashedPhone(hash=KENYAN, country_found=True)


@pytest.mark.parametrize(
    "country",
    ["GB", "gb", " GB ", "UK", "United Kingdom", "united kingdom", "+44", "0044", "44"],
)
def test_a_country_is_read_from_its_code_its_name_or_its_dial_code(country: str):
    assert phone_region(country, "") == "GB"


@pytest.mark.parametrize("country", ["KE", "Kenya", "+254", "00254"])
def test_kenya_is_read_however_its_country_is_written(country: str):
    assert phone_region(country, "") == "KE"


@pytest.mark.parametrize("currency", ["GBP", "gbp", " GBP "])
def test_without_a_country_a_currency_of_exactly_one_country_gives_its_region(currency: str):
    assert phone_region("", currency) == "GB"
    assert phone_region("", "KES") == "KE"
    assert phone_region("", "ZAR") == "ZA"


@pytest.mark.parametrize("currency", ["EUR", "USD", "XOF", "AUD", "", "pounds"])
def test_a_currency_shared_by_several_countries_or_unknown_decides_nothing(currency: str):
    assert phone_region("", currency) is None


def test_the_country_decides_before_the_currency():
    assert phone_region("Kenya", "GBP") == "KE"


@pytest.mark.parametrize("country", ["Atlantis", "ZZ", "+999", "Europe"])
def test_a_country_that_is_not_one_falls_back_on_the_currency(country: str):
    assert phone_region(country, "") is None
    assert phone_region(country, "GBP") == "GB"


# 3. Otherwise the digits as written, flagged as having no country found.


def test_with_no_clue_to_the_country_the_digits_as_written_are_hashed_and_flagged():
    assert hashed_phone("07700 900101", None) == HashedPhone(
        hash=UK_AS_WRITTEN, country_found=False
    )


@pytest.mark.parametrize(("written", "region"), [("12", "GB"), ("+44 12", None), ("0012", "GB")])
def test_a_number_that_cannot_be_read_even_with_a_region_is_flagged(written: str, region):
    hashed = hashed_phone(written, region)

    assert hashed is not None and not hashed.country_found


@pytest.mark.parametrize("missing", ["", "  ", "n/a", "+", "()-"])
def test_a_phone_with_no_digits_has_no_hash(missing: str):
    assert hashed_phone(missing, "GB") is None
