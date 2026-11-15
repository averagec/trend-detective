"""A circle of independent cells with no real trend must rarely show a mixed-sign warning.

Before the Benjamini-Hochberg fix, each cell was tested at 5% with no correction, so a circle of
about 60 cells showed both a significant rise and a significant fall in about half of the trials.
"""

import numpy as np

from trend_detective.process.selection import Grid, analyse_circle


def _null_cube(seed: int, n_lat: int = 40, n_lon: int = 40, n_months: int = 240):
    rng = np.random.default_rng(seed)
    lat = np.arange(n_lat) * 0.5 - 10.0
    lon = np.arange(n_lon) * 0.5 + 100.0
    t = np.arange(n_months)
    season = 2.0 * np.sin(2 * np.pi * t / 12)[:, None, None]
    values = season + rng.normal(0.0, 1.0, (n_months, n_lat, n_lon))  # independent, no trend
    periods = [f"{1990 + m // 12}{m % 12 + 1:02d}" for m in range(n_months)]
    return values, periods, Grid(lat, lon)


def test_mixed_signal_is_rare_on_null_circles():
    mixed = 0
    trials = 20
    for k in range(trials):
        values, periods, grid = _null_cube(seed=k)
        result = analyse_circle(values, periods, grid, -2.0, 110.0, 250.0, "K", "x")
        assert result.cells_used >= 40
        if any("Mixed signal" in w for w in result.warnings):
            mixed += 1
    assert mixed <= 2, f"mixed-sign warning on {mixed} of {trials} null circles"


def test_expected_per_sign_is_reported():
    values, periods, grid = _null_cube(seed=99)
    result = analyse_circle(values, periods, grid, -2.0, 110.0, 250.0, "K", "x")
    assert result.expected_per_sign == 0.025 * result.cells_used
