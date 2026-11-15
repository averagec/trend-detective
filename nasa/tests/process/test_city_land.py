"""The one-cell city warning states the land share when it is known."""

import numpy as np

from trend_detective.process.selection import Grid, analyse_city


def _cube(n_months=240):
    lat = np.arange(-2.0, 2.01, 0.5)
    lon = np.arange(104.0, 108.01, 0.5)
    rng = np.random.default_rng(5)
    values = rng.normal(0.0, 1.0, (n_months, lat.size, lon.size))
    periods = [f"{1990 + m // 12}{m % 12 + 1:02d}" for m in range(n_months)]
    return values, periods, Grid(lat, lon)


def test_land_share_appears_in_the_warning():
    values, periods, grid = _cube()
    res = analyse_city(values, periods, grid, -0.1, 106.1, "K", "x", "Testville", land_share=0.4)
    assert any("40% of months" in w for w in res.warnings)


def test_no_land_share_means_no_land_sentence():
    values, periods, grid = _cube()
    res = analyse_city(values, periods, grid, -0.1, 106.1, "K", "x", "Testville")
    assert not any("land values" in w for w in res.warnings)
