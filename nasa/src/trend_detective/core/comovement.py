"""Co-movement between a driving factor and rainfall. Pure functions only: no I/O, no network.

Owns: the correlation of two deseasonalised monthly series, with the same autocorrelation
adjustment as core/trend.py, and the slope and implied change in rainfall for a factor anomaly.

Co-movement is not a cause. Results must be shown as "moved together", never as "caused by"
(docs/science-rules.md, rule 7). Only linear relationships are reported (rule 9).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from trend_detective.core.trend import lag1_autocorr

MIN_OVERLAP = 10  # months where both series have a value


@dataclass(frozen=True)
class Comovement:
    r: float  # Pearson correlation of the anomalies
    p_value: float  # two-sided, with the effective sample size
    n: int  # months where both series have a value
    n_eff: float  # effective sample size after lag-1 autocorrelation
    slope: float  # rainfall units per factor unit (least squares)
    period_anomaly: float  # factor anomaly averaged over the chosen months (factor units)
    implied_change: float  # slope x period_anomaly, in rainfall units (co-movement only)


def comovement(
    rain_anomaly: np.ndarray, factor_anomaly: np.ndarray, period_indices: list[int]
) -> Comovement:
    """Co-movement of a factor's anomalies with rainfall anomalies over their shared months.

    Both inputs are deseasonalised (core/trend.deseasonalize) on the same monthly timeline, with
    NaN where a month is missing. `period_indices` are the timeline positions of the chosen period.
    """
    y = np.asarray(rain_anomaly, dtype=float)
    x = np.asarray(factor_anomaly, dtype=float)
    if x.shape != y.shape:
        raise ValueError("the two series must be on the same monthly timeline")
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < MIN_OVERLAP:
        raise ValueError(f"the series share {n} month(s); at least {MIN_OVERLAP} are needed")
    xs, ys = x[ok], y[ok]
    if np.std(xs) == 0 or np.std(ys) == 0:
        raise ValueError("a series has no variation over the shared months")

    r = float(np.corrcoef(xs, ys)[0, 1])
    rho = float(np.clip(lag1_autocorr(x) * lag1_autocorr(y), -0.99, 0.99))
    n_eff = max(n * (1 - rho) / (1 + rho), 3.0)
    dof = n_eff - 2
    r2 = min(r * r, 1 - 1e-12)
    t_stat = r * np.sqrt(dof / (1 - r2))
    p = float(2 * stats.t.sf(abs(t_stat), dof))

    slope = float(np.polyfit(xs, ys, 1)[0])
    period = x[np.asarray(period_indices, dtype=int)]
    period_anomaly = float(np.nanmean(period)) if np.isfinite(period).any() else float("nan")
    implied = slope * period_anomaly
    return Comovement(r, p, n, float(n_eff), slope, period_anomaly, float(implied))
