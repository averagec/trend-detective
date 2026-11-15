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
    annual_means,
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


# --- the yearly view: yearly averages of the seasonal anomalies -----------------------------------


def test_annual_means_average_the_months_of_each_year_and_drop_thin_years():
    a = np.arange(36, dtype=float)  # three whole years
    assert list(annual_means(a)) == [5.5, 17.5, 29.5]
    thin = a.copy()
    thin[:3] = np.nan  # year 1 keeps 9 months: under the 10 needed
    out = annual_means(thin)
    assert np.isnan(out[0]) and out[1] == 17.5
    ten = a.copy()
    ten[:2] = np.nan  # 10 months left: kept, averaged over those 10 only
    assert annual_means(ten)[0] == np.mean(np.arange(2, 12))


def test_annual_means_handle_a_record_that_does_not_end_in_december():
    out = annual_means(np.arange(30, dtype=float))  # 2.5 years: the half year has 6 months only
    assert out.size == 3 and np.isnan(out[2])


def test_yearly_clear_trend_is_detected_and_its_slope_matches_the_monthly_one():
    v = series(30, 1.5)
    m = judge_case(v, "mm", "x", first_year=1990)
    y = judge_case(v, "mm", "x", first_year=1990, frequency="yearly")
    assert y.frequency == "yearly" and y.verdict == "detected"
    assert y.lineup.n_sims == 1000 and y.lineup.beat == 0
    assert y.summary.n_months == 30  # thirty yearly values
    assert abs(y.summary.ols_per_decade - m.summary.ols_per_decade) < 0.02
    assert y.analysed.size == 30


def test_yearly_has_less_power_than_monthly_on_a_weak_trend():
    """The same record can be significant monthly and not yearly: fewer points, same slope."""
    gaps = 0
    for seed in range(12):
        v = series(25, 0.35, noise=0.8, phi=0.5, seed=seed)
        m = judge_case(v, "u", "x", first_year=1990, n_sims=100)
        y = judge_case(v, "u", "x", first_year=1990, n_sims=100, frequency="yearly")
        assert abs(m.summary.ols_per_decade - y.summary.ols_per_decade) < 0.05
        gaps += m.assessment.significant and not y.assessment.significant
    assert gaps >= 1  # at least one record where monthly sees it and yearly does not


def test_yearly_record_under_ten_years_is_never_detected():
    r = judge_case(series(8, 3.0), "mm", "Short", first_year=2010, frequency="yearly")
    assert r.verdict == "not_detected" and r.years_needed == 10.0
    assert checks(r)["record_length"] is False


def test_yearly_lineup_false_alarm_rate_is_near_five_percent():
    hits = 0
    runs = 80
    for k in range(runs):
        v = series(30, 0.0, phi=0.4, seed=300 + k)
        r = judge_case(v, "u", "x", first_year=1990, n_sims=200, frequency="yearly")
        hits += r.lineup.share < 0.05
    assert hits / runs < 0.15


def test_yearly_same_record_gets_the_same_lineup_and_differs_from_monthly():
    v = series(20, 0.3, seed=5)
    a = judge_case(v, "mm", "x", first_year=2000, frequency="yearly")
    b = judge_case(v.copy(), "mm", "x", first_year=2000, frequency="yearly")
    assert np.array_equal(a.lineup.sims_per_decade, b.lineup.sims_per_decade)
    m = judge_case(v, "mm", "x", first_year=2000)
    assert not np.array_equal(a.lineup.sims_per_decade, m.lineup.sims_per_decade)


def test_yearly_instrument_change_makes_a_significant_trend_suspect():
    v = series(24, 1.5)
    r = judge_case(v, "cm", "Water", first_year=2002, gap_years=(2017, 2018), frequency="yearly")
    assert r.verdict == "suspect" and checks(r)["instrument_change"] is False


def test_yearly_checks_run_in_years():
    flat = series(15, 0.0, noise=0.2, seed=1)
    ann = annual_means(deseasonalize(flat))
    ann[-1] += 30.0  # one huge last year
    assert _leave_one_year_out(ann, ann, active=True, steps_per_year=1).ok is False
    v = series(30, 0.0, noise=0.3, seed=2)
    early = annual_means(deseasonalize(v))
    early[:10] += np.linspace(8.0, 0.0, 10)
    assert _later_start_check(early, 30.0, -1.0, active=True, steps_per_year=1).ok is False


