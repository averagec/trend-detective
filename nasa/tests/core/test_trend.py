"""Golden tests: the stats must recover known answers from synthetic data.
These are the project's science sensors. Never weaken them to make a change pass."""

import numpy as np
from scipy import stats

from trend_detective.core.trend import (
    area_weighted_mean,
    benjamini_hochberg,
    deseasonalize,
    mann_kendall,
    ols_band,
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


def test_band_golden_values_on_a_hand_worked_series():
    # y = [0, 1, 0, 1, 0]: slope 0, intercept 0.4, SSR 1.2, n = n_eff = 5, Sxx = 10, mean t = 2.
    # var(fit at t) = (1.2 / 3) / 5 + (1.2 / 3 / 10) (t - 2)^2, tcrit(0.975, 3 dof) = 3.18245.
    y = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
    fit, low, high = ols_band(y, np.array([2.0, 0.0, 4.0, 6.0]))
    np.testing.assert_allclose(fit, 0.4, atol=1e-12)
    np.testing.assert_allclose(high - fit, [0.9001317, 1.5590739, 1.5590739, 2.7003952], rtol=1e-6)
    np.testing.assert_allclose(fit - low, high - fit, rtol=1e-12)  # symmetric about the line


def test_band_opens_at_the_rate_of_the_slope_ci():
    y = deseasonalize(synthetic(0.004, noise=0.5))
    r = ols_trend(y)
    mean_t = (y.size - 1) / 2
    at = np.array([mean_t, 0.0, y.size - 1.0])
    fit, low, high = ols_band(y, at)
    half = (high - low) / 2
    slope_half = (r.ci_high - r.ci_low) / 2
    np.testing.assert_allclose(fit, r.slope * at + r.intercept, atol=1e-12)
    for k in (1, 2):  # away from the mean the extra width is exactly the slope CI times distance
        np.testing.assert_allclose(
            half[k] ** 2, half[0] ** 2 + (slope_half * (at[k] - mean_t)) ** 2, rtol=1e-9
        )
    assert half[0] < half[1] and half[0] < half[2]  # narrowest at the middle of the record


def test_band_is_wider_when_anomalies_are_autocorrelated():
    rng = np.random.default_rng(7)
    n = MONTHS
    white = rng.normal(0, 1, n)
    ar = np.zeros(n)
    for k in range(1, n):
        ar[k] = 0.8 * ar[k - 1] + rng.normal()
    mid = np.array([(n - 1) / 2])
    for series in (white, ar):
        _, low, high = ols_band(series, mid)
        sigma = np.std(series - np.polyval(np.polyfit(np.arange(n), series, 1), np.arange(n)))
        naive_half = stats.t.ppf(0.975, n - 2) * sigma / np.sqrt(n)
        if series is white:
            assert (high - low)[0] / 2 < 1.5 * naive_half
        else:
            assert (high - low)[0] / 2 > 2.0 * naive_half  # n_eff is far below n


def test_band_covers_the_true_line_about_95_percent_of_the_time():
    rng = np.random.default_rng(2026)
    n, hits, runs = 240, 0, 400
    t = np.arange(n)
    for _ in range(runs):
        y = 0.01 * t + rng.normal(0, 1, n)
        _, low, high = ols_band(y, np.array([n / 4]))
        hits += low[0] <= 0.01 * (n / 4) <= high[0]
    assert 0.90 <= hits / runs <= 0.99


def test_band_ignores_missing_months_but_keeps_their_positions():
    y = 0.02 * np.arange(60.0) + np.sin(np.arange(60.0))
    y[10:14] = np.nan
    fit, low, high = ols_band(y, np.array([0.0, 30.0, 59.0]))
    r = ols_trend(y)
    np.testing.assert_allclose(fit, r.slope * np.array([0.0, 30.0, 59.0]) + r.intercept)
    assert np.all(low < fit) and np.all(fit < high)


def test_flat_exact_line_has_a_zero_width_band():
    fit, low, high = ols_band(2.0 + 0.5 * np.arange(10.0), np.array([0.0, 5.0, 9.0]))
    np.testing.assert_allclose(high - low, 0.0, atol=1e-9)


def test_benjamini_hochberg_matches_the_textbook_example():
    p = np.array([0.01, 0.04, 0.03, 0.005, np.nan])
    adj = benjamini_hochberg(p)
    assert np.allclose(adj[:4], [0.02, 0.04, 0.04, 0.02])
    assert np.isnan(adj[4])
    assert np.allclose(adj[:4], stats.false_discovery_control(p[:4], method="bh"))


def test_benjamini_hochberg_keeps_false_alarms_near_five_percent():
    flagged = 0
    for _ in range(200):
        p = RNG.uniform(0, 1, 50)
        flagged += (benjamini_hochberg(p) < 0.05).any()
    assert flagged / 200 < 0.10
