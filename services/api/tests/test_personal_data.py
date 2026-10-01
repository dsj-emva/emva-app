"""Email and phone are normalised, then SHA-256 hashed (decision 0010); expected hashes are
the SHA-256 of the normalised text, worked out by hand with `printf %s ... | shasum -a 256`."""

import pytest

from emva_api.personal_data import hashed_email, hashed_phone

ADA = "e2c10c5fecf966a1ec3d1429830ec4b04572085147fd88e7317967a95d7c5081"
PHONE = "b1e7c34f8f2731a143d8b4fdfdaf3a5c07eeae72a9ff3fee323da77936ff2d01"


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
        "+44 (0)7700 900101",
        "+44-7700-900-101",
        " +44 (7700) 900 101 ",
        "+44.7700.900101",
    ],
)
def test_a_phone_in_international_form_keeps_its_plus_and_digits_only(written: str):
    assert hashed_phone(written) == PHONE


def test_a_phone_written_without_a_country_is_kept_as_its_digits_and_no_country_is_guessed():
    without_country = hashed_phone("07700 900101")

    assert without_country == hashed_phone("07700900101")
    assert without_country != PHONE
    assert without_country != hashed_phone("+4407700900101")


def test_a_plus_that_is_not_leading_is_dropped():
    assert hashed_phone("44 + 7700 900101") == hashed_phone("447700900101")


@pytest.mark.parametrize("missing", ["", "  ", "n/a", "+", "()-"])
def test_a_phone_with_no_digits_has_no_hash(missing: str):
    assert hashed_phone(missing) is None
