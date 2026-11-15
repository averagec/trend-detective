"""Golden tests for additions to core/trend.py: r1 on the OLS result, the Benjamini-Hochberg
paper example, and the autocorrelation-aware Mann-Kendall test.

Kept apart from test_trend.py so that file stays exactly as the golden reference. Each test uses
its own seeded generator, so the results do not depend on test order.
"""

import numpy as np
from scipy import stats

from trend_detective.core.trend import ols_trend

MONTHS = 12 * 20  # 20 years of monthly data


def ar1(n, phi, rng, burn=100):
    """Stationary AR(1) noise with unit innovations."""
    e = rng.normal(0, 1, n + burn)
    x = np.zeros(n + burn)
    for k in range(1, n + burn):
        x[k] = phi * x[k - 1] + e[k]
    return x[burn:]


# --- r1 and n_eff on the OLS result (exposed so the page can explain the adjustment) ---------


def test_r1_and_n_eff_on_a_hand_worked_series():
    # y = [1, 1, 0, 0, 1, 1]: the slope is 0 by symmetry, so the residuals are y - 2/3 and
    # sum(r[i] r[i+1]) = 2/9, sum(r^2) = 4/3, hence r1 = 1/6 and n_eff = 6 (5/6) / (7/6) = 30/7.
    r = ols_trend(np.array([1.0, 1.0, 0.0, 0.0, 1.0, 1.0]))
    assert abs(r.slope) < 1e-12
    assert abs(r.r1 - 1 / 6) < 1e-12
    assert abs(r.n_eff - 30 / 7) < 1e-12


def test_negative_autocorrelation_is_floored_at_zero():
    # y = [0, 1, 0, 1, 0]: residual r1 is -0.8. It is not used to shrink the uncertainty,
    # so r1 is reported as 0 and n_eff stays n.
    r = ols_trend(np.array([0.0, 1.0, 0.0, 1.0, 0.0]))
    assert r.r1 == 0.0
    assert r.n_eff == 5.0


def test_n_eff_always_follows_from_r1():
    rng = np.random.default_rng(1)
    for phi in (0.0, 0.4, 0.8):
        r = ols_trend(ar1(300, phi, rng))
        expected = max(r.n * (1 - r.r1) / (1 + r.r1), 3.0)
        assert abs(r.n_eff - expected) < 1e-9
        assert 0.0 <= r.r1 < 1.0


# --- summarise(leading_pad): front padding is not a gap in the record ------------------------


def test_leading_pad_is_not_counted_as_missing_months():
    from trend_detective.core.summary import summarise

    # 11 NaN months align the first value to December; 24 real months follow: no gaps at all
    y = np.concatenate([np.full(11, np.nan), np.sin(np.arange(24.0))])
    assert any("missing" in w for w in summarise(y, "K", "x").warnings)  # 31% without the hint
    assert not any("missing" in w for w in summarise(y, "K", "x", leading_pad=11).warnings)
    # a real gap after the padding is still reported
    y[20:26] = np.nan
    assert any("missing" in w for w in summarise(y, "K", "x", leading_pad=11).warnings)


# --- Benjamini-Hochberg: the worked example of the original paper ----------------------------


def test_benjamini_hochberg_1995_paper_example():
    from scipy import stats

    from trend_detective.core.trend import benjamini_hochberg

    # 15 p-values from Benjamini & Hochberg (1995). Adjusted value of the i-th smallest is
    # min over j >= i of p_j * 15 / j. Worked by hand (rank: p * 15 / rank):
    #   1: .0015  2: .003  3: .0095  4: .035625  5: .0603  6: .0695  7: .063857...  8: .0645
    #   9: .0765  10: .486  11: .581182  12: .714875  13: .753231  14: .813214  15: 1
    # Ranks 6 and 7 show the running minimum: .0695 is replaced by rank 7's .063857...
    p = np.array([0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344, 0.0459,
                  0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.0000])  # fmt: skip
    expected = np.array([0.0015, 0.003, 0.0095, 0.035625, 0.0603, 0.0298 * 15 / 7,
                         0.0298 * 15 / 7, 0.0645, 0.0765, 0.486, 0.4262 * 15 / 11,
                         0.5719 * 15 / 12, 0.6528 * 15 / 13, 0.7590 * 15 / 14, 1.0])  # fmt: skip
    np.testing.assert_allclose(benjamini_hochberg(p), expected, rtol=1e-12)
    # input order must not matter: the adjusted values follow their p-values
    order = np.random.default_rng(0).permutation(15)
    np.testing.assert_allclose(benjamini_hochberg(p[order]), expected[order], rtol=1e-12)
    np.testing.assert_allclose(benjamini_hochberg(p), stats.false_discovery_control(p), rtol=1e-12)
    # at q < 0.05 the paper's procedure rejects the 4 smallest p-values (and no more)
    assert (benjamini_hochberg(p) < 0.05).sum() == 4


