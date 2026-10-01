"""Scrambling what identifies a lead (decision 0010): its email, its phone and its identifier in
the CRM (often its email) are normalised, then SHA-256 hashed, the form the ad platforms'
matching takes, so the raw value is never needed again.

A phone is resolved to E.164 (ruling 10 of the phase 1 PRD), deterministically:
1. written with "+" or "00", it is read as written;
2. otherwise it is read in the lead's region, from the lead's own country or, failing that, a
   currency used by exactly one country;
3. otherwise, or when it cannot be read as a possible number, the digits as written are hashed
   and flagged as having no country found.

Pure: no I/O.
"""

import hashlib
import re
from dataclasses import dataclass

import phonenumbers
from phonenumbers.geodata.locale import LOCALE_DATA

# Currencies used by exactly one country (ruling 10). A currency several countries use (EUR,
# USD, XOF, AUD...) is not here, and says nothing about a lead's country.
SINGLE_COUNTRY_CURRENCIES: dict[str, str] = {
    "AED": "AE",
    "CAD": "CA",
    "GBP": "GB",
    "JPY": "JP",
    "KES": "KE",
    "RWF": "RW",
    "SEK": "SE",
    "TZS": "TZ",
    "UGX": "UG",
}

# Names a country column commonly holds that are not the country's English name or ISO code.
_ALSO_CALLED: dict[str, str] = {
    "uk": "GB",
    "great britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "usa": "US",
    "united states of america": "US",
}


def _english_name(region: str) -> str:
    names = LOCALE_DATA.get(region, {})
    name = names.get("en", "")
    return names.get(name[1:], "") if name.startswith("*") else name


_REGIONS: dict[str, str] = {
    **{_english_name(region).casefold(): region for region in phonenumbers.SUPPORTED_REGIONS},
    **_ALSO_CALLED,
}
_REGIONS.pop("", None)


@dataclass(frozen=True)
class HashedPhone:
    hash: str
    # False when the phone's country could not be found, so its digits as written were hashed.
    country_found: bool


def hashed_identifier(written: str) -> str | None:
    """The hash of the lead's identifier trimmed, its case kept; None when there is none."""
    trimmed = written.strip()
    return _sha256(trimmed) if trimmed else None


def hashed_email(written: str) -> str | None:
    """The hash of the email trimmed and lower-cased; None when there is none."""
    normalised = written.strip().lower()
    return _sha256(normalised) if normalised else None


def phone_region(country: str, currency: str) -> str | None:
    """The region to read a lead's phone in: from its country (an ISO code, a name, or a dial
    code such as "+254"), or failing that a currency used by exactly one country."""
    return _country(country) or SINGLE_COUNTRY_CURRENCIES.get(currency.strip().upper())


def hashed_phone(written: str, region: str | None) -> HashedPhone | None:
    """The hash of the phone in E.164; None when it has no digits."""
    digits = re.sub(r"\D", "", written)
    if not digits:
        return None
    text = written.strip()
    if text.startswith("00"):
        text = "+" + text[2:]
    international = text.startswith("+")
    if international or region is not None:
        try:
            number = phonenumbers.parse(text, None if international else region)
        except phonenumbers.NumberParseException:
            number = None
        if number is not None and phonenumbers.is_possible_number(number):
            e164 = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
            return HashedPhone(hash=_sha256(e164), country_found=True)
    return HashedPhone(hash=_sha256(digits), country_found=False)


def _country(written: str) -> str | None:
    text = written.strip()
    dial_code = re.fullmatch(r"(?:\+|00)?(\d{1,3})", text)
    if dial_code:
        region = phonenumbers.region_code_for_country_code(int(dial_code[1]))
        return None if region == phonenumbers.UNKNOWN_REGION else region
    if text.upper() in phonenumbers.SUPPORTED_REGIONS:
        return text.upper()
    return _REGIONS.get(text.casefold())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
