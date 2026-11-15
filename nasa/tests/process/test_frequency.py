"""Tests for the yearly aggregation (process/frequency.py)."""

import numpy as np

from trend_detective.process.frequency import to_yearly


def _periods(start_year: int, n_years: int) -> list[str]:
    return [f"{y}-{m:02d}" for y in range(start_year, start_year + n_years) for m in range(1, 13)]


def test_full_years_give_the_annual_mean():
    periods = _periods(2000, 2)
    values = np.array([1.0] * 12 + [3.0] * 12)
    years, annual = to_yearly(periods, values)
    assert years == [2000, 2001]
    assert np.allclose(annual, [1.0, 3.0])


def test_year_with_fewer_than_ten_valid_months_is_nan():
    periods = _periods(2000, 2)
    values = np.array([1.0] * 12 + [3.0] * 12)
    values[:3] = np.nan  # 2000 has 9 valid months
    years, annual = to_yearly(periods, values)
    assert np.isnan(annual[0])
    assert annual[1] == 3.0


def test_accepts_yyyymm_periods_too():
    periods = [f"2000{m:02d}" for m in range(1, 13)]
    years, annual = to_yearly(periods, np.full(12, 2.0))
    assert years == [2000] and annual[0] == 2.0
