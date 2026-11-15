"""City series for the CASES flow (process/city_cases.py): nearest cell with data, whole years."""

import numpy as np

from trend_detective.process.city_cases import calendar_years, distance_km, nearest_cell

LATS = np.array([-4.0, -3.5, -3.0])
LONS = np.array([102.5, 103.125])


def cube(n=48):
    return np.arange(n * 6, dtype=float).reshape(n, 3, 2)


def test_distance_is_zero_for_the_same_point_and_about_111_km_per_degree_of_latitude():
    assert distance_km(1.0, 100.0, 1.0, 100.0) == 0.0
    assert abs(distance_km(0.0, 100.0, 1.0, 100.0) - 111.19) < 0.5


def test_nearest_cell_is_the_closest_one_with_data():
    i, j, km = nearest_cell(cube(), LATS, LONS, -3.8, 102.27)
    assert (LATS[i], LONS[j]) == (-4.0, 102.5)
    assert km < 40


def test_a_cell_without_enough_months_is_skipped():
    v = cube()
    v[:, 0, 0] = np.nan  # the nearest cell has no data (an ocean cell for a land variable)
    v[:10, 0, 0] = 1.0  # only 10 months: fewer than 24, still skipped
    i, j, _ = nearest_cell(v, LATS, LONS, -3.8, 102.27)
    assert (i, j) != (0, 0)


def test_no_cell_within_150_km_gives_none():
    assert nearest_cell(cube(), LATS, LONS, 20.0, 120.0) is None
    v = np.full((48, 3, 2), np.nan)
    assert nearest_cell(v, LATS, LONS, -3.8, 102.27) is None


def test_calendar_years_start_in_january_and_mark_missing_months():
    series = np.arange(36, dtype=float)  # 1999-11 to 2002-10
    series[5] = np.nan
    out = calendar_years(series, "199911", 2000, 2001)
    assert len(out) == 24
    assert out[0] == 2.0  # 2000-01 is index 2 of the series
    assert out[3] is None  # 2000-04 is index 5, NaN
    assert out[-1] == 25.0  # 2001-12
    assert calendar_years(series, "199911", 1999, 1999)[:10] == [None] * 10  # before the record
