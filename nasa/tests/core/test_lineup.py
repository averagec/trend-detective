"""Golden tests for the noise lineup and the case verdict (core/lineup.py).

Series are built from known parts (a seasonal cycle, a straight trend, AR(1) noise) so the right
answer is known. Never loosen a tolerance here to make a change pass.
"""

from __future__ import annotations

import numpy as np

from trend_detective.core.lineup import (
    VERDICTS,
    _later_start_check,
    _leave_one_year_out,
    judge_case,
)
from trend_detective.core.trend import deseasonalize


def series(years: int, per_decade: float, noise: float = 0.5, phi: float = 0.3, seed: int = 0):
    """Seasonal cycle + straight trend + AR(1) noise, starting in January."""
    rng = np.random.default_rng(seed)
    n = years * 12
    e = rng.normal(0.0, noise, n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return 8.0 * np.sin(np.arange(n) * 2 * np.pi / 12) + x + per_decade / 120.0 * np.arange(n)


def checks(result) -> dict[str, bool]:
    return {c.code: c.ok for c in result.checks}


def test_clear_trend_is_detected_and_beats_every_fake():
    r = judge_case(series(30, 1.5), "mm", "Sea level", first_year=1990)
    assert r.verdict == "detected"
    assert r.lineup.beat == 0
    assert all(c.ok for c in r.checks)
    assert r.assessment.verdict == "rise"
    assert abs(r.summary.ols_per_decade - 1.5) < 0.3
    assert r.years_needed is None


def test_a_falling_trend_is_detected_too():
    r = judge_case(series(30, -1.5), "mm", "Sea level", first_year=1990)
    assert r.verdict == "detected"
    assert r.assessment.verdict == "fall"


def test_pure_noise_is_not_detected_and_says_how_long_it_would_take_or_none():
    r = judge_case(series(30, 0.0, seed=3), "mm", "Noise", first_year=1990)
    assert r.verdict == "not_detected"
    assert r.lineup.share >= 0.05
    assert r.lineup.n_sims == 1000 and r.lineup.sims_per_decade.size == 1000


def test_record_under_ten_years_is_never_detected():
    r = judge_case(series(6, 3.0), "mm", "Short", first_year=2010)
    assert r.verdict == "not_detected"
    assert checks(r)["record_length"] is False
    assert r.years_needed == 10.0


def test_same_record_gets_the_same_lineup():
    v = series(20, 0.3, seed=5)
    a = judge_case(v, "mm", "x", first_year=2000)
    b = judge_case(v.copy(), "mm", "x", first_year=2000)
    assert np.array_equal(a.lineup.sims_per_decade, b.lineup.sims_per_decade)
    assert a.verdict == b.verdict


def test_fakes_have_no_trend_and_the_real_slope_is_not_among_the_typical_ones():
    r = judge_case(series(30, 1.5), "mm", "x", first_year=1990)
    sims = r.lineup.sims_per_decade
    assert abs(float(np.mean(sims))) < 0.1  # trend-free on average
    assert abs(r.lineup.observed_per_decade) > np.max(np.abs(sims))


def test_lineup_false_alarm_rate_is_near_five_percent():
    """On records with NO trend, about 5% should beat 95% of the fakes' strength."""
    hits = 0
    runs = 80
    for k in range(runs):
        v = series(25, 0.0, phi=0.4, seed=100 + k)
        r = judge_case(v, "u", "x", first_year=1990, n_sims=200)
        hits += r.lineup.share < 0.05
    assert hits / runs < 0.15


def test_leave_one_year_out_flags_a_slope_that_one_year_carries():
    """A flat record with one huge last year has a slope only because of that year."""
    flat = series(12, 0.0, noise=0.2, seed=1)
    flat[-12:] += 30.0
    check = _leave_one_year_out(flat, flat - np.nanmean(flat), active=True)
    assert check.ok is False
    assert check.code == "one_year"
    assert "year 12" in check.text


def test_leave_one_year_out_passes_a_steady_trend():
    v = series(30, 1.5)
    assert _leave_one_year_out(v, deseasonalize(v), active=True).ok is True


def test_later_start_check_flags_a_trend_that_only_exists_early():
    v = series(30, 0.0, noise=0.3, seed=2)
    v[: 10 * 12] += np.linspace(8.0, 0.0, 10 * 12)  # a fall in the first ten years, flat after
    check = _later_start_check(v, 30.0, -1.0, active=True)
    assert check.ok is False


def test_instrument_change_inside_the_window_makes_a_significant_trend_suspect():
    v = series(24, 1.5)
    r = judge_case(v, "cm", "Water", first_year=2002, gap_years=(2017, 2018))
    assert r.verdict == "suspect"
    assert checks(r)["instrument_change"] is False
    clear = judge_case(v[: 12 * 12], "cm", "Water", first_year=2002, gap_years=(2017, 2018))
    assert checks(clear)["instrument_change"] is True


def test_missing_months_are_allowed():
    v = series(30, 1.5)
    v[::7] = np.nan
    r = judge_case(v, "mm", "Gappy", first_year=1990)
    assert r.verdict == "detected"


def test_too_little_data_is_not_detected_and_has_no_lineup():
    v = np.full(60, np.nan)
    v[:10] = np.arange(10.0)
    r = judge_case(v, "mm", "Nearly empty", first_year=2000)
    assert r.verdict == "not_detected"
    assert r.lineup is None and r.checks == ()


def test_verdict_is_always_one_of_the_three_labels():
    for slope in (-2.0, 0.0, 2.0):
        assert judge_case(series(15, slope, seed=2), "u", "x", first_year=2000).verdict in VERDICTS