def test_benjamini_hochberg_never_lowers_a_p_value_and_keeps_order():
    from trend_detective.core.trend import benjamini_hochberg

    p = np.random.default_rng(3).uniform(0, 1, 40)
    q = benjamini_hochberg(p)
    assert np.all(q >= p - 1e-15) and np.all(q <= 1.0)
    i, j = np.argsort(p)[:-1], np.argsort(p)[1:]
    assert np.all(q[i] <= q[j] + 1e-15)  # a larger p never gets a smaller q


# --- Autocorrelation-aware Mann-Kendall (docs/decisions/0007) --------------------------------


def independent_r1_of_sen_residuals(y):
    """r1 computed from scratch for a gap-free series: no code shared with core."""
    n = len(y)
    pair_slopes = [(y[j] - y[i]) / (j - i) for i in range(n) for j in range(i + 1, n)]
    b = float(np.median(pair_slopes))
    e = np.array(y) - b * np.arange(n)
    e = e - e.mean()
    return max(float(np.sum(e[:-1] * e[1:]) / np.sum(e * e)), 0.0)


def test_mk_ar1_follows_the_stated_formula():
    from trend_detective.core.trend import mann_kendall, mann_kendall_ar1

    rng = np.random.default_rng(11)
    y = 0.02 * np.arange(60) + ar1(60, 0.6, rng)
    r1 = independent_r1_of_sen_residuals(y)
    assert r1 > 0.2  # the case is a real test of the adjustment
    # the plain test gives z (z = (S -/+ 1) / sqrt(Var S)); the adjusted one divides by sqrt(f)
    z = stats.norm.isf(mann_kendall(y).p_value / 2)
    f = (1 + r1) / (1 - r1)  # n / n_eff
    expected = 2 * stats.norm.sf(z / np.sqrt(f))
    result = mann_kendall_ar1(y)
    assert abs(result.p_value - expected) < 1e-12
    assert abs(result.r1 - r1) < 1e-12
    assert abs(result.n_eff - 60 * (1 - r1) / (1 + r1)) < 1e-9
    assert result.method == "mann-kendall-ar1" and result.n == 60


def test_mk_ar1_equals_the_plain_test_when_r1_is_not_positive():
    from trend_detective.core.trend import mann_kendall, mann_kendall_ar1

    y = 0.001 * np.arange(60) + np.where(np.arange(60) % 2 == 0, 1.0, -1.0)  # alternating
    assert independent_r1_of_sen_residuals(y) == 0.0  # negative autocorrelation is floored
    plain, adjusted = mann_kendall(y), mann_kendall_ar1(y)
    assert adjusted.p_value == plain.p_value
    assert adjusted.n_eff == 60.0 and adjusted.r1 == 0.0
    assert adjusted.slope == plain.slope


def test_mk_ar1_on_a_perfect_line_matches_the_hand_computed_value():
    from trend_detective.core.trend import mann_kendall_ar1

    # y = 1..6: S = 15 and Var(S) = 6 * 5 * 17 / 18 = 28.333; the Sen residuals are constant,
    # so r1 = 0 and z = (15 - 1) / sqrt(28.333) = 2.6300, p = 0.008536
    result = mann_kendall_ar1(np.arange(1.0, 7.0))
    assert result.r1 == 0.0 and result.slope == 1.0
    assert abs(result.p_value - 2 * stats.norm.sf(14 / np.sqrt(510 / 18))) < 1e-12
    assert abs(result.p_value - 0.008536) < 1e-5


