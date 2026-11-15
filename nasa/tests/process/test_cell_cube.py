"""Golden check: the per-cell cube reproduces the trend found by hand for the Jakarta cell.

The reference values came from reading the raw MERRA-2 files directly for the cell centred at
(-6.0, 106.875), over 561 months from 1980-01 to 2026-09. If this test fails, the cube or the
cleaning changed; do not loosen the tolerances, find the cause.
"""

import numpy as np
import pytest

from trend_detective.core.trend import deseasonalize, mann_kendall, ols_trend
from trend_detective.process.cell_cube import OUT, load

CELL_LAT, CELL_LON = -6.0, 106.875
REFERENCE = {
    # variable: (OLS slope per decade, Mann-Kendall (Sen) slope per decade), in data units
    "t2m": (0.1645, 0.164),
    "precip": (0.3276, 0.2289),
}

cube_path = OUT / "merra2_idn.npz"
pytestmark = pytest.mark.skipif(not cube_path.exists(), reason="cell cube not built yet")


@pytest.fixture(scope="module")
def cube():
    return load(cube_path)


def cell_index(cube):
    i = int(np.argmin(np.abs(cube.lat - CELL_LAT)))
    j = int(np.argmin(np.abs(cube.lon - CELL_LON)))
    return i, j


def test_cell_centre_is_the_jakarta_cell(cube):
    i, j = cell_index(cube)
    assert cube.lat[i] == pytest.approx(CELL_LAT)
    assert cube.lon[j] == pytest.approx(CELL_LON)


def test_record_length_and_no_gaps(cube):
    for variable in REFERENCE:
        assert len(cube.periods[variable]) == 561
        assert cube.periods[variable][0] == "198001"
        assert cube.periods[variable][-1] == "202609"
        i, j = cell_index(cube)
        assert np.isfinite(cube.values[variable][:, i, j]).all()


@pytest.mark.parametrize("variable", sorted(REFERENCE))
def test_cell_trend_matches_reference(cube, variable):
    i, j = cell_index(cube)
    series = cube.values[variable][:, i, j].astype(float)
    anomalies = deseasonalize(series)
    ols = ols_trend(anomalies)
    mk = mann_kendall(anomalies)
    expected_ols, expected_sen = REFERENCE[variable]
    assert ols.slope * 120 == pytest.approx(expected_ols, abs=5e-4)
    assert mk.slope * 120 == pytest.approx(expected_sen, abs=5e-4)
    assert ols.p_value < 0.05  # both were significant at 95% in the reference run
