"""Email and phone are normalised, then SHA-256 hashed (decision 0010); so is the lead
identifier. Expected hashes are the SHA-256 of the normalised text, worked out by hand with
`printf %s ... | shasum -a 256`."""

import pytest

from emva_api.personal_data import Country, hashed_email, hashed_identifier, hashed_phone

ADA = "e2c10c5fecf966a1ec3d1429830ec4b04572085147fd88e7317967a95d7c5081"
PHONE = "b1e7c34f8f2731a143d8b4fdfdaf3a5c07eeae72a9ff3fee323da77936ff2d01"  # +447700900101
IRISH_PHONE = "a637b5abcabb658ef3805201d8687a52c201a74f2802933fa490c0c4b8c50dd7"  # +353871234567
FRENCH_PHONE = "42d573cfc315801d4cd8eddd5416b416a0bf298b9b9e12d6b07442c91db42bd8"  # +33612345678
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


@pytest.mark.parametrize(
    "written",
    [
        "+447700900101",
        "+44 7700 900101",
        "+44-7700-900-101",
        "+44.7700.900101",
        " +44 (7700) 900 101 ",
        "+44 (0)7700 900101",
        "+44 0 7700 900101",
        "+440 7700 900101",
        "0044 7700 900101",
        "00 44 (0) 7700 900101",
        "07700 900101",
        "07700900101",
        "(07700) 900101",
        "7700 900101",
    ],
)
def test_a_uk_phone_however_written_is_hashed_in_international_form(written: str):
    assert hashed_phone(written, Country.GB) == PHONE


def test_a_phone_without_an_international_prefix_takes_the_default_country():
    assert hashed_phone("087 123 4567", Country.IE) == IRISH_PHONE
    assert hashed_phone("087 123 4567", Country.GB) != IRISH_PHONE


def test_a_phone_with_an_international_prefix_keeps_its_own_country():
    assert hashed_phone("+44 7700 900101", Country.IE) == PHONE
    assert hashed_phone("0044 7700 900101", Country.IE) == PHONE
    assert hashed_phone("+353 (0)87 123 4567", Country.GB) == IRISH_PHONE


def test_a_phone_from_a_country_not_on_the_list_is_kept_as_written_with_its_code():
    assert hashed_phone("+33 6 12 34 56 78", Country.GB) == FRENCH_PHONE
    assert hashed_phone("0033 6 12 34 56 78", Country.GB) == FRENCH_PHONE


@pytest.mark.parametrize("missing", ["", "  ", "n/a", "+", "()-"])
def test_a_phone_with_no_digits_has_no_hash(missing: str):
    assert hashed_phone(missing, Country.GB) is None


@pytest.mark.parametrize("written", ["L-1001", " L-1001 ", "L-1001\t"])
def test_a_lead_identifier_is_trimmed_and_hashed_but_keeps_its_case(written: str):
    assert hashed_identifier(written) == L1001
    assert hashed_identifier("l-1001") != L1001