def test_yearly_with_too_few_years_has_no_lineup():
    v = np.full(60, np.nan)
    v[:20] = np.arange(20.0)  # one full year and 8 months: a single yearly value (3 needed)
    r = judge_case(v, "mm", "Tiny", first_year=2000, frequency="yearly")
    assert r.verdict == "not_detected" and r.lineup is None


def test_an_unknown_frequency_is_refused():
    import pytest

    with pytest.raises(ValueError, match="frequency"):
        judge_case(series(10, 1.0), "u", "x", frequency="daily")


# --- the one-sentence headline --------------------------------------------------------------------


def test_headline_for_a_detected_rise_names_the_direction_size_and_reason():
    r = judge_case(series(30, 1.5), "mm", "x", first_year=1990)
    h = r.headline
    assert h.startswith("Rising trend detected: about ")
    assert "mm per decade" in h and "both statistical tests agree" in h.lower()
    assert "none of 1,000 random look-alike records were as strong" in h
    assert h.endswith("it held up in every check.")


def test_headline_for_a_detected_fall_says_falling():
    assert judge_case(series(30, -1.5), "mm", "x", first_year=1990).headline.startswith(
        "Falling trend detected"
    )


def test_headline_for_no_trend_uses_the_repo_wording_and_a_plain_reason():
    h = judge_case(series(30, 0.0, seed=3), "mm", "x", first_year=1990).headline
    assert h.startswith("No significant trend detected (yet): the data are too noisy to confirm")
    assert "could be chance" in h
    assert "small" not in h  # a big slope in a noisy record is not "small"


def _borderline_record():
    """A record whose tests come close to 0.05 but do not pass (found by a fixed search)."""
    for seed in range(200):
        v = series(25, 0.25, noise=0.9, phi=0.5, seed=seed)
        r = judge_case(v, "mm", "x", first_year=1990, n_sims=200)
        p = min(r.assessment.ols_q, r.assessment.mk_q)
        if r.verdict == "not_detected" and r.assessment.verdict == "none" and 0.05 < p < 0.15:
            return r
    raise AssertionError("no borderline record found")


def test_headline_for_a_borderline_result_says_so_and_what_came_close():
    h = _borderline_record().headline
    start = "No significant trend detected (yet), but it is borderline: a rise of about"
    assert h.startswith(start)
    assert "came close but did not pass the tests" in h
    assert "random look-alike records were" in h
    assert h.endswith("More years of data could settle it.")


def test_headline_borderline_mentions_a_lineup_that_looks_significant_on_its_own():
    """Ambon-like: no test passes, but under 5% of the fakes are as strong: say so, not "chance"."""
    for seed in range(300):
        r = judge_case(series(25, 0.25, noise=0.9, phi=0.5, seed=seed), "mm", "x",
                       first_year=1990, n_sims=300)  # fmt: skip
        if r.assessment.verdict == "none" and r.lineup.share < 0.05 and r.verdict == "not_detected":
            assert "only" in r.headline and "were as strong" in r.headline
            assert "borderline" in r.headline
            return
    raise AssertionError("no record with a significant lineup but no significant test found")


def test_headline_for_a_short_record_says_how_many_years_are_needed():
    h = judge_case(series(6, 3.0), "mm", "x", first_year=2010).headline
    assert h.startswith("No significant trend detected (yet): the record is only 6 years long")
    assert "at least 10 are needed" in h


def test_headline_for_a_suspect_case_gives_the_failed_check_in_plain_words():
    h = judge_case(
        series(24, 1.5), "cm", "x", first_year=2002, gap_years=(2017, 2018)
    ).headline
    assert h.startswith("Rising trend found, but treat it with caution")
    assert "the measuring instrument changed during this period" in h


def test_headline_when_there_is_too_little_data():
    v = np.full(60, np.nan)
    v[:10] = np.arange(10.0)
    h = judge_case(v, "mm", "x", first_year=2000).headline
    assert h == "No significant trend detected (yet): there is too little data to judge."


def test_headline_is_one_sentence_per_view_and_never_claims_a_cause():
    for freq in ("monthly", "yearly"):
        for slope in (-2.0, 0.0, 2.0):
            h = judge_case(
                series(25, slope, seed=4), "u", "x", first_year=2000, n_sims=100, frequency=freq
            ).headline
            assert h and "\n" not in h
            for banned in ("prove", "caused by", "because of"):
                assert banned not in h.lower()
