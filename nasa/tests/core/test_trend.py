"""Golden tests: the stats must recover known answers from synthetic data.
These are the project's science sensors. Never weaken them to make a change pass."""
import numpy as np
from scipy import stats

from trend_detective.core.trend import (
    area_weighted_mean,
    deseasonalize,
    mann_kendall,
    ols_trend,
)

RNG = np.random.default_rng(42)
MONTHS = 12 * 20  # 20 years of monthly data


def synthetic(slope_per_month, noise=0.3, seasonal_amp=5.0, n=MONTHS):
    t = np.arange(n)
    season = seasonal_amp * np.sin(2 * np.pi * t / 12)
    return slope_per_month * t + season + RNG.normal(0, noise, n)


def test_recovers_known_trend_after_deseasonalizing():
    y = deseasonalize(synthetic(0.01))
    r = ols_trend(y)
    assert r.ci_low < 0.01 < r.ci_high
    assert r.significant


def test_seasonal_cycle_hides_nothing_once_removed():
    y = synthetic(0.0, seasonal_amp=10.0)
    anomalies = deseasonalize(y)
    assert np.std(anomalies) < 0.5  # only noise left


def test_white_noise_is_rarely_significant():
    hits = sum(ols_trend(RNG.normal(0, 1, MONTHS)).significant for _ in range(200))
    assert hits / 200 < 0.10  # nominal 5%


def test_autocorrelation_widens_ci():
    n = MONTHS
    ar = np.zeros(n)
    for k in range(1, n):
        ar[k] = 0.8 * ar[k - 1] + RNG.normal()
    r = ols_trend(ar)
    assert r.n_eff < r.n / 3


def test_mann_kendall_matches_kendall_tau():
    y = deseasonalize(synthetic(0.005, noise=1.0))
    mk = mann_kendall(y)
    tau = stats.kendalltau(np.arange(y.size), y, method="asymptotic")
    assert np.sign(mk.slope) == np.sign(tau.statistic)
    assert abs(mk.p_value - tau.pvalue) < 0.01


def test_mann_kendall_sens_slope_robust_to_outlier():
    y = 0.02 * np.arange(120.0)
    y[60] = 1000.0
    assert abs(mann_kendall(y).slope - 0.02) < 1e-9


def test_opposite_regional_trends_are_both_detected():
    north = ols_trend(deseasonalize(synthetic(+0.01)))
    south = ols_trend(deseasonalize(synthetic(-0.01)))
    assert north.slope > 0 and south.slope < 0
    assert north.significant and south.significant


def test_area_weighting_downweights_poles():
    lats = np.array([0.0, 80.0])
    field = np.array([[1.0, 1.0], [10.0, 10.0]])
    assert area_weighted_mean(field, lats) < 5.5  # unweighted mean
