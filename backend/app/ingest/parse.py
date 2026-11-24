"""Parsing helpers for scraped Instagram counts."""
from __future__ import annotations

import re

_MULT = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
_RE = re.compile(r"^([0-9][0-9,]*(?:\.[0-9]+)?)\s*([KMB]?)$", re.IGNORECASE)


def parse_count(s: str | int | float | None) -> int | None:
    """"34.4M" -> 34400000, "5,181" -> 5181, "22.7K" -> 22700, None/"" -> None."""
    if s is None:
        return None
    if isinstance(s, bool):
        return None
    if isinstance(s, (int, float)):
        return int(s)
    text = str(s).strip().replace(" ", "").replace(" ", "")
    if not text:
        return None
    m = _RE.match(text)
    if not m:
        return None
    num, suffix = m.group(1).replace(",", ""), m.group(2).upper()
    # round() avoids float artefacts like 22.7 * 1000 = 22699.999...
    return int(round(float(num) * _MULT[suffix]))
