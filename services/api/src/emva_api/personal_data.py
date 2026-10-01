"""Scrambling what identifies a lead (decision 0010): its email, its phone and its identifier in
the CRM (often its email) are normalised, then SHA-256 hashed, the form the ad platforms'
matching takes, so the raw value is never needed again.

Pure: no I/O.
"""

import enum
import hashlib
import re
from dataclasses import dataclass


class Country(enum.StrEnum):
    """The countries a phone written without an international prefix can be read as from."""

    GB = "GB"
    IE = "IE"


@dataclass(frozen=True)
class Dialling:
    name: str
    calling_code: str
    # Dialled before a national number within the country, dropped in international form.
    trunk_prefix: str
    # Dialled before a calling code from within the country, written in place of "+".
    international_prefix: str


DIALLING: dict[Country, Dialling] = {
    Country.GB: Dialling("United Kingdom", "44", "0", "00"),
    Country.IE: Dialling("Ireland", "353", "0", "00"),
}


def hashed_identifier(written: str) -> str | None:
    """The hash of the lead's identifier trimmed, its case kept; None when there is none."""
    trimmed = written.strip()
    return _sha256(trimmed) if trimmed else None


def hashed_email(written: str) -> str | None:
    """The hash of the email trimmed and lower-cased; None when there is none."""
    normalised = written.strip().lower()
    return _sha256(normalised) if normalised else None


def hashed_phone(written: str, country: Country) -> str | None:
    """The hash of the phone in international form, "+" then digits only; None without digits.

    A number written with "+", or with the country's international prefix ("00"), keeps the
    calling code it is written with. Any other number is national: its trunk prefix ("0") is
    dropped and the country's calling code put before it. A trunk prefix written after a calling
    code on the list ("+44 (0)7700…", "+44 0 7700…") is dropped too.
    """
    digits = re.sub(r"\D", "", written)
    if not digits:
        return None
    dialling = DIALLING[country]
    if written.strip().startswith("+"):
        international = digits
    elif digits.startswith(dialling.international_prefix):
        international = digits[len(dialling.international_prefix) :]
    else:
        national = digits.removeprefix(dialling.trunk_prefix)
        international = dialling.calling_code + national
    for known in DIALLING.values():
        written_with_trunk = known.calling_code + known.trunk_prefix
        if international.startswith(written_with_trunk):
            international = known.calling_code + international[len(written_with_trunk) :]
            break
    return _sha256(f"+{international}")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
