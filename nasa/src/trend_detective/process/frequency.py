"""Yearly aggregation of monthly series. Owns: turning monthly values into annual means under a
completeness rule. Averages only: no trend statistics here (those come from core/).

Rule (proposed, docs/stats_trend.md): a year counts only when at least MIN_MONTHS of its 12 months
have a value. Otherwise the year is NaN, so a short year cannot pull the trend.
"""

from __future__ import annotations

import numpy as np

MIN_MONTHS = 10


def to_yearly(
    periods: list[str], values: np.ndarray, min_months: int = MIN_MONTHS
) -> tuple[list[int], np.ndarray]:
    """Annual means of a monthly series. `periods` is 'YYYY-MM' or 'YYYYMM', one per value.

    Returns (years, annual values). A year with fewer than `min_months` valid months is NaN.
    """
    v = np.asarray(values, dtype=float)
    if len(periods) != v.size:
        raise ValueError("periods and values must have the same length")
    years = sorted({int(p[:4]) for p in periods})
    out = np.full(len(years), np.nan)
    for k, year in enumerate(years):
        idx = [i for i, p in enumerate(periods) if int(p[:4]) == year]
        vals = v[idx]
        ok = vals[np.isfinite(vals)]
        if ok.size >= min_months:
            out[k] = float(ok.mean())
    return years, out
