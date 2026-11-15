"""Trend in yearly event counts (for example GDIS floods per cell per year). Pure functions only.

Owns: the Sen slope per decade and the Mann-Kendall test on counts, plus the plain-language
warnings. Counts are not normal, so OLS is not used here; both functions are rank-based and handle
ties (core/trend.py). No I/O, no network.

Why no OLS: a count series with many zero years does not fit a straight line. The rank test does
not assume a distribution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trend_detective.core.trend import mann_kendall, sens_slope

YEARS_PER_DECADE = 10
MIN_YEARS = 10
MAX_ZERO_SHARE = 0.5


@dataclass(frozen=True)
class CountTrend:
    n_years: int
    total: float
    mean_per_year: float
    zero_share: float
    sen_per_decade: float  # change in events per decade
    mk_p: float  # Mann-Kendall p-value (two-sided, normal approximation)
    significant: bool  # p < 0.05 before any correction across cells
    direction: str  # "rise", "fall" or "none"
    warnings: tuple[str, ...]


def count_trend(counts: np.ndarray) -> CountTrend:
    """Trend of one yearly count series. `counts` has one value per year, in order."""
    y = np.asarray(counts, dtype=float)
    n = int(y.size)
    if n < 3:
        raise ValueError("need at least 3 years of counts")
    zero_share = float(np.mean(y == 0))
    warnings: list[str] = []
    if n < MIN_YEARS:
        warnings.append(
            f"Only {n} years of counts; a trend over fewer than 10 years is not reliable."
        )
    if zero_share > MAX_ZERO_SHARE:
        warnings.append(
            f"{zero_share:.0%} of years have no events, so the trend rests on a few years."
        )
    mk = mann_kendall(y)
    sen = sens_slope(y) * YEARS_PER_DECADE
    significant = bool(mk.p_value < 0.05)
    direction = "none"
    if significant:
        direction = "rise" if sen > 0 else "fall" if sen < 0 else "none"
    return CountTrend(
        n_years=n,
        total=float(y.sum()),
        mean_per_year=float(y.mean()),
        zero_share=zero_share,
        sen_per_decade=float(sen),
        mk_p=float(mk.p_value),
        significant=significant,
        direction=direction,
        warnings=tuple(warnings),
    )
