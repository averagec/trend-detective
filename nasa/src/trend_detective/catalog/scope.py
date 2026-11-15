"""The project's analysis window: 1980 to 2018. One place for it; every output is limited to it.

Owns: the window and the helper that clamps a requested range to it. Text only; no statistics.
Why 2018: GDIS (the disaster records) ends in 2018, and the flood and drought comparison needs the
same years as the climate data.
"""

from __future__ import annotations

FIRST_YEAR = 1980
LAST_YEAR = 2018


def clamp(first: int | None, last: int | None) -> tuple[int, int]:
    """The requested years limited to the project window. Missing ends take the window's ends.

    Raises ValueError if the range does not overlap the window, or if first is after last.
    """
    lo = FIRST_YEAR if first is None else max(int(first), FIRST_YEAR)
    hi = LAST_YEAR if last is None else min(int(last), LAST_YEAR)
    if first is not None and last is not None and first > last:
        raise ValueError("from must be on or before to")
    if lo > hi:
        raise ValueError(f"the project covers {FIRST_YEAR} to {LAST_YEAR} only")
    return lo, hi


def in_scope(year: int) -> bool:
    return FIRST_YEAR <= year <= LAST_YEAR
