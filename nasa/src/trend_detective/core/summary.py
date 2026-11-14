"""Plain-language trend summary for one monthly series. Pure functions only: no I/O.

Owns: running the two tests (OLS with autocorrelation-adjusted CI, Mann-Kendall with Sen's
slope) on deseasonalised anomalies, the record-length and data-gap checks, and the sentence
shown to users. Every number comes from core/trend.py. See docs/statistics.md and
docs/science-rules.md for the rules these implement.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trend_detective.core.trend import deseasonalize, mann_kendall, ols_band, ols_trend

MONTHS_PER_DECADE = 120
MIN_YEARS = 10  # science rule 2: show a warning under 10 years of monthly data
MAX_MISSING_FRACTION = 0.10
BAND_OFFSET = 6  # months after January: where each year's band is evaluated (the yearly bar)


@dataclass(frozen=True)
class Summary:
    n_months: int  # months with a value
    n_years: float
    ols_per_decade: float  # slope, units per decade
    ols_ci_per_decade: tuple[float, float]  # 95% CI, autocorrelation-adjusted
    ols_p: float
    ols_significant: bool
    sen_per_decade: float  # Sen's slope, units per decade (Mann-Kendall's slope)
    mk_p: float  # unadjusted for autocorrelation, see docs/statistics.md
    mk_significant: bool
    tests_agree: bool
    warnings: tuple[str, ...]
    sentence: str
    ols_intercept: float = float("nan")  # intercept of the OLS line on the anomalies
    ols_slope_per_month: float = float("nan")  # same slope as ols_per_decade / 120
    # 95% band around the OLS line, one row per year of the series: (years after the first year,
    # line value, lower, upper), in the unit of the anomalies. Empty when there is no trend.
    ols_band_by_year: tuple[tuple[int, float, float, float], ...] = ()


def summarise(series: np.ndarray, unit: str, label: str) -> Summary:
    """Summarise one monthly series. `series` must start in January, one value per month
    (NaN where a month is missing)."""
    y = np.asarray(series, dtype=float)
    n_valid = int(np.isfinite(y).sum())
    years = n_valid / 12.0
    warnings: list[str] = []
    if years < MIN_YEARS:
        warnings.append(
            f"Only {years:.1f} years of data; trends under {MIN_YEARS} years are not reliable."
        )
    missing = 1.0 - n_valid / y.size
    if missing > MAX_MISSING_FRACTION:
        warnings.append(f"{missing:.0%} of months are missing.")
    if n_valid < 24:  # with under two years each calendar month has at most one value
        nan = float("nan")
        return Summary(
            n_months=n_valid,
            n_years=years,
            ols_per_decade=nan,
            ols_ci_per_decade=(nan, nan),
            ols_p=nan,
            ols_significant=False,
            sen_per_decade=nan,
            mk_p=nan,
            mk_significant=False,
            tests_agree=False,
            warnings=tuple(warnings),
            sentence=f"{label}: not enough data for a trend (need at least two years).",
        )

    anomalies = deseasonalize(y)  # science rule 1
    ols = ols_trend(anomalies)  # science rule 3
    mk = mann_kendall(anomalies)

    # One point per year, only where it lies inside the record (no extrapolation).
    year_offsets = np.arange((y.size - 1 - BAND_OFFSET) // 12 + 1)  # y.size >= 24 here
    fit, low, high = ols_band(anomalies, year_offsets * 12 + BAND_OFFSET)
    band = tuple(
        (int(k), float(f), float(lo), float(hi))
        for k, f, lo, hi in zip(year_offsets, fit, low, high, strict=True)
    )

    per = MONTHS_PER_DECADE
    ols_per = ols.slope * per
    ci = (ols.ci_low * per, ols.ci_high * per)
    sen_per = mk.slope * per
    agree = bool(np.sign(ols.slope) == np.sign(mk.slope) and ols.significant == (mk.p_value < 0.05))
    if not agree:
        warnings.append(
            "The two tests disagree: check for outliers or a non-linear pattern before trusting it."
        )

    if ols.significant:
        verb = "rose" if ols_per > 0 else "fell"
        sentence = (
            f"{label} {verb} by {abs(ols_per):.2f} {unit} per decade "
            f"(95% CI {ci[0]:+.2f} to {ci[1]:+.2f}), statistically significant at 95%."
        )
    else:
        sentence = (
            f"{label}: no significant trend detected (yet). "
            f"The estimated change is {ols_per:+.2f} {unit} per decade."
        )

    return Summary(
        n_months=n_valid,
        n_years=years,
        ols_per_decade=ols_per,
        ols_ci_per_decade=ci,
        ols_p=ols.p_value,
        ols_significant=ols.significant,
        sen_per_decade=sen_per,
        mk_p=mk.p_value,
        mk_significant=mk.p_value < 0.05,
        tests_agree=agree,
        warnings=tuple(warnings),
        sentence=sentence,
        ols_intercept=ols.intercept,
        ols_slope_per_month=ols.slope,
        ols_band_by_year=band,
    )
