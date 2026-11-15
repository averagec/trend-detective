"""Tests for the selection engine: city cell, circle rule, timeline, mask, mixed-signal warning."""

import numpy as np
import pytest

from trend_detective.process.cell_cube import OUT, load
from trend_detective.process.selection import (
    Grid,
    SelectionError,
    analyse_circle,
    analyse_city,
    circle_cells,
    city_cell,
    to_timeline,
)

JAKARTA = (-6.1805357, 106.8280366)  # place pin from the Google Maps link
MERRA = Grid(lat=-12.0 + 0.5 * np.arange(39), lon=94.375 + 0.625 * np.arange(77))  # cube grid


def monthly_periods(first_year: int, years: int) -> list[str]:
    return [f"{first_year + i // 12:04d}{i % 12 + 1:02d}" for i in range(12 * years)]


def trending_cube(slopes: np.ndarray, years: int = 24, seed: int = 3) -> np.ndarray:
    """Synthetic monthly values (months, lat, lon): one linear trend per cell plus noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(12 * years, dtype=float)[:, None, None]
    season = 3.0 * np.sin(2 * np.pi * t / 12)
    return 290.0 + slopes[None] * t + season + rng.normal(0, 0.3, (12 * years, *slopes.shape))


def test_city_cell_is_the_jakarta_cell():
    cell = city_cell(MERRA, *JAKARTA)
    assert cell.lat == pytest.approx(-6.0)
    assert cell.lon == pytest.approx(106.875)
    assert cell.width_km == pytest.approx(69, abs=1.5)
    assert cell.height_km == pytest.approx(55.6, abs=0.5)


def test_city_outside_grid_is_refused():
    with pytest.raises(SelectionError):
        city_cell(MERRA, 40.0, 10.0)


@pytest.mark.parametrize("radius", [74.9, 250.1, 0.0, 1000.0])
def test_radius_outside_75_to_250_km_is_refused(radius):
    with pytest.raises(SelectionError, match="radius must be 75 to 250"):
        circle_cells(MERRA, *JAKARTA, radius)


def test_circle_at_jakarta_holds_four_cells_at_75_km_and_52_at_250():
    assert len(circle_cells(MERRA, *JAKARTA, 75.0)) == 4
    assert len(circle_cells(MERRA, *JAKARTA, 250.0)) == 52


def test_every_75_km_circle_in_a_random_sample_has_at_least_four_cells():
    rng = np.random.default_rng(1)
    for _ in range(50):
        lat = rng.uniform(-11, 6)
        lon = rng.uniform(95, 141)
        assert len(circle_cells(MERRA, lat, lon, 75.0)) >= 4


def test_circle_with_too_few_cells_is_refused():
    tiny = Grid(lat=np.array([0.0, 0.5]), lon=np.array([0.0, 0.625]))
    with pytest.raises(SelectionError, match="at least 4"):
        circle_cells(tiny, 0.0, 0.0, 75.0)


def test_series_must_start_in_january():
    with pytest.raises(SelectionError, match="January"):
        to_timeline(["199002", "199003"], np.array([1.0, 2.0]))


def test_missing_month_becomes_nan_on_the_timeline():
    periods = ["199001", "199002", "199004"]
    full = to_timeline(periods, np.array([1.0, 2.0, 4.0]))
    assert full.size == 4
    assert np.isnan(full[2])
    assert full[3] == 4.0


def test_uniform_circle_has_no_mixed_warning():
    periods = monthly_periods(1990, 24)
    slopes = np.full((39, 77), 0.002)
    values = trending_cube(slopes)
    result = analyse_circle(values, periods, MERRA, *JAKARTA, 100.0, "K", "Test circle")
    assert result.cells_used == result.cells_in_circle
    assert result.rising == result.cells_used
    assert result.falling == 0
    assert not any("Mixed signal" in w for w in result.warnings)
    assert result.average.ols_per_decade == pytest.approx(0.24, abs=0.05)


def test_mixed_circle_warns_that_the_average_hides_the_signal():
    periods = monthly_periods(1990, 24)
    slopes = np.zeros((39, 77))
    west_cut = city_cell(MERRA, *JAKARTA).j
    slopes[:, :west_cut] = 0.003  # western cells rise
    slopes[:, west_cut:] = -0.003  # eastern cells fall
    values = trending_cube(slopes)
    result = analyse_circle(values, periods, MERRA, *JAKARTA, 250.0, "K", "Mixed circle")
    assert result.rising > 0 and result.falling > 0
    assert any("Mixed signal" in w for w in result.warnings)


def test_cell_with_no_data_is_dropped_and_reported():
    periods = monthly_periods(1990, 24)
    values = trending_cube(np.full((39, 77), 0.002))
    cell = city_cell(MERRA, *JAKARTA)
    values[:, cell.i, cell.j - 1] = np.nan
    result = analyse_circle(values, periods, MERRA, *JAKARTA, 100.0, "K", "Gap circle")
    assert result.cells_used == result.cells_in_circle - 1
    assert any("no data in any month" in w for w in result.warnings)


def test_city_result_carries_the_one_cell_scale_warning():
    periods = monthly_periods(1990, 24)
    values = trending_cube(np.full((39, 77), 0.002))
    result = analyse_city(values, periods, MERRA, *JAKARTA, "K", "Jakarta", "Central Jakarta")
    assert result.cell.lat == pytest.approx(-6.0)
    assert any("one grid cell" in w for w in result.warnings)


cube_path = OUT / "merra2_idn.npz"


@pytest.mark.skipif(not cube_path.exists(), reason="cell cube not built yet")
def test_jakarta_city_on_the_real_cube_matches_the_golden_trend():
    cube = load(cube_path)
    grid = Grid(cube.lat, cube.lon)
    result = analyse_city(
        cube.values["t2m"],
        cube.periods["t2m"],
        grid,
        *JAKARTA,
        "K",
        "Central Jakarta",
        "Central Jakarta",
    )
    assert result.summary.ols_per_decade == pytest.approx(0.1645, abs=5e-4)
    assert result.summary.ols_significant
