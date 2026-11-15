"""Golden tests for core/events.py and core/comovement.py. Known answers on constructed series.

Never loosen a tolerance here to make a change pass; fix the code or open an ADR.
"""

import numpy as np
import pytest

from trend_detective.core.comovement import comovement
from trend_detective.core.events import (
    assess,
    complete_annual_totals,
    percentile_rank,
    same_month_values,
)

MONTHS = 40 * 12  # 1980-01 to 2019-12


def constant_totals(value: float = 100.0, months: int = MONTHS) -> np.ndarray:
    return np.full(months, value)


def test_percentile_rank_known_values():
    base = np.arange(1.0, 11.0)  # 1..10
    assert percentile_rank(10.0, base) == pytest.approx(100.0)
    assert percentile_rank(5.0, base) == pytest.approx(50.0)
    assert percentile_rank(0.5, base) == pytest.approx(0.0)
    assert percentile_rank(5.0, np.array([1.0, np.nan, 5.0])) == pytest.approx(100.0)
    assert np.isnan(percentile_rank(np.nan, base))


def test_same_month_values_picks_the_calendar_month():
    totals = np.arange(36, dtype=float)  # 3 years, index = month
    assert list(same_month_values(totals, 6)) == [6.0, 18.0, 30.0]  # every July
    assert list(same_month_values(totals, 18)) == [6.0, 18.0, 30.0]  # index 18 is also July


def test_partial_years_are_left_out_of_the_annual_baseline():
    totals = np.ones(26)  # two full years and two months
    assert complete_annual_totals(totals).tolist() == [12.0, 12.0]


def test_a_single_spike_month_is_a_one_time_flood():
    rng = np.random.default_rng(0)
    rate = 3.0 + rng.normal(0, 0.3, MONTHS)  # no trend
    totals = rate * 30.0
    spike = 35 * 12 + 6  # July 2015
    totals[spike] = 30.0 * 14.0
    rate[spike] = 14.0
    res = assess(totals, rate, [spike], "flood", "month")
    assert res.extreme
    assert res.percentile == pytest.approx(100.0)
    assert res.call == "one_time_event"
    assert res.trend_direction == "none"
    assert res.amount_mm > 0 and res.percent > 0


def test_extreme_in_a_wetting_trend_is_called_consistent_with_the_trend():
    rng = np.random.default_rng(1)
    t = np.arange(MONTHS, dtype=float)
    rate = 3.0 + 0.0015 * t + rng.normal(0, 0.4, MONTHS)  # clear wetting trend
    totals = rate * 30.0
    last_july = 39 * 12 + 6
    totals[last_july] = 30.0 * (rate[last_july] + 6.0)
    rate[last_july] = totals[last_july] / 30.0
    res = assess(totals, rate, [last_july], "flood", "month")
    assert res.trend_direction == "wetter"
    assert res.trend_p_value < 0.05
    assert res.call == "extreme_in_trend"


def test_a_dry_month_is_a_drought_with_a_negative_amount():
    totals = constant_totals(100.0)
    totals[12 * 30 + 1] = 40.0  # a very dry February
    rate = totals / 30.0
    res = assess(totals, rate, [12 * 30 + 1], "drought", "month")
    assert res.extreme
    assert res.percentile <= 10.0  # 40 mm is below every other February
    assert res.amount_mm == pytest.approx(-60.0)
    assert res.percent == pytest.approx(-60.0)
    assert res.call == "one_time_event"


def test_a_normal_month_is_not_unusual():
    rng = np.random.default_rng(3)
    totals = rng.normal(100.0, 5.0, MONTHS)
    idx = 12 * 30 + 6
    totals[idx] = np.median(same_month_values(totals, idx))  # sits at the median
    res = assess(totals, totals / 30.0, [idx], "flood", "month")
    assert 40.0 <= res.percentile <= 60.0
    assert not res.extreme
    assert res.call == "not_unusual"


def test_year_amount_is_the_observed_total_minus_the_median_annual_total():
    totals = constant_totals(100.0)
    start = 30 * 12
    totals[start : start + 12] = 80.0  # a dry year: 960 mm against a median of 1200 mm
    indices = list(range(start, start + 12))
    res = assess(totals, totals / 30.0, indices, "drought", "year")
    assert res.observed_mm == pytest.approx(960.0)
    assert res.median_mm == pytest.approx(1200.0)
    assert res.amount_mm == pytest.approx(-240.0)
    assert res.percent == pytest.approx(-20.0)
    assert res.extreme
    assert res.peak is not None and res.peak.index in indices


def test_year_needs_twelve_indices_and_month_needs_one():
    totals = constant_totals()
    with pytest.raises(ValueError):
        assess(totals, totals, [1, 2], "flood", "year")
    with pytest.raises(ValueError):
        assess(totals, totals, [1, 2], "flood", "month")


def test_incident_must_be_flood_or_drought():
    totals = constant_totals()
    with pytest.raises(ValueError):
        assess(totals, totals, [0], "heatwave", "month")


def test_comovement_of_an_exact_linear_relation():
    x = np.sin(np.arange(120) / 3.0)
    y = 2.0 * x
    res = comovement(y, x, [5, 6, 7])
    assert res.r == pytest.approx(1.0, abs=1e-9)
    assert res.slope == pytest.approx(2.0, abs=1e-9)
    assert res.period_anomaly == pytest.approx(np.nanmean(x[[5, 6, 7]]))
    assert res.implied_change == pytest.approx(2.0 * res.period_anomaly)
    assert res.p_value < 1e-6


def test_comovement_of_an_opposite_relation_is_negative():
    x = np.sin(np.arange(120) / 3.0)
    res = comovement(-x, x, [0])
    assert res.r == pytest.approx(-1.0, abs=1e-9)
    assert res.slope == pytest.approx(-1.0, abs=1e-9)


def test_comovement_of_independent_noise_is_not_significant():
    rng = np.random.default_rng(2)
    res = comovement(rng.normal(size=240), rng.normal(size=240), [10])
    assert abs(res.r) < 0.3
    assert res.p_value > 0.01


def test_comovement_needs_enough_shared_months():
    x = np.array([1.0, np.nan, 3.0, 4.0] + [np.nan] * 20)
    with pytest.raises(ValueError):
        comovement(x, x, [0])


def test_comovement_requires_the_same_timeline():
    with pytest.raises(ValueError):
        comovement(np.ones(12), np.ones(13), [0])
