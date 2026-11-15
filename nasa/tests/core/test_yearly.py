"""Golden tests for the yearly view of summarise(). Known answers, no tolerance loosened."""

import numpy as np
import pytest

from trend_detective.core.summary import summarise


def test_noiseless_yearly_slope_is_recovered_per_decade():
    years = np.arange(40, dtype=float)
    y = 0.05 * years  # 0.05 units per year = 0.5 per decade, no noise
    s = summarise(y, "K", "x", steps_per_year=1)
    assert s.ols_per_decade == pytest.approx(0.5, abs=1e-9)
    assert s.sen_per_decade == pytest.approx(0.5, abs=1e-9)
    assert s.ols_significant


def test_yearly_series_is_not_deseasonalised():
    # Deseasonalising one value per year would remove the whole trend (each calendar slot has one
    # value). The yearly path must keep it, so the slope above is still 0.5 per decade.
    y = 0.05 * np.arange(20, dtype=float)
    s = summarise(y, "K", "x", steps_per_year=1)
    assert s.ols_per_decade == pytest.approx(0.5, abs=1e-9)


def test_short_yearly_record_gives_no_trend():
    s = summarise(np.array([1.0, np.nan, 2.0]), "K", "x", steps_per_year=1)
    assert np.isnan(s.ols_per_decade)
    assert "three years" in s.sentence


def test_yearly_record_under_ten_years_gets_a_warning():
    s = summarise(0.05 * np.arange(6, dtype=float), "K", "x", steps_per_year=1)
    assert any("Only" in w and "years of data" in w for w in s.warnings)


def test_bad_steps_per_year_is_rejected():
    with pytest.raises(ValueError):
        summarise(np.arange(30, dtype=float), "K", "x", steps_per_year=4)
