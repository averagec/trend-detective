"""Tests for the plain-language summary. They use synthetic series with known answers."""

import numpy as np

from trend_detective.core.summary import summarise

RNG = np.random.default_rng(7)


def monthly(slope_per_month, years=30, noise=0.3):
    n = 12 * years
    t = np.arange(n)
    season = 4.0 * np.sin(2 * np.pi * t / 12)
    return slope_per_month * t + season + RNG.normal(0, noise, n)


def test_known_warming_is_recovered_per_decade_and_significant():
    s = summarise(monthly(0.01), "K", "Test region temperature")  # 0.01 K/month = 1.2 K/decade
    assert abs(s.ols_per_decade - 1.2) < 0.1
    assert s.ols_ci_per_decade[0] < 1.2 < s.ols_ci_per_decade[1]
    assert "rose" in s.sentence and "statistically significant at 95%" in s.sentence
    assert s.tests_agree
    assert s.warnings == ()


def test_no_trend_gives_the_no_trend_sentence():
    s = summarise(monthly(0.0, noise=1.0), "K", "Test region temperature")
    assert "no significant trend detected (yet)" in s.sentence
    assert "statistically significant" not in s.sentence


def test_short_record_gets_a_warning():
    s = summarise(monthly(0.01, years=6), "K", "Short record")
    assert any("Only 6.0 years" in w for w in s.warnings)


def test_many_missing_months_get_a_warning():
    y = monthly(0.01)
    y[::3] = np.nan  # a third of the months missing
    s = summarise(y, "K", "Gappy record")
    assert any("missing" in w for w in s.warnings)
    assert s.n_months == int(np.isfinite(y).sum())


def test_falling_series_says_fell():
    s = summarise(monthly(-0.01), "mm day-1", "Test rainfall")
    assert "fell" in s.sentence and s.sen_per_decade < 0


def test_one_year_of_data_gives_no_trend_not_a_false_significant_one():
    s = summarise(monthly(0.01, years=1), "K", "One year")
    assert np.isnan(s.ols_per_decade)
    assert not s.ols_significant
    assert "not enough data" in s.sentence


def test_band_has_one_row_per_year_on_the_ols_line():
    s = summarise(monthly(0.01, years=30), "K", "Test region temperature")
    assert [row[0] for row in s.ols_band_by_year] == list(range(30))
    for k, fit, low, high in s.ols_band_by_year:
        assert low < fit < high
        assert fit == np.float64(s.ols_intercept + s.ols_slope_per_month * (12 * k + 6))
    widths = [high - low for _, _, low, high in s.ols_band_by_year]
    assert min(widths) == widths[14] or min(widths) == widths[15]  # narrowest mid-record
    assert widths[0] > widths[14] and widths[-1] > widths[14]


def test_band_stops_before_a_partial_year_that_ends_before_midyear():
    y = monthly(0.01, years=6)[: 12 * 5 + 3]  # 5 years and 3 months
    s = summarise(y, "K", "Partial last year")
    assert [row[0] for row in s.ols_band_by_year] == [0, 1, 2, 3, 4]


def test_no_band_when_there_is_no_trend_to_draw():
    s = summarise(monthly(0.01, years=1), "K", "One year")
    assert s.ols_band_by_year == ()
