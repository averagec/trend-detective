"""Years of record needed to detect a trend of a given size. Pure functions: no I/O, no network.

Method: a simulation, not a closed formula. Synthetic AR(1) noise with the observed standard
deviation and lag-1 autocorrelation, plus a linear trend of the observed size. For each record
length we count how often core.trend.ols_trend finds a significant trend (p < alpha) with the
right sign. The shortest record that reaches the target probability is returned (bisection).

This is our estimate for the dashboard. It is NOT the Weatherhead et al. (1998) equation, which
could not be read when this was written. See docs/stats_trend.md.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

from trend_detective.core.trend import deseasonalize, lag1_autocorr, ols_trend

MIN_YEARS = 3


def noise_params(series: np.ndarray, steps_per_year: int) -> tuple[float, float]:
    """(standard deviation, lag-1 autocorrelation) of the anomalies. Monthly series are
    deseasonalised first; yearly series are used as they are."""
    y = np.asarray(series, dtype=float)
    anomalies = deseasonalize(y) if steps_per_year == 12 else y
    finite = anomalies[np.isfinite(anomalies)]
    if finite.size < 3:
        return float("nan"), float("nan")
    sigma = float(finite.std(ddof=1))
    phi = float(np.clip(lag1_autocorr(anomalies), 0.0, 0.95))
    return sigma, phi


def years_needed(
    slope_per_decade: float,
    sigma: float,
    phi: float,
    steps_per_year: int = 12,
    probability: float = 0.9,
    alpha: float = 0.05,
    n_sims: int = 200,
    max_years: int = 100,
    seed: int = 0,
) -> float | None:
    """Shortest record (in years) that detects a trend of this size with the given probability.

    Returns None when the trend is zero or not a number, when the noise is not a number, or when
    even max_years is not enough.
    """
    if not np.isfinite(slope_per_decade) or slope_per_decade == 0:
        return None
    if not (np.isfinite(sigma) and np.isfinite(phi)):
        return None
    slope_step = slope_per_decade / (10.0 * steps_per_year)  # per month or per year
    rng = np.random.default_rng(seed)
    e_sd = max(sigma, 1e-12) * np.sqrt(max(1.0 - phi**2, 1e-12))

    def power(n_years: int) -> float:
        n = n_years * steps_per_year
        t = np.arange(n, dtype=float)
        hits = 0
        for _ in range(n_sims):
            e = rng.normal(0.0, e_sd, n)
            noise = lfilter([1.0], [1.0, -phi], e) if phi > 0 else e
            y = slope_step * t + noise
            fit = ols_trend(y, alpha=alpha)
            if fit.p_value < alpha and np.sign(fit.slope) == np.sign(slope_step):
                hits += 1
        return hits / n_sims

    if power(max_years) < probability:
        return None
    lo, hi = MIN_YEARS, max_years  # power(hi) is at or above the target
    while lo < hi:
        mid = (lo + hi) // 2
        if power(mid) >= probability:
            hi = mid
        else:
            lo = mid + 1
    return float(lo)