def test_mk_ar1_is_never_more_significant_than_the_plain_test():
    from trend_detective.core.trend import mann_kendall, mann_kendall_ar1

    rng = np.random.default_rng(5)
    for k in range(60):
        y = ar1(90, [0.0, 0.3, 0.6, 0.85][k % 4], rng) + rng.uniform(0, 0.03) * np.arange(90)
        assert mann_kendall_ar1(y).p_value >= mann_kendall(y).p_value - 1e-15


def test_mk_ar1_white_noise_is_rarely_significant():
    from trend_detective.core.trend import mann_kendall_ar1

    rng = np.random.default_rng(21)
    hits = sum(mann_kendall_ar1(rng.normal(0, 1, MONTHS)).p_value < 0.05 for _ in range(300))
    assert hits / 300 < 0.10  # nominal 5%; 3% measured (docs/decisions/0007)


def test_mk_ar1_trend_free_ar1_noise_is_less_often_significant_than_the_plain_test():
    from trend_detective.core.trend import mann_kendall, mann_kendall_ar1

    rng = np.random.default_rng(34)
    runs, plain, adjusted = 300, 0, 0
    for _ in range(runs):
        y = ar1(MONTHS, 0.6, rng)  # no trend at all
        plain += mann_kendall(y).p_value < 0.05
        adjusted += mann_kendall_ar1(y).p_value < 0.05
    assert plain / runs > 0.20  # the plain test is badly over-confident here (29% measured)
    assert adjusted / runs < 0.10  # the adjusted one is close to the nominal 5%
    assert adjusted < plain / 2


def test_mk_ar1_still_finds_a_real_trend_in_autocorrelated_data():
    from trend_detective.core.trend import mann_kendall_ar1

    rng = np.random.default_rng(8)
    hits = 0
    for _ in range(100):
        hits += mann_kendall_ar1(0.01 * np.arange(MONTHS) + ar1(MONTHS, 0.3, rng)).p_value < 0.05
    assert hits / 100 > 0.90  # clear trend, mild memory: power stays high
    one = mann_kendall_ar1(0.01 * np.arange(MONTHS) + ar1(MONTHS, 0.3, rng))
    assert abs(one.slope - 0.01) < 0.003


def test_mk_ar1_ignores_missing_values_and_needs_three():
    import pytest

    from trend_detective.core.trend import mann_kendall_ar1

    y = 0.05 * np.arange(40.0) + np.sin(np.arange(40.0))
    y[[5, 6, 20]] = np.nan
    assert mann_kendall_ar1(y).n == 37
    with pytest.raises(ValueError):
        mann_kendall_ar1(np.array([1.0, np.nan, 2.0]))


def test_mk_ar1_constant_series_is_not_significant():
    from trend_detective.core.trend import mann_kendall_ar1

    result = mann_kendall_ar1(np.full(50, 3.0))
    assert result.p_value == 1.0 and result.slope == 0.0


def test_summary_reports_both_mann_kendall_p_values():
    from trend_detective.core.summary import summarise

    rng = np.random.default_rng(2)
    # ten years of monthly anomalies with strong memory and no trend, on a seasonal cycle
    y = 280 + 3 * np.sin(2 * np.pi * np.arange(240) / 12) + 3 * ar1(240, 0.8, rng)
    s = summarise(y, "K", "x")
    assert s.mk_p_ar1 >= s.mk_p  # the adjusted p-value is never smaller
    assert s.mk_ar1_significant == (s.mk_p_ar1 < 0.05)
    assert s.mk_significant == (s.mk_p < 0.05)  # the existing flag keeps its meaning
    short = summarise(y[:20], "K", "x")
    assert np.isnan(short.mk_p_ar1) and short.mk_ar1_significant is False
