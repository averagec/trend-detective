"""Flood and drought events for one city and one month or year. Pure functions: no I/O, no network.

Owns: where a month or year sits in its own climate (percentile against the same calendar month,
or against annual totals), the amount and percent change against the climatological median, the
peak month, the trend of the rainfall rate, and the call (one-time event, extreme within a trend,
or not unusual). Rules: docs/science-rules.md and docs/statistics.md §4.5.

Inputs are monthly series on one timeline that starts in January, with NaN for missing months:
  totals : rainfall total per month, mm (rate x days in month)
  rate   : rainfall rate per month, mm/day (the trend is tested on this)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trend_detective.core.trend import deseasonalize, ols_trend

EXTREME_DRY = 10.0  # percentile at or below this is a dry extreme (drought)
EXTREME_WET = 90.0  # percentile at or above this is a wet extreme (flood)
MONTHS_PER_DECADE = 120
MIN_YEARS = 10  # science rule 2


@dataclass(frozen=True)
class MonthCall:
    index: int  # position on the monthly timeline (0 = first January)
    total_mm: float
    median_mm: float  # median of the same calendar month over the record
    percent: float  # 100 x (total - median) / median
    percentile: float  # where this month sits among the same calendar month, 0 to 100


@dataclass(frozen=True)
class EventResult:
    incident: str  # "flood" or "drought"
    kind: str  # "month" or "year"
    observed_mm: float  # period total (a month or a complete year)
    median_mm: float  # climatological median of the period total
    amount_mm: float  # observed minus median; negative means drier
    percent: float  # 100 x amount / median
    percentile: float  # the period total against its own baseline, 0 to 100
    extreme: bool  # in the direction of the incident, beyond the 10th or 90th percentile
    months: tuple[MonthCall, ...]
    peak: MonthCall | None  # where and when in the period the signal was strongest
    trend_slope_per_decade: float  # mm/day per decade, on the monthly rate
    trend_p_value: float
    trend_direction: str  # "wetter", "drier" or "none" (only when significant at 95%)
    call: str  # "one_time_event", "extreme_in_trend" or "not_unusual"
    sentence: str
    warnings: tuple[str, ...]


def percentile_rank(value: float, baseline: np.ndarray) -> float:
    """Share of the baseline values at or below `value`, in percent."""
    b = np.asarray(baseline, dtype=float)
    b = b[np.isfinite(b)]
    if b.size == 0 or not np.isfinite(value):
        return float("nan")
    return float(100.0 * np.mean(b <= value))


def same_month_values(totals: np.ndarray, index: int) -> np.ndarray:
    """All finite values of the calendar month of timeline position `index`."""
    vals = np.asarray(totals, dtype=float)[index % 12 :: 12]
    return vals[np.isfinite(vals)]


def complete_annual_totals(totals: np.ndarray) -> np.ndarray:
    """Sum of each calendar year that has all 12 months. Partial years are left out."""
    t = np.asarray(totals, dtype=float)
    years = t.size // 12
    blocks = t[: years * 12].reshape(years, 12)
    complete = np.all(np.isfinite(blocks), axis=1)
    return blocks[complete].sum(axis=1)


def _percent(amount: float, median: float) -> float:
    return float(100.0 * amount / median) if np.isfinite(median) and median > 0 else float("nan")


def _is_extreme(incident: str, percentile: float) -> bool:
    if not np.isfinite(percentile):
        return False
    return percentile >= EXTREME_WET if incident == "flood" else percentile <= EXTREME_DRY


def assess(
    totals: np.ndarray,
    rate: np.ndarray,
    indices: list[int],
    incident: str,
    kind: str,
) -> EventResult:
    """Classify a chosen month (kind "month", one index) or a complete year (kind "year")."""
    if incident not in ("flood", "drought"):
        raise ValueError("incident must be 'flood' or 'drought'")
    if kind == "month" and len(indices) != 1:
        raise ValueError("a month needs exactly one index")
    if kind == "year" and len(indices) != 12:
        raise ValueError("a year needs twelve indices")
    t = np.asarray(totals, dtype=float)
    warnings: list[str] = []

    calls: list[MonthCall] = []
    for i in indices:
        base = same_month_values(t, i)
        med = float(np.median(base)) if base.size else float("nan")
        x = float(t[i])
        if base.size < MIN_YEARS:
            warnings.append(f"Only {base.size} years of this calendar month; the baseline is weak.")
        calls.append(
            MonthCall(i, x, med, _percent(x - med, med), percentile_rank(x, base))
        )

    if kind == "month":
        only = calls[0]
        observed, median = only.total_mm, only.median_mm
        percentile = only.percentile
    else:
        vals = t[np.asarray(indices)]
        observed = float(vals.sum()) if np.all(np.isfinite(vals)) else float("nan")
        if not np.isfinite(observed):
            warnings.append("The chosen year has missing months, so its total is not reliable.")
        annual = complete_annual_totals(t)
        if annual.size < MIN_YEARS:
            warnings.append(f"Only {annual.size} complete years; the yearly baseline is weak.")
        median = float(np.median(annual)) if annual.size else float("nan")
        percentile = percentile_rank(observed, annual)

    amount = observed - median if np.isfinite(observed) and np.isfinite(median) else float("nan")
    percent = _percent(amount, median)
    extreme = _is_extreme(incident, percentile)

    if incident == "flood":
        peak = max(calls, key=lambda c: c.percentile if np.isfinite(c.percentile) else -1.0)
    else:
        peak = min(calls, key=lambda c: c.percentile if np.isfinite(c.percentile) else 101.0)

    rate_anom = deseasonalize(np.asarray(rate, dtype=float))
    finite_rate = np.isfinite(rate_anom)
    if finite_rate.sum() >= 3:
        trend = ols_trend(rate_anom)
        slope_decade = float(trend.slope * MONTHS_PER_DECADE)
        p = float(trend.p_value)
    else:
        slope_decade, p = float("nan"), float("nan")
    years = int(np.isfinite(np.asarray(rate, dtype=float)).sum() / 12)
    if years < MIN_YEARS:
        warnings.append(f"Only {years} years of monthly data; the trend is not reliable.")
    significant = bool(np.isfinite(p) and p < 0.05)
    if significant and slope_decade > 0:
        direction = "wetter"
    elif significant and slope_decade < 0:
        direction = "drier"
    else:
        direction = "none"

    same_way_trend = (incident == "flood" and direction == "wetter") or (
        incident == "drought" and direction == "drier"
    )
    if not extreme:
        call = "not_unusual"
    elif same_way_trend:
        call = "extreme_in_trend"
    else:
        call = "one_time_event"

    word = "month" if kind == "month" else "year"
    if call == "not_unusual":
        sentence = f"This {word} is not unusual for {incident} conditions."
    elif call == "one_time_event":
        sentence = (
            f"This {word} is an extreme {incident} ({percentile:.0f}th percentile), "
            "with no significant trend in the same direction: a one-time event."
        )
    else:
        sentence = (
            f"This {word} is an extreme {incident} ({percentile:.0f}th percentile), "
            f"in line with a significant {direction} trend."
        )

    return EventResult(
        incident=incident,
        kind=kind,
        observed_mm=observed,
        median_mm=median,
        amount_mm=float(amount),
        percent=percent,
        percentile=percentile,
        extreme=bool(extreme),
        months=tuple(calls),
        peak=peak,
        trend_slope_per_decade=slope_decade,
        trend_p_value=p,
        trend_direction=direction,
        call=call,
        sentence=sentence,
        warnings=tuple(warnings),
    )
