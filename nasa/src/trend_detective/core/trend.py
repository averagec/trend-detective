"""Trend statistics. Pure functions only: no I/O, no network, no plotting.

Owns: deseasonalising, OLS trend + confidence interval (autocorrelation-adjusted),
Mann-Kendall test, Sen's slope, and area-weighted regional means.
See docs/science-rules.md for the rules these functions implement.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class TrendResult:
    slope: float  # units per time step
    ci_low: float
    ci_high: float
    p_value: float
    n: int
    n_eff: float  # effective sample size after lag-1 autocorrelation
    method: str
    intercept: float = float("nan")  # OLS intercept, for drawing the line (OLS only)

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05


def deseasonalize(values: np.ndarray, period: int = 12) -> np.ndarray:
    """Subtract the mean of each calendar slot (e.g. each month) to get anomalies.

    `values` must start at slot 0 (e.g. January) and be evenly spaced. NaNs are ignored.
    """
    y = np.asarray(values, dtype=float)
    out = y.copy()
    for k in range(period):
        slot = y[k::period]
        out[k::period] = slot - np.nanmean(slot)
    return out


def lag1_autocorr(resid: np.ndarray) -> float:
    r = resid[~np.isnan(resid)]
    if r.size < 3:
        return 0.0
    r = r - r.mean()
    denom = np.dot(r, r)
    return float(np.dot(r[:-1], r[1:]) / denom) if denom > 0 else 0.0


def ols_trend(values: np.ndarray, alpha: float = 0.05) -> TrendResult:
    """Least-squares linear trend with a CI using effective sample size
    n_eff = n (1 - r1) / (1 + r1) (Santer et al. 2000) to account for autocorrelation."""
    y = np.asarray(values, dtype=float)
    t = np.arange(y.size, dtype=float)
    m = ~np.isnan(y)
    t, y = t[m], y[m]
    n = y.size
    if n < 3:
        raise ValueError("need at least 3 non-missing values")
    slope, intercept = np.polyfit(t, y, 1)
    resid = y - (slope * t + intercept)
    r1 = max(lag1_autocorr(resid), 0.0)
    n_eff = max(n * (1 - r1) / (1 + r1), 3.0)
    dof = n_eff - 2
    s2 = np.sum(resid**2) / dof
    se = np.sqrt(s2 / np.sum((t - t.mean()) ** 2))
    tcrit = stats.t.ppf(1 - alpha / 2, dof)
    if se > 0:
        p = 2 * stats.t.sf(abs(slope / se), dof)
    else:  # no residual spread: a flat line has p = 1; any other exact slope has p = 0
        p = 1.0 if slope == 0 else 0.0
    return TrendResult(
        slope,
        slope - tcrit * se,
        slope + tcrit * se,
        float(p),
        n,
        n_eff,
        "ols",
        float(intercept),
    )


def ols_band(
    values: np.ndarray, at: np.ndarray, alpha: float = 0.05
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Confidence band around the OLS line of `ols_trend`, at the time steps `at`.

    Returns (fit, low, high): the line value and the 95% band limits (units of `values`),
    where time is the index into `values` (as in `ols_trend`). It uses the same n_eff and
    degrees of freedom (n_eff - 2) as the slope CI, so the band opens up away from the mean
    time at exactly the rate of that CI:

        var(fit at t) = s^2 / n_eff + se_slope^2 * (t - mean_t)^2

    with s^2 = SSR / (n - 2), the residual variance, and se_slope from `ols_trend`. This is
    the band for the line (where the true trend plausibly lies), not for single months.
    See docs/statistics.md section 4.2.
    """
    y = np.asarray(values, dtype=float)
    fit = ols_trend(y, alpha)  # raises if fewer than 3 values
    t = np.arange(y.size, dtype=float)
    m = ~np.isnan(y)
    t, y = t[m], y[m]
    resid = y - (fit.slope * t + fit.intercept)
    ssr = float(np.sum(resid**2))
    dof = fit.n_eff - 2
    sxx = float(np.sum((t - t.mean()) ** 2))
    level_var = ssr / (fit.n - 2) / fit.n_eff
    slope_var = ssr / dof / sxx
    tcrit = stats.t.ppf(1 - alpha / 2, dof)
    tau = np.asarray(at, dtype=float)
    centre = fit.slope * tau + fit.intercept
    half = tcrit * np.sqrt(level_var + slope_var * (tau - t.mean()) ** 2)
    return centre, centre - half, centre + half


def sens_slope(values: np.ndarray) -> float:
    """Median of all pairwise slopes (robust to outliers)."""
    y = np.asarray(values, dtype=float)
    t = np.arange(y.size)
    m = ~np.isnan(y)
    t, y = t[m], y[m]
    i, j = np.triu_indices(y.size, k=1)
    return float(np.median((y[j] - y[i]) / (t[j] - t[i])))


def mann_kendall(values: np.ndarray) -> TrendResult:
    """Mann-Kendall trend test (tie-corrected, normal approximation) with Sen's slope.

    Assumes independent observations: run on deseasonalised anomalies, and treat
    p-values on strongly autocorrelated series as optimistic (see docs/science-rules.md).
    """
    y = np.asarray(values, dtype=float)
    y = y[~np.isnan(y)]
    n = y.size
    if n < 3:
        raise ValueError("need at least 3 non-missing values")
    i, j = np.triu_indices(n, k=1)
    s = float(np.sum(np.sign(y[j] - y[i])))
    _, counts = np.unique(y, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18
    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0
    p = float(2 * stats.norm.sf(abs(z)))
    slope = sens_slope(y)
    return TrendResult(slope, np.nan, np.nan, p, n, float(n), "mann-kendall")


def area_weighted_mean(field: np.ndarray, lats: np.ndarray) -> float:
    """Mean of a (lat, lon) grid weighted by cos(latitude). NaNs ignored."""
    f = np.asarray(field, dtype=float)
    w = np.cos(np.deg2rad(np.asarray(lats, dtype=float)))[:, None] * np.ones_like(f)
    m = ~np.isnan(f)
    return float(np.sum(f[m] * w[m]) / np.sum(w[m]))
