"""Scrambling a lead's email and phone (decision 0010): each is normalised, then SHA-256 hashed,
the form the ad platforms' matching takes, so the raw value is never needed again.

Pure: no I/O.
"""

import hashlib
import re


def hashed_email(written: str) -> str | None:
    """The hash of the email trimmed and lower-cased; None when there is none."""
    normalised = written.strip().lower()
    return _sha256(normalised) if normalised else None


def hashed_phone(written: str) -> str | None:
    """The hash of the phone as its digits only, after a "+" when it is written with one.

    A number written with a leading "+" is in international form; a "(0)" written in it (the
    national trunk zero, as in "+44 (0)7700 900101") is dropped. A number without a "+" is kept
    as its digits: its country is not known, so none is guessed. None when there are no digits.
    """
    text = written.strip()
    international = text.startswith("+")
    if international:
        text = text.replace("(0)", "")
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    return _sha256(f"+{digits}" if international else digits)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
