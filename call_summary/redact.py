"""Privacy first: strip identifying details before a transcript leaves your system.

The summary doesn't need a phone number, an ID number or an email address to be
useful, so we replace them with placeholders before calling any AI model.
"""
from __future__ import annotations

import re

PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    # Israeli-style mobile / landline, with or without separators or +972
    ("PHONE", re.compile(r"(?:\+972[-\s]?|0)(?:[2-9]\d?)[-\s]?\d{3}[-\s]?\d{4}\b")),
    # 9-digit ID numbers (and other long digit runs such as bank accounts)
    ("ID", re.compile(r"\b\d{8,10}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
]


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Return the redacted text and a count of what was removed."""
    counts: dict[str, int] = {}
    for label, pattern in PATTERNS:
        text, n = pattern.subn(f"[{label}]", text)
        if n:
            counts[label] = n
    return text, counts
